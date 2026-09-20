"""hand_state.py — rol y fuerza de la mano conocida del hero (pegar.txt §1, §6, §8).

Clasificación determinística de la mano del hero sobre el board actual:
    - strength : categoría de la mano formada (HIGH_CARD .. STRAIGHT_FLUSH)
    - draw     : draw actual (NONE / BDFD / BDSD / GUTSHOT / OESD / FD / COMBO)
    - role     : hand_role (STRONG_VALUE / VALUE / MEDIUM / STRONG_DRAW /
                 WEAK_DRAW / AIR) para filtrar candidatos de acciones.

Uso:
    hs = classify(['7s', '6s'], ['9s', '8s', '2d'])
    hs.role          # 'STRONG_DRAW'  (OESD + FD = COMBO)
    hs.draw          # 'COMBO'
    hs.strength      # 'HIGH_CARD'
"""

from dataclasses import dataclass

from .cards import card_id, rank_of, suit_of
from .hand_evaluator import category_name, evaluate_hand

# ---------------------------------------------------------------------------
# strength por categoría de `category_name`
# ---------------------------------------------------------------------------

_STRENGTH = {
    'high card': 'HIGH_CARD',
    'pair': 'PAIR',
    'two pair': '2PAIR',
    'trips': 'SET',
    'straight': 'STRAIGHT',
    'flush': 'FLUSH',
    'full house': 'FULL_HOUSE',
    'four of a kind': 'QUADS',
    'straight flush': 'STRAIGHT_FLUSH',
}

# ---------------------------------------------------------------------------
# draw detection
# ---------------------------------------------------------------------------


def _flush_draw(hero, board):
    """'NONE' | 'BDFD' | 'FD' | 'COMBO' (combinable con straight draw)."""
    suits = [suit_of(c) for c in hero + board]
    hero_suits = {suit_of(c) for c in hero}
    count = {}
    for s in suits:
        count[s] = count.get(s, 0) + 1
    fd = any(s in hero_suits and count[s] >= 4 for s in count)
    bdfd = (not fd and
            any(s in hero_suits and count[s] == 3 for s in count))
    return 'FD' if fd else ('BDFD' if bdfd else 'NONE')


def _straight_draw(hero, board):
    """'NONE' | 'BDSD' | 'GUTSHOT' | 'OESD' (A cuenta como alta y como baja)."""
    hero_ranks = {rank_of(c) + 2 for c in hero}   # 2..14
    if 14 in hero_ranks:
        hero_ranks.add(1)                          # A también bajo (wheel)
    all_ranks = set(hero_ranks) | {rank_of(c) + 2 for c in board}
    if 14 in all_ranks:
        all_ranks.add(1)

    comps = set()
    used_hand = False
    for start in range(1, 11):                     # ventanas de 5 en 5
        window = set(range(start, start + 5))
        miss = window - all_ranks
        if len(miss) == 1 and (window & hero_ranks):
            comps.add(next(iter(miss)))
            used_hand = True
    if len(comps) >= 2:
        return 'OESD'
    if len(comps) == 1:
        return 'GUTSHOT'

    # backdoor: 3+ consecutivas del hero+board con ≥1 carta del hero
    if used_hand:
        srt = [r for r in range(1, 15) if r in all_ranks]
        run = best = 1
        for a, b in zip(srt, srt[1:]):
            run = run + 1 if b == a + 1 else 1
            best = max(best, run)
        if best >= 3:
            any_run = any(all((h in all_ranks) for h in [b, b + 1, b + 2])
                          and (set(range(b, b + 3)) & hero_ranks)
                          for b in range(1, 13))
            return 'BDSD' if any_run else 'NONE'
    return 'NONE'


# ---------------------------------------------------------------------------
# HandState y clasificación
# ---------------------------------------------------------------------------

_STRONG_MADE = {'STRAIGHT_FLUSH', 'QUADS', 'FULL_HOUSE',
                'FLUSH', 'STRAIGHT', 'SET'}


@dataclass
class HandState:
    """Estado de la mano del hero (hecho + draw + rol)."""
    hero_codes: tuple
    board_codes: tuple
    strength: str
    draw: str
    role: str

    def nut_advantage(self):
        """Aproximación de nut_advantage con la mano única del hero.

        HERO: mano capaz de ser nuts/near-nuts en el board actual;
        VILLAIN: mano sin prácticamente nada; en el resto NEUTRAL.
        """
        if self.strength in _STRONG_MADE:
            return 'HERO'
        if self.strength == 'HIGH_CARD' and self.draw == 'NONE':
            return 'VILLAIN'
        return 'NEUTRAL'


def classify(hero_codes, board_codes):
    """Clasifica la mano del hero sobre el board -> HandState."""
    hero = tuple(hero_codes)
    board = tuple(board_codes)
    hero_ids = tuple(card_id(c) for c in hero)
    board_ids = tuple(card_id(c) for c in board)
    score = evaluate_hand(hero, board)
    strength = _STRENGTH[category_name(score)]

    if strength in _STRONG_MADE:
        draw = 'NONE'
        role = 'STRONG_VALUE'
    elif strength == '2PAIR':
        draw = 'NONE'
        role = 'VALUE'
    elif strength == 'PAIR':
        fd = _flush_draw(hero_ids, board_ids)
        sd = _straight_draw(hero_ids, board_ids)
        draw = _combo(fd, sd)
        role = 'MEDIUM'
    else:                                   # HIGH_CARD
        fd = _flush_draw(hero_ids, board_ids)
        sd = _straight_draw(hero_ids, board_ids)
        draw = _combo(fd, sd)
        if fd == 'FD' and sd == 'OESD':
            role = 'STRONG_DRAW'
        elif fd == 'FD' or sd == 'OESD':
            role = 'STRONG_DRAW'
        elif sd == 'GUTSHOT':
            role = 'WEAK_DRAW'
        elif draw in ('BDFD', 'BDSD'):
            role = 'WEAK_DRAW'
        else:
            role = 'AIR'

    return HandState(hero_codes=hero, board_codes=board,
                     strength=strength, draw=draw, role=role)


def _combo(fd, sd):
    """Draw combinado: COMBO si FD+apertura, si no el más fuerte."""
    if fd == 'FD' and sd in ('OESD', 'GUTSHOT'):
        return 'COMBO'
    order = ['OESD', 'GUTSHOT', 'FD', 'BDFD', 'BDSD']
    for name in order:
        if name in (fd, sd):
            return name
    return 'NONE'


# ---------------------------------------------------------------------------
# ventaja de rango / nuts
# ---------------------------------------------------------------------------


def range_advantage(hero_equity):
    """Ventaja de rango por la equity vs el rango villains (0.45-0.55 neutro)."""
    if hero_equity >= 0.55:
        return 'HERO'
    if hero_equity < 0.45:
        return 'VILLAIN'
    return 'NEUTRAL'