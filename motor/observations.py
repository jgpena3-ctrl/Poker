"""observations.py — extractor de DecisionObservation (APRENDIZAJE.md §4).

Una `Observation` es UNA decisión de UN jugador en UNA calle, con el contexto
rico de la spec: street, pot_type (SRP/3BP/4BP), pot_before, stack efectivo,
SPR, nº jugadores activos, textura del board, `facing` (qué hay que
enfrentar: none/bet/cbet/barrel/raise), sizing y secuencia preflop.
Alimenta las behavior tables por perfil (§7).

Reglas:
- `pot_before` = aportes acumulados en acciones anteriores (el recorder anota
  lo aportado en cada acción).
- `sizing` (b/r) = amount / pot_before (fracción del bote).
- `stack_effective` = stack inicial − lo ya aportado por el jugador.
- `facing` describe lo que ve el jugador: 'none' (sin apuesta vigente) o el
  label de la apuesta/raise vigente ('cbet' si el apostador es el iniciador
  preflop en flop, 'barrel' en turn, 'donk' si otro agresor en bote subido en
  flop/turn, 'bet' si es otro agresor en river/limpeado, 'raise').
- `hand_known` = tiene cartas registradas (incluye hero).
"""
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .learn import HERO_NAMES, load_hands
from .situation import board_texture

RAISE_ACTS = ('b', 'r')
STREETS = ('preflop', 'flop', 'turn', 'river')


@dataclass
class Observation:
    hand_id: str
    street: str
    player: str
    kind: str                       # hero | villain
    pos: str
    action: str                     # f | x | c | b | r
    amount: float
    sizing: Optional[float]         # b/r: amount / pot_before
    pot_before: float
    stack_effective: Optional[float]
    spr: Optional[float]
    pot_type: str                   # SRP | 3BP | 4BP (raises preflop)
    players_active: int
    board: str                      # '5h,6d,4d' — '' si preflop
    texture_class: Optional[str]    # monotone/two_tone/rainbow(+pair)
    facing: str                     # none | cbet | bet | barrel | raise
    raised_before: int              # raises previos preflop (solo preflop)
    preflop_sequence: str           # 'UTG:b,BB:c'
    hand_known: bool
    cards: str


def _texture_class(board):
    if len(board) not in (3, 4, 5):
        return None               # boards incompletos del recorder: sin clase
    t = board_texture(board)
    base = 'monotone' if t['monotone'] else ('two_tone' if t['two_tone']
                                             else 'rainbow')
    if t['pairs']:
        base += '+pair'
    return base


def _seq(hand, street) -> List[Tuple[str, str, float]]:
    """[(pos, act, amt)] de una calle (dicts o tuplas del DB)."""
    s = (hand.get('streets', {}).get(street, {}) or {})
    out = []
    for a in s.get('actions', []) or []:
        if isinstance(a, dict):
            pos, act = a.get('pos'), a.get('action')
            try:
                amt = float(a.get('amount') or 0.0)
            except (TypeError, ValueError):
                amt = 0.0
        else:
            try:
                pos, act, amt = a[0], a[1], float(a[2] or 0.0)
            except (IndexError, TypeError, ValueError):
                continue
        if pos and act:
            out.append((pos, act, amt))
    return out


def lead_label(street: str, leader: str, pf_initiator: str,
               pot_raised: bool) -> str:
    """Label de un lead (primera apuesta/subida de la calle).

    Fuente de verdad ÚNICA para el etiquetado de leads: lo usa el
    entrenamiento (observations) y el servicio (asistente._villain_postflop)
    para que ambas vías caigan en las mismas celdas (evita el skew).

    - flop/turn del INICIADOR preflop en bote subido → 'cbet' / 'barrel'.
    - flop/turn del NO iniciador en bote subido → 'donk'.
    - resto (river, bote limpeado, preflop) → 'bet'.
    """
    if street == 'flop' and leader == pf_initiator:
        return 'cbet'
    if street == 'turn' and leader == pf_initiator:
        return 'barrel'
    if street in ('flop', 'turn') and pot_raised:
        return 'donk'
    return 'bet'


def extract_hand(hand) -> List[Observation]:
    name_of = {p.get('pos'): (p.get('name') or p.get('pos'))
               for p in hand.get('players', [])}
    stake_of, cards_of, invested = {}, {}, {}
    for p in hand.get('players', []):
        pos = p.get('pos')
        try:
            stake_of[pos] = float(p.get('stack') or 0.0)
        except (TypeError, ValueError):
            stake_of[pos] = 0.0
        cards_of[pos] = p.get('cards') or ''
        invested[pos] = 0.0

    pf_seq = _seq(hand, 'preflop')
    total_players = max(1, len(hand.get('players', [])))
    folded: set = set()
    total = 0.0                     # aportado en la mano hasta la decisión
    pf_raises = 0                    # raises preflop ya contados
    pf_initiator = next((p for p, a, _ in reversed(pf_seq)
                         if a in RAISE_ACTS), '')

    obs: List[Observation] = []
    prev_board: list = []
    for street in STREETS:
        acts = _seq(hand, street)
        board = ((hand.get('streets', {}).get(street, {}) or {}).get('board')
                 or [])
        # La DB real guarda en turn/river SOLO la carta nueva (1), no el
        # board acumulado: reconstruirlo a partir del flop (si no colisiona).
        if (street in ('turn', 'river') and len(board) == 1
                and len(prev_board) >= 3 and board[0] not in prev_board):
            board = prev_board + board
        tclass = _texture_class(board) if street != 'preflop' else None
        if board:
            prev_board = list(board)
        street_facing = None          # label de la apuesta/raise vigente
        for pos, act, amt in acts:
            pot_before = total
            active = max(1, total_players - len(folded))
            pot_type = ('SRP' if pf_raises <= 0 else
                        '3BP' if pf_raises == 1 else '4BP')
            eff = stake_of.get(pos)
            eff_stack = (eff - invested.get(pos, 0.0)) if eff else None

            if street_facing:
                facing = street_facing
            else:
                facing = 'none'
            if act in RAISE_ACTS:
                street_facing = ('raise' if street_facing else
                                 lead_label(street, pos, pf_initiator,
                                            pf_raises >= 1))
            sizing = None
            if act in RAISE_ACTS and pot_before > 0:
                sizing = amt / pot_before

            name = name_of.get(pos, pos)
            obs.append(Observation(
                hand_id=hand.get('hand_id', '?'),
                street=street,
                player=name,
                kind='hero' if name in HERO_NAMES else 'villain',
                pos=pos, action=act, amount=amt, sizing=sizing,
                pot_before=pot_before,
                stack_effective=eff_stack,
                spr=eff_stack / pot_before
                if (eff_stack is not None and pot_before > 0) else 0.0,
                pot_type=pot_type,
                players_active=active,
                board=','.join(board),
                texture_class=tclass,
                facing=facing,
                raised_before=pf_raises if street == 'preflop' else 0,
                preflop_sequence='/'.join(f'{p}:{a}' for p, a, _ in pf_seq),
                hand_known=bool(cards_of.get(pos)),
                cards=cards_of.get(pos, '')))

            if street == 'preflop' and act in RAISE_ACTS:
                pf_raises += 1
            total += amt
            invested[pos] = invested.get(pos, 0.0) + amt
            if act == 'f':
                folded.add(pos)
    return obs


def extract_hands(hands) -> List[Observation]:
    obs = []
    for hand in hands:
        obs.extend(extract_hand(hand))
    return obs


def behavior_table(obs: List[Observation], by_player: Dict[str, str],
                   min_n: int = 3):
    """Frecuencias de acción por (label, street, texture, facing).

    `by_player`: {player: etiqueta de perfil}. Solo celdas con n>=min_n.
    Devuelve {(label, street, texture, facing): {'n': k, 'f': x, 'x': 0.x,
    'c': x, 'b': x, 'r': x, 'sizing_mean': p}} con % sobre el total.
    """
    agg: Dict[tuple, dict] = {}
    for o in obs:
        label = by_player.get(o.player, '?')
        key = (label, o.street, o.texture_class or '-', o.facing)
        cell = agg.setdefault(key, {'n': 0, 'f': 0, 'x': 0, 'c': 0, 'b': 0,
                                    'r': 0, 'size': 0.0})
        cell['n'] += 1
        cell[o.action] += 1
        if o.action in ('b', 'r') and o.sizing is not None:
            cell['size'] += o.sizing
    result = {}
    for key, cell in agg.items():
        if cell['n'] < min_n:
            continue
        out = {a: round(cell[a] / cell['n'], 3)
               for a in ('f', 'x', 'c', 'b', 'r')}
        if cell['b'] + cell['r']:
            out['sizing_mean'] = round(cell['size'] / (cell['b'] + cell['r']),
                                       3)
        out['n'] = cell['n']
        result[key] = out
    return result


def main(argv=None):
    """CLI: python -m motor.observations [--json] [--out PATH]"""
    import sys
    args = list(argv or sys.argv[1:])
    write_json = '--json' in args
    out_path = ''
    if '--out' in args:
        i = args.index('--out')
        out_path = args[i + 1] if len(args) > i + 1 else ''
    hands = load_hands()
    obs = extract_hands(hands)
    print(f'Manos: {len(hands)}  Observaciones: {len(obs)}')
    if write_json:
        path = out_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'observations.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump([vars(o) for o in obs], f, indent=2,
                      ensure_ascii=False)
        print(f'-> {path}')


if __name__ == '__main__':
    main()