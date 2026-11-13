# -*- coding: utf-8 -*-
"""Tests de contrato F0.7 para integridad de escrituras.

No escriben en `data/`: el arnés simula la base como una cadena y comprueba
que ninguna ruta de fallo puede declarar `committed`, que el CAS invalida la
autoridad de la transacción, que el plan queda ligado a una declaración de
writer validada y a su política efectiva, que las rutas no escapan del
repositorio ni de `data/_backup/`, que el append liga contenido, bytes, hash y
líneas, y que los pins rechazan duplicados.

Categorías:

1. Contrato puro: planes, evidencia, estados, writers, journal.
2. Simulación de fallos: arnés y matrices antes/después de `replaced`.
3. Integración real: fuera del alcance F0; no se abre ni se escribe `data/`.
"""
import copy
import gc
import hashlib
import json
import os
import weakref
from contextlib import contextmanager
from dataclasses import replace

import pytest

import motor.write_contract as wc
from motor.write_contract import (
    ABORTED,
    APPEND,
    BACKUP_VERIFIED,
    CAS_CONFLICT,
    COMMITTED,
    CONTRACT_VERSION,
    CasConflict,
    DEFAULT_LOCK_POLICY,
    FAILED,
    JOURNAL_CORRUPTION_POLICY,
    JOURNAL_EVIDENCE_BINDING_POLICY,
    JOURNAL_GENESIS_SHA256,
    JOURNAL_JSON_DUPLICATE_KEYS_POLICY,
    JOURNAL_JSON_PARSER_REQUIRED,
    JOURNAL_JSON_PARSER_REQUIREMENT,
    JOURNAL_PARTIAL_VALIDATION_POLICY,
    JOURNAL_PLAN_BINDING_POLICY,
    JOURNAL_RAW_JSON_SUPPORTED,
    JOURNAL_RECOVERY_POLICY,
    JOURNAL_SCHEMA_VERSION,
    JOURNAL_THIRD_HASH_POLICY,
    JOURNAL_TRUNCATION_POLICY,
    LOCK_ACL_REQUIRED,
    LOCK_FALLBACKS_ALLOWED,
    LOCK_FAILURE_POLICY,
    LOCK_MECHANISM,
    LOCK_MULTI_HOST_ALLOWED,
    LOCK_NAME,
    LOCK_SID_REQUIRED,
    LOCK_TIMEOUT_SECONDS,
    LOCK_WAIT_ABANDONED_POLICY,
    LockPolicy,
    MANIFEST_PENDING,
    MANIFEST_VERIFIED,
    PINS_PROPOSED,
    PINS_RUNTIME_UPDATE_ALLOWED,
    PINS_SYMBOLS,
    POST_VERIFIED,
    PREIMAGE_VERIFIED,
    PREPARED,
    QUARANTINED,
    READER_POLICY,
    REPLACED,
    REWRITE,
    SNAPSHOT,
    SNAPSHOT_ROOT,
    TEMP_VERIFIED,
    TARGET_DB,
    TARGET_MANIFEST,
    TARGET_POSTFLOP_RANGES,
    TARGET_PROFILE_RANGES,
    TARGET_POLICIES,
    TargetPolicy,
    TERMINAL_STATES,
    TRANSITIONS,
    TransactionRecord,
    WriteContractError,
    WritePlan,
    WriterDeclaration,
    assert_committed,
    canonical_sha256,
    journal_record_from_transaction,
    journal_record_sha256,
    lock_policy_fingerprint,
    new_transaction,
    plan_fingerprint,
    plan_policy_fingerprint,
    recovery_action,
    target_policy_fingerprint,
    transition,
    validate_journal_chain,
    validate_journal_record,
    validate_writer_declaration,
)

HASH_PRE = 'a' * 64
HASH_POST = 'b' * 64
HASH_MANIFEST_PRE = 'c' * 64
HASH_MANIFEST_POST = 'd' * 64
HASH_PINS_SOURCE = 'e' * 64
PINS_COMMIT = '8594ed5'
PRE_BYTES = 100
REWRITE_POST_BYTES = 120
REWRITE_POST_LINES = 10

APPEND_CONTENT = '{"append": 1}\n'
APPEND_BYTES = len(APPEND_CONTENT.encode('utf-8'))
APPEND_LINES = APPEND_CONTENT.count('\n')
APPEND_POST_BYTES = PRE_BYTES + APPEND_BYTES
APPEND_POST_LINES = REWRITE_POST_LINES + APPEND_LINES

PLANNED_AT = '2026-11-12T00:00:00Z'
REPLACED_AT = '2026-11-12T00:00:01Z'
COMMITTED_AT = '2026-11-12T00:00:02Z'


_TXN_SEQUENCE = 0


def _next_txn_id():
    global _TXN_SEQUENCE
    _TXN_SEQUENCE += 1
    return 'txn-f0-%d' % _TXN_SEQUENCE


@contextmanager
def _isolated_contract_state():
    """Aísla los globals del contrato y restaura sus contenedores previos.

    Las copias de los contenidos se mantienen independientes. Se instalan
    contenedores temporales en el módulo para no borrar ni mutar durante la
    prueba los registros previos; al salir se restaura el contenido y también
    la identidad de los contenedores originales. Se guardan los campos
    mutables de cada `_AuthorityState` y las referencias fuertes autorizadas
    para restaurar la misma instancia y sus relaciones.
    """
    original_authorities = wc._AUTHORITIES
    original_used_txn_ids = wc._USED_TXN_IDS
    authorities_snapshot = dict(original_authorities)
    txn_ids_snapshot = set(original_used_txn_ids)
    authority_state_snapshots = []
    seen_authorities = []
    for authority in authorities_snapshot.values():
        if type(authority) is not wc._AuthorityState or any(
                previous is authority for previous in seen_authorities):
            continue
        seen_authorities.append(authority)
        authorized_records = authority.authorized_records
        authority_state_snapshots.append((
            authority,
            authority.txn_id,
            authority.plan_fingerprint,
            authority.transaction_uid,
            authority.active,
            authority.authorized_history,
            authorized_records,
            list(authorized_records),
        ))
    try:
        wc._AUTHORITIES = {}
        wc._USED_TXN_IDS = set()
        yield
    finally:
        try:
            for snapshot in authority_state_snapshots:
                (authority, txn_id, plan_fingerprint, transaction_uid,
                 active, authorized_history, records_object,
                 records_snapshot) = snapshot
                authority.txn_id = txn_id
                authority.plan_fingerprint = plan_fingerprint
                authority.transaction_uid = transaction_uid
                authority.active = active
                authority.authorized_history = authorized_history
                authority.authorized_records = records_object
                records_object[:] = records_snapshot
            original_authorities.clear()
            original_authorities.update(authorities_snapshot)
            original_used_txn_ids.clear()
            original_used_txn_ids.update(txn_ids_snapshot)
        finally:
            wc._AUTHORITIES = original_authorities
            wc._USED_TXN_IDS = original_used_txn_ids


@pytest.fixture(autouse=True)
def _isolate_contract_state():
    # El aislamiento de globals existe solo en el arnés, no en producción.
    with _isolated_contract_state():
        yield


def _declaration(name='writer-de-prueba', target=TARGET_DB, operation=REWRITE,
                 lock_policy=None):
    if lock_policy is None:
        lock_policy = LockPolicy()
    if operation == SNAPSHOT:
        return WriterDeclaration(
            name=name,
            operation=SNAPSHOT,
            targets=(target,),
            requires_lock=True,
            requires_cas=True,
            requires_backup=True,
            requires_manifest_verification=False,
            requires_pins_proposal=False,
            lock_policy=lock_policy,
        )
    policy = TARGET_POLICIES[target]
    return WriterDeclaration(
        name=name,
        operation=operation,
        targets=(target,),
        requires_lock=policy.requires_lock,
        requires_cas=policy.requires_cas,
        requires_backup=policy.requires_backup,
        requires_manifest_verification=policy.requires_manifest_verification,
        requires_pins_proposal=policy.requires_pins_proposal,
        lock_policy=lock_policy,
    )


def _candidate_values(operation):
    if operation == APPEND:
        return HASH_POST, APPEND_POST_LINES, APPEND_POST_BYTES
    if operation == SNAPSHOT:
        return HASH_PRE, REWRITE_POST_LINES, PRE_BYTES
    return HASH_POST, REWRITE_POST_LINES, REWRITE_POST_BYTES


def _plan(**overrides):
    operation = overrides.get('operation', REWRITE)
    lock_policy = overrides.get('lock_policy')
    if lock_policy is None:
        lock_policy = LockPolicy()
    if operation == SNAPSHOT:
        target = overrides.get('target_path', SNAPSHOT_ROOT + '/db.jsonl')
        source = overrides.get('snapshot_of', TARGET_DB)
        default_declaration = _declaration(
            target=source,
            operation=SNAPSHOT,
            lock_policy=lock_policy,
        )
    else:
        target = overrides.get('target_path', TARGET_DB)
        declaration_target = target if target in TARGET_POLICIES else TARGET_DB
        default_declaration = _declaration(
            target=declaration_target,
            operation=operation,
            lock_policy=lock_policy,
        )
    declaration = overrides.get('writer_declaration', default_declaration) \
        if 'writer_declaration' not in overrides else overrides[
            'writer_declaration']
    sha, lines, nbytes = _candidate_values(operation)
    data = {
        'txn_id': overrides.get('txn_id', _next_txn_id()),
        'writer': 'writer-de-prueba',
        'operation': operation,
        'expected_pre_sha256': HASH_PRE,
        'expected_pre_lines': REWRITE_POST_LINES,
        'expected_pre_bytes': PRE_BYTES,
        'candidate_sha256': sha,
        'candidate_lines': lines,
        'candidate_bytes': nbytes,
        'target_path': target,
        'writer_declaration': declaration,
    }
    if operation == SNAPSHOT:
        data['snapshot_of'] = source
        data['manifest_required'] = False
        data['pins_required'] = False
    else:
        policy = TARGET_POLICIES.get(target)
        data['manifest_required'] = (
            policy.requires_manifest_verification if policy else False)
        data['pins_required'] = (
            policy.requires_pins_proposal if policy else False)
        if data['manifest_required']:
            manifest_pre = HASH_PRE if target == TARGET_MANIFEST \
                else HASH_MANIFEST_PRE
            manifest_post = HASH_POST if target == TARGET_MANIFEST \
                else HASH_MANIFEST_POST
            data.update({
                'manifest_path': TARGET_MANIFEST,
                'manifest_expected_sha256': manifest_pre,
                'manifest_candidate_sha256': manifest_post,
            })
        if data['pins_required']:
            data['pins_path'] = 'motor/learn.py'
            data['pins_expected_sha256'] = HASH_PINS_SOURCE
    data.update(overrides)
    return WritePlan(**data)


def _record(**overrides):
    return new_transaction(_plan(**overrides), PLANNED_AT)


def _record_for(plan):
    return new_transaction(plan, PLANNED_AT)


def _pins_values(plan):
    return {
        'HANDS_DB_SHA256': plan.candidate_sha256,
        'HANDS_DB_COMMIT': PINS_COMMIT,
        'HANDS_DB_LINEAS': plan.candidate_lines,
    }


def _backup_evidence(plan, **overrides):
    evidence = {
        'backup_path': 'data/_backup/%s.jsonl' % plan.txn_id,
        'backup_sha256': plan.expected_pre_sha256,
        'backup_bytes': plan.expected_pre_bytes,
        'backup_txn_id': plan.txn_id,
        'backup_disposition': 'created',
    }
    evidence.update(overrides)
    return evidence


def _temp_evidence(plan, **overrides):
    parent, name = plan.target_path.rsplit('/', 1)
    evidence = {
        'temp_path': '%s/%s.%s.tmp' % (parent, name, plan.txn_id),
        'temp_sha256': plan.candidate_sha256,
        'temp_lines': plan.candidate_lines,
        'temp_bytes': plan.candidate_bytes,
    }
    evidence.update(overrides)
    return evidence


def _append_evidence(content=APPEND_CONTENT, **overrides):
    raw = content.encode('utf-8')
    evidence = {
        'preimage_prefix_verified': True,
        'append_boundary_verified': True,
        'append_content': content,
        'append_content_sha256': hashlib.sha256(raw).hexdigest(),
        'append_content_bytes': len(raw),
        'append_content_lines': content.count('\n'),
    }
    evidence.update(overrides)
    return evidence


def _replaced_evidence(plan, **overrides):
    evidence = {
        'replaced_at': REPLACED_AT,
        'operation_verified': True,
    }
    if plan.operation == APPEND:
        evidence.update(_append_evidence())
    elif plan.operation == SNAPSHOT:
        evidence.update({
            'snapshot_verified': True,
            'canonical_target_unchanged': True,
        })
    else:
        evidence['rewrite_complete_verified'] = True
    evidence.update(overrides)
    return evidence


def _manifest_pending(plan):
    if plan.manifest_required:
        return {'manifest_pending_at': REPLACED_AT}
    return {
        'manifest_pending_at': REPLACED_AT,
        'manifest_skipped_reason': 'la prueba no toca el manifiesto',
    }


def _manifest_verified(plan):
    if plan.manifest_required:
        return {
            'manifest_observed_pre_sha256': plan.manifest_expected_sha256,
            'manifest_sha256': plan.manifest_candidate_sha256,
            'manifest_verified': True,
        }
    return {}


def _pins_evidence(plan):
    if plan.pins_required:
        values = _pins_values(plan)
        return {
            'pins_applied': False,
            'pins_proposed_sha256': canonical_sha256(
                values, 'pins_proposed_values'),
            'pins_symbols': list(PINS_SYMBOLS),
            'pins_proposed_values': values,
            'pins_source_sha256': plan.pins_expected_sha256,
        }
    return {
        'pins_applied': False,
        'pins_skipped_reason':
            'los pins se revisan fuera de la transacción',
    }


def _steps(plan):
    return [
        (PREIMAGE_VERIFIED, {
            'observed_pre_sha256': plan.expected_pre_sha256,
            'observed_pre_lines': plan.expected_pre_lines,
            'observed_pre_bytes': plan.expected_pre_bytes,
        }),
        (BACKUP_VERIFIED, _backup_evidence(plan)),
        (TEMP_VERIFIED, _temp_evidence(plan)),
        (REPLACED, _replaced_evidence(plan)),
        (POST_VERIFIED, {
            'post_sha256': plan.candidate_sha256,
            'post_lines': plan.candidate_lines,
            'post_bytes': plan.candidate_bytes,
        }),
        (MANIFEST_PENDING, _manifest_pending(plan)),
        (MANIFEST_VERIFIED, _manifest_verified(plan)),
        (PINS_PROPOSED, _pins_evidence(plan)),
        (COMMITTED, {'committed_at': COMMITTED_AT}),
    ]


def _apply_steps(record, steps, fail_at=None):
    for state, evidence in steps:
        if state == fail_at:
            return record, state
        record = transition(record, state, evidence)
    return record, None


def _frames(plan=None, stop_before=None):
    if plan is None:
        plan = _plan()
    record = _record_for(plan)
    frames = [record]
    for state, evidence in _steps(plan):
        if state == stop_before:
            break
        record = transition(record, state, evidence)
        frames.append(record)
    return frames


def _committed_record(plan=None):
    return assert_committed(_frames(plan)[-1])


def _journal_entries(frames):
    entries = []
    previous = JOURNAL_GENESIS_SHA256
    for sequence, frame in enumerate(frames):
        entry = journal_record_from_transaction(frame, sequence, previous)
        entries.append(entry)
        previous = entry['record_sha256']
    return entries


def _journal_chain(plan=None, stop_before=None):
    return _journal_entries(_frames(plan, stop_before=stop_before))


def _reseal(entry):
    changed = dict(entry)
    changed['evidence_sha256'] = canonical_sha256(changed['evidence'],
                                                  'evidence')
    changed['record_sha256'] = journal_record_sha256(changed)
    return changed


def _raw_journal(plan, sequence, state, previous, evidence,
                 authority_id='a' * 32, transaction_uid='b' * 32):
    record = {
        'schema_version': JOURNAL_SCHEMA_VERSION,
        'contract_version': CONTRACT_VERSION,
        'txn_id': plan.txn_id,
        'plan_fingerprint': plan_fingerprint(plan),
        'authority_id': authority_id,
        'transaction_uid': transaction_uid,
        'sequence': sequence,
        'state': state,
        'previous_sha256': previous,
        'evidence': evidence,
        'evidence_sha256': canonical_sha256(evidence, 'evidence'),
    }
    record['record_sha256'] = journal_record_sha256(record)
    return record


class Harness:
    """Arnés mínimo: la base solo cambia en `replaced`."""

    def __init__(self, plan=None):
        self.plan = plan or _plan()
        self.record = _record_for(self.plan)
        self.steps = _steps(self.plan)
        self.target = 'PREIMAGEN'
        self.replaced = False

    def apply_until(self, fail_at=None):
        for state, evidence in self.steps:
            if state == fail_at:
                return state
            self.record = transition(self.record, state, evidence)
            if state == REPLACED:
                self.target = 'POSTIMAGEN'
                self.replaced = True
        return None


def test_happy_path_reaches_committed():
    record = _committed_record()
    assert record.state == COMMITTED
    assert record.history == (
        PREPARED, PREIMAGE_VERIFIED, BACKUP_VERIFIED, TEMP_VERIFIED,
        REPLACED, POST_VERIFIED, MANIFEST_PENDING, MANIFEST_VERIFIED,
        PINS_PROPOSED, COMMITTED,
    )
    assert record.evidence['post_sha256'] == HASH_POST
    assert record.evidence['post_bytes'] == REWRITE_POST_BYTES
    assert record.evidence['operation_verified'] is True
    assert CONTRACT_VERSION == 'F0.5 (2026-11-12)'


@pytest.mark.parametrize('target,manifest_required,pins_required', [
    (TARGET_DB, True, True),
    (TARGET_PROFILE_RANGES, True, False),
])
def test_happy_path_with_manifest_and_pins(target, manifest_required,
                                          pins_required):
    plan = _plan(target_path=target)
    record = _committed_record(plan)
    assert record.state == COMMITTED
    assert record.evidence['manifest_required'] is manifest_required
    assert record.evidence['pins_required'] is pins_required
    if pins_required:
        assert record.evidence['pins_proposed_values']['HANDS_DB_SHA256'] == \
            HASH_POST
        assert record.evidence['pins_proposed_values']['HANDS_DB_LINEAS'] == \
            REWRITE_POST_LINES


def test_cannot_skip_a_state():
    plan = _plan()
    with pytest.raises(WriteContractError):
        transition(_record_for(plan), BACKUP_VERIFIED,
                   _backup_evidence(plan))


def test_preimage_mismatch_is_terminal_cas_conflict():
    plan = _plan()
    record = _record_for(plan)
    bad = {
        'observed_pre_sha256': HASH_POST,
        'observed_pre_lines': REWRITE_POST_LINES,
        'observed_pre_bytes': PRE_BYTES,
    }
    with pytest.raises(CasConflict) as caught:
        transition(record, PREIMAGE_VERIFIED, bad)
    conflict = caught.value.record
    assert conflict is not None
    assert conflict.state == CAS_CONFLICT
    assert conflict.history == (PREPARED, CAS_CONFLICT)
    assert CAS_CONFLICT in TERMINAL_STATES
    assert TRANSITIONS[CAS_CONFLICT] == ()
    with pytest.raises(WriteContractError):
        transition(conflict, PREIMAGE_VERIFIED, {
            'observed_pre_sha256': HASH_PRE,
            'observed_pre_lines': REWRITE_POST_LINES,
            'observed_pre_bytes': PRE_BYTES,
        })
    with pytest.raises(WriteContractError):
        assert_committed(conflict)
    direct = transition(_record(), CAS_CONFLICT, bad)
    assert direct.state == CAS_CONFLICT
    entries = _journal_entries([record, conflict])
    assert recovery_action(entries, plan=plan) == CAS_CONFLICT


def test_cas_conflict_invalidates_original_and_any_copy():
    """D1: el registro original y sus copias no pueden seguir tras el CAS."""
    plan = _plan()
    original = _record_for(plan)
    bad = {
        'observed_pre_sha256': HASH_POST,
        'observed_pre_lines': REWRITE_POST_LINES,
        'observed_pre_bytes': PRE_BYTES,
    }
    good = {
        'observed_pre_sha256': HASH_PRE,
        'observed_pre_lines': REWRITE_POST_LINES,
        'observed_pre_bytes': PRE_BYTES,
    }
    with pytest.raises(CasConflict) as caught:
        transition(original, PREIMAGE_VERIFIED, bad)
    conflict = caught.value.record
    assert conflict.state == CAS_CONFLICT

    # 1. El registro original no puede continuar.
    with pytest.raises(WriteContractError):
        transition(original, PREIMAGE_VERIFIED, good)
    with pytest.raises(WriteContractError):
        _apply_steps(original, _steps(plan))

    # 2. Una copia equivalente conserva el authority_id invalidado.
    copied = replace(original)
    assert copied.authority_id == original.authority_id
    with pytest.raises(WriteContractError):
        transition(copied, PREIMAGE_VERIFIED, good)

    shallow_copy = copy.copy(original)
    with pytest.raises(WriteContractError):
        transition(shallow_copy, PREIMAGE_VERIFIED, good)

    # 3. Una copia construida a mano con la misma autoridad tampoco avanza.
    manual = TransactionRecord(
        state=original.state,
        plan=original.plan,
        evidence=original.evidence,
        history=original.history,
        authority_id=original.authority_id,
        transaction_uid=original.transaction_uid,
    )
    with pytest.raises(WriteContractError):
        transition(manual, PREIMAGE_VERIFIED, good)

    # 4. Sin autoridad registrada no hay transición posible.
    orphan = TransactionRecord(
        state=original.state,
        plan=original.plan,
        evidence=original.evidence,
        history=original.history,
        authority_id='',
    )
    with pytest.raises(WriteContractError):
        transition(orphan, PREIMAGE_VERIFIED, good)

    # 5. Ninguna ruta alcanza committed.
    with pytest.raises(WriteContractError):
        assert_committed(original)
    with pytest.raises(WriteContractError):
        assert_committed(conflict)
    with pytest.raises(WriteContractError):
        assert_committed(copied)


@pytest.mark.parametrize('field,value', [
    ('observed_pre_sha256', HASH_POST),
    ('observed_pre_lines', 9),
    ('observed_pre_bytes', PRE_BYTES - 1),
])
def test_each_cas_field_mismatch_is_terminal(field, value):
    evidence = {
        'observed_pre_sha256': HASH_PRE,
        'observed_pre_lines': REWRITE_POST_LINES,
        'observed_pre_bytes': PRE_BYTES,
    }
    evidence[field] = value
    with pytest.raises(CasConflict) as caught:
        transition(_record(), PREIMAGE_VERIFIED, evidence)
    assert caught.value.record.state == CAS_CONFLICT


def test_backup_must_be_the_verified_preimage_and_txn():
    plan = _plan()
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:1])
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED,
                   _backup_evidence(plan, backup_sha256=HASH_POST))
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED,
                   _backup_evidence(plan, backup_txn_id='otro-txn'))
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED,
                   _backup_evidence(plan, backup_path=TARGET_DB))
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED,
                   _backup_evidence(plan,
                                    backup_disposition='preexisting_other'))


@pytest.mark.parametrize('path', [
    'data/_backup/../_backup/txn-f0.jsonl',
    'data/_backup/otro.jsonl',
    'data/otro/txn-f0.jsonl',
    'data/_backupX/txn-f0.jsonl',
    'data/_backup',
])
def test_backup_path_must_be_canonical_owned_and_under_backup_root(path):
    """D5: `data/_backupX` no es `data/_backup`; el límite es de directorio."""
    plan = _plan()
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:1])
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED,
                   _backup_evidence(plan, backup_path=path))


def test_backup_path_inside_backup_root_is_accepted():
    plan = _plan()
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:1])
    accepted = transition(record, BACKUP_VERIFIED, _backup_evidence(plan))
    assert accepted.state == BACKUP_VERIFIED


def test_cross_drive_path_is_a_contract_error():
    """D5: otra unidad de Windows no puede escapar como ValueError crudo."""
    if os.name != 'nt':
        pytest.skip('la prueba de unidad distinta es específica de Windows')
    with pytest.raises(WriteContractError):
        _plan(target_path='Z:/fuera/hands_db.jsonl').validate()


def test_target_backup_and_temp_collisions_are_rejected():
    plan = _plan()
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:2])
    backup_path = _backup_evidence(plan)['backup_path']
    with pytest.raises(WriteContractError):
        transition(record, TEMP_VERIFIED,
                   _temp_evidence(plan, temp_path=backup_path))
    with pytest.raises(WriteContractError):
        transition(record, TEMP_VERIFIED,
                   _temp_evidence(plan,
                                  temp_path='data/_backup/%s.tmp'
                                  % plan.txn_id))
    with pytest.raises(WriteContractError):
        transition(record, TEMP_VERIFIED,
                   _temp_evidence(plan, temp_path=plan.target_path))

    plan2 = _plan()
    record2, _ = _apply_steps(_record_for(plan2), _steps(plan2)[:1])
    with pytest.raises(WriteContractError):
        transition(record2, BACKUP_VERIFIED,
                   _backup_evidence(plan2, backup_path=plan2.target_path))


def test_temp_and_post_must_match_candidate_and_paths():
    plan = _plan()
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:2])
    with pytest.raises(WriteContractError):
        transition(record, TEMP_VERIFIED,
                   _temp_evidence(plan, temp_sha256=HASH_PRE))
    with pytest.raises(WriteContractError):
        transition(record, TEMP_VERIFIED,
                   _temp_evidence(plan, temp_path=TARGET_DB))
    with pytest.raises(WriteContractError):
        transition(record, TEMP_VERIFIED,
                   _temp_evidence(
                       plan,
                       temp_path='data/../data/hands_db.jsonl.txn-f0.tmp'))

    record, _ = _apply_steps(record, _steps(plan)[2:4])
    with pytest.raises(WriteContractError):
        transition(record, POST_VERIFIED, {
            'post_sha256': HASH_PRE,
            'post_lines': plan.candidate_lines,
            'post_bytes': plan.candidate_bytes,
        })


def test_after_replace_only_quarantine_is_allowed():
    plan = _plan()
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:4])
    with pytest.raises(WriteContractError):
        transition(record, FAILED, {'failure_reason': 'fallo tardío'})
    quarantined = transition(record, QUARANTINED, {
        'quarantine_reason': 'la base ya fue reemplazada y no verifica',
    })
    assert quarantined.state == QUARANTINED
    with pytest.raises(WriteContractError):
        assert_committed(quarantined)


def test_manifest_requires_verifiable_evidence():
    plan = _plan()
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:6])
    with pytest.raises(WriteContractError):
        transition(record, MANIFEST_VERIFIED, {
            'manifest_sha256': HASH_MANIFEST_POST,
            'manifest_verified': True,
        })


def test_manifest_path_is_bound_to_target_manifest():
    with pytest.raises(WriteContractError):
        _plan(
            manifest_required=True,
            manifest_path='data/otro_manifiesto.json',
        ).validate()


def test_manifest_pending_cannot_be_skipped():
    plan = _plan()
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:5])
    with pytest.raises(WriteContractError):
        transition(record, MANIFEST_VERIFIED, {})


def test_pins_are_proposed_not_applied_and_bound_to_values():
    plan = _plan()
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:7])
    base = _pins_evidence(plan)
    with pytest.raises(WriteContractError):
        transition(record, PINS_PROPOSED, dict(base, pins_applied=True))
    with pytest.raises(WriteContractError):
        transition(record, PINS_PROPOSED, dict(
            base, pins_symbols=[PINS_SYMBOLS[0]]))
    with pytest.raises(WriteContractError):
        transition(record, PINS_PROPOSED, dict(
            base, pins_proposed_sha256=HASH_PINS_SOURCE))
    with pytest.raises(WriteContractError):
        transition(record, PINS_PROPOSED, dict(
            base, pins_proposed_values=dict(
                _pins_values(plan), HANDS_DB_SHA256=HASH_PRE)))
    with pytest.raises(WriteContractError):
        transition(record, PINS_PROPOSED, dict(
            base, pins_proposed_values=dict(
                _pins_values(plan), HANDS_DB_LINEAS=11)))
    with pytest.raises(WriteContractError):
        transition(record, PINS_PROPOSED, dict(
            base, pins_source_sha256='no-es-sha'))
    with pytest.raises(WriteContractError):
        transition(record, PINS_PROPOSED, dict(
            base, pins_source_sha256=HASH_PRE))
    assert transition(record, PINS_PROPOSED, base).evidence['pins_applied'] \
        is False


@pytest.mark.parametrize('symbols', [
    [PINS_SYMBOLS[0], PINS_SYMBOLS[0], PINS_SYMBOLS[1], PINS_SYMBOLS[2]],
    [PINS_SYMBOLS[0], PINS_SYMBOLS[1]],
    list(PINS_SYMBOLS) + ['OTRO'],
])
def test_pins_reject_duplicates_omissions_and_extra_symbols(symbols):
    """D8: la comparación de conjuntos aceptaba duplicados."""
    plan = _plan()
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:7])
    base = _pins_evidence(plan)
    with pytest.raises(WriteContractError):
        transition(record, PINS_PROPOSED,
                   dict(base, pins_symbols=symbols))


def test_pins_reject_extra_or_missing_values():
    plan = _plan()
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:7])
    base = _pins_evidence(plan)
    values = dict(_pins_values(plan), EXTRA='x')
    with pytest.raises(WriteContractError):
        transition(record, PINS_PROPOSED, dict(
            base,
            pins_proposed_values=values,
            pins_proposed_sha256=canonical_sha256(
                values, 'pins_proposed_values'),
        ))
    values = dict(_pins_values(plan))
    values.pop('HANDS_DB_COMMIT')
    with pytest.raises(WriteContractError):
        transition(record, PINS_PROPOSED, dict(
            base,
            pins_proposed_values=values,
            pins_proposed_sha256=canonical_sha256(
                values, 'pins_proposed_values'),
        ))


def test_plan_fields_cannot_be_overridden_by_evidence():
    plan = _plan()
    evidence = {
        'observed_pre_sha256': HASH_PRE,
        'observed_pre_lines': REWRITE_POST_LINES,
        'observed_pre_bytes': PRE_BYTES,
        'manifest_required': False,
    }
    with pytest.raises(WriteContractError):
        transition(_record_for(plan), PREIMAGE_VERIFIED, evidence)


def test_verified_evidence_cannot_be_overwritten():
    plan = _plan()
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:1])
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED,
                   dict(_backup_evidence(plan),
                        observed_pre_sha256=HASH_PRE))


def test_committed_cannot_be_forged_with_invalid_history_or_evidence():
    committed = _committed_record()
    with pytest.raises(WriteContractError):
        assert_committed(TransactionRecord(
            state=COMMITTED,
            plan=committed.plan,
            evidence=committed.evidence,
            history=(PREPARED, COMMITTED),
        ))
    evidence = committed.as_dict()['evidence']
    evidence['backup_txn_id'] = 'otro-txn'
    with pytest.raises(WriteContractError):
        assert_committed(TransactionRecord(
            state=COMMITTED,
            plan=committed.plan,
            evidence=evidence,
            history=committed.history,
        ))
    evidence = committed.as_dict()['evidence']
    evidence['manifest_required'] = 1
    with pytest.raises(WriteContractError):
        assert_committed(TransactionRecord(
            state=COMMITTED,
            plan=committed.plan,
            evidence=evidence,
            history=committed.history,
        ))


def test_retries_are_idempotent_but_terminal_retries_fail():
    record = _record()
    assert transition(record, PREPARED, {}) is record
    with pytest.raises(WriteContractError):
        transition(record, PREPARED, {'abort_reason': 'no aplica'})
    with pytest.raises(WriteContractError):
        transition(_committed_record(), COMMITTED, {})


def test_terminal_states_do_not_transition():
    for terminal in TERMINAL_STATES:
        if terminal == COMMITTED:
            record = _committed_record()
        elif terminal == CAS_CONFLICT:
            with pytest.raises(CasConflict) as caught:
                transition(_record(), PREIMAGE_VERIFIED, {
                    'observed_pre_sha256': HASH_POST,
                    'observed_pre_lines': REWRITE_POST_LINES,
                    'observed_pre_bytes': PRE_BYTES,
                })
            record = caught.value.record
        elif terminal == ABORTED:
            record = transition(_record(), ABORTED,
                                {'abort_reason': 'prueba'})
        elif terminal == FAILED:
            record = transition(_record(), FAILED,
                                {'failure_reason': 'prueba'})
        else:
            record = transition(_record(), QUARANTINED,
                                {'quarantine_reason': 'prueba'})
        assert TRANSITIONS[terminal] == ()
        with pytest.raises(WriteContractError):
            transition(record, PREPARED, {})


def test_plan_rejects_invalid_hashes_lines_bytes_operations_and_paths():
    with pytest.raises(WriteContractError):
        _plan(expected_pre_sha256='a').validate()
    with pytest.raises(WriteContractError):
        _plan(candidate_lines=-1).validate()
    with pytest.raises(WriteContractError):
        _plan(expected_pre_bytes=-1).validate()
    with pytest.raises(WriteContractError):
        _plan(operation='delete').validate()
    with pytest.raises(WriteContractError):
        _plan(manifest_required=True, manifest_path=None).validate()
    with pytest.raises(WriteContractError):
        _plan(pins_required=True, pins_path=None).validate()
    with pytest.raises(WriteContractError):
        _plan(pins_required=True, pins_expected_sha256=None).validate()
    with pytest.raises(WriteContractError):
        _plan(target_path='data/otro.json').validate()
    with pytest.raises(WriteContractError):
        _plan(target_path='data/../data/hands_db.jsonl').validate()
    with pytest.raises(WriteContractError):
        _plan(target_path=os.path.abspath(TARGET_DB)).validate()
    with pytest.raises(WriteContractError):
        _plan(txn_id='../txn').validate()


@pytest.mark.parametrize('overrides', [
    {'manifest_required': False},
    {'pins_required': False},
])
def test_base_target_cannot_weaken_manifest_or_pins(overrides):
    """D4: los flags del caller no pueden debilitar TARGET_POLICIES."""
    with pytest.raises(WriteContractError):
        _plan(**overrides).validate()


def test_plan_requires_a_validated_writer_declaration():
    """D4: sin declaración, con otro target o incompleta no hay plan."""
    with pytest.raises(WriteContractError):
        _plan(writer_declaration=None).validate()
    other = _declaration(target=TARGET_MANIFEST, operation=REWRITE)
    with pytest.raises(WriteContractError):
        _plan(writer_declaration=other).validate()
    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='destino-desconocido', operation=REWRITE,
            targets=('data/otro.json',),
            requires_lock=True, requires_cas=True, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=False,
        )
    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='incompleta', operation=REWRITE, targets=(TARGET_DB,),
            requires_lock=None, requires_cas=True, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=True,
        )


def test_plan_flags_must_match_the_validated_declaration():
    """D4: la declaración no puede exigir más de lo que el plan ejecuta."""
    policy = TARGET_POLICIES[TARGET_PROFILE_RANGES]
    stronger = WriterDeclaration(
        name='writer-de-prueba', operation=REWRITE,
        targets=(TARGET_PROFILE_RANGES,),
        requires_lock=policy.requires_lock,
        requires_cas=policy.requires_cas,
        requires_backup=policy.requires_backup,
        requires_manifest_verification=True,
        requires_pins_proposal=True,
    )
    with pytest.raises(WriteContractError):
        _plan(target_path=TARGET_PROFILE_RANGES,
              writer_declaration=stronger).validate()


def test_plan_binds_effective_target_policy():
    """D4: el plan fija el fingerprint de la política efectiva del destino."""
    plan = _plan()
    record = _record_for(plan)
    assert record.evidence['target_policy_fingerprint'] == \
        plan_policy_fingerprint(plan)
    assert record.evidence['target_policy_fingerprint'] == \
        target_policy_fingerprint(TARGET_DB)
    derived = _plan(target_path=TARGET_PROFILE_RANGES)
    derived_record = _record_for(derived)
    assert derived_record.evidence['target_policy_fingerprint'] == \
        target_policy_fingerprint(TARGET_PROFILE_RANGES)
    snapshot = _plan(operation=SNAPSHOT)
    snapshot_record = _record_for(snapshot)
    assert snapshot_record.evidence['target_policy_fingerprint'] == \
        plan_policy_fingerprint(snapshot)
    forged = record.as_dict()['evidence']
    forged['target_policy_fingerprint'] = 'f' * 64
    with pytest.raises(WriteContractError):
        transition(TransactionRecord(
            state=PREPARED, plan=plan, evidence=forged,
            history=(PREPARED,)), PREIMAGE_VERIFIED, {
                'observed_pre_sha256': HASH_PRE,
                'observed_pre_lines': REWRITE_POST_LINES,
                'observed_pre_bytes': PRE_BYTES,
            })


def test_writer_targets_are_frozen_and_validation_survives_mutation():
    """D4: mutar la colección original no cambia la declaración validada."""
    targets = [TARGET_DB]
    policy = TARGET_POLICIES[TARGET_DB]
    declaration = WriterDeclaration(
        name='writer-de-prueba', operation=REWRITE, targets=targets,
        requires_lock=policy.requires_lock,
        requires_cas=policy.requires_cas,
        requires_backup=policy.requires_backup,
        requires_manifest_verification=policy.requires_manifest_verification,
        requires_pins_proposal=policy.requires_pins_proposal,
    )
    targets.append(TARGET_PROFILE_RANGES)
    assert declaration.targets == (TARGET_DB,)
    assert declaration.validate() is declaration
    with pytest.raises(TypeError):
        declaration.targets[0] = TARGET_PROFILE_RANGES
    with pytest.raises(AttributeError):
        declaration.targets = (TARGET_PROFILE_RANGES,)


def test_plan_cannot_be_weakened_after_construction():
    """D4: el plan y su política quedan congelados y se revalidan."""
    plan = _plan()
    with pytest.raises(AttributeError):
        plan.manifest_required = False
    with pytest.raises(AttributeError):
        plan.pins_required = False
    with pytest.raises(AttributeError):
        plan.writer_declaration.requires_pins_proposal = False
    with pytest.raises(AttributeError):
        plan.lock_policy.timeout_seconds = 0
    with pytest.raises(WriteContractError):
        _plan(manifest_required=False).validate()
    with pytest.raises(WriteContractError):
        _plan(pins_required=False).validate()
    with pytest.raises(WriteContractError):
        _plan(target_path=TARGET_PROFILE_RANGES,
              pins_required=True).validate()

    weakened = _plan()
    object.__setattr__(weakened, 'manifest_required', False)
    with pytest.raises(WriteContractError):
        weakened.validate()
    weakened = _plan(lock_policy=type(DEFAULT_LOCK_POLICY)())
    object.__setattr__(weakened.lock_policy, 'timeout_seconds', 0)
    with pytest.raises(WriteContractError):
        weakened.validate()


def test_append_and_snapshot_operation_semantics():
    with pytest.raises(WriteContractError):
        _plan(operation=APPEND, candidate_bytes=PRE_BYTES - 1).validate()
    with pytest.raises(WriteContractError):
        _plan(operation=APPEND, candidate_lines=9).validate()
    with pytest.raises(WriteContractError):
        _plan(operation=APPEND, candidate_bytes=PRE_BYTES,
              candidate_lines=APPEND_POST_LINES).validate()
    with pytest.raises(WriteContractError):
        _plan(operation=APPEND, candidate_lines=REWRITE_POST_LINES).validate()
    assert _plan(operation=APPEND).validate().operation == APPEND
    with pytest.raises(WriteContractError):
        _plan(operation=SNAPSHOT, target_path=TARGET_DB).validate()
    with pytest.raises(WriteContractError):
        _plan(operation=SNAPSHOT, candidate_sha256=HASH_POST).validate()
    snapshot = _plan(operation=SNAPSHOT)
    assert snapshot.validate().snapshot_of == TARGET_DB


def test_append_content_binds_bytes_hash_lines_and_deltas():
    """D7: mismo hash/bytes con candidate_lines distinto no puede avanzar."""
    plan = _plan(operation=APPEND)
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:3])
    base = _replaced_evidence(plan)
    assert transition(record, REPLACED, base).state == REPLACED

    with pytest.raises(WriteContractError):
        transition(record, REPLACED,
                   dict(base, append_content_lines=APPEND_LINES + 1))
    with pytest.raises(WriteContractError):
        transition(record, REPLACED,
                   dict(base, append_content_sha256=HASH_PRE))
    with pytest.raises(WriteContractError):
        transition(record, REPLACED,
                   dict(base, append_content_bytes=APPEND_BYTES + 1))

    inconsistent = _plan(operation=APPEND,
                         candidate_lines=APPEND_POST_LINES + 1)
    inconsistent_record, _ = _apply_steps(
        _record_for(inconsistent), _steps(inconsistent)[:3])
    with pytest.raises(WriteContractError):
        transition(inconsistent_record, REPLACED,
                   _replaced_evidence(inconsistent))


def test_append_rejects_empty_and_missing_final_newline():
    with pytest.raises(WriteContractError):
        _plan(operation=APPEND, candidate_bytes=PRE_BYTES,
              candidate_lines=APPEND_POST_LINES,
              candidate_sha256=HASH_PRE).validate()
    with pytest.raises(WriteContractError):
        _plan(operation=APPEND, candidate_bytes=PRE_BYTES + 1,
              candidate_lines=REWRITE_POST_LINES).validate()

    plan = _plan(operation=APPEND)
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:3])
    base = _replaced_evidence(plan)
    content = APPEND_CONTENT.rstrip('\n')
    raw = content.encode('utf-8')
    with pytest.raises(WriteContractError):
        transition(record, REPLACED, dict(
            base,
            append_content=content,
            append_content_sha256=hashlib.sha256(raw).hexdigest(),
            append_content_bytes=len(raw),
            append_content_lines=content.count('\n'),
        ))


def test_operation_evidence_is_required_before_replace():
    plan = _plan()
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:3])
    with pytest.raises(WriteContractError):
        transition(record, REPLACED, {
            'replaced_at': REPLACED_AT,
            'operation_verified': True,
        })
    with pytest.raises(WriteContractError):
        transition(record, REPLACED, dict(
            _replaced_evidence(plan), rewrite_complete_verified=False))

    append_plan = _plan(operation=APPEND)
    append_record, _ = _apply_steps(
        _record_for(append_plan), _steps(append_plan)[:3])
    with pytest.raises(WriteContractError):
        transition(append_record, REPLACED, {
            'replaced_at': REPLACED_AT,
            'operation_verified': True,
        })


def test_writer_declaration_fails_closed_for_all_target_categories():
    valid = _declaration(target=TARGET_DB)
    assert validate_writer_declaration(valid) is valid

    for target in (TARGET_PROFILE_RANGES, TARGET_POSTFLOP_RANGES,
                   TARGET_MANIFEST):
        with pytest.raises(WriteContractError):
            WriterDeclaration(
                name='sin-controles', operation=REWRITE, targets=(target,),
                requires_lock=False, requires_cas=False,
                requires_backup=False,
                requires_manifest_verification=False,
                requires_pins_proposal=False,
            )

    derived = _declaration(target=TARGET_POSTFLOP_RANGES)
    assert derived.validate() is derived

    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='destino-desconocido', operation=REWRITE,
            targets=('data/otro.json',),
            requires_lock=True, requires_cas=True, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=False,
        )
    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='manifiesto-append', operation=APPEND,
            targets=(TARGET_MANIFEST,),
            requires_lock=True, requires_cas=True, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=False,
        )
    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='alias', operation=REWRITE,
            targets=('data/../data/hands_db.jsonl',),
            requires_lock=True, requires_cas=True, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=True,
        )

    for attribute in ('requires_lock', 'requires_cas', 'requires_backup',
                      'requires_pins_proposal'):
        policy = TARGET_POLICIES[TARGET_DB]
        values = {
            'requires_lock': policy.requires_lock,
            'requires_cas': policy.requires_cas,
            'requires_backup': policy.requires_backup,
            'requires_manifest_verification':
                policy.requires_manifest_verification,
            'requires_pins_proposal': policy.requires_pins_proposal,
        }
        values[attribute] = False
        with pytest.raises(WriteContractError):
            WriterDeclaration(
                name='sin-%s' % attribute, operation=REWRITE,
                targets=(TARGET_DB,), **values)

    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='snapshot-sin-backup', operation=SNAPSHOT,
            targets=(TARGET_DB,), requires_lock=True, requires_cas=True,
            requires_backup=False,
            requires_manifest_verification=False,
            requires_pins_proposal=False,
        )


def test_lock_policy_is_finite_and_validated_at_every_entry_point():
    """D6: NaN, infinito, cero, negativos y no numéricos no son timeouts."""
    for timeout in (float('nan'), float('inf'), float('-inf'), 0, -1,
                    '30', True, None):
        with pytest.raises(WriteContractError):
            type(DEFAULT_LOCK_POLICY)(timeout_seconds=timeout)
    assert DEFAULT_LOCK_POLICY.validate() is DEFAULT_LOCK_POLICY


def test_mutated_lock_policy_is_rejected_at_all_entry_points():
    """D6: la validación no depende solo de calcular el fingerprint."""
    policy = type(DEFAULT_LOCK_POLICY)()
    object.__setattr__(policy, 'timeout_seconds', float('nan'))
    with pytest.raises(WriteContractError):
        policy.validate()
    with pytest.raises(WriteContractError):
        lock_policy_fingerprint(policy)
    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='lock-mutado', operation=REWRITE, targets=(TARGET_DB,),
            requires_lock=True, requires_cas=True, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=True,
            lock_policy=policy,
        )


def test_plan_lock_policy_must_match_validated_writer():
    custom = type(DEFAULT_LOCK_POLICY)(timeout_seconds=1.0)
    declaration = _declaration(lock_policy=DEFAULT_LOCK_POLICY)
    with pytest.raises(WriteContractError):
        _plan(lock_policy=custom,
              writer_declaration=declaration).validate()
    assert _plan(lock_policy=custom).validate().lock_policy == custom


def test_lock_policy_fingerprint_is_bound_to_plan_and_journal():
    plan = _plan()
    chain = _journal_chain(plan)
    other = _plan(lock_policy=type(DEFAULT_LOCK_POLICY)(timeout_seconds=1.0))
    assert plan_fingerprint(plan) != plan_fingerprint(other)
    assert lock_policy_fingerprint(plan.lock_policy) != \
        lock_policy_fingerprint(other.lock_policy)
    with pytest.raises(WriteContractError):
        validate_journal_chain(chain, plan=other)


def test_lock_and_recovery_policy_is_fail_closed_and_bound_to_plan():
    assert LOCK_MECHANISM == 'windows_named_mutex'
    assert LOCK_NAME == r'Global\Poker.HandsDB.v1'
    assert LOCK_FALLBACKS_ALLOWED is False
    assert LOCK_MULTI_HOST_ALLOWED is False
    assert LOCK_WAIT_ABANDONED_POLICY == 'recover_then_write'
    assert LOCK_FAILURE_POLICY == 'abort_visible'
    assert LOCK_TIMEOUT_SECONDS == 30.0
    assert LOCK_ACL_REQUIRED is True
    assert LOCK_SID_REQUIRED is True
    assert READER_POLICY == 'verified_snapshot_under_exclusive_mutex'
    assert JOURNAL_RECOVERY_POLICY == 'quarantine_no_auto_restore'
    assert JOURNAL_PLAN_BINDING_POLICY == 'plan_fingerprint_required'
    assert (JOURNAL_EVIDENCE_BINDING_POLICY ==
            'state_evidence_and_sha256_required')
    assert PINS_RUNTIME_UPDATE_ALLOWED is False

    for invalid in (
        {'fallbacks_allowed': True},
        {'multi_host_allowed': True},
        {'timeout_seconds': 0},
        {'acl_required': False},
        {'sid_required': False},
        {'name': 'otro-mutex'},
    ):
        with pytest.raises(WriteContractError):
            type(DEFAULT_LOCK_POLICY)(**invalid)

    plan = _plan()
    record = _record_for(plan)
    assert record.evidence['lock_policy_fingerprint'] == \
        lock_policy_fingerprint(plan.lock_policy)
    forged = record.as_dict()['evidence']
    forged['lock_policy_fingerprint'] = 'f' * 64
    with pytest.raises(WriteContractError):
        transition(TransactionRecord(
            state=PREPARED, plan=plan, evidence=forged,
            history=(PREPARED,)), PREIMAGE_VERIFIED, {
                'observed_pre_sha256': HASH_PRE,
                'observed_pre_lines': REWRITE_POST_LINES,
                'observed_pre_bytes': PRE_BYTES,
            })
    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='lock-invalido', operation=REWRITE, targets=(TARGET_DB,),
            requires_lock=True, requires_cas=True, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=True,
            lock_policy=type(DEFAULT_LOCK_POLICY)(fallbacks_allowed=True),
        )


def test_journal_schema_hash_chain_plan_and_truncation():
    plan = _plan()
    chain = _journal_chain(plan)
    assert len(validate_journal_chain(chain, plan=plan)) == len(chain)
    assert validate_journal_record(chain[0], plan=plan)['state'] == PREPARED
    assert chain[0]['plan_fingerprint'] == plan_fingerprint(plan)
    assert chain[0]['evidence_sha256'] == canonical_sha256(
        chain[0]['evidence'], 'evidence')
    assert JOURNAL_TRUNCATION_POLICY == 'quarantine'
    assert JOURNAL_CORRUPTION_POLICY == 'quarantine'
    assert JOURNAL_THIRD_HASH_POLICY == 'quarantine'

    with pytest.raises(WriteContractError):
        validate_journal_chain(chain[:2], expected_records=len(chain),
                               plan=plan)

    corrupt = dict(chain[1])
    corrupt['state'] = BACKUP_VERIFIED
    corrupt = _reseal(corrupt)
    with pytest.raises(WriteContractError):
        validate_journal_record(corrupt, plan=plan)

    third_hash = dict(chain[0])
    third_hash['third_sha256'] = 'f' * 64
    third_hash = _reseal(third_hash)
    with pytest.raises(WriteContractError):
        validate_journal_record(third_hash, plan=plan)


def test_journal_rejects_empty_evidence_and_wrong_plan():
    plan = _plan()
    states = [
        PREPARED, PREIMAGE_VERIFIED, BACKUP_VERIFIED, TEMP_VERIFIED,
        REPLACED, POST_VERIFIED, MANIFEST_PENDING, MANIFEST_VERIFIED,
        PINS_PROPOSED, COMMITTED,
    ]
    empty_chain = []
    previous = JOURNAL_GENESIS_SHA256
    for sequence, state in enumerate(states):
        record = _raw_journal(plan, sequence, state, previous, {})
        empty_chain.append(record)
        previous = record['record_sha256']
    with pytest.raises(WriteContractError):
        validate_journal_record(empty_chain[0], plan=plan)
    assert recovery_action(empty_chain, plan=plan) == QUARANTINED

    valid = _journal_chain(plan)
    other = _plan(candidate_sha256='f' * 64,
                  candidate_bytes=REWRITE_POST_BYTES + 1)
    with pytest.raises(WriteContractError):
        validate_journal_chain(valid, plan=other)
    assert recovery_action(valid, plan=other) == QUARANTINED
    assert recovery_action(valid) == QUARANTINED


def test_journal_without_plan_is_structural_only_not_authorization():
    """D2: sin plan no se autentica el plan ni se autoriza recuperación."""
    plan = _plan()
    chain = _journal_chain(plan)
    assert validate_journal_record(chain[0])['state'] == PREPARED
    assert recovery_action(chain, plan=None) == QUARANTINED
    assert JOURNAL_PARTIAL_VALIDATION_POLICY == (
        'structural_only_without_plan_not_recovery_authorization')

    discrepant = dict(chain[0])
    evidence = dict(discrepant['evidence'])
    evidence['txn_id'] = 'otro-txn'
    discrepant['evidence'] = evidence
    discrepant = _reseal(discrepant)
    with pytest.raises(WriteContractError):
        validate_journal_record(discrepant)
    with pytest.raises(WriteContractError):
        validate_journal_record(discrepant, plan=plan)


def test_journal_rejects_broken_links_bad_transitions_and_removed_evidence():
    plan = _plan()
    frames = _frames(plan)
    chain = _journal_entries(frames)

    broken = dict(chain[1])
    broken['previous_sha256'] = JOURNAL_GENESIS_SHA256
    broken = _reseal(broken)
    with pytest.raises(WriteContractError):
        validate_journal_chain([chain[0], broken], plan=plan)

    replaced = frames[4]
    invalid_transition = journal_record_from_transaction(
        replaced, 1, chain[0]['record_sha256'])
    with pytest.raises(WriteContractError):
        validate_journal_chain([chain[0], invalid_transition], plan=plan)

    changed = dict(chain[-1])
    evidence = dict(changed['evidence'])
    evidence.pop('backup_path')
    changed['evidence'] = evidence
    changed = _reseal(changed)
    with pytest.raises(WriteContractError):
        validate_journal_chain(chain[:-1] + [changed], plan=plan)


def test_recovery_aborts_before_replace_and_quarantines_after():
    plan = _plan()
    frames = _frames(plan)
    before = _journal_entries(frames[:4])
    after = _journal_entries(frames[:5])
    committed = _journal_entries(frames)

    conflict_plan = _plan()
    record = _record_for(conflict_plan)
    with pytest.raises(CasConflict) as caught:
        transition(record, PREIMAGE_VERIFIED, {
            'observed_pre_sha256': HASH_POST,
            'observed_pre_lines': REWRITE_POST_LINES,
            'observed_pre_bytes': PRE_BYTES,
        })
    conflict = _journal_entries([record, caught.value.record])

    assert recovery_action([], plan=plan) == 'noop'
    assert recovery_action(before, plan=plan) == ABORTED
    assert recovery_action(after, plan=plan) == QUARANTINED
    assert recovery_action(committed, plan=plan) == COMMITTED
    assert recovery_action(conflict, plan=conflict_plan) == CAS_CONFLICT
    assert recovery_action(before, expected_records=len(after),
                           plan=plan) == QUARANTINED


@pytest.mark.parametrize('fail_at', [
    PREIMAGE_VERIFIED, BACKUP_VERIFIED, TEMP_VERIFIED,
    REPLACED, POST_VERIFIED, MANIFEST_PENDING, MANIFEST_VERIFIED,
    PINS_PROPOSED,
])
def test_fault_matrix_never_commits_and_preserves_preimage_before_replace(
        fail_at):
    harness = Harness()
    state = harness.apply_until(fail_at=fail_at)
    assert state == fail_at
    assert harness.record.state != COMMITTED
    with pytest.raises(WriteContractError):
        assert_committed(harness.record)
    if fail_at in (PREIMAGE_VERIFIED, BACKUP_VERIFIED, TEMP_VERIFIED,
                   REPLACED):
        assert harness.replaced is False
        assert harness.target == 'PREIMAGEN'
        aborted = transition(harness.record, ABORTED, {
            'abort_reason': 'fallo antes de reemplazar',
        })
        assert aborted.state == ABORTED
    else:
        assert harness.replaced is True
        quarantined = transition(harness.record, QUARANTINED, {
            'quarantine_reason': 'fallo después de reemplazar',
        })
        assert quarantined.state == QUARANTINED


def test_evidence_is_deeply_immutable():
    record = _committed_record()
    with pytest.raises(TypeError):
        record.evidence['pins_proposed_values']['HANDS_DB_LINEAS'] = 11
    with pytest.raises(TypeError):
        record.evidence['pins_symbols'][0] = 'OTRO'
    copied = record.as_dict()['evidence']
    copied['pins_proposed_values']['HANDS_DB_LINEAS'] = 11
    assert record.evidence['pins_proposed_values']['HANDS_DB_LINEAS'] == \
        REWRITE_POST_LINES
    direct = TransactionRecord(
        state=PREPARED,
        plan=_plan(),
        evidence={'nested': {'value': 1}},
        history=(PREPARED,),
    )
    with pytest.raises(TypeError):
        direct.evidence['nested']['value'] = 2


def test_canonical_journal_hash_rejects_ambiguous_json():
    assert journal_record_sha256({'b': 2, 'a': 1}) == \
        journal_record_sha256({'a': 1, 'b': 2})
    with pytest.raises(WriteContractError):
        journal_record_sha256({1: 'x'})
    with pytest.raises(WriteContractError):
        journal_record_sha256({'evidence': {'x': float('nan')}})
    with pytest.raises(WriteContractError):
        journal_record_sha256({'evidence': {'x': float('inf')}})
    with pytest.raises(WriteContractError):
        canonical_sha256({'x': object()})


def test_json_duplicate_key_detection_is_an_f1_requirement():
    """D9: F0 no parsea JSON crudo; el parser estricto es requisito de F1."""
    assert JOURNAL_RAW_JSON_SUPPORTED is False
    assert JOURNAL_JSON_PARSER_REQUIRED is True
    assert JOURNAL_JSON_DUPLICATE_KEYS_POLICY == \
        'reject_with_object_pairs_hook'
    assert JOURNAL_JSON_PARSER_REQUIREMENT == \
        'object_pairs_hook_reject_duplicate_keys'
    raw = '{"a": 1, "a": 2}'
    collapsed = json.loads(raw)
    assert collapsed == {'a': 2}
    assert canonical_sha256(collapsed) == canonical_sha256({'a': 2})


def test_timestamps_require_iso_8601_timezone():
    with pytest.raises(WriteContractError):
        new_transaction(_plan(), '2026-11-12T00:00:00')
    with pytest.raises(WriteContractError):
        new_transaction(_plan(), '2026-11-12')
    assert new_transaction(
        _plan(), '2026-11-12T00:00:00+02:00').state == PREPARED

    plan = _plan()
    record, _ = _apply_steps(_record_for(plan), _steps(plan)[:3])
    with pytest.raises(WriteContractError):
        transition(record, REPLACED, _replaced_evidence(
            plan, replaced_at='2026-11-12T00:00:01'))
    record, _ = _apply_steps(record, _steps(plan)[3:8])
    with pytest.raises(WriteContractError):
        transition(record, COMMITTED, {
            'committed_at': '2026-11-12T00:00:02',
        })


def test_committed_requires_all_postconditions():
    record = _committed_record()
    with pytest.raises(WriteContractError):
        assert_committed(transition(record, PREPARED, {}))
    assert record.evidence['manifest_required'] is True
    assert record.evidence['pins_required'] is True
    assert record.evidence['pins_applied'] is False

def test_d1_malformed_cas_conflict_evidence_still_invalidates():
    plan = _plan()
    record = _record_for(plan)
    bad = {
        'observed_pre_sha256': HASH_POST,
        'observed_pre_lines': REWRITE_POST_LINES,
        'observed_pre_bytes': PRE_BYTES,
        'cas_conflict_at': 'no-es-iso-8601',
    }
    with pytest.raises(WriteContractError):
        transition(record, PREIMAGE_VERIFIED, bad)
    with pytest.raises(WriteContractError):
        transition(record, PREIMAGE_VERIFIED, {
            'observed_pre_sha256': HASH_PRE,
            'observed_pre_lines': REWRITE_POST_LINES,
            'observed_pre_bytes': PRE_BYTES,
        })
    with pytest.raises(WriteContractError):
        assert_committed(record)

    direct = _record()
    with pytest.raises(WriteContractError):
        transition(direct, CAS_CONFLICT, dict(bad, cas_conflict_reason=''))
    with pytest.raises(WriteContractError):
        transition(direct, PREIMAGE_VERIFIED, {
            'observed_pre_sha256': HASH_PRE,
            'observed_pre_lines': REWRITE_POST_LINES,
            'observed_pre_bytes': PRE_BYTES,
        })
    with pytest.raises(WriteContractError):
        assert_committed(direct)


def test_d1_duplicate_txn_id_is_rejected():
    plan = _plan()
    _record_for(plan)
    with pytest.raises(WriteContractError):
        new_transaction(plan, PLANNED_AT)


def test_d1_authority_from_another_transaction_cannot_be_borrowed():
    plan = _plan()
    original = _record_for(plan)
    peer_authority = '1' * 32
    peer_transaction = '2' * 32
    wc._AUTHORITIES[peer_authority] = wc._AuthorityState(
        txn_id=plan.txn_id,
        plan_fingerprint=plan_fingerprint(plan),
        transaction_uid=peer_transaction,
        active=True,
        authorized_history=(PREPARED,),
    )
    forged = replace(original, authority_id=peer_authority)
    with pytest.raises(WriteContractError):
        transition(forged, PREIMAGE_VERIFIED, {
            'observed_pre_sha256': HASH_PRE,
            'observed_pre_lines': REWRITE_POST_LINES,
            'observed_pre_bytes': PRE_BYTES,
        })
    with pytest.raises(WriteContractError):
        assert_committed(forged)


def test_d1_manual_reconstruction_without_transaction_uid_is_rejected():
    record = _record()
    forged = TransactionRecord(
        state=record.state,
        plan=record.plan,
        evidence=record.evidence,
        history=record.history,
        authority_id=record.authority_id,
    )
    with pytest.raises(WriteContractError):
        transition(forged, PREIMAGE_VERIFIED, {
            'observed_pre_sha256': HASH_PRE,
            'observed_pre_lines': REWRITE_POST_LINES,
            'observed_pre_bytes': PRE_BYTES,
        })


def test_d1_invalidated_authority_cannot_emit_commit_journal_or_chain():
    plan = _plan()
    frames = _frames(plan)
    committed = frames[-1]
    entries = _journal_entries(frames)
    assert recovery_action(entries, plan=plan) == COMMITTED

    wc._invalidate_authority(committed.authority_id,
                             (PREPARED, CAS_CONFLICT))
    with pytest.raises(WriteContractError):
        assert_committed(committed)
    with pytest.raises(WriteContractError):
        journal_record_from_transaction(
            committed, len(frames) - 1, entries[-2]['record_sha256'])
    with pytest.raises(WriteContractError):
        validate_journal_chain(entries, plan=plan)
    assert recovery_action(entries, plan=plan) == QUARANTINED


def test_d1_journal_chain_from_another_authority_is_rejected():
    plan_a = _plan()
    plan_b = _plan()
    chain_a = _journal_chain(plan_a)
    chain_b = _journal_chain(plan_b)
    with pytest.raises(WriteContractError):
        validate_journal_chain(chain_a, plan=plan_b)
    with pytest.raises(WriteContractError):
        validate_journal_chain(chain_b, plan=plan_a)
    assert recovery_action(chain_a, plan=plan_b) == QUARANTINED
    assert recovery_action(chain_b, plan=plan_a) == QUARANTINED


def test_d1_txn_reset_audit_identifier_cannot_be_reused():
    """La reproducción independiente queda cerrada en la API normal."""
    plan = _plan(txn_id='txn-reset-audit')
    original = _record_for(plan)
    assert not hasattr(wc, 'reset_authority_registry')
    with pytest.raises(WriteContractError):
        new_transaction(plan, PLANNED_AT)
    assert original.plan.txn_id == 'txn-reset-audit'


def test_d1_invalidation_does_not_release_txn_id():
    plan = _plan(txn_id='txn-invalidated-kept')
    record = _record_for(plan)
    wc._invalidate_authority(record.authority_id)
    with pytest.raises(WriteContractError):
        new_transaction(plan, PLANNED_AT)


def test_d1_normal_transition_does_not_release_txn_id():
    plan = _plan(txn_id='txn-transition-kept')
    record = _record_for(plan)
    transition(record, PREIMAGE_VERIFIED, {
        'observed_pre_sha256': HASH_PRE,
        'observed_pre_lines': REWRITE_POST_LINES,
        'observed_pre_bytes': PRE_BYTES,
    })
    with pytest.raises(WriteContractError):
        new_transaction(plan, PLANNED_AT)


@pytest.mark.parametrize('terminal', [
    ABORTED, FAILED, QUARANTINED, CAS_CONFLICT, COMMITTED,
])
def test_d1_terminal_transaction_does_not_release_txn_id(terminal):
    plan = _plan(txn_id='txn-terminal-kept')
    if terminal == COMMITTED:
        record = _committed_record(plan)
    else:
        record = _record_for(plan)
        if terminal == CAS_CONFLICT:
            with pytest.raises(CasConflict) as caught:
                transition(record, PREIMAGE_VERIFIED, {
                    'observed_pre_sha256': HASH_POST,
                    'observed_pre_lines': REWRITE_POST_LINES,
                    'observed_pre_bytes': PRE_BYTES,
                })
            record = caught.value.record
        else:
            reason_key = {
                ABORTED: 'abort_reason',
                FAILED: 'failure_reason',
                QUARANTINED: 'quarantine_reason',
            }[terminal]
            record = transition(record, terminal, {reason_key: 'test'})
        assert record.state == terminal
    with pytest.raises(WriteContractError):
        new_transaction(plan, PLANNED_AT)


def test_d1_failed_record_validation_still_burns_txn_id(monkeypatch):
    plan = _plan(txn_id='txn-validation-failed-kept')

    def fail_validation(_record):
        raise WriteContractError('fallo inyectado de validación')

    with monkeypatch.context() as patcher:
        patcher.setattr(wc, '_validate_record', fail_validation)
        with pytest.raises(WriteContractError):
            new_transaction(plan, PLANNED_AT)

    with pytest.raises(WriteContractError):
        new_transaction(plan, PLANNED_AT)


def test_d4_target_policy_is_immutable_and_canonical():
    policy = TARGET_POLICIES[TARGET_DB]
    assert type(policy) is TargetPolicy
    with pytest.raises(AttributeError):
        object.__setattr__(policy, 'requires_manifest_verification', False)
    plan = _plan()
    assert plan.validate() is plan
    assert _committed_record(plan).state == COMMITTED


def test_d4_writeplan_subclass_cannot_override_validation():
    class EvilPlan(WritePlan):
        def validate(self):
            return self

    base = _plan()
    evil = EvilPlan(**base.__dict__)
    with pytest.raises(WriteContractError):
        new_transaction(evil, PLANNED_AT)


def test_d4_writer_declaration_subclass_cannot_weaken_validation():
    class EvilDeclaration(WriterDeclaration):
        def validate(self):
            return self

    base = _declaration()
    evil = EvilDeclaration(**base.__dict__)
    with pytest.raises(WriteContractError):
        _plan(writer_declaration=evil).validate()


def test_d4_manifest_target_is_writable_with_consistent_hashes():
    plan = _plan(target_path=TARGET_MANIFEST)
    record = _committed_record(plan)
    assert record.state == COMMITTED
    assert record.evidence['manifest_required'] is True
    with pytest.raises(WriteContractError):
        _plan(target_path=TARGET_MANIFEST,
              manifest_expected_sha256=HASH_MANIFEST_PRE).validate()
    with pytest.raises(WriteContractError):
        _plan(target_path=TARGET_MANIFEST,
              manifest_candidate_sha256=HASH_MANIFEST_POST).validate()


def test_d5_backup_and_temp_names_use_the_complete_txn_identity():
    plan_a = _plan(txn_id='txn-f0')
    plan_b = _plan(txn_id='txn-f0-other')
    record = _apply_steps(_record_for(plan_a), _steps(plan_a)[:1])[0]
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED, _backup_evidence(
            plan_a, backup_path='data/_backup/%s.jsonl' % plan_b.txn_id))
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED, _backup_evidence(
            plan_a, backup_path='data/_backup/sub/%s.jsonl'
            % plan_a.txn_id))

    record = _apply_steps(record, _steps(plan_a)[1:2])[0]
    with pytest.raises(WriteContractError):
        transition(record, TEMP_VERIFIED, _temp_evidence(
            plan_a, temp_path='data/hands_db.jsonl.%s.tmp' % plan_b.txn_id))
    with pytest.raises(WriteContractError):
        transition(record, TEMP_VERIFIED, _temp_evidence(
            plan_a, temp_path='data/otro/hands_db.jsonl.%s.tmp'
            % plan_a.txn_id))


def test_d6_huge_lock_timeouts_are_contract_errors_not_overflow():
    for timeout in (10 ** 1000, 10 ** 400, 2 ** 2000):
        with pytest.raises(WriteContractError):
            LockPolicy(timeout_seconds=timeout)


def test_d6_lock_policy_subclass_cannot_forge_validation_or_fingerprint():
    class EvilLock(LockPolicy):
        def validate(self):
            return self

        def as_dict(self):
            return {'timeout_seconds': 1.0}

    evil = EvilLock(timeout_seconds=float('nan'))
    with pytest.raises(WriteContractError):
        lock_policy_fingerprint(evil)
    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='lock-falso', operation=REWRITE, targets=(TARGET_DB,),
            requires_lock=True, requires_cas=True, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=True,
            lock_policy=evil,
        )


def test_d6_mutated_lock_is_revalidated_before_transition():
    plan = _plan()
    record = _record_for(plan)
    object.__setattr__(plan.lock_policy, 'timeout_seconds', 10 ** 1000)
    with pytest.raises(WriteContractError):
        plan.validate()
    with pytest.raises(WriteContractError):
        transition(record, PREIMAGE_VERIFIED, {
            'observed_pre_sha256': HASH_PRE,
            'observed_pre_lines': REWRITE_POST_LINES,
            'observed_pre_bytes': PRE_BYTES,
        })


def test_d7_lone_surrogates_are_contract_errors():
    plan = _plan(operation=APPEND)
    record = _apply_steps(_record_for(plan), _steps(plan)[:3])[0]
    base = _replaced_evidence(plan)
    with pytest.raises(WriteContractError):
        transition(record, REPLACED,
                   dict(base, append_content='\ud800\n'))


def test_d8_pins_symbols_are_literal_and_not_stripped():
    plan = _plan()
    record = _apply_steps(_record_for(plan), _steps(plan)[:7])[0]
    base = _pins_evidence(plan)
    for symbols in (
        [PINS_SYMBOLS[0] + ' ', PINS_SYMBOLS[1], PINS_SYMBOLS[2]],
        [' ' + PINS_SYMBOLS[0], PINS_SYMBOLS[1], PINS_SYMBOLS[2]],
    ):
        with pytest.raises(WriteContractError):
            transition(record, PINS_PROPOSED,
                       dict(base, pins_symbols=symbols))


def test_d2_minimal_committed_record_is_partial_without_plan():
    committed = _committed_record()
    plan = committed.plan
    minimal = _raw_journal(
        plan, 0, COMMITTED, JOURNAL_GENESIS_SHA256,
        {'txn_id': plan.txn_id, 'committed_at': COMMITTED_AT},
        authority_id=committed.authority_id,
        transaction_uid=committed.transaction_uid,
    )
    assert validate_journal_record(minimal)['state'] == COMMITTED
    assert recovery_action([minimal]) == QUARANTINED
    with pytest.raises(WriteContractError):
        validate_journal_record(minimal, plan=plan)
    assert recovery_action([minimal], plan=plan) == QUARANTINED

@pytest.mark.parametrize('other_txn', [
    'txn-f0-other', 'txn-f0.other', 'txn-f0_other',
])
def test_d5_ambiguous_txn_identifiers_do_not_share_artifacts(other_txn):
    plan_a = _plan(txn_id='txn-f0')
    plan_b = _plan(txn_id=other_txn)
    record = _apply_steps(_record_for(plan_a), _steps(plan_a)[:1])[0]
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED, _backup_evidence(
            plan_a, backup_path='data/_backup/%s.jsonl' % plan_b.txn_id))
    record = transition(record, BACKUP_VERIFIED, _backup_evidence(plan_a))
    with pytest.raises(WriteContractError):
        transition(record, TEMP_VERIFIED, _temp_evidence(
            plan_a, temp_path='data/hands_db.jsonl.%s.tmp' % plan_b.txn_id))

def test_d1_copy_of_active_record_is_not_a_capability():
    record = _record()
    copied = replace(record)
    with pytest.raises(WriteContractError):
        transition(copied, PREIMAGE_VERIFIED, {
            'observed_pre_sha256': HASH_PRE,
            'observed_pre_lines': REWRITE_POST_LINES,
            'observed_pre_bytes': PRE_BYTES,
        })
    assert transition(record, PREIMAGE_VERIFIED, {
        'observed_pre_sha256': HASH_PRE,
        'observed_pre_lines': REWRITE_POST_LINES,
        'observed_pre_bytes': PRE_BYTES,
    }).state == PREIMAGE_VERIFIED


def test_d1_reconstruction_with_copied_fields_is_not_a_capability():
    record = _record()
    forged = TransactionRecord(
        state=record.state,
        plan=record.plan,
        evidence=record.evidence,
        history=record.history,
        authority_id=record.authority_id,
        transaction_uid=record.transaction_uid,
    )
    with pytest.raises(WriteContractError):
        transition(forged, PREIMAGE_VERIFIED, {
            'observed_pre_sha256': HASH_PRE,
            'observed_pre_lines': REWRITE_POST_LINES,
            'observed_pre_bytes': PRE_BYTES,
        })

def test_state_isolation_defaults_and_policy_mapping_are_not_shared():
    first = _declaration()
    second = _declaration()
    assert first.lock_policy is not second.lock_policy

    first_plan = _plan()
    second_plan = _plan()
    assert first_plan.lock_policy is not second_plan.lock_policy
    assert first_plan.lock_policy is not first.lock_policy

    with pytest.raises(TypeError):
        TARGET_POLICIES[TARGET_DB] = TARGET_POLICIES[TARGET_DB]


def test_fixture_restores_nonempty_registry_and_authority_identity():
    authority_id = 'a' * 32
    transaction_uid = 'b' * 32
    txn_id = 'txn-fixture-sentinel'
    authorized_record = TransactionRecord(
        state=PREPARED,
        plan=_plan(txn_id=txn_id),
        evidence={},
        history=(PREPARED,),
        authority_id=authority_id,
        transaction_uid=transaction_uid,
    )
    authority = wc._AuthorityState(
        txn_id=txn_id,
        plan_fingerprint='c' * 64,
        transaction_uid=transaction_uid,
        authorized_records=[authorized_record],
    )
    authorized_records = authority.authorized_records
    wc._AUTHORITIES[authority_id] = authority
    wc._USED_TXN_IDS.add(txn_id)
    original_authorities = wc._AUTHORITIES
    original_used_ids = wc._USED_TXN_IDS

    with _isolated_contract_state():
        assert wc._AUTHORITIES == {}
        assert wc._USED_TXN_IDS == set()
        assert wc._AUTHORITIES is not original_authorities
        assert wc._USED_TXN_IDS is not original_used_ids
        authority.active = False
        authority.txn_id = 'txn-alterado-temporalmente'
        authorized_records.clear()
        wc._AUTHORITIES['d' * 32] = object()
        wc._USED_TXN_IDS.add('txn-created-inside-fixture')

    assert wc._AUTHORITIES is original_authorities
    assert wc._USED_TXN_IDS is original_used_ids
    assert wc._AUTHORITIES == {authority_id: authority}
    assert wc._USED_TXN_IDS == {txn_id}
    restored = wc._AUTHORITIES[authority_id]
    assert restored is authority
    assert restored.txn_id == txn_id
    assert restored.transaction_uid == transaction_uid
    assert restored.active is True
    assert restored.authorized_records is authorized_records
    assert restored.authorized_records == [authorized_record]
    assert restored.authorized_records[0] is authorized_record
    assert restored.authorized_records[0].authority_id == authority_id
    assert restored.authorized_records[0].transaction_uid == transaction_uid
    assert restored.authorized_records[0].plan.txn_id == txn_id
    assert txn_id in wc._USED_TXN_IDS


def test_fixture_restores_both_registries_after_exception():
    authority_id = 'e' * 32
    txn_id = 'txn-fixture-exception-sentinel'
    authority = wc._AuthorityState(
        txn_id=txn_id,
        plan_fingerprint='f' * 64,
        transaction_uid='1' * 32,
    )
    wc._AUTHORITIES[authority_id] = authority
    wc._USED_TXN_IDS.add(txn_id)

    with pytest.raises(RuntimeError, match='fallo simulado'):
        with _isolated_contract_state():
            assert wc._AUTHORITIES == {}
            assert wc._USED_TXN_IDS == set()
            wc._AUTHORITIES['2' * 32] = object()
            wc._USED_TXN_IDS.add('txn-transitorio')
            raise RuntimeError('fallo simulado')

    assert wc._AUTHORITIES.get(authority_id) is authority
    assert wc._USED_TXN_IDS == {txn_id}
    assert authority.txn_id in wc._USED_TXN_IDS


def test_fixture_preserves_an_initially_empty_state():
    original_authorities = wc._AUTHORITIES
    original_used_ids = wc._USED_TXN_IDS
    assert original_authorities == {}
    assert original_used_ids == set()

    with _isolated_contract_state():
        plan = _plan(txn_id='txn-fixture-empty-start')
        _record_for(plan)
        assert plan.txn_id in wc._USED_TXN_IDS
        assert len(wc._AUTHORITIES) == 1

    assert wc._AUTHORITIES is original_authorities
    assert wc._USED_TXN_IDS is original_used_ids
    assert wc._AUTHORITIES == {}
    assert wc._USED_TXN_IDS == set()


def test_fixture_scopes_isolate_tests_without_releasing_in_scope_ids():
    plan = _plan(txn_id='txn-fixture-scope-boundary')
    with _isolated_contract_state():
        record = _record_for(plan)
        assert record.authority_id in wc._AUTHORITIES
        assert plan.txn_id in wc._USED_TXN_IDS
        with pytest.raises(WriteContractError):
            new_transaction(plan, PLANNED_AT)


def test_d1_reconstruction_rejected_after_external_original_reference_dropped():
    plan = _plan(txn_id='txn-strong-instance-reference')
    original = _record_for(plan)
    authority_id = original.authority_id
    transaction_uid = original.transaction_uid
    state = wc._AUTHORITIES[authority_id]
    original_ref = weakref.ref(original)
    copied_fields = {
        'state': original.state,
        'plan': original.plan,
        'evidence': original.evidence,
        'history': original.history,
        'authority_id': authority_id,
        'transaction_uid': transaction_uid,
    }
    assert any(authorized is original
               for authorized in state.authorized_records)

    del original
    gc.collect()

    # La autoridad mantiene vivo el objeto, sin depender de que se reutilice
    # o no un entero devuelto por id().
    retained_original = original_ref()
    assert retained_original is not None
    assert any(authorized is retained_original
               for authorized in state.authorized_records)

    reconstructed = TransactionRecord(**copied_fields)
    assert reconstructed is not retained_original
    assert not any(authorized is reconstructed
                   for authorized in state.authorized_records)
    with pytest.raises(WriteContractError):
        transition(reconstructed, PREIMAGE_VERIFIED, {
            'observed_pre_sha256': plan.expected_pre_sha256,
            'observed_pre_lines': plan.expected_pre_lines,
            'observed_pre_bytes': plan.expected_pre_bytes,
        })


def test_d1_copies_and_reconstructions_are_not_authorized_instances():
    record = _record()
    copies = [replace(record), TransactionRecord(
        state=record.state,
        plan=record.plan,
        evidence=record.evidence,
        history=record.history,
        authority_id=record.authority_id,
        transaction_uid=record.transaction_uid,
    )]
    shallow = copy.copy(record)
    if shallow is not record:
        copies.append(shallow)
    try:
        deep = copy.deepcopy(record)
    except (TypeError, copy.Error):
        # MappingProxyType evidence is not deepcopy/pickle compatible.
        deep = None
    if deep is not None and deep is not record:
        copies.append(deep)

    for copied_record in copies:
        assert copied_record is not record
        with pytest.raises(WriteContractError):
            transition(copied_record, PREIMAGE_VERIFIED, {
                'observed_pre_sha256': HASH_PRE,
                'observed_pre_lines': REWRITE_POST_LINES,
                'observed_pre_bytes': PRE_BYTES,
            })


def test_d1_authority_keeps_history_instances_alive_for_journal_lifecycle():
    plan = _plan(txn_id='txn-strong-history-retention')
    frames = _frames(plan)
    state = wc._AUTHORITIES[frames[-1].authority_id]
    frame_refs = [weakref.ref(frame) for frame in frames]
    authorized_records = state.authorized_records
    assert len(authorized_records) == len(frames)
    assert all(any(authorized is frame for authorized in authorized_records)
               for frame in frames)

    del frames
    gc.collect()

    retained_frames = [frame_ref() for frame_ref in frame_refs]
    assert all(frame is not None for frame in retained_frames)
    assert all(any(authorized is frame for authorized in authorized_records)
               for frame in retained_frames)
    entries = _journal_entries(retained_frames)
    assert entries[-1]['state'] == COMMITTED
    assert wc.assert_committed(retained_frames[-1]).state == COMMITTED


def test_d1_invalidated_authority_retains_only_real_conflict_instances():
    plan = _plan(txn_id='txn-strong-conflict-retention')
    prepared = _record_for(plan)
    prepared_ref = weakref.ref(prepared)
    with pytest.raises(CasConflict) as caught:
        transition(prepared, PREIMAGE_VERIFIED, {
            'observed_pre_sha256': HASH_POST,
            'observed_pre_lines': REWRITE_POST_LINES,
            'observed_pre_bytes': PRE_BYTES,
        })
    conflict = caught.value.record
    conflict_ref = weakref.ref(conflict)
    state = wc._AUTHORITIES[prepared.authority_id]
    del prepared, conflict
    gc.collect()

    retained_prepared = prepared_ref()
    retained_conflict = conflict_ref()
    assert retained_prepared is not None
    assert retained_conflict is not None
    assert any(item is retained_prepared for item in state.authorized_records)
    assert any(item is retained_conflict for item in state.authorized_records)
    entries = _journal_entries([retained_prepared, retained_conflict])
    assert recovery_action(entries, plan=plan) == CAS_CONFLICT
    with pytest.raises(WriteContractError):
        transition(retained_prepared, PREIMAGE_VERIFIED, {
            'observed_pre_sha256': HASH_PRE,
            'observed_pre_lines': REWRITE_POST_LINES,
            'observed_pre_bytes': PRE_BYTES,
        })

    # Simula el siguiente ámbito de prueba: el ID del ámbito anterior no se
    # filtra, pero tampoco se limpia dentro del nuevo ámbito activo.
    with _isolated_contract_state():
        assert wc._AUTHORITIES == {}
        assert wc._USED_TXN_IDS == set()
        next_record = _record_for(plan)
        assert next_record.plan.txn_id == plan.txn_id
        assert plan.txn_id in wc._USED_TXN_IDS
        with pytest.raises(WriteContractError):
            new_transaction(plan, PLANNED_AT)
