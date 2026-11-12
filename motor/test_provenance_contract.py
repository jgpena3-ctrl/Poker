# -*- coding: utf-8 -*-
"""Tests P0-4: envelope de procedencia y compatibilidad (sombra)."""
import hashlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.provenance_contract import (  # noqa: E402
    CLASS_HISTORICAL_ONLY,
    CLASS_NOT_SUITABLE,
    HISTORICAL,
    INCOMPATIBLE,
    ORIGIN_HISTORICAL,
    ORIGIN_REBUILT,
    ORIGIN_STATIC,
    PARTIAL,
    UNKNOWN,
    all_envelopes,
    artifact_readers_inventory,
    audit_provenance,
    auxiliary_tool_flows,
    build_models_envelope,
    cache_inventory,
    compatibility_matrix,
    detect_mixture,
    mixture_cases,
    preflop_matrices_envelope,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _components():
    return {e.component: e for e in all_envelopes()}


def _sha(path):
    with open(os.path.join(ROOT, path), 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_build_models_is_partial_not_verified():
    env = build_models_envelope()
    assert env.component == 'build_models'
    assert env.origin == ORIGIN_REBUILT
    # B1 declara la reproduccion de la base como no demostrada: no se puede
    # vender como verified.
    assert env.status == PARTIAL
    assert env.database_hash is not None
    assert env.hands_received == 877
    assert any('B1' in n for n in env.notes)
    assert any('provisional' in n for n in env.notes)


def test_window_hash_matches_calibration_window():
    env = build_models_envelope()
    with open(os.path.join(ROOT, 'data', 'calibration_window.json'),
              encoding='utf-8') as f:
        cw = json.load(f)
    assert env.window_hash == cw['window']['selected_lines_sha256']
    assert env.window_id and '877' in env.window_id
    assert env.window_hash_source == 'data/calibration_window.json'


def test_all_seven_historical_derivatives_are_inventoried_and_identified():
    envs = _components()
    names = ('profile_ranges', 'postflop_ranges', 'preflop_stats',
             'player_stats', 'profiles', 'behavior', 'observations')
    with open(os.path.join(ROOT, 'data', 'calibration_window.json'),
              encoding='utf-8') as f:
        canonical = json.load(f)['derivatives']['canonical_sha256']
    for name in names:
        env = envs[name]
        assert env.origin == ORIGIN_HISTORICAL
        assert env.status == PARTIAL
        assert env.artifact_hash_matches is True
        assert env.expected_artifact_hash == canonical[
            os.path.basename(env.source_path)]
        # El hash de base del artefacto historico no se inventa.
        assert env.database_hash is None
        assert any('no se hereda el hash actual' in n for n in env.notes)


def test_historical_artifacts_never_declared_current_compatible():
    envs = _components()
    for name in ('profile_ranges', 'postflop_ranges', 'behavior',
                 'player_stats', 'profiles', 'preflop_stats',
                 'observations'):
        assert envs[name].status != 'verified'
    pr = envs['profile_ranges']
    assert pr.status in (PARTIAL, INCOMPATIBLE)


def test_preflop_matrices_have_unknown_provenance():
    env = preflop_matrices_envelope()
    assert env.component == 'preflop_matrices'
    assert env.origin == ORIGIN_STATIC
    assert env.status == UNKNOWN
    assert env.artifact_hash
    for field in ('database_hash', 'hands_received', 'window',
                  'window_hash', 'code_commit', 'built_at'):
        assert field in env.missing_fields
    assert any('no se sabe' in n for n in env.notes)
    assert any('no declarar compatible' in n for n in env.notes)


def test_compatibility_is_computed_from_envelopes():
    matrix = compatibility_matrix()
    by_pair = {(r['left'], r['right']): r for r in matrix}
    assert by_pair[('build_models', 'profile_ranges')]['compatible'] is False
    assert by_pair[('build_models', 'postflop_ranges')]['compatible'] is False
    assert by_pair[('build_models', 'behavior')]['compatible'] is False
    assert by_pair[('build_models', 'preflop_matrices')]['compatible'] is None
    assert by_pair[('ranges', 'preflop_matrices')]['compatible'] is None
    hist = by_pair[('profile_ranges', 'postflop_ranges')]
    assert hist['compatible'] is True
    assert hist['scope'] == 'historical_only'
    current = by_pair[('build_models', 'oracle_priors')]
    assert current['compatible'] is True
    assert current['scope'] == 'current'


def test_mixture_cases_register_what_would_be_blocked():
    cases = {c['case']: c for c in mixture_cases()}
    incompatible = cases['reconstruido_vs_perfil_historico']
    assert incompatible['would_block'] is True
    assert incompatible['verdict'] == 'incompatible'
    unknown = cases['reconstruido_vs_matrices_sin_procedencia']
    assert unknown['would_block'] is False
    assert unknown['would_warn'] is True
    assert unknown['verdict'] == 'unknown'


def test_detect_mixture_rejects_uninventoried_components():
    result = detect_mixture(['build_models', 'no_existe'])
    assert result['verdict'] == 'unknown'
    assert result['would_warn'] is True
    assert 'no inventariados' in result['error']


def test_auxiliary_tools_classification_and_flow():
    envs = _components()
    diag = envs['diagnosticar_56_154']
    assert diag.classification == CLASS_HISTORICAL_ONLY
    assert diag.origin == ORIGIN_HISTORICAL
    assert diag.status == HISTORICAL
    assert any('snapshot' in n for n in diag.notes)
    gui = envs['range_lab_gui']
    assert gui.classification == CLASS_NOT_SUITABLE
    assert gui.status == INCOMPATIBLE
    assert any('mezclando' in n or 'mezcla' in n for n in gui.notes)
    assert any('no comunica' in n for n in gui.notes)
    flows = {f['tool']: f for f in auxiliary_tool_flows()}
    assert flows['diagnosticar_56_154']['models_built'] == []
    assert 'Oracle(build(hands, labels)) si _oracle is None' in (
        flows['range_lab_gui']['models_built'])
    assert flows['range_lab_gui']['classification'] == CLASS_NOT_SUITABLE


def test_readers_do_not_check_provenance():
    rows = {r['reader']: r for r in artifact_readers_inventory()}
    assert rows['PostflopRangeModel.load']['checks_provenance'] is False
    assert rows['PostflopRangeModel.load']['drops_oracle'] is True
    assert rows['ProfileRangeModel.load']['checks_provenance'] is False


def test_cache_inventory_lists_invalidation_keys():
    caches = {c['cache']: c for c in cache_inventory()}
    for name in ('_TABLES (preflop.py)',
                 '_tables_cache (player_ranges.py)',
                 '_scores_cache (PostflopRangeModel)',
                 '_poblacion (Oracle)',
                 '_omega (ProfileRangeModel)',
                 '_base_rates (Profiles)'):
        assert name in caches
        assert caches[name]['invalidation_needed']
        assert caches[name]['depends_on']
    assert caches['_TABLES (preflop.py)']['survives_base_change'] is True
    assert caches['_poblacion (Oracle)']['survives_base_change'] is False


def test_audit_is_read_only_and_reports_unknowns():
    before = {name: _sha('data/' + name) for name in (
        'hands_db.jsonl', 'profile_ranges.json', 'postflop_ranges.json',
        'behavior.json', 'preflop_matrices.json')}
    result = audit_provenance()
    after = {name: _sha('data/' + name) for name in before}
    assert before == after
    assert result['code_commit']
    assert result['database_hash']
    assert result['reliable_hands'] == 877
    assert result['window']['window_hash']
    assert any(e['component'] == 'preflop_matrices'
               and e['status'] == UNKNOWN for e in result['envelopes'])
    assert any(r['compatible'] is False for r in result['compatibility'])
    assert result['notes']


def test_envelope_roundtrip_json():
    env = build_models_envelope()
    data = env.as_dict()
    assert data['component'] == 'build_models'
    assert isinstance(data['missing_fields'], list)
    assert data['window_hash']


def test_audit_does_not_change_models_or_vectors():
    import numpy as np
    from motor.asistente_live import build_models

    models = build_models(verbose=False)
    pf = models.postflop_model

    def digest(model):
        doc = model.to_json()
        doc.pop('meta', None)
        payload = json.dumps(
            doc, sort_keys=True, default=lambda o: o.tolist())
        return hashlib.sha256(payload.encode()).hexdigest()

    labels_before = dict(models.labels)
    digest_before = digest(pf)
    label = labels_before.get('ALKILADO') or next(iter(labels_before.values()))
    vec_before = pf.prob_vec(label, 'turn', 'x', ['Qh', '7s', '2c'], 'b')

    audit_provenance()

    assert digest(pf) == digest_before
    assert dict(models.labels) == labels_before
    vec_after = pf.prob_vec(label, 'turn', 'x', ['Qh', '7s', '2c'], 'b')
    assert np.array_equal(vec_before, vec_after)
