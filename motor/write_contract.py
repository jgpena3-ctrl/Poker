# -*- coding: utf-8 -*-
"""F0.2: contrato de integridad para escrituras canónicas.

Este módulo no abre archivos, no crea mutex, no escribe journal y no toca
`data/`. Define el vocabulario, las rutas canónicas y las transiciones que
F1/F2 deben implementar, para que la implementación no invente estados ni
acepte evidencia incompleta.

Reglas que el contrato fija:

- La exclusión es un mutex de Windows con nombre `Global\\Poker.HandsDB.v1`.
  No hay fallback a lockfile ni a bloqueo de biblioteca. Si el mutex no se
  puede crear o el timeout vence, se aborta de forma visible.
- `WAIT_ABANDONED` se adquiere, pero antes de escribir se ejecuta la
  recuperación. No se ignora.
- Los lectores no bloquean la base: leen una instantánea verificada bajo el
  mismo mutex exclusivo. Si la base, el manifiesto o la ventana no coinciden,
  se aborta.
- Un journal corrupto, truncado, con evidencia no ligada al plan o con un
  tercer hash se pone en cuarentena. No se restaura automáticamente.
- Los pins son código: se proponen para revisión, no se actualizan en runtime.
- Ninguna ausencia se convierte en cero ni en una evidencia válida.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

CONTRACT_VERSION = 'F0.2 (2026-11-12)'
ROOT = Path(__file__).resolve().parents[1]

TARGET_DB = 'data/hands_db.jsonl'
TARGET_MANIFEST = 'data/calibration_window.json'
TARGET_PROFILE_RANGES = 'data/profile_ranges.json'
TARGET_POSTFLOP_RANGES = 'data/postflop_ranges.json'
TARGET_PREFLOP_STATS = 'data/preflop_stats.json'
TARGET_PLAYER_STATS = 'data/player_stats.json'
TARGET_PROFILES = 'data/profiles.json'
TARGET_BEHAVIOR = 'data/behavior.json'
TARGET_BEHAVIOR_PROBS = 'data/behavior_probs.json'
TARGET_OBSERVATIONS = 'data/observations.json'

TARGET_MODEL_FILES = (TARGET_PROFILE_RANGES, TARGET_POSTFLOP_RANGES)
TARGET_DERIVED_FILES = (
    TARGET_PROFILE_RANGES,
    TARGET_POSTFLOP_RANGES,
    TARGET_PREFLOP_STATS,
    TARGET_PLAYER_STATS,
    TARGET_PROFILES,
    TARGET_BEHAVIOR,
    TARGET_BEHAVIOR_PROBS,
    TARGET_OBSERVATIONS,
)

PINS_SYMBOLS = ('HANDS_DB_SHA256', 'HANDS_DB_COMMIT', 'HANDS_DB_LINEAS')
PINS_SOURCE_PATHS = ('motor/learn.py',)
PINS_RUNTIME_UPDATE_ALLOWED = False

LOCK_MECHANISM = 'windows_named_mutex'
LOCK_NAME = r'Global\Poker.HandsDB.v1'
LOCK_FALLBACKS_ALLOWED = False
LOCK_MULTI_HOST_ALLOWED = False
LOCK_WAIT_ABANDONED_POLICY = 'recover_then_write'
LOCK_FAILURE_POLICY = 'abort_visible'
LOCK_TIMEOUT_SECONDS = 30.0
LOCK_ACL_REQUIRED = True
LOCK_SID_REQUIRED = True
READER_POLICY = 'verified_snapshot_under_exclusive_mutex'
JOURNAL_RECOVERY_POLICY = 'quarantine_no_auto_restore'

PREPARED = 'prepared'
PREIMAGE_VERIFIED = 'preimage_verified'
CAS_CONFLICT = 'cas_conflict'
BACKUP_VERIFIED = 'backup_verified'
TEMP_VERIFIED = 'temp_verified'
REPLACED = 'replaced'
POST_VERIFIED = 'post_verified'
MANIFEST_PENDING = 'manifest_pending'
MANIFEST_VERIFIED = 'manifest_verified'
PINS_PROPOSED = 'pins_proposed'
COMMITTED = 'committed'
ABORTED = 'aborted'
FAILED = 'failed'
QUARANTINED = 'quarantined'

SUCCESS_STATES = (COMMITTED,)
TERMINAL_STATES = (COMMITTED, CAS_CONFLICT, ABORTED, FAILED, QUARANTINED)
JOURNAL_STATES = (
    PREPARED,
    PREIMAGE_VERIFIED,
    CAS_CONFLICT,
    BACKUP_VERIFIED,
    TEMP_VERIFIED,
    REPLACED,
    POST_VERIFIED,
    MANIFEST_PENDING,
    MANIFEST_VERIFIED,
    PINS_PROPOSED,
    COMMITTED,
    ABORTED,
    FAILED,
    QUARANTINED,
)

TRANSITIONS: Mapping[str, Tuple[str, ...]] = MappingProxyType({
    PREPARED: (PREIMAGE_VERIFIED, CAS_CONFLICT, ABORTED, FAILED, QUARANTINED),
    PREIMAGE_VERIFIED: (BACKUP_VERIFIED, ABORTED, FAILED, QUARANTINED),
    CAS_CONFLICT: (),
    BACKUP_VERIFIED: (TEMP_VERIFIED, ABORTED, FAILED, QUARANTINED),
    TEMP_VERIFIED: (REPLACED, ABORTED, FAILED, QUARANTINED),
    REPLACED: (POST_VERIFIED, QUARANTINED),
    POST_VERIFIED: (MANIFEST_PENDING, QUARANTINED),
    MANIFEST_PENDING: (MANIFEST_VERIFIED, QUARANTINED),
    MANIFEST_VERIFIED: (PINS_PROPOSED, QUARANTINED),
    PINS_PROPOSED: (COMMITTED, QUARANTINED),
    COMMITTED: (),
    ABORTED: (),
    FAILED: (),
    QUARANTINED: (),
})

APPEND = 'append'
REWRITE = 'rewrite'
SNAPSHOT = 'snapshot'
WRITE_OPERATIONS = (APPEND, REWRITE, SNAPSHOT)
SNAPSHOT_ROOT = 'data/_snapshot_f0'
BACKUP_ROOT = 'data/_backup'
BACKUP_ROOT_PREFIX = BACKUP_ROOT
BACKUP_DISPOSITIONS = ('created', 'reused_same_txn')

TARGET_CATEGORY_BASE = 'base'
TARGET_CATEGORY_MANIFEST = 'manifest'
TARGET_CATEGORY_MODEL = 'model'
TARGET_CATEGORY_DERIVED = 'derived'


@dataclass(frozen=True)
class TargetPolicy:
    category: str
    operations: Tuple[str, ...]
    requires_lock: bool
    requires_cas: bool
    requires_backup: bool
    requires_manifest_verification: bool
    requires_pins_proposal: bool


TARGET_POLICIES: Mapping[str, TargetPolicy] = MappingProxyType({
    TARGET_DB: TargetPolicy(
        TARGET_CATEGORY_BASE,
        (APPEND, REWRITE),
        True, True, True, True, True,
    ),
    TARGET_MANIFEST: TargetPolicy(
        TARGET_CATEGORY_MANIFEST,
        (REWRITE,),
        True, True, True, True, False,
    ),
    TARGET_PROFILE_RANGES: TargetPolicy(
        TARGET_CATEGORY_MODEL,
        (REWRITE,),
        True, True, True, True, False,
    ),
    TARGET_POSTFLOP_RANGES: TargetPolicy(
        TARGET_CATEGORY_MODEL,
        (REWRITE,),
        True, True, True, True, False,
    ),
    TARGET_PREFLOP_STATS: TargetPolicy(
        TARGET_CATEGORY_DERIVED,
        (REWRITE,),
        True, True, True, True, False,
    ),
    TARGET_PLAYER_STATS: TargetPolicy(
        TARGET_CATEGORY_DERIVED,
        (REWRITE,),
        True, True, True, True, False,
    ),
    TARGET_PROFILES: TargetPolicy(
        TARGET_CATEGORY_DERIVED,
        (REWRITE,),
        True, True, True, True, False,
    ),
    TARGET_BEHAVIOR: TargetPolicy(
        TARGET_CATEGORY_DERIVED,
        (REWRITE,),
        True, True, True, True, False,
    ),
    TARGET_BEHAVIOR_PROBS: TargetPolicy(
        TARGET_CATEGORY_DERIVED,
        (REWRITE,),
        True, True, True, True, False,
    ),
    TARGET_OBSERVATIONS: TargetPolicy(
        TARGET_CATEGORY_DERIVED,
        (REWRITE,),
        True, True, True, True, False,
    ),
})

REQUIRED_EVIDENCE: Mapping[str, Tuple[str, ...]] = MappingProxyType({
    PREPARED: (
        'txn_id', 'writer', 'target_path', 'operation',
        'expected_pre_sha256', 'expected_pre_lines', 'expected_pre_bytes',
        'candidate_sha256', 'candidate_lines', 'candidate_bytes',
        'writer_declaration_fingerprint',
        'lock_policy_fingerprint', 'planned_at',
    ),
    PREIMAGE_VERIFIED: (
        'observed_pre_sha256', 'observed_pre_lines', 'observed_pre_bytes',
    ),
    CAS_CONFLICT: (
        'observed_pre_sha256', 'observed_pre_lines', 'observed_pre_bytes',
        'cas_conflict_reason', 'cas_conflict_at',
    ),
    BACKUP_VERIFIED: (
        'backup_path', 'backup_sha256', 'backup_bytes', 'backup_txn_id',
        'backup_disposition',
    ),
    TEMP_VERIFIED: ('temp_path', 'temp_sha256', 'temp_lines', 'temp_bytes'),
    REPLACED: ('replaced_at', 'operation_verified'),
    POST_VERIFIED: ('post_sha256', 'post_lines', 'post_bytes'),
    MANIFEST_PENDING: ('manifest_pending_at',),
    MANIFEST_VERIFIED: (),
    PINS_PROPOSED: ('pins_applied',),
    COMMITTED: ('committed_at',),
    ABORTED: ('abort_reason',),
    FAILED: ('failure_reason',),
    QUARANTINED: ('quarantine_reason',),
})

PLAN_OWNED_EVIDENCE = frozenset((
    'txn_id', 'writer', 'target_path', 'operation',
    'expected_pre_sha256', 'expected_pre_lines', 'expected_pre_bytes',
    'candidate_sha256', 'candidate_lines', 'candidate_bytes',
    'manifest_required', 'pins_required', 'writer_declaration_fingerprint',
    'lock_policy_fingerprint',
    'manifest_path', 'manifest_expected_sha256', 'manifest_candidate_sha256',
    'pins_path', 'pins_expected_sha256', 'snapshot_of',
))

EVIDENCE_KEYS = frozenset(
    {key for keys in REQUIRED_EVIDENCE.values() for key in keys}
    | {
        'planned_at',
        'manifest_sha256', 'manifest_observed_pre_sha256',
        'manifest_verified', 'manifest_skipped_reason',
        'pins_proposed_sha256', 'pins_symbols', 'pins_proposed_values',
        'pins_source_sha256', 'pins_skipped_reason',
        'operation_verified', 'preimage_prefix_verified',
        'append_boundary_verified', 'rewrite_complete_verified',
        'snapshot_verified', 'canonical_target_unchanged',
    }
)

JOURNAL_SCHEMA_VERSION = 2
JOURNAL_HASH_FIELDS = (
    'previous_sha256', 'record_sha256', 'evidence_sha256')
JOURNAL_GENESIS_SHA256 = '0' * 64
JOURNAL_TRUNCATION_POLICY = 'quarantine'
JOURNAL_CORRUPTION_POLICY = 'quarantine'
JOURNAL_THIRD_HASH_POLICY = 'quarantine'
JOURNAL_PLAN_BINDING_POLICY = 'plan_fingerprint_required'
JOURNAL_EVIDENCE_BINDING_POLICY = 'state_evidence_and_sha256_required'
JOURNAL_RAW_JSON_SUPPORTED = False
JOURNAL_JSON_PARSER_REQUIRED = True
JOURNAL_JSON_DUPLICATE_KEYS_POLICY = 'reject_with_object_pairs_hook'
RECOVERY_ACTION_BEFORE_REPLACE = ABORTED
RECOVERY_ACTION_AFTER_REPLACE = QUARANTINED

TXN_ID_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
COMMIT_PATTERN = re.compile(r'^[0-9a-fA-F]{7,64}$')


class WriteContractError(ValueError):
    """El contrato no se cumple; la escritura no puede continuar."""


class CasConflict(WriteContractError):
    """La preimagen observada no coincide y la transacción queda terminal."""

    def __init__(self, message: str, record: Optional['TransactionRecord'] = None):
        super().__init__(message)
        self.record = record


def _nonempty(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WriteContractError('%s debe ser una cadena no vacía' % field_name)
    return value.strip()


def _sha256(value: Any, field_name: str) -> str:
    value = _nonempty(value, field_name)
    if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise WriteContractError('%s debe ser un SHA-256 hex de 64 caracteres'
                                 % field_name)
    return value


def _nonnegative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise WriteContractError('%s debe ser un entero >= 0' % field_name)
    return value


def _lines(value: Any, field_name: str) -> int:
    return _nonnegative_int(value, field_name)


def _bytes(value: Any, field_name: str) -> int:
    return _nonnegative_int(value, field_name)


def _flag(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise WriteContractError('%s debe ser booleano' % field_name)
    return value


def _timestamp(value: Any, field_name: str) -> str:
    text = _nonempty(value, field_name)
    normalized = text[:-1] + '+00:00' if text.endswith('Z') else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise WriteContractError('%s debe ser ISO-8601' % field_name)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WriteContractError('%s debe incluir zona horaria' % field_name)
    return text


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path_within_root(value: Any, field_name: str) -> str:
    text = _nonempty(value, field_name)
    if '\x00' in text:
        raise WriteContractError('%s contiene NUL' % field_name)
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    real = Path(os.path.realpath(str(candidate)))
    rel = os.path.relpath(str(real), str(ROOT)).replace(os.sep, '/')
    if rel == '.' or rel == '..' or rel.startswith('../'):
        raise WriteContractError('%s queda fuera del repositorio' % field_name)
    return rel


def canonical_path(value: Any, field_name: str = 'ruta') -> str:
    """Devuelve la ruta relativa canónica, resolviendo aliases y symlinks."""
    return _path_within_root(value, field_name)


def _require_canonical_path(value: Any, field_name: str) -> str:
    text = _nonempty(value, field_name)
    if '\\' in text:
        raise WriteContractError('%s debe usar separadores /' % field_name)
    canonical = _path_within_root(text, field_name)
    if canonical != text:
        raise WriteContractError('%s no es una ruta canónica: %s -> %s'
                                 % (field_name, text, canonical))
    return canonical


def _path_key(value: Any, field_name: str = 'ruta') -> str:
    return os.path.normcase(canonical_path(value, field_name))


def _same_path(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    return _path_key(left) == _path_key(right)


def _target_policy(path: Any) -> TargetPolicy:
    canonical = _require_canonical_path(path, 'target_path')
    try:
        return TARGET_POLICIES[canonical]
    except KeyError:
        raise WriteContractError('target_path no declarado: %s' % canonical)


def _freeze_value(value: Any, field_name: str = 'valor') -> Any:
    if isinstance(value, Mapping):
        frozen = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise WriteContractError(
                    '%s contiene una clave no textual o vacía' % field_name)
            frozen[key] = _freeze_value(item, '%s.%s' % (field_name, key))
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item, field_name) for item in value)
    if isinstance(value, (set, frozenset)):
        try:
            return frozenset(_freeze_value(item, field_name) for item in value)
        except TypeError:
            raise WriteContractError(
                '%s contiene un conjunto no inmutable' % field_name)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WriteContractError('%s contiene un número no finito'
                                     % field_name)
        return value
    if isinstance(value, (str, int, bool, type(None))):
        return value
    raise WriteContractError('%s contiene un tipo no permitido: %s'
                             % (field_name, type(value).__name__))


def _to_jsonable(value: Any, field_name: str = 'valor') -> Any:
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise WriteContractError(
                    '%s contiene una clave no textual o vacía' % field_name)
            result[key] = _to_jsonable(item, '%s.%s' % (field_name, key))
        return result
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item, field_name) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_to_jsonable(item, field_name) for item in value]
        return sorted(items, key=lambda item: json.dumps(
            item, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
            allow_nan=False))
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WriteContractError('%s contiene un número no finito'
                                     % field_name)
        return value
    if isinstance(value, (str, int, bool, type(None))):
        return value
    raise WriteContractError('%s contiene un tipo no serializable: %s'
                             % (field_name, type(value).__name__))


def _canonical_bytes(value: Any, field_name: str) -> bytes:
    payload = _to_jsonable(value, field_name)
    try:
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError) as exc:
        raise WriteContractError('%s no serializable: %s' % (field_name, exc))
    return raw


def _canonical_sha256(value: Any, field_name: str = 'valor') -> str:
    return hashlib.sha256(_canonical_bytes(value, field_name)).hexdigest()


def canonical_sha256(value: Any, field_name: str = 'valor') -> str:
    """SHA-256 del JSON canónico; rechaza NaN, Infinity y claves no textuales."""
    return _canonical_sha256(value, field_name)


def _evidence_mapping(evidence: Optional[Mapping[str, Any]]
                      ) -> Mapping[str, Any]:
    if evidence is None:
        return MappingProxyType({})
    if not isinstance(evidence, Mapping):
        raise WriteContractError('evidence debe ser un mapping')
    return _freeze_value(evidence, 'evidence')


def _assert_immutable(value: Any, field_name: str = 'evidence') -> None:
    if isinstance(value, Mapping):
        if not isinstance(value, MappingProxyType):
            raise WriteContractError('%s debe ser inmutable' % field_name)
        for key, item in value.items():
            _assert_immutable(item, '%s.%s' % (field_name, key))
        return
    if isinstance(value, tuple):
        for item in value:
            _assert_immutable(item, field_name)
        return
    if isinstance(value, frozenset):
        for item in value:
            _assert_immutable(item, field_name)
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WriteContractError('%s contiene un número no finito'
                                     % field_name)
        return
    if isinstance(value, (str, int, bool, type(None))):
        return
    raise WriteContractError('%s contiene un tipo mutable o no permitido'
                             % field_name)


def _require(evidence: Mapping[str, Any], names: Tuple[str, ...]) -> None:
    missing = [n for n in names if n not in evidence or evidence[n] is None]
    if missing:
        raise WriteContractError('falta evidencia: %s' % ', '.join(missing))


def _require_text(evidence: Mapping[str, Any], name: str) -> str:
    return _nonempty(evidence.get(name), name)


def _check_sha(evidence: Mapping[str, Any], name: str,
               expected: str) -> None:
    got = _sha256(evidence.get(name), name)
    if got != expected:
        raise WriteContractError('%s no coincide con el hash esperado'
                                 % name)


def _check_lines(evidence: Mapping[str, Any], name: str,
                 expected: int) -> None:
    got = _lines(evidence.get(name), name)
    if got != expected:
        raise WriteContractError('%s no coincide con las líneas esperadas'
                                 % name)


def _check_bytes(evidence: Mapping[str, Any], name: str,
                 expected: int) -> None:
    got = _bytes(evidence.get(name), name)
    if got != expected:
        raise WriteContractError('%s no coincide con los bytes esperados'
                                 % name)


def _check_cas_sha(evidence: Mapping[str, Any], name: str,
                   expected: str) -> None:
    got = _sha256(evidence.get(name), name)
    if got != expected:
        raise CasConflict('%s no coincide: CAS rechaza la preimagen' % name)


def _check_cas_lines(evidence: Mapping[str, Any], name: str,
                     expected: int) -> None:
    got = _lines(evidence.get(name), name)
    if got != expected:
        raise CasConflict('%s no coincide: CAS rechaza la preimagen' % name)


def _check_cas_bytes(evidence: Mapping[str, Any], name: str,
                     expected: int) -> None:
    got = _bytes(evidence.get(name), name)
    if got != expected:
        raise CasConflict('%s no coincide: CAS rechaza la preimagen' % name)


@dataclass(frozen=True)
class LockPolicy:
    """Parámetros ejecutables que F1 debe respetar sin fallback."""

    mechanism: str = LOCK_MECHANISM
    name: str = LOCK_NAME
    timeout_seconds: float = LOCK_TIMEOUT_SECONDS
    fallbacks_allowed: bool = LOCK_FALLBACKS_ALLOWED
    multi_host_allowed: bool = LOCK_MULTI_HOST_ALLOWED
    wait_abandoned_policy: str = LOCK_WAIT_ABANDONED_POLICY
    failure_policy: str = LOCK_FAILURE_POLICY
    acl_required: bool = LOCK_ACL_REQUIRED
    sid_required: bool = LOCK_SID_REQUIRED

    def as_dict(self) -> Dict[str, Any]:
        return {
            'mechanism': self.mechanism,
            'name': self.name,
            'timeout_seconds': self.timeout_seconds,
            'fallbacks_allowed': self.fallbacks_allowed,
            'multi_host_allowed': self.multi_host_allowed,
            'wait_abandoned_policy': self.wait_abandoned_policy,
            'failure_policy': self.failure_policy,
            'acl_required': self.acl_required,
            'sid_required': self.sid_required,
        }

    def validate(self) -> 'LockPolicy':
        if self.mechanism != LOCK_MECHANISM:
            raise WriteContractError('mecanismo de mutex no permitido')
        if self.name != LOCK_NAME:
            raise WriteContractError('nombre de mutex no permitido')
        if isinstance(self.timeout_seconds, bool) or not isinstance(
                self.timeout_seconds, (int, float)) or \
                not math.isfinite(self.timeout_seconds) or \
                self.timeout_seconds <= 0:
            raise WriteContractError(
                'timeout_seconds debe ser un número finito > 0')
        if _flag(self.fallbacks_allowed, 'fallbacks_allowed'):
            raise WriteContractError('no se permite fallback de mutex')
        if _flag(self.multi_host_allowed, 'multi_host_allowed'):
            raise WriteContractError('no se permite multi-host')
        if self.wait_abandoned_policy != LOCK_WAIT_ABANDONED_POLICY:
            raise WriteContractError('política WAIT_ABANDONED inválida')
        if self.failure_policy != LOCK_FAILURE_POLICY:
            raise WriteContractError('política de fallo de mutex inválida')
        if not _flag(self.acl_required, 'acl_required'):
            raise WriteContractError('el mutex exige ACL')
        if not _flag(self.sid_required, 'sid_required'):
            raise WriteContractError('el mutex exige SID')
        return self


DEFAULT_LOCK_POLICY = LockPolicy()


def lock_policy_fingerprint(policy: LockPolicy) -> str:
    policy.validate()
    return _canonical_sha256(policy.as_dict(), 'lock_policy')


@dataclass(frozen=True)
class WriterDeclaration:
    """Contrato mínimo que F3 debe exigir a cada writer declarado."""

    name: str
    operation: str
    targets: Tuple[str, ...]
    requires_lock: bool
    requires_cas: bool
    requires_backup: bool
    requires_manifest_verification: bool
    requires_pins_proposal: bool
    lock_policy: LockPolicy = DEFAULT_LOCK_POLICY

    def __post_init__(self) -> None:
        if isinstance(self.targets, (list, tuple)):
            object.__setattr__(self, 'targets', tuple(self.targets))

    def as_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'operation': self.operation,
            'targets': list(self.targets),
            'requires_lock': self.requires_lock,
            'requires_cas': self.requires_cas,
            'requires_backup': self.requires_backup,
            'requires_manifest_verification':
                self.requires_manifest_verification,
            'requires_pins_proposal': self.requires_pins_proposal,
            'lock_policy': self.lock_policy.as_dict(),
        }

    def validate(self) -> 'WriterDeclaration':
        _nonempty(self.name, 'name')
        if self.operation not in WRITE_OPERATIONS:
            raise WriteContractError('operation inválida: %r' % self.operation)
        self.lock_policy.validate()
        for attribute in (
                'requires_lock', 'requires_cas', 'requires_backup',
                'requires_manifest_verification', 'requires_pins_proposal'):
            _flag(getattr(self, attribute), attribute)
        if not isinstance(self.targets, (tuple, list)) or not self.targets:
            raise WriteContractError('targets no puede estar vacío')
        normalized = []
        seen = set()
        for target in self.targets:
            canonical = _require_canonical_path(target, 'targets')
            key = os.path.normcase(canonical)
            if key in seen:
                raise WriteContractError('targets no puede repetir destinos')
            seen.add(key)
            normalized.append(canonical)
        if self.operation == SNAPSHOT:
            if len(normalized) != 1:
                raise WriteContractError(
                    'un writer snapshot debe declarar un único origen')
            source = normalized[0]
            if source not in TARGET_POLICIES:
                raise WriteContractError(
                    '%s declara un origen snapshot no canónico: %s'
                    % (self.name, source))
            if not self.requires_lock:
                raise WriteContractError(
                    '%s escribe un snapshot sin exigir mutex' % self.name)
            if not self.requires_cas:
                raise WriteContractError(
                    '%s escribe un snapshot sin exigir CAS' % self.name)
            if not self.requires_backup:
                raise WriteContractError(
                    '%s escribe un snapshot sin exigir backup' % self.name)
            if self.requires_pins_proposal and PINS_RUNTIME_UPDATE_ALLOWED:
                raise WriteContractError('los pins no se aplican en runtime')
            return self
        for target in normalized:
            try:
                policy = TARGET_POLICIES[target]
            except KeyError:
                raise WriteContractError(
                    '%s declara un destino no canónico: %s'
                    % (self.name, target))
            if self.operation not in policy.operations:
                raise WriteContractError(
                    '%s usa %s en un destino que no lo permite'
                    % (self.name, self.operation))
            requirements = (
                ('requires_lock', policy.requires_lock, 'mutex'),
                ('requires_cas', policy.requires_cas, 'CAS'),
                ('requires_backup', policy.requires_backup, 'backup'),
                ('requires_manifest_verification',
                 policy.requires_manifest_verification, 'manifiesto'),
                ('requires_pins_proposal',
                 policy.requires_pins_proposal, 'propuesta de pins'),
            )
            for attribute, required, label in requirements:
                if required and not getattr(self, attribute):
                    raise WriteContractError(
                        '%s escribe %s sin exigir %s'
                        % (self.name, target, label))
        if self.requires_pins_proposal and PINS_RUNTIME_UPDATE_ALLOWED:
            raise WriteContractError('los pins no se aplican en runtime')
        return self


def writer_declaration_fingerprint(
        declaration: WriterDeclaration) -> str:
    declaration.validate()
    return _canonical_sha256(declaration.as_dict(), 'writer_declaration')


@dataclass(frozen=True)
class WritePlan:
    """Intención declarada antes de adquirir el mutex y escribir."""

    txn_id: str
    writer: str
    operation: str
    expected_pre_sha256: str
    expected_pre_lines: int
    expected_pre_bytes: int
    candidate_sha256: str
    candidate_lines: int
    candidate_bytes: int
    target_path: str = TARGET_DB
    manifest_required: bool = False
    pins_required: bool = False
    manifest_path: Optional[str] = None
    manifest_expected_sha256: Optional[str] = None
    manifest_candidate_sha256: Optional[str] = None
    pins_path: Optional[str] = None
    pins_expected_sha256: Optional[str] = None
    snapshot_of: Optional[str] = None
    lock_policy: LockPolicy = DEFAULT_LOCK_POLICY
    writer_declaration: Optional[WriterDeclaration] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            'txn_id': self.txn_id,
            'writer': self.writer,
            'operation': self.operation,
            'expected_pre_sha256': self.expected_pre_sha256,
            'expected_pre_lines': self.expected_pre_lines,
            'expected_pre_bytes': self.expected_pre_bytes,
            'candidate_sha256': self.candidate_sha256,
            'candidate_lines': self.candidate_lines,
            'candidate_bytes': self.candidate_bytes,
            'target_path': self.target_path,
            'manifest_required': self.manifest_required,
            'pins_required': self.pins_required,
            'manifest_path': self.manifest_path,
            'manifest_expected_sha256': self.manifest_expected_sha256,
            'manifest_candidate_sha256': self.manifest_candidate_sha256,
            'pins_path': self.pins_path,
            'pins_expected_sha256': self.pins_expected_sha256,
            'snapshot_of': self.snapshot_of,
            'lock_policy': self.lock_policy.as_dict(),
            'writer_declaration': (
                self.writer_declaration.as_dict()
                if self.writer_declaration is not None else None),
        }

    def validate(self) -> 'WritePlan':
        txn_id = _nonempty(self.txn_id, 'txn_id')
        if TXN_ID_PATTERN.fullmatch(txn_id) is None:
            raise WriteContractError('txn_id contiene caracteres no permitidos')
        _nonempty(self.writer, 'writer')
        if self.operation not in WRITE_OPERATIONS:
            raise WriteContractError('operation inválida: %r' % self.operation)
        if self.writer_declaration is None:
            raise WriteContractError('writer_declaration es obligatoria')
        self.writer_declaration.validate()
        self.lock_policy.validate()
        _require_canonical_path(self.target_path, 'target_path')
        if self.target_path == TARGET_MANIFEST:
            raise WriteContractError(
                'manifest_path debe declararse aparte; target_path no es el '
                'manifiesto')
        _sha256(self.expected_pre_sha256, 'expected_pre_sha256')
        _lines(self.expected_pre_lines, 'expected_pre_lines')
        _bytes(self.expected_pre_bytes, 'expected_pre_bytes')
        _sha256(self.candidate_sha256, 'candidate_sha256')
        _lines(self.candidate_lines, 'candidate_lines')
        _bytes(self.candidate_bytes, 'candidate_bytes')
        _flag(self.manifest_required, 'manifest_required')
        _flag(self.pins_required, 'pins_required')
        if self.manifest_required:
            if self.manifest_path != TARGET_MANIFEST:
                raise WriteContractError(
                    'manifest_path debe ser %s' % TARGET_MANIFEST)
            _require_canonical_path(self.manifest_path, 'manifest_path')
            _sha256(self.manifest_expected_sha256,
                    'manifest_expected_sha256')
            _sha256(self.manifest_candidate_sha256,
                    'manifest_candidate_sha256')
        else:
            if self.manifest_path is not None:
                raise WriteContractError(
                    'manifest_path requiere manifest_required=True')
            if self.manifest_expected_sha256 is not None:
                raise WriteContractError(
                    'manifest_expected_sha256 requiere manifest_required=True')
            if self.manifest_candidate_sha256 is not None:
                raise WriteContractError(
                    'manifest_candidate_sha256 requiere manifest_required=True')
        if self.pins_required:
            pins_path = _require_canonical_path(self.pins_path, 'pins_path')
            if pins_path not in PINS_SOURCE_PATHS:
                raise WriteContractError('pins_path no declarado: %s'
                                         % pins_path)
            _sha256(self.pins_expected_sha256, 'pins_expected_sha256')
        else:
            if self.pins_path is not None:
                raise WriteContractError('pins_path requiere pins_required=True')
            if self.pins_expected_sha256 is not None:
                raise WriteContractError(
                    'pins_expected_sha256 requiere pins_required=True')
        if self.snapshot_of is not None:
            _require_canonical_path(self.snapshot_of, 'snapshot_of')
        self._validate_target_operation()
        self._validate_writer_binding()
        return self

    def _validate_target_operation(self) -> None:
        if self.operation == SNAPSHOT:
            if self.snapshot_of is None:
                raise WriteContractError('snapshot_of es obligatorio en snapshot')
            source = _require_canonical_path(self.snapshot_of, 'snapshot_of')
            if source not in TARGET_POLICIES:
                raise WriteContractError(
                    'snapshot_of no es un destino declarado: %s' % source)
            target = _require_canonical_path(self.target_path, 'target_path')
            if not target.startswith(SNAPSHOT_ROOT + '/'):
                raise WriteContractError(
                    'snapshot debe escribir bajo %s/' % SNAPSHOT_ROOT)
            if _same_path(target, source):
                raise WriteContractError(
                    'snapshot no puede escribir el recurso canónico')
            if self.candidate_sha256 != self.expected_pre_sha256 or \
                    self.candidate_lines != self.expected_pre_lines or \
                    self.candidate_bytes != self.expected_pre_bytes:
                raise WriteContractError(
                    'snapshot debe copiar la preimagen sin cambios')
            return
        if self.snapshot_of is not None:
            raise WriteContractError('snapshot_of solo pertenece a snapshot')
        policy = _target_policy(self.target_path)
        if self.operation not in policy.operations:
            raise WriteContractError(
                'operación %s no permitida para %s'
                % (self.operation, self.target_path))
        if self.operation == APPEND:
            if self.candidate_bytes < self.expected_pre_bytes:
                raise WriteContractError(
                    'append no puede reducir los bytes de la preimagen')
            if self.candidate_lines < self.expected_pre_lines:
                raise WriteContractError(
                    'append no puede reducir las líneas de la preimagen')
            if self.candidate_bytes == self.expected_pre_bytes:
                if self.candidate_sha256 != self.expected_pre_sha256:
                    raise WriteContractError(
                        'append con los mismos bytes debe conservar la '
                        'preimagen')
                if self.candidate_lines != self.expected_pre_lines:
                    raise WriteContractError(
                        'append con los mismos bytes debe conservar las líneas')
            if self.candidate_lines > self.expected_pre_lines and \
                    self.candidate_bytes == self.expected_pre_bytes:
                raise WriteContractError(
                    'append con más líneas debe aumentar los bytes')
            if self.candidate_sha256 == self.expected_pre_sha256 and \
                    self.candidate_bytes != self.expected_pre_bytes:
                raise WriteContractError(
                    'append no puede cambiar bytes conservando el hash')

    def _validate_writer_binding(self) -> None:
        declaration = self.writer_declaration
        if declaration is None:
            raise WriteContractError('writer_declaration es obligatoria')
        if self.writer != declaration.name:
            raise WriteContractError(
                'writer no coincide con la declaración validada')
        if self.operation != declaration.operation:
            raise WriteContractError(
                'operation no coincide con la declaración validada')
        if self.lock_policy != declaration.lock_policy:
            raise WriteContractError(
                'lock_policy no coincide con la declaración validada')
        if self.operation == SNAPSHOT:
            source = _require_canonical_path(self.snapshot_of, 'snapshot_of')
            if declaration.targets != (source,):
                raise WriteContractError(
                    'la declaración snapshot no corresponde al origen del plan')
            return
        target = _require_canonical_path(self.target_path, 'target_path')
        if target not in declaration.targets:
            raise WriteContractError(
                'la declaración no corresponde al target_path del plan')
        policy = _target_policy(target)
        if policy.requires_manifest_verification and \
                not self.manifest_required:
            raise WriteContractError(
                'target_path exige verificación de manifiesto')
        if policy.requires_pins_proposal and not self.pins_required:
            raise WriteContractError('target_path exige propuesta de pins')


def plan_fingerprint(plan: WritePlan) -> str:
    plan.validate()
    return _canonical_sha256(plan.as_dict(), 'plan')


@dataclass
class _AuthorityState:
    txn_id: str
    plan_fingerprint: str
    active: bool = True


_AUTHORITIES: Dict[str, _AuthorityState] = {}


def _register_authority(plan: WritePlan) -> str:
    authority_id = uuid.uuid4().hex
    _AUTHORITIES[authority_id] = _AuthorityState(
        txn_id=plan.txn_id,
        plan_fingerprint=plan_fingerprint(plan),
    )
    return authority_id


def _invalidate_authority(authority_id: str) -> None:
    state = _AUTHORITIES.get(authority_id)
    if state is None:
        raise WriteContractError('autoridad de transacción desconocida')
    state.active = False


def _check_authority(record: 'TransactionRecord') -> _AuthorityState:
    if not record.authority_id:
        raise WriteContractError(
            'el registro no tiene autoridad de transacción')
    state = _AUTHORITIES.get(record.authority_id)
    if state is None:
        raise WriteContractError('autoridad de transacción desconocida')
    if state.txn_id != record.plan.txn_id:
        raise WriteContractError(
            'la autoridad de transacción no corresponde al txn_id')
    if state.plan_fingerprint != plan_fingerprint(record.plan):
        raise WriteContractError(
            'la autoridad de transacción no corresponde al plan')
    return state


def _require_active_authority(record: 'TransactionRecord') -> None:
    state = _check_authority(record)
    if not state.active:
        raise WriteContractError(
            'transacción invalidada por un conflicto CAS')


@dataclass(frozen=True)
class TransactionRecord:
    """Estado observable de una transacción; inmutable por transición."""

    state: str
    plan: WritePlan
    evidence: Mapping[str, Any] = field(default_factory=dict)
    history: Tuple[str, ...] = ()
    authority_id: str = field(default='', repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'evidence',
                           _freeze_value(self.evidence, 'evidence'))
        if not isinstance(self.history, tuple):
            object.__setattr__(self, 'history', tuple(self.history))

    def as_dict(self) -> Dict[str, Any]:
        return {
            'contract_version': CONTRACT_VERSION,
            'state': self.state,
            'history': list(self.history),
            'evidence': _to_jsonable(self.evidence, 'evidence'),
        }


def new_transaction(plan: WritePlan, planned_at: str) -> TransactionRecord:
    plan.validate()
    evidence = {
        'txn_id': plan.txn_id,
        'writer': plan.writer,
        'target_path': plan.target_path,
        'operation': plan.operation,
        'expected_pre_sha256': plan.expected_pre_sha256,
        'expected_pre_lines': plan.expected_pre_lines,
        'expected_pre_bytes': plan.expected_pre_bytes,
        'candidate_sha256': plan.candidate_sha256,
        'candidate_lines': plan.candidate_lines,
        'candidate_bytes': plan.candidate_bytes,
        'manifest_required': plan.manifest_required,
        'pins_required': plan.pins_required,
        'writer_declaration_fingerprint':
            writer_declaration_fingerprint(plan.writer_declaration),
        'lock_policy_fingerprint': lock_policy_fingerprint(plan.lock_policy),
        'planned_at': _timestamp(planned_at, 'planned_at'),
    }
    if plan.manifest_path is not None:
        evidence['manifest_path'] = plan.manifest_path
    if plan.manifest_expected_sha256 is not None:
        evidence['manifest_expected_sha256'] = plan.manifest_expected_sha256
    if plan.manifest_candidate_sha256 is not None:
        evidence['manifest_candidate_sha256'] = plan.manifest_candidate_sha256
    if plan.pins_path is not None:
        evidence['pins_path'] = plan.pins_path
    if plan.pins_expected_sha256 is not None:
        evidence['pins_expected_sha256'] = plan.pins_expected_sha256
    if plan.snapshot_of is not None:
        evidence['snapshot_of'] = plan.snapshot_of
    authority_id = _register_authority(plan)
    try:
        return _validate_record(TransactionRecord(
            state=PREPARED,
            plan=plan,
            evidence=evidence,
            history=(PREPARED,),
            authority_id=authority_id,
        ))
    except Exception:
        _AUTHORITIES.pop(authority_id, None)
        raise


def _check_plan_evidence(record: TransactionRecord) -> None:
    plan = record.plan
    evidence = record.evidence
    expected = {
        'txn_id': plan.txn_id,
        'writer': plan.writer,
        'target_path': plan.target_path,
        'operation': plan.operation,
        'expected_pre_sha256': plan.expected_pre_sha256,
        'expected_pre_lines': plan.expected_pre_lines,
        'expected_pre_bytes': plan.expected_pre_bytes,
        'candidate_sha256': plan.candidate_sha256,
        'candidate_lines': plan.candidate_lines,
        'candidate_bytes': plan.candidate_bytes,
        'manifest_required': plan.manifest_required,
        'pins_required': plan.pins_required,
        'writer_declaration_fingerprint':
            writer_declaration_fingerprint(plan.writer_declaration),
        'lock_policy_fingerprint': lock_policy_fingerprint(plan.lock_policy),
    }
    for name, value in expected.items():
        if name not in evidence:
            raise WriteContractError(
                'la evidencia no puede contradecir el plan: %s' % name)
        if name in ('manifest_required', 'pins_required'):
            observed = _flag(evidence.get(name), name)
        elif name in ('expected_pre_lines', 'candidate_lines',
                      'expected_pre_bytes', 'candidate_bytes'):
            observed = _nonnegative_int(evidence.get(name), name)
        elif name in ('expected_pre_sha256', 'candidate_sha256',
                      'lock_policy_fingerprint'):
            observed = _sha256(evidence.get(name), name)
        else:
            observed = _nonempty(evidence.get(name), name)
        if observed != value:
            raise WriteContractError(
                'la evidencia no puede contradecir el plan: %s' % name)
    _timestamp(evidence.get('planned_at'), 'planned_at')
    optional = {
        'manifest_path': plan.manifest_path,
        'manifest_expected_sha256': plan.manifest_expected_sha256,
        'manifest_candidate_sha256': plan.manifest_candidate_sha256,
        'pins_path': plan.pins_path,
        'pins_expected_sha256': plan.pins_expected_sha256,
        'snapshot_of': plan.snapshot_of,
    }
    for name, value in optional.items():
        if value is None:
            if name in evidence:
                raise WriteContractError(
                    '%s no pertenece al plan' % name)
        elif name not in evidence:
            raise WriteContractError(
                'la evidencia no puede contradecir el plan: %s' % name)
        elif name.endswith('_sha256'):
            if _sha256(evidence.get(name), name) != value:
                raise WriteContractError(
                    'la evidencia no puede contradecir el plan: %s' % name)
        elif _nonempty(evidence.get(name), name) != value:
            raise WriteContractError(
                'la evidencia no puede contradecir el plan: %s' % name)


def _check_operation(record: TransactionRecord,
                     evidence: Mapping[str, Any]) -> None:
    plan = record.plan
    if _flag(evidence.get('operation_verified'), 'operation_verified') \
            is not True:
        raise WriteContractError('operation_verified debe ser True')
    if plan.operation == APPEND:
        if _flag(evidence.get('preimage_prefix_verified'),
                 'preimage_prefix_verified') is not True:
            raise WriteContractError(
                'append exige preimagen como prefijo verificado')
        if _flag(evidence.get('append_boundary_verified'),
                 'append_boundary_verified') is not True:
            raise WriteContractError(
                'append exige frontera de línea verificada')
    elif plan.operation == REWRITE:
        if _flag(evidence.get('rewrite_complete_verified'),
                 'rewrite_complete_verified') is not True:
            raise WriteContractError(
                'rewrite exige reemplazo completo verificado')
    elif plan.operation == SNAPSHOT:
        if _flag(evidence.get('snapshot_verified'),
                 'snapshot_verified') is not True:
            raise WriteContractError('snapshot exige copia verificada')
        if _flag(evidence.get('canonical_target_unchanged'),
                 'canonical_target_unchanged') is not True:
            raise WriteContractError(
                'snapshot no puede alterar el recurso canónico')


def _check_backup(record: TransactionRecord,
                  evidence: Mapping[str, Any]) -> None:
    plan = record.plan
    backup_path = _require_canonical_path(evidence.get('backup_path'),
                                          'backup_path')
    if _same_path(backup_path, plan.target_path):
        raise WriteContractError('backup_path no puede ser el target')
    for name, other in (
            ('manifest_path', plan.manifest_path),
            ('pins_path', plan.pins_path),
            ('snapshot_of', plan.snapshot_of)):
        if other is not None and _same_path(backup_path, other):
            raise WriteContractError('backup_path no puede ser %s' % name)
    if not backup_path.startswith(BACKUP_ROOT_PREFIX):
        raise WriteContractError(
            'backup_path debe quedar bajo %s' % BACKUP_ROOT_PREFIX)
    if plan.txn_id not in Path(backup_path).name:
        raise WriteContractError('backup_path debe identificar el txn_id')
    disposition = _require_text(evidence, 'backup_disposition')
    if disposition not in BACKUP_DISPOSITIONS:
        raise WriteContractError('backup_disposition inválida: %s'
                                 % disposition)
    if _nonempty(evidence.get('backup_txn_id'), 'backup_txn_id') != \
            plan.txn_id:
        raise WriteContractError('backup_txn_id debe coincidir con txn_id')
    _check_sha(evidence, 'backup_sha256', plan.expected_pre_sha256)
    _check_bytes(evidence, 'backup_bytes', plan.expected_pre_bytes)


def _check_temp(record: TransactionRecord,
                evidence: Mapping[str, Any]) -> None:
    plan = record.plan
    temp_path = _require_canonical_path(evidence.get('temp_path'),
                                        'temp_path')
    if _same_path(temp_path, plan.target_path):
        raise WriteContractError('temp_path no puede ser el target')
    if not temp_path.endswith('.tmp'):
        raise WriteContractError('temp_path debe terminar en .tmp')
    if plan.txn_id not in Path(temp_path).name:
        raise WriteContractError('temp_path debe identificar el txn_id')
    for name, other in (
            ('backup_path', evidence.get('backup_path')),
            ('manifest_path', plan.manifest_path),
            ('pins_path', plan.pins_path),
            ('snapshot_of', plan.snapshot_of)):
        if other is not None and _same_path(temp_path, other):
            raise WriteContractError('temp_path no puede ser %s' % name)
    _check_sha(evidence, 'temp_sha256', plan.candidate_sha256)
    _check_lines(evidence, 'temp_lines', plan.candidate_lines)
    _check_bytes(evidence, 'temp_bytes', plan.candidate_bytes)


def _check_cas_conflict(record: TransactionRecord,
                        evidence: Mapping[str, Any]) -> None:
    plan = record.plan
    observed_sha = _sha256(evidence.get('observed_pre_sha256'),
                           'observed_pre_sha256')
    observed_lines = _lines(evidence.get('observed_pre_lines'),
                            'observed_pre_lines')
    observed_bytes = _bytes(evidence.get('observed_pre_bytes'),
                            'observed_pre_bytes')
    if (observed_sha == plan.expected_pre_sha256 and
            observed_lines == plan.expected_pre_lines and
            observed_bytes == plan.expected_pre_bytes):
        raise WriteContractError(
            'cas_conflict exige una discrepancia con la preimagen')
    _require_text(evidence, 'cas_conflict_reason')
    _timestamp(evidence.get('cas_conflict_at'), 'cas_conflict_at')


def _check_manifest_pending(record: TransactionRecord,
                            evidence: Mapping[str, Any]) -> None:
    plan = record.plan
    _timestamp(evidence.get('manifest_pending_at'), 'manifest_pending_at')
    if not plan.manifest_required:
        _require_text(evidence, 'manifest_skipped_reason')


def _check_manifest(record: TransactionRecord,
                    evidence: Mapping[str, Any]) -> None:
    plan = record.plan
    if plan.manifest_required:
        _require(evidence, (
            'manifest_observed_pre_sha256', 'manifest_sha256',
            'manifest_verified',
        ))
        _check_sha(evidence, 'manifest_observed_pre_sha256',
                   plan.manifest_expected_sha256)
        _check_sha(evidence, 'manifest_sha256',
                   plan.manifest_candidate_sha256)
        if evidence.get('manifest_verified') is not True:
            raise WriteContractError('manifest_verified debe ser True')
    else:
        _require_text(evidence, 'manifest_skipped_reason')


def _normalize_pins_symbols(symbols: Any) -> Tuple[str, ...]:
    if isinstance(symbols, (str, bytes)) or not isinstance(
            symbols, (list, tuple, set, frozenset)):
        raise WriteContractError(
            'pins_symbols debe ser una colección de símbolos')
    normalized = tuple(_nonempty(symbol, 'pins_symbols') for symbol in symbols)
    if set(normalized) != set(PINS_SYMBOLS):
        missing = sorted(set(PINS_SYMBOLS) - set(normalized))
        extra = sorted(set(normalized) - set(PINS_SYMBOLS))
        detail = []
        if missing:
            detail.append('faltan: %s' % ', '.join(missing))
        if extra:
            detail.append('sobran: %s' % ', '.join(extra))
        raise WriteContractError('pins_symbols incompleto (%s)'
                                 % '; '.join(detail))
    return normalized


def _check_pins(record: TransactionRecord,
                evidence: Mapping[str, Any]) -> None:
    plan = record.plan
    _require(evidence, ('pins_applied',))
    applied = _flag(evidence.get('pins_applied'), 'pins_applied')
    if applied or PINS_RUNTIME_UPDATE_ALLOWED:
        raise WriteContractError(
            'los pins se proponen para revisión; no se aplican en runtime')
    if not plan.pins_required:
        _require_text(evidence, 'pins_skipped_reason')
        return
    _normalize_pins_symbols(evidence.get('pins_symbols'))
    values = evidence.get('pins_proposed_values')
    if not isinstance(values, Mapping):
        raise WriteContractError('pins_proposed_values debe ser un mapping')
    if set(values) != set(PINS_SYMBOLS):
        raise WriteContractError(
            'pins_proposed_values debe cubrir exactamente %s'
            % ', '.join(PINS_SYMBOLS))
    _check_sha(evidence, 'pins_proposed_sha256',
               _canonical_sha256(values, 'pins_proposed_values'))
    if _sha256(values.get('HANDS_DB_SHA256'), 'HANDS_DB_SHA256') != \
            plan.candidate_sha256:
        raise WriteContractError(
            'HANDS_DB_SHA256 debe coincidir con el candidato')
    if _nonnegative_int(values.get('HANDS_DB_LINEAS'),
                        'HANDS_DB_LINEAS') != plan.candidate_lines:
        raise WriteContractError(
            'HANDS_DB_LINEAS debe coincidir con el candidato')
    commit = _nonempty(values.get('HANDS_DB_COMMIT'), 'HANDS_DB_COMMIT')
    if COMMIT_PATTERN.fullmatch(commit) is None:
        raise WriteContractError('HANDS_DB_COMMIT no es un commit válido')
    source_sha = _sha256(evidence.get('pins_source_sha256'),
                         'pins_source_sha256')
    if source_sha != plan.pins_expected_sha256:
        raise WriteContractError(
            'pins_source_sha256 no coincide con el plan')


def _check_state_evidence(record: TransactionRecord, state: str,
                          evidence: Mapping[str, Any]) -> None:
    plan = record.plan
    _require(evidence, REQUIRED_EVIDENCE[state])
    if state == PREIMAGE_VERIFIED:
        _check_cas_sha(evidence, 'observed_pre_sha256',
                       plan.expected_pre_sha256)
        _check_cas_lines(evidence, 'observed_pre_lines',
                         plan.expected_pre_lines)
        _check_cas_bytes(evidence, 'observed_pre_bytes',
                         plan.expected_pre_bytes)
    elif state == CAS_CONFLICT:
        _check_cas_conflict(record, evidence)
    elif state == BACKUP_VERIFIED:
        _check_backup(record, evidence)
    elif state == TEMP_VERIFIED:
        _check_temp(record, evidence)
    elif state == REPLACED:
        _timestamp(evidence.get('replaced_at'), 'replaced_at')
        _check_operation(record, evidence)
    elif state == POST_VERIFIED:
        _check_sha(evidence, 'post_sha256', plan.candidate_sha256)
        _check_lines(evidence, 'post_lines', plan.candidate_lines)
        _check_bytes(evidence, 'post_bytes', plan.candidate_bytes)
    elif state == MANIFEST_PENDING:
        _check_manifest_pending(record, evidence)
    elif state == MANIFEST_VERIFIED:
        _check_manifest(record, evidence)
    elif state == PINS_PROPOSED:
        _check_pins(record, evidence)
    elif state == COMMITTED:
        _check_sha(evidence, 'post_sha256', plan.candidate_sha256)
        _check_lines(evidence, 'post_lines', plan.candidate_lines)
        _check_bytes(evidence, 'post_bytes', plan.candidate_bytes)
        _check_manifest(record, evidence)
        _check_pins(record, evidence)
        _timestamp(evidence.get('committed_at'), 'committed_at')
    elif state == ABORTED:
        _require_text(evidence, 'abort_reason')
    elif state == FAILED:
        _require_text(evidence, 'failure_reason')
    elif state == QUARANTINED:
        _require_text(evidence, 'quarantine_reason')


def _validate_record(record: TransactionRecord) -> TransactionRecord:
    record.plan.validate()
    if not isinstance(record.evidence, Mapping):
        raise WriteContractError('evidence debe ser un mapping')
    _assert_immutable(record.evidence)
    if record.state not in JOURNAL_STATES:
        raise WriteContractError('estado actual inválido: %r' % record.state)
    _check_plan_evidence(record)
    if not isinstance(record.history, tuple) or not record.history:
        raise WriteContractError('history debe ser una tupla no vacía')
    if any(state not in JOURNAL_STATES for state in record.history):
        raise WriteContractError('history contiene un estado inválido')
    if record.history[0] != PREPARED:
        raise WriteContractError('history debe empezar en prepared')
    if record.history[-1] != record.state:
        raise WriteContractError('history no termina en el estado actual')
    if len(set(record.history)) != len(record.history):
        raise WriteContractError('history no puede repetir estados')
    for previous, following in zip(record.history, record.history[1:]):
        if following not in TRANSITIONS[previous]:
            raise WriteContractError(
                'history contiene una transición no permitida: %s -> %s'
                % (previous, following))
    for state in record.history:
        _check_state_evidence(record, state, record.evidence)
    _check_authority(record)
    return record


def _merge_evidence(record: TransactionRecord,
                    evidence: Mapping[str, Any]) -> Mapping[str, Any]:
    merged = dict(record.evidence)
    for name, value in evidence.items():
        if name in PLAN_OWNED_EVIDENCE:
            raise WriteContractError(
                'la evidencia no puede sobrescribir el plan: %s' % name)
        if name in merged:
            raise WriteContractError(
                'la evidencia ya está fijada: %s' % name)
        if name not in EVIDENCE_KEYS:
            raise WriteContractError('evidencia desconocida: %s' % name)
        merged[name] = value
    return _freeze_value(merged, 'evidence')


def transition(record: TransactionRecord, next_state: str,
               evidence: Optional[Mapping[str, Any]] = None
               ) -> TransactionRecord:
    """Aplica una transición permitida y exige su evidencia."""
    _validate_record(record)
    _require_active_authority(record)
    raw = _evidence_mapping(evidence)
    if next_state == record.state:
        if record.state in TERMINAL_STATES:
            raise WriteContractError(
                'un estado terminal no admite reintentos: %s' % next_state)
        for name, value in raw.items():
            if name not in record.evidence:
                raise WriteContractError(
                    'el reintento no puede cambiar evidencia: %s' % name)
            if _to_jsonable(record.evidence[name]) != _to_jsonable(value):
                raise WriteContractError(
                    'el reintento no puede cambiar evidencia: %s' % name)
        return record
    if next_state not in JOURNAL_STATES:
        raise WriteContractError('estado destino inválido: %r' % next_state)
    allowed = TRANSITIONS[record.state]
    if next_state not in allowed:
        raise WriteContractError(
            'transición no permitida: %s -> %s' % (record.state, next_state))
    if next_state == PREIMAGE_VERIFIED:
        _require(raw, REQUIRED_EVIDENCE[PREIMAGE_VERIFIED])
        observed_sha = _sha256(raw.get('observed_pre_sha256'),
                               'observed_pre_sha256')
        observed_lines = _lines(raw.get('observed_pre_lines'),
                                'observed_pre_lines')
        observed_bytes = _bytes(raw.get('observed_pre_bytes'),
                                'observed_pre_bytes')
        plan = record.plan
        if not (observed_sha == plan.expected_pre_sha256 and
                observed_lines == plan.expected_pre_lines and
                observed_bytes == plan.expected_pre_bytes):
            conflict_evidence = dict(raw)
            conflict_evidence['cas_conflict_reason'] = \
                'la preimagen observada difiere de la declarada'
            conflict_evidence.setdefault('cas_conflict_at', _utc_now())
            merged = _merge_evidence(record, conflict_evidence)
            conflict = _validate_record(TransactionRecord(
                state=CAS_CONFLICT,
                plan=plan,
                evidence=merged,
                history=record.history + (CAS_CONFLICT,),
                authority_id=record.authority_id,
            ))
            _invalidate_authority(record.authority_id)
            raise CasConflict(
                'CAS rechaza la preimagen; la transacción queda terminal',
                record=conflict)
    elif next_state == CAS_CONFLICT:
        _require(raw, ('observed_pre_sha256', 'observed_pre_lines',
                       'observed_pre_bytes'))
        conflict_evidence = dict(raw)
        conflict_evidence.setdefault(
            'cas_conflict_reason',
            'la preimagen observada difiere de la declarada')
        conflict_evidence.setdefault('cas_conflict_at', _utc_now())
        merged = _merge_evidence(record, conflict_evidence)
        _check_state_evidence(record, CAS_CONFLICT, merged)
        conflict = _validate_record(TransactionRecord(
            state=CAS_CONFLICT,
            plan=record.plan,
            evidence=merged,
            history=record.history + (CAS_CONFLICT,),
            authority_id=record.authority_id,
        ))
        _invalidate_authority(record.authority_id)
        return conflict
    merged = _merge_evidence(record, raw)
    _check_state_evidence(record, next_state, merged)
    return _validate_record(TransactionRecord(
        state=next_state,
        plan=record.plan,
        evidence=merged,
        history=record.history + (next_state,),
        authority_id=record.authority_id,
    ))


def assert_committed(record: TransactionRecord) -> TransactionRecord:
    """Devuelve el registro solo si la transacción terminó completa."""
    _validate_record(record)
    _require_active_authority(record)
    if record.state != COMMITTED:
        raise WriteContractError('la transacción no está committed: %s'
                                 % record.state)
    return record


def journal_record_sha256(record: Mapping[str, Any]) -> str:
    """Hash canónico del sobre de journal, sin incluir `record_sha256`."""
    if not isinstance(record, Mapping):
        raise WriteContractError('el registro de journal debe ser un mapping')
    if any(not isinstance(key, str) for key in record):
        raise WriteContractError('el journal exige claves textuales')
    payload = {key: value for key, value in record.items()
               if key != 'record_sha256'}
    return _canonical_sha256(payload, 'journal')


def journal_record_from_transaction(record: TransactionRecord,
                                    sequence: int,
                                    previous_sha256: str) -> Dict[str, Any]:
    """Construye un registro de journal ligado al plan y a su evidencia."""
    _validate_record(record)
    evidence = _to_jsonable(record.evidence, 'evidence')
    payload = {
        'schema_version': JOURNAL_SCHEMA_VERSION,
        'contract_version': CONTRACT_VERSION,
        'txn_id': record.plan.txn_id,
        'plan_fingerprint': plan_fingerprint(record.plan),
        'sequence': _lines(sequence, 'sequence'),
        'state': record.state,
        'previous_sha256': _sha256(previous_sha256, 'previous_sha256'),
        'evidence': evidence,
        'evidence_sha256': _canonical_sha256(evidence, 'evidence'),
    }
    payload['record_sha256'] = journal_record_sha256(payload)
    return payload


def validate_journal_record(record: Mapping[str, Any],
                            plan: Optional[WritePlan] = None
                            ) -> Dict[str, Any]:
    """Valida forma, hashes, plan, evidencia y ausencia de un tercer hash."""
    if not isinstance(record, Mapping):
        raise WriteContractError('el registro de journal debe ser un mapping')
    if any(not isinstance(key, str) for key in record):
        raise WriteContractError('el journal exige claves textuales')
    _require(record, (
        'schema_version', 'contract_version', 'txn_id', 'plan_fingerprint',
        'sequence', 'state', 'previous_sha256', 'evidence', 'evidence_sha256',
        'record_sha256',
    ))
    schema_version = record.get('schema_version')
    if isinstance(schema_version, bool) or not isinstance(schema_version, int) \
            or schema_version != JOURNAL_SCHEMA_VERSION:
        raise WriteContractError('schema_version de journal inválido')
    if record.get('contract_version') != CONTRACT_VERSION:
        raise WriteContractError('contract_version de journal inválido')
    txn_id = _nonempty(record.get('txn_id'), 'txn_id')
    _sha256(record.get('plan_fingerprint'), 'plan_fingerprint')
    _lines(record.get('sequence'), 'sequence')
    state = record.get('state')
    if state not in JOURNAL_STATES:
        raise WriteContractError('estado de journal inválido: %r' % state)
    _sha256(record.get('previous_sha256'), 'previous_sha256')
    _sha256(record.get('record_sha256'), 'record_sha256')
    _sha256(record.get('evidence_sha256'), 'evidence_sha256')
    raw_evidence = record.get('evidence')
    if not isinstance(raw_evidence, Mapping):
        raise WriteContractError('evidence de journal debe ser un mapping')
    if not raw_evidence:
        raise WriteContractError('evidence de journal no puede estar vacía')
    evidence = _freeze_value(raw_evidence, 'evidence')
    _require(evidence, REQUIRED_EVIDENCE[state])
    if _nonempty(evidence.get('txn_id'), 'evidence.txn_id') != txn_id:
        raise WriteContractError(
            'evidence.txn_id no coincide con el txn_id del journal')
    if _canonical_sha256(raw_evidence, 'evidence') != \
            record.get('evidence_sha256'):
        raise WriteContractError('evidence_sha256 de journal no coincide')
    extra_hashes = sorted(
        str(name) for name in record
        if name not in JOURNAL_HASH_FIELDS
        and name.lower().endswith('sha256'))
    if extra_hashes:
        raise WriteContractError(
            'journal con tercer hash: %s' % ', '.join(extra_hashes))
    if plan is not None:
        plan.validate()
        if txn_id != plan.txn_id:
            raise WriteContractError('txn_id de journal no coincide con plan')
        if record.get('plan_fingerprint') != plan_fingerprint(plan):
            raise WriteContractError(
                'journal no está ligado al plan declarado')
        check_record = TransactionRecord(
            state=state,
            plan=plan,
            evidence=evidence,
            history=(PREPARED, state) if state != PREPARED else (PREPARED,),
        )
        _check_plan_evidence(check_record)
        _check_state_evidence(check_record, state, evidence)
    expected = journal_record_sha256(record)
    if record.get('record_sha256') != expected:
        raise WriteContractError('record_sha256 de journal no coincide')
    return dict(record)


def validate_journal_chain(records: Any,
                           expected_records: Optional[int] = None,
                           plan: Optional[WritePlan] = None
                           ) -> Tuple[Dict[str, Any], ...]:
    """Valida cadena, plan, evidencia acumulada y truncado esperado."""
    if not isinstance(records, (list, tuple)):
        raise WriteContractError('el journal debe ser una lista o tupla')
    if expected_records is not None:
        expected = _lines(expected_records, 'expected_records')
        if len(records) != expected:
            raise WriteContractError(
                'journal truncado: %d registros, se esperaban %d'
                % (len(records), expected))
    if not records:
        return ()
    chain = []
    previous_sha = None
    previous_state = None
    previous_evidence = None
    txn_id = None
    fingerprint = None
    for index, raw in enumerate(records):
        record = validate_journal_record(raw, plan=plan)
        if record['sequence'] != index:
            raise WriteContractError('secuencia de journal discontinua')
        if txn_id is None:
            txn_id = record['txn_id']
        elif record['txn_id'] != txn_id:
            raise WriteContractError('txn_id inconsistente en journal')
        if fingerprint is None:
            fingerprint = record['plan_fingerprint']
        elif record['plan_fingerprint'] != fingerprint:
            raise WriteContractError(
                'plan_fingerprint inconsistente en journal')
        expected_previous = (JOURNAL_GENESIS_SHA256 if index == 0
                             else previous_sha)
        if record['previous_sha256'] != expected_previous:
            raise WriteContractError('cadena de hashes de journal rota')
        if index == 0:
            if record['state'] != PREPARED:
                raise WriteContractError('journal debe empezar en prepared')
            if record['previous_sha256'] != JOURNAL_GENESIS_SHA256:
                raise WriteContractError('journal debe empezar en génesis')
        else:
            if record['state'] not in TRANSITIONS[previous_state]:
                raise WriteContractError(
                    'transición de journal no permitida: %s -> %s'
                    % (previous_state, record['state']))
        current_evidence = record['evidence']
        if previous_evidence is not None:
            for name, value in previous_evidence.items():
                if name not in current_evidence:
                    raise WriteContractError(
                        'journal elimina evidencia ya verificada: %s' % name)
                if _to_jsonable(current_evidence[name]) != \
                        _to_jsonable(value):
                    raise WriteContractError(
                        'journal cambia evidencia ya verificada: %s' % name)
        previous_sha = record['record_sha256']
        previous_state = record['state']
        previous_evidence = current_evidence
        chain.append(record)
    return tuple(chain)


def recovery_action(records: Any,
                    expected_records: Optional[int] = None,
                    plan: Optional[WritePlan] = None) -> str:
    """Política de recuperación; sin plan verificable no hay restauración."""
    try:
        chain = validate_journal_chain(
            records, expected_records=expected_records, plan=plan)
    except WriteContractError:
        return QUARANTINED
    if not chain:
        return 'noop'
    if plan is None:
        return QUARANTINED
    state = chain[-1]['state']
    if state in TERMINAL_STATES:
        return state
    if state in (REPLACED, POST_VERIFIED, MANIFEST_PENDING,
                 MANIFEST_VERIFIED, PINS_PROPOSED):
        return RECOVERY_ACTION_AFTER_REPLACE
    return RECOVERY_ACTION_BEFORE_REPLACE


@dataclass(frozen=True)
class WriterDeclaration:
    """Contrato mínimo que F3 debe exigir a cada writer declarado."""

    name: str
    operation: str
    targets: Tuple[str, ...]
    requires_lock: bool
    requires_cas: bool
    requires_backup: bool
    requires_manifest_verification: bool
    requires_pins_proposal: bool
    lock_policy: LockPolicy = DEFAULT_LOCK_POLICY

    def validate(self) -> 'WriterDeclaration':
        _nonempty(self.name, 'name')
        if self.operation not in WRITE_OPERATIONS:
            raise WriteContractError('operation inválida: %r' % self.operation)
        self.lock_policy.validate()
        if not isinstance(self.targets, (tuple, list)) or not self.targets:
            raise WriteContractError('targets no puede estar vacío')
        normalized = []
        seen = set()
        for target in self.targets:
            canonical = _require_canonical_path(target, 'targets')
            key = os.path.normcase(canonical)
            if key in seen:
                raise WriteContractError('targets no puede repetir destinos')
            seen.add(key)
            normalized.append(canonical)
        for target in normalized:
            try:
                policy = TARGET_POLICIES[target]
            except KeyError:
                raise WriteContractError(
                    '%s declara un destino no canónico: %s'
                    % (self.name, target))
            if self.operation not in policy.operations:
                raise WriteContractError(
                    '%s usa %s en un destino que no lo permite'
                    % (self.name, self.operation))
            requirements = (
                ('requires_lock', policy.requires_lock, 'mutex'),
                ('requires_cas', policy.requires_cas, 'CAS'),
                ('requires_backup', policy.requires_backup, 'backup'),
                ('requires_manifest_verification',
                 policy.requires_manifest_verification, 'manifiesto'),
                ('requires_pins_proposal',
                 policy.requires_pins_proposal, 'propuesta de pins'),
            )
            for attribute, required, label in requirements:
                if required and not getattr(self, attribute):
                    raise WriteContractError(
                        '%s escribe %s sin exigir %s'
                        % (self.name, target, label))
        if self.requires_pins_proposal and PINS_RUNTIME_UPDATE_ALLOWED:
            raise WriteContractError('los pins no se aplican en runtime')
        return self


def validate_writer_declaration(
        declaration: WriterDeclaration) -> WriterDeclaration:
    return declaration.validate()
