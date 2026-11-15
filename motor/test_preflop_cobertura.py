"""Cobertura preflop: alias, ausencias intencionales y huecos reales."""
from motor.asistente_live import (_pf_coverage_lookup, _pf_evs, _pf_freq,
                                  _pf_table_audit, _pf_table_lookup,
                                  _sample_preflop_action)
from motor.preflop import (_ENGINE_PAIR_ACTIONS, _PREFLOP_ORDER,
                           audit_engine_coverage, classify_missing_table,
                           load_tables, lookup_table, table_key)
from motor.preflop_coverage import CoverageRequest, resolve_coverage


def _engine_queries():
    """Mismo universo de consultas que audit_engine_coverage()."""
    queries = []
    for pos in _PREFLOP_ORDER:
        queries.append(('OR', pos, ''))
        queries.append(('ROL', pos, ''))
        for vs in _PREFLOP_ORDER:
            if vs == pos:
                continue
            for action in _ENGINE_PAIR_ACTIONS:
                queries.append((action, pos, vs))
    return queries


def _historical_lookup(action, pos='', vs=''):
    """Replica el lookup anterior, solo como referencia de regresión."""
    if pos:
        table, source, status = lookup_table(action, pos, vs)
        if table is not None:
            return table['probs'], source, status
        for key, candidate in sorted(load_tables().items()):
            if candidate['action'] == action and candidate['pos'] == pos:
                return candidate['probs'], key, 'fallback_other_vs'
    return None, None, 'missing'


def _historical_frequency(query, hand_idx):
    probs, _source, _status = _historical_lookup(*query)
    return None if probs is None else float(probs[hand_idx])


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


def test_pf_coverage_lookup_preserves_historical_tuple():
    from motor.asistente_live import _pf_coverage_lookup
    probs, source, status, resolution = _pf_coverage_lookup('OR', 'UTG', '')
    assert status == 'exact'
    assert probs is not None
    assert source == 'OR_UTG'
    assert resolution.coverage_state == 'exact'


def test_pf_coverage_lookup_or_bb_is_impossible():
    from motor.asistente_live import _pf_coverage_lookup
    probs, source, status, resolution = _pf_coverage_lookup('OR', 'BB', '')
    assert probs is None
    assert status == 'missing'
    assert resolution.coverage_state == 'impossible'


def test_pf_table_audit_keeps_canonical_metadata():
    from motor.asistente_live import _pf_table_audit
    audit = _pf_table_audit([('OR', 'UTG', '')])
    item = audit[0]
    assert item['coverage_state'] == 'exact'
    assert item['fallback_used'] is False
    assert item['approximation_used'] is False
    assert 'source_key' in item


def test_sin_semilla_se_genera_y_se_registra_una():
    _action, meta = _sample_preflop_action({'retirar': 1.0})
    assert isinstance(meta['seed'], int)
    assert meta['seed'] >= 0


def test_pf_coverage_lookup_preserves_historical_alias():
    probs, source, status, resolution = _pf_coverage_lookup(
        '4B', 'UTG', 'MP')
    assert status == 'alias'
    assert source == '4B_UTG_vs_HJ'
    assert resolution.coverage_state == 'alias'
    assert resolution.alias_of == '4B_UTG_vs_HJ'
    assert probs is not None
    assert (probs == load_tables()[source]['probs']).all()


def test_pf_coverage_lookup_preserves_historical_fallback():
    probs, source, status, resolution = _pf_coverage_lookup(
        '4B', 'BTN', 'MP')
    assert status == 'fallback_other_vs'
    assert source == '4B_BTN_vs_BB'
    assert resolution.coverage_state == 'coverage_gap'
    assert resolution.source_key == '4B_BTN_vs_BB'
    assert resolution.fallback_used is True
    assert resolution.fallback_reason == 'fallback_to_other_vs'
    assert resolution.approximation_used is True
    assert probs is not None
    assert (probs == load_tables()[source]['probs']).all()


def test_pf_coverage_lookup_unknown_has_no_fallback_or_probs():
    probs, source, status, resolution = _pf_coverage_lookup(
        '4B', 'MP', 'UTG')
    assert probs is None
    assert source is None
    assert status == 'missing'
    assert resolution.coverage_state == 'unknown'
    assert resolution.source_key is None
    assert resolution.reason == 'unknown'
    assert resolution.fallback_used is False
    assert resolution.approximation_used is False


def test_key_mismatch_is_unknown_without_fallback():
    request = CoverageRequest(
        requested_key='NO_EXISTE',
        action='OR',
        pos='UTG',
        vs='',
    )
    resolution = resolve_coverage(request)
    assert resolution.coverage_state == 'unknown'
    assert resolution.reason == 'key_mismatch'
    assert resolution.source_key is None
    assert resolution.fallback_used is False


def test_impossible_absence_has_no_fallback_or_probs():
    for query in (('OR', 'BB', ''), ('ROL', 'UTG', '')):
        probs, source, status, resolution = _pf_coverage_lookup(*query)
        assert probs is None
        assert source is None
        assert status == 'missing'
        assert resolution.coverage_state == 'impossible'
        assert resolution.source_key is None
        assert resolution.fallback_used is False
        item = _pf_table_audit([query])[0]
        assert item['coverage_state'] == 'impossible'
        assert item['classification'] == resolution.reason
        assert item['structural_classification'] == \
            classify_missing_table(*query)


def test_pf_table_audit_keeps_full_metadata_for_fallback_and_unknown():
    audit = _pf_table_audit([
        ('4B', 'BTN', 'MP'),
        ('4B', 'MP', 'UTG'),
    ])
    fallback, unknown = audit

    assert fallback['coverage_state'] == 'coverage_gap'
    assert fallback['source_key'] == '4B_BTN_vs_BB'
    assert fallback['fallback_used'] is True
    assert fallback['fallback_reason'] == 'fallback_to_other_vs'
    assert fallback['approximation_used'] is True
    assert fallback['classification'] == 'coverage_gap'
    assert fallback['reason'] == 'fallback_to_other_vs'
    assert fallback['structural_classification'] == 'coverage_gap'

    assert unknown['coverage_state'] == 'unknown'
    assert unknown['source_key'] is None
    assert unknown['fallback_used'] is False
    assert unknown['fallback_reason'] is None
    assert unknown['approximation_used'] is False
    assert unknown['classification'] == 'unknown'
    assert unknown['reason'] == 'unknown'
    assert unknown['structural_classification'] == 'impossible_action_order'


def test_pf_coverage_lookup_loads_tables_once(monkeypatch):
    import motor.asistente_live as asistente

    calls = []
    original = asistente.load_tables

    def counted():
        calls.append(True)
        return original()

    monkeypatch.setattr(asistente, 'load_tables', counted)
    asistente._pf_coverage_lookup('OR', 'UTG', '')
    assert len(calls) == 1


def test_pf_table_audit_resolves_once_per_query(monkeypatch):
    import motor.asistente_live as asistente

    queries = [
        ('OR', 'UTG', ''),
        ('4B', 'BTN', 'MP'),
        ('4B', 'MP', 'UTG'),
    ]
    calls = []
    original = asistente.resolve_coverage

    def counted(request, *args, **kwargs):
        calls.append(request.requested_key)
        return original(request, *args, **kwargs)

    monkeypatch.setattr(asistente, 'resolve_coverage', counted)
    audit = asistente._pf_table_audit(queries)

    assert len(audit) == len(queries)
    assert calls == [table_key(*query) for query in queries]


def test_valid_queries_keep_probabilities_and_historical_status():
    checked = 0
    for query in _engine_queries():
        if classify_missing_table(*query) == 'impossible_action_order':
            continue
        old_probs, old_source, old_status = _historical_lookup(*query)
        new_probs, new_source, new_status = _pf_table_lookup(*query)
        assert new_status == old_status
        assert new_source == old_source
        if old_probs is None:
            assert new_probs is None
        else:
            assert new_probs is not None
            assert (new_probs == old_probs).all()
        checked += 1
    assert checked == 77


def test_reachable_coverage_keeps_frequencies_ev_and_recommendations():
    pair_spots = [
        (('3B', 'BB', 'SB'), ('Call_OR', 'BB', 'SB')),
        (('4B', 'BTN', 'MP'), ('Call_3B', 'BTN', 'MP')),
        (('5B', 'BB', 'SB'), ('Call_4B', 'BB', 'SB')),
    ]
    single_spots = [
        ('open', ('OR', 'UTG', '')),
        ('call', ('ROL', 'BTN', '')),
        ('call', ('Call_5B', 'BB', 'SB')),
    ]

    for hand_idx in range(0, 1326, 97):
        for raise_query, call_query in pair_spots:
            old_raise = _historical_frequency(raise_query, hand_idx)
            old_call = _historical_frequency(call_query, hand_idx)
            new_raise = _pf_freq(*raise_query, hand_idx)
            new_call = _pf_freq(*call_query, hand_idx)
            assert new_raise == old_raise
            assert new_call == old_call

            old_ev = _pf_evs(old_raise or 0.0, old_call or 0.0)
            new_ev = _pf_evs(new_raise or 0.0, new_call or 0.0)
            assert new_ev == old_ev

            seed = 123456789 + hand_idx
            old_action, old_meta = _sample_preflop_action(old_ev, seed=seed)
            new_action, new_meta = _sample_preflop_action(new_ev, seed=seed)
            assert new_action == old_action
            assert new_meta == old_meta

        for kind, query in single_spots:
            old_freq = _historical_frequency(query, hand_idx)
            new_freq = _pf_freq(*query, hand_idx)
            assert new_freq == old_freq

            if kind == 'open':
                old_ev = {'retirar': 1.0 - (old_freq or 0.0),
                          'subir': old_freq or 0.0}
                new_ev = {'retirar': 1.0 - (new_freq or 0.0),
                          'subir': new_freq or 0.0}
            else:
                old_ev = {'igualar': old_freq or 0.0,
                          'retirar': 1.0 - (old_freq or 0.0)}
                new_ev = {'igualar': new_freq or 0.0,
                          'retirar': 1.0 - (new_freq or 0.0)}
            assert new_ev == old_ev

            seed = 987654321 + hand_idx
            old_action, old_meta = _sample_preflop_action(old_ev, seed=seed)
            new_action, new_meta = _sample_preflop_action(new_ev, seed=seed)
            assert new_action == old_action
            assert new_meta == old_meta


def test_49_order_dependent_queries_are_unknown_without_coverage():
    """Las 49 consultas con fallback histórico eran imposibles no validadas.

    El cambio es una corrección semántica intencional: no son secuencias
    válidas verificadas, por lo que no deben declararse ``impossible`` ni
    recibir un vector de fallback. Se conserva la causa estructural en
    ``structural_classification`` sin confundirla con el estado resuelto.
    """
    affected = []
    for query in _engine_queries():
        if classify_missing_table(*query) != 'impossible_action_order':
            continue
        _probs, _source, status = _historical_lookup(*query)
        if status == 'fallback_other_vs':
            affected.append(query)

    assert len(affected) == 49

    for query in affected:
        probs, source, status, resolution = _pf_coverage_lookup(*query)
        assert probs is None
        assert source is None
        assert status == 'missing'
        assert resolution.coverage_state == 'unknown'
        assert resolution.reason == 'unknown'
        assert resolution.source_key is None
        assert resolution.fallback_used is False
        assert resolution.approximation_used is False

        item = _pf_table_audit([query])[0]
        assert item['coverage_state'] == 'unknown'
        assert item['classification'] == 'unknown'
        assert item['reason'] == 'unknown'
        assert item['fallback_used'] is False
        assert item['structural_classification'] == \
            'impossible_action_order'
