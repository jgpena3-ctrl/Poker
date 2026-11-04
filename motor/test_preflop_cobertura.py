"""Cobertura preflop: alias, ausencias intencionales y huecos reales."""
from motor.asistente_live import _pf_table_audit, _sample_preflop_action
from motor.preflop import (audit_engine_coverage, classify_missing_table,
                           lookup_table)


def test_alias_declarado_hj_es_mp():
    table, source, status = lookup_table('4B', 'UTG', 'MP')
    assert table is not None
    assert source == '4B_UTG_vs_HJ'
    assert status == 'alias'


def test_ausencias_intencionales_no_son_huecos():
    assert classify_missing_table('OR', 'BB', '') == \
        'intentional_check_option'
    assert classify_missing_table('ROL', 'UTG', '') == \
        'intentional_no_prior_limp'


def test_orden_imposible_no_es_hueco_de_cobertura():
    # El BTN actúa después del CO: el CO no puede enfrentar su raise.
    assert classify_missing_table('3B', 'CO', 'BTN') == \
        'impossible_action_order'
    # Para 4B hacen falta dos raisers anteriores; el UTG no puede ser el
    # último raiser del MP.
    assert classify_missing_table('4B', 'MP', 'UTG') == \
        'impossible_action_order'


def test_huecos_reales_se_declaran():
    assert classify_missing_table('Call_OR', 'SB', 'BTN') == 'coverage_gap'
    assert classify_missing_table('Call_3B', 'BB', 'SB') == 'coverage_gap'
    assert classify_missing_table('4B', 'BB', 'SB') == 'coverage_gap'


def test_auditoria_del_grammar_del_motor_no_tiene_ausencias_sin_clasificar():
    audit = audit_engine_coverage()
    assert audit['alias'] == [
        {'key': '4B_UTG_vs_MP', 'source': '4B_UTG_vs_HJ'},
    ]
    assert audit['unclassified_missing'] == []
    assert {item['key'] for item in audit['intentional_missing']} == {
        'OR_BB', 'ROL_UTG'}


def test_auditoria_de_un_spot_marca_fallback_y_hueco():
    audit = _pf_table_audit([
        ('4B', 'UTG', 'MP'),
        ('Call_OR', 'SB', 'BTN'),
        ('4B', 'BTN', 'MP'),
        ('4B', 'BB', 'SB'),
        ('OR', 'BB', ''),
    ])
    by_key = {item['key']: item for item in audit}
    assert by_key['4B_UTG_vs_MP']['status'] == 'alias'
    assert by_key['Call_OR_SB_vs_BTN']['status'] == 'missing'
    assert by_key['Call_OR_SB_vs_BTN']['classification'] == 'coverage_gap'
    assert by_key['4B_BTN_vs_MP']['status'] == 'fallback_other_vs'
    assert by_key['4B_BTN_vs_MP']['source'] == '4B_BTN_vs_BB'
    assert by_key['4B_BTN_vs_MP']['classification'] == 'coverage_gap'
    assert by_key['4B_BB_vs_SB']['status'] == 'missing'
    assert by_key['4B_BB_vs_SB']['classification'] == 'coverage_gap'
    assert by_key['OR_BB']['classification'] == 'intentional_check_option'


def test_el_sorteo_preflop_es_reproducible_con_la_misma_semilla():
    ev = {'retirar': 0.5, 'subir': 0.3, 'igualar': 0.2}
    first, meta1 = _sample_preflop_action(ev, seed=987654321)
    second, meta2 = _sample_preflop_action(ev, seed=987654321)
    assert first == second
    assert meta1['seed'] == meta2['seed'] == 987654321
    assert meta1['distribution'] == ev
    assert meta1['mechanism'] == 'weighted_choice_with_replacement'


def test_sin_semilla_se_genera_y_se_registra_una():
    _action, meta = _sample_preflop_action({'retirar': 1.0})
    assert isinstance(meta['seed'], int)
    assert meta['seed'] >= 0
