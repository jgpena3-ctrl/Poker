"""player_ranges.py — Perfil → Modelo de Rango (pegar6, preflop).

Cierra el hueco del pipeline: P(A|H, C, P) — probabilidad de que el perfil
`P` ejecute la acción `A` con la mano `H` en el spot `C` (no_raise /
facing_open / facing_3bet), preflop.

```
hands_db.jsonl
    │  learn.load_hands()          learn.preflop_events (cat, denom, cards)
    ▼
ProfileRangeModel                    P(A|H, spot, perfil)   ← ESTE MÓDULO
    ├─ p_matrix(...) → grid 13×13 (celda = clase de mano)
    ├─ prob_vec(...) → (1326,)      listo para RangeState.update
    ├─ p_hand(...)   → P(A|H) de una mano concreta ('AsKd')
    │
    ▼
RangeEngine / recommend_loop (rango rival perfilado)
```

DOS FUENTES QUE NUNCA SE MEZCLAN (TECNICO §3.1):
- mano conocida (hand_known + cartas) → este modelo (P(A|H, contexto));
- mano desconocida                    → solo frecuencia de acción
  (behavior.py / Oracle) — no entra aquí.

MÉTODO — SHRINKAGE A LA BASE POBLACIONAL (n pequeña, TECNICO §6):
Por (perfil, spot) se acumula `opp` (todas las primeras decisiones preflop
con mano conocida) y `cnt` por (perfil, spot, acción). En cada celda del
grid 13×13:

    P(A|H,C,P) = (cnt + alpha·prior) / (opp + alpha)

donde `prior` es la tabla base de la misma acción del
`preflop_matrices.json` (prior encaja por posición cuando se pide `pos`),
o un prior plano (FLAT_PRIOR) si la acción no tiene tabla (limp/fold/
bb_check/call_limp/roll...). Perfiles sin manos en el spot se pliegan a la
base. `alpha` = 2.0 pseudo-conteos por defecto: con n≈0 manda la base, con
n grande manda lo empírico del perfil.

La muestra real es pequeña (de la DB real: ~1.043 decisiones con cartas):
el grid del perfil NO se desglosa por posición en los conteos; la posición
solo modula el prior cuando se pasa `pos`. El grid empírico del perfil
"Regular" en spot no_raise ya acumula varias decenas de manos.

El perfil de ROL: los perfiles derivan de `profile.py` (etiqueta); el
modelo NUNCA mezcla manos conocidas del HERO (Jarduan) con las de rivales
por diseño — se usa la etiqueta del HERO si aparece, igual que behavior.
"""
import json
import os
from typing import Dict, Optional, Tuple

import numpy as np

from .learn import load_hands, preflop_events
from .preflop import CELL_COL, CELL_ROW, matrix_to_probs

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RANGES_PATH = os.path.join(REPO_DIR, 'data', 'profile_ranges.json')

GRID_RANKS = 'AKQJT98765432'
DEFAULT_ALPHA = 2.0         # pseudo-conteos del shrinkage
FLAT_PRIOR = 0.15           # prior cuando la acción no tiene tabla base

# categoría en learn.py -> prefijo de la tabla en preflop_matrices.json
CAT_TABLE = {
    'open': 'OR', 'rol': 'OR', 'call_open': 'Call_OR', '3bet': '3B',
    'squeeze': 'SQUEEZE', '4bet': '4B', 'call_3bet': 'Call_3B',
    'limp': 'LIMP', 'call_limp': 'LIMP',
}

# stat de agresión por spot (para el ajuste individual)
SPOT_STAT = {
    'no_raise': 'pfr', 'facing_open': 'b3', 'facing_3bet': 'b4',
}

_tables_cache = None


def _load_tables():
    global _tables_cache
    if _tables_cache is None:
        with open(os.path.join(REPO_DIR, 'data', 'preflop_matrices.json'),
                  encoding='utf-8') as f:
            _tables_cache = json.load(f)['tables']
    return _tables_cache


def _cell_(cards: str) -> Optional[Tuple[int, int]]:
    """Celda (i, j) del grid 13×13 para una mano 'AsKd' ('' o inválida → None).

     i = fila (rango más alto), j = col. Pares en la diagonal; suited
     i≤j; offset i>j — igual convenio que preflop.py.
    """
    if not cards or len(cards) < 4:
        return None
    r0, r1 = cards[0], cards[2]
    if r0 not in GRID_RANKS or r1 not in GRID_RANKS:
        return None
    i, j = GRID_RANKS.index(r0), GRID_RANKS.index(r1)
    if i == j:
        return i, j
    return (i, j) if cards[1] == cards[3] else (j, i)


class ProfileRangeModel:
    """P(A|H, spot, perfil) preflop — grid 13×13 por (perfil, spot).

    Construcción: from_hands(hands, o labels={jugador: perfil}).
    Consultas: p_matrix, prob_vec (para RangeState), p_hand, report.
    Persistencia: to_json/save/load (data/profile_ranges.json).
    """

    def __init__(self, alpha: float = DEFAULT_ALPHA):
        self.alpha = float(alpha)
        self.opp: Dict[Tuple[str, str], np.ndarray] = {}   # (perfil, spot)
        self.cnt: Dict[Tuple[str, str, str], np.ndarray] = {}  # (p,spot,c)
        self.perfil: Dict[str, str] = {}                  # jugador → perfil
        self.profiles = None                             # Profiles (stats/ω)

    # ------------------------------------------------------------------

    @classmethod
    def from_hands(cls, hands, labels: Optional[Dict[str, str]] = None,
                   alpha: float = DEFAULT_ALPHA) -> 'ProfileRangeModel':
        """Construye desde hands (DB). `labels` opcional: jugador → perfil
        (default: perfiles estimados por Profile_lab.from_hands)."""
        from .profile import Profiles

        if labels is None:
            profs = Profiles.from_hands(hands)
            labels = {name: p.label for name, p in profs.profiles.items()}
        model = cls(alpha=alpha)
        model.perfil = dict(labels)
        model.profiles = Profiles.from_hands(hands)
        for hand in hands:
            for ev in preflop_events(hand):
                if not ev.hand_known or not ev.cards:
                    continue
                perfil = labels.get(ev.player)
                if perfil is None:
                    continue
                cell = _cell_(ev.cards)
                if cell is None:
                    continue
                opp_key = (perfil, ev.denom)
                if opp_key not in model.opp:
                    model.opp[opp_key] = np.zeros((13, 13), dtype=np.float32)
                model.opp[opp_key][cell] += 1.0
                cnt_key = (perfil, ev.denom, ev.category)
                if cnt_key not in model.cnt:
                    model.cnt[cnt_key] = np.zeros((13, 13), dtype=np.float32)
                model.cnt[cnt_key][cell] += 1.0
        return model

    # ------------------------------------------------------------------

    def _prior_grid(self, action: str, pos: str = '') -> np.ndarray:
        prefix = CAT_TABLE.get(action)
        if not prefix:
            return np.full((13, 13), FLAT_PRIOR, dtype=np.float32)
        tables = _load_tables()
        chosen = None
        if pos:
            chosen = tables.get(f'{prefix}_{pos}')
        if chosen is None:
            for name, t in tables.items():
                if t.get('action') == prefix:
                    chosen = t
                    break
        if chosen is None or 'matrix' not in chosen:
            return np.full((13, 13), FLAT_PRIOR, dtype=np.float32)
        return np.asarray(chosen['matrix'], dtype=np.float32)

    def p_matrix(self, perfil: str, spot: str, action: str,
                 pos: str = '') -> np.ndarray:
        """Grid 13×13 de P(A|r, spot, perfil) con shrinkage."""
        prior = self._prior_grid(action, pos)
        opp = self.opp.get((perfil, spot))
        if opp is None:
            return prior.copy()
        cnt = self.cnt.get((perfil, spot, action))
        if cnt is None:
            cnt = np.zeros((13, 13), dtype=np.float32)
        return (cnt + self.alpha * prior) / (opp + self.alpha)

    def range_matrix(self, perfil: str, spot: str, action: str,
                     pos: str = '') -> np.ndarray:
        """Alias de p_matrix (nombre conforme a la doc del módulo)."""
        return self.p_matrix(perfil, spot, action, pos)

    def prob_vec(self, perfil: str, spot: str, action: str,
                 pos: str = '') -> np.ndarray:
        """Vector (1326,) operativo para `RangeState.update`."""
        m = self.p_matrix(perfil, spot, action, pos)
        return np.asarray(m, dtype=np.float32)[CELL_ROW, CELL_COL]

    def p_hand(self, perfil: str, spot: str, action: str,
               hand: str, pos: str = '') -> float:
        cell = _cell_(hand)
        if cell is None:
            return 0.0
        return float(self.p_matrix(perfil, spot, action, pos)[cell])

    # ------------------------------------------------------------------
    # Ajuste individual (pegar6, paso 2): ω por spot + desviación
    # ------------------------------------------------------------------

    def player_omega(self, player: str, spot: str,
                     fade: float = 20.0) -> float:
        """Factor ω del jugador (freq real / media de su perfil) para `spot`.

        stat de agresión del spot (no_raise→pfr, facing_open→b3,
        facing_3bet→b4), comparado con la media de los jugadores del mismo
        perfil. Sin datos → 1.0. Con poca muestra propia el factor se pliega
        a 1.0 (fade-in: alpha = min(1, n_player/fade)).
        """
        if self.profiles is None:
            return 1.0
        prof = self.profiles.profiles.get(player)
        if prof is None:
            return 1.0
        stat = SPOT_STAT.get(spot)
        if stat is None:
            return 1.0
        freq = prof.stats.get(stat)
        if freq is None:
            return 1.0
        peers = [s for s in (
            p.stats.get(stat)
            for p in self.profiles.profiles.values()
            if p.label == prof.label and p.stats.get(stat) is not None)
            if s is not None]
        if not peers:
            return 1.0
        base = sum(peers) / len(peers)
        if base <= 0:
            return 1.0
        w = max(0.25, min(4.0, freq / base))
        alpha = min(1.0, prof.n / fade)
        return 1.0 + alpha * (w - 1.0)

    def p_player(self, player: str, spot: str, action: str,
                 pos: str = '') -> np.ndarray:
        """Grid 13×13 del jugador: perfil escalado por su ω del spot."""
        perfil = self.perfil.get(player)
        if perfil is None:
            return self._prior_grid(action, pos)
        m = self.p_matrix(perfil, spot, action, pos).copy()
        w = self.player_omega(player, spot)
        if w != 1.0 and perfil is not None:
            m *= w
        return np.clip(m, 0.0, 1.0)

    def prob_vec_player(self, player: str, spot: str, action: str,
                        pos: str = '') -> np.ndarray:
        """Vector (1326,) del rango individual (perfil·ω) para RangeState."""
        m = self.p_player(player, spot, action, pos)
        return np.asarray(m, dtype=np.float32)[CELL_ROW, CELL_COL]

    # ----------------------------------------------------------------

    def to_json(self) -> dict:
        return {
            'meta': {'alpha': self.alpha, 'origen': 'hands_db.jsonl'},
            'perfil': dict(self.perfil),
            'opp': {f'{k[0]}|{k[1]}': v.tolist()
                    for k, v in self.opp.items()},
            'cnt': {f'{k[0]}|{k[1]}|{k[2]}': v.tolist()
                    for k, v in self.cnt.items()},
            'omega': {p: {s: round(self.player_omega(p, s), 4)
                          for s in SPOT_STAT}
                      for p in sorted(self.perfil)},
        }

    def save(self, path: str = RANGES_PATH):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_json(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str = RANGES_PATH) -> 'ProfileRangeModel':
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        model = cls(alpha=data['meta']['alpha'])
        model.perfil = data['perfil']
        for k, v in data['opp'].items():
            a, b = k.split('|')
            model.opp[(a, b)] = np.asarray(v, dtype=np.float32)
        for k, v in data['cnt'].items():
            a, b, c = k.split('|')
            model.cnt[(a, b, c)] = np.asarray(v, dtype=np.float32)
        return model

    # ----------------------------------------------------------------

    def report(self) -> str:
        lines = [f'{"perfil":<18}{"spot":<14}{"n":>5}   acciones',
                 '-' * 72]
        for (perfil, spot), g in sorted(self.opp.items(),
                                        key=lambda kv: -kv[1].sum()):
            n = int(g.sum())
            acts = []
            for k, c in self.cnt.items():
                if k[0] == perfil and k[1] == spot and c.sum() > 0:
                    acts.append(f'{k[2]}:{int(c.sum())}')
            lines.append(f'{perfil:<18}{spot:<14}{n:>5}   '
                         f'{" ".join(acts[:8])}')
        if self.profiles is not None:
            lines += ['', 'Ajuste individual (omega real/perfil por spot):',
                      f'{"jugador":<14}{"pfr":>7}{"b3":>7}{"b4":>7}']
            for p, pj in sorted(self.perfil.items()):
                prof = self.profiles.profiles.get(p)
                if prof is None or prof.n < 4:
                    continue
                w = {s: self.player_omega(p, s) for s in SPOT_STAT}
                lines.append(f'{p[:12]:<14}'
                             f'{w["no_raise"]:>7.2f}'
                             f'{w["facing_open"]:>7.2f}'
                             f'{w["facing_3bet"]:>7.2f}')
        return '\n'.join(lines)


def main(argv=None):
    import sys

    want_json = '--json' in (argv if argv is not None else sys.argv[1:])
    hands = load_hands()
    model = ProfileRangeModel.from_hands(hands)
    print(f'Manos válidas: {len(hands)}\n')
    print(model.report())
    if want_json:
        model.save()
        print(f'\n-> {RANGES_PATH}')


if __name__ == '__main__':
    main()