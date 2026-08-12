"""postflop_ranges.py — P(A|H) postflop por perfil (pegar6, paso 3).

Cierre del hueco documentado en recommend_loop: "Updates bayesianos postflop
con P(A|H)". Conecta la evidencia de mano conocida postflop (observations.py)
con el `RangeState` del motor.

```
hands_db.jsonl
    │  extract_hands()      (street, facing, action, board, cards, hand_known)
    ▼
behavior.py / Oracle        P(A|C) por perfil (sin mano)      → prior
postflop_ranges.py          P(A|H, street, facing, perfil)    → ESTE MÓDULO
    ├─ p_action(..., bucket, action)  → P(A|H) de un bucket de fuerza
    ├─ prob_vec(..., board, action)   → (1326,) → RangeState.update
    │
    ▼
recommend_loop (villain.update(P(A|H)))
```

MÉTODO — FUERZA → BUCKETS + SHRINKAGE AL ORACLE:
1. Para cada board se evalúan los 1326 combos (hand_evaluator), se ordenan
   los scores y se divide en `n_buckets` percentiles (0 = aire, último =
   nuts sobre el board).
2. Las observaciones postflop con mano conocida se agrupan por
   (perfil, street, facing, bucket): el denominador `opp` cuenta las manos
   que llegaron a ese spot; `cnt` las que ejecutaron la acción A.
3. La estimación por bucket es shrinkage hacia el **prior del Oracle**
   (P(A|C) del perfil, con sus fallbacks):

       P(A|H,bucket) = (cnt_bucket + alpha·prior) / (opp_bucket + alpha)

   Con n→0 manda el Oracle; con n grande manda la evidencia de la mano.

Nota (misma lección §6): la DB real tiene 1.043 decisiones con mano
conocida, repartidas por perfil×street×facing×bucket; el grid de buckets
es grueso (5) a propósito para no atomizar la muestra. Leer siempre la `n`
de la casilla.
"""
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

from .behavior import Oracle, build
from .hand_evaluator import evaluate_batch
from .observations import STREETS, extract_hands
from .profile import Profiles
from .ranges import COMBO0, COMBO1, HAND_MASKS, N_COMBOS

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PF_RANGES_PATH = os.path.join(REPO_DIR, 'data', 'postflop_ranges.json')

DEFAULT_ALPHA = 2.0
DEFAULT_BUCKETS = 5
ACTIONS = ('x', 'b', 'c', 'f', 'r')


def _board_ids(board: str):
    """Ids (0..51) de un board '5h,6d,4d'; None si inválido (<3 cartas)."""
    if not board:
        return None
    codes = [c for c in board.split(',') if c]
    if len(codes) < 3:
        return None
    try:
        from .cards import card_id
        ids = np.asarray([card_id(c) for c in codes], dtype=np.intp)
    except ValueError:
        return None
    if len(np.unique(ids)) != len(ids):      # cartas duplicadas: board roto
        return None
    return ids


def _strength_buckets(board_codes, n_buckets=DEFAULT_BUCKETS):
    """Bucket (0..n-1) de fuerza de cada combo legal en `board`.

    Percentiles del score de cada combo (sobre los combos LEGALES, los que
    no chocan con el board); los ilegales quedan en bucket 0 (inertes: el
    RangeState los descarta con su máscara).
    """
    from .hand_evaluator import legal_hands

    board = np.asarray(board_codes, dtype=np.intp)
    known = 0
    for c in board.tolist():
        known |= 1 << int(c)
    ids = legal_hands(known)
    scores = evaluate_batch(np.column_stack([COMBO0[ids], COMBO1[ids]]), board)
    order = np.argsort(scores, kind='stable')
    n_legal = len(ids)
    ranks = np.empty(n_legal, dtype=np.intp)
    ranks[order] = np.arange(n_legal)
    frac = np.clip(ranks / max(n_legal - 1, 1), 0.0, 1.0)
    buckets = np.minimum((frac * n_buckets).astype(np.intp), n_buckets - 1)
    full = np.zeros(N_COMBOS, dtype=np.intp)
    full[ids] = buckets
    return scores, full


class PostflopRangeModel:
    """P(A|H, street, facing, perfil) postflop, buckets de fuerza + Oracle.

    Construcción: from_hands(hands, labels opcional). Consultas:
      p_action(perfil, street, facing, bucket, action) -> float
      prob_vec(perfil, street, facing, board_codes, action) -> (1326,)
    Persistencia: to_json / save / load (data/postflop_ranges.json).
    """

    def __init__(self, alpha: float = DEFAULT_ALPHA,
                 n_buckets: int = DEFAULT_BUCKETS):
        self.alpha = float(alpha)
        self.n_buckets = n_buckets
        self.opp: Dict[Tuple[str, str, str, int], int] = {}
        self.cnt: Dict[Tuple[str, str, str, int, str], int] = {}
        self.labels: Dict[str, str] = {}
        self._oracle = None
        self._scores_cache: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}

    # ------------------------------------------------------------------

    @classmethod
    def from_hands(cls, hands, labels: Optional[Dict[str, str]] = None,
                   alpha: float = DEFAULT_ALPHA,
                   n_buckets: int = DEFAULT_BUCKETS) -> 'PostflopRangeModel':
        """Construye desde las manos (observaciones postflop con mano
        conocida y board válido). `labels`: jugador → perfil (opcional;
        default: estimados por Profiles.from_hands)."""
        if labels is None:
            profs = Profiles.from_hands(hands)
            labels = {name: p.label for name, p in profs.profiles.items()}
        model = cls(alpha=alpha, n_buckets=n_buckets)
        model.labels = dict(labels)
        model._oracle = Oracle(build(hands, labels=model.labels))
        obs = extract_hands(hands)
        for o in obs:
            if not o.hand_known or not o.cards:
                continue
            if o.street == 'preflop':
                continue
            bid = _board_ids(o.board)
            if bid is None:
                continue
            perfil = labels.get(o.player)
            if perfil is None:
                continue
            from .cards import card_id

            cs = o.cards if isinstance(o.cards, (list, tuple)) \
                else [o.cards[i:i + 2] for i in range(0, len(o.cards), 2)]
            cards = np.asarray([card_id(c) for c in cs], dtype=np.intp)
            bucket = model._bucket_of(cards, bid)
            key = (perfil, o.street, o.facing, bucket)
            model.opp[key] = model.opp.get(key, 0) + 1
            akey = key + (o.action,)
            model.cnt[akey] = model.cnt.get(akey, 0) + 1
        return model

    def _bucket_of(self, cards: np.ndarray, board_ids: np.ndarray) -> int:
        """Bucket de fuerza de una mano (2 cartas) sobre el board dado."""
        scores, buckets = self._board_buckets(board_ids)
        b0 = 1 << int(cards[0])
        b1 = 1 << int(cards[1])
        mask = ((HAND_MASKS & b0) != 0) & ((HAND_MASKS & b1) != 0)
        if not mask.any():
            return 0
        idx = int(np.where(mask)[0][0])
        return int(buckets[idx])

    def _board_buckets(self, board_ids: np.ndarray):
        key = board_ids.astype(str).tobytes()
        if key not in self._scores_cache:
            self._scores_cache[key] = _strength_buckets(board_ids,
                                                        self.n_buckets)
        return self._scores_cache[key]

    # ------------------------------------------------------------------

    def _prior(self, perfil: str, street: str, facing: str):
        """P(A|C) del Oracle para el perfil (o población si no hay celda)."""
        if self._oracle is None:
            return None
        res = self._oracle.p_action(perfil, street, facing)
        if res:
            return res['actions']
        return None

    def p_action(self, perfil: str, street: str, facing: str, bucket: int,
                 action: str) -> float:
        """P(A|H) del bucket: cnt+alpha·prior Oracle / (opp+alpha)."""
        key = (perfil, street, facing, bucket)
        opp = self.opp.get(key, 0)
        prior = self._prior(perfil, street, facing)
        if prior is None:
            # sin Oracle (construcción manual): prior plano
            prior = {a: 0.2 for a in ACTIONS} if opp else None
            if prior is None:
                return 0.0
        p0 = prior.get(action, 0.0)
        if opp == 0:
            return p0
        cnt = self.cnt.get(key + (action,), 0)
        return (cnt + self.alpha * p0) / (opp + self.alpha)

    def prob_vec(self, perfil: str, street: str, facing: str,
                 board_codes, action: str) -> np.ndarray:
        """Vector (1326,) de P(A|H) para RangeState.update.

        board_codes: ['Qh','7s','2c'] (ids o códigos 'Ah').
        """
        board = np.asarray([c for c in board_codes])
        if board.dtype.kind in 'US':
            from .cards import card_id
            board = np.asarray([card_id(str(c)) for c in board],
                               dtype=np.intp)
        scores, buckets = self._board_buckets(board)
        out = np.empty(N_COMBOS, dtype=np.float32)
        for b in range(self.n_buckets):
            idx = buckets == b
            out[idx] = self.p_action(perfil, street, facing, b, action)
        return out

    def report(self) -> str:
        lines = ['perfil            street  facing   n   acciones',
                 '-' * 64]
        for key, n in sorted(self.opp.items(),
                             key=lambda kv: -kv[1]):
            perfil, st, facing, b = key
            acts = []
            for a in ACTIONS:
                c = self.cnt.get(key + (a,), 0)
                if c:
                    acts.append(f'{a}:{c}')
            lines.append(f'{perfil:<18}{st:<7} {facing:<7} b{b} {n:>4}   '
                         f'{" ".join(acts[:6])}')
        return '\n'.join(lines)

    # ------------------------------------------------------------------

    def to_json(self) -> dict:
        return {
            'meta': {'alpha': self.alpha, 'n_buckets': self.n_buckets,
                     'origen': 'hands_db.jsonl'},
            'labels': dict(self.labels),
            'opp': {f'{k[0]}|{k[1]}|{k[2]}|{k[3]}': v
                    for k, v in self.opp.items()},
            'cnt': {f'{k[0]}|{k[1]}|{k[2]}|{k[3]}|{k[4]}': v
                    for k, v in self.cnt.items()},
        }

    def save(self, path: str = PF_RANGES_PATH):
        import json

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_json(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str = PF_RANGES_PATH) -> 'PostflopRangeModel':
        import json

        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        model = cls(alpha=data['meta']['alpha'],
                    n_buckets=data['meta']['n_buckets'])
        model.labels = data['labels']
        for k, v in data['opp'].items():
            a, b, c, d = k.split('|')
            model.opp[(a, b, c, int(d))] = v
        for k, v in data['cnt'].items():
            a, b, c, d, e = k.split('|')
            model.cnt[(a, b, c, int(d), e)] = v
        return model


def main(argv=None):
    import sys

    import json

    from .learn import load_hands

    want_json = '--json' in (argv if argv is not None else sys.argv[1:])
    hands = load_hands()
    model = PostflopRangeModel.from_hands(hands)
    print(f'Manos: {len(hands)} · buckets: {model.n_buckets}\n')
    print(model.report())
    if want_json:
        model.save()
        print(f'\n-> {PF_RANGES_PATH}')


if __name__ == '__main__':
    main()