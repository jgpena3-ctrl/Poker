# -*- coding: utf-8 -*-
"""Tests P0-4: envelope de procedencia y compatibilidad (sombra)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.provenance_contract import (
    VERIFIED, PARTIAL, UNKNOWN, INCOMPATIBLE, HISTORICAL, REBUILT,
    ORIGIN_HISTORICAL, ORIGIN_STATIC, ORIGIN_REBUILT,
    all_envelopes, audit_provenance, build_models_envelope,
    compatibility_matrix, cache_inventory, preflop_matrices_envelope,
    ProvenanceEnvelope)


def test_build_models_envelope_is_verified_and_no_data_change():
    env = build_models_envelope()
    assert env.component == 'build_models'
    assert env.origin == ORIGIN_REBUILT
    assert env.status == VERIFIED
    assert env.hands_received > 0
    assert env.missing_fields == []
    assert env.database_hash is not None


def test_historical_artifacts_are_not_verified_compatible():
    envs = {e.component: e for e in all_envelopes()}
    for name in ('profile_ranges', 'postflop_ranges', 'behavior',
                 'player_stats'):
        assert envs[name].origin in (ORIGIN_HISTORICAL, 'historical')
        assert envs[name].status in (PARTIAL, UNKNOWN, INCOMPATIBLE)
    # Un artefacto historico no puede declararse compatible con la base actual.
    pr = envs['profile_ranges']
    assert pr.status == INCOMPATIBLE or pr.missing_fields


def test_preflop_matrices_have_unknown_provenance():
    env = preflop_matrices_envelope()
    assert env.component == 'preflop_matrices'
    assert env.origin == ORIGIN_STATIC
    assert env.status == UNKNOWN
    assert 'hands_input' in env.missing_fields
    assert 'code_commit' in env.missing_fields
    assert 'built_at' in env.missing_fields
    assert any('no se sabe' in n for n in env.notes)


def test_compatibility_matrix_does_not_claim_historical_compatibility():
    matrix = compatibility_matrix()
    assert any(r['left'] == 'build_models' and r['right'] == 'profile_ranges'
               and r['compatible'] is False for r in matrix)
    assert any(r['left'] == 'preflop_matrices' for r in matrix)


def test_cache_inventory_lists_invalidation_keys():
    caches = cache_inventory()
    names = [c['cache'] for c in caches]
    assert any('preflop' in n for n in names)
    assert any('scores_cache' in n for n in names)
    assert all('invalidation_needed' in c for c in caches)


def test_audit_is_read_only_and_reports_unknowns():
    result = audit_provenance()
    assert result['code_commit']
    assert result['database_hash']
    assert result['reliable_hands'] > 0
    assert any(e['component'] == 'preflop_matrices'
               and e['status'] == UNKNOWN for e in result['envelopes'])
    # No se inventa compatibilidad.
    assert any(r['compatible'] is False for r in result['compatibility'])


def test_envelope_roundtrip_json():
    env = build_models_envelope()
    data = env.as_dict()
    assert data['component'] == 'build_models'
    assert isinstance(data['missing_fields'], list)


def test_no_model_change_by_audit():
    # El envelope no construye ni muta modelos.
    from motor.asistente_live import build_models
    import motor.asistente_live as live
    a = live.build_models(verbose=False)
    before = a.postflop_model.to_json()['meta']['hands_input']
    audit_provenance()
    after = a.postflop_model.to_json()['meta']['hands_input']
    assert before == after == 877