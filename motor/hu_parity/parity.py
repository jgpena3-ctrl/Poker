"""Adaptador de paridad HU sobre el motor original ``asistente_live``.

Este modulo es la Fase 10.1. No modifica ``motor/asistente_live.py`` ni el
recorder: los instancia y los usa. La puerta HU se aplica *antes* de llamar al
motor live. Las predicciones se persisten en el registro prospectivo aislado;
el resultado posterior se registra como evento separado.

Modos de posicion:

- ``live_default``: replica exactamente las posiciones que asigna el recorder
  original (en HU suele dar BTN/BB). Es paridad con el defecto live, no una
  correccion estrategica.
- ``hu_sb_bb``: fuerza SB/BB en la mesa HU mediante ``MANUAL_POSITIONS``. Usa
  el mismo motor, pero corrige la posicion HU de forma explicita. La diferencia
  se declara en la prediccion.

Nada de esto autoriza un piloto real ni escribe en ``data/`` por defecto.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from types import MethodType
from typing import Any, Callable, Mapping, Optional, Tuple

from ..hu_prospective import (
    HUOutcome,
    HUPrediction,
    ProspectiveHURegistry,
    VerificationResult,
)
from ..hu_experimental.capture import CapturedFrame, HUCaptureAdapter
from ..hu_experimental.config import ExperimentalConfig
from ..hu_experimental.state import (
    HUState,
    StateInterpretationError,
    interpret_state,
)


PARITY_VERSION = 'hu_experimental_live_parity_v1'


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_capture_time(value: Any) -> Optional[datetime]:
    try:
        captured_at = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=timezone.utc)
        return captured_at.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, default=str))
    except (TypeError, ValueError):
        return str(value)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> Optional[str]:
    try:
        if path.is_file():
            return _sha256_bytes(path.read_bytes())
    except OSError:
        return None
    return None


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


class SnapshotCollector:
    """Recolector en memoria compatible con ``DecisionLog``.

    ``asistente_live`` llama a ``record_decision`` antes de invocar ``on_reco``.
    Recolectar ese snapshot evita escribir ``data/decisions.jsonl`` y conserva
    exactamente lo que el motor sabia en el momento de decidir.
    """

    def __init__(self, secondary: Any = None):
        self.secondary = secondary
        self.clear()

    def clear(self) -> None:
        self.snapshot: Optional[dict] = None
        self.decision_id: Optional[str] = None
        self.hand_id: Optional[str] = None
        self.street: Optional[str] = None
        self.hero_position: Optional[str] = None
        self.actions_seen_count: Optional[int] = None

    def record_decision(self, snapshot, *, hand_id=None, street=None,
                        hero_position=None, actions_seen_count=None):
        self.snapshot = _json_safe(dict(snapshot))
        self.hand_id = hand_id
        self.street = street
        self.hero_position = hero_position
        self.actions_seen_count = actions_seen_count
        if self.secondary is not None:
            self.decision_id = self.secondary.record_decision(
                self.snapshot, hand_id=hand_id, street=street,
                hero_position=hero_position,
                actions_seen_count=actions_seen_count)
        else:
            self.decision_id = uuid.uuid4().hex
        return self.decision_id

    def resolve_hand(self, hand):
        if self.secondary is not None:
            return self.secondary.resolve_hand(hand)
        return 0

    def discard_hand(self, hand_id, reason='canceled'):
        if self.secondary is not None:
            return self.secondary.discard_hand(hand_id, reason=reason)
        return 0


@dataclass(frozen=True)
class LiveActionView:
    action: str
    amount: float
    ev: Optional[float]
    status: str
    reason: Optional[str] = None


@dataclass(frozen=True)
class LiveEVView:
    actions: Tuple[LiveActionView, ...]
    best_action: Optional[str]
    best_ev: Optional[float]
    status: str
    action_values_kind: str

    def as_dict(self) -> dict:
        return {
            'status': self.status,
            'best_action': self.best_action,
            'best_ev': self.best_ev,
            'action_values_kind': self.action_values_kind,
            'actions': [
                {'action': a.action, 'amount': a.amount, 'ev': a.ev,
                 'status': a.status, 'reason': a.reason}
                for a in self.actions
            ],
        }


@dataclass(frozen=True)
class ParityAnalysis:
    state: HUState
    snapshot: Mapping[str, Any]
    prediction: Optional[HUPrediction]
    decision_key: Optional[str]
    live_recommendation: Optional[str]
    canonical_status: str
    canonical_reason: Optional[str]
    sequence_status: str
    coverage_state: str
    range_kind: str
    range_source: str
    range_provenance: Mapping[str, Any]
    equity: Optional[float]
    equity_method: Optional[str]
    equity_uncertainty: Optional[str]
    ev_result: Optional[LiveEVView]
    selected_action: Optional[str]
    provisional_selected_action: Optional[str]
    legal_actions: Tuple[str, ...]
    uncertainty_reasons: Tuple[str, ...]
    assumptions: Tuple[str, ...]
    warnings: Tuple[str, ...]
    capture_source: str
    captured_at: str
    elapsed_ms: Mapping[str, float] = field(default_factory=dict)

    @property
    def has_decision(self) -> bool:
        return self.prediction is not None

    def as_dict(self) -> dict:
        return {
            'parity_version': PARITY_VERSION,
            'state': self.state.as_dict(),
            'snapshot': dict(self.snapshot),
            'prediction': (self.prediction.to_payload()
                           if self.prediction is not None else None),
            'decision_key': self.decision_key,
            'live_recommendation': self.live_recommendation,
            'canonical_status': self.canonical_status,
            'canonical_reason': self.canonical_reason,
            'sequence_status': self.sequence_status,
            'coverage_state': self.coverage_state,
            'range_kind': self.range_kind,
            'range_source': self.range_source,
            'range_provenance': dict(self.range_provenance),
            'equity': self.equity,
            'equity_method': self.equity_method,
            'equity_uncertainty': self.equity_uncertainty,
            'ev': self.ev_result.as_dict() if self.ev_result else None,
            'selected_action': self.selected_action,
            'provisional_selected_action': self.provisional_selected_action,
            'legal_actions': list(self.legal_actions),
            'uncertainty_reasons': list(self.uncertainty_reasons),
            'assumptions': list(self.assumptions),
            'warnings': list(self.warnings),
            'capture_source': self.capture_source,
            'captured_at': self.captured_at,
            'elapsed_ms': dict(self.elapsed_ms),
        }


@dataclass(frozen=True)
class ParityRegistration:
    analysis: ParityAnalysis
    prediction: HUPrediction
    event: Mapping[str, Any]
    registry_path: str

    @property
    def prediction_id(self) -> str:
        return self.prediction.prediction_id


class LiveParityAssistant:
    """Asistente experimental HU que usa el motor y el recorder originales."""

    def __init__(self, config: Optional[ExperimentalConfig] = None, *,
                 capture: Optional[HUCaptureAdapter] = None,
                 registry: Optional[ProspectiveHURegistry] = None,
                 models: Any = None,
                 clock: Optional[Callable[[], str]] = None,
                 logger: Optional[Callable[..., Any]] = None,
                 capture_guard: Any = None):
        self.config = config or ExperimentalConfig.default()
        self.capture_adapter = capture or HUCaptureAdapter(clock=clock)
        self.registry = registry or ProspectiveHURegistry(
            self.config.registry_path)
        self.models = models
        self._clock = clock or _now_iso
        self._logger = logger or (lambda *args, **kwargs: None)
        self.capture_guard = capture_guard
        self._engine = None
        self._lock = threading.RLock()
        self._collector = SnapshotCollector()
        self._last_frame: Optional[CapturedFrame] = None
        self._last_analysis: Optional[ParityAnalysis] = None
        self._registrations: dict = {}
        self._pending: dict = {}
        self._finalized_hands: list = []
        self._last_accepted_capture_at: Optional[datetime] = None
        self._last_frame_fingerprint: Optional[str] = None
        self._startup_pending_ids: set = set()
        self._startup_registry_error: Optional[str] = None
        self._load_startup_pending_predictions()
        self._data_snapshot_id = _sha256_file(
            Path(self.config.parity_hands_path))

    @property
    def registry_path(self) -> Path:
        return self.registry.storage_path

    @property
    def engine(self):
        return self._engine

    def capture(self) -> CapturedFrame:
        self._assert_restart_clear()
        guard_warning = None
        if self.capture_guard is not None:
            guard_warning = self.capture_guard.acquire()
        frame = self.capture_adapter.capture()
        if guard_warning:
            frame = replace(frame, warnings=tuple(dict.fromkeys(
                tuple(frame.warnings) + (guard_warning,))))
        self._last_frame = frame
        self._last_analysis = None
        return frame

    def set_capture_guard(self, guard) -> None:
        """Inyecta la guardia de sesion usada por la GUI independiente."""
        self.capture_guard = guard

    def _load_startup_pending_predictions(self) -> None:
        """Marca eventos sin outcome de una ejecucion anterior como bloqueo."""
        try:
            verification = self.registry.verify_integrity()
            if not verification.ok:
                raise ValueError('; '.join(verification.issues))
            events = self.registry.read_events()
        except Exception as exc:  # registro ilegible: no iniciar a ciegas
            self._startup_registry_error = str(exc)
            return
        predictions = {
            event.get('payload', {}).get('prediction_id')
            for event in events if event.get('event_type') == 'HU_PREDICTION'
        }
        completed = {
            event.get('payload', {}).get('prediction_id')
            for event in events if event.get('event_type') == 'HU_OUTCOME'
        }
        self._startup_pending_ids = {
            prediction_id for prediction_id in predictions - completed
            if prediction_id
        }

    def _assert_restart_clear(self) -> None:
        if self._startup_registry_error:
            raise RuntimeError(
                'registro prospectivo no verificable; captura bloqueada: %s'
                % self._startup_registry_error)
        if not self._startup_pending_ids:
            return
        try:
            events = self.registry.read_events()
        except Exception as exc:
            raise RuntimeError(
                'no se pudieron reconciliar predicciones previas: %s' % exc)
        completed = {
            event.get('payload', {}).get('prediction_id')
            for event in events if event.get('event_type') == 'HU_OUTCOME'
        }
        self._startup_pending_ids.difference_update(completed)
        if self._startup_pending_ids:
            ids = ', '.join(sorted(self._startup_pending_ids))
            raise RuntimeError(
                'reinicio bloqueado: predicciones previas sin outcome (%s); '
                'reconciliar antes de capturar para evitar asociar otra mano'
                % ids)

    def _capture_sequence_rejection(self, frame: CapturedFrame):
        captured_at = _parse_capture_time(frame.captured_at)
        if captured_at is None:
            return 'capture_timestamp_invalid'
        fingerprint = _sha256_bytes(json.dumps(
            _json_safe(frame.state), sort_keys=True, ensure_ascii=False
        ).encode('utf-8'))
        previous = self._last_accepted_capture_at
        if previous is not None and captured_at < previous:
            return 'out_of_order_capture'
        if previous is not None and captured_at == previous:
            if fingerprint == self._last_frame_fingerprint:
                return 'duplicate_capture_timestamp'
            return 'capture_timestamp_collision'
        self._last_accepted_capture_at = captured_at
        self._last_frame_fingerprint = fingerprint
        return None

    def _find_persisted_decision(self, decision_key: str):
        if not decision_key:
            return None
        for event in reversed(self.registry.read_events()):
            if event.get('event_type') != 'HU_PREDICTION':
                continue
            payload = event.get('payload') or {}
            metadata = payload.get('metadata') or {}
            if metadata.get('decision_key') == decision_key:
                return event
        return None

    def ensure_engine(self):
        """Construye el motor live una sola vez, con salidas aisladas."""
        if self._engine is not None:
            return self._engine
        from .. import asistente_live as live
        from ..decision_log import DecisionLog
        import recorder_live

        models = self.models or live.build_models(verbose=False)
        engine = live.Asistente(models=models, hero_name=self.config.hero_name,
                                verbose=False)
        runtime = Path(self.config.runtime_dir)
        recorder = recorder_live.LiveRecorder(
            output_path=str(self.config.parity_hands_path),
            ambiguity_capture_dir=str(runtime / 'ambiguedades'),
        )
        # En HU el SB/button actua primero preflop y segundo postflop. El
        # recorder original conserva el orden de 6-max ['SB','BB',...] en
        # postflop, incorrecto al renombrar BTN como SB. Se corrige solo esta
        # instancia experimental; el modulo original no se toca.
        if self.config.parity_position_mode == 'hu_sb_bb':
            def hu_street_order(_recorder, state, street_name):
                del state
                if street_name == 'preflop':
                    return ['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB']
                return ['BB', 'SB', 'UTG', 'MP', 'CO', 'BTN']
            recorder._get_street_order = MethodType(hu_street_order, recorder)
        engine.rec = recorder
        if self.config.parity_position_mode == 'hu_sb_bb':
            engine._next_to_act = MethodType(_hu_next_to_act, engine)
            engine._hero_act = MethodType(_hu_hero_act, engine)
        engine.rec.on_hand_finalized = self._on_hand_finalized
        secondary = None
        if self.config.parity_enable_live_decision_log:
            secondary = DecisionLog(path=str(runtime / 'decisions_parity.jsonl'))
        self._collector = SnapshotCollector(secondary=secondary)
        engine.decision_log = self._collector
        engine.shadow = bool(self.config.parity_enable_shadow_logs)
        self._engine = engine
        return engine

    def analyze(self, source: Any = None, *, require_turn: bool = False,
                force_reco: bool = True) -> ParityAnalysis:
        # El motor original y el recorder no son thread-safe. El lock impide
        # que el polling automatico y el boton manual muten la misma mano.
        with self._lock:
            analysis = self._analyze(source, require_turn=require_turn,
                                     force_reco=force_reco)
            self._last_analysis = analysis
            return analysis

    def _analyze(self, source: Any = None, *, require_turn: bool = False,
                 force_reco: bool = True) -> ParityAnalysis:
        self._assert_restart_clear()
        started = datetime.now(timezone.utc).timestamp()
        if source is None:
            frame = self.capture()
        elif isinstance(source, CapturedFrame):
            frame = source
            self._last_frame = frame
        elif isinstance(source, Mapping):
            frame = CapturedFrame(state=dict(source),
                                  captured_at=self._clock(),
                                  source='mapping')
            self._last_frame = frame
        else:
            raise TypeError('source debe ser None, CapturedFrame o mapping')

        temporal_reason = self._temporal_rejection(frame)
        if temporal_reason:
            return self._blocked_analysis(
                frame, None, temporal_reason, started,
                warnings=frame.warnings)
        sequence_reason = self._capture_sequence_rejection(frame)
        if sequence_reason:
            return self._blocked_analysis(
                frame, None, sequence_reason, started,
                warnings=frame.warnings)

        try:
            hu = interpret_state(frame.state, hero_seat=self.config.hero_seat)
        except StateInterpretationError as exc:
            return self._blocked_analysis(
                frame, None, 'invalid_state:%s' % exc, started,
                warnings=frame.warnings)

        reasons = list(hu.uncertainty_reasons)
        warnings = list(frame.warnings)
        if hu.status != 'ready':
            return self._blocked_analysis(
                frame, hu, hu.reason or hu.status, started,
                reasons=reasons, warnings=warnings)
        if len(hu.active_seats) != 2:
            return self._blocked_analysis(
                frame, hu, 'not_heads_up:%d_active' % len(hu.active_seats),
                started, reasons=reasons, warnings=warnings)
        if len(hu.hero_cards) != 2:
            return self._blocked_analysis(
                frame, hu, 'hero_cards_not_observed', started,
                reasons=reasons, warnings=warnings)

        self.ensure_engine()
        self._collector.clear()
        captured = {}
        finalized_before = len(self._finalized_hands)
        restore_positions = self._apply_position_mode(hu)
        try:
            def on_reco(text, evs, sit, label):
                captured['text'] = text
                captured['evs'] = evs
                captured['sit'] = sit
                captured['label'] = label

            result = self._engine.step(
                frame.state, frame.image, frame.pil,
                log=self._logger, on_reco=on_reco,
                require_turn=(True if self.config.parity_position_mode ==
                              'hu_sb_bb' else require_turn),
                force_reco=force_reco,
            )
        finally:
            self._restore_positions(restore_positions)

        if len(self._finalized_hands) > finalized_before:
            return self._blocked_analysis(
                frame, hu, 'hand_finalized_during_capture_cycle', started,
                reasons=reasons, warnings=warnings)

        if self.config.parity_position_mode == 'hu_sb_bb':
            if self._engine._hero_pid() != hu.hero_seat:
                return self._blocked_analysis(
                    frame, hu, 'hero_identity_mismatch', started,
                    reasons=reasons, warnings=warnings)
            if not _hu_next_to_act(self._engine, frame.state, hu.hero_seat):
                return self._blocked_analysis(
                    frame, hu, 'no_hu_decision_pending', started,
                    reasons=reasons, warnings=warnings)

        if (self.config.parity_position_mode == 'hu_sb_bb'
                and hu.street != 'preflop'):
            order_reason = self._postflop_order_rejection()
            if order_reason:
                return self._blocked_analysis(
                    frame, hu, order_reason, started, reasons=reasons,
                    warnings=warnings)

        if result is None or not captured or self._collector.snapshot is None:
            reason = getattr(self._engine, 'last_reco_reason', None) \
                or 'live_engine_no_recommendation'
            return self._blocked_analysis(
                frame, hu, reason, started, reasons=reasons,
                warnings=warnings)
        return self._build_analysis(frame, hu, captured, started, reasons,
                                    warnings)

    def _postflop_order_rejection(self) -> Optional[str]:
        """No predice si el modelo live no dispone del primer turno HU real."""
        hand = getattr(getattr(self._engine, 'rec', None), 'hand', None)
        if not hand:
            return 'postflop_position_order_unverified'
        actions = (((hand.get('streets') or {}).get('flop') or {})
                   .get('actions') or [])
        if not actions:
            return 'postflop_position_order_unverified:no_flop_action_evidence'
        first = actions[0]
        if first.get('pos') != 'BB':
            return 'postflop_position_order_discrepancy:first=%s' % (
                first.get('pos'))
        if first.get('ambiguous') or first.get('inferred'):
            return 'postflop_position_order_unverified:ambiguous_first_action'
        return None

    def _temporal_rejection(self, frame: CapturedFrame) -> Optional[str]:
        """Rechaza frames antiguos o con captura/OCR demasiado tardios."""
        captured_at = _parse_capture_time(frame.captured_at)
        if captured_at is None:
            return 'capture_timestamp_invalid'
        age = datetime.now(timezone.utc).timestamp() - captured_at.timestamp()
        if age < -1.0:
            return 'capture_timestamp_in_future'
        if age > self.config.max_frame_age_s:
            return 'stale_capture:%.3fs' % age
        if (frame.capture_ms is not None
                and frame.capture_ms > self.config.max_capture_ms):
            return 'capture_delay:%.1fms' % frame.capture_ms
        if frame.ocr_ms is not None and frame.ocr_ms > self.config.max_ocr_ms:
            return 'ocr_delay:%.1fms' % frame.ocr_ms
        return None

    def _apply_position_mode(self, hu: HUState):
        if self.config.parity_position_mode != 'hu_sb_bb':
            return None
        if hu.button_seat not in hu.active_seats:
            return None
        import recorder_live

        previous = dict(recorder_live.MANUAL_POSITIONS)
        recorder_live.MANUAL_POSITIONS.clear()
        recorder_live.MANUAL_POSITIONS[hu.button_seat] = 'SB'
        for seat in hu.active_seats:
            if seat != hu.button_seat:
                recorder_live.MANUAL_POSITIONS[seat] = 'BB'
                break
        return previous

    @staticmethod
    def _restore_positions(previous) -> None:
        if previous is None:
            return
        import recorder_live
        recorder_live.MANUAL_POSITIONS.clear()
        recorder_live.MANUAL_POSITIONS.update(previous)

    def _build_analysis(self, frame: CapturedFrame, hu: HUState,
                        captured: Mapping[str, Any], started: float,
                        reasons: list, warnings: list) -> ParityAnalysis:
        snapshot = dict(self._collector.snapshot or {})
        # El snapshot de DecisionLog puede no repetir estos campos, pero el
        # colector los recibe por separado. Se congelan junto con la decision.
        if snapshot.get('hand_id') is None:
            snapshot['hand_id'] = self._collector.hand_id
        if snapshot.get('street') is None:
            snapshot['street'] = self._collector.street
        if snapshot.get('hero_position') is None:
            snapshot['hero_position'] = self._collector.hero_position
        if snapshot.get('actions_seen_count') is None:
            snapshot['actions_seen_count'] = self._collector.actions_seen_count
        preflop = snapshot.get('street') == 'preflop'
        position_mismatch = (
            bool(snapshot.get('hero_position'))
            and bool(hu.hero_position)
            and snapshot.get('hero_position') != hu.hero_position
        )
        if position_mismatch:
            if {snapshot.get('hero_position'), hu.hero_position} == {'BTN',
                                                                     'SB'}:
                reasons.append('position_mapping_live_btn_vs_hu_sb')
            else:
                reasons.append('position_mapping_live_vs_hu')
        if self.config.parity_position_mode == 'hu_sb_bb':
            reasons.append('position_mode_hu_correction_not_exact_live_parity')
        if preflop:
            reasons.append('preflop_action_is_sampled')
            reasons.append('preflop_equity_not_computed')
        reasons.append('live_engine_recommendation_not_certified')

        ev_view = self._live_ev_view(snapshot, preflop)
        coverage = self._coverage_state(snapshot, preflop)
        range_kind = 'statistics' if preflop else 'estimated'
        range_source = (
            'asistente_live:preflop_matrices'
            if preflop else
            'asistente_live:ProfileRangeModel+PostflopRangeModel'
        )
        equity = None if preflop else _finite(snapshot.get('equity'))
        equity_uncertainty = (
            'preflop_frequency_not_equity' if preflop else None)
        recommendation = snapshot.get('recommended_action')
        if recommendation is None and ev_view is not None:
            recommendation = ev_view.best_action

        decision_key = self._decision_key(snapshot)
        prediction = self._build_prediction(
            hu, snapshot, ev_view, captured.get('label'),
            position_mismatch, preflop, decision_key)
        elapsed = (datetime.now(timezone.utc).timestamp() - started) * 1000.0
        return ParityAnalysis(
            state=hu,
            snapshot=snapshot,
            prediction=prediction,
            decision_key=decision_key,
            live_recommendation=recommendation,
            canonical_status='unresolved',
            canonical_reason='live_engine_snapshot_not_re_evaluated',
            sequence_status='not_evaluated',
            coverage_state=coverage,
            range_kind=range_kind,
            range_source=range_source,
            range_provenance={
                'source': 'asistente_live_snapshot',
                'live_snapshot_sha256': _sha256_bytes(
                    json.dumps(_json_safe(snapshot), sort_keys=True,
                               ensure_ascii=False).encode('utf-8')),
                'live_position': snapshot.get('hero_position'),
                'hu_position': hu.hero_position,
                'live_default_position': (
                    'BTN' if hu.button_seat == hu.hero_seat else 'BB'),
                'position_correction': (
                    'button_is_sb_and_hu_postflop_order_overridden'
                    if self.config.parity_position_mode == 'hu_sb_bb'
                    else 'none_diagnostic_live_default'),
                'position_mismatch': position_mismatch,
                'villain_range': snapshot.get('villain_range'),
                'reproducibility': snapshot.get('reproducibility'),
                'preflop_table_audit': snapshot.get('preflop_table_audit'),
                'model_evidence': snapshot.get('model_evidence'),
            },
            equity=equity,
            equity_method=('situation_engine_vs_profile_range'
                           if equity is not None else None),
            equity_uncertainty=equity_uncertainty,
            ev_result=ev_view,
            selected_action=None,
            provisional_selected_action=recommendation,
            legal_actions=tuple(snapshot.get('candidate_actions') or ()),
            uncertainty_reasons=tuple(dict.fromkeys(reasons)),
            assumptions=(
                'La recomendacion la produce el motor asistente_live original.',
                'La recomendacion live no se reclasifica como demostrada.',
                'La equity preflop no se calcula: las tablas devuelven frecuencias.',
                'El resultado posterior se registra como evento separado.',
                'hu_sb_bb corrige deliberadamente el BTN/SB y el orden HU; '
                'no es paridad exacta con live_default.',
                'La recomendacion no se presenta como decision validada.',
            ),
            warnings=tuple(dict.fromkeys(warnings)),
            capture_source=frame.source,
            captured_at=frame.captured_at,
            elapsed_ms={'analysis': elapsed},
        )

    def _blocked_analysis(self, frame: CapturedFrame, hu: Optional[HUState],
                          reason: str, started: float, *,
                          reasons=None, warnings=None) -> ParityAnalysis:
        elapsed = (datetime.now(timezone.utc).timestamp() - started) * 1000.0
        if hu is None:
            hu = HUState(
                status='unresolved', reason=reason,
                hero_seat=self.config.hero_seat,
                villain_seat=None, hero_position=None, villain_position=None,
                active_seats=(), street='preflop', hero_cards=(), board=(),
                pot=None, to_call=None, hero_stack=None, villain_stack=None,
                hero_bet=None, villain_bet=None, button_seat=None,
                uncertainty_reasons=tuple(reasons or ()),
                observed_fields=(), raw_state=dict(frame.state),
            )
        return ParityAnalysis(
            state=hu,
            snapshot={},
            prediction=None,
            decision_key=None,
            live_recommendation=None,
            canonical_status=('no_decision' if hu.status == 'no_decision'
                              else 'unresolved'),
            canonical_reason=reason,
            sequence_status='not_evaluated',
            coverage_state='unknown',
            range_kind='unknown',
            range_source='none',
            range_provenance={},
            equity=None,
            equity_method=None,
            equity_uncertainty=None,
            ev_result=None,
            selected_action=None,
            provisional_selected_action=None,
            legal_actions=(),
            uncertainty_reasons=tuple(dict.fromkeys(
                list(reasons or ()) + [reason])),
            assumptions=(
                'No se invoca el motor live cuando la puerta HU no esta lista.',
            ),
            warnings=tuple(dict.fromkeys(warnings or ())),
            capture_source=frame.source,
            captured_at=frame.captured_at,
            elapsed_ms={'analysis': elapsed},
        )

    @staticmethod
    def _live_ev_view(snapshot: Mapping[str, Any],
                      preflop: bool) -> Optional[LiveEVView]:
        if preflop:
            values = snapshot.get('preflop_action_frequencies') or {}
            kind = 'frequency'
        else:
            values = snapshot.get('ev_by_action') or {}
            kind = 'ev'
        if not values:
            return None
        actions = []
        best = None
        best_value = None
        for action, value in values.items():
            number = _finite(value)
            if number is not None and (best_value is None or number > best_value):
                best, best_value = action, number
            actions.append(LiveActionView(
                action=str(action), amount=0.0, ev=number,
                status='usable' if number is not None else 'unknown',
                reason=None if number is not None else 'not_finite',
            ))
        return LiveEVView(
            actions=tuple(actions),
            best_action=snapshot.get('recommended_action') or best,
            best_ev=best_value,
            status='preflop_frequency' if preflop else 'live_ev',
            action_values_kind=kind,
        )

    @staticmethod
    def _coverage_state(snapshot: Mapping[str, Any], preflop: bool) -> str:
        if not preflop:
            return 'unknown'
        audit = snapshot.get('preflop_table_audit') or []
        states = {item.get('coverage_state') for item in audit
                  if isinstance(item, Mapping)}
        if states and states == {'exact'}:
            return 'exact'
        if states and states <= {'exact', 'alias'}:
            return 'alias'
        return 'unknown'

    @staticmethod
    def _decision_key(snapshot: Mapping[str, Any]) -> Optional[str]:
        if not snapshot:
            return None
        hand = snapshot.get('cards_known') or {}
        payload = {
            'hand_id': snapshot.get('hand_id'),
            'street': snapshot.get('street'),
            'actions_seen_count': snapshot.get('actions_seen_count'),
            'pot': snapshot.get('pot'),
            'to_call': snapshot.get('to_call'),
            'bets': snapshot.get('bets'),
            'stacks': snapshot.get('stacks'),
            'positions': snapshot.get('positions'),
            'hero': hand.get('hero'),
            'board': hand.get('board'),
        }
        return _sha256_bytes(json.dumps(
            _json_safe(payload), sort_keys=True, ensure_ascii=False
        ).encode('utf-8'))

    def _build_prediction(self, hu: HUState, snapshot: Mapping[str, Any],
                          ev_view: Optional[LiveEVView], label: Optional[str],
                          position_mismatch: bool, preflop: bool,
                          decision_key: Optional[str]) -> HUPrediction:
        cards = snapshot.get('cards_known') or {}
        hero_id = snapshot.get('hero_id')
        bets = snapshot.get('bets') or {}
        values = (
            snapshot.get('preflop_action_frequencies')
            if preflop else snapshot.get('ev_by_action')
        ) or {}
        action_ev = [
            {'action': str(action), 'amount': 0.0, 'ev': _finite(value),
             'status': ('usable' if _finite(value) is not None else 'unknown'),
             'value_kind': 'frequency' if preflop else 'ev'}
            for action, value in values.items()
        ]
        uncertainty = []
        if preflop:
            uncertainty.extend([
                'preflop_action_is_sampled',
                'preflop_equity_not_computed',
                'preflop_values_are_frequencies',
            ])
        if position_mismatch:
            if {snapshot.get('hero_position'), hu.hero_position} == {'BTN',
                                                                     'SB'}:
                uncertainty.append('position_mapping_live_btn_vs_hu_sb')
            else:
                uncertainty.append('position_mapping_live_vs_hu')
        if self.config.parity_position_mode == 'hu_sb_bb':
            uncertainty.append(
                'position_mode_hu_correction_not_exact_live_parity')
        uncertainty.append('live_engine_recommendation_not_certified')
        metadata = {
            'source': 'asistente_live',
            'engine': PARITY_VERSION,
            'decision_id': self._collector.decision_id,
            'hand_id': snapshot.get('hand_id'),
            'street': snapshot.get('street'),
            'actions_seen_count': snapshot.get('actions_seen_count'),
            'live_label': label,
            'live_position': snapshot.get('hero_position'),
            'hu_position': hu.hero_position,
            'position_mode': self.config.parity_position_mode,
            'live_default_position': (
                'BTN' if hu.button_seat == hu.hero_seat else 'BB'),
            'position_correction': (
                'button_is_sb_and_hu_postflop_order_overridden'
                if self.config.parity_position_mode == 'hu_sb_bb'
                else 'none_diagnostic_live_default'),
            'position_mismatch': bool(position_mismatch),
            'preflop': bool(preflop),
            'action_values_kind': 'frequency' if preflop else 'ev',
            # La puerta HU garantiza exactamente dos asientos activos. El
            # valor del snapshot live se conserva solo como dato de auditoria;
            # la prediccion de paridad no autoriza multiway.
            'multiway': False,
            'multiway_soportado': False,
            'live_snapshot_multiway_soportado': snapshot.get(
                'multiway_soportado'),
            'hand_db_path': str(self.config.parity_hands_path),
            'hand_db_snapshot_sha256': self._data_snapshot_id,
            'live_decision_log_enabled':
                bool(self.config.parity_enable_live_decision_log),
            'shadow_logs_enabled': bool(self.config.parity_enable_shadow_logs),
            'preflop_sampling': snapshot.get('preflop_sampling'),
            'preflop_table_audit': snapshot.get('preflop_table_audit'),
            'model_evidence': snapshot.get('model_evidence'),
            'decision_key': decision_key,
        }
        return HUPrediction(
            prediction_id=uuid.uuid4().hex,
            emitted_at=self._clock(),
            hero_position=snapshot.get('hero_position') or hu.hero_position
            or 'UNKNOWN',
            canonical_status='unresolved',
            coverage_state=self._coverage_state(snapshot, preflop),
            sequence_status='not_evaluated',
            range_kind='statistics' if preflop else 'estimated',
            range_source=(
                'asistente_live:preflop_matrices' if preflop else
                'asistente_live:ProfileRangeModel+PostflopRangeModel'),
            range_provenance={
                'source': 'asistente_live_snapshot',
                'live_position': snapshot.get('hero_position'),
                'hu_position': hu.hero_position,
                'position_mismatch': bool(position_mismatch),
                'preflop_table_audit': snapshot.get('preflop_table_audit'),
                'reproducibility': snapshot.get('reproducibility'),
            },
            # El snapshot live no garantiza que response_model_inputs sea
            # una distribucion normalizada; se conserva en provenance.
            response_distribution=None,
            equity=None if preflop else _finite(snapshot.get('equity')),
            equity_scenario=(None if preflop else
                             'showdown_vs_profile_range'),
            equity_method=(None if preflop else
                           'situation_engine_vs_profile_range'),
            action_ev=action_ev,
            selected_action=None,
            provisional_selected_action=(
                snapshot.get('recommended_action')
                or (ev_view.best_action if ev_view else None)),
            legal_actions=list(snapshot.get('candidate_actions') or ()),
            uncertainty_reasons=uncertainty,
            pot=_finite(snapshot.get('pot')),
            to_call=_finite(snapshot.get('to_call')),
            hero_stack=_finite((snapshot.get('stacks') or {}).get(hero_id)),
            villain_stack=_finite((snapshot.get('stacks') or {}).get(
                snapshot.get('villain_id'))),
            hero_contribution_before=_finite(bets.get(hero_id)),
            villain_contribution_before=_finite(bets.get(
                snapshot.get('villain_id'))),
            board=list(cards.get('board') or ()),
            hero_cards=list(cards.get('hero') or ()),
            prior_actions=list(snapshot.get('actions_before_decision') or ()),
            code_version=PARITY_VERSION,
            data_snapshot_id=self._data_snapshot_id,
            assumptions=[
                'Recomendacion del motor asistente_live original.',
                'No es una decision demostrada del registro HU.',
                'El snapshot se congela antes de la accion posterior.',
                'La posicion live y la posicion HU se declaran por separado.',
            ],
            metadata=metadata,
        )

    def register_analysis(self, analysis: ParityAnalysis, *,
                          prediction_id: Optional[str] = None,
                          emitted_at: Optional[str] = None
                          ) -> ParityRegistration:
        with self._lock:
            registration = self._register_analysis(
                analysis, prediction_id=prediction_id, emitted_at=emitted_at)
            self._flush_post_capture_observations()
            return registration

    def _register_analysis(self, analysis: ParityAnalysis, *,
                           prediction_id: Optional[str] = None,
                           emitted_at: Optional[str] = None
                           ) -> ParityRegistration:
        self._assert_restart_clear()
        if not isinstance(analysis, ParityAnalysis):
            raise TypeError('analysis debe ser ParityAnalysis')
        prediction = analysis.prediction
        if prediction is None:
            raise ValueError('la analisis no contiene prediccion')
        self._assert_registry_integrity()
        if prediction.metadata.get('position_mode') != 'hu_sb_bb':
            raise ValueError(
                'live_default es solo diagnostico; no se persiste prediccion')
        recorder_hand = (self._engine.rec.hand
                         if self._engine is not None else None) or {}
        hand_id = (analysis.snapshot.get('hand_id')
                   or recorder_hand.get('hand_id'))
        if not hand_id:
            raise ValueError(
                'prediccion no registrada: hand_identity_unavailable')
        if prediction.metadata.get('hand_id') != hand_id:
            metadata = dict(prediction.metadata or {})
            metadata['hand_id'] = hand_id
            prediction = HUPrediction(
                **{**prediction.to_payload(), 'metadata': metadata})
        temporal_reason = self._analysis_temporal_rejection(analysis)
        if temporal_reason:
            raise ValueError('prediccion no registrada: %s' % temporal_reason)
        if prediction_id or emitted_at:
            prediction = HUPrediction(
                **{**prediction.to_payload(),
                   **({'prediction_id': prediction_id}
                      if prediction_id else {}),
                   **({'emitted_at': emitted_at} if emitted_at else {})})
        key = analysis.decision_key or prediction.prediction_id
        if key in self._registrations:
            return self._registrations[key]
        existing = self._find_persisted_decision(analysis.decision_key)
        if existing is not None:
            stored_prediction = HUPrediction(**existing['payload'])
            registration = ParityRegistration(
                analysis=analysis, prediction=stored_prediction,
                event=existing, registry_path=str(self.registry_path))
            self._registrations[key] = registration
            if not self._prediction_has_outcome(stored_prediction.prediction_id):
                self._remember_pending(analysis, stored_prediction)
            return registration
        event = self.registry.register_prediction(prediction)
        registration = ParityRegistration(
            analysis=analysis,
            prediction=prediction,
            event=event,
            registry_path=str(self.registry_path),
        )
        self._registrations[key] = registration
        self._remember_pending(analysis, prediction)
        return registration

    def _remember_pending(self, analysis, prediction):
        snapshot = analysis.snapshot
        hand = (self._engine.rec.hand if self._engine is not None else None) or {}
        self._pending[prediction.prediction_id] = {
            'prediction_id': prediction.prediction_id,
            'hand_id': snapshot.get('hand_id') or hand.get('hand_id'),
            'street': snapshot.get('street'),
            'hero_position': snapshot.get('hero_position'),
            'actions_seen_count': snapshot.get('actions_seen_count'),
            'actions_seen': [
                a for a in snapshot.get('actions_before_decision') or []
                if a.get('street') == snapshot.get('street')
            ],
        }

    def _prediction_has_outcome(self, prediction_id):
        return any(
            event.get('event_type') == 'HU_OUTCOME'
            and (event.get('payload') or {}).get('prediction_id') == prediction_id
            for event in self.registry.read_events()
        )

    def _analysis_temporal_rejection(self, analysis: ParityAnalysis):
        frame = self._last_frame
        if frame is not None and frame.captured_at == analysis.captured_at:
            return self._temporal_rejection(frame)
        captured_at = _parse_capture_time(analysis.captured_at)
        if captured_at is None:
            return 'capture_timestamp_invalid'
        age = datetime.now(timezone.utc).timestamp() - captured_at.timestamp()
        if age < -1.0:
            return 'capture_timestamp_in_future'
        if age > self.config.max_frame_age_s:
            return 'stale_capture:%.3fs' % age
        return None

    def _assert_registry_integrity(self) -> None:
        verification = self.registry.verify_integrity()
        if not verification.ok:
            raise RuntimeError(
                'registro prospectivo integro requerido: %s'
                % '; '.join(verification.issues))

    def predict_and_register(self, source: Any = None, *,
                             prediction_id: Optional[str] = None,
                             emitted_at: Optional[str] = None
                             ) -> ParityRegistration:
        with self._lock:
            if source is not None and source is self._last_frame \
                    and self._last_analysis is not None:
                analysis = self._last_analysis
            else:
                analysis = self.analyze(source)
            return self.register_analysis(
                analysis, prediction_id=prediction_id,
                emitted_at=emitted_at)

    def poll_once(self):
        """Un ciclo de observacion automatica: analiza y persiste si hay spot."""
        from .automation import PollEvent
        with self._lock:
            cycle_started = time.perf_counter()
            try:
                phase_started = time.perf_counter()
                analysis = self.analyze(None, require_turn=True,
                                        force_reco=False)
                analysis_ms = (time.perf_counter() - phase_started) * 1000.0
                registration = None
                if self.config.parity_position_mode != 'hu_sb_bb':
                    return PollEvent(
                        analysis=analysis,
                        error=('live_default es solo diagnostico; '
                               'no se persiste prediccion'),
                        elapsed_ms=(time.perf_counter() - cycle_started) * 1000.0,
                        phase_times_ms={'capture_and_analysis': analysis_ms})
                persist_ms = 0.0
                if analysis.prediction is not None:
                    key = (analysis.decision_key
                           or analysis.prediction.prediction_id)
                    if key not in self._registrations:
                        phase_started = time.perf_counter()
                        registration = self._register_analysis(analysis)
                        persist_ms = (time.perf_counter() - phase_started) * 1000.0
                phase_started = time.perf_counter()
                self._flush_post_capture_observations()
                outcome_ms = (time.perf_counter() - phase_started) * 1000.0
                total_ms = (time.perf_counter() - cycle_started) * 1000.0
                return PollEvent(
                    analysis=analysis, registration=registration,
                    elapsed_ms=total_ms,
                    phase_times_ms={
                        'capture_and_analysis': analysis_ms,
                        'prediction_persistence': persist_ms,
                        'posterior_observation_and_persistence': outcome_ms,
                        'total': total_ms,
                    })
            except Exception as exc:  # noqa: BLE001
                total_ms = (time.perf_counter() - cycle_started) * 1000.0
                return PollEvent(error=str(exc), elapsed_ms=total_ms)

    def _record_observed_outcomes(self) -> None:
        engine = self._engine
        if engine is None:
            return
        hand = getattr(engine.rec, 'hand', None)
        if not hand:
            return
        hand_id = hand.get('hand_id')
        for prediction_id, item in list(self._pending.items()):
            if not item.get('hand_id') or item.get('hand_id') != hand_id:
                continue
            street = item.get('street')
            record = ((hand.get('streets') or {}).get(street) or {})
            actions = record.get('actions') or []
            seen = Counter(_signature(a) for a in item.get('actions_seen') or [])
            new_actions = []
            for candidate in actions:
                key = _signature(candidate)
                if seen[key]:
                    seen[key] -= 1
                else:
                    new_actions.append(candidate)
            hero_action = next(
                (a for a in new_actions
                 if a.get('pos') == item.get('hero_position')), None)
            if hero_action is not None:
                self._register_auto_outcome(
                    prediction_id,
                    observed_action=hero_action.get('action'),
                    new_information={
                        'hand_id': hand_id,
                        'street': street,
                        'actions': _json_safe(new_actions),
                    },
                )

    def _flush_post_capture_observations(self) -> None:
        """Persiste posterior solo despues de capturar/calcular/persistir."""
        finalized, self._finalized_hands = self._finalized_hands, []
        for hand in finalized:
            self._record_finalized_hand(hand)
        self._expire_pending_after_hand_change()
        self._record_observed_outcomes()

    def _expire_pending_after_hand_change(self) -> None:
        hand = getattr(getattr(self._engine, 'rec', None), 'hand', None)
        if not hand or not hand.get('hand_id'):
            return
        current_hand_id = hand.get('hand_id')
        for prediction_id, item in list(self._pending.items()):
            expected = item.get('hand_id')
            if expected and expected != current_hand_id:
                self._register_auto_outcome(
                    prediction_id,
                    exclusion_reason='hand_id_changed_before_outcome',
                    new_information={
                        'expected_hand_id': expected,
                        'observed_hand_id': current_hand_id,
                        'association': 'excluded_not_joined_across_hands',
                    },
                )

    def _on_hand_finalized(self, hand) -> None:
        # El callback ocurre dentro de process_frame, antes de que el ciclo
        # automatico pueda persistir la prediccion actual. Se difiere cualquier
        # escritura/outcome hasta _flush_post_capture_observations().
        self._finalized_hands.append(_json_safe(hand))

    def _record_finalized_hand(self, hand) -> None:
        if self._collector.secondary is not None:
            try:
                self._collector.secondary.resolve_hand(hand)
            except Exception:
                pass
        hand_id = hand.get('hand_id')
        revealed = {
            p.get('pos'): p.get('cards') for p in hand.get('players') or []
            if p.get('cards')
        }
        for prediction_id, item in list(self._pending.items()):
            if not item.get('hand_id') or item.get('hand_id') != hand_id:
                continue
            hero_action = _last_hero_action(
                hand, item.get('hero_position'))
            self._register_auto_outcome(
                prediction_id,
                observed_action=hero_action,
                new_information={
                    'hand_id': hand_id,
                    'streets': _json_safe(hand.get('streets') or {}),
                },
                result={
                    'final_pot': hand.get('final_pot'),
                    'winner_ids': _json_safe(hand.get('winner')),
                    'showdown': _json_safe(hand.get('showdown')),
                    'revealed_cards': _json_safe(revealed),
                },
            )

    def _register_auto_outcome(self, prediction_id: str, *,
                               observed_action: Optional[str] = None,
                               new_information: Optional[Mapping[str, Any]] = None,
                               result: Optional[Mapping[str, Any]] = None,
                               exclusion_reason: Optional[str] = None,
                               ) -> Optional[Mapping[str, Any]]:
        try:
            event = self.record_outcome(
                prediction_id,
                observed_action=observed_action,
                new_information=new_information,
                result=result,
                exclusion_reason=exclusion_reason,
                notes='auto_observed_by_hu_parity',
            )
        except Exception as exc:  # noqa: BLE001 - no romper el polling
            self._logger('[parity] no se pudo registrar outcome %s: %s'
                         % (prediction_id, exc))
            return None
        self._pending.pop(prediction_id, None)
        return event

    def record_outcome(self, prediction_id: str, *,
                       outcome_id: Optional[str] = None,
                       observed_at: Optional[str] = None,
                       observed_action: Optional[str] = None,
                       new_information: Optional[Mapping[str, Any]] = None,
                       result: Optional[Mapping[str, Any]] = None,
                       exclusion_reason: Optional[str] = None,
                       notes: Optional[str] = None) -> Mapping[str, Any]:
        with self._lock:
            return self._record_outcome(
                prediction_id, outcome_id=outcome_id,
                observed_at=observed_at, observed_action=observed_action,
                new_information=new_information, result=result,
                exclusion_reason=exclusion_reason, notes=notes)

    def _record_outcome(self, prediction_id: str, *,
                        outcome_id: Optional[str] = None,
                        observed_at: Optional[str] = None,
                        observed_action: Optional[str] = None,
                        new_information: Optional[Mapping[str, Any]] = None,
                        result: Optional[Mapping[str, Any]] = None,
                        exclusion_reason: Optional[str] = None,
                        notes: Optional[str] = None) -> Mapping[str, Any]:
        self._assert_registry_integrity()
        outcome = HUOutcome(
            outcome_id=outcome_id or uuid.uuid4().hex,
            prediction_id=prediction_id,
            observed_at=observed_at or self._clock(),
            observed_action=observed_action,
            new_information=new_information,
            result=result,
            exclusion_reason=exclusion_reason,
            notes=notes,
        )
        return self.registry.register_outcome(outcome)

    def verify(self) -> VerificationResult:
        return self.registry.verify_integrity()

    def create_backup(self, backup_path: Optional[Any] = None):
        if backup_path is None:
            self.config.backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            backup_path = self.config.backup_dir / (
                '%s.%s.jsonl' % (self.registry_path.stem, stamp))
        return self.registry.create_backup(backup_path)

    def restore_backup(self, backup_path: Any, *,
                       destination: Optional[Any] = None,
                       overwrite: bool = False) -> Path:
        return self.registry.restore_backup(backup_path, destination,
                                            overwrite=overwrite)


def _hu_next_to_act(self, state, hero_pid=None):
    """Turno HU estricto para el adapter SB/BB, sin orden 6-max heredado."""
    hero_pid = hero_pid or self._hero_pid()
    hand = getattr(getattr(self, 'rec', None), 'hand', None)
    if not hand:
        return False
    street = hand.get('current_street') or 'preflop'
    positions = self._pos_map(state)
    folds = self._recorded_folds()
    order = ('SB', 'BB') if street == 'preflop' else ('BB', 'SB')
    players = {}
    for pid, position in positions.items():
        if position not in order or position in folds:
            continue
        if state.get('%s_state' % pid) != 'activo':
            continue
        stack = state.get('%s_stake' % pid)
        if not isinstance(stack, (int, float)) or stack <= 0.01:
            continue
        players[position] = pid
    sequence = [position for position in order if position in players]
    if len(sequence) != 2 or positions.get(hero_pid) not in sequence:
        return False

    bets = {position: state.get('%s_bet' % players[position]) or 0.0
            for position in sequence}
    max_bet = max(bets.values(), default=0.0)
    owing = [position for position in sequence
             if max_bet - bets[position] > 0.01]
    if owing:
        return players[owing[0]] == hero_pid

    actions = (((hand.get('streets') or {}).get(street) or {})
               .get('actions') or [])
    acted = {action.get('pos') for action in actions
             if action.get('action') in ('x', 'c', 'f', 'b', 'r')}
    next_position = next((position for position in sequence
                          if position not in acted), None)
    return next_position is not None and players[next_position] == hero_pid


def _hu_hero_act(self, state, _pil=None):
    """El frame visual no sustituye la puerta HU de turno/acción pendiente."""
    return _hu_next_to_act(self, state, self._hero_pid())


def _signature(action: Mapping[str, Any]):
    return (action.get('pos'), action.get('action'),
            action.get('amount'), action.get('amount_type'))


def _last_hero_action(hand: Mapping[str, Any],
                      hero_position: Optional[str]) -> Optional[str]:
    if not hero_position:
        return None
    for street in ('river', 'turn', 'flop', 'preflop'):
        actions = ((hand.get('streets') or {}).get(street) or {}).get(
            'actions') or []
        for action in reversed(actions):
            if action.get('pos') == hero_position:
                return action.get('action')
    return None
