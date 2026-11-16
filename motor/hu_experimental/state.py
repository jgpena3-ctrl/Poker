"""Interpretacion conservadora del estado capturado de una mesa HU.

No completa campos ausentes y no convierte ``None`` en cero. Cuando el estado
no permite una decision HU, devuelve un estado ``no_decision`` o ``unresolved``
con motivos inspeccionables.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Tuple


SEATS = ('hero', 'p1', 'p2', 'p3', 'p4', 'p5')
INACTIVE_LABELS = frozenset({
    'retirarse', 'ausente', 'inactivo', 'sin jugador', 'fuera', 'folded',
    'inactive', 'empty',
})
RANKS = frozenset('23456789TJQKA')
SUITS = frozenset('shdc')


class StateInterpretationError(ValueError):
    """El estado capturado no tiene un formato interpretable."""


@dataclass(frozen=True)
class HUState:
    status: str
    reason: Optional[str]
    hero_seat: str
    villain_seat: Optional[str]
    hero_position: Optional[str]
    villain_position: Optional[str]
    active_seats: Tuple[str, ...]
    street: str
    hero_cards: Tuple[str, ...]
    board: Tuple[str, ...]
    pot: Optional[float]
    to_call: Optional[float]
    hero_stack: Optional[float]
    villain_stack: Optional[float]
    hero_bet: Optional[float]
    villain_bet: Optional[float]
    button_seat: Optional[str]
    uncertainty_reasons: Tuple[str, ...] = ()
    observed_fields: Tuple[str, ...] = ()
    raw_state: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.status not in ('ready', 'unresolved', 'no_decision'):
            raise ValueError('status de estado HU invalido')
        if self.hero_seat not in SEATS:
            raise ValueError('hero_seat invalido')
        if self.villain_seat is not None and self.villain_seat not in SEATS:
            raise ValueError('villain_seat invalido')
        if self.hero_position is not None and self.hero_position not in ('SB', 'BB', 'BTN'):
            raise ValueError('hero_position invalida')
        if self.villain_position is not None and self.villain_position not in ('SB', 'BB', 'BTN'):
            raise ValueError('villain_position invalida')
        if self.street not in ('preflop', 'flop', 'turn', 'river'):
            raise ValueError('street invalida')
        for name in ('pot', 'to_call', 'hero_stack', 'villain_stack',
                     'hero_bet', 'villain_bet'):
            value = getattr(self, name)
            if value is not None:
                if not math.isfinite(float(value)) or float(value) < 0:
                    raise ValueError('%s debe ser finito y no negativo' % name)

    @property
    def ready(self) -> bool:
        return self.status == 'ready'

    @property
    def can_estimate(self) -> bool:
        return self.ready and len(self.hero_cards) == 2

    def as_dict(self) -> dict:
        return {
            'status': self.status,
            'reason': self.reason,
            'hero_seat': self.hero_seat,
            'villain_seat': self.villain_seat,
            'hero_position': self.hero_position,
            'villain_position': self.villain_position,
            'active_seats': list(self.active_seats),
            'street': self.street,
            'hero_cards': list(self.hero_cards),
            'board': list(self.board),
            'pot': self.pot,
            'to_call': self.to_call,
            'hero_stack': self.hero_stack,
            'villain_stack': self.villain_stack,
            'hero_bet': self.hero_bet,
            'villain_bet': self.villain_bet,
            'button_seat': self.button_seat,
            'uncertainty_reasons': list(self.uncertainty_reasons),
            'observed_fields': list(self.observed_fields),
        }


def _as_number(value: Any, name: str, reasons: list) -> Optional[float]:
    if value is None:
        reasons.append('%s_not_observed' % name)
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        reasons.append('%s_not_numeric' % name)
        return None
    value = float(value)
    if not math.isfinite(value) or value < 0:
        reasons.append('%s_invalid' % name)
        return None
    return value


def _card_code(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, Mapping):
        rank = value.get('rank')
        suit = value.get('suit')
        if rank in (None, '') or suit in (None, ''):
            return None
        value = '%s%s' % (rank, suit)
    if not isinstance(value, str):
        raise StateInterpretationError('carta con formato invalido')
    text = value.strip()
    if not text:
        return None
    if len(text) == 3 and text[:2] == '10':
        text = 'T' + text[2]
    if len(text) != 2:
        raise StateInterpretationError('carta con longitud invalida: %r' % value)
    rank = text[0].upper()
    suit = text[1].lower()
    if rank not in RANKS or suit not in SUITS:
        raise StateInterpretationError('carta invalida: %r' % value)
    return rank + suit


def _cards(values: Any, name: str) -> Tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = [values[i:i + 2] for i in range(0, len(values), 2)]
    if not isinstance(values, Iterable) or isinstance(values, Mapping):
        raise StateInterpretationError('%s debe ser una secuencia' % name)
    out = []
    for item in values:
        code = _card_code(item)
        if code is not None:
            out.append(code)
    return tuple(out)


def _duplicates(values: Iterable[str]) -> Tuple[str, ...]:
    seen = set()
    dup = set()
    for value in values:
        if value in seen:
            dup.add(value)
        seen.add(value)
    return tuple(sorted(dup))


def _street(board: Tuple[str, ...]) -> str:
    if len(board) == 0:
        return 'preflop'
    if len(board) == 3:
        return 'flop'
    if len(board) == 4:
        return 'turn'
    return 'river'


def interpret_state(state: Mapping[str, Any], *,
                    hero_seat: str = 'hero') -> HUState:
    """Normaliza un estado capturado sin inventar campos ausentes."""
    if not isinstance(state, Mapping):
        raise StateInterpretationError('state debe ser un mapping')
    if hero_seat not in SEATS:
        raise StateInterpretationError('hero_seat invalido')
    reasons = []
    observed = []

    active = []
    for seat in SEATS:
        state_key = '%s_state' % seat
        if state_key not in state:
            continue
        value = state.get(state_key)
        if isinstance(value, str):
            text = value.strip().lower()
            if text and text not in INACTIVE_LABELS:
                active.append(seat)
            observed.append('%s_state' % seat)
        elif value is None:
            reasons.append('%s_state_unknown' % seat)
    active_seats = tuple(active)

    if hero_seat not in active_seats:
        return HUState(
            status='no_decision', reason='hero_not_active',
            hero_seat=hero_seat, villain_seat=None, hero_position=None,
            villain_position=None, active_seats=active_seats,
            street='preflop', hero_cards=(), board=(), pot=None,
            to_call=None, hero_stack=None, villain_stack=None, hero_bet=None,
            villain_bet=None, button_seat=None,
            uncertainty_reasons=tuple(reasons), observed_fields=tuple(observed),
            raw_state=dict(state),
        )
    if len(active_seats) != 2:
        reasons.append('not_heads_up:%d_active' % len(active_seats))
        return HUState(
            status='no_decision', reason='not_heads_up',
            hero_seat=hero_seat,
            villain_seat=(active_seats[0] if active_seats[0] != hero_seat
                          else active_seats[1] if len(active_seats) > 1 else None),
            hero_position=None, villain_position=None,
            active_seats=active_seats, street='preflop', hero_cards=(),
            board=(), pot=None, to_call=None, hero_stack=None,
            villain_stack=None, hero_bet=None, villain_bet=None,
            button_seat=state.get('btn') if isinstance(state.get('btn'), str)
            else None,
            uncertainty_reasons=tuple(reasons), observed_fields=tuple(observed),
            raw_state=dict(state),
        )

    villain_seat = active_seats[0] if active_seats[0] != hero_seat else active_seats[1]

    try:
        hero_cards = _cards(state.get('hero_cards'), 'hero_cards')
        board = _cards(state.get('community', state.get('board')), 'board')
    except StateInterpretationError as exc:
        reasons.append(str(exc))
        return HUState(
            status='no_decision', reason='invalid_cards', hero_seat=hero_seat,
            villain_seat=villain_seat, hero_position=None,
            villain_position=None, active_seats=active_seats,
            street='preflop', hero_cards=(), board=(), pot=None, to_call=None,
            hero_stack=None, villain_stack=None, hero_bet=None, villain_bet=None,
            button_seat=state.get('btn') if isinstance(state.get('btn'), str)
            else None,
            uncertainty_reasons=tuple(reasons), observed_fields=tuple(observed),
            raw_state=dict(state),
        )

    if len(board) not in (0, 3, 4, 5):
        reasons.append('invalid_board_count:%d' % len(board))
        return HUState(
            status='no_decision', reason='invalid_board', hero_seat=hero_seat,
            villain_seat=villain_seat, hero_position=None,
            villain_position=None, active_seats=active_seats,
            street='preflop', hero_cards=hero_cards, board=board, pot=None,
            to_call=None, hero_stack=None, villain_stack=None, hero_bet=None,
            villain_bet=None, button_seat=state.get('btn') if isinstance(state.get('btn'), str)
            else None,
            uncertainty_reasons=tuple(reasons), observed_fields=tuple(observed),
            raw_state=dict(state),
        )

    duplicates = _duplicates(hero_cards + board)
    if duplicates:
        reasons.append('duplicate_cards:%s' % ','.join(duplicates))
        return HUState(
            status='no_decision', reason='duplicate_cards', hero_seat=hero_seat,
            villain_seat=villain_seat, hero_position=None,
            villain_position=None, active_seats=active_seats,
            street=_street(board), hero_cards=hero_cards, board=board, pot=None,
            to_call=None, hero_stack=None, villain_stack=None, hero_bet=None,
            villain_bet=None, button_seat=state.get('btn') if isinstance(state.get('btn'), str)
            else None,
            uncertainty_reasons=tuple(reasons), observed_fields=tuple(observed),
            raw_state=dict(state),
        )

    if len(hero_cards) != 2:
        reasons.append('hero_cards_not_observed')
    if len(board) >= 3:
        observed.append('community')
    observed.append('hero_cards')

    button = state.get('btn')
    if button not in SEATS:
        reasons.append('button_not_observed')
        button_seat = None
        hero_position = None
        villain_position = None
    else:
        button_seat = button
        observed.append('btn')
        if button == hero_seat:
            # En HU el boton es la ciega pequena; el contrato preflop usa SB/BB.
            hero_position, villain_position = 'SB', 'BB'
        elif button == villain_seat:
            hero_position, villain_position = 'BB', 'SB'
        else:
            reasons.append('button_not_in_hand')
            hero_position = villain_position = None

    pot = _as_number(state.get('pot'), 'pot', reasons)
    hero_stack = _as_number(state.get('%s_stake' % hero_seat),
                            'hero_stack', reasons)
    villain_stack = _as_number(state.get('%s_stake' % villain_seat),
                               'villain_stack', reasons)
    hero_bet = _as_number(state.get('%s_bet' % hero_seat),
                          'hero_bet', reasons)
    villain_bet = _as_number(state.get('%s_bet' % villain_seat),
                             'villain_bet', reasons)

    explicit_to_call = state.get('to_call')
    if explicit_to_call is not None:
        to_call = _as_number(explicit_to_call, 'to_call', reasons)
        observed.append('to_call')
    elif hero_bet is not None and villain_bet is not None:
        to_call = max(villain_bet - hero_bet, 0.0)
        observed.append('to_call_derived_from_bets')
    else:
        to_call = None

    for name, value in (('pot', pot), ('hero_stack', hero_stack),
                        ('villain_stack', villain_stack),
                        ('hero_bet', hero_bet), ('villain_bet', villain_bet)):
        if value is not None:
            observed.append(name)

    status = 'ready'
    reason = None
    if len(hero_cards) != 2:
        status = 'unresolved'
        reason = 'hero_cards_not_observed'
    elif hero_position is None or villain_position is None:
        status = 'unresolved'
        reason = 'position_not_observed'
    elif pot is None or hero_stack is None or villain_stack is None:
        status = 'unresolved'
        reason = 'economic_state_incomplete'
    elif to_call is None:
        status = 'unresolved'
        reason = 'to_call_not_observed'

    return HUState(
        status=status, reason=reason, hero_seat=hero_seat,
        villain_seat=villain_seat, hero_position=hero_position,
        villain_position=villain_position, active_seats=active_seats,
        street=_street(board), hero_cards=hero_cards, board=board, pot=pot,
        to_call=to_call, hero_stack=hero_stack, villain_stack=villain_stack,
        hero_bet=hero_bet, villain_bet=villain_bet, button_seat=button_seat,
        uncertainty_reasons=tuple(reasons), observed_fields=tuple(observed),
        raw_state=dict(state),
    )
