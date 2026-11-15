"""Tests del arnés HU-P5: escenarios reales y sintéticos separados."""
import pytest

from motor.hu_scenarios import (
    DATA_SNAPSHOT_SHA256, PreflopScenario, REAL_PREFLOP_SCENARIOS,
    SYNTHETIC_PREFLOP_SCENARIOS, all_preflop_scenarios,
    run_all_preflop_scenarios, run_preflop_scenario,
)
from motor.preflop_canonical import canonical_preflop


def test_escenarios_reales_llevan_identidad_y_no_se_mezclan():
    assert REAL_PREFLOP_SCENARIOS
    for scenario in REAL_PREFLOP_SCENARIOS:
        assert scenario.source_kind == 'real'
        assert scenario.hand_id
        assert scenario.data_snapshot_hash
    assert SYNTHETIC_PREFLOP_SCENARIOS
    for scenario in SYNTHETIC_PREFLOP_SCENARIOS:
        assert scenario.source_kind == 'synthetic'
        assert scenario.hand_id is None
        assert scenario.data_snapshot_hash is None


def test_no_se_puede_declarar_un_real_sin_identidad():
    with pytest.raises(ValueError):
        PreflopScenario(
            scenario_id='x', source_kind='real', hero_position='UTG',
            actions=({'pos': 'UTG', 'action': 'b', 'amount': 2.5},),
            expected={'canonical_status': 'resolved'})
    with pytest.raises(ValueError):
        PreflopScenario(
            scenario_id='x', source_kind='synthetic', hero_position='UTG',
            hand_id='H_1', data_snapshot_hash='abc',
            actions=({'pos': 'UTG', 'action': 'b', 'amount': 2.5},),
            expected={'canonical_status': 'resolved'})


def test_arnes_ejecuta_todos_los_escenarios_declarados():
    results = run_all_preflop_scenarios()
    assert len(results) == len(all_preflop_scenarios())
    assert all(r.passed for r in results), [
        (r.scenario_id, [c.as_dict() for c in r.checks if not c.passed])
        for r in results if not r.passed]


def test_escenario_sintetico_controlado_detecta_regresion():
    scenario = PreflopScenario(
        scenario_id='x', source_kind='synthetic', hero_position='UTG',
        actions=(
            {'pos': 'SB', 'action': 'p', 'amount': 0.5},
            {'pos': 'BB', 'action': 'p', 'amount': 1.0},
            {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        ),
        expected={'category': '3bet'})
    result = run_preflop_scenario(scenario)
    assert result.passed is False
    assert result.actual['category'] == 'open'
    assert any(c.field == 'category' and not c.passed
               for c in result.checks)


def test_escenario_real_no_lee_la_base_para_decidir():
    scenario = REAL_PREFLOP_SCENARIOS[0]
    result = run_preflop_scenario(scenario)
    assert result.passed
    assert result.decision.status == 'resolved'
    assert result.decision.classification.category == 'open'
    assert result.decision.action_ready is True

def test_hash_de_snapshot_es_el_completo_y_lo_usan_los_reales():
    assert DATA_SNAPSHOT_SHA256 == (
        '3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E')
    assert len(DATA_SNAPSHOT_SHA256) == 64
    for scenario in REAL_PREFLOP_SCENARIOS:
        assert scenario.data_snapshot_hash == DATA_SNAPSHOT_SHA256


def test_r10_es_la_apertura_de_sb_de_h0066_no_el_bb_reasignado():
    by_id = {s.scenario_id: s for s in REAL_PREFLOP_SCENARIOS}
    r10 = by_id['R10_sb_open_after_folds']
    assert r10.hand_id == 'H_0066'
    assert r10.hero_position == 'SB'
    assert r10.actions[-2:] == (
        {'pos': 'SB', 'action': 'r', 'amount': 3.0},
        {'pos': 'BB', 'action': 'c', 'amount': 3.0},
    )
    result = run_preflop_scenario(r10)
    assert result.passed, [c.as_dict() for c in result.checks]
    assert result.decision.classification.category == 'open'
    assert result.decision.decision_plan.table_raise == 'OR'


def test_r18_conserva_la_secuencia_completa_de_h0032():
    by_id = {s.scenario_id: s for s in REAL_PREFLOP_SCENARIOS}
    r18 = by_id['R18_h0032_bb_vs_sb_3bet']
    assert r18.hand_id == 'H_0032'
    assert r18.hero_position == 'BB'
    assert r18.actions[5] == {
        'pos': 'SB', 'action': 'r', 'amount': 5.0,
        'amount_semantics': 'absoluta'}
    assert r18.actions[-1] == {'pos': 'SB', 'action': 'c', 'amount': 9.0}
    result = run_preflop_scenario(r18)
    assert result.passed, [c.as_dict() for c in result.checks]
    assert result.decision.classification.category == '3bet'
    assert result.decision.decision_plan.table_raise == '3B'


def test_at_index_no_aplica_a_escenarios_historicos():
    with pytest.raises(ValueError):
        PreflopScenario(
            scenario_id='x', source_kind='synthetic', hero_position='UTG',
            mode='historical', at_index=0,
            actions=({'pos': 'UTG', 'action': 'b', 'amount': 2.5},),
            expected={'canonical_status': 'resolved'})
    with pytest.raises(ValueError):
        canonical_preflop(
            [{'pos': 'UTG', 'action': 'b', 'amount': 2.5}], 'UTG',
            mode='historical', at_index=0)
