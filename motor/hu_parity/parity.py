"""Adaptador de paridad HU sobre el motor original ``asistente_live``.

Este modulo es la Fase 10.1. No modifica ``motor/asistente_live.py`` ni el
recorder: los instancia y los usa. La puerta HU se aplica *antes* de llamar al
motor live. Las predicciones se persisten en el registro prospectivo aislado;
el resultado posterior se registra como evento separado.

Modos de posicion:

- ``live_default``: replica exactamente las posiciones que asigna el recorder
  original (en HU suele dar BTN/BB). Es paridad con el defecto live, no una
  correccion estrategica, y no se persiste (solo diagnostico).
- ``hu_in_6max``: modo operativo para mesas 6-max. Usa las posiciones y el
  orden live de la mesa, y solo recomienda cuando quedan exactamente 2
  jugadores activos en la mano. No fuerza SB/BB: la situacion HU se define por
  los jugadores activos, no por el tipo de mesa.
- ``hu_sb_bb``: fuerza SB/BB en una mesa realmente HU mediante
  ``MANUAL_POSITIONS``. Usa el mismo motor, pero corrige la posicion HU de
  forma explicita. La diferencia se declara en la prediccion.

Nada de esto autoriza un piloto real ni escribe en ``data/`` por defecto.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
import time
import uuid
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
)
from .recorder_bridge import (
    RecorderSnapshot,
    SnapshotLiveRecorder,
    build_unprocessed_snapshot,
    interpret_recorder_snapshot,
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
    recorder_snapshot: Optional[RecorderSnapshot] = None

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
            'recorder_snapshot': (
                self.recorder_snapshot.as_dict()
                if self.recorder_snapshot is not None else None),
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
        self._capture_lock = threading.Lock()
        self._collector = SnapshotCollector()
        self._last_frame: Optional[CapturedFrame] = None
        self._last_analysis: Optional[ParityAnalysis] = None
        self._last_decision_analysis: Optional[ParityAnalysis] = None
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

    def pending_outcome_ids(self) -> tuple:
        """Predicciones de una ejecucion previa aun sin outcome observado.

        Solo lectura. La GUI las presenta al operador para que registre la
        accion observada antes de iniciar una captura nueva. No modifica el
        bloqueo de reinicio: ``_assert_restart_clear`` sigue siendo la unica
        puerta que lo levanta.
        """
        return tuple(sorted(self._startup_pending_ids))

    def pending_outcomes(self) -> tuple:
        """Metadatos legibles de las predicciones previas sin outcome.

        Solo lectura. Devuelve ``prediction_id``, ``hand_id``, ``street``,
        ``hu_position``, ``action`` y ``emitted_at`` para que la GUI pida el
        resultado sin mostrar unicamente un identificador hexadecimal.
        """
        ids = set(self._startup_pending_ids)
        if not ids:
            return ()
        entries = {}
        try:
            events = self.registry.read_events()
        except Exception:  # registro ilegible: la GUI mostrara el id
            events = ()
        for event in events:
            if event.get('event_type') != 'HU_PREDICTION':
                continue
            payload = event.get('payload') or {}
            prediction_id = payload.get('prediction_id')
            if prediction_id not in ids:
                continue
            metadata = payload.get('metadata') or {}
            entries[prediction_id] = {
                'prediction_id': prediction_id,
                'hand_id': metadata.get('hand_id'),
                'street': metadata.get('street'),
                'hu_position': metadata.get('hu_position'),
                'action': payload.get('provisional_selected_action'),
                'emitted_at': payload.get('emitted_at'),
            }
        return tuple(
            entries.get(prediction_id)
            or {'prediction_id': prediction_id}
            for prediction_id in sorted(ids))

    def startup_registry_error(self) -> Optional[str]:
        """Error de verificacion del registro al iniciar, si lo hubo."""
        return self._startup_registry_error

    @property
    def engine(self):
        return self._engine

    def capture(self) -> CapturedFrame:
        # Manual y polling automatico comparten adapter/lectores; una segunda
        # captura concurrente podria reutilizar buffers o mezclar frames.
        with self._capture_lock:
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

    def prepare(self) -> float:
        """Inicializa los lectores originales sin capturar ni analizar.

        Se expone para que la GUI pueda pagar el arranque de plantillas OCR
        (~5-8 s la primera vez) antes de la primera captura y mostrar el coste
        como ``setup_ms``, nunca como latencia del frame.
        """
        prepare = getattr(self.capture_adapter, 'prepare', None)
        if prepare is None:
            return 0.0
        with self._capture_lock:
            return prepare() or 0.0

    def prepare_engine(self):
        """Construye el motor original y sus salidas aisladas sin capturar."""
        with self._lock:
            return self.ensure_engine()

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
        """Construye el motor live una sola vez, con salidas aisladas.

        El recorder es ``SnapshotLiveRecorder`` en modo diagnostico estricto:
        no escribe el hand DB, no guarda frames/ambiguedades, no ejecuta el
        callback persistente de ``DecisionLog`` y no registra outcomes de
        manos reales. El motor original sigue recibiendo el estado bruto.
        """
        if self._engine is not None:
            return self._engine
        from .. import asistente_live as live

        models = self.models or live.build_models(verbose=False)
        engine = live.Asistente(models=models, hero_name=self.config.hero_name,
                                verbose=False)
        runtime = Path(self.config.runtime_dir)
        recorder = SnapshotLiveRecorder(
            output_path=str(self.config.parity_hands_path),
            ambiguity_capture_dir=str(runtime / 'ambiguedades'),
            diagnostic_mode=True,
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
        # ``hu_in_6max`` conserva el orden y las posiciones 6-max del motor
        # original; la puerta solo exige 2 jugadores activos. No se reemplazan
        # ``_next_to_act``/``_hero_act`` porque eso impondria el orden HU.
        if self.config.parity_position_mode == 'hu_sb_bb':
            engine._next_to_act = MethodType(_hu_next_to_act, engine)
            engine._hero_act = MethodType(_hu_hero_act, engine)
        # Sin callback persistente: las manos finalizadas se recogen en
        # memoria mediante ``take_finalized_hands``. No se convierten en
        # outcomes automaticamente; ``record_outcome`` es la unica operacion
        # de escritura posterior explicita.
        engine.rec.on_hand_finalized = None
        # La configuracion historica de DecisionLog se ignora en diagnostico.
        # ``SnapshotCollector`` no escribe ni abre rutas persistentes.
        self._collector = SnapshotCollector(secondary=None)
        engine.decision_log = self._collector
        engine.shadow = False
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

        # Snapshot de diagnostico sin ejecutar el recorder. Conserva lo que el
        # OCR mostro para que un rechazo temporal no aparezca como estado vacio.
        # No es un snapshot procesado y nunca se usa como puerta operativa.
        recorder = getattr(self._engine, 'rec', None)
        pre_snapshot = build_unprocessed_snapshot(
            recorder, frame.state, sequence=0,
            captured_at=frame.captured_at, capture_source=frame.source,
            image=frame.image)
        try:
            pre_hu = interpret_recorder_snapshot(
                pre_snapshot, hero_seat=self.config.hero_seat,
                require_processed=False)
            invalid_reason = None
        except (StateInterpretationError, ValueError) as exc:
            pre_hu = None
            invalid_reason = 'invalid_state:%s' % exc

        diagnostic_reasons = (list(pre_hu.uncertainty_reasons)
                              if pre_hu else [])
        temporal_reason = self._temporal_rejection(frame)
        if temporal_reason:
            observed = (replace(pre_hu, status='unresolved',
                                reason=temporal_reason)
                        if pre_hu is not None else None)
            return self._blocked_analysis(
                frame, observed, temporal_reason, started,
                reasons=diagnostic_reasons, warnings=frame.warnings,
                recorder_snapshot=pre_snapshot)
        sequence_reason = self._capture_sequence_rejection(frame)
        if sequence_reason:
            observed = (replace(pre_hu, status='unresolved',
                                reason=sequence_reason)
                        if pre_hu is not None else None)
            return self._blocked_analysis(
                frame, observed, sequence_reason, started,
                reasons=diagnostic_reasons, warnings=frame.warnings,
                recorder_snapshot=pre_snapshot)
        if invalid_reason is not None:
            return self._blocked_analysis(
                frame, None, invalid_reason, started,
                warnings=frame.warnings, recorder_snapshot=pre_snapshot)

        self.ensure_engine()
        recorder = self._engine.rec
        self._drain_recorder_finalized()
        self._collector.clear()
        captured = {}
        finalized_before = len(self._finalized_hands)

        # El modo operativo 6-max no debe iniciar una mano incompleta si la
        # GUI/polling se abre cuando el board ya tiene flop/turn/river. Sin la
        # historia preflop el ledger no puede reconciliar el bote observado;
        # se espera a una mano nueva, empezando por preflop, en vez de procesar
        # y conservar una reconstruccion parcial.
        if (self.config.parity_position_mode == 'hu_in_6max'
                and recorder.hand is None
                and pre_hu is not None
                and pre_hu.street in ('flop', 'turn', 'river')):
            return self._blocked_analysis(
                frame, pre_hu, 'awaiting_preflop_after_midhand_start', started,
                reasons=diagnostic_reasons, warnings=frame.warnings,
                recorder_snapshot=pre_snapshot)

        # El recorder procesa la captura exactamente una vez. Se le entrega
        # una copia para que ninguna mutacion interna (p.ej. reasignacion de
        # cartas) altere el estado bruto que recibira el motor original.
        restore_positions = (self._apply_position_mode(pre_hu)
                             if pre_hu is not None else None)
        try:
            try:
                recorder.process_frame(
                    frame.state, frame.image, log=self._logger,
                    captured_at=frame.captured_at,
                    capture_source=frame.source)
            except Exception as exc:
                snapshot = recorder.last_snapshot
                self._drain_recorder_finalized()
                return self._blocked_analysis(
                    frame, None, 'recorder_error:%s' % exc, started,
                    reasons=list(frame.warnings), warnings=frame.warnings,
                    recorder_snapshot=snapshot)
            snapshot = recorder.last_snapshot
            self._drain_recorder_finalized()
        finally:
            self._restore_positions(restore_positions)

        if snapshot is None:
            return self._blocked_analysis(
                frame, None, 'recorder_snapshot_unavailable', started,
                reasons=list(frame.warnings), warnings=frame.warnings)
        hu = interpret_recorder_snapshot(
            snapshot, hero_seat=self.config.hero_seat)
        reasons = list(hu.uncertainty_reasons)
        warnings = list(frame.warnings)

        if len(self._finalized_hands) > finalized_before:
            return self._blocked_analysis(
                frame, hu, 'hand_finalized_during_capture_cycle', started,
                reasons=reasons, warnings=warnings,
                recorder_snapshot=snapshot)
        if hu.status != 'ready':
            return self._blocked_analysis(
                frame, hu, hu.reason or hu.status, started,
                reasons=reasons, warnings=warnings,
                recorder_snapshot=snapshot)
        if len(hu.active_seats) != 2:
            return self._blocked_analysis(
                frame, hu, 'not_heads_up:%d_active' % len(hu.active_seats),
                started, reasons=reasons, warnings=warnings,
                recorder_snapshot=snapshot)
        if len(hu.hero_cards) != 2:
            return self._blocked_analysis(
                frame, hu, 'hero_cards_not_observed', started,
                reasons=reasons, warnings=warnings,
                recorder_snapshot=snapshot)

        if self.config.parity_position_mode in ('hu_sb_bb', 'hu_in_6max'):
            if self._engine._hero_pid() != hu.hero_seat:
                return self._blocked_analysis(
                    frame, hu, 'hero_identity_mismatch', started,
                    reasons=reasons, warnings=warnings,
                    recorder_snapshot=snapshot)
        if self.config.parity_position_mode == 'hu_sb_bb':
            if not _hu_next_to_act(self._engine, frame.state, hu.hero_seat):
                return self._blocked_analysis(
                    frame, hu, 'no_hu_decision_pending', started,
                    reasons=reasons, warnings=warnings,
                    recorder_snapshot=snapshot)

        # En ``hu_in_6max`` el turno lo decide el motor live con las posiciones
        # y el orden 6-max de la mano. No se aplica el corrector HU de
        # ``hu_sb_bb`` ni la puerta de orden postflop HU: la situacion HU se
        # define por los 2 jugadores activos, no por el tipo de mesa.
        if (self.config.parity_position_mode == 'hu_sb_bb'
                and hu.street != 'preflop'):
            order_reason = self._postflop_order_rejection()
            if order_reason:
                return self._blocked_analysis(
                    frame, hu, order_reason, started, reasons=reasons,
                    warnings=warnings, recorder_snapshot=snapshot)

        # La unica ejecucion real de ``process_frame`` ya ocurrio. ``step``
        # recibe el estado bruto y no vuelve a procesar el frame; su llamada
        # interna queda registrada como suprimida, no como segunda ejecucion.
        try:
            with recorder.suppress_processing():
                def on_reco(text, evs, sit, label):
                    captured['text'] = text
                    captured['evs'] = evs
                    captured['sit'] = sit
                    captured['label'] = label

                result = self._engine.step(
                    frame.state, frame.image, frame.pil,
                    log=self._logger, on_reco=on_reco,
                    require_turn=(True if self.config.parity_position_mode in
                                  ('hu_sb_bb', 'hu_in_6max') else require_turn),
                    force_reco=force_reco,
                )
        except Exception as exc:  # el fallo no puede saltarse la puerta
            return self._blocked_analysis(
                frame, hu, 'live_engine_error:%s' % exc, started,
                reasons=reasons, warnings=warnings,
                recorder_snapshot=snapshot)

        if result is None or not captured or self._collector.snapshot is None:
            cached = self._dedupe_cached_analysis(frame, started)
            if cached is not None:
                return cached
            reason = getattr(self._engine, 'last_reco_reason', None) \
                or 'live_engine_no_recommendation'
            return self._blocked_analysis(
                frame, hu, reason, started, reasons=reasons,
                warnings=warnings, recorder_snapshot=snapshot)
        analysis = self._build_analysis(
            frame, hu, captured, started, reasons, warnings,
            recorder_snapshot=snapshot)
        self._last_decision_analysis = analysis
        return analysis

    def _dedupe_cached_analysis(self, frame: CapturedFrame,
                                started: float) -> Optional[ParityAnalysis]:
        """Reusa la prediccion vigente cuando el motor omite recalcular.

        ``asistente_live.step`` deduplica por firma de estado: si el polling
        vuelve a leer la misma situacion no emite una nueva recomendacion
        (``force_reco=False``). Sin reutilizar el analisis anterior la GUI
        reemplazaria la prediccion visible por "sin recomendacion" en el
        siguiente ciclo, mostrandola solo un instante.
        """
        engine = self._engine
        if engine is None:
            return None
        if getattr(engine, 'last_reco_reason', None) is not None:
            return None
        last_key = getattr(engine, 'last_reco_key', None)
        if last_key is None:
            return None
        try:
            current_key = engine._state_key(frame.state)
        except Exception:  # noqa: BLE001 - sin firma no se reutiliza nada
            return None
        if current_key != last_key:
            return None
        previous = self._last_decision_analysis
        if previous is None or previous.prediction is None:
            return None
        elapsed = (datetime.now(timezone.utc).timestamp() - started) * 1000.0
        return replace(
            previous,
            capture_source=frame.source,
            captured_at=frame.captured_at,
            warnings=tuple(dict.fromkeys(
                tuple(previous.warnings) + tuple(frame.warnings))),
            elapsed_ms={'analysis': elapsed})

    def _drain_recorder_finalized(self) -> None:
        recorder = getattr(self._engine, 'rec', None)
        taker = getattr(recorder, 'take_finalized_hands', None)
        if taker is None:
            return
        self._finalized_hands.extend(
            _json_safe(hand) for hand in taker())

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
        if (len(hu.active_seats) != 2
                or hu.button_seat not in hu.active_seats
                or hu.contradictions):
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
                        reasons: list, warnings: list, *,
                        recorder_snapshot: Optional[RecorderSnapshot] = None
                        ) -> ParityAnalysis:
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
        elif self.config.parity_position_mode == 'hu_in_6max':
            reasons.append('position_mode_live_6max_situation_hu')
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
                    else ('none_live_6max_positions'
                          if self.config.parity_position_mode == 'hu_in_6max'
                          else 'none_diagnostic_live_default')),
                'position_mismatch': position_mismatch,
                'villain_range': snapshot.get('villain_range'),
                'reproducibility': snapshot.get('reproducibility'),
                'preflop_table_audit': snapshot.get('preflop_table_audit'),
                'model_evidence': snapshot.get('model_evidence'),
                'recorder_snapshot_fingerprint': (
                    recorder_snapshot.fingerprint
                    if recorder_snapshot is not None else None),
                'recorder_snapshot_sequence': (
                    recorder_snapshot.sequence
                    if recorder_snapshot is not None else None),
                'recorder_snapshot_sha256': hu.recorder_snapshot_sha256,
                'pot_read': (
                    recorder_snapshot.pot_read
                    if recorder_snapshot is not None else None),
                'pot_recorded': (
                    recorder_snapshot.pot_live_calculated
                    if recorder_snapshot is not None else None),
                'to_call_source': hu.provenance.get('to_call'),
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
                ('hu_sb_bb corrige deliberadamente el BTN/SB y el orden HU; '
                 'no es paridad exacta con live_default.'
                 if self.config.parity_position_mode == 'hu_sb_bb' else
                 'La recomendacion usa las posiciones y el orden 6-max de la '
                 'mesa; la situacion HU se define por los 2 jugadores activos.'
                 if self.config.parity_position_mode == 'hu_in_6max' else
                 'live_default es solo referencia diagnostica; no se persiste.'),
                'La recomendacion no se presenta como decision validada.',
                'La capa HU interpreta el RecorderSnapshot; el motor recibe '
                'el estado bruto original sin mutarlo.',
                'El recorder se ejecuto una sola vez; la llamada interna de '
                'step quedo suprimida y no reproceso el frame.',
            ),
            warnings=tuple(dict.fromkeys(warnings)),
            capture_source=frame.source,
            captured_at=frame.captured_at,
            elapsed_ms={'analysis': elapsed},
            recorder_snapshot=recorder_snapshot,
        )

    def _blocked_analysis(self, frame: CapturedFrame, hu: Optional[HUState],
                          reason: str, started: float, *,
                          reasons=None, warnings=None,
                          recorder_snapshot: Optional[RecorderSnapshot] = None
                          ) -> ParityAnalysis:
        elapsed = (datetime.now(timezone.utc).timestamp() - started) * 1000.0
        if hu is None:
            raw_state = (recorder_snapshot.as_dict()['raw_state']
                         if recorder_snapshot is not None else dict(frame.state))
            hu = HUState(
                status='unresolved', reason=reason,
                hero_seat=self.config.hero_seat,
                villain_seat=None, hero_position=None, villain_position=None,
                active_seats=(), street='preflop', hero_cards=(), board=(),
                pot=None, to_call=None, hero_stack=None, villain_stack=None,
                hero_bet=None, villain_bet=None, button_seat=None,
                uncertainty_reasons=tuple(reasons or ()),
                observed_fields=(), raw_state=raw_state,
                recorder_snapshot_sha256=(
                    recorder_snapshot.fingerprint
                    if recorder_snapshot is not None else None),
                interpretation_source=(
                    'recorder_snapshot' if recorder_snapshot is not None
                    else 'raw_state'),
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
            recorder_snapshot=recorder_snapshot,
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
        elif self.config.parity_position_mode == 'hu_in_6max':
            uncertainty.append('position_mode_live_6max_situation_hu')
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
                else ('none_live_6max_positions'
                      if self.config.parity_position_mode == 'hu_in_6max'
                      else 'none_diagnostic_live_default')),
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
            # En Fase 10.5 el modo diagnostico ignora estas rutas: siempre
            # quedan desactivadas para no persistir decisiones/artefactos.
            'live_decision_log_enabled': False,
            'shadow_logs_enabled': False,
            'recorder_diagnostic_mode': True,
            'auto_outcomes_enabled': False,
            'recorder_snapshot_fingerprint': hu.recorder_snapshot_sha256,
            'hu_interpretation_source': hu.interpretation_source,
            'hu_contradictions': list(hu.contradictions),
            'hu_provenance': dict(hu.provenance),
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
        if prediction.metadata.get('position_mode') not in (
                'hu_sb_bb', 'hu_in_6max'):
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
                if self.config.parity_position_mode not in (
                        'hu_sb_bb', 'hu_in_6max'):
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
                cleanup_ms = (time.perf_counter() - phase_started) * 1000.0
                total_ms = (time.perf_counter() - cycle_started) * 1000.0
                return PollEvent(
                    analysis=analysis, registration=registration,
                    elapsed_ms=total_ms,
                    phase_times_ms={
                        'capture_and_analysis': analysis_ms,
                        'prediction_persistence': persist_ms,
                        'post_capture_cleanup': cleanup_ms,
                        'total': total_ms,
                    })
            except Exception as exc:  # noqa: BLE001
                total_ms = (time.perf_counter() - cycle_started) * 1000.0
                return PollEvent(error=str(exc), elapsed_ms=total_ms)

    def _flush_post_capture_observations(self) -> None:
        """Descarta el buffer operacional sin registrar outcomes reales.

        En Fase 10.5 no se registran outcomes de manos reales automaticamente.
        El ledger solo recibe eventos por ``register_analysis``/``record_outcome``
        explicitos. Las finalizaciones se descartan de la cola operativa, no de
        los snapshots ni de la auditoria en memoria del recorder.
        """
        self._finalized_hands = []

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
        event = self.registry.register_outcome(outcome)
        self._pending.pop(prediction_id, None)
        # Un outcome explicito reconcilia tambien la prediccion de una
        # ejecucion anterior. ``_assert_restart_clear`` lo vuelve a verificar
        # contra el registro antes de capturar.
        self._startup_pending_ids.discard(prediction_id)
        return event

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
