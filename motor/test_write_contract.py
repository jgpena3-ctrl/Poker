# -*- coding: utf-8 -*-
"""Tests F0.2 del contrato de integridad de escrituras.

No escriben en `data/`: el arnés simula la base como una cadena y comprueba
que ninguna ruta de fallo puede declarar `committed`, que el CAS es terminal,
que el journal está ligado al plan y que la evidencia es inmutable.
"""
import os

import pytest

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
    JOURNAL_PLAN_BINDING_POLICY,
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
    recovery_action,
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
POST_BYTES = 120
PINS_VALUES = {
    'HANDS_DB_SHA256': HASH_POST,
    'HANDS_DB_COMMIT': PINS_COMMIT,
    'HANDS_DB_LINEAS': 10,
}
PINS_HASH = canonical_sha256(PINS_VALUES, 'pins_proposed_values')


def _plan(**overrides):
    data = {
        'txn_id': 'txn-f0',
        'writer': 'writer-de-prueba',
        'operation': REWRITE,
        'expected_pre_sha256': HASH_PRE,
        'expected_pre_lines': 10,
        'expected_pre_bytes': PRE_BYTES,
        'candidate_sha256': HASH_POST,
        'candidate_lines': 10,
        'candidate_bytes': POST_BYTES,
        'target_path': TARGET_DB,
    }
    if overrides.get('manifest_required') is True:
        data.update({
            'manifest_path': TARGET_MANIFEST,
            'manifest_expected_sha256': HASH_MANIFEST_PRE,
            'manifest_candidate_sha256': HASH_MANIFEST_POST,
        })
    if overrides.get('pins_required') is True:
        data['pins_path'] = 'motor/learn.py'
        data['pins_expected_sha256'] = HASH_PINS_SOURCE
    data.update(overrides)
    return WritePlan(**data)


def _record(manifest_required=False, pins_required=False, operation=REWRITE):
    return new_transaction(
        _plan(manifest_required=manifest_required,
              pins_required=pins_required,
              operation=operation),
        '2026-11-12T00:00:00Z')


def _backup_evidence(**overrides):
    evidence = {
        'backup_path': 'data/_backup_f0/txn-f0.jsonl',
        'backup_sha256': HASH_PRE,
        'backup_bytes': PRE_BYTES,
        'backup_txn_id': 'txn-f0',
        'backup_disposition': 'created',
    }
    evidence.update(overrides)
    return evidence


def _replaced_evidence(operation=REWRITE, **overrides):
    evidence = {
        'replaced_at': '2026-11-12T00:00:01Z',
        'operation_verified': True,
    }
    if operation == APPEND:
        evidence.update({
            'preimage_prefix_verified': True,
            'append_boundary_verified': True,
        })
    elif operation == SNAPSHOT:
        evidence.update({
            'snapshot_verified': True,
            'canonical_target_unchanged': True,
        })
    else:
        evidence['rewrite_complete_verified'] = True
    evidence.update(overrides)
    return evidence


def _steps(manifest_required=False, pins_required=False, operation=REWRITE):
    return [
        (PREIMAGE_VERIFIED, {
            'observed_pre_sha256': HASH_PRE,
            'observed_pre_lines': 10,
            'observed_pre_bytes': PRE_BYTES,
        }),
        (BACKUP_VERIFIED, _backup_evidence()),
        (TEMP_VERIFIED, {
            'temp_path': 'data/hands_db.jsonl.txn-f0.tmp',
            'temp_sha256': HASH_POST,
            'temp_lines': 10,
            'temp_bytes': POST_BYTES,
        }),
        (REPLACED, _replaced_evidence(operation)),
        (POST_VERIFIED, {
            'post_sha256': HASH_POST,
            'post_lines': 10,
            'post_bytes': POST_BYTES,
        }),
    ] + _tail_steps(manifest_required, pins_required)


def _tail_steps(manifest_required, pins_required):
    if manifest_required:
        pending = {'manifest_pending_at': '2026-11-12T00:00:01Z'}
        verified = {
            'manifest_observed_pre_sha256': HASH_MANIFEST_PRE,
            'manifest_sha256': HASH_MANIFEST_POST,
            'manifest_verified': True,
        }
    else:
        pending = {
            'manifest_pending_at': '2026-11-12T00:00:01Z',
            'manifest_skipped_reason':
                'la prueba no toca el manifiesto',
        }
        verified = {}
    if pins_required:
        pins = {
            'pins_applied': False,
            'pins_proposed_sha256': PINS_HASH,
            'pins_symbols': list(PINS_SYMBOLS),
            'pins_proposed_values': dict(PINS_VALUES),
            'pins_source_sha256': HASH_PINS_SOURCE,
        }
    else:
        pins = {
            'pins_applied': False,
            'pins_skipped_reason':
                'los pins se revisan fuera de la transacción',
        }
    return [
        (MANIFEST_PENDING, pending),
        (MANIFEST_VERIFIED, verified),
        (PINS_PROPOSED, pins),
        (COMMITTED, {'committed_at': '2026-11-12T00:00:02Z'}),
    ]


def _apply_steps(record, steps, fail_at=None):
    for state, evidence in steps:
        if state == fail_at:
            return record, state
        record = transition(record, state, evidence)
    return record, None


def _frames(manifest_required=False, pins_required=False,
            operation=REWRITE, stop_before=None):
    record = _record(manifest_required, pins_required, operation)
    frames = [record]
    for state, evidence in _steps(manifest_required, pins_required,
                                  operation):
        if state == stop_before:
            break
        record = transition(record, state, evidence)
        frames.append(record)
    return frames


def _committed_record(manifest_required=False, pins_required=False,
                      operation=REWRITE):
    return assert_committed(_frames(manifest_required, pins_required,
                                    operation)[-1])


def _journal_entries(frames):
    entries = []
    previous = JOURNAL_GENESIS_SHA256
    for sequence, frame in enumerate(frames):
        entry = journal_record_from_transaction(frame, sequence, previous)
        entries.append(entry)
        previous = entry['record_sha256']
    return entries


def _journal_chain(manifest_required=False, pins_required=False,
                   stop_before=None):
    return _journal_entries(_frames(manifest_required, pins_required,
                                    stop_before=stop_before))


def _reseal(entry):
    changed = dict(entry)
    changed['evidence_sha256'] = canonical_sha256(changed['evidence'],
                                                  'evidence')
    changed['record_sha256'] = journal_record_sha256(changed)
    return changed


def _raw_journal(plan, sequence, state, previous, evidence):
    record = {
        'schema_version': JOURNAL_SCHEMA_VERSION,
        'contract_version': CONTRACT_VERSION,
        'txn_id': plan.txn_id,
        'plan_fingerprint': plan_fingerprint(plan),
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

    def __init__(self, manifest_required=False, pins_required=False):
        self.record = _record(manifest_required, pins_required)
        self.steps = _steps(manifest_required, pins_required)
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
    assert record.evidence['post_bytes'] == POST_BYTES
    assert record.evidence['operation_verified'] is True
    assert CONTRACT_VERSION == 'F0.2 (2026-11-12)'


@pytest.mark.parametrize('manifest_required,pins_required', [
    (True, False), (False, True), (True, True),
])
def test_happy_path_with_manifest_and_pins(manifest_required, pins_required):
    record = _committed_record(manifest_required, pins_required)
    assert record.state == COMMITTED
    assert record.evidence['manifest_required'] is manifest_required
    assert record.evidence['pins_required'] is pins_required
    if pins_required:
        assert record.evidence['pins_proposed_values']['HANDS_DB_SHA256'] == \
            HASH_POST
        assert record.evidence['pins_proposed_sha256'] == PINS_HASH


def test_cannot_skip_a_state():
    with pytest.raises(WriteContractError):
        transition(_record(), BACKUP_VERIFIED, _backup_evidence())


def test_preimage_mismatch_is_terminal_cas_conflict():
    record = _record()
    bad = {
        'observed_pre_sha256': HASH_POST,
        'observed_pre_lines': 10,
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
            'observed_pre_lines': 10,
            'observed_pre_bytes': PRE_BYTES,
        })
    with pytest.raises(WriteContractError):
        assert_committed(conflict)
    direct = transition(_record(), CAS_CONFLICT, bad)
    assert direct.state == CAS_CONFLICT
    entries = _journal_entries([record, conflict])
    assert recovery_action(entries, plan=record.plan) == CAS_CONFLICT


@pytest.mark.parametrize('field,value', [
    ('observed_pre_sha256', HASH_POST),
    ('observed_pre_lines', 9),
    ('observed_pre_bytes', PRE_BYTES - 1),
])
def test_each_cas_field_mismatch_is_terminal(field, value):
    evidence = {
        'observed_pre_sha256': HASH_PRE,
        'observed_pre_lines': 10,
        'observed_pre_bytes': PRE_BYTES,
    }
    evidence[field] = value
    with pytest.raises(CasConflict) as caught:
        transition(_record(), PREIMAGE_VERIFIED, evidence)
    assert caught.value.record.state == CAS_CONFLICT


def test_backup_must_be_the_verified_preimage_and_txn():
    record, _ = _apply_steps(_record(), _steps()[:1])
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED,
                   _backup_evidence(backup_sha256=HASH_POST))
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED,
                   _backup_evidence(backup_txn_id='otro-txn'))
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED,
                   _backup_evidence(backup_path=TARGET_DB))
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED,
                   _backup_evidence(backup_disposition='preexisting_other'))


@pytest.mark.parametrize('path', [
    'data/../data/_backup_f0/txn-f0.jsonl',
    'data/_backup_f0/otro.jsonl',
    'data/otro/txn-f0.jsonl',
])
def test_backup_path_must_be_canonical_owned_and_under_backup_root(path):
    record, _ = _apply_steps(_record(), _steps()[:1])
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED,
                   _backup_evidence(backup_path=path))


def test_temp_and_post_must_match_candidate_and_paths():
    record, _ = _apply_steps(_record(), _steps()[:2])
    with pytest.raises(WriteContractError):
        transition(record, TEMP_VERIFIED, {
            'temp_path': 'data/hands_db.jsonl.txn-f0.tmp',
            'temp_sha256': HASH_PRE,
            'temp_lines': 10,
            'temp_bytes': POST_BYTES,
        })
    with pytest.raises(WriteContractError):
        transition(record, TEMP_VERIFIED, {
            'temp_path': TARGET_DB,
            'temp_sha256': HASH_POST,
            'temp_lines': 10,
            'temp_bytes': POST_BYTES,
        })
    with pytest.raises(WriteContractError):
        transition(record, TEMP_VERIFIED, {
            'temp_path': 'data/../data/hands_db.jsonl.txn-f0.tmp',
            'temp_sha256': HASH_POST,
            'temp_lines': 10,
            'temp_bytes': POST_BYTES,
        })

    record, _ = _apply_steps(_record(), _steps()[:4])
    with pytest.raises(WriteContractError):
        transition(record, POST_VERIFIED, {
            'post_sha256': HASH_PRE,
            'post_lines': 10,
            'post_bytes': POST_BYTES,
        })


def test_after_replace_only_quarantine_is_allowed():
    record, _ = _apply_steps(_record(), _steps()[:4])
    with pytest.raises(WriteContractError):
        transition(record, FAILED, {'failure_reason': 'fallo tardío'})
    quarantined = transition(record, QUARANTINED, {
        'quarantine_reason': 'la base ya fue reemplazada y no verifica',
    })
    assert quarantined.state == QUARANTINED
    with pytest.raises(WriteContractError):
        assert_committed(quarantined)


def test_manifest_requires_verifiable_evidence():
    record, _ = _apply_steps(
        _record(manifest_required=True), _steps(True)[:6])
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
    record, _ = _apply_steps(_record(), _steps()[:5])
    with pytest.raises(WriteContractError):
        transition(record, MANIFEST_VERIFIED, {})


def test_pins_are_proposed_not_applied_and_bound_to_values():
    record, _ = _apply_steps(
        _record(pins_required=True), _steps(False, True)[:7])
    base = {
        'pins_applied': False,
        'pins_proposed_sha256': PINS_HASH,
        'pins_symbols': list(PINS_SYMBOLS),
        'pins_proposed_values': dict(PINS_VALUES),
        'pins_source_sha256': HASH_PINS_SOURCE,
    }
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
                PINS_VALUES, HANDS_DB_SHA256=HASH_PRE)))
    with pytest.raises(WriteContractError):
        transition(record, PINS_PROPOSED, dict(
            base, pins_proposed_values=dict(
                PINS_VALUES, HANDS_DB_LINEAS=11)))
    with pytest.raises(WriteContractError):
        transition(record, PINS_PROPOSED, dict(
            base, pins_source_sha256='no-es-sha'))
    with pytest.raises(WriteContractError):
        transition(record, PINS_PROPOSED, dict(
            base, pins_source_sha256=HASH_PRE))
    assert transition(record, PINS_PROPOSED, base).evidence['pins_applied'] \
        is False


def test_plan_fields_cannot_be_overridden_by_evidence():
    evidence = {
        'observed_pre_sha256': HASH_PRE,
        'observed_pre_lines': 10,
        'observed_pre_bytes': PRE_BYTES,
        'manifest_required': True,
    }
    with pytest.raises(WriteContractError):
        transition(_record(), PREIMAGE_VERIFIED, evidence)


def test_verified_evidence_cannot_be_overwritten():
    record, _ = _apply_steps(_record(), _steps()[:1])
    with pytest.raises(WriteContractError):
        transition(record, BACKUP_VERIFIED,
                   dict(_backup_evidence(),
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
                    'observed_pre_lines': 10,
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


def test_append_and_snapshot_operation_semantics():
    with pytest.raises(WriteContractError):
        _plan(operation=APPEND, candidate_bytes=PRE_BYTES - 1).validate()
    with pytest.raises(WriteContractError):
        _plan(operation=APPEND, candidate_lines=9).validate()
    with pytest.raises(WriteContractError):
        _plan(operation=APPEND, candidate_bytes=PRE_BYTES).validate()
    assert _plan(operation=APPEND).validate().operation == APPEND
    with pytest.raises(WriteContractError):
        _plan(operation=SNAPSHOT, target_path=TARGET_DB).validate()
    with pytest.raises(WriteContractError):
        _plan(operation=SNAPSHOT,
              target_path=SNAPSHOT_ROOT + '/db.jsonl').validate()
    snapshot = _plan(
        operation=SNAPSHOT,
        target_path=SNAPSHOT_ROOT + '/db.jsonl',
        snapshot_of=TARGET_DB,
        candidate_sha256=HASH_PRE,
        candidate_lines=10,
        candidate_bytes=PRE_BYTES,
    )
    assert snapshot.validate().snapshot_of == TARGET_DB


def test_operation_evidence_is_required_before_replace():
    record, _ = _apply_steps(_record(), _steps()[:3])
    with pytest.raises(WriteContractError):
        transition(record, REPLACED, {
            'replaced_at': '2026-11-12T00:00:01Z',
            'operation_verified': True,
        })
    with pytest.raises(WriteContractError):
        transition(record, REPLACED, dict(
            _replaced_evidence(), rewrite_complete_verified=False))
    append_record, _ = _apply_steps(
        _record(operation=APPEND), _steps(operation=APPEND)[:3])
    with pytest.raises(WriteContractError):
        transition(append_record, REPLACED, {
            'replaced_at': '2026-11-12T00:00:01Z',
            'operation_verified': True,
        })


def test_writer_declaration_fails_closed_for_all_target_categories():
    valid = WriterDeclaration(
        name='writer-de-prueba',
        operation=REWRITE,
        targets=(TARGET_DB,),
        requires_lock=True,
        requires_cas=True,
        requires_backup=True,
        requires_manifest_verification=True,
        requires_pins_proposal=True,
    )
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
            ).validate()

    derived = WriterDeclaration(
        name='derivado-valido', operation=REWRITE,
        targets=(TARGET_POSTFLOP_RANGES,),
        requires_lock=True, requires_cas=True, requires_backup=True,
        requires_manifest_verification=True,
        requires_pins_proposal=False,
    )
    assert derived.validate() is derived

    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='destino-desconocido', operation=REWRITE,
            targets=('data/otro.json',),
            requires_lock=True, requires_cas=True, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=False,
        ).validate()
    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='manifiesto-append', operation=APPEND,
            targets=(TARGET_MANIFEST,),
            requires_lock=True, requires_cas=True, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=False,
        ).validate()
    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='alias', operation=REWRITE,
            targets=('data/../data/hands_db.jsonl',),
            requires_lock=True, requires_cas=True, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=True,
        ).validate()

    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='sin-mutex', operation=REWRITE, targets=(TARGET_DB,),
            requires_lock=False, requires_cas=True, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=True,
        ).validate()
    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='sin-cas', operation=REWRITE, targets=(TARGET_DB,),
            requires_lock=True, requires_cas=False, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=True,
        ).validate()
    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='sin-backup', operation=REWRITE, targets=(TARGET_DB,),
            requires_lock=True, requires_cas=True, requires_backup=False,
            requires_manifest_verification=True,
            requires_pins_proposal=True,
        ).validate()
    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='sin-pins', operation=REWRITE, targets=(TARGET_DB,),
            requires_lock=True, requires_cas=True, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=False,
        ).validate()
    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='snapshot-sin-backup', operation=SNAPSHOT,
            targets=(TARGET_DB,), requires_lock=True, requires_cas=True,
            requires_backup=False,
            requires_manifest_verification=True,
            requires_pins_proposal=True,
        ).validate()


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
    assert DEFAULT_LOCK_POLICY.validate() is DEFAULT_LOCK_POLICY

    for invalid in (
        {'fallbacks_allowed': True},
        {'multi_host_allowed': True},
        {'timeout_seconds': 0},
        {'acl_required': False},
        {'sid_required': False},
        {'name': 'otro-mutex'},
    ):
        with pytest.raises(WriteContractError):
            type(DEFAULT_LOCK_POLICY)(**invalid).validate()

    plan = _plan()
    record = new_transaction(plan, '2026-11-12T00:00:00Z')
    assert record.evidence['lock_policy_fingerprint'] == \
        lock_policy_fingerprint(plan.lock_policy)
    forged = record.as_dict()['evidence']
    forged['lock_policy_fingerprint'] = 'f' * 64
    with pytest.raises(WriteContractError):
        transition(TransactionRecord(
            state=PREPARED, plan=plan, evidence=forged,
            history=(PREPARED,)), PREIMAGE_VERIFIED, {
                'observed_pre_sha256': HASH_PRE,
                'observed_pre_lines': 10,
                'observed_pre_bytes': PRE_BYTES,
            })
    with pytest.raises(WriteContractError):
        _plan(lock_policy=type(DEFAULT_LOCK_POLICY)(
            fallbacks_allowed=True)).validate()
    with pytest.raises(WriteContractError):
        WriterDeclaration(
            name='lock-invalido', operation=REWRITE, targets=(TARGET_DB,),
            requires_lock=True, requires_cas=True, requires_backup=True,
            requires_manifest_verification=True,
            requires_pins_proposal=True,
            lock_policy=type(DEFAULT_LOCK_POLICY)(fallbacks_allowed=True),
        ).validate()


def test_journal_schema_hash_chain_plan_and_truncation():
    plan = _plan()
    chain = _journal_chain()
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

    valid = _journal_chain()
    other = _plan(candidate_sha256='f' * 64, candidate_bytes=121)
    with pytest.raises(WriteContractError):
        validate_journal_chain(valid, plan=other)
    assert recovery_action(valid, plan=other) == QUARANTINED
    assert recovery_action(valid) == QUARANTINED


def test_journal_rejects_broken_links_bad_transitions_and_removed_evidence():
    plan = _plan()
    chain = _journal_chain()

    broken = dict(chain[1])
    broken['previous_sha256'] = JOURNAL_GENESIS_SHA256
    broken = _reseal(broken)
    with pytest.raises(WriteContractError):
        validate_journal_chain([chain[0], broken], plan=plan)

    replaced = _frames(stop_before=POST_VERIFIED)[-1]
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
    before = _journal_chain(stop_before=REPLACED)
    after = _journal_chain(stop_before=POST_VERIFIED)
    committed = _journal_chain()
    with pytest.raises(CasConflict) as caught:
        transition(_record(), PREIMAGE_VERIFIED, {
            'observed_pre_sha256': HASH_POST,
            'observed_pre_lines': 10,
            'observed_pre_bytes': PRE_BYTES,
        })
    conflict = _journal_entries([_record(), caught.value.record])

    assert recovery_action([], plan=plan) == 'noop'
    assert recovery_action(before, plan=plan) == ABORTED
    assert recovery_action(after, plan=plan) == QUARANTINED
    assert recovery_action(committed, plan=plan) == COMMITTED
    assert recovery_action(conflict, plan=plan) == CAS_CONFLICT
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
    record = _committed_record(pins_required=True)
    with pytest.raises(TypeError):
        record.evidence['pins_proposed_values']['HANDS_DB_LINEAS'] = 11
    with pytest.raises(TypeError):
        record.evidence['pins_symbols'][0] = 'OTRO'
    copied = record.as_dict()['evidence']
    copied['pins_proposed_values']['HANDS_DB_LINEAS'] = 11
    assert record.evidence['pins_proposed_values']['HANDS_DB_LINEAS'] == 10
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


def test_timestamps_require_iso_8601_timezone():
    with pytest.raises(WriteContractError):
        new_transaction(_plan(), '2026-11-12T00:00:00')
    with pytest.raises(WriteContractError):
        new_transaction(_plan(), '2026-11-12')
    assert new_transaction(
        _plan(), '2026-11-12T00:00:00+02:00').state == PREPARED

    record, _ = _apply_steps(_record(), _steps()[:3])
    with pytest.raises(WriteContractError):
        transition(record, REPLACED, _replaced_evidence(
            replaced_at='2026-11-12T00:00:01'))
    record, _ = _apply_steps(_record(), _steps()[:8])
    with pytest.raises(WriteContractError):
        transition(record, COMMITTED, {
            'committed_at': '2026-11-12T00:00:02',
        })


def test_committed_requires_all_postconditions():
    record = _committed_record()
    with pytest.raises(WriteContractError):
        assert_committed(transition(record, PREPARED, {}))
    assert record.evidence['manifest_required'] is False
    assert record.evidence['pins_applied'] is False
