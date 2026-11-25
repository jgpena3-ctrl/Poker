"""Regresiones de decisión preflop: secuencia estricta y abstención.

Cubre los defectos mecánicos del motor compartido:
- una cobertura ausente no se convierte en fold 0/100%;
- el nodo se reconstruye contando también las subidas del héroe;
- una secuencia no resoluble se abstiene en vez de inventar el nodo.
"""
from types import SimpleNamespace

import pytest

from motor.asistente_live import (Asistente, _pf_coverage_lookup, _pf_evs,
                                  _pf_freq)
from motor.preflop_contract import (context_at, final_context,
                                    plan_from_context)


class _NoModels:
    range_model = None


@pytest.fixture
def asis():
    a = Asistente.__new__(Asistente)
    a.models = _NoModels()
    a.live_stacks = {}
    a._last_seen_stake = {}
    a.rec = SimpleNamespace(hand=None)
    a.verbose = False
    return a


def _hand(actions):
    return {'streets': {'preflop': {'actions': actions}}}


def _pf_state(btn='p3'):
    return {
        'pot': 1.5, 'btn': btn,
        'hero_cards': [{'rank': '6', 'suit': 'c'},
                       {'rank': '4', 'suit': 's'}],
        'p1_state': 'activo', 'p1_stake': 109.5, 'p1_bet': 0.0,
        'p2_state': 'activo', 'p2_stake': 59.5, 'p2_bet': 0.0,
        'p3_state': 'activo', 'p3_stake': 101.5, 'p3_bet': 0.0,
        'p4_state': 'activo', 'p4_stake': 53.2, 'p4_bet': 0.5,
        'p5_state': 'activo', 'p5_stake': 59.0, 'p5_bet': 1.0,
    }


def _keys(evs):
    return {item['key'] for item in evs.preflop_table_audit}


def test_h1374_28_cuenta_la_subida_previa_del_heroe(asis):
    # BTN (hero) abre, SB 3-betea y BB se retira. El nodo del hero es
    # responder a un 3-bet: 4B/Call_3B, no 3B/Call_OR.
    asis.rec.hand = _hand([
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'CO', 'action': 'f', 'amount': 0.0},
        {'pos': 'BTN', 'action': 'r', 'amount': 2.5},
        {'pos': 'SB', 'action': 'r', 'amount': 10.5},
        {'pos': 'BB', 'action': 'f', 'amount': 0.0},
    ])
    evs = asis._recom_preflop(
        _pf_state(), ['As', 'Ks'], 'BTN', 2.5, 14.0, 8.0,
        'TIBURON', 'x', None, False)

    assert evs is not None
    assert _keys(evs) == {'4B_BTN_vs_SB', 'Call_3B_BTN_vs_SB'}
    assert all(item['coverage_state'] == 'exact'
               for item in evs.preflop_table_audit)
    assert abs(sum(evs.ev.values()) - 1.0) < 1e-9


def test_h1374_28_mantiene_75_25_y_repite_la_seleccion_con_semilla(asis):
    # Cartas y secuencia de la captura #28. La semilla registrada en el replay
    # se inyecta para verificar que el mismo sorteo vuelve a dar la misma
    # acción, sin cambiar el muestreo ponderado.
    asis.rec.hand = _hand([
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'BTN', 'action': 'r', 'amount': 2.5},
        {'pos': 'SB', 'action': 'r', 'amount': 10.5},
        {'pos': 'BB', 'action': 'f', 'amount': 0.0},
    ])
    seed = 6505878476735301527
    args = (_pf_state(), ['5s', 'As'], 'BTN', 2.5, 14.0, 8.0,
            'TIBURON', 'x', None, False)
    first = asis._recom_preflop(*args, seed=seed, effective_stack=92.0)
    second = asis._recom_preflop(*args, seed=seed, effective_stack=92.0)

    assert first.ev == {'retirar': 0.0, 'igualar': 0.75, 'subir': 0.25}
    assert first.chosen == second.chosen == 'subir'
    assert first.preflop_sampling['seed'] == seed
    assert first.preflop_sampling['mechanism'] == \
        'weighted_choice_with_replacement'


def test_h1365_54_limp_raise_no_se_convierte_en_fold(asis):
    # SB (hero) limpa y BB sube. El nodo es 3B/Call_OR vs BB, pero esas
    # tablas no modelan un limp-3bet: se abstiene, no se inventa fold.
    asis.rec.hand = _hand([
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'CO', 'action': 'f', 'amount': 0.0},
        {'pos': 'BTN', 'action': 'f', 'amount': 0.0},
        {'pos': 'SB', 'action': 'c', 'amount': 1.0},
        {'pos': 'BB', 'action': 'r', 'amount': 15.0},
    ])
    evs = asis._recom_preflop(
        _pf_state(), ['As', 'Ks'], 'SB', 1.0, 16.5, 14.0,
        'TIBURON', 'x', None, False)

    assert evs is None
    assert asis.last_reco_reason.startswith('preflop_coverage_unusable:')
    # 3B puede tener fallback autorizado, pero Call_OR no: la distribución
    # sigue incompleta y el motor se abstiene.
    assert 'Call_OR_SB_vs_BB' in asis.last_reco_reason
    coverage = {item['key']: item
                for item in asis.last_preflop_abstention['coverage']}
    assert coverage['3B_SB_vs_BB']['coverage_state'] == 'coverage_gap'
    assert coverage['Call_OR_SB_vs_BB']['usable'] is False
    plan = asis.last_preflop_abstention['plan']
    assert plan['raises_before'] == 1
    assert plan['limps_before'] == 1


def test_h1372_37_cobertura_exacta_conserva_nodo_y_distribucion(asis):
    # MP abre y SB se retira: BB (hero) decide con 3B/Call_OR exactas.
    asis.rec.hand = _hand([
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'MP', 'action': 'r', 'amount': 2.5},
        {'pos': 'CO', 'action': 'f', 'amount': 0.0},
        {'pos': 'BTN', 'action': 'f', 'amount': 0.0},
        {'pos': 'SB', 'action': 'f', 'amount': 0.0},
    ])
    evs = asis._recom_preflop(
        _pf_state(), ['Jc', '6c'], 'BB', 1.0, 4.0, 1.5,
        'TIBURON', 'x', None, False)

    assert evs is not None
    assert _keys(evs) == {'3B_BB_vs_MP', 'Call_OR_BB_vs_MP'}
    assert all(item['coverage_state'] == 'exact'
               for item in evs.preflop_table_audit)
    assert abs(sum(evs.ev.values()) - 1.0) < 1e-9
    # La tabla exacta da fold 100% para J6s; se conserva, no se "mejora"
    # para coincidir con ninguna acción histórica.
    assert evs.ev['retirar'] == pytest.approx(1.0)
    assert evs.chosen == 'retirar'


def test_secuencia_no_resoluble_se_abstiene(asis):
    # SB iguala por debajo del nivel vigente y no consta all-in: el estado
    # no es resoluble; no se inventa el nodo.
    asis.rec.hand = _hand([
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        {'pos': 'SB', 'action': 'c', 'amount': 1.0},
    ])
    evs = asis._recom_preflop(
        _pf_state(), ['As', 'Ks'], 'BB', 1.0, 4.0, 1.5,
        'TIBURON', 'x', None, False)

    assert evs is None
    assert asis.last_reco_reason.startswith('preflop_sequence_unresolved:')
    assert asis.last_preflop_abstention is not None


def test_squeeze_con_caller_previo_no_usa_tablas_de_3bet_heads_up(asis):
    # UTG abre, MP paga y CO debe decidir. Es squeeze/over-call, no el nodo
    # heads-up 3B/Call_OR; las tablas disponibles no dan una distribución
    # completa para este contexto.
    asis.rec.hand = _hand([
        {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        {'pos': 'MP', 'action': 'c', 'amount': 2.5},
    ])
    evs = asis._recom_preflop(
        _pf_state(), ['As', 'Ks'], 'CO', 0.0, 6.5, 2.5,
        'TIBURON', 'x', None, False)

    assert evs is None
    assert asis.last_reco_reason == (
        'preflop_distribution_unavailable:squeeze_or_overcall_node')
    plan = asis.last_preflop_abstention['plan']
    assert plan['raises_before'] == 1
    assert plan['callers_before'] == 1


def test_respuesta_a_squeeze_no_usa_tablas_de_4bet_heads_up(asis):
    # UTG abre, MP paga, CO squeezea y BTN debe decidir. La subida previa
    # está clasificada como squeeze por el contrato; no es una 3B ordinaria.
    asis.rec.hand = _hand([
        {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        {'pos': 'MP', 'action': 'c', 'amount': 2.5},
        {'pos': 'CO', 'action': 'r', 'amount': 10.0},
    ])
    evs = asis._recom_preflop(
        _pf_state(), ['As', 'Ks'], 'BTN', 0.0, 15.0, 10.0,
        'TIBURON', 'x', None, False)

    assert evs is None
    assert asis.last_reco_reason == (
        'preflop_distribution_unavailable:response_after_squeeze')
    assert asis.last_preflop_abstention['plan']['raises_before'] == 2


def test_bb_sin_apuesta_usa_la_opcion_estructural_de_pasar(asis):
    # Sin raise ni limp, OR_BB no existe por contrato; la única acción
    # modelada es pasar. No es una abstención ni un fold inventado.
    asis.rec.hand = _hand([
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
    ])
    evs = asis._recom_preflop(
        _pf_state(), ['6c', '4s'], 'BB', 1.0, 1.5, 0.0,
        'PEZ', 'x', None, False)

    assert evs is not None
    assert evs.best()[0] == 'pasar'
    audit = {item['key']: item for item in evs.preflop_table_audit}
    assert audit['OR_BB']['coverage_state'] == 'impossible'
    assert audit['OR_BB']['classification'] == 'intentional_check_option'


def test_alias_aprobado_es_usable(asis):
    # UTG (hero) abre y MP 3-betea. 4B_UTG_vs_MP tiene alias aprobado
    # 4B_UTG_vs_HJ; Call_3B_UTG_vs_MP es exacta.
    asis.rec.hand = _hand([
        {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        {'pos': 'MP', 'action': 'r', 'amount': 8.0},
    ])
    evs = asis._recom_preflop(
        _pf_state(), ['As', 'Ks'], 'UTG', 2.5, 10.5, 5.5,
        'TIBURON', 'x', None, False)

    assert evs is not None
    audit = {item['key']: item for item in evs.preflop_table_audit}
    assert audit['4B_UTG_vs_MP']['coverage_state'] == 'alias'
    assert audit['4B_UTG_vs_MP']['source_key'] == '4B_UTG_vs_HJ'
    assert audit['Call_3B_UTG_vs_MP']['coverage_state'] == 'exact'


def test_fallback_autorizado_se_usa_y_se_audita(asis):
    # UTG abre, MP 3-betea y CO (hero) decide. 4B/Call_3B CO vs MP son
    # coverage_gap con fallback autorizado a otra posición rival.
    asis.rec.hand = _hand([
        {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        {'pos': 'MP', 'action': 'r', 'amount': 8.0},
    ])
    evs = asis._recom_preflop(
        _pf_state(), ['As', 'Ks'], 'CO', 0.0, 10.5, 8.0,
        'TIBURON', 'x', None, False)

    assert evs is not None
    for item in evs.preflop_table_audit:
        assert item['coverage_state'] == 'coverage_gap'
        assert item['fallback_used'] is True
        assert item['approximation_used'] is True


@pytest.mark.parametrize(
    'actions,index,raises,limps,callers,vs_pos,table_raise,table_call', [
        # Apertura del rival.
        ([{'pos': 'SB', 'action': 'p', 'amount': 0.5},
          {'pos': 'BB', 'action': 'p', 'amount': 1.0},
          {'pos': 'UTG', 'action': 'r', 'amount': 2.5}],
         None, 1, 0, 0, 'UTG', '3B', 'Call_OR'),
        # Apertura del héroe: antes de su acción no hay raises.
        ([{'pos': 'UTG', 'action': 'r', 'amount': 2.5}],
         0, 0, 0, 0, '', 'OR', None),
        # Héroe frente a una apertura.
        ([{'pos': 'BB', 'action': 'p', 'amount': 1.0},
          {'pos': 'UTG', 'action': 'r', 'amount': 2.5}],
         None, 1, 0, 0, 'UTG', '3B', 'Call_OR'),
        # Héroe frente a un 3-bet tras su propia apertura.
        ([{'pos': 'BTN', 'action': 'r', 'amount': 2.5},
          {'pos': 'SB', 'action': 'r', 'amount': 10.5}],
         None, 2, 0, 0, 'SB', '4B', 'Call_3B'),
        # Héroe frente a un 4-bet (3 raises previos).
        ([{'pos': 'UTG', 'action': 'r', 'amount': 2.5},
          {'pos': 'MP', 'action': 'r', 'amount': 8.0},
          {'pos': 'CO', 'action': 'r', 'amount': 20.0}],
         None, 3, 0, 0, 'CO', '5B', 'Call_4B'),
        # Limp.
        ([{'pos': 'SB', 'action': 'p', 'amount': 0.5},
          {'pos': 'BB', 'action': 'p', 'amount': 1.0},
          {'pos': 'UTG', 'action': 'c', 'amount': 1.0}],
         None, 0, 1, 0, '', 'ROL', None),
        # Limp y raise posterior.
        ([{'pos': 'SB', 'action': 'p', 'amount': 0.5},
          {'pos': 'BB', 'action': 'p', 'amount': 1.0},
          {'pos': 'UTG', 'action': 'c', 'amount': 1.0},
          {'pos': 'MP', 'action': 'r', 'amount': 4.0}],
         None, 1, 1, 0, 'MP', '3B', 'Call_OR'),
        # Varios jugadores: dos callers tras la apertura.
        ([{'pos': 'UTG', 'action': 'r', 'amount': 2.5},
          {'pos': 'MP', 'action': 'c', 'amount': 2.5},
          {'pos': 'CO', 'action': 'c', 'amount': 2.5}],
         None, 1, 0, 2, 'UTG', '3B', 'Call_OR'),
        # Ciegas estructurales: no son raises ni limps.
        ([{'pos': 'SB', 'action': 'p', 'amount': 0.5},
          {'pos': 'BB', 'action': 'p', 'amount': 1.0}],
         None, 0, 0, 0, '', 'OR', None),
    ])
def test_plan_reconstruye_el_nodo(actions, index, raises, limps, callers,
                                  vs_pos, table_raise, table_call):
    context = (final_context(actions) if index is None
               else context_at(actions, index))
    plan = plan_from_context(context)
    assert plan.status == 'resolved'
    assert plan.raises_before == raises
    assert plan.limps_before == limps
    assert plan.callers_before == callers
    assert plan.vs_pos == vs_pos
    assert plan.table_raise == table_raise
    assert plan.table_call == table_call


def test_plan_secuencia_con_call_incompleto_no_es_resoluble():
    actions = [
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        {'pos': 'SB', 'action': 'c', 'amount': 1.0},
    ]
    plan = plan_from_context(final_context(actions))
    assert plan.status == 'unresolved'
    assert plan.reason == 'call_incompleto_sin_allin'


def test_pf_freq_no_convierte_unknown_en_cero():
    probs, source, status, resolution = _pf_coverage_lookup(
        '3B', 'UTG', 'MP',
        source_context={'sequence_status': 'not_evaluated'})
    assert probs is None
    assert source is None
    assert status == 'missing'
    assert resolution.coverage_state == 'unknown'
    assert _pf_freq('3B', 'UTG', 'MP', 0) is None


def test_pf_evs_rechaza_frecuencia_ausente():
    with pytest.raises(ValueError, match='frecuencia preflop ausente'):
        _pf_evs(None, 0.25)
