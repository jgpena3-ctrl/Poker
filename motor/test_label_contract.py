# -*- coding: utf-8 -*-
"""P0-5 — pruebas del contrato contextual de etiquetas (sombra)."""
import hashlib
import json
import os

import numpy as np
import pytest

from .label_contract import (
    FIRST_RELIABILITY_BAND,
    LABEL_UNKNOWN,
    STATE_CURRENT,
    STATE_HISTORICAL,
    STATE_INCOMPATIBLE,
    STATE_INSUFFICIENT,
    STATE_PROVISIONAL,
    STATE_UNKNOWN,
    STATUS_COINCIDENT,
    STATUS_DIFFERENT,
    STATUS_HISTORICAL_NOT_REPRODUCIBLE,
    STATUS_INCOMPATIBLE,
    STATUS_INSUFFICIENT,
    STATUS_SERVING_UNAVAILABLE,
    STATUS_UNKNOWN,
    compare_labels,
    historical_decision,
    historical_evidence_diffs,
    label_audit,
    serving_decision,
    simple_label,
    training_decision,
)
from .profile import HANDS_BANDS, PEZ, TIBURON, PlayerProfile, Profiles


PROV = {
    'provenance': 'test',
    'provenance_status': 'partial',
    'window': 'test',
    'window_hash': None,
    'built_commit': None,
    'code_dirty': False,
    'hands_n': 10,
}


def _profile(name='X', n=10, stats=None, counts=None, stack=None):
    return PlayerProfile(name, n=n, stats=stats, counts=counts,
                         stack_mean=stack)


# ---------------------------------------------------------------------------
# Reglas
# ---------------------------------------------------------------------------

def test_simple_label_precedence_and_strict_thresholds():
    # El stack manda incluso si las stats dirían lo contrario.
    assert simple_label(0.0, 1.0, 49.9) == PEZ
    assert simple_label(0.0, 1.0, 50.0) == TIBURON
    # Fallback estricto: >0.32 y <0.10.
    assert simple_label(0.33, 0.09, 50.0) == PEZ
    assert simple_label(0.32, 0.09, 50.0) == TIBURON
    assert simple_label(0.33, 0.10, 50.0) == TIBURON
    # Sin información no se inventa PEZ.
    assert simple_label(None, None, None) == TIBURON


def test_training_stack_rule_is_provisional_with_small_stack_sample():
    p = _profile(n=2, stats={'vpip': 0.5, 'pfr': 0.5},
                 counts={'vpip': (2, 1), 'pfr': (2, 1)}, stack=48.8)
    d = training_decision(p, 2, 877, provenance=PROV)
    assert d.label == PEZ
    assert d.method == 'stack_mean_lt_50bb'
    assert d.state == STATE_PROVISIONAL
    assert d.variables['stack_mean_bb'] == 48.8
    assert d.relevant_observations['stack_observations'] == 2
    assert d.reproducible is True
    assert d.valid_for_serving is True
    assert any('margen' in u for u in d.uncertainty)


def test_training_fallback_traces_vpip_pfr():
    p = _profile(n=1, stats={'vpip': 1.0, 'pfr': 0.0},
                 counts={'vpip': (1, 1), 'pfr': (1, 0)}, stack=123.5)
    d = training_decision(p, 1, 877, provenance=PROV)
    assert d.label == PEZ
    assert d.method == 'loose_passive_fallback'
    assert d.variables['vpip'] == 1.0
    assert d.variables['pfr'] == 0.0
    assert d.relevant_observations['vpip_opp'] == 1
    assert d.relevant_observations['pfr_opp'] == 1
    assert d.state == STATE_PROVISIONAL


def test_training_missing_evidence_is_insufficient_not_valid_tiburon():
    p = _profile(n=0)
    d = training_decision(p, 0, 877, provenance=PROV)
    assert d.label == TIBURON  # salida efectiva del clasificador actual
    assert d.contract_label == LABEL_UNKNOWN  # el contrato no la valida
    assert d.state == STATE_INSUFFICIENT
    assert d.method == 'default_no_evidence'
    assert d.valid_for_serving is False
    assert d.rules_blocking
    assert any('sin ninguna evidencia' in u for u in d.uncertainty)


def test_training_missing_stats_does_not_invent_fallback():
    p = _profile(n=5, stats={}, stack=60.0)
    d = training_decision(p, 5, 877, provenance=PROV)
    assert d.label == TIBURON
    assert d.state == STATE_INSUFFICIENT
    assert d.method == 'default_rest_no_stats'
    assert d.valid_for_serving is False
    assert any('VPIP/PFR' in b for b in d.rules_blocking)


def test_first_reliability_band_is_reused_not_invented():
    assert FIRST_RELIABILITY_BAND == HANDS_BANDS[0][0] == 40


# ---------------------------------------------------------------------------
# Serving
# ---------------------------------------------------------------------------

def test_serving_uses_only_stack_and_actual_classifier():
    low = serving_decision('p1', [49.9], source='test')
    high = serving_decision('p1', [50.0], source='test')
    none = serving_decision('p1', [], state={}, source='test')
    assert low.label == PEZ
    assert high.label == TIBURON
    assert none.label == TIBURON
    assert none.contract_label == LABEL_UNKNOWN
    assert none.state == STATE_INSUFFICIENT
    assert none.method == 'default_tiburon_no_info'
    # El contrato de serving no incorpora VPIP/PFR: no existen en sus variables.
    assert 'vpip' not in low.variables
    assert 'pfr' not in low.variables
    assert any('no usa VPIP' in u for u in low.uncertainty)


def test_serving_current_stack_branch_without_session_history():
    d = serving_decision('p1', [], state={'p1_stake': 49.0},
                         source='test')
    assert d.label == PEZ
    assert d.method == 'current_stack_lt_50bb'
    assert d.state == STATE_CURRENT
    d2 = serving_decision('p1', [], state={'p1_stake': 50.0},
                          source='test')
    assert d2.label == TIBURON


def test_stack_rule_parity_with_same_evidence():
    for value in (0.0, 1.0, 49.999, 50.0, 100.0):
        train = simple_label(None, None, value)
        mean = serving_decision('p', [value], source='test')
        stake = serving_decision('p', [], state={'p_stake': value},
                                 source='test')
        assert train == mean.label == stake.label
    assert simple_label(None, None, None) == TIBURON


# ---------------------------------------------------------------------------
# Histórico
# ---------------------------------------------------------------------------

def test_historical_decision_does_not_fill_missing_fields():
    d = historical_decision('X', {'player': 'X', 'label': PEZ,
                                  'stats': {}, 'n': 2})
    assert d.label == PEZ
    assert d.contract_label == LABEL_UNKNOWN  # no reproducible sin campos
    assert d.state == STATE_HISTORICAL
    assert d.hands_n is None
    assert d.relevant_observations['pfr_opp'] is None
    assert d.relevant_observations['stack_observations'] is None
    assert d.reproducible is False
    assert d.window_hash is None
    assert d.built_commit is None
    assert any('no registra' in u for u in d.uncertainty)


def test_historical_consistent_fields_make_label_reproducible():
    d = historical_decision('X', {
        'label': PEZ, 'stats': {'vpip': 1.0, 'pfr': 0.0},
        'stack_mean': 123.5})
    assert d.reproducible is True
    assert d.contract_label == PEZ
    assert d.state == STATE_HISTORICAL


def test_historical_entry_without_label_is_unknown_not_tiburon():
    d = historical_decision('X', {'player': 'X', 'stats': {}})
    assert d.label == LABEL_UNKNOWN
    assert d.contract_label == LABEL_UNKNOWN
    assert d.state == STATE_UNKNOWN
    assert d.reproducible is False


def test_historical_entry_missing_is_unknown():
    d = historical_decision('X', None)
    assert d.label == LABEL_UNKNOWN
    assert d.state == STATE_UNKNOWN
    assert d.method == 'historical_entry_missing'


def test_historical_incompatible_provenance_marks_state(monkeypatch):
    import motor.label_contract as lc

    monkeypatch.setattr(lc, '_historical_provenance', lambda: {
        'provenance': 'test', 'provenance_status': 'incompatible',
        'artifact_hash_matches': False, 'window': None,
        'window_hash': None, 'built_commit': None, 'hands_n': None,
        'code_dirty': False,
    })
    d = lc.historical_decision('X', {'label': PEZ, 'stats': {},
                                    'stack_mean': None})
    assert d.state == STATE_INCOMPATIBLE
    assert d.contract_label == LABEL_UNKNOWN
    assert d.valid_for_serving is False


def test_compare_labels_unknown_and_historical_mismatch():
    training = training_decision(
        _profile(n=10, stats={'vpip': 0.2, 'pfr': 0.2},
                 counts={'vpip': (10, 2), 'pfr': (10, 2)}, stack=60.0),
        10, 877, provenance=PROV)
    unknown = historical_decision('X', None)
    serving = serving_decision('X', [60.0], source='test')
    c = compare_labels(training, unknown, serving)
    assert c.status == STATUS_UNKNOWN

    other = historical_decision('X', {
        'label': PEZ, 'stats': {'vpip': 0.2, 'pfr': 0.2},
        'stack_mean': 60.0})
    c2 = compare_labels(training, other, serving)
    assert c2.status == STATUS_HISTORICAL_NOT_REPRODUCIBLE


def test_compare_labels_insufficient_and_incompatible():
    p = _profile(n=0)
    training = training_decision(p, 0, 877, provenance=PROV)
    hist = historical_decision('X', {
        'label': TIBURON, 'stats': {'vpip': 0.0, 'pfr': 0.0},
        'stack_mean': 60.0})
    serving = serving_decision('X', [], source='test')
    c = compare_labels(training, hist, serving)
    assert c.status == STATUS_INSUFFICIENT

    bad = training_decision(p, 0, 877, provenance=dict(
        PROV, provenance_status='incompatible'))
    assert bad.state == STATE_INCOMPATIBLE
    c2 = compare_labels(bad, hist, serving)
    assert c2.status == STATUS_INCOMPATIBLE


# ---------------------------------------------------------------------------
# Auditoría reproducible
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def audit():
    return label_audit()


def test_audit_training_counts(audit):
    assert audit['hands_in_window'] == 877
    assert audit['training']['players'] == 138
    assert audit['training']['labels'] == {PEZ: 78, TIBURON: 60}
    assert audit['training']['provisional'] == 105
    assert audit['training']['current'] == 33
    assert audit['training']['insufficient'] == 0


def test_audit_historical_labels_and_evidence(audit):
    h = audit['historical']
    assert h['players'] == 139
    assert h['common_with_current'] == 138
    assert h['coincident'] == 138
    assert h['different'] == 0
    assert h['only_historical'] == ['HERO']
    assert h['only_current'] == []
    assert h['provenance_status'] == 'partial'
    assert h['artifact_hash_matches'] is True
    # La etiqueta coincide, pero el artefacto NO es una reproducción
    # byte-a-byte de los contadores/estadísticas actuales.
    diffs = h['evidence_diffs']
    assert diffs['n_different'] == 12
    assert diffs['stats_different'] == 24
    assert diffs['stack_mean_different'] == 1


def test_audit_historical_hero_is_not_reproducible(audit):
    rows = audit['historical']['only_historical_rows']
    assert len(rows) == 1
    row = rows[0]
    assert row['player'] == 'HERO'
    assert row['status'] == STATUS_HISTORICAL_NOT_REPRODUCIBLE
    assert row['state'] == STATE_INCOMPATIBLE
    assert row['current_evidence_available'] is False
    assert row['label'] == TIBURON
    assert row['contract_label'] == LABEL_UNKNOWN
    assert row['hands_n'] is None
    assert row['relevant_observations']['pfr_opp'] is None
    assert row['relevant_observations']['stack_observations'] is None


def test_audit_serving_counts_and_parity(audit):
    mean = audit['serving_session_mean']['counts']
    last = audit['serving_current_stack']['counts']
    assert mean == {STATUS_COINCIDENT: 116,
                    STATUS_SERVING_UNAVAILABLE: 22}
    assert last == {STATUS_COINCIDENT: 98,
                    STATUS_SERVING_UNAVAILABLE: 18,
                    STATUS_DIFFERENT: 22}
    assert audit['parity_stack_rule']['same_evidence_mean']['errors'] == []
    assert audit['parity_stack_rule']['same_evidence_last']['errors'] == []
    # Toda diferencia con el stack actual tiene una razón declarada.
    reasons = {d['reason'] for d in audit['differences_current_stack']}
    assert reasons
    assert all(r for r in reasons)


def test_audit_small_samples_four_players(audit):
    by_name = {s['player']: s for s in audit['small_samples']}
    assert set(by_name) == {'Valentina22', 'Sp1609', 'Ocampo99', 'Nnn1'}

    v = by_name['Valentina22']
    assert v['training']['label'] == PEZ
    assert v['training']['method'] == 'stack_mean_lt_50bb'
    assert v['training']['state'] == STATE_PROVISIONAL
    assert v['n_vpip_opportunities'] == 2
    assert v['stack_mean_bb'] == 48.8
    assert abs(v['stack_margin_bb'] - 1.2) < 1e-9
    assert v['comparison_session_mean']['status'] == STATUS_COINCIDENT
    assert v['comparison_current_stack']['status'] == STATUS_COINCIDENT
    assert v['historical_label_reproducible_from_fields'] is True

    for name, n in (('Sp1609', 1), ('Ocampo99', 2), ('Nnn1', 2)):
        s = by_name[name]
        assert s['training']['label'] == PEZ
        assert s['training']['method'] == 'loose_passive_fallback'
        assert s['training']['state'] == STATE_PROVISIONAL
        assert s['n_vpip_opportunities'] == n
        assert s['current_evidence_available'] is True
        assert s['historical_label_reproducible_from_fields'] is True
        assert s['comparison_session_mean']['status'] == \
            STATUS_SERVING_UNAVAILABLE
        assert s['comparison_current_stack']['status'] == \
            STATUS_SERVING_UNAVAILABLE


def test_historical_evidence_diffs_do_not_claim_identity():
    from .learn import load_hands

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, 'data', 'profiles.json'),
              encoding='utf-8') as f:
        hist = json.load(f)
    profs = Profiles.from_hands(load_hands(reliable_only=True))
    diffs = historical_evidence_diffs(profs, hist)
    assert diffs['common_players'] == 138
    assert diffs['n_different'] == 12
    assert diffs['stats_different'] == 24
    assert diffs['stack_mean_different'] == 1
    assert diffs['note']


# ---------------------------------------------------------------------------
# No cambio efectivo
# ---------------------------------------------------------------------------

def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def test_audit_is_read_only_on_canonical_data():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    names = ['hands_db.jsonl', 'profiles.json', 'calibration_window.json',
             'preflop_matrices.json']
    paths = [os.path.join(root, 'data', n) for n in names]
    before = {p: _sha256(p) for p in paths}
    label_audit()
    after = {p: _sha256(p) for p in paths}
    assert before == after


def test_audit_does_not_change_models_labels_or_vectors():
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        from .asistente_live import build_models

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

    result = label_audit()

    assert result['training']['labels'] == {PEZ: 78, TIBURON: 60}
    assert digest(pf) == digest_before
    assert dict(models.labels) == labels_before
    vec_after = pf.prob_vec(label, 'turn', 'x', ['Qh', '7s', '2c'], 'b')
    assert np.array_equal(vec_before, vec_after)
