"""profile.py — perfiles de jugador (APRENDIZAJE.md §5.4-§5.6).

Vector de estadísticas de transición -> buckets, etiqueta derivada y
confianza por muestra usando una posterior Beta por estadística:

    P(rate ∈ bin | opp, act)  con  rate ~ Beta(act+1, opp-act+1)

- La confianza del perfil es la masa media de los bins modales: con poca
  muestra la posterior está muy repartida (perfil "probable"); con mucha,
  concentrada ("confiable").
- `omega(spot)`: ratio frecuencia real / frecuencia base de la matriz
  (preflop_matrices.json) con clamp [0.25, 4] para escalar rangos (§5.6).
"""
import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from scipy.special import betainc

from .learn import load_hands
from .stats import TransitionStats

MATRICES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'preflop_matrices.json')

# pesos de combinaciones por tipo de mano en la tabla 13x13 (6max, sin blockers)
_RANK = 'AKQJT98765432'
_COMBO = {}
for i, r1 in enumerate(_RANK):
    for j, r2 in enumerate(_RANK):
        if i == j:
            _COMBO[(i, j)] = 6            # pareja
        elif i < j:
            _COMBO[(i, j)] = 4            # suited
            _COMBO[(j, i)] = 12           # offsuit


@dataclass(frozen=True)
class Bin:
    name: str
    lo: float
    hi: Optional[float]          # None = +inf


STAT_BINS: Dict[str, List[Bin]] = {
    'vpip': [Bin('tight', 0, 0.18), Bin('mid', 0.18, 0.32), Bin('loose', 0.32, None)],
    'pfr':  [Bin('low', 0, 0.10), Bin('mid', 0.10, 0.18), Bin('high', 0.18, None)],
    'b3':   [Bin('low', 0, 0.05), Bin('mid', 0.05, 0.10), Bin('high', 0.10, None)],
    'cbet': [Bin('low', 0, 0.40), Bin('mid', 0.40, 0.60), Bin('high', 0.60, None)],
    'wtsd': [Bin('low', 0, 0.25), Bin('mid', 0.25, 0.40), Bin('high', 0.40, None)],
}

# stats de transición derivables para perfilar: clave stat en PlayerStats
PROFILE_STATS = ('vpip', 'pfr', 'b3', 'cbet')

# umbrales de confianza por número de manos (§5.5)
HANDS_BANDS = ((40, 'probable'), (500, 'confiable'), (5000, 'individual'))


def beta_mass(opp, act, lo, hi=None):
    """P(lo <= rate < hi) para rate ~ Beta(act+1, opp-act+1)."""
    a, b = act + 1.0, opp - act + 1.0
    if hi is None:
        return 1.0 - betainc(a, b, lo)
    return betainc(a, b, hi) - betainc(a, b, lo)


class PlayerProfile:
    """Perfil de un jugador: vector estadístico + bins + etiqueta + ω."""

    def __init__(self, player, hero=False, n=0,
                 stats: Optional[Dict[str, float]] = None,
                 counts: Optional[Dict[str, Tuple[int, int]]] = None):
        self.player = player
        self.hero = hero
        self.n = n
        self.stats = dict(stats or {})
        self.counts = dict(counts or {})
        self.bins: Dict[str, str] = {}
        self._bin_mass: Dict[str, float] = {}
        self._compute_bins()
        self.label = _archetype(self.bins)
        self.confidence = self._confidence()

    # ------------------------------------------------------------------

    def _compute_bins(self):
        for stat, bins in STAT_BINS.items():
            opp, act = self.counts.get(stat, (0, 0))
            if opp <= 0:
                self.bins[stat] = 'n/a'
                self._bin_mass[stat] = 0.0
                continue
            # bin por la media de la posterior Beta (contracción con la
            # anterior uniforme); confianza = masa modal de la posterior.
            mean = (act + 1.0) / (opp + 2.0)
            best = min(range(len(bins)),
                       key=lambda i: abs(mean - (bins[i].lo + (bins[i].hi or 1.0)) / 2.0))
            self.bins[stat] = bins[best].name
            probs = [beta_mass(opp, act, b.lo, b.hi) for b in bins]
            self._bin_mass[stat] = max(probs)

    def _confidence(self):
        masses = [m for m in self._bin_mass.values() if m > 0]
        if not masses:
            return 0.0
        return float(math.prod(masses) ** (1.0 / len(masses)))

    def reliability(self):
        """Etiqueta según n de manos observadas (§5.5)."""
        for threshold, name in HANDS_BANDS:
            if self.n < threshold:
                return name
        return 'individual'

    def omega(self, table_name, base_rates, low=0.25, high=4.0):
        """Ratio frecuencia real / base de la matriz, clamp [low, high].

        table_name: 'OR_UTG', '3B_CO_vs_BTN', ... (claves de
        preflop_matrices.json). El stat usado se infiere del prefijo.
        """
        base = base_rates.get(table_name)
        if base is None or base <= 0:
            return None
        stat = _stat_for_table(table_name)
        freq = self.stats.get(stat)
        if freq is None:
            return None
        return max(low, min(high, freq / base))

    def to_dict(self):
        return {
            'player': self.player,
            'hero': self.hero,
            'n': self.n,
            'stats': {k: round(v, 4) for k, v in self.stats.items()},
            'bins': self.bins,
            'label': self.label,
            'confidence': round(self.confidence, 3),
            'reliability': self.reliability(),
        }


def _stat_for_table(table_name):
    if table_name.startswith('OR'):
        return 'pfr'
    if table_name.startswith('3B'):
        return 'b3'
    if table_name.startswith('4B'):
        return 'b4'
    if 'CBET' in table_name or 'Cbet' in table_name:
        return 'cbet'
    return 'pfr'


def _archetype(bins):
    vpip, pfr, b3 = bins.get('vpip', 'n/a'), bins.get('pfr', 'n/a'), bins.get('b3', 'n/a')
    if vpip == 'n/a':
        return 'unknown'
    agg = pfr in ('high',)
    if vpip == 'tight':
        return 'TAG' if agg else ('Nit' if pfr == 'low' else 'Tight-passive')
    if vpip == 'loose':
        return 'LAG' if agg else 'Loose-passive'
    if pfr == 'low':
        return 'Passive-reg'
    return 'Loose-reg' if b3 == 'high' else 'Regular'


class Profiles:
    """Todos los perfiles del dataset + tasas base de las matrices."""

    def __init__(self):
        self.profiles: Dict[str, PlayerProfile] = {}
        self.base_rates: Dict[str, float] = {}

    @classmethod
    def from_hands(cls, hands, matrices_path=MATRICES_PATH):
        obj = cls()
        agg = TransitionStats.from_hands(hands)
        obj.base_rates = load_base_rates(matrices_path)
        for name, st in agg.players.items():
            counts = {k: (v[0], v[1]) for k, v in st.c.items()}
            stats = {k: st.freq(k) for k, v in st.c.items() if v[0]}
            stats = {k: f for k, f in stats.items() if f is not None}
            obj.profiles[name] = PlayerProfile(
                player=name, hero=st.hero, n=counts.get('vpip', (0, 0))[0],
                stats=stats, counts=counts)
        return obj

    def report(self, players=None, cols=('vpip', 'pfr', 'b3', 'cbet')):
        head = 'PLAYER'.ljust(12) + '  n'.rjust(4) + ''.join(
            f'{c:>6}' for c in cols) + '  ETIQUETA'.ljust(18) + ' CONF  REL'
        lines = [head, '-' * len(head)]
        for name in (players or sorted(self.profiles)):
            p = self.profiles[name]
            cells = []
            for c in cols:
                f = p.stats.get(c)
                cell = p.stats.get(c)
                cells.append(f'{cell * 100:5.0f}%' if cell is not None else '    -')
            star = '*' if p.hero else ' '
            lines.append(f'{name[:12]:<12}{star}{p.n:>4}' + ''.join(cells) +
                         f'  {p.label:<18}{p.confidence:4.0%}  {p.reliability()}')
        return '\n'.join(lines)

    def to_dict(self):
        return {name: p.to_dict() for name, p in sorted(self.profiles.items())}


def load_base_rates(matrices_path=MATRICES_PATH):
    """Tasa base (frecuencia media ponderada por combos) de cada tabla."""
    if not matrices_path or not os.path.exists(matrices_path):
        return {}
    tables = json.load(open(matrices_path, encoding='utf-8')).get('tables', {})
    rates = {}
    for name, t in tables.items():
        matrix = t.get('matrix')
        if not isinstance(matrix, list) or len(matrix) != 13:
            continue
        total_w = total_p = 0.0
        for i, row in enumerate(matrix):
            if not isinstance(row, list) or len(row) != 13:
                continue
            for j, freq in enumerate(row):
                try:
                    f = float(freq)
                except (TypeError, ValueError):
                    continue
                w = _COMBO.get((i, j), 1)
                total_w += w
                total_p += f * w
        rates[name] = total_p / total_w if total_w else 0.0
    return rates


def main(argv=None):
    """CLI: python -m motor.profile [--json] [--out PATH]"""
    import sys
    argv = list(argv or sys.argv[1:])
    write_json = '--json' in argv
    out_path = ''
    if '--out' in argv:
        idx = argv.index('--out')
        out_path = argv[idx + 1] if len(argv) > idx + 1 else ''
    hands = load_hands()
    profs = Profiles.from_hands(hands)
    print(f'Manos: {len(hands)}\n')
    print(profs.report())
    if write_json:
        path = out_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'profiles.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(profs.to_dict(), f, indent=2, ensure_ascii=False)
        print(f'\n-> {path}')


if __name__ == '__main__':
    main()