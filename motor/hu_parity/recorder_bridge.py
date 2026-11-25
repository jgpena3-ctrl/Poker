"""Puente experimental entre el recorder original y la capa HU.

El recorder original sigue siendo el unico propietario de la deteccion. Este
modulo no reproduce OCR ni heuristica de acciones: envuelve ``LiveRecorder`` y
congela, despues de cada ``process_frame``, un ``RecorderSnapshot`` inmutable.

Reglas de la fase 10.5:

* El estado bruto de la captura nunca se muta para adaptarlo a HU.
* El motor original sigue recibiendo el estado bruto de la captura.
* La capa HU usa exclusivamente ``RecorderSnapshot``/``DecisionStateView``.
* En modo diagnostico no se persisten manos, decisiones ni evidencias.
* Las contradicciones bloqueantes producen abstención; nunca se corrigen en
  silencio ni se convierten valores desconocidos en cero.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional, Tuple

_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
for _sub in ('tools', 'recorder'):
    _path = os.path.join(_PKG_ROOT, _sub)
    if _path not in sys.path:
        sys.path.insert(0, _path)

import recorder_live  # noqa: E402

from ..hu_experimental.state import (  # noqa: E402
    ACTIVE_LABELS,
    INACTIVE_LABELS,
    SEATS,
    HUState,
    StateInterpretationError,
    _card_code,
    _duplicates,
    _street,
)


_CARD_TEXT = re.compile(r'(10|[2-9TJQKA])([shdc])', re.IGNORECASE)
_CARD_TOLERANCE = 0.15


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, default=str))
    except (TypeError, ValueError):
        return str(value)


def _plain(value: Any) -> Any:
    """Convierte el snapshot a estructuras JSON sin perder campos."""
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_plain(v) for v in value]
    if dataclass_is_instance(value):
        return _plain(value.as_dict())
    return value


def _freeze(value: Any) -> Any:
    """Copia recursivamente a contenedores de solo lectura."""
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(v) for v in value)
    return value


def dataclass_is_instance(value: Any) -> bool:
    return hasattr(value, 'as_dict') and hasattr(value, '__dataclass_fields__')


def _as_number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) and value >= 0 else None


def _read_number(raw: Mapping[str, Any], key: str) -> Tuple[Optional[float], bool]:
    """Devuelve (valor, observado) sin convertir None/invalidos en cero."""
    if key not in raw:
        return None, False
    return _as_number(raw.get(key)), True


def _cards_strict(values: Any, name: str) -> Tuple[str, ...]:
    """Normaliza cartas y conserva el error de formato para la auditoria."""
    if values is None:
        return ()
    if isinstance(values, str):
        text = values.strip()
        if not text:
            return ()
        matches = _CARD_TEXT.findall(text)
        if not matches:
            raise StateInterpretationError('%s invalidas: %r' % (name, values))
        remainder = _CARD_TEXT.sub('', text).strip()
        if remainder:
            raise StateInterpretationError(
                '%s con caracteres invalidos: %r' % (name, values))
        return tuple(
            (rank.upper().replace('10', 'T')) + suit.lower()
            for rank, suit in matches
        )
    if isinstance(values, Mapping) or not isinstance(values, Iterable):
        raise StateInterpretationError('%s debe ser una secuencia' % name)
    out = []
    for item in values:
        code = _card_code(item)
        if code is not None:
            out.append(code)
    return tuple(out)


def _cards_safe(values: Any, name: str,
                errors: list) -> Tuple[str, ...]:
    try:
        return _cards_strict(values, name)
    except StateInterpretationError as exc:
        errors.append('%s:%s' % (name, exc))
        return ()


def _cards_equal(left: Tuple[str, ...], right: Tuple[str, ...],
                 ordered: bool = False) -> bool:
    if not left or not right:
        return True
    if ordered:
        return left == right
    return sorted(left) == sorted(right)


def _fmt_cards(values: Iterable[str]) -> str:
    return ','.join(values) if values else 'none'


def _fmt_number(value: Optional[float]) -> str:
    return 'unknown' if value is None else ('%.4g' % value)


def _image_sha256(image: Any) -> Optional[str]:
    if image is None:
        return None
    if isinstance(image, bytes):
        payload = image
    elif hasattr(image, 'tobytes'):
        try:
            payload = image.tobytes()
        except Exception:
            return None
    else:
        return None
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class DecisionStateView:
    """Vista normalizada y exclusiva de la capa HU.

    El motor original no consume esta vista. Incluye tanto las posiciones
    registradas por el recorder (``BTN/BB`` en ``live_default``) como la
    normalizacion HU (``SB/BB``), sin modificar el estado bruto.
    """

    hero_seat: str
    villain_seat: Optional[str]
    active_seats: Tuple[str, ...]
    recorder_positions: Mapping[str, str]
    hu_positions: Mapping[str, str]
    button_seat: Optional[str]
    street: str
    hero_cards: Tuple[str, ...]
    board: Tuple[str, ...]
    pot: Optional[float]
    pot_read: Optional[float]
    pot_recorded: Optional[float]
    to_call: Optional[float]
    hero_stack: Optional[float]
    villain_stack: Optional[float]
    hero_bet: Optional[float]
    villain_bet: Optional[float]
    hero_contribution: Optional[float]
    villain_contribution: Optional[float]
    actions: Tuple[Mapping[str, Any], ...]
    contradictions: Tuple[str, ...]
    ambiguities: Tuple[str, ...]
    provenance: Mapping[str, str]
    observed_fields: Tuple[str, ...]
    unknown_fields: Tuple[str, ...]
    hand_id: Optional[str]
    board_observed: bool

    def as_dict(self) -> dict:
        return {
            'hero_seat': self.hero_seat,
            'villain_seat': self.villain_seat,
            'active_seats': list(self.active_seats),
            'recorder_positions': dict(self.recorder_positions),
            'hu_positions': dict(self.hu_positions),
            'button_seat': self.button_seat,
            'street': self.street,
            'hero_cards': list(self.hero_cards),
            'board': list(self.board),
            'pot': self.pot,
            'pot_read': self.pot_read,
            'pot_recorded': self.pot_recorded,
            'to_call': self.to_call,
            'hero_stack': self.hero_stack,
            'villain_stack': self.villain_stack,
            'hero_bet': self.hero_bet,
            'villain_bet': self.villain_bet,
            'hero_contribution': self.hero_contribution,
            'villain_contribution': self.villain_contribution,
            'actions': _plain(self.actions),
            'contradictions': list(self.contradictions),
            'ambiguities': list(self.ambiguities),
            'provenance': dict(self.provenance),
            'observed_fields': list(self.observed_fields),
            'unknown_fields': list(self.unknown_fields),
            'hand_id': self.hand_id,
            'board_observed': self.board_observed,
        }


@dataclass(frozen=True)
class RecorderSnapshot:
    """Foto inmutable de una lectura y del estado reconstruido por recorder."""

    sequence: int
    fingerprint: str
    processed: bool
    captured_at: Optional[str]
    capture_source: Optional[str]
    image_sha256: Optional[str]
    raw_state: Mapping[str, Any]
    recorder_state: Optional[Mapping[str, Any]]
    hand: Optional[Mapping[str, Any]]
    finalized_hands: Tuple[Mapping[str, Any], ...]
    positions: Mapping[str, str]
    button_read: Optional[str]
    button_recorded: Optional[str]
    active_seats: Tuple[str, ...]
    folded_seats: Tuple[str, ...]
    inactive_seats: Tuple[str, ...]
    allin_seats: Tuple[str, ...]
    cards_read: Mapping[str, Tuple[str, ...]]
    cards_recorded: Mapping[str, Tuple[str, ...]]
    stacks_read: Mapping[str, Optional[float]]
    bets_read: Mapping[str, Optional[float]]
    board_read: Tuple[str, ...]
    board_recorded: Tuple[str, ...]
    street: str
    pot_read: Optional[float]
    pot_read_source: Optional[str]
    pot_live_calculated: Optional[float]
    pot_final_calculated: Optional[float]
    pot_breakdown: Mapping[str, Any]
    contributions: Mapping[str, Optional[float]]
    contributions_by_street: Mapping[str, Mapping[str, Optional[float]]]
    to_call: Optional[float]
    to_call_source: str
    actions_by_street: Mapping[str, Tuple[Mapping[str, Any], ...]]
    ambiguities: Tuple[Mapping[str, Any], ...]
    contradictions: Tuple[str, ...]
    observed_fields: Tuple[str, ...]
    unknown_fields: Tuple[str, ...]
    decision_view: DecisionStateView

    def as_dict(self) -> dict:
        return {
            'sequence': self.sequence,
            'fingerprint': self.fingerprint,
            'processed': self.processed,
            'captured_at': self.captured_at,
            'capture_source': self.capture_source,
            'image_sha256': self.image_sha256,
            'raw_state': _plain(self.raw_state),
            'recorder_state': _plain(self.recorder_state),
            'hand': _plain(self.hand),
            'finalized_hands': _plain(self.finalized_hands),
            'positions': dict(self.positions),
            'button_read': self.button_read,
            'button_recorded': self.button_recorded,
            'active_seats': list(self.active_seats),
            'folded_seats': list(self.folded_seats),
            'inactive_seats': list(self.inactive_seats),
            'allin_seats': list(self.allin_seats),
            'cards_read': {k: list(v) for k, v in self.cards_read.items()},
            'cards_recorded': {
                k: list(v) for k, v in self.cards_recorded.items()},
            'stacks_read': dict(self.stacks_read),
            'bets_read': dict(self.bets_read),
            'board_read': list(self.board_read),
            'board_recorded': list(self.board_recorded),
            'street': self.street,
            'pot_read': self.pot_read,
            'pot_read_source': self.pot_read_source,
            'pot_live_calculated': self.pot_live_calculated,
            'pot_final_calculated': self.pot_final_calculated,
            'pot_breakdown': _plain(self.pot_breakdown),
            'contributions': dict(self.contributions),
            'contributions_by_street': _plain(self.contributions_by_street),
            'to_call': self.to_call,
            'to_call_source': self.to_call_source,
            'actions_by_street': _plain(self.actions_by_street),
            'ambiguities': _plain(self.ambiguities),
            'contradictions': list(self.contradictions),
            'observed_fields': list(self.observed_fields),
            'unknown_fields': list(self.unknown_fields),
            'decision_view': self.decision_view.as_dict(),
        }


class SnapshotLiveRecorder(recorder_live.LiveRecorder):
    """Extiende el recorder original sin duplicar su maquina de estados.

    En ``diagnostic_mode`` la finalizacion se ejecuta en memoria para conservar
    el ciclo de vida de la mano, pero toda salida persistente se intercepta:
    el hand DB se redirige a ``os.devnull``, los sidecars de sesion y las
    evidencias de ambiguedad no se escriben y no se invoca ningun callback
    persistente. El ledger prospectivo no se toca desde este objeto.
    """

    def __init__(self, *args, diagnostic_mode: bool = True,
                 allow_finalized_callback: bool = False, **kwargs):
        self.diagnostic_mode = bool(diagnostic_mode)
        self.allow_finalized_callback = bool(allow_finalized_callback)
        self.process_frame_calls = 0
        self.process_frame_executions = 0
        self.suppressed_process_calls = 0
        self.suppressed_write_attempts = []
        self.finalized_hands = []
        self._unconsumed_finalized = []
        self._frame_finalized = []
        self._frame_finalized_contexts = []
        self._suppress_processing = False
        self._snapshot_sequence = 0
        self.last_snapshot = None
        self.last_finalized_hand = None
        super().__init__(*args, **kwargs)

    # -- control de una sola ejecucion real por captura ---------------------
    @contextmanager
    def suppress_processing(self):
        """Evita que ``Asistente.step`` vuelva a procesar el mismo frame.

        La llamada interna a ``process_frame`` se contabiliza como suprimida,
        no como ejecucion del recorder. El frame ya fue procesado exactamente
        una vez por ``LiveParityAssistant``.
        """
        self._suppress_processing = True
        try:
            yield
        finally:
            self._suppress_processing = False

    def take_finalized_hands(self):
        out, self._unconsumed_finalized = self._unconsumed_finalized, []
        return list(out)

    # -- captura ------------------------------------------------------------
    def save_frame(self, state, img_arr, log=print):
        if self.diagnostic_mode:
            self.suppressed_write_attempts.append(
                ('frame', self.capture_dir))
            return None
        return super().save_frame(state, img_arr, log=log)

    def _save_ambiguity_evidence(self, row):
        if self.diagnostic_mode:
            self.suppressed_write_attempts.append(
                ('ambiguity', self.ambiguity_capture_dir))
            return None
        return super()._save_ambiguity_evidence(row)

    def _record_session_result(self, hand):
        if self.diagnostic_mode:
            self.suppressed_write_attempts.append(
                ('session_result', self.session_dir))
            return None
        return super()._record_session_result(hand)

    # -- ciclo de vida ------------------------------------------------------
    def finalize_hand(self, state):
        if not self.diagnostic_mode:
            return super().finalize_hand(state)

        context = None
        if self.hand is not None:
            positions = {
                player.get('_id'): player.get('pos')
                for player in self.hand.get('players') or []
                if player.get('_id') and player.get('pos')
            }
            by_street = {}
            for street in ('preflop', 'flop', 'turn', 'river'):
                try:
                    values = self._street_contributions(street)
                except Exception:
                    values = {}
                by_street[street] = {
                    pid: _as_number(values.get(position))
                    for pid, position in positions.items()
                }
            try:
                live_breakdown = self._pot_breakdown(final=False)
            except Exception:
                live_breakdown = {}
            context = {
                'hand': copy.deepcopy(self.hand),
                'contributions_by_street': by_street,
                'positions': positions,
                'pot_live_calculated': _as_number(
                    live_breakdown.get('pot_live_calculated')),
            }

        captured = []
        previous_callback = self.on_hand_finalized
        previous_saved = self.on_hand_saved
        previous_output = self.output_path
        previous_session = self.session_dir
        previous_log = getattr(self, '_last_log', None)

        # El collector recibe la mano finalizada en memoria. No se propaga a
        # callbacks externos en modo diagnostico.
        self.on_hand_finalized = captured.append
        self.on_hand_saved = None
        self.output_path = os.devnull
        self.session_dir = None
        self._last_log = (lambda *args, **kwargs: None)
        self.suppressed_write_attempts.append(
            ('hand_db', previous_output))
        try:
            super().finalize_hand(state)
        finally:
            self.output_path = previous_output
            self.session_dir = previous_session
            self.on_hand_saved = previous_saved
            self.on_hand_finalized = previous_callback
            if previous_log is None:
                self.__dict__.pop('_last_log', None)
            else:
                self._last_log = previous_log

        hand = captured[-1] if captured else None
        if hand is not None:
            self.finalized_hands.append(hand)
            self._unconsumed_finalized.append(hand)
            self._frame_finalized.append(hand)
            if context is not None:
                self._frame_finalized_contexts.append(context)
            self.last_finalized_hand = hand
            if self.allow_finalized_callback and previous_callback is not None:
                try:
                    previous_callback(hand)
                except Exception:
                    pass
        return hand

    def process_frame(self, state, img_arr, log=print, *,
                      captured_at=None, capture_source=None):
        self.process_frame_calls += 1
        if self._suppress_processing:
            self.suppressed_process_calls += 1
            return None

        raw_state = copy.deepcopy(dict(state))
        recorder_state = dict(state)
        self._frame_finalized = []
        self._frame_finalized_contexts = []
        try:
            super().process_frame(recorder_state, img_arr, log=log)
            _normalize_street_boards(self.hand)
        except Exception as exc:
            self.process_frame_executions += 1
            self._snapshot_sequence += 1
            self.last_snapshot = build_recorder_snapshot(
                self,
                raw_state=raw_state,
                recorder_state=recorder_state,
                sequence=self._snapshot_sequence,
                processed=False,
                finalized_hands=list(self._frame_finalized),
                finalized_contexts=list(self._frame_finalized_contexts),
                processing_error=str(exc),
                captured_at=captured_at,
                capture_source=capture_source,
                image_sha256=_image_sha256(img_arr),
            )
            raise
        self.process_frame_executions += 1
        self._snapshot_sequence += 1
        self.last_snapshot = build_recorder_snapshot(
            self,
            raw_state=raw_state,
            recorder_state=recorder_state,
            sequence=self._snapshot_sequence,
            processed=True,
            finalized_hands=list(self._frame_finalized),
            finalized_contexts=list(self._frame_finalized_contexts),
            captured_at=captured_at,
            capture_source=capture_source,
            image_sha256=_image_sha256(img_arr),
        )
        return None


def _raw_seat_labels(raw: Mapping[str, Any]):
    labels = {}
    unknown = []
    observed = []
    for seat in SEATS:
        key = '%s_state' % seat
        if key not in raw:
            labels[seat] = None
            unknown.append('%s_not_observed' % key)
            continue
        observed.append(key)
        value = raw.get(key)
        if not isinstance(value, str):
            labels[seat] = None
            unknown.append('%s_invalid' % key)
            continue
        text = value.strip().lower()
        if text in ACTIVE_LABELS:
            labels[seat] = 'active'
        elif text in INACTIVE_LABELS:
            labels[seat] = 'inactive'
        else:
            labels[seat] = None
            unknown.append('%s_unrecognized' % key)
    return labels, unknown, observed


def _raw_cards_value(raw: Mapping[str, Any], pid: str):
    for key in ('%s_cards' % pid, pid + '_cards'):
        if key in raw and raw.get(key) not in (None, '', []):
            return raw.get(key)
    if pid == 'hero':
        for key in ('hero_cards', 'cards_hero'):
            if key in raw and raw.get(key) not in (None, '', []):
                return raw.get(key)
    return None


def _recorded_hand(recorder) -> Optional[Mapping[str, Any]]:
    hand = getattr(recorder, 'hand', None)
    return copy.deepcopy(hand) if hand else None


def _recorded_players(hand: Optional[Mapping[str, Any]]):
    return {
        player.get('_id'): player
        for player in ((hand or {}).get('players') or [])
        if player.get('_id')
    }


def _derive_positions(raw: Mapping[str, Any]) -> dict:
    """Geometria de respaldo para snapshots no procesados/no recorder."""
    btn = raw.get('btn')
    seats = list(getattr(recorder_live, 'SCREEN_SEATS', SEATS))
    if btn not in seats:
        return {}
    manual = getattr(recorder_live, 'MANUAL_POSITIONS', {}) or {}
    seated = [seat for seat in seats
              if raw.get('%s_state' % seat) not in ('sin jugador', 'fuera')]
    active = [seat for seat in seated
              if seat not in getattr(recorder_live, 'MANUAL_INACTIVE', set())
              or seat == btn]
    positions = {btn: 'BTN'}
    index = seats.index(btn)
    left_players = []
    for offset in range(1, len(seats)):
        seat = seats[(index + offset) % len(seats)]
        if seat in active:
            left_players.append(seat)
    if len(left_players) >= 2:
        positions[left_players[0]] = 'SB'
        positions[left_players[1]] = 'BB'
    elif len(left_players) == 1:
        positions[left_players[0]] = 'BB'
    cursor = (index - 1) % len(seats)
    for position in ('CO', 'MP', 'UTG'):
        for _ in range(len(seats)):
            seat = seats[cursor]
            if seat in active and seat not in positions:
                positions[seat] = position
                cursor = (cursor - 1) % len(seats)
                break
            cursor = (cursor - 1) % len(seats)
    for pid, position in manual.items():
        if position:
            positions[pid] = position
    return positions


def _recorded_positions(recorder, hand, raw) -> dict:
    positions = {}
    for pid, player in _recorded_players(hand).items():
        if player.get('pos'):
            positions[pid] = player.get('pos')
    if positions:
        return positions
    if recorder is not None:
        try:
            return dict(recorder._assign_positions(raw))
        except Exception:
            pass
    return _derive_positions(raw)


def _recorded_board(hand: Optional[Mapping[str, Any]]) -> Tuple[str, ...]:
    if not hand:
        return ()
    com = hand.get('comunitarias') or {}
    pieces = []
    for street in ('flop', 'turn', 'river'):
        values = com.get(street) or []
        if not values:
            values = ((hand.get('streets') or {}).get(street) or {}).get(
                'board') or []
        pieces.extend(values)
    return tuple(pieces)


def _actions_by_street(hand: Optional[Mapping[str, Any]]):
    out = {}
    for street in ('preflop', 'flop', 'turn', 'river'):
        actions = ((hand or {}).get('streets') or {}).get(street) or {}
        out[street] = tuple(copy.deepcopy(actions.get('actions') or []))
    return out


def _folded_positions(recorder) -> set:
    return set(getattr(recorder, '_folded_positions', set()) or set())


def _active_seats(recorder, hand, raw, labels, unknown):
    """Asientos activos actuales sin inventar los que el OCR no vio."""
    players = _recorded_players(hand)
    folded_positions = _folded_positions(recorder) if hand else set()
    folded_pids = (set(getattr(recorder, '_inactive_players', set()) or set())
                   if hand else set())
    active = []
    ambiguities = []
    contradictions = []

    if hand:
        for seat in SEATS:
            player = players.get(seat)
            if not player or not player.get('active') or not player.get('pos'):
                continue
            if player.get('pos') in folded_positions or seat in folded_pids:
                folded_pids.add(seat)
                continue
            label = labels.get(seat)
            if label == 'active':
                active.append(seat)
            elif label == 'inactive':
                # El recorder aun no registro el fold, pero el OCR ya muestra
                # la silla fuera. No se cuenta como activa ni se inventa nada.
                ambiguities.append('raw_inactive_not_recorded_fold:%s' % seat)
                folded_pids.add(seat)
            # label None ya aparece en unknown: la puerta se abstiene.
        for seat in SEATS:
            player = players.get(seat)
            if (labels.get(seat) == 'active'
                    and (not player or not player.get('active')
                         or not player.get('pos'))):
                contradictions.append(
                    'raw_active_not_in_recorded_hand:%s' % seat)
    else:
        for seat in SEATS:
            if labels.get(seat) == 'active':
                active.append(seat)
        for pid in folded_pids:
            if pid in active:
                active.remove(pid)

    if unknown:
        contradictions.append('active_player_count_uncertain')
    return tuple(active), tuple(sorted(folded_pids, key=SEATS.index)), \
        ambiguities, contradictions


def _hu_position_view(active_seats, positions, button):
    if len(active_seats) != 2 or button not in active_seats:
        return {}
    other = active_seats[0] if active_seats[1] == button else active_seats[1]
    return {button: 'SB', other: 'BB'}


def _pot_tolerance(pot_read: Optional[float]) -> float:
    return max(0.5, 0.05 * abs(pot_read or 0.0))


def _derive_to_call(pair):
    if pair[0] is None or pair[1] is None:
        return None
    return max(0.0, float(pair[1]) - float(pair[0]))


def _normalize_street_boards(hand) -> None:
    """Completa el board acumulado en las calles turn/river del hand.

    El recorder guarda en ``streets[street]['board']`` solo la carta nueva de
    turn/river. El motor original consume ese board como si fuera el board
    completo al actualizar el rango del rival y falla con ``KeyError: 3`` en
    turn (2 cartas + 1 carta de board). Se normaliza solo la copia de mano que
    usa el motor; el estado OCR crudo no se modifica.
    """
    if not isinstance(hand, Mapping):
        return
    streets = hand.get('streets')
    if not isinstance(streets, Mapping):
        return
    flop_data = streets.get('flop') or {}
    if not isinstance(flop_data, Mapping):
        return
    flop_board = [str(card) for card in (flop_data.get('board') or [])]
    if len(flop_board) > 3:
        flop_board = flop_board[:3]
    if len(flop_board) == 3:
        turn_data = streets.get('turn') or {}
        if isinstance(turn_data, Mapping):
            turn_board = [str(card) for card in (turn_data.get('board') or [])]
            if len(turn_board) == 1:
                turn_board = flop_board + turn_board
                turn_data['board'] = turn_board
            elif len(turn_board) > 4:
                turn_board = turn_board[:4]
            if len(turn_board) == 4:
                river_data = streets.get('river') or {}
                if isinstance(river_data, Mapping):
                    river_board = [
                        str(card) for card in (river_data.get('board') or [])]
                    if len(river_board) == 1:
                        river_data['board'] = turn_board + river_board
                    elif len(river_board) > 5:
                        river_data['board'] = river_board[:5]


def _ledger_zero_contributions(hand, street, positions, active_seats,
                               folded_seats, allin_seats, contributions,
                               bets_read):
    """Contribution 0.0 declarada por el ledger de acciones del recorder.

    En postflop no hay ciegas forzadas: si un jugador activo no tiene ninguna
    accion en la calle actual, su contribucion en esa calle es 0.0. Esto no
    convierte en cero un ``hero_bet`` ausente del OCR; solo se usa cuando el
    recorder tiene mano y ledger de acciones, el jugador esta activo y no hay
    apuesta OCR observada. Si falta el ledger, hay una accion no-check o una
    contradiccion, no se aplica y el estado sigue desconocido.
    """
    zero = set()
    if not hand or street not in ('flop', 'turn', 'river'):
        return zero
    street_data = (hand.get('streets') or {}).get(street) or {}
    actions = street_data.get('actions')
    if not isinstance(actions, list):
        return zero
    for seat in active_seats:
        if seat in folded_seats or seat in allin_seats:
            continue
        if contributions.get(seat) is not None:
            continue
        if bets_read.get(seat) is not None:
            continue
        pos = positions.get(seat)
        if not pos:
            continue
        player_actions = [
            action for action in actions
            if isinstance(action, Mapping) and action.get('pos') == pos
        ]
        if any(action.get('action') not in ('x', 'check')
               for action in player_actions):
            continue
        zero.add(seat)
    return zero


def build_recorder_snapshot(recorder, *, raw_state: Mapping[str, Any],
                            recorder_state: Optional[Mapping[str, Any]] = None,
                            sequence: int = 0, processed: bool = True,
                            finalized_hands=(),
                            finalized_contexts=(),
                            processing_error: Optional[str] = None,
                            captured_at: Optional[str] = None,
                            capture_source: Optional[str] = None,
                            image_sha256: Optional[str] = None):
    """Congela la lectura original y el estado reconstruido por el recorder."""
    raw = copy.deepcopy(dict(raw_state))
    processed_state = (copy.deepcopy(dict(recorder_state))
                       if recorder_state is not None else None)
    hand = _recorded_hand(recorder) if processed else None
    finalized_records = tuple(copy.deepcopy(finalized_hands))
    finalized_context = (copy.deepcopy(finalized_contexts[-1])
                         if finalized_contexts else None)
    detail_hand = (hand or (finalized_context or {}).get('hand'))
    recorded_hand_present = detail_hand is not None
    players = _recorded_players(detail_hand)
    labels, unknown_states, observed_state_fields = _raw_seat_labels(raw)
    active_seats, folded_seats, active_ambiguities, active_contradictions = \
        _active_seats(recorder, detail_hand, raw, labels, unknown_states)
    inactive_seats = tuple(
        seat for seat in SEATS if labels.get(seat) == 'inactive'
        and seat not in active_seats)
    positions = (_recorded_positions(recorder, detail_hand, raw)
                 if processed else {})
    contradictions = list(active_contradictions)
    ambiguities = list(active_ambiguities)
    observed = list(observed_state_fields)
    unknown = list(unknown_states)
    if 'btn' in raw:
        observed.append('btn')
        if raw.get('btn') is None:
            unknown.append('button_read_not_observed')
    else:
        unknown.append('button_read_not_observed')
    button_read = raw.get('btn')
    button_recorded = ((detail_hand or {}).get('btn_player')
                       if detail_hand else None)
    button = button_recorded or button_read
    if button_read not in SEATS:
        if button_read is not None:
            contradictions.append('button_invalid:%s' % button_read)
        button_read = None
    if button_recorded not in SEATS:
        if button_recorded is not None:
            contradictions.append(
                'button_recorded_invalid:%s' % button_recorded)
        button_recorded = None
    if button_recorded and button_read and button_recorded != button_read:
        contradictions.append(
            'button_ocr_vs_recorded:ocr=%s,recorder=%s'
            % (button_read, button_recorded))
    if button not in SEATS:
        button = None

    # -- cartas -------------------------------------------------------------
    cards_read = {}
    cards_recorded = {}
    for seat in SEATS:
        read_values = _raw_cards_value(raw, seat)
        read_cards = _cards_safe(read_values, '%s_cards' % seat,
                                 contradictions)
        recorded_cards = ()
        player = players.get(seat)
        if player and player.get('cards'):
            recorded_cards = _cards_safe(
                player.get('cards'), '%s_recorded_cards' % seat,
                contradictions)
        cards_read[seat] = read_cards
        cards_recorded[seat] = recorded_cards
        if read_values is not None:
            observed.append('%s_cards' % seat)
        elif seat == 'hero':
            unknown.append('hero_cards_not_observed')
        if recorded_cards:
            observed.append('%s_cards_recorded' % seat)

    hero_read = cards_read.get('hero', ())
    hero_recorded = cards_recorded.get('hero', ())
    if hero_read and hero_recorded and not _cards_equal(
            hero_read, hero_recorded):
        contradictions.append(
            'hero_cards_ocr_vs_recorded:ocr=%s,recorder=%s'
            % (_fmt_cards(hero_read), _fmt_cards(hero_recorded)))
        hero_cards_for_view = ()
    else:
        hero_cards_for_view = hero_recorded or hero_read

    board_key = 'community' if 'community' in raw else (
        'board' if 'board' in raw else None)
    board_observed = (board_key is not None
                      and raw.get(board_key) is not None)
    board_read = ()
    if board_key is not None:
        observed.append(board_key)
        board_read = _cards_safe(raw.get(board_key), 'board', contradictions)
    if not board_observed:
        unknown.append('board_not_observed')
    board_recorded = _cards_safe(
        _recorded_board(detail_hand), 'recorded_board', contradictions) \
        if detail_hand else ()

    if board_recorded:
        observed.append('board_recorded')
    if board_read and board_recorded and board_read != board_recorded:
        contradictions.append(
            'board_ocr_vs_recorded:ocr=%s,recorder=%s'
            % (_fmt_cards(board_read), _fmt_cards(board_recorded)))
        board_for_view = ()
    elif board_recorded and board_key is not None and not board_read:
        contradictions.append(
            'board_missing_in_ocr_but_recorded:%s'
            % _fmt_cards(board_recorded))
        board_for_view = ()
    else:
        board_for_view = board_recorded or board_read

    if len(board_for_view) not in (0, 3, 4, 5):
        contradictions.append('invalid_board_count:%d' % len(board_for_view))

    # -- calle --------------------------------------------------------------
    hand_street = (detail_hand or {}).get('current_street')
    if hand_street in ('preflop', 'flop', 'turn', 'river'):
        street = hand_street
    else:
        street = _street(board_for_view)
    if detail_hand and (hand_street in ('preflop', 'flop', 'turn', 'river')):
        expected_counts = {'preflop': 0, 'flop': 3, 'turn': 4, 'river': 5}
        expected = expected_counts[hand_street]
        if expected and len(board_for_view) != expected:
            contradictions.append(
                'street_board_mismatch:street=%s,board=%d'
                % (hand_street, len(board_for_view)))

    # -- economia -----------------------------------------------------------
    pot_read, pot_observed = _read_number(raw, 'pot')
    pot_source_key = 'pot'
    if pot_read is None and raw.get('pot') is None and 'pot_wide' in raw:
        wide_value, wide_observed = _read_number(raw, 'pot_wide')
        if wide_value is not None:
            pot_read = wide_value
            pot_observed = wide_observed
            pot_source_key = 'pot_wide'
    if pot_observed:
        observed.append(pot_source_key)
    if (not pot_observed or (raw.get('pot') is None
                             and raw.get('pot_wide') is None)):
        unknown.append('pot_not_observed')
    elif pot_read is None:
        invalid_key = 'pot' if raw.get('pot') is not None else 'pot_wide'
        contradictions.append('invalid_numeric:%s' % invalid_key)

    pot_breakdown = {}
    pot_live = None
    pot_final = None
    if hand:
        try:
            pot_breakdown = recorder._pot_breakdown(final=False)
            pot_live = _as_number(pot_breakdown.get('pot_live_calculated'))
            pot_final = _as_number(pot_breakdown.get('pot_calculated'))
            observed.append('pot_live_calculated')
        except Exception as exc:
            ambiguities.append('pot_breakdown_error:%s' % exc)
    elif finalized_records:
        audit = (finalized_records[-1].get('recorder_audit') or {})
        pot_breakdown = copy.deepcopy(audit)
        pot_live = _as_number(
            (finalized_context or {}).get('pot_live_calculated'))
        pot_final = _as_number(audit.get('pot_calculated'))
        if pot_final is not None:
            observed.append('pot_final_calculated')

    pot_for_view = pot_read
    if pot_read is None and pot_live is not None:
        pot_for_view = pot_live

    # La comparacion pot_read/pot_live se difiere hasta conocer los aportes
    # all-in inferidos: el visor de la mesa incluye la apuesta viva y el
    # recorder puede no haberla incorporado al ledger en ese frame.

    stacks_read = {}
    observed_fields = list(observed)
    for seat in SEATS:
        key = '%s_stake' % seat
        value, was_observed = _read_number(raw, key)
        stacks_read[seat] = value
        if was_observed:
            observed_fields.append('%s_stake' % seat)
            if raw.get(key) is not None and value is None:
                contradictions.append('invalid_numeric:%s' % key)
        else:
            unknown.append('%s_stake_not_observed' % seat)

    bets_read = {}
    for seat in SEATS:
        key = '%s_bet' % seat
        value, was_observed = _read_number(raw, key)
        bets_read[seat] = value
        if was_observed:
            observed_fields.append('%s_bet' % seat)
            if raw.get(key) is not None and value is None:
                contradictions.append('invalid_numeric:%s' % key)
        else:
            unknown.append('%s_bet_not_observed' % seat)

    if hand:
        try:
            raw_contrib = recorder._street_contributions(street)
        except Exception:
            raw_contrib = {}
        contributions = {}
        for seat in SEATS:
            pos = positions.get(seat)
            value = raw_contrib.get(pos) if pos else None
            contributions[seat] = _as_number(value)
        if contributions:
            observed_fields.append('recorder_contributions')
    elif finalized_context:
        contributions = (finalized_context.get('contributions_by_street') or {}).get(
            street, {})
    else:
        contributions = {}

    contributions_by_street = {}
    if hand:
        for street_name in ('preflop', 'flop', 'turn', 'river'):
            try:
                street_values = recorder._street_contributions(street_name)
            except Exception:
                street_values = {}
            contributions_by_street[street_name] = {
                seat: _as_number(street_values.get(positions.get(seat)))
                if positions.get(seat) else None
                for seat in SEATS
            }
    elif finalized_context:
        by_pid = finalized_context.get('contributions_by_street') or {}
        contributions_by_street = {
            street_name: {
                seat: _as_number((by_pid.get(street_name) or {}).get(seat))
                for seat in SEATS
            }
            for street_name in ('preflop', 'flop', 'turn', 'river')
        }
    else:
        contributions_by_street = {
            street_name: {seat: None for seat in SEATS}
            for street_name in ('preflop', 'flop', 'turn', 'river')
        }

    # El badge "All-in" tapa el stack y el OCR no puede leer un cero: el
    # stack queda ``None``. Solo se infiere all-in si, además de una apuesta
    # positiva, el ledger confirma que el aporte total iguala el stack inicial.
    # Se conserva el ``None`` bruto y se declara la inferencia.
    recorder_allin = set(getattr(recorder, '_allin_players', set()) or set())

    def ledger_confirms_allin(seat):
        """Confirma que el stack inicial ya se agoto con los aportes."""
        player_pos = positions.get(seat)
        initial = next(
            (player.get('stack') for player in (hand or {}).get('players') or ()
             if player.get('pos') == player_pos), None)
        if initial is None:
            return False
        total = 0.0
        for street_name in ('preflop', 'flop', 'turn', 'river'):
            value = (contributions_by_street.get(street_name) or {}).get(seat)
            if street_name == street:
                value = max(value or 0.0, bets_read.get(seat) or 0.0)
            total += float(value or 0.0)
        return abs(float(initial) - total) <= _CARD_TOLERANCE

    inferred_allin = set()
    if processed and recorded_hand_present and hand:
        for seat in active_seats:
            if seat in folded_seats or seat in recorder_allin:
                continue
            bet = bets_read.get(seat)
            if (stacks_read.get(seat) is None and bet is not None
                    and bet > 0.0 and ledger_confirms_allin(seat)):
                inferred_allin.add(seat)
                ambiguities.append(
                    'allin_inferred_from_unreadable_stack:%s' % seat)
                observed_fields.append('allin_inferred:%s' % seat)

    inferred_allin_contrib = {}
    for seat in inferred_allin:
        if contributions.get(seat) is None and bets_read.get(seat) is not None:
            amount = float(bets_read[seat])
            contributions[seat] = amount
            if street in contributions_by_street:
                contributions_by_street[street][seat] = amount
            inferred_allin_contrib[seat] = amount
            observed_fields.append(
                'allin_contribution_from_ocr_bet:%s' % seat)

    allin_set = set()
    if processed and recorded_hand_present:
        allin_set.update(
            seat for seat in SEATS
            if seat in recorder_allin and seat in active_seats)
    allin_set.update(inferred_allin)
    allin_seats = tuple(seat for seat in SEATS if seat in allin_set)
    if allin_seats:
        observed_fields.append('allin_seats')

    effective_stacks = dict(stacks_read)
    for seat in allin_seats:
        if effective_stacks.get(seat) is None:
            effective_stacks[seat] = 0.0
            observed_fields.append('allin_stack_zero:%s' % seat)

    # El visor de la mesa incluye la apuesta viva de la calle. Si el ledger
    # aun no la incorporo, el pot leido solo cuadra al sumar el aporte all-in
    # observado. Se reconcilia de forma explicita, nunca en silencio.
    if pot_read is not None and pot_live is not None:
        difference = abs(pot_read - pot_live)
        tolerance = _pot_tolerance(pot_read)
        if difference <= tolerance:
            pot_for_view = pot_read
        else:
            inferred_total = sum(inferred_allin_contrib.values())
            reconciled = pot_live + inferred_total
            if (inferred_total > 0.0
                    and abs(pot_read - reconciled) <= tolerance):
                pot_for_view = pot_read
                ambiguities.append(
                    'pot_reconciled_inferred_allin:read=%s,recorded=%s,'
                    'inferred=%s'
                    % (_fmt_number(pot_read), _fmt_number(pot_live),
                       _fmt_number(inferred_total)))
                observed_fields.append('pot_reconciled_inferred_allin')
            else:
                contradictions.append(
                    'pot_read_vs_calculated:read=%s,recorded=%s,diff=%.2f'
                    % (_fmt_number(pot_read), _fmt_number(pot_live),
                       difference))
                pot_for_view = None

    # Un jugador activo sin accion postflop tiene contribucion 0.0 en el
    # ledger del recorder. Se declara con procedencia propia; no se deduce de
    # un campo OCR ausente.
    ledger_zero = _ledger_zero_contributions(
        hand, street, positions, active_seats, folded_seats, allin_seats,
        contributions, bets_read)
    for seat in ledger_zero:
        contributions[seat] = 0.0
        if street in contributions_by_street:
            contributions_by_street[street][seat] = 0.0
    if ledger_zero:
        observed_fields.append('recorder_action_ledger_zero')

    # Un asiento all-in no puede aportar en una calle posterior. Su ausencia
    # en el ledger no es un campo desconocido: el aporte de esa calle es 0.0.
    for seat in allin_seats:
        if contributions.get(seat) is None and bets_read.get(seat) is None:
            contributions[seat] = 0.0
            if street in contributions_by_street:
                contributions_by_street[street][seat] = 0.0
            observed_fields.append('allin_contribution_zero:%s' % seat)

    # -- to_call ------------------------------------------------------------
    explicit_to_call, explicit_observed = _read_number(raw, 'to_call')
    if explicit_observed:
        observed_fields.append('to_call')
        if raw.get('to_call') is not None and explicit_to_call is None:
            contradictions.append('invalid_numeric:to_call')
    villain = next((seat for seat in active_seats if seat != 'hero'), None)
    hero_contrib = contributions.get('hero') if recorded_hand_present else None
    villain_contrib = (contributions.get(villain)
                       if recorded_hand_present and villain else None)

    raw_hero_bet = bets_read.get('hero')
    raw_villain_bet = bets_read.get(villain) if villain else None

    # La apuesta OCR es por calle. Si el recorder dispone de una contribucion
    # independiente para esa misma calle, no se escoge una silenciosamente.
    for seat, raw_bet in (('hero', raw_hero_bet),
                          (villain, raw_villain_bet)):
        if not seat:
            continue
        recorded_bet = (contributions.get(seat)
                        if recorded_hand_present else None)
        if (raw_bet is not None and recorded_bet is not None
                and abs(raw_bet - recorded_bet) > _CARD_TOLERANCE):
            contradictions.append(
                'bet_vs_contribution:%s:ocr=%s,recorded=%s'
                % (seat, _fmt_number(raw_bet), _fmt_number(recorded_bet)))

    hero_bet = raw_hero_bet
    villain_bet = raw_villain_bet
    hero_bet_source = 'ocr_bet' if hero_bet is not None else 'unknown'
    villain_bet_source = ('ocr_bet' if villain_bet is not None
                          else 'unknown')
    if hero_bet is None and hero_contrib is not None:
        hero_bet = hero_contrib
        hero_bet_source = ('recorder_action_ledger_zero'
                           if 'hero' in ledger_zero
                           else 'recorder_contribution')
    if villain_bet is None and villain_contrib is not None:
        villain_bet = villain_contrib
        villain_bet_source = ('recorder_action_ledger_zero'
                              if villain in ledger_zero
                              else 'recorder_contribution')

    contribution_to_call = _derive_to_call((hero_contrib, villain_contrib))
    bets_to_call = _derive_to_call((hero_bet, villain_bet))

    to_call = None
    to_call_source = 'unknown'
    if explicit_to_call is not None:
        to_call = explicit_to_call
        to_call_source = 'explicit'
    elif contribution_to_call is not None:
        to_call = contribution_to_call
        if inferred_allin_contrib:
            to_call_source = 'allin_bet_reconciled'
        else:
            to_call_source = ('recorder_action_ledger'
                              if ledger_zero else 'recorder_contributions')
    elif bets_to_call is not None:
        to_call = bets_to_call
        to_call_source = 'bets'

    if explicit_to_call is not None:
        derived = (contribution_to_call if contribution_to_call is not None
                   else bets_to_call)
        if derived is not None and abs(explicit_to_call - derived) > \
                _CARD_TOLERANCE:
            contradictions.append(
                'to_call_explicit_vs_derived:explicit=%s,derived=%s'
                % (_fmt_number(explicit_to_call), _fmt_number(derived)))
            to_call = None
            to_call_source = 'contradiction'
    elif contribution_to_call is not None and bets_to_call is not None:
        if abs(contribution_to_call - bets_to_call) > _CARD_TOLERANCE:
            contradictions.append(
                'to_call_bets_vs_contributions:bets=%s,recorded=%s'
                % (_fmt_number(bets_to_call),
                   _fmt_number(contribution_to_call)))
            to_call = None
            to_call_source = 'contradiction'
    if to_call is None and to_call_source == 'unknown':
        unknown.append('to_call_not_observed')

    # -- posiciones HU y contradicciones de boton ---------------------------
    hu_positions = _hu_position_view(active_seats, positions, button)
    if button is not None and button not in active_seats:
        contradictions.append('button_not_in_active:%s' % button)
    if button is None:
        unknown.append('button_not_observed')
    if len(active_seats) == 2 and not hu_positions:
        contradictions.append('hu_positions_not_observable')

    # -- acciones y ambiguedades del recorder -------------------------------
    actions = _actions_by_street(detail_hand)
    recorder_ambiguities = tuple(
        copy.deepcopy(getattr(recorder, '_hand_ambiguities', []) or [])
    ) if processed and recorded_hand_present else ()
    if recorder_ambiguities:
        observed_fields.append('recorder_ambiguities')
        ambiguities.extend(
            str(item.get('code') or 'ambiguity')
            for item in recorder_ambiguities
            if isinstance(item, Mapping))

    if processing_error:
        contradictions.append('recorder_error:%s' % processing_error)

    # -- deduplicacion de cartas -------------------------------------------
    ocr_cards = tuple(
        card for seat in SEATS for card in cards_read.get(seat, ())) \
        + tuple(board_read)
    recorded_cards_all = tuple(
        card for seat in SEATS for card in cards_recorded.get(seat, ())) \
        + tuple(board_recorded)
    for source_name, card_pool in (
            ('ocr', ocr_cards), ('recorder', recorded_cards_all)):
        duplicates = _duplicates(card_pool)
        if duplicates:
            contradictions.append(
                'duplicate_cards_%s:%s' %
                (source_name, ','.join(duplicates)))

    # -- vista de decision HU ----------------------------------------------
    provenance = {
        'cards': ('recorded+ocr' if hero_read and hero_recorded else
                  'recorded' if hero_recorded else
                  'ocr' if hero_read else 'unknown'),
        'board': ('recorded+ocr' if board_read and board_recorded else
                  'recorded' if board_recorded else
                  'ocr' if board_read else
                  'observed_empty' if board_observed else 'unknown'),
        'pot': ('ocr+recorded' if pot_read is not None and pot_live is not None
                else 'ocr' if pot_read is not None else
                'recorded' if pot_live is not None else 'unknown'),
        'pot_read_source': pot_source_key if pot_read is not None else 'unknown',
        'to_call': to_call_source,
        'positions': ('recorded_hand' if recorded_hand_present else
                      'derived_from_button' if positions else 'unknown'),
        'button': ('recorded+ocr' if button_read and button_recorded else
                   'ocr' if button_read else
                   'recorded' if button_recorded else 'unknown'),
        'stacks': ('ocr+allin_inferred' if inferred_allin else
                   'ocr+recorder_allin' if allin_seats else 'ocr'),
        'hero_bet': hero_bet_source,
        'villain_bet': villain_bet_source,
        'street': 'recorded_hand' if hand_street in (
            'preflop', 'flop', 'turn', 'river') else 'derived_from_board',
        'active_seats': 'recorded_hand' if recorded_hand_present else 'ocr',
    }
    if hero_cards_for_view and board_for_view:
        observed_fields.append('cards_visible')
    if pot_for_view is not None:
        observed_fields.append('pot_usable')
    if to_call is not None:
        observed_fields.append('to_call_usable')

    decision_view = DecisionStateView(
        hero_seat='hero',
        villain_seat=villain,
        active_seats=active_seats,
        recorder_positions=MappingProxyType(dict(positions)),
        hu_positions=MappingProxyType(dict(hu_positions)),
        button_seat=button,
        street=street,
        hero_cards=tuple(hero_cards_for_view),
        board=tuple(board_for_view),
        pot=pot_for_view,
        pot_read=pot_read,
        pot_recorded=pot_live,
        to_call=to_call,
        hero_stack=effective_stacks.get('hero'),
        villain_stack=effective_stacks.get(villain) if villain else None,
        hero_bet=hero_bet,
        villain_bet=villain_bet,
        hero_contribution=hero_contrib,
        villain_contribution=villain_contrib,
        actions=_freeze(tuple(
            {**copy.deepcopy(action), 'street': street_name}
            for street_name, street_actions in actions.items()
            for action in street_actions
        )),
        contradictions=tuple(dict.fromkeys(contradictions)),
        ambiguities=tuple(dict.fromkeys(ambiguities)),
        provenance=MappingProxyType(provenance),
        observed_fields=tuple(dict.fromkeys(observed_fields)),
        unknown_fields=tuple(dict.fromkeys(unknown)),
        hand_id=(detail_hand or {}).get('hand_id'),
        board_observed=board_observed,
    )

    fingerprint_payload = {
        'sequence': sequence,
        'processed': processed,
        'raw_state': raw,
        'captured_at': captured_at,
        'capture_source': capture_source,
        'image_sha256': image_sha256,
        'hand': hand,
        'finalized_hands': finalized_records,
        'finalized_context': finalized_context,
        'positions': positions,
        'active_seats': active_seats,
        'pot_read': pot_read,
        'pot_live_calculated': pot_live,
        'to_call': to_call,
        'actions': actions,
        'contributions_by_street': contributions_by_street,
        'contradictions': contradictions,
    }
    fingerprint = hashlib.sha256(json.dumps(
        _json_safe(fingerprint_payload), sort_keys=True,
        ensure_ascii=False).encode('utf-8')).hexdigest()

    return RecorderSnapshot(
        sequence=sequence,
        fingerprint=fingerprint,
        processed=processed,
        captured_at=captured_at,
        capture_source=capture_source,
        image_sha256=image_sha256,
        raw_state=_freeze(raw),
        recorder_state=_freeze(processed_state)
        if processed_state is not None else None,
        hand=_freeze(hand) if hand is not None else None,
        finalized_hands=tuple(_freeze(h) for h in finalized_records),
        positions=MappingProxyType(dict(positions)),
        button_read=button_read,
        button_recorded=button_recorded,
        active_seats=active_seats,
        folded_seats=folded_seats,
        inactive_seats=inactive_seats,
        allin_seats=allin_seats,
        cards_read=MappingProxyType(dict(cards_read)),
        cards_recorded=MappingProxyType(dict(cards_recorded)),
        stacks_read=MappingProxyType(dict(stacks_read)),
        bets_read=MappingProxyType(dict(bets_read)),
        board_read=board_read,
        board_recorded=board_recorded,
        street=street,
        pot_read=pot_read,
        pot_read_source=pot_source_key if pot_read is not None else None,
        pot_live_calculated=pot_live,
        pot_final_calculated=pot_final,
        pot_breakdown=_freeze(copy.deepcopy(pot_breakdown)),
        contributions=MappingProxyType(dict(contributions)),
        contributions_by_street=_freeze(contributions_by_street),
        to_call=to_call,
        to_call_source=to_call_source,
        actions_by_street=_freeze({
            street_name: tuple(copy.deepcopy(actions))
            for street_name, actions in actions.items()
        }),
        ambiguities=tuple(_freeze(copy.deepcopy(a))
                          for a in recorder_ambiguities),
        contradictions=tuple(dict.fromkeys(contradictions)),
        observed_fields=tuple(dict.fromkeys(observed_fields)),
        unknown_fields=tuple(dict.fromkeys(unknown)),
        decision_view=decision_view,
    )


def build_unprocessed_snapshot(recorder, state: Mapping[str, Any], *,
                               sequence: int = 0,
                               captured_at: Optional[str] = None,
                               capture_source: Optional[str] = None,
                               image: Any = None):
    """Snapshot de diagnostico para frames rechazados antes del recorder.

    No ejecuta ``process_frame`` ni modifica el recorder. Conserva lo que el
    OCR mostro para que la GUI no lo presente como un estado vacio.
    """
    return build_recorder_snapshot(
        recorder, raw_state=state, recorder_state=None, sequence=sequence,
        processed=False, finalized_hands=(), captured_at=captured_at,
        capture_source=capture_source, image_sha256=_image_sha256(image))


def interpret_recorder_snapshot(snapshot: RecorderSnapshot, *,
                                hero_seat: str = 'hero',
                                require_processed: bool = True,
                                hu_positions_override: Optional[Mapping[str, str]] = None,
                                ignored_contradictions: Iterable[str] = ()) -> HUState:
    """Convierte el snapshot del recorder en el contrato HU normalizado.

    ``require_processed=False`` solo se usa para mostrar el estado observado
    antes de un rechazo temporal. La puerta operativa siempre exige un
    snapshot procesado por el recorder.
    """
    if hero_seat not in SEATS:
        raise StateInterpretationError('hero_seat invalido')
    view = snapshot.decision_view

    active_seats = tuple(view.active_seats)
    villain = view.villain_seat
    if villain is None:
        villain = next((seat for seat in active_seats if seat != hero_seat),
                       None)

    reasons = list(view.contradictions)
    reasons.extend(view.ambiguities)
    reasons.extend(view.unknown_fields)
    if require_processed and not snapshot.processed:
        reasons.append('frame_not_processed')
    if not view.board_observed:
        reasons.append('board_not_observed')

    contradictions = tuple(view.contradictions)
    blocking_contradictions = tuple(
        item for item in contradictions
        if not any(item.startswith(prefix)
                   for prefix in ignored_contradictions))
    if hu_positions_override is None:
        positions_for_state = view.hu_positions
    else:
        positions_for_state = MappingProxyType(dict(hu_positions_override))
    status = 'ready'
    reason = None

    def finish(status_value, reason_value, *, cards=None, board=None,
               pot=None, to_call=None, positions=None):
        hero_position = villain_position = None
        if positions:
            hero_position = positions.get(hero_seat)
            villain_position = positions.get(villain) if villain else None
            if hero_position not in ('SB', 'BB', 'BTN'):
                hero_position = None
            if villain_position not in ('SB', 'BB', 'BTN'):
                villain_position = None
        return HUState(
            status=status_value,
            reason=reason_value,
            hero_seat=hero_seat,
            villain_seat=villain,
            hero_position=hero_position,
            villain_position=villain_position,
            active_seats=active_seats,
            street=view.street,
            hero_cards=tuple(view.hero_cards if cards is None else cards),
            board=tuple(view.board if board is None else board),
            pot=view.pot if pot is None else pot,
            to_call=view.to_call if to_call is None else to_call,
            hero_stack=view.hero_stack,
            villain_stack=view.villain_stack,
            hero_bet=view.hero_bet,
            villain_bet=view.villain_bet,
            button_seat=view.button_seat,
            uncertainty_reasons=tuple(dict.fromkeys(reasons)),
            observed_fields=view.observed_fields,
            raw_state=_plain(snapshot.raw_state),
            contradictions=contradictions,
            provenance=dict(view.provenance),
            actions=view.actions,
            hand_id=view.hand_id,
            recorder_snapshot_sha256=snapshot.fingerprint,
            interpretation_source='recorder_snapshot',
        )

    if require_processed and not snapshot.processed:
        return finish('unresolved', 'frame_not_processed')
    if hero_seat not in active_seats:
        return finish('no_decision', 'hero_not_active')
    if len(active_seats) != 2:
        reasons.append('not_heads_up:%d_active' % len(active_seats))
        return finish('no_decision', 'not_heads_up')
    if blocking_contradictions:
        first = blocking_contradictions[0]
        if first.startswith('active_player_count_uncertain'):
            return finish('unresolved', 'active_player_count_uncertain')
        return finish('unresolved', 'contradiction:%s' % first.split(':', 1)[0])

    if not view.hero_cards:
        reasons.append('hero_cards_not_observed')
        return finish('unresolved', 'hero_cards_not_observed')
    if len(view.hero_cards) != 2:
        reasons.append('hero_cards_not_observed')
        return finish('unresolved', 'hero_cards_not_observed')
    if not view.board_observed:
        return finish('unresolved', 'board_not_observed')
    if not positions_for_state:
        reasons.append('position_not_observed')
        return finish('unresolved', 'position_not_observed')
    if view.pot is None:
        reasons.append('economic_state_incomplete')
        return finish('unresolved', 'economic_state_incomplete')
    if view.hero_stack is None or view.villain_stack is None:
        reasons.append('economic_state_incomplete')
        return finish('unresolved', 'economic_state_incomplete')
    if view.to_call is None:
        reasons.append('to_call_not_observed')
        return finish('unresolved', 'to_call_not_observed')

    return finish('ready', None, positions=positions_for_state)


__all__ = [
    'DecisionStateView',
    'RecorderSnapshot',
    'SnapshotLiveRecorder',
    'build_recorder_snapshot',
    'build_unprocessed_snapshot',
    'interpret_recorder_snapshot',
]
