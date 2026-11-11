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

La cantidad de manos, observaciones y celdas se audita por separado en
`tools/auditar_muestra_postflop.py`. `opp` cuenta observaciones, no manos
distintas; leer ambos tamaños en cada consulta. El grid de buckets es grueso
(5) a propósito, pero eso no constituye un intervalo de confianza.
"""
import os
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np

from .behavior import Oracle, build
from .hand_evaluator import evaluate_batch
from .observations import STREETS, extract_hands
from ._procedencia import procedencia
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
        self.n_hands_input = None   # manos recibidas
        self.n_hands_used = None    # manos que aportaron observacion
        self.n_hands_with_known_cards = None
        self.n_hands_with_postflop_observation = None
        self.n_observations_used = None
        self.opp: Dict[Tuple[str, str, str, int], int] = {}
        self.cnt: Dict[Tuple[str, str, str, int, str], int] = {}
        self._cell_hand_counts: Dict[Tuple[str, str, str, int], int] = {}
        self._cell_hand_ids: Dict[Tuple[str, str, str, int], set] = {}
        self._evidence_counts_known = False
        self.labels: Dict[str, str] = {}
        self._oracle = None
        self._oracle_injection_source = 'none'
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
        model.n_hands_input = len(hands)
        model.n_hands_used = 0
        model.labels = dict(labels)
        model._oracle = Oracle(build(hands, labels=model.labels))
        model._oracle_injection_source = 'Oracle built from input hands'
        obs = extract_hands(hands)
        manos_con_obs = set()
        manos_con_obs_postflop = set()
        manos_por_celda = defaultdict(set)
        for o in obs:
            if not o.hand_known or not o.cards:
                continue
            # Una mano cuenta como 'usada' si aporta >=1 observacion con cartas
            manos_con_obs.add(o.hand_id)
            if o.street == 'preflop':
                continue
            bid = _board_ids(o.board)
            if bid is None:
                continue
            perfil = labels.get(o.player)
            if perfil is None:
                continue
            from .cards import card_id, is_card_code

            cs = o.cards if isinstance(o.cards, (list, tuple)) \
                else [o.cards[i:i + 2] for i in range(0, len(o.cards), 2)]
            # El historial puede traer marcadores ('-', '') cuando el
            # recorder no capturó la mano: no son una mano, y no pueden
            # entrar al estimador de fuerza.
            cs = [c for c in cs if is_card_code(c)]
            if len(cs) != 2:
                continue
            cards = np.asarray([card_id(c) for c in cs], dtype=np.intp)
            bucket = model._bucket_of(cards, bid)
            key = (perfil, o.street, o.facing, bucket)
            model.opp[key] = model.opp.get(key, 0) + 1
            akey = key + (o.action,)
            model.cnt[akey] = model.cnt.get(akey, 0) + 1
            manos_con_obs_postflop.add(o.hand_id)
            manos_por_celda[key].add(o.hand_id)
        model.n_hands_used = len(manos_con_obs)
        model.n_hands_with_known_cards = len(manos_con_obs)
        model.n_hands_with_postflop_observation = len(manos_con_obs_postflop)
        model.n_observations_used = sum(model.opp.values())
        model._cell_hand_counts = {
            key: len(ids) for key, ids in manos_por_celda.items()}
        model._cell_hand_ids = {
            key: set(ids) for key, ids in manos_por_celda.items()}
        model._evidence_counts_known = True
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

    def evidence_for(self, perfil: str, street: str, facing: str,
                     bucket: int, action: str,
                     eligibility_projection: Optional[dict] = None) -> dict:
        """Descompone una probabilidad actual en observaciones y prior.

        No es usado por `p_action`; calcula solo metadatos y deja intacta la
        probabilidad. `prior_weight` es la contribución algebraica exacta del
        prior en la fórmula existente, no un nivel de confianza.
        """
        key = (perfil, street, facing, bucket)
        n = self.opp.get(key, 0)
        action_n = self.cnt.get(key + (action,), 0)
        hand_n = (self._cell_hand_counts.get(key)
                  if self._evidence_counts_known else None)
        prior_result = None
        oracle_evidence = None
        if self._oracle is not None:
            prior_result = self._oracle.p_action(perfil, street, facing)
            if hasattr(self._oracle, 'evidence'):
                oracle_evidence = self._oracle.evidence(
                    perfil, street, facing, distribution=prior_result)
        if prior_result is not None:
            prior_source = prior_result.get('source', 'oracle')
            prior_probability = prior_result['actions'].get(action, 0.0)
            prior_used = True
        elif n > 0:
            prior_source = ('flat_no_oracle' if self._oracle is None else
                            'flat_oracle_no_cell')
            prior_probability = 0.2
            prior_used = True
        else:
            prior_source = ('no_prior_model' if self._oracle is None else
                            'oracle_no_distribution')
            prior_probability = 0.0
            prior_used = False
        if prior_used:
            prior_weight = self.alpha / (n + self.alpha)
            observation_weight = n / (n + self.alpha)
            prior_dominated = prior_weight >= 0.5
        else:
            prior_weight = None
            observation_weight = 0.0
            prior_dominated = False
        if n == 0:
            coverage = 'prior_only' if prior_used else 'no_evidence_no_prior'
            reasons = (['no bucket observations; estimate is prior-only']
                       if prior_used else
                       ['no observations and no available prior'])
        elif n < 3:
            coverage = 'thin_observations_n_lt_3'
            reasons = ['fewer than 3 observations in this bucket']
        elif n < 20:
            coverage = 'limited_observations_n_lt_20'
            reasons = ['fewer than 20 observations in this bucket']
        else:
            coverage = 'observations_n_ge_20'
            reasons = []
        if hand_n == 1:
            reasons.append('all evidence comes from one hand')
        if prior_dominated:
            reasons.append('prior algebraic weight is at least 50%')
        if not reasons:
            reasons.append('no calibrated uncertainty interval is available')
        return {
            'contract': 'postflop_evidence_v1',
            'profile': perfil, 'street': street, 'facing': facing,
            'bucket': bucket, 'action': action,
            'estimate': self.p_action(perfil, street, facing, bucket, action),
            'observation_count': n,
            'distinct_hand_count': hand_n,
            'action_observation_count': action_n,
            'observation_provenance': 'hands_db.jsonl via extract_hands',
            'model_prior_source': prior_source,
            'prior_probability': (prior_probability if prior_used
                                 else 'not_available'),
            'prior_available': prior_used,
            'prior_returned_n': (prior_result.get('n', 0)
                                 if prior_result else 0),
            'prior_support_observations': (
                oracle_evidence.get('support_observations')
                if oracle_evidence else 0),
            'prior_evidence': oracle_evidence,
            'alpha': self.alpha,
            'prior_weight': prior_weight,
            'observation_weight': observation_weight,
            'prior_dominated': prior_dominated,
            'coverage': coverage,
            'confidence': 'not_quantified',
            'uncertainty_reasons': reasons,
            'eligibility_projection': (eligibility_projection or {
                'status': 'not_attached',
                'reason': 'P0-2 shadow counts are in the audit; no effective filtering'}),
        }

    def p_action_with_evidence(self, perfil: str, street: str, facing: str,
                              bucket: int, action: str) -> dict:
        """Convenience return: old scalar plus additive evidence metadata."""
        return self.evidence_for(perfil, street, facing, bucket, action)

    def evidence_for_vector(self, perfil: str, street: str, facing: str,
                            board_codes, action: str) -> dict:
        """Evidence sidecar for the five-bucket vector used by `prob_vec`."""
        board = np.asarray([c for c in board_codes])
        if board.dtype.kind in 'US':
            from .cards import card_id
            board = np.asarray([card_id(str(c)) for c in board],
                               dtype=np.intp)
        _scores, buckets = self._board_buckets(board)
        by_bucket = [self.evidence_for(
            perfil, street, facing, b, action) for b in range(self.n_buckets)]
        return {
            'contract': 'postflop_vector_evidence_v1',
            'profile': perfil, 'street': street, 'facing': facing,
            'action': action, 'board': [str(c) for c in board_codes],
            'buckets': by_bucket,
            'observations_total': sum(x['observation_count']
                                      for x in by_bucket),
            'distinct_hands_across_buckets': (
                len(set().union(*[
                    self._cell_hand_ids.get((perfil, street, facing, b), set())
                    for b in range(self.n_buckets)]))
                if self._evidence_counts_known else None),
            'confidence': 'not_quantified',
            'uncertainty_reason': 'vector contains bucket-specific evidence; '
                                  'inspect each bucket, not one pooled n',
            'bucket_ids_present_on_board': sorted(set(int(b) for b in buckets)),
        }

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

    def evidence_metadata(self) -> dict:
        """Tamaños y procedencia; nunca se consulta desde `p_action`."""
        return {
            'contract': 'postflop_evidence_v1',
            'hands_received': self.n_hands_input,
            'legacy_hands_used': self.n_hands_used,
            'hands_with_known_card_observation':
                self.n_hands_with_known_cards,
            'hands_with_postflop_observation':
                self.n_hands_with_postflop_observation,
            'observations_used': (self.n_observations_used
                                  if self.n_observations_used is not None
                                  else sum(self.opp.values())),
            'populated_cells': len(self.opp),
            'whole_hand_validation': 'none; row-level observation filters only',
            'observation_provenance': 'hands_db.jsonl via extract_hands',
            'prior_provenance': self._oracle_injection_source,
            'oracle_injected': self._oracle is not None,
            'prior_formula': '(action_count + alpha*prior_probability) / '
                             '(observation_count + alpha)',
            'flat_prior_probability': 0.2,
            'flat_prior_condition':
                'used only if Oracle is unavailable and bucket observation_count > 0',
            'eligibility_policy': {
                'mode': 'shadow_only',
                'effective_filtering': False,
                'per_cell_projection': 'available from P0-3 audit, not serialized',
            },
            'uncertainty': {
                'confidence': 'not_quantified',
                'interval_method': None,
                'reason': 'no calibrated statistical interval implemented',
            },
        }

    # ------------------------------------------------------------------

    def to_json(self) -> dict:
        return {
            'meta': dict({'alpha': self.alpha,
                          'n_buckets': self.n_buckets,
                          'origen': 'hands_db.jsonl'},
                         **procedencia(self.n_hands_input,
                                            self.n_hands_used)),
            'labels': dict(self.labels),
            'opp': {f'{k[0]}|{k[1]}|{k[2]}|{k[3]}': v
                    for k, v in self.opp.items()},
            'cnt': {f'{k[0]}|{k[1]}|{k[2]}|{k[3]}|{k[4]}': v
                    for k, v in self.cnt.items()},
            'evidence': {
                **self.evidence_metadata(),
                'cell_distinct_hands': {
                    f'{k[0]}|{k[1]}|{k[2]}|{k[3]}': sorted(ids)
                    for k, ids in self._cell_hand_ids.items()},
            },
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
        model.n_hands_input = data['meta'].get('hands_input')
        model.n_hands_used = data['meta'].get('hands_used')
        model.labels = data['labels']
        for k, v in data['opp'].items():
            a, b, c, d = k.split('|')
            model.opp[(a, b, c, int(d))] = v
        for k, v in data['cnt'].items():
            a, b, c, d, e = k.split('|')
            model.cnt[(a, b, c, int(d), e)] = v
        model.n_observations_used = sum(model.opp.values())
        evidence = data.get('evidence') or {}
        if evidence:
            model.n_hands_with_known_cards = evidence.get(
                'hands_with_known_card_observation')
            model.n_hands_with_postflop_observation = evidence.get(
                'hands_with_postflop_observation')
            model._cell_hand_ids = {}
            for key, ids in evidence.get('cell_distinct_hands', {}).items():
                a, b, c, d = key.split('|')
                model._cell_hand_ids[(a, b, c, int(d))] = set(ids)
            model._cell_hand_counts = {
                key: len(ids) for key, ids in model._cell_hand_ids.items()}
            model._evidence_counts_known = bool(
                evidence.get('hands_with_postflop_observation') is not None)
        else:
            # En JSON históricos solo se guardaban manos_input/used y tablas
            # de observaciones; el n de manos distintas por celda no se puede
            # reconstruir a partir de opp.
            model.n_hands_with_known_cards = model.n_hands_used
            model._evidence_counts_known = False
        # El formato histórico no serializa Oracle. No inyectarlo aquí:
        # hacerlo cambiaría p_action frente al comportamiento actual.
        model._oracle = None
        model._oracle_injection_source = (
            'not serialized by legacy load; flat fallback remains active')
        return model


def main(argv=None):
    import json
    import sys

    from .learn import load_hands

    want_json = '--json' in (argv if argv is not None else sys.argv[1:])
    hands = load_hands(reliable_only=True)
    model = PostflopRangeModel.from_hands(hands)
    print(f'Manos: {len(hands)} · buckets: {model.n_buckets}\n')
    print(model.report())
    if want_json:
        model.save()
        print(f'\n-> {PF_RANGES_PATH}')


if __name__ == '__main__':
    main()
