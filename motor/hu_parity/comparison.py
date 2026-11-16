"""Comparacion auditable entre la reconstruccion HU y el recorder live.

Cada campo se clasifica como exacto, semantico (normalizacion declarada),
discrepancia relevante o no comparable por falta de evidencia. La ausencia de
datos nunca se convierte en equivalencia.
"""
from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import MethodType
from typing import Any, Mapping, Optional, Tuple

_PKG_ROOT = Path(__file__).resolve().parents[2]
for _sub in ('tools', 'recorder'):
    _path = str(_PKG_ROOT / _sub)
    if _path not in sys.path:
        sys.path.insert(0, _path)

import recorder_live

from ..hu_experimental.state import HUState, interpret_state


EXACT = 'exact'
SEMANTIC = 'semantic'
DISCREPANCY = 'discrepancy'
NOT_COMPARABLE = 'not_comparable'


@dataclass(frozen=True)
class FieldComparison:
    field: str
    status: str
    experimental: Any
    live: Any
    code: Optional[str] = None
    normalization: Optional[str] = None
    note: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            'field': self.field,
            'status': self.status,
            'experimental': self.experimental,
            'live': self.live,
            'code': self.code,
            'normalization': self.normalization,
            'note': self.note,
        }


@dataclass(frozen=True)
class StateComparison:
    hu: HUState
    live: Mapping[str, Any]
    comparisons: Tuple[FieldComparison, ...]

    @property
    def discrepancies(self) -> Tuple[Mapping[str, Any], ...]:
        return tuple(item.as_dict() for item in self.comparisons
                     if item.status == DISCREPANCY)

    @property
    def not_comparable(self) -> Tuple[Mapping[str, Any], ...]:
        return tuple(item.as_dict() for item in self.comparisons
                     if item.status == NOT_COMPARABLE)

    @property
    def classification(self) -> str:
        statuses = {item.status for item in self.comparisons}
        if DISCREPANCY in statuses:
            return 'relevant_discrepancy'
        if NOT_COMPARABLE in statuses:
            return 'not_comparable_insufficient_information'
        if SEMANTIC in statuses:
            return 'semantic_equivalence'
        return 'exact_equivalence'

    @property
    def matches(self) -> bool:
        return self.classification in ('exact_equivalence',
                                       'semantic_equivalence')

    def as_dict(self) -> dict:
        return {
            'hu': self.hu.as_dict(),
            'live': dict(self.live),
            'comparisons': [item.as_dict() for item in self.comparisons],
            'discrepancies': list(self.discrepancies),
            'not_comparable': list(self.not_comparable),
            'classification': self.classification,
            'matches': self.matches,
            'normalizations': {
                'stack': ('el recorder almacena stake + apuesta visible; '
                          'se resta la apuesta actual para comparar stack detras'),
                'cards': 'rango normalizado a mayuscula, palo a minuscula',
                'money': 'igualdad numerica con tolerancia 1e-9; sin redondeo',
            },
        }


def compare_frame_state(state: Mapping[str, Any], *,
                        work_dir: Optional[Any] = None,
                        manual_positions: Optional[Mapping[str, str]] = None,
                        hero_seat: str = 'hero') -> StateComparison:
    """Reconstruye un mismo frame con ambos sistemas y clasifica campos.

    ``manual_positions`` habilita la correccion HU explicita. Cuando se usa
    SB/BB, el recorder de esta instancia recibe tambien el orden de accion
    correcto para HU: SB luego BB preflop y BB luego SB postflop.
    """
    root = Path(work_dir) if work_dir is not None else Path(
        tempfile.mkdtemp(prefix='hu_compare_'))
    root.mkdir(parents=True, exist_ok=True)
    recorder = recorder_live.LiveRecorder(
        output_path=str(root / 'hands_compare.jsonl'),
        ambiguity_capture_dir=str(root / 'ambiguedades'),
    )

    previous_positions = dict(recorder_live.MANUAL_POSITIONS)
    try:
        if manual_positions is not None:
            recorder_live.MANUAL_POSITIONS.clear()
            recorder_live.MANUAL_POSITIONS.update(manual_positions)
            if set(manual_positions.values()) >= {'SB', 'BB'}:
                def hu_street_order(_recorder, frame_state, street_name):
                    del frame_state
                    if street_name == 'preflop':
                        return ['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB']
                    return ['BB', 'SB', 'UTG', 'MP', 'CO', 'BTN']
                recorder._get_street_order = MethodType(
                    hu_street_order, recorder)
        recorder.process_frame(state, None, log=lambda *_: None)
        if recorder.hand is None:
            recorder.start_hand(state)
        else:
            # Un segundo frame idéntico permite actualizar max_pot y las
            # transiciones de calle sin introducir información posterior.
            recorder.process_frame(state, None, log=lambda *_: None)
    finally:
        recorder_live.MANUAL_POSITIONS.clear()
        recorder_live.MANUAL_POSITIONS.update(previous_positions)

    hu = interpret_state(state, hero_seat=hero_seat)
    hand = recorder.hand
    if hand is None:
        return StateComparison(
            hu=hu, live={}, comparisons=(FieldComparison(
                field='hand_state', status=NOT_COMPARABLE,
                experimental='interpreted', live=None,
                code='live_hand_not_started',
                note='El recorder live no inicio mano con este frame.'),))

    players = {p.get('_id'): p for p in hand.get('players') or []}
    active_players = [p for p in players.values() if p.get('active')]
    active_ids = tuple(sorted(p.get('_id') for p in active_players
                              if p.get('_id')))
    positions = {pid: p.get('pos') for pid, p in players.items()
                 if p.get('active')}
    hero_id = hu.hero_seat
    villain_id = hu.villain_seat
    hero_player = players.get(hero_id)
    villain_player = players.get(villain_id)
    current_street = hand.get('current_street') or 'preflop'
    current_actions = (((hand.get('streets') or {}).get(current_street) or {})
                       .get('actions') or [])
    contributions_by_pos = recorder._street_contributions(
        current_street, apply_returns=True)
    hero_position = positions.get(hero_id)
    villain_position = positions.get(villain_id)
    live_contributions = {
        hero_id: contributions_by_pos.get(hero_position)
        if hero_position else None,
        villain_id: contributions_by_pos.get(villain_position)
        if villain_position else None,
    }

    def stake_behind(player, seat):
        if player is None:
            return None
        stack = player.get('stack')
        bet = state.get('%s_bet' % seat)
        if _number(stack) is None or _number(bet) is None:
            return None
        return float(stack) - float(bet)

    live_button = next((pid for pid, pos in positions.items()
                        if pos == 'BTN'), None)
    button_source = 'derived_from_live_position'
    if live_button is None and state.get('btn'):
        live_button = state.get('btn')
        button_source = 'input_btn_fallback'

    live_to_call = None
    hero_live_contribution = live_contributions.get(hero_id)
    if hero_live_contribution is not None and all(
            value is not None for value in live_contributions.values()):
        live_to_call = max(
            max(live_contributions.values()) - hero_live_contribution, 0.0)

    live_player_to_act = _live_player_to_act(recorder, state, hu)
    expected_to_act = state.get('player_to_act', state.get('to_act'))
    live_hand_state = 'in_progress' if hand is not None else None
    explicit_hand_state = state.get('hand_state')
    community = hand.get('comunitarias') or {}
    live_board = tuple(
        card for street_name in ('flop', 'turn', 'river')
        for card in (community.get(street_name) or ())
    )
    if not live_board:
        live_board = tuple(card for street_name in ('flop', 'turn', 'river')
                           for card in ((hand.get('streets') or {}).get(
                               street_name, {}).get('board') or ()))

    live = {
        'active_seats': active_ids,
        'active_count': len(active_ids),
        'positions': positions,
        'hero_id': hero_id if hero_player else None,
        'villain_id': villain_id if villain_player else None,
        'hero_position': hero_position,
        'villain_position': villain_position,
        'hero_cards': _split_cards(hero_player.get('cards')
                                   if hero_player else None),
        'villain_cards': _split_cards(villain_player.get('cards')
                                      if villain_player else None),
        'board': live_board,
        'pot': hand.get('max_pot'),
        'street': current_street,
        'hand_state': live_hand_state,
        'explicit_hand_state': explicit_hand_state,
        'button_seat': live_button,
        'button_source': button_source,
        'hero_stack': stake_behind(hero_player, hero_id),
        'villain_stack': stake_behind(villain_player, villain_id),
        'hero_bet': live_contributions.get(hero_id),
        'villain_bet': live_contributions.get(villain_id),
        'raw_hero_bet': state.get('%s_bet' % hero_id),
        'raw_villain_bet': state.get('%s_bet' % villain_id),
        'hero_contribution': live_contributions.get(hero_id),
        'villain_contribution': live_contributions.get(villain_id),
        'to_call': live_to_call,
        'pending_action': ('facing_bet' if live_to_call is not None
                           and live_to_call > 1e-9 else
                           'check_or_bet' if live_to_call is not None else None),
        'player_to_act': live_player_to_act,
        'player_to_act_source': 'asistente_live._next_to_act',
        'actions': _safe_actions(hand),
        'current_actions': _safe_actions({'streets': {
            current_street: {'actions': current_actions}}})[current_street],
    }

    comparisons = []
    _add(comparisons, 'active_count', len(hu.active_seats), len(active_ids))
    _add(comparisons, 'active_players', tuple(sorted(hu.active_seats)), active_ids)
    _add(comparisons, 'hero_identity', hu.hero_seat, live['hero_id'])
    _add(comparisons, 'villain_identity', hu.villain_seat, live['villain_id'])
    _add_position(comparisons, 'hero_position', hu.hero_position, hero_position)
    _add_position(comparisons, 'villain_position', hu.villain_position,
                  villain_position)
    _add(comparisons, 'hero_private_cards', tuple(hu.hero_cards),
         live['hero_cards'], normalizer=_normalize_cards,
         semantic_normalization='rank upper-case, suit lower-case, 10→T')
    _add(comparisons, 'villain_private_cards',
         _state_cards(state, villain_id), live['villain_cards'],
         normalizer=_normalize_cards,
         semantic_normalization='rank upper-case, suit lower-case, 10→T')
    _add(comparisons, 'board', tuple(hu.board), live['board'],
         normalizer=_normalize_cards,
         semantic_normalization='rank upper-case, suit lower-case, 10→T')
    _add(comparisons, 'street', hu.street, live['street'])
    _add(comparisons, 'button_seat', hu.button_seat,
         live_button if button_source == 'derived_from_live_position' else None,
         note=('En SB/BB el hand live no persiste el botón; el fallback procede '
               'del mismo frame y no es una comparación independiente.'))
    _add(comparisons, 'hero_stack', hu.hero_stack, live['hero_stack'],
         semantic_normalization=(
             'live_player.stack = stake visible + bet; se resta la apuesta '
             'visible para obtener stack detras'))
    _add(comparisons, 'villain_stack', hu.villain_stack,
         live['villain_stack'], semantic_normalization=(
             'live_player.stack = stake visible + bet; se resta la apuesta '
             'visible para obtener stack detras'))
    _add(comparisons, 'pot', hu.pot, live['pot'])
    _add(comparisons, 'hero_bet', hu.hero_bet, live['hero_bet'])
    _add(comparisons, 'villain_bet', hu.villain_bet, live['villain_bet'])
    _add(comparisons, 'hero_contribution', hu.hero_bet,
         live['hero_contribution'])
    _add(comparisons, 'villain_contribution', hu.villain_bet,
         live['villain_contribution'])
    _add(comparisons, 'to_call', hu.to_call, live_to_call)
    hu_pending = (None if hu.to_call is None else
                  'facing_bet' if hu.to_call > 1e-9 else 'check_or_bet')
    _add(comparisons, 'pending_action', hu_pending, live['pending_action'])
    _add(comparisons, 'player_to_act', expected_to_act, live_player_to_act,
         code='turn_order',
         note=('Solo comparable si el fixture/frame aporta player_to_act o '
               'to_act; el recorder no recibe un marcador visual de turno.'))
    normalized_hand_state = _normalize_hand_state(explicit_hand_state)
    _add(comparisons, 'hand_state', normalized_hand_state, live_hand_state,
         note='hand_state requiere una etiqueta explicita en el frame.')

    return StateComparison(hu=hu, live=live,
                           comparisons=tuple(comparisons))


def _live_player_to_act(recorder, state, hu):
    if hu.villain_seat is None:
        return None
    try:
        from .. import asistente_live as live_module
        probe = live_module.Asistente.__new__(live_module.Asistente)
        probe.rec = recorder
        probe.hero_name = 'Hero'
        candidates = [seat for seat in (hu.hero_seat, hu.villain_seat)
                      if probe._next_to_act(state, seat)]
        return candidates[0] if len(candidates) == 1 else None
    except Exception:
        return None


def _add(comparisons, field, experimental, live, *,
         semantic_normalization=None, code=None, note=None, normalizer=None):
    if experimental is None or live is None:
        status = NOT_COMPARABLE
        normalization = semantic_normalization
    else:
        left = normalizer(experimental) if normalizer else experimental
        right = normalizer(live) if normalizer else live
        equal = _equal(left, right)
        if not equal:
            status = DISCREPANCY
        elif (semantic_normalization and normalizer
              and not _equal(experimental, live)) or semantic_normalization and not normalizer:
            status = SEMANTIC
        elif normalizer and not _equal(experimental, live):
            status = SEMANTIC
        else:
            status = EXACT
        normalization = (semantic_normalization
                         if status == SEMANTIC else None)
    comparisons.append(FieldComparison(
        field=field, status=status, experimental=experimental, live=live,
        code=code or (field if status == DISCREPANCY else None),
        normalization=normalization, note=note))


def _add_position(comparisons, field, experimental, live):
    code = None
    note = None
    if {experimental, live} == {'SB', 'BTN'}:
        code = 'position_mapping_btn_vs_sb'
        note = ('El interprete HU nombra SB al boton; live_default conserva '
                'BTN. Es una correccion deliberada, no equivalencia exacta.')
    _add(comparisons, field, experimental, live, code=code, note=note)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _equal(left, right, tolerance=1e-9):
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) <= tolerance
    return left == right


def _normalize_cards(cards):
    if cards is None:
        return None
    out = []
    for card in cards:
        text = str(card).strip()
        if len(text) == 3 and text[:2] == '10':
            text = 'T' + text[2]
        if len(text) == 2:
            text = text[0].upper() + text[1].lower()
        out.append(text)
    return tuple(out)


def _state_cards(state, seat):
    if not seat:
        return None
    raw = state.get('%s_cards' % seat)
    if raw is None and seat == 'hero':
        raw = state.get('hero_cards')
    if raw is None:
        return None
    return _normalize_cards(_split_cards(raw))


def _normalize_hand_state(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ('active', 'in_progress', 'in progress', 'playing'):
        return 'in_progress'
    if text in ('complete', 'completed', 'finished', 'showdown', 'closed'):
        return 'complete'
    return text


def _split_cards(cards):
    if not cards:
        return ()
    if isinstance(cards, str):
        text = cards.strip()
        out = []
        index = 0
        while index < len(text):
            width = 3 if text[index:index + 2] == '10' else 2
            if index + width > len(text):
                break
            out.append(text[index:index + width])
            index += width
        return tuple(out)
    out = []
    for card in cards:
        if isinstance(card, Mapping):
            rank, suit = card.get('rank'), card.get('suit')
            out.append('%s%s' % (rank, suit) if rank and suit else '')
        else:
            out.append(str(card))
    return tuple(card for card in out if card)


def _safe_actions(hand) -> dict:
    result = {}
    for street, record in (hand.get('streets') or {}).items():
        result[street] = [
            {k: action.get(k) for k in
             ('pos', 'action', 'amount', 'amount_type')}
            for action in record.get('actions') or []
        ]
    return result
