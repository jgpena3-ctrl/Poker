"""learn.py — extracción de frecuencias preflop desde hands_db.jsonl.

Especificación: DOCS/APRENDIZAJE.md (pegar4 · perfiles pegar5 §5).

Principios:
- Dos tipos de evidencia que NO se mezclan: mano conocida (P(A|H, contexto))
  y mano desconocida (P(A|contexto)). `hand_known` se guarda por evento.
- `Jarduan` (hero) siempre con mano conocida (HERO_NAMES).
- Cada jugador entra UNA vez por mano con su primera decisión preflop; el
  estado del bote en ese momento (raises/limps previos) define la categoría
  (limp / open / RIL / 3bet / squeeze / 4bet / fold...) y el denominador
  (oportunidad) al que aporta.

Categorías y sus denominadores (CATEGORY_DENOM):
    no_raise      : fold, limp, open, call_limp, rol, bb_check
    facing_open   : call_open, 3bet, squeeze, fold_vs_open
    facing_3bet   : call_3bet, 4bet, fold_vs_3bet

Taxonomía completa y racional: docs/APRENDIZAJE.md §6.
"""
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, Tuple

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_DIR, 'data', 'hands_db.jsonl')

BB = 1.0                                  # big blind nominal del juego
HERO_NAMES = ('Jarduan',)                 # el usuario real: mano siempre conocida

CATEGORY_DENOM = {
    'fold': 'no_raise', 'limp': 'no_raise', 'open': 'no_raise',
    'call_limp': 'no_raise', 'rol': 'no_raise', 'bb_check': 'no_raise',
    'call_open': 'facing_open', '3bet': 'facing_open',
    'squeeze': 'facing_open', 'fold_vs_open': 'facing_open',
    'call_3bet': 'facing_3bet', '4bet': 'facing_3bet',
    'fold_vs_3bet': 'facing_3bet',
}
DENOM_ORDER = ('no_raise', 'facing_open', 'facing_3bet')
CATEGORY_ORDER = ('open', 'limp', 'rol', 'call_limp', 'call_open', '3bet',
                  'squeeze', '4bet', 'call_3bet', 'fold', 'fold_vs_open',
                  'fold_vs_3bet', 'bb_check')


# ---------------------------------------------------------------------------
# Carga y lectura del historial
# ---------------------------------------------------------------------------

def load_hands(path=None):
    """Carga las manos válidas (dicts) de data/hands_db.jsonl.

    Descartadas: líneas rotas o faltan `players`/`streets`.
    """
    path = path or DB_PATH
    hands = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                hand = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(hand, dict) and hand.get('streets') is not None \
                    and hand.get('players') is not None:
                hands.append(hand)
    return hands


def player_of_pos(hand, pos):
    """Nombre del jugador sentado en `pos` ('' si no está)."""
    for p in hand.get('players', []):
        if p.get('pos') == pos:
            return p.get('name') or ''
    return ''


def cards_of_pos(hand, pos):
    """Cartas registradas del jugador en `pos` ('' si ninguna)."""
    for p in hand.get('players', []):
        if p.get('pos') == pos and p.get('cards'):
            c = p['cards']
            return ''.join(c) if isinstance(c, (list, tuple)) else str(c)
    return ''


def hand_known(player, cards):
    """Mano conocida si hay cartas registradas o si es hero (Jarduan)."""
    return bool(cards) or player in HERO_NAMES


# ---------------------------------------------------------------------------
# Clasificación de la primera decisión preflop
# ---------------------------------------------------------------------------

@dataclass
class PreflopEvent:
    """Primera decisión preflop de un jugador en una mano."""
    hand_id: str
    player: str
    pos: str
    category: str                 # clave en CATEGORY_DENOM
    denom: str                    # no_raise | facing_open | facing_3bet
    amount: float
    hand_known: bool
    cards: str
    prereq: Tuple[str, ...]       # acciones previas ('POS:a')


def classify_first_action(action, amount, raises_before, limps_before, bb=BB):
    """Categoría + denominador de la primera decisión preflop de un jugador.

    action: 'f' | 'x' | 'c' | 'b' | 'r'   (formato del recorder)
    """
    if action == 'x':
        return 'bb_check', 'no_raise'
    if action == 'f':
        if raises_before == 0:
            return 'fold', 'no_raise'
        if raises_before == 1:
            return 'fold_vs_open', 'facing_open'
        return 'fold_vs_3bet', 'facing_3bet'
    if action == 'c':
        if raises_before == 0:
            return ('limp' if limps_before == 0 else 'call_limp'), 'no_raise'
        if raises_before == 1:
            return 'call_open', 'facing_open'
        return 'call_3bet', 'facing_3bet'
    if action in ('b', 'r'):
        if raises_before == 0:
            return 'open' if limps_before == 0 else 'rol', 'no_raise'
        if raises_before == 1:
            return 'squeeze' if limps_before >= 1 else '3bet', 'facing_open'
        return '4bet', 'facing_3bet'
    raise ValueError(f'acción preflop desconocida: {action!r}')


def _preflop_sequence(hand):
    """Secuencia preflop normalizada: [(pos, action, amount)] válidos.

    Acepta entradas del recorder (dicts) o tuplas (pos, action, amount).
    """
    actions = (hand.get('streets', {}).get('preflop', {}) or {}).get('actions', [])
    seq = []
    for a in actions:
        if isinstance(a, dict):
            pos, act = a.get('pos'), a.get('action')
            try:
                amount = float(a.get('amount') or 0.0)
            except (TypeError, ValueError):
                amount = 0.0
        else:
            try:
                pos, act, amount = a[0], a[1], float(a[2] or 0.0)
            except (IndexError, TypeError, ValueError):
                continue
        if not pos or not act:
            continue
        seq.append((pos, act, amount))
    return seq


def preflop_events(hand, bb=BB):
    """Primera decisión de cada jugador en preflop -> [PreflopEvent]."""
    seq = _preflop_sequence(hand)
    events = []
    decided = set()
    for i, (pos, act, amount) in enumerate(seq):
        if pos in decided:
            continue                      # solo la primera decisión
        decided.add(pos)
        raises = sum(1 for p, a, m in seq[:i] if a in ('b', 'r'))
        limps = sum(1 for p, a, m in seq[:i] if a == 'c')
        category, denom = classify_first_action(act, amount, raises, limps, bb)
        cards = cards_of_pos(hand, pos)
        events.append(PreflopEvent(
            hand_id=hand.get('hand_id', '?'),
            player=player_of_pos(hand, pos) or pos,
            pos=pos,
            category=category,
            denom=denom,
            amount=amount,
            hand_known=hand_known(player_of_pos(hand, pos), cards),
            cards=cards,
            prereq=tuple(f'{p}:{a}' for p, a, _ in seq[:i]),
        ))
    return events


# ---------------------------------------------------------------------------
# Agregación de frecuencias
# ---------------------------------------------------------------------------

class PreflopStats:
    """Frecuencias preflop por jugador (cats / denoms), con mano conocida o no."""

    def __init__(self):
        self.cats: Dict[str, Counter] = defaultdict(Counter)
        self.denoms: Dict[str, Counter] = defaultdict(Counter)
        self.known: Dict[str, Counter] = defaultdict(Counter)   # manos conocidas por denom
        self.hands: int = 0

    @classmethod
    def from_hands(cls, hands, bb=BB):
        stats = cls()
        stats.hands = len(hands)
        for hand in hands:
            for ev in preflop_events(hand, bb):
                stats.cats[ev.player][ev.category] += 1
                stats.denoms[ev.player][ev.denom] += 1
                if ev.hand_known:
                    stats.known[ev.player][ev.denom] += 1
        return stats

    def opportunities(self, player, category=None):
        if category is None:
            return sum(self.denoms[player].values())
        return self.denoms[player][CATEGORY_DENOM[category]]

    def freq(self, player, category):
        """Frecuencia de `category` sobre su denominador (None si sin opp)."""
        n = self.opportunities(player, category)
        if n == 0:
            return None
        return self.cats[player][category] / n

    def report(self, players=None) -> str:
        cols = ('open', 'limp', 'rol', 'call_open', '3bet', 'squeeze',
                '4bet', 'call_3bet')
        head = ('PLAYER' ).ljust(12) + ''.join(f'{c:>9}' for c in cols) + '   opp'
        lines = [head, '-' * len(head)]
        for name in (players or sorted(self.cats)):
            if not self.cats[name]:
                continue
            row = []
            for c in cols:
                f = self.freq(name, c)
                row.append(f'{f * 100:8.0f}%' if f is not None else '    n/a')
            opp = sum(self.denoms[name].values())
            lines.append(f'{name[:12]:<12}' + ''.join(row) + f'   {opp:>3}')
        return '\n'.join(lines)

    def to_dict(self):
        return {
            'hands': self.hands,
            'denoms': {p: dict(d) for p, d in self.denoms.items()},
            'cats': {p: dict(c) for p, c in self.cats.items()},
            'known_denoms': {p: dict(d) for p, d in self.known.items()},
        }


def main(argv=None):
    """CLI: python -m motor.learn [--json] [--out PATH]."""
    import sys
    argv = list(argv or sys.argv[1:])
    write_json = '--json' in argv
    out_path = ''
    if '--out' in argv:
        out_path = argv[argv.index('--out') + 1] if len(argv) > argv.index('--out') + 1 else ''
    hands = load_hands()
    stats = PreflopStats.from_hands(hands)
    print(f'Manos cargadas: {len(hands)}\n')
    print(stats.report())
    if write_json:
        path = out_path or os.path.join(REPO_DIR, 'data', 'preflop_stats.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(stats.to_dict(), f, indent=2, ensure_ascii=False)
        print(f'\n-> {path}')


if __name__ == '__main__':
    main()