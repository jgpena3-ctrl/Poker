"""Registro prospectivo HU aislado (Fase 5).

No se integra con live, serving, recorder ni pipeline de datos. Su funcion es
registrar evidencia con trazabilidad, preservando la separacion entre
prediccion y resultado posterior.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

SCHEMA_VERSION = 'hu_prospective_v1'
EVENT_PREDICTION = 'HU_PREDICTION'
EVENT_OUTCOME = 'HU_OUTCOME'

PREDICTION_FORBIDDEN_KEYS = {
    'observed_action', 'observed_result', 'showdown_cards',
    'final_pot', 'final_stacks', 'outcome_timestamp',
}

PROTECTED_DATA_DIRNAME = 'data'
PROTECTED_NAMES = {
    'hands_db.jsonl', 'hands_db.jsonl.bak', 'decisions.jsonl',
    'observations.json',
}


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('timestamp debe ser una cadena ISO-8601 no vacía')
    text = value.strip()
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError('timestamp ISO-8601 inválido: %r' % value) from exc


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('%s debe ser numérico' % name)
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('%s debe ser finito' % name)
    return value


def _nonnegative_number(value: Any, name: str) -> float:
    value = _finite_number(value, name)
    if value < 0:
        raise ValueError('%s no puede ser negativo' % name)
    return value


def _safe_storage_path(path: Any) -> Path:
    if not isinstance(path, (str, os.PathLike)):
        raise ValueError('storage_path debe ser una ruta')
    resolved = Path(path).expanduser().resolve()
    if resolved.is_dir():
        raise ValueError('storage_path no puede ser un directorio')
    project_root = Path(__file__).resolve().parents[1]
    protected_data_dir = (project_root / PROTECTED_DATA_DIRNAME).resolve()
    # Evita escribir en el dataset histórico o en artefactos existentes.
    if resolved.name in PROTECTED_NAMES:
        raise ValueError('storage_path apunta a un artefacto protegido')
    if resolved == protected_data_dir or protected_data_dir in resolved.parents:
        raise ValueError('storage_path no puede estar dentro de data/')
    if resolved.exists() and not resolved.is_file():
        raise ValueError('storage_path no es un archivo regular')
    return resolved


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=False, default=str)


def _canonical_hash(event: Mapping[str, Any]) -> str:
    payload = {k: v for k, v in event.items() if k != 'canonical_hash'}
    return hashlib.sha256(_canonical_json(payload).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class HUPrediction:
    prediction_id: str
    emitted_at: str
    hero_position: str
    canonical_status: str
    coverage_state: Optional[str] = None
    sequence_status: Optional[str] = None
    range_kind: Optional[str] = None
    range_source: Optional[str] = None
    range_provenance: Optional[Mapping[str, Any]] = None
    response_distribution: Optional[Mapping[str, Any]] = None
    equity: Optional[float] = None
    equity_scenario: Optional[str] = None
    equity_method: Optional[str] = None
    action_ev: Optional[Iterable[Mapping[str, Any]]] = None
    selected_action: Optional[str] = None
    provisional_selected_action: Optional[str] = None
    legal_actions: Optional[Iterable[str]] = None
    uncertainty_reasons: Optional[Iterable[str]] = None
    pot: Optional[float] = None
    to_call: Optional[float] = None
    hero_stack: Optional[float] = None
    villain_stack: Optional[float] = None
    hero_contribution_before: Optional[float] = None
    villain_contribution_before: Optional[float] = None
    board: Optional[Iterable[str]] = None
    hero_cards: Optional[Iterable[str]] = None
    prior_actions: Optional[Iterable[Any]] = None
    code_version: Optional[str] = None
    data_snapshot_id: Optional[str] = None
    assumptions: Optional[Iterable[str]] = None
    metadata: Optional[Mapping[str, Any]] = None

    def to_payload(self) -> Dict[str, Any]:
        payload = asdict(self)
        # Convierte iterables a listas JSON-serializables sin inferir valores.
        for key in ('action_ev', 'legal_actions', 'uncertainty_reasons',
                    'board', 'hero_cards', 'prior_actions', 'assumptions'):
            value = payload.get(key)
            if value is not None:
                payload[key] = list(value)
        if payload.get('range_provenance') is not None:
            payload['range_provenance'] = dict(payload['range_provenance'])
        if payload.get('response_distribution') is not None:
            payload['response_distribution'] = dict(
                payload['response_distribution'])
        if payload.get('metadata') is not None:
            payload['metadata'] = dict(payload['metadata'])
        return payload


@dataclass(frozen=True)
class HUOutcome:
    outcome_id: str
    prediction_id: str
    observed_at: str
    observed_action: Optional[str] = None
    new_information: Optional[Mapping[str, Any]] = None
    result: Optional[Mapping[str, Any]] = None
    exclusion_reason: Optional[str] = None
    notes: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        payload = asdict(self)
        if payload.get('new_information') is not None:
            payload['new_information'] = dict(payload['new_information'])
        if payload.get('result') is not None:
            payload['result'] = dict(payload['result'])
        return payload


def _coerce_prediction(prediction: Any) -> HUPrediction:
    if isinstance(prediction, HUPrediction):
        return prediction
    if isinstance(prediction, Mapping):
        return HUPrediction(**dict(prediction))
    raise TypeError('prediction debe ser HUPrediction o mapping')


def _coerce_outcome(outcome: Any) -> HUOutcome:
    if isinstance(outcome, HUOutcome):
        return outcome
    if isinstance(outcome, Mapping):
        return HUOutcome(**dict(outcome))
    raise TypeError('outcome debe ser HUOutcome o mapping')


def _contains_forbidden_keys(value: Any, forbidden: set) -> set:
    found: set = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in forbidden:
                found.add(key)
            found |= _contains_forbidden_keys(item, forbidden)
    elif isinstance(value, (list, tuple)):
        for item in value:
            found |= _contains_forbidden_keys(item, forbidden)
    return found


def _validate_prediction_payload(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload, Mapping):
        raise TypeError('payload de predicción debe ser mapping')
    forbidden = _contains_forbidden_keys(payload, PREDICTION_FORBIDDEN_KEYS)
    if forbidden:
        raise ValueError('la predicción contiene datos posteriores: %s'
                         % ', '.join(sorted(forbidden)))
    prediction_id = payload.get('prediction_id')
    if not isinstance(prediction_id, str) or not prediction_id.strip():
        raise ValueError('prediction_id debe ser una cadena no vacía')
    _parse_timestamp(payload.get('emitted_at'))
    hero_position = payload.get('hero_position')
    if hero_position is not None and (not isinstance(hero_position, str)
                                     or not hero_position.strip()):
        raise ValueError('hero_position inválido')
    canonical_status = payload.get('canonical_status')
    if canonical_status is not None and canonical_status not in (
            'resolved', 'unresolved', 'no_decision'):
        raise ValueError('canonical_status inválido')
    coverage_state = payload.get('coverage_state')
    if coverage_state is not None and coverage_state not in (
            'exact', 'alias', 'coverage_gap', 'impossible', 'unknown',
            'complete_exact', 'complete_with_alias', 'partial',
            'none_applicable', 'unresolved'):
        raise ValueError('coverage_state inválido')
    for field_name in ('pot', 'to_call', 'hero_stack', 'villain_stack',
                       'hero_contribution_before', 'villain_contribution_before'):
        value = payload.get(field_name)
        if value is not None:
            _nonnegative_number(value, field_name)
    equity = payload.get('equity')
    if equity is not None:
        equity = _finite_number(equity, 'equity')
        if not 0.0 <= equity <= 1.0:
            raise ValueError('equity debe estar en [0,1]')
    response_distribution = payload.get('response_distribution')
    if response_distribution is not None:
        if not isinstance(response_distribution, Mapping):
            raise ValueError('response_distribution debe ser mapping')
        total = 0.0
        for key, value in response_distribution.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError('clave de respuesta inválida')
            prob = _finite_number(value, 'response_distribution[%s]' % key)
            if not 0.0 <= prob <= 1.0:
                raise ValueError('probabilidad de respuesta fuera de [0,1]')
            total += prob
        if abs(total - 1.0) > 1e-9 and len(response_distribution) > 0:
            raise ValueError('response_distribution debe sumar 1')
    action_ev = payload.get('action_ev')
    if action_ev is not None:
        if not isinstance(action_ev, (list, tuple)):
            raise ValueError('action_ev debe ser lista o tupla')
        for item in action_ev:
            if not isinstance(item, Mapping):
                raise ValueError('cada EV debe ser mapping')
            ev = item.get('ev')
            if ev is not None:
                _finite_number(ev, 'action_ev.ev')
    range_kind = payload.get('range_kind')
    if range_kind is not None and range_kind not in (
            'observed', 'estimated', 'prior', 'statistics', 'unknown'):
        raise ValueError('range_kind inválido')
    if payload.get('range_source') is not None and not isinstance(
            payload.get('range_source'), str):
        raise ValueError('range_source debe ser cadena')
    if payload.get('range_provenance') is not None and not isinstance(
            payload.get('range_provenance'), Mapping):
        raise ValueError('range_provenance debe ser mapping')


def _validate_outcome_payload(payload: Mapping[str, Any],
                             prediction: Mapping[str, Any]) -> None:
    if not isinstance(payload, Mapping):
        raise TypeError('payload de resultado debe ser mapping')
    outcome_id = payload.get('outcome_id')
    if not isinstance(outcome_id, str) or not outcome_id.strip():
        raise ValueError('outcome_id debe ser una cadena no vacía')
    prediction_id = payload.get('prediction_id')
    if not isinstance(prediction_id, str) or not prediction_id.strip():
        raise ValueError('prediction_id debe ser una cadena no vacía')
    if prediction_id != prediction.get('prediction_id'):
        raise ValueError('outcome no referencia una predicción existente')
    observed_at = _parse_timestamp(payload.get('observed_at'))
    emitted_at = _parse_timestamp(prediction.get('emitted_at'))
    if observed_at < emitted_at:
        raise ValueError('observed_at no puede ser anterior a emitted_at')
    new_information = payload.get('new_information')
    if new_information is not None and not isinstance(new_information, Mapping):
        raise ValueError('new_information debe ser mapping')
    result = payload.get('result')
    if result is not None and not isinstance(result, Mapping):
        raise ValueError('result debe ser mapping')
    observed_action = payload.get('observed_action')
    if observed_action is not None and not isinstance(observed_action, str):
        raise ValueError('observed_action debe ser cadena o None')
    exclusion_reason = payload.get('exclusion_reason')
    if exclusion_reason is not None and not isinstance(exclusion_reason, str):
        raise ValueError('exclusion_reason debe ser cadena o None')


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    event_count: int
    verified_count: int
    issues: Tuple[str, ...]
    truncated: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            'ok': self.ok,
            'event_count': self.event_count,
            'verified_count': self.verified_count,
            'issues': list(self.issues),
            'truncated': self.truncated,
        }


@dataclass(frozen=True)
class BackupResult:
    backup_path: str
    sha256: str
    event_count: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            'backup_path': self.backup_path,
            'sha256': self.sha256,
            'event_count': self.event_count,
        }


class ProspectiveHURegistry:
    """Registro append-only aislado para evidencia prospectiva HU."""

    def __init__(self, storage_path: Any):
        self.storage_path = _safe_storage_path(storage_path)

    @property
    def lock_path(self) -> Path:
        return self.storage_path.with_name(self.storage_path.name + '.lock')

    @contextmanager
    def _writer_lock(self):
        lock_path = self.lock_path
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        # Intento atomico de creacion. Si existe, se considera bloqueo activo.
        try:
            fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            # Recuperacion conservadora de bloqueo obsoleto: solo si el PID
            # registrado no esta vivo. No se asume portabilidad perfecta.
            try:
                text = lock_path.read_text(encoding='utf-8').strip()
                pid = int(text) if text else None
            except (OSError, ValueError):
                pid = None
            if pid is not None:
                try:
                    os.kill(pid, 0)
                    alive = True
                except (OSError, ProcessLookupError, ValueError):
                    alive = False
                if not alive:
                    try:
                        lock_path.unlink()
                    except OSError:
                        pass
                    try:
                        fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    except FileExistsError:
                        raise RuntimeError('no se pudo adquirir el bloqueo de escritura')
                else:
                    raise RuntimeError('ya existe un escritor activo para este registro')
            else:
                raise RuntimeError('ya existe un escritor activo para este registro')
        os.write(fd, str(os.getpid()).encode('ascii'))
        os.close(fd)
        try:
            yield
        finally:
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass

    def _read_events(self) -> List[Dict[str, Any]]:
        if not self.storage_path.exists():
            return []
        events: List[Dict[str, Any]] = []
        with self.storage_path.open('r', encoding='utf-8') as f:
            for line_number, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError('JSON inválido en línea %d' % line_number) from exc
                if not isinstance(event, dict):
                    raise ValueError('evento no es un objeto JSON en línea %d'
                                     % line_number)
                events.append(event)
        return events

    def _existing_ids(self) -> Tuple[set, set]:
        event_ids = set()
        prediction_ids = set()
        for event in self._read_events():
            event_ids.add(event.get('event_id'))
            payload = event.get('payload', {})
            if event.get('event_type') == EVENT_PREDICTION:
                prediction_ids.add(payload.get('prediction_id'))
        return event_ids, prediction_ids

    def _find_prediction(self, prediction_id: str) -> Optional[Dict[str, Any]]:
        for event in self._read_events():
            if event.get('event_type') == EVENT_PREDICTION:
                payload = event.get('payload', {})
                if payload.get('prediction_id') == prediction_id:
                    return event
        return None

    def _append_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        event = dict(event)
        event['canonical_hash'] = _canonical_hash(event)
        line = _canonical_json(event) + '\n'
        # Validar antes de tocar el archivo.
        json.loads(line)
        with self.storage_path.open('a', encoding='utf-8') as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        return event

    def register_prediction(self, prediction: Any) -> Dict[str, Any]:
        with self._writer_lock():
            pred = _coerce_prediction(prediction)
            payload = pred.to_payload()
            _validate_prediction_payload(payload)
            event_ids, prediction_ids = self._existing_ids()
            event_id = payload['prediction_id']
            if event_id in event_ids:
                raise ValueError('event_id duplicado: %s' % event_id)
            if payload['prediction_id'] in prediction_ids:
                raise ValueError('prediction_id duplicado: %s'
                                 % payload['prediction_id'])
            event = {
                'schema_version': SCHEMA_VERSION,
                'event_type': EVENT_PREDICTION,
                'event_id': event_id,
                'created_at': payload['emitted_at'],
                'payload': payload,
            }
            return self._append_event(event)

    def register_outcome(self, outcome: Any) -> Dict[str, Any]:
        with self._writer_lock():
            out = _coerce_outcome(outcome)
            payload = out.to_payload()
            prediction_event = self._find_prediction(payload['prediction_id'])
            if prediction_event is None:
                raise ValueError('la predicción referenciada no existe: %s'
                                 % payload['prediction_id'])
            _validate_outcome_payload(payload, prediction_event['payload'])
            event_ids, _ = self._existing_ids()
            event_id = payload['outcome_id']
            if event_id in event_ids:
                raise ValueError('event_id duplicado: %s' % event_id)
            event = {
                'schema_version': SCHEMA_VERSION,
                'event_type': EVENT_OUTCOME,
                'event_id': event_id,
                'created_at': payload['observed_at'],
                'payload': payload,
            }
            return self._append_event(event)

    def read_events(self) -> List[Dict[str, Any]]:
        return self._read_events()

    def list_predictions(self) -> List[Dict[str, Any]]:
        return [e for e in self._read_events()
                if e.get('event_type') == EVENT_PREDICTION]

    def list_outcomes(self) -> List[Dict[str, Any]]:
        return [e for e in self._read_events()
                if e.get('event_type') == EVENT_OUTCOME]

    def get_prediction(self, prediction_id: str) -> Optional[Dict[str, Any]]:
        return self._find_prediction(prediction_id)

    def get_outcome(self, outcome_id: str) -> Optional[Dict[str, Any]]:
        for event in self._read_events():
            if (event.get('event_type') == EVENT_OUTCOME
                    and event.get('payload', {}).get('outcome_id') == outcome_id):
                return event
        return None

    def verify_integrity(self) -> VerificationResult:
        issues: List[str] = []
        events: List[Dict[str, Any]] = []
        truncated = False
        if not self.storage_path.exists():
            return VerificationResult(ok=True, event_count=0,
                                     verified_count=0, issues=())
        try:
            with self.storage_path.open('r', encoding='utf-8') as f:
                for line_number, raw in enumerate(f, 1):
                    if raw == '' :
                        continue
                    if not raw.endswith('\n'):
                        truncated = True
                        issues.append('línea %d truncada' % line_number)
                        # Intentar parsear lo disponible igualmente.
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        issues.append('JSON inválido en línea %d' % line_number)
                        continue
                    if not isinstance(event, dict):
                        issues.append('evento no es objeto en línea %d'
                                      % line_number)
                        continue
                    if event.get('schema_version') != SCHEMA_VERSION:
                        issues.append('versión no soportada en línea %d' % line_number)
                    if 'canonical_hash' not in event:
                        issues.append('falta canonical_hash en línea %d'
                                      % line_number)
                    else:
                        try:
                            recomputed = _canonical_hash(event)
                        except Exception:
                            recomputed = None
                        if recomputed is not None and recomputed != event.get('canonical_hash'):
                            issues.append('hash incorrecto en línea %d' % line_number)
                    events.append(event)
        except OSError as exc:
            issues.append('error de lectura: %s' % exc)
            return VerificationResult(ok=False, event_count=0,
                                     verified_count=0, issues=tuple(issues),
                                     truncated=truncated)

        event_ids = []
        prediction_ids = []
        prediction_events = {}
        for index, event in enumerate(events, 1):
            event_id = event.get('event_id')
            event_ids.append(event_id)
            payload = event.get('payload', {})
            if not isinstance(payload, dict):
                issues.append('payload inválido en evento %d' % index)
                continue
            if event.get('event_type') == EVENT_PREDICTION:
                pid = payload.get('prediction_id')
                prediction_ids.append(pid)
                prediction_events[pid] = event
            elif event.get('event_type') == EVENT_OUTCOME:
                pid = payload.get('prediction_id')
                if pid not in prediction_events:
                    issues.append('referencia inexistente en evento %d' % index)
                else:
                    try:
                        _validate_outcome_payload(payload, prediction_events[pid]['payload'])
                    except ValueError as exc:
                        issues.append('resultado inválido en evento %d: %s'
                                      % (index, exc))
            else:
                issues.append('tipo de evento desconocido en línea %d' % index)

        # Duplicados.
        seen_event_ids = set()
        for event_id in event_ids:
            if event_id in seen_event_ids:
                issues.append('event_id duplicado: %s' % event_id)
            seen_event_ids.add(event_id)
        seen_prediction_ids = set()
        for pid in prediction_ids:
            if pid in seen_prediction_ids:
                issues.append('prediction_id duplicado: %s' % pid)
            seen_prediction_ids.add(pid)

        # Orden temporal.
        previous_time = None
        for index, event in enumerate(events, 1):
            created_at = event.get('created_at')
            try:
                current_time = _parse_timestamp(created_at)
            except ValueError:
                issues.append('timestamp inválido en evento %d' % index)
                continue
            if previous_time is not None and current_time < previous_time:
                issues.append('secuencia temporal inválida en evento %d' % index)
            previous_time = current_time

        verified_count = len(events) - len(issues) if not issues else max(
            0, len(events) - len(issues))
        # Una verificacion util reporta eventos parseados; los issues no se
        # convierten en conteo negativo.
        verified_count = len(events)
        ok = len(issues) == 0 and not truncated
        return VerificationResult(ok=ok, event_count=len(events),
                                 verified_count=verified_count,
                                 issues=tuple(issues), truncated=truncated)

    def verify(self) -> VerificationResult:
        return self.verify_integrity()

    def create_backup(self, backup_path: Any) -> BackupResult:
        backup_path = _safe_storage_path(backup_path)
        if backup_path == self.storage_path:
            raise ValueError('la copia de seguridad debe estar en otra ubicacion')
        if backup_path.exists():
            raise ValueError('la copia de seguridad ya existe')
        result = self.verify_integrity()
        if not result.ok:
            raise ValueError('no se puede respaldar un registro no íntegro')
        if not self.storage_path.exists():
            raise ValueError('no existe registro para respaldar')
        # Copia atomica a destino temporal y luego rename.
        temp_path = backup_path.with_name(backup_path.name + '.tmp')
        try:
            with self.storage_path.open('rb') as src, temp_path.open('wb') as dst:
                shutil.copyfileobj(src, dst)
                dst.flush()
                os.fsync(dst.fileno())
            os.replace(temp_path, backup_path)
        finally:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
        data = backup_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        sidecar = backup_path.with_name(backup_path.name + '.sha256')
        sidecar.write_text(digest + '\n', encoding='utf-8')
        return BackupResult(backup_path=str(backup_path), sha256=digest,
                            event_count=result.event_count)

    def verify_backup(self, backup_path: Any) -> VerificationResult:
        backup_path = _safe_storage_path(backup_path)
        if not backup_path.exists():
            raise ValueError('la copia de seguridad no existe')
        sidecar = backup_path.with_name(backup_path.name + '.sha256')
        if sidecar.exists():
            expected = sidecar.read_text(encoding='utf-8').strip()
            actual = hashlib.sha256(backup_path.read_bytes()).hexdigest()
            if expected != actual:
                return VerificationResult(ok=False, event_count=0,
                                         verified_count=0,
                                         issues=('hash de respaldo incorrecto',))
        # Reutiliza la verificacion de eventos sobre la copia.
        backup_registry = ProspectiveHURegistry(backup_path)
        return backup_registry.verify_integrity()

    def restore_backup(self, backup_path: Any,
                       destination: Optional[Any] = None,
                       overwrite: bool = False) -> Path:
        backup_path = _safe_storage_path(backup_path)
        backup_result = self.verify_backup(backup_path)
        if not backup_result.ok:
            raise ValueError('la copia de seguridad no es íntegra')
        if destination is None:
            destination = self.storage_path
        destination = _safe_storage_path(destination)
        if destination.exists() and not overwrite:
            raise ValueError('el destino ya existe; use overwrite=True')
        temp_path = destination.with_name(destination.name + '.restore.tmp')
        try:
            with backup_path.open('rb') as src, temp_path.open('wb') as dst:
                shutil.copyfileobj(src, dst)
                dst.flush()
                os.fsync(dst.fileno())
            if destination.exists():
                # Conserva el original con sufijo .pre_restore por seguridad.
                backup_original = destination.with_name(
                    destination.name + '.pre_restore')
                if backup_original.exists():
                    raise ValueError('ya existe una copia .pre_restore')
                os.replace(destination, backup_original)
            os.replace(temp_path, destination)
        finally:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
        restored_registry = ProspectiveHURegistry(destination)
        restored_result = restored_registry.verify_integrity()
        if not restored_result.ok:
            raise ValueError('el registro restaurado no es íntegro')
        return destination

    def restore_from_backup(self, backup_path: Any,
                            destination: Optional[Any] = None,
                            overwrite: bool = False) -> Path:
        return self.restore_backup(backup_path, destination, overwrite)

    # Alias de compatibilidad para tests o consumidores.
    def add_prediction(self, prediction: Any) -> Dict[str, Any]:
        return self.register_prediction(prediction)

    def add_outcome(self, outcome: Any) -> Dict[str, Any]:
        return self.register_outcome(outcome)

    def append_prediction(self, prediction: Any) -> Dict[str, Any]:
        return self.register_prediction(prediction)

    def append_outcome(self, outcome: Any) -> Dict[str, Any]:
        return self.register_outcome(outcome)

    def record_prediction(self, prediction: Any) -> Dict[str, Any]:
        return self.register_prediction(prediction)

    def record_outcome(self, outcome: Any) -> Dict[str, Any]:
        return self.register_outcome(outcome)


# Alias de compatibilidad para posibles nombres esperados por tests.
HUProspectiveRegistry = ProspectiveHURegistry
HUProspectiveStore = ProspectiveHURegistry
ProspectiveHUStore = ProspectiveHURegistry