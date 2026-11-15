"""Tests de la vista canónica preflop HU-P1A (sombra, sin live)."""
import pytest

from motor.preflop import table_key
from motor.preflop_canonical import (
    CanonicalPreflopDecision, PlanCoverage, canonical_preflop,
)
from motor.preflop_contract import (
    PreflopContext, context_at, first_decision, plan_from_context,
    table_plan, walk_preflop,
)
from motor.preflop_coverage import (
    CoverageAggregate, CoverageRequest, aggregate_coverage, resolve_coverage,
)


def _src(actions):
    return list(actions)


def _open_then_call():
    return _src([
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
        {'pos': 'MP', 'action': 'c', 'amount': 2.5},
    ])


# ---------------------------------------------------------------------------
# Estado relativo al héroe, no última acción global
# ---------------------------------------------------------------------------

def test_table_plan_usa_el_prefijo_previo_a_la_decision_del_heroe():
    actions = _open_then_call() + [
        {'pos': 'CO', 'action': 'b', 'amount': 8.0},
    ]
    plan = table_plan(actions, 'CO')
    assert plan.raises_before == 1
    assert plan.callers_before == 1
    assert plan.table_raise == '3B'
    assert plan.table_call == 'Call_OR'

    # Si se usa el contexto final, el plan sería 4B/Call_3B.
    assert plan_from_context(context_at(actions)).table_raise == '4B'


def test_current_mode_reconstruye_el_nodo_sin_exigir_accion_del_heroe():
    d = canonical_preflop(_open_then_call(), 'CO', mode='current', at_index=4)
    assert d.status == 'resolved'
    assert d.classification is None
    assert d.decision_plan.raises_before == 1
    assert d.decision_plan.table_raise == '3B'
    assert d.decision_plan.table_call == 'Call_OR'
    assert d.range_query is None
    assert d.coverage.coverage_state == 'partial'
    assert d.action_ready is False


def test_context_at_no_mira_acciones_posteriores():
    actions = _src([
        {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
        {'pos': 'MP', 'action': 'r', 'amount': 8.0},
        {'pos': 'CO', 'action': 'b', 'amount': 20.0},
    ])
    ctx = context_at(actions, 2)
    assert ctx.raises_before == 2
    assert ctx.last_aggressor == 'MP'
    assert plan_from_context(ctx).table_raise == '4B'
    assert context_at(actions).raises_before == 3


# ---------------------------------------------------------------------------
# Estados que no pueden producir plan/consulta
# ---------------------------------------------------------------------------

def test_no_decision_historica_no_produce_plan_ni_rango():
    d = canonical_preflop(_open_then_call(), 'CO')
    assert d.status == 'no_decision'
    assert d.decision_plan is None
    assert d.range_query is None
    assert d.coverage is None
    assert d.plan_coverage == ()
    assert d.action_ready is False


def test_decision_unresolved_no_produce_plan_ni_rango():
    d = canonical_preflop(_src([
        {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
        {'pos': 'MP', 'action': 'r', 'amount': 2.5},
    ]), 'MP')
    assert d.status == 'unresolved'
    assert d.classification is None
    assert d.decision_plan is None
    assert d.range_query is None
    assert d.coverage is None
    assert 'subida_sin_incremento' in d.reasons


def test_decision_canonica_valida_combinaciones_invalidas():
    with pytest.raises(ValueError):
        CanonicalPreflopDecision(
            status='resolved', mode='historical', hero_position='UTG',
            context=PreflopContext.initial(), decision_plan=None,
            classification=None, range_query=None, plan_coverage=(),
            coverage=None, sequence_status='not_evaluated')
    with pytest.raises(ValueError):
        CanonicalPreflopDecision(
            status='unresolved', mode='historical', hero_position='UTG',
            context=PreflopContext.initial(), decision_plan=object(),
            classification=None, range_query=None, plan_coverage=(),
            coverage=None, sequence_status='not_evaluated')


# ---------------------------------------------------------------------------
# Coveraje estricto: huecos visibles, sin fallback
# ---------------------------------------------------------------------------

def test_cobertura_de_hueco_no_usa_fallback_ni_rellena_con_cero():
    d = canonical_preflop(_src([
        {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
        {'pos': 'MP', 'action': 'b', 'amount': 8.0},
    ]), 'CO', mode='current', at_index=2)
    assert d.decision_plan.table_raise == '4B'
    assert d.decision_plan.table_call == 'Call_3B'
    assert d.coverage.coverage_state == 'partial'
    assert d.coverage.counts == {'coverage_gap': 2}
    by_key = {q.requested_key: q for q in d.plan_coverage}
    raise_q = by_key[table_key('4B', 'CO', 'MP')]
    call_q = by_key[table_key('Call_3B', 'CO', 'MP')]
    assert raise_q.resolution.source_key is None
    assert raise_q.resolution.fallback_used is False
    assert call_q.resolution.source_key is None
    assert d.action_ready is False


def test_alias_autorizado_no_se_confunde_con_exactitud():
    alias = resolve_coverage(CoverageRequest(
        requested_key=table_key('4B', 'UTG', 'MP'),
        action='4B', pos='UTG', vs='MP'))
    assert alias.coverage_state == 'alias'
    assert alias.approximation_used is False
    assert alias.source_key == '4B_UTG_vs_HJ'


def test_agregado_preserva_estados_individuales():
    exact = resolve_coverage(CoverageRequest(
        requested_key=table_key('OR', 'UTG', ''), action='OR', pos='UTG'))
    gap = resolve_coverage(CoverageRequest(
        requested_key=table_key('Call_OR', 'MP', 'UTG'),
        action='Call_OR', pos='MP', vs='UTG'))
    alias = resolve_coverage(CoverageRequest(
        requested_key=table_key('4B', 'UTG', 'MP'),
        action='4B', pos='UTG', vs='MP'))
    impossible = resolve_coverage(CoverageRequest(
        requested_key=table_key('OR', 'BB', ''), action='OR', pos='BB'))

    agg = aggregate_coverage((exact, gap))
    assert agg.coverage_state == 'partial'
    assert agg.counts == {'exact': 1, 'coverage_gap': 1}
    assert agg.complete is False

    agg = aggregate_coverage((exact, impossible))
    assert agg.coverage_state == 'complete_exact'
    assert agg.complete is True

    agg = aggregate_coverage((alias, impossible))
    assert agg.coverage_state == 'complete_with_alias'
    assert agg.complete is True

    agg = aggregate_coverage((impossible,))
    assert agg.coverage_state == 'none_applicable'
    assert agg.complete is False

    agg = aggregate_coverage(())
    assert agg.coverage_state == 'unresolved'


def test_agregado_sigue_la_tabla_de_combinaciones_del_contrato():
    unknown = resolve_coverage(CoverageRequest(
        requested_key=table_key('3B', 'UTG', 'MP'),
        action='3B', pos='UTG', vs='MP',
        source_context={'sequence_status': 'not_evaluated'}))
    impossible = resolve_coverage(CoverageRequest(
        requested_key=table_key('OR', 'BB', ''), action='OR', pos='BB'))
    gap = resolve_coverage(CoverageRequest(
        requested_key=table_key('Call_OR', 'MP', 'UTG'),
        action='Call_OR', pos='MP', vs='UTG'))

    assert unknown.coverage_state == 'unknown'
    assert aggregate_coverage((impossible, unknown)).coverage_state == 'partial'
    assert aggregate_coverage((unknown, unknown)).coverage_state == 'unknown'
    assert aggregate_coverage((gap, unknown)).coverage_state == 'partial'
    assert aggregate_coverage((impossible, gap)).coverage_state == 'partial'


def test_agregado_rechaza_conteos_incoherentes():
    exact = resolve_coverage(CoverageRequest(
        requested_key=table_key('OR', 'UTG', ''), action='OR', pos='UTG'))
    with pytest.raises(ValueError):
        CoverageAggregate(coverage_state='complete_exact',
                          counts={'exact': 2}, resolutions=(exact,))


def test_plan_coverage_exige_clave_coherente():
    exact = resolve_coverage(CoverageRequest(
        requested_key=table_key('OR', 'UTG', ''), action='OR', pos='UTG'))
    with pytest.raises(ValueError):
        PlanCoverage(slot='raise', requested_key='OR_MP', resolution=exact)

# ---------------------------------------------------------------------------
# Calls: solo igualan nivel o son all-in declarado y coherente
# ---------------------------------------------------------------------------

def _call_sequence(amount, **extra):
    call = {'pos': 'MP', 'action': 'c', 'amount': amount}
    call.update(extra)
    return _src([
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
        call,
    ])


def test_call_completo_igual_al_nivel_y_cuenta_llamada():
    actions = _call_sequence(2.5)
    got = first_decision(actions, 'MP')
    assert got.status == 'resolved'
    assert got.category == 'call_open'
    assert got.reason is None
    assert walk_preflop(actions)[-1].after.callers_before == 1


def test_call_corto_all_in_declarado_y_coherente_es_valido():
    actions = _call_sequence(2.0, all_in=True, stack_before=2.0,
                             stack_after=0.0)
    got = first_decision(actions, 'MP')
    assert got.status == 'resolved'
    assert got.category == 'call_open'
    assert walk_preflop(actions)[-1].after.callers_before == 1


@pytest.mark.parametrize('extra', [
    {},
    {'all_in': True},
    {'all_in': True, 'stack_before': 1.0},
    {'all_in': True, 'stack_before': 2.0, 'stack_after': 0.5},
])
def test_call_corto_sin_evidencia_all_in_completa_no_cuenta(extra):
    actions = _call_sequence(2.0, **extra)
    got = first_decision(actions, 'MP')
    assert got.status == 'unresolved'
    assert got.reason == 'call_incompleto_sin_allin'
    assert walk_preflop(actions)[-1].after.callers_before == 0


@pytest.mark.parametrize('amount,reason', [
    (None, 'importe_ausente'),
    (0.0, 'importe_cero'),
    (3.0, 'call_excede_nivel'),
])
def test_call_ausente_cero_o_excedido_nunca_cuenta(amount, reason):
    actions = _call_sequence(amount)
    got = first_decision(actions, 'MP')
    assert got.status == 'unresolved'
    assert got.reason == reason
    assert walk_preflop(actions)[-1].after.callers_before == 0


# ---------------------------------------------------------------------------
# Ciegas: explicitas o estructurales, nunca una voluntaria reasignada
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('actions', [
    [
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
    ],
    [
        {'pos': 'SB', 'action': 'b', 'amount': 0.5},
        {'pos': 'BB', 'action': 'b', 'amount': 1.0},
    ],
])
def test_ciegas_estructurales_sb_y_bb_son_no_decision(actions):
    steps = walk_preflop(_src(actions))
    assert [s.classification.category for s in steps] == ['blind', 'blind']
    assert [s.classification.status for s in steps] == [
        'non_decision', 'non_decision']
    final = steps[-1].after
    assert final.voluntary_actions == 0
    assert final.bb_posted is True
    assert final.current_level == 1.0


def test_eventos_de_ciega_explicitos_mandan_aunque_cambie_el_orden():
    steps = walk_preflop(_src([
        {'pos': 'BB', 'action': 'b', 'amount': 1.0,
         'event_type': 'big_blind'},
        {'pos': 'SB', 'action': 'b', 'amount': 0.5,
         'event_type': 'small_blind'},
    ]))
    assert [s.classification.category for s in steps] == ['blind', 'blind']
    assert [s.classification.status for s in steps] == [
        'non_decision', 'non_decision']


def test_evento_voluntario_no_se_reclasifica_como_ciega():
    steps = walk_preflop(_src([
        {'pos': 'SB', 'action': 'b', 'amount': 2.5,
         'event_type': 'voluntary_action'},
    ]))
    assert len(steps) == 1
    assert steps[0].classification.category == 'open'
    assert steps[0].classification.status == 'resolved'


def test_ciega_estructural_y_luego_apertura_voluntaria():
    actions = _src([
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'f', 'amount': 0.0},
        {'pos': 'SB', 'action': 'r', 'amount': 3.0},
        {'pos': 'BB', 'action': 'c', 'amount': 3.0},
    ])
    steps = walk_preflop(actions)
    assert [s.classification.category for s in steps] == [
        'blind', 'blind', 'fold', 'open', 'call_open']
    assert steps[3].classification.category != 'blind'
    assert steps[-1].after.callers_before == 1


# ---------------------------------------------------------------------------
# Plan de tablas sin decision y serializacion de cobertura
# ---------------------------------------------------------------------------

def test_table_plan_sin_decision_no_inventa_tablas():
    plan = table_plan(_open_then_call(), 'CO')
    assert plan.status == 'unresolved'
    assert plan.reason == 'sin_decision'
    assert plan.table_raise is None
    assert plan.table_call is None


def test_resolucion_y_agregado_serializan_cada_consulta():
    exact = resolve_coverage(CoverageRequest(
        requested_key=table_key('OR', 'UTG', ''), action='OR', pos='UTG'))
    gap = resolve_coverage(CoverageRequest(
        requested_key=table_key('Call_OR', 'MP', 'UTG'),
        action='Call_OR', pos='MP', vs='UTG'))
    agg = aggregate_coverage((exact, gap))
    data = agg.as_dict()
    assert data['coverage_state'] == 'partial'
    assert len(data['queries']) == 2
    required = {
        'requested_key', 'coverage_state', 'source_key', 'reason', 'alias_of',
        'fallback_key', 'fallback_reason', 'action', 'pos', 'vs',
        'resolved_by', 'fallback_used', 'approximation_used',
    }
    for query in data['queries']:
        assert required <= set(query)
    assert data['queries'][0]['coverage_state'] == 'exact'
    assert data['queries'][1]['coverage_state'] == 'coverage_gap'
