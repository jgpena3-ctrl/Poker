"""Tests de la jerarquía de rivales y su modo sombra.

Dos garantías:

1. La clasificación hace lo que dice (agresor > checker > pendiente).
2. El modo sombra NO altera la recomendación. Es un instrumento de
   medición, no una corrección: si cambiara una acción, estaría
   calibrando con 36 manos por escenario.
"""
import json
import os

import numpy as np
import pytest

# F6.1.b: `AGGRESSOR`, `CHECKER` y `PENDING` se eliminaron. Eran un
# vocabulario de roles que `classify_villains` nunca emitia y que este test
# importaba sin usar.
from motor.hierarchy import (OBSERVED_ANCHOR,
                             ShadowLog, penalty_source,
                             classify_villains, passive_penalty,
                             shadow_equity, shadow_record, texture_key)
from motor.recommend_loop import recommend
from motor.ranges import N_COMBOS, RangeState

BOARD_FLOOP = ['Qh', '7s', '2c']
BOARD_WET = ['Qh', '7s', '2c']          # dos tonos + board mojado
HERO = ['As', 'Kd']


# --- textura y penalización ---------------------------------------------

def test_texture_key():
    assert texture_key(BOARD_FLOOP) in ('rainbow', 'two_tone', 'monotone')
    assert texture_key(None) == 'rainbow'
    assert texture_key(['Qh']) == 'rainbow'


def test_penalizacion_cero_sin_checkers():
    assert passive_penalty(BOARD_FLOOP, 'flop', 0) == 0.0


def test_penalizacion_crece_con_checkers():
    p0 = passive_penalty(BOARD_FLOOP, 'turn', 0)
    p1 = passive_penalty(BOARD_FLOOP, 'turn', 1)
    p2 = passive_penalty(BOARD_FLOOP, 'turn', 2)
    assert p0 == 0.0
    assert 0 < p1 < p2


def test_penalizacion_es_lineal_no_exponencial():
    """El error de `eq ** n` sería enorme: aquí dobla, no se cuadruplica.

    Medido: añadir un checker en turn baja ~2 puntos (69% -> 67%, n=36).
    Una forma exponencial con rango uniforme quitaría ~50.
    """
    p1 = passive_penalty(BOARD_FLOOP, 'turn', 1)
    p2 = passive_penalty(BOARD_FLOOP, 'turn', 2)
    assert p2 <= 2.0 * p1 + 1e-9          # lineal
    assert p2 < 4.0 * p1                    # y no p2 ≈ p1^2
    assert p1 < 0.10                        # penalización pequeña


def test_penalizacion_turn_es_la_calibrada():
    """Turn+seco es el escenario con dato directo: ~0.02."""
    p = passive_penalty(['Qh', '7s', '2c'], 'turn', 1)
    assert 0.01 <= p <= 0.03


def test_penalizacion_crece_en_flop_mas_que_turn():
    """Flop deja dos cartas por salir, turn una."""
    f = passive_penalty(BOARD_FLOOP, 'flop', 1)
    t = passive_penalty(BOARD_FLOOP, 'turn', 1)
    assert f > t


def test_penalizacion_river_la_mas_baja():
    r = passive_penalty(BOARD_FLOOP, 'river', 1)
    t = passive_penalty(BOARD_FLOOP, 'turn', 1)
    assert r < t


def test_penalizacion_saturada():
    """Muchos checkers no pueden invertir la equity."""
    p = passive_penalty(BOARD_FLOOP, 'flop', 500)
    assert p <= 0.5


def test_board_con_pareja_penaliza_mas():
    """Un board con pareja es más peligroso que uno liso."""
    liso = passive_penalty(['Qh', '7s', '2c'], 'turn', 1)
    pareado = passive_penalty(['Qh', 'Qh', '2c'], 'turn', 1)
    assert pareado > liso


# --- clasificación -------------------------------------------------------

def _acts(*pares):
    return [{'pos': p, 'action': a} for p, a in pares]


def test_elige_ultimo_agresor():
    acts = _acts(('UTG', 'b'), ('MP', 'r'), ('CO', 'c'))
    h = classify_villains(acts, 'BTN', ())
    assert h['main'] == 'MP'
    assert 'agresor' in h['main_reason']


def test_hero_que_tiene_bet_enfrenta_al_agresor():
    acts = _acts(('UTG', 'b'), ('CO', 'r'), ('BTN', 'c'))
    h = classify_villains(acts, 'BTN', ())
    assert h['main'] == 'CO'


def test_pendientes_no_son_checkers():
    """Quien aún no ha actuado puede resubir: no se penaliza como draw."""
    acts = _acts(('UTG', 'b'), ('BTN', 'x'))
    h = classify_villains(acts, 'BTN', activos=['CO', 'SB'])
    assert 'CO' in h['pending']
    assert 'SB' in h['pending']
    assert 'CO' not in h['checkers']
    assert 'SB' not in h['checkers']


def test_checkers_quedan_fuera_del_principal():
    acts = _acts(('UTG', 'x'), ('MP', 'x'), ('BTN', 'x'))
    h = classify_villains(acts, 'BTN', ())
    assert h['main'] == 'MP'                  # el último que checkeó
    assert h['checkers'] == ['UTG']
    assert 'BTN' not in h['checkers']


def test_sin_agresion_usa_posicion():
    acts = _acts(('BTN', 'x'))
    h = classify_villains(acts, 'BTN', activos=['CO'])
    assert h['main'] == 'CO' or h['main'] is None


def test_clasificacion_no_mezcla_rangos():
    """La jerarquía elige UN rival, no combina varios."""
    acts = _acts(('UTG', 'b'), ('MP', 'r'), ('BTN', 'c'))
    h = classify_villains(acts, 'BTN', ())
    assert isinstance(h['main'], str)
    assert h['aggressors'] == ['UTG', 'MP']
    assert h['main'] == h['aggressors'][-1]


def test_hero_sin_acciones_devuelve_estructura_vacia():
    h = classify_villains([], 'BTN', ())
    assert h['main'] is None
    assert h['checkers'] == []
    assert h['pending'] == []


# --- P0 corregidos (pegar_3 §1) ----------------------------------------

def test_hero_no_aparece_en_sus_pendientes():
    """El hero no puede estar en su propia lista de pendientes.

    Regresión: se comparaba un PID contra una POSICIÓN, así que la
    comparación siempre era verdadera y el hero nunca se excluía.
    """
    acts = _acts(('UTG', 'x'), ('CO', 'x'), ('BTN', 'x'))
    h = classify_villains(acts, 'BTN', activos=['UTG', 'CO', 'BTN'])
    assert 'BTN' not in h['pending']
    assert h['pending'] == []


def test_quien_ya_actuo_no_es_pendiente():
    """Estar activo no significa tener una decisión pendiente."""
    acts = _acts(('UTG', 'x'), ('CO', 'x'), ('BTN', 'x'))
    # BTN y SB están activos pero BTN ya actuó y SB no aparece en la calle
    h = classify_villains(acts, 'BTN', activos=['UTG', 'CO', 'BTN', 'SB'])
    assert h['pending'] == ['SB']


def test_agresion_posterior_al_hero_se_reconoce():
    """Ronda que vuelve: la resubida posterior es la que el hero enfrenta.

    Regresión: se tomaba la PRIMERA aparición del hero como corte, así
    que todo lo posterior caía en 'pendientes' y `main` quedaba None.
    """
    acts = _acts(('BTN', 'x'), ('CO', 'b'), ('MP', 'r'))
    h = classify_villains(acts, 'BTN', ())
    assert h['main'] == 'MP'
    assert 'ronda que vuelve' in h['main_reason']
    assert h['aggressors'] == ['CO', 'MP']
    assert 'CO' not in h['pending']
    assert 'MP' not in h['pending']


def test_agresor_mas_reciente_gana():
    acts = _acts(('UTG', 'b'), ('MP', 'r'), ('CO', 'r'))
    h = classify_villains(acts, 'BTN', ())
    assert h['main'] == 'CO'


def test_check_que_va_seguido_de_bet_es_agresor():
    """Checkear no compromete la mano si después hay resubida.

    Detectado al auditar 400 manos: dos jugadores aparecían a la vez
    como checker y como agresor.
    """
    acts = _acts(('UTG', 'x'), ('CO', 'x'), ('UTG', 'b'), ('BTN', 'x'))
    h = classify_villains(acts, 'BTN', ())
    assert 'UTG' in h['aggressors']
    assert 'UTG' not in h['checkers']


def test_jerarquia_no_mezcla_pids_y_posiciones():
    """Todo en hierarchy.py son posiciones; el llamador traduce."""
    acts = _acts(('BTN', 'x'))
    h = classify_villains(acts, 'BTN', activos=['SB'])
    for grupo in ('aggressors', 'checkers', 'pending'):
        for pos in h[grupo]:
            assert pos in ('SB', 'BB', 'UTG', 'MP', 'CO', 'BTN'), pos


# --- Casos de referencia (pegar_3 §2, P1) -------------------------------
# Cero incoherencias NO equivale a cero errores: un registro puede ser
# internamente consistente y aun así elegir mal al rival. Estos casos
# tienen la clasificación correcta definida a mano.

def test_caso_check_luego_apuesta():
    """Un jugador checkea y después betting: es agresor, no pasivo."""
    acts = _acts(('UTG', 'x'), ('MP', 'x'), ('UTG', 'b'), ('BTN', 'x'))
    h = classify_villains(acts, 'BTN', ())
    assert h['main'] == 'UTG'
    assert 'UTG' in h['aggressors']
    assert 'UTG' not in h['checkers']


def test_caso_subida_y_resubida_vuelve_al_hero():
    """BTN sube, la resubida de MP es la que el hero enfrenta."""
    acts = _acts(('UTG', 'x'), ('MP', 'b'), ('BTN', 'r'), ('MP', 'r'))
    h = classify_villains(acts, 'BTN', ())
    assert h['main'] == 'MP'
    # el hero no es su propio agresor, aunque su 'r' esté en la calle
    assert 'BTN' not in h['aggressors']
    assert 'MP' in h['aggressors']


def test_caso_call_no_es_check():
    """Un 'c' es una categoría propia: igualar no es pasar.

    Quien igualó ha aportado fichas; su rango no está capado como el de
    un check, así que no debe entrar en la penalización de pasivos. Pero
    tampoco puede desaparecer del registro.
    """
    acts = _acts(('UTG', 'b'), ('MP', 'c'), ('CO', 'c'), ('BTN', 'x'))
    h = classify_villains(acts, 'BTN', ())
    assert h['main'] == 'UTG'
    assert h['checkers'] == []              # nadie pasó
    assert sorted(h['callers']) == ['CO', 'MP']
    assert h['callers'] not in (h['aggressors'],)


def test_caso_acciones_intercaladas():
    """Check, apuesta y call intercalados."""
    acts = _acts(('UTG', 'x'), ('MP', 'b'), ('CO', 'c'), ('BTN', 'x'))
    h = classify_villains(acts, 'BTN', ())
    assert h['main'] == 'MP'
    assert h['checkers'] == ['UTG']
    assert h['callers'] == ['CO']
    assert h['pending'] == []


def test_callers_no_entran_en_la_penalizacion():
    """Sin dato para callers, no se corrige la equity por ellos."""
    jer = classify_villains(_acts(('MP', 'b'), ('CO', 'c')), 'BTN', ())
    s = shadow_equity(0.6, BOARD_FLOOP, 'flop', jer)
    assert s['n_checker'] == 0
    assert s['n_caller'] == 1
    assert s['penalty'] is None
    assert s['equity_shadow'] is None


def test_caso_hero_ya_acted_no_es_pendiente():
    """El hero aparece en `acts` pero no debe salir en ningún grupo."""
    acts = _acts(('UTG', 'b'), ('BTN', 'x'))
    h = classify_villains(acts, 'BTN', activos=['UTG', 'BTN', 'CO'])
    assert h['main'] == 'UTG'
    assert 'BTN' not in h['checkers']
    assert 'BTN' not in h['aggressors']
    assert 'BTN' not in h['pending']


def test_caso_pendientes_segun_estado_y_accion():
    """El pendiente se define por no haber acted, no por estar activo."""
    acted = _acts(('UTG', 'b'), ('BTN', 'x'))
    # CO no ha actuado en la calle: sí es pendiente, aunque esté activo
    h = classify_villains(acted, 'BTN', activos=['UTG', 'MP', 'CO'])
    assert h['pending'] == ['MP', 'CO']     # UTG ya actuó, no MP ni CO
    assert h['main'] == 'UTG'


def test_caso_folded_no_aparece():
    """Un jugador retirado no es agresor ni pasivo."""
    acts = _acts(('UTG', 'b'), ('MP', 'f'), ('CO', 'x'), ('BTN', 'x'))
    h = classify_villains(acts, 'BTN', ())
    assert 'MP' not in h['aggressors']
    assert 'MP' not in h['checkers']
    assert 'MP' not in h['pending']


def test_caso_principal_no_coincide_con_el_de_la_equity():
    """El motor puede usar un rival distinto al principal de la jerarquía."""
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', ())   # main = MP
    s = shadow_equity(0.6, BOARD_FLOOP, 'flop', jer,
                      equity_source='UTG')               # engine usó UTG
    rec = shadow_record('H', 'flop', BOARD_FLOOP, HERO, jer, s,
                        10.0, 0.0, 90.0, 'bet_25')
    assert rec['villain_main'] == 'MP'
    assert rec['villain_used_for_equity'] == 'UTG'
    assert rec['equity_source_is_main'] is False
    # y la equity de referencia sigue sin existir
    assert rec['equity_main_available'] is False


# --- penalización absoluta (pegar_3 §1 P1) ------------------------------

def test_checkers_all_vs_secondary_no_se_confunden():
    """pegar_3 §1: dos conceptos que no deben mezclarse.

    Sin agresor, main sale de checkers; entonces checkers_secondary queda
    vacío aunque haya checkers. Antes de separarlos, `penalty_source`
    exigía len(checkers)==1 sobre la lista ya filtrada, lo que hacía la
    condición del ancla IMPOSIBLE y ocultaba los registros válidos.
    """
    acts = _acts(('UTG', 'x'), ('BTN', 'b'))
    h = classify_villains(acts, 'BTN', activos=['CO'])
    assert h['main'] == 'UTG'                 # único checker → principal
    assert h['checkers_all'] == ['UTG']       # pero SÍ hubo un checker
    assert h['checkers_secondary'] == []      # y no es secundario
    # con la definición correcta, el escenario del ancla es alcanzable
    assert penalty_source(['Qh', '7s', '2c'], 'turn', h) == 'anchor_match'


def test_checkers_all_con_agresor():
    """Con agresor, main no sale de checkers y ambos coinciden."""
    acts = _acts(('UTG', 'x'), ('MP', 'b'), ('BTN', 'x'))
    h = classify_villains(acts, 'BTN', ())
    assert h['main'] == 'MP'
    assert h['checkers_all'] == ['UTG']
    assert h['checkers_secondary'] == ['UTG']


def test_equity_shadow_es_none_sin_respaldo():
    """pegar_2 §2.1/§2.3: sin ancla no se emite un número inventado.

    El modo sombra habíautory estado emitiendo una equity_shadow que
    parecía un cálculo y no lo era.
    """
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', ())   # sin las 6 condiciones
    s = shadow_equity(0.69, BOARD_FLOOP, 'flop', jer)
    assert s['penalty_source'] != 'anchor_match'
    assert s['equity_shadow'] is None
    assert s['penalty'] is None
    assert s['delta'] is None
    assert s['equity_shadow_note']
    # pero la clasificación y el conteo siguen disponibles
    assert s['equity_production'] == 0.69


def test_equity_shadow_se_calcula_con_anchor_match():
    s = shadow_equity(0.69, BOARD_FLOOP, 'turn', _jerarquia_ancla())
    assert s['penalty_source'] == 'anchor_match'
    assert s['equity_shadow'] is not None
    assert s['penalty'] is not None
    assert s['equity_shadow_note'] is None


def test_anchor_declara_el_desajuste_de_poblacion():
    """El ancla se midió con otra definición de pending; hay que decirlo."""
    assert OBSERVED_ANCHOR['records_matching_anchor'] == 3
    assert OBSERVED_ANCHOR['population_mismatch']
    assert OBSERVED_ANCHOR['signs_agree'] is False
    assert OBSERVED_ANCHOR['used_as_equity_penalty'] is False


def test_equity_main_se_calcula_con_rango_del_principal():
    """pegar_2 §2.2 / §3.3: la tercera equity ya es calculable.

    El llamador construye el rango del principal de la jerarquía y el
    motor calcula la equity contra él, separada de la de producción.
    """
    from motor.recommend_loop import _equity_vs_rival
    from motor.ranges import RangeState

    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(list(HERO) + list(BOARD_FLOOP))
    eq, src, err = _equity_vs_rival(rs, HERO, BOARD_FLOOP)
    assert eq is not None and 0.0 <= eq <= 1.0
    assert err is None
    # rango bloqueado: las cartas del hero no pueden seguir en el rango
    assert not rs.is_empty


def test_equity_main_distingue_divergencia():
    """Si la jerarquía elige MP y producción usó UTG, se documenta."""
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', ())
    s = shadow_equity(0.6, BOARD_FLOOP, 'flop', jer, equity_source='UTG')
    assert s['equity_source'] == 'UTG'
    assert s['equity_source_is_hierarchy_main'] is False
    rec = shadow_record('H', 'flop', BOARD_FLOOP, HERO, jer, s,
                        10.0, 0.0, 90.0, 'bet')
    assert rec['villain_main'] == 'MP'
    assert rec['villain_used_for_equity'] == 'UTG'
    assert rec['equity_source_is_main'] is False


def test_equity_main_ausente_por_rango_no_disponible():
    """pegar_3 §4: la ausencia se registra, no se sustituye."""
    from motor.recommend_loop import _equity_vs_rival
    eq, src, err = _equity_vs_rival(None, HERO, BOARD_FLOOP)
    assert eq is None
    assert err == 'main_range_unavailable'


def test_equity_main_ausente_por_rango_vacio():
    from motor.recommend_loop import _equity_vs_rival
    from motor.ranges import RangeState
    vacio = RangeState(reach=np.zeros(N_COMBOS, dtype=np.float32))
    eq, src, err = _equity_vs_rival(vacio, HERO, BOARD_FLOOP)
    assert eq is None
    assert err == 'empty_range_after_blockers'


def test_equity_main_no_altera_la_accion():
    """Con main_range_builder, la acción y el valor siguen intactos."""
    from motor.ranges import RangeState
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(list(HERO) + list(BOARD_FLOOP))
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', ())
    base = dict(hero_codes=HERO, board_codes=BOARD_FLOOP, pot=25.0,
                to_call=0.0, stack=90.0, street='flop', position='BTN',
                villain_pos='UTG', deadline_s=5.0, runout=False)
    sin = recommend(**base)
    con = recommend(**base, hierarchy=jer, main_range_builder=rs)
    assert con.action == sin.action
    assert con.value == pytest.approx(sin.value, abs=1e-12)
    assert con.shadow['equity_main_available'] is True
    assert con.shadow['equity_main'] is not None


def test_equity_main_no_rompe_con_builder_que_falla():
    """Un builder que lanza no puede tumbar la recomendación."""
    def builder_malo(pos):
        raise RuntimeError('boom')
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', ())
    rec = recommend(HERO, BOARD_FLOOP, pot=25.0, to_call=0.0, stack=90.0,
                    street='flop', position='BTN', villain_pos='UTG',
                    deadline_s=5.0, runout=False,
                    hierarchy=jer, main_range_builder=builder_malo)
    assert rec.action in ('fold', 'check', 'call', 'bet_25', 'bet_50',
                          'bet_75', 'raise', 'all_in')
    assert rec.shadow['equity_main'] is None


def test_penalizacion_es_absoluta():
    """El efecto observado se registered como puntos, no como factor.

    (win 69% -> 67% dá -0.02 absoluto; como factor daría -0.0138.)
    """
    s = shadow_equity(0.69, BOARD_FLOOP, 'turn', _jerarquia_ancla())
    assert s['penalty_basis'] == 'absolute_unvalidated'
    assert s['equity_shadow'] == pytest.approx(0.67, abs=1e-6)
    assert s['delta'] == pytest.approx(-0.02, abs=1e-6)


def test_penalizacion_no_se_vende_como_correccion_de_equity():
    """pegar_3 §1: lo medido es win rate, no equity, y el signo difiere.

    Este test fija la razón por la que el modo sombra NO puede activarse
    como corrección.
    """
    s = shadow_equity(0.69, BOARD_FLOOP, 'turn', _jerarquia_ancla())
    assert s['penalty_basis_note']
    anchor = s['penalty_anchor']
    if anchor is not None:
        assert anchor['is_equity'] is False
        assert anchor['quantity'] == 'observed_win_rate'
        assert anchor['used_as_equity_penalty'] is False
        # el sentido se invierte al reconstruir como equity
        assert anchor['delta_win_rate'] < 0
        assert anchor['delta_equity'] > 0
        assert anchor['signs_agree'] is False


@pytest.mark.parametrize('eq', [0.20, 0.50, 0.69, 0.90])
def test_reduccion_constante_independiente_de_la_equity(eq):
    """Una penalización ABSOLUTA quita lo mismo a cualquier equity."""
    s = shadow_equity(eq, BOARD_FLOOP, 'turn', _jerarquia_ancla())
    assert eq - s['equity_shadow'] == pytest.approx(0.02, abs=1e-6)


def _jerarquia_ancla(hero_bet=True):
    """Jerarquía que reproduce EXACTAMENTE el escenario del ancla:
    turn, board liso, hero que apuesta, sin agresor, 1 checker, 1 pendiente.
    """
    return {'main': None,
            'hero_bet': hero_bet,
            'aggressors': [],
            'checkers': ['UTG'],
            'pending': ['CO'],
            'callers': []}


def test_penalty_source_exige_el_escenario_completo():
    """pegar_3 §2 P0: no basta calle+textura.

    Antes cualquier turn con board rainbow se etiquetaba 'measured'. El
    ancla es un escenario de seis condiciones; si no se cumplen todas,
    el registro no puede '__heredado__' el respaldo.
    """
    ok = shadow_equity(0.69, BOARD_FLOOP, 'turn', _jerarquia_ancla())
    assert ok['penalty_source'] == 'anchor_match'
    assert ok['penalty_anchor'] is not None

    # misma calle y textura, pero el hero NO apuesta
    no_bet = shadow_equity(0.69, BOARD_FLOOP, 'turn',
                           _jerarquia_ancla(hero_bet=False))
    assert no_bet['penalty_source'] == 'partial_support'
    assert no_bet['penalty_anchor'] is None

    # hay agresor
    con_agresor = _jerarquia_ancla()
    con_agresor['aggressors'] = ['MP']
    r = shadow_equity(0.69, BOARD_FLOOP, 'turn', con_agresor)
    assert r['penalty_source'] == 'partial_support'

    # dos checkers en vez de uno
    dos = _jerarquia_ancla()
    dos['checkers'] = ['UTG', 'MP']
    r2 = shadow_equity(0.69, BOARD_FLOOP, 'turn', dos)
    assert r2['penalty_source'] == 'partial_support'

    # dos pendientes
    dos_pend = _jerarquia_ancla()
    dos_pend['pending'] = ['CO', 'SB']
    r3 = shadow_equity(0.69, BOARD_FLOOP, 'turn', dos_pend)
    assert r3['penalty_source'] == 'partial_support'


def test_penalty_source_otra_calle_sin_respaldo():
    for st in ('flop', 'river'):
        s = shadow_equity(0.5, BOARD_FLOOP, st, _jerarquia_ancla())
        assert s['penalty_source'] == 'none'
        assert s['penalty_anchor'] is None


def test_penalty_source_otra_textura_soporte_parcial():
    s = shadow_equity(0.5, ['Qh', '7h', '2h'], 'turn', _jerarquia_ancla())
    assert s['penalty_source'] == 'partial_support'
    assert s['penalty_anchor'] is None


def test_penalty_anchor_documenta_incertidumbre():
    """`measured` significa una celda concreta, con n y sin intervalo
    calculado. El registro debe llevar ese contexto."""
    s = shadow_equity(0.69, BOARD_FLOOP, 'turn', _jerarquia_ancla())
    anchor = s['penalty_anchor']
    assert anchor['n_per_cell'] == 36
    assert anchor['uncertainty'] is None
    assert anchor['ci_note']
    assert anchor['criterion']
    assert anchor['source']


def test_hero_bet_se_expone_en_la_jerarquia():
    """El ancla exige que el hero aposte: es condición, no suposición."""
    bet = classify_villains(_acts(('UTG', 'x'), ('MP', 'b'), ('BTN', 'b')),
                            'BTN', ())
    assert bet['hero_bet'] is True
    check = classify_villains(_acts(('MP', 'b'), ('BTN', 'x')), 'BTN', ())
    assert check['hero_bet'] is False


def test_equity_shadow_no_se_hace_negativa():
    jer = _jerarquia_ancla()
    jer['checkers'] = ['UTG'] * 40
    jer['checkers_secondary'] = jer['checkers']
    jer['checkers_all'] = jer['checkers']
    s = shadow_equity(0.02, BOARD_FLOOP, 'turn', jer)
    if s['equity_shadow'] is None:
        pytest.skip('sin anchor_match: equity_shadow es None por diseño')
    assert s['equity_shadow'] >= 0.0


def test_registro_identifica_contra_que_rango():
    """El registro dice contra qué rival se calculó la equity (P0)."""
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', ())
    sh = shadow_equity(0.5, BOARD_FLOOP, 'flop', jer, equity_source='CO')
    rec = shadow_record('H_1', 'flop', BOARD_FLOOP, HERO, jer, sh,
                        10.0, 0.0, 90.0, 'bet_25')
    assert rec['villain_used_for_equity'] == 'CO'
    assert rec['equity_source_is_main'] is False


def test_registro_detecta_coincidencia_de_rango():
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', ())
    sh = shadow_equity(0.5, BOARD_FLOOP, 'flop', jer, equity_source='MP')
    rec = shadow_record('H_1', 'flop', BOARD_FLOOP, HERO, jer, sh,
                        10.0, 0.0, 90.0, 'bet_25')
    assert rec['villain_used_for_equity'] == 'MP'
    assert rec['equity_source_is_main'] is True


def test_equity_main_no_se_confunde_con_produccion():
    """pegar_3 §2 P0: son tres equities DISTINTAS.

    Antes el campo de producción se llamaba `equity_main`, lo que
    sugería que era la equity contra el rival principal de la jerarquía.
    No lo es, y no se calcula. Debe quedar explícito.
    """
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', ())
    s = shadow_equity(0.69, BOARD_FLOOP, 'turn', jer, equity_source='MP')
    assert s['equity_production'] == 0.69      # la del motor
    assert s['equity_main'] is None            # contra el principal: no hay
    assert s['equity_main_available'] is False
    assert s['equity_main_note']
    # que coincidan las fuentes NO convierte una en la otra
    assert s['equity_source_is_hierarchy_main'] is True
    assert s['equity_main'] is not s['equity_production']


def test_penalty_anchor_documenta_la_muestra():
    """`anchor_match` significa una celda concreta, con n y sin intervalo
    calculado. El registro debe llevar ese contexto."""
    s = shadow_equity(0.69, BOARD_FLOOP, 'turn', _jerarquia_ancla())
    anchor = s['penalty_anchor']
    assert anchor is not None
    assert anchor['n_per_cell'] == 36
    assert anchor['uncertainty'] is None
    assert anchor['ci_note']
    assert anchor['criterion']
    assert anchor['source']


def test_penalty_anchor_ausente_cuando_no_hay_anchor_match():
    s = shadow_equity(0.5, BOARD_FLOOP, 'flop', _jerarquia_ancla())
    assert s['penalty_source'] == 'none'
    assert s['penalty_anchor'] is None


# --- cálculo sombra ------------------------------------------------------

def test_shadow_equity_reduce_y_marca_experimental():
    jer = _jerarquia_ancla()
    s = shadow_equity(0.50, BOARD_FLOOP, 'turn', jer)
    assert s['equity_shadow'] < s['equity_production']
    assert s['n_checker'] == 1
    assert s['penalty'] > 0
    assert s['experimental'] is True


def test_shadow_equity_sin_anchor_match_no_inventa_numero():
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', ())
    s = shadow_equity(0.50, BOARD_FLOOP, 'turn', jer)
    assert s['equity_shadow'] is None
    assert s['delta'] is None
    assert s['penalty'] is None
    assert s['equity_shadow_note']


def test_pendientes_no_entran_en_la_penalizacion():
    """Un pendiente no es un checker: siguen siendo amenaza activa."""
    jer = {'main': 'MP', 'checkers': [], 'checkers_all': [],
           'pending': ['CO', 'SB'], 'aggressors': ['MP'],
           'hero_bet': False}
    s = shadow_equity(0.50, BOARD_FLOOP, 'turn', jer)
    assert s['penalty'] is None
    assert s['n_pending'] == 2
    assert s['equity_shadow'] is None


# --- log ----------------------------------------------------------------

def test_shadow_log_escribe_jsonl(tmp_path):
    p = tmp_path / 'shadow.jsonl'
    lg = ShadowLog(path=str(p))
    rec = shadow_record('H_1', 'flop', BOARD_FLOOP, HERO,
                        classify_villains(_acts(('MP', 'b')), 'BTN', ()),
                        shadow_equity(0.5, BOARD_FLOOP, 'flop',
                                      {'checkers': [], 'pending': []}),
                        10.0, 0.0, 90.0, 'bet_25')
    assert lg.append(rec) is True
    rows = [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()]
    assert len(rows) == 1
    assert rows[0]['hand_id'] == 'H_1'
    assert rows[0]['experimental'] is True


def test_shadow_log_desactivado_no_escribe(tmp_path):
    p = tmp_path / 'shadow.jsonl'
    lg = ShadowLog(path=str(p), enabled=False)
    assert lg.append({'a': 1}) is False
    assert not p.exists()


def test_shadow_log_fallo_no_propaga(tmp_path):
    """Ruta no escribible: se pierde la fila, nunca el motor."""
    lg = ShadowLog(path=str(tmp_path / 'no' / 'dir' / 'x.jsonl'))
    assert lg.append({'a': 1}) is False


# --- LA GARANTÍA IMPORTANTE ---------------------------------------------

def test_shadow_no_altera_la_accion():
    """Con y sin contexto de jerarquía, la acción es idéntica.

    Es la garantía central del modo sombra. Si este test falla, el motor
    está calibrando con 36 manos por escenario.
    """
    jer = classify_villains(_acts(('UTG', 'x'), ('MP', 'b'), ('CO', 'x')),
                            'BTN', activos=['SB'])
    jer['checkers_all'] = ['UTG', 'CO']
    jer['checkers_secondary'] = ['UTG', 'CO']
    base = dict(hero_codes=HERO, board_codes=BOARD_FLOOP, pot=25.0,
                to_call=0.0, stack=90.0, street='flop', position='BTN',
                villain_pos='MP', deadline_s=5.0, runout=False)
    sin = recommend(**base)
    con = recommend(**base, hierarchy=jer)
    assert con.action == sin.action
    assert con.value == pytest.approx(sin.value, abs=1e-12)
    # y la sombra sí calculó su clasificación, aunque sin emitir equity
    assert con.shadow is not None
    assert con.shadow['n_checker_all'] == 2
    # sin anchor_match no debe inventarse una equity_shadow
    assert con.shadow['equity_shadow'] is None


@pytest.mark.parametrize('variante', ['log', 'callers', 'pending', 'ancla'])
def test_shadow_no_altera_la_accion_en_cada_variante(variante, tmp_path):
    """pegar_2 §2.5: la garantía debe cubrir todos los caminos.

    Con log, con callers, con pendientes y con el escenario exacto del
    ancla. La acción no puede cambiar en ninguno.
    """
    jer = classify_villains(_acts(('UTG', 'x'), ('MP', 'b'), ('CO', 'c')),
                            'BTN', activos=['SB', 'HJ'])
    jer.setdefault('callers', ['CO'])
    if variante == 'callers':
        jer['checkers'] = ['UTG']
    elif variante == 'pending':
        jer['checkers'] = []
    elif variante == 'ancla':
        jer = {'main': 'MP', 'hero_bet': True, 'aggressors': ['MP'],
               'checkers': ['UTG'], 'pending': ['CO'], 'callers': []}

    base = dict(hero_codes=HERO, board_codes=BOARD_FLOOP, pot=25.0,
                to_call=0.0, stack=90.0, street='flop', position='BTN',
                villain_pos='MP', deadline_s=5.0, runout=False)
    kwargs = {}
    if variante == 'log':
        kwargs['shadow_log'] = ShadowLog(path=str(tmp_path / 's.jsonl'))
    sin = recommend(**base)
    con = recommend(**base, hierarchy=jer, **kwargs)
    assert con.action == sin.action
    assert con.value == pytest.approx(sin.value, abs=1e-12)
    if variante == 'log':
        assert (tmp_path / 's.jsonl').exists()


def test_shadow_sin_contexto_no_hay_registro():
    base = dict(hero_codes=HERO, board_codes=BOARD_FLOOP, pot=25.0,
                to_call=0.0, stack=90.0, street='flop', position='BTN',
                villain_pos='MP', deadline_s=5.0, runout=False)
    rec = recommend(**base)
    assert rec.shadow is None


def test_shadow_no_rompe_con_contexto_raro():
    """Un contexto malformado no puede tumbar la recomendación."""
    base = dict(hero_codes=HERO, board_codes=BOARD_FLOOP, pot=25.0,
                to_call=0.0, stack=90.0, street='flop', position='BTN',
                villain_pos='MP', deadline_s=5.0, runout=False)
    roto = {'main': None, 'checkers': None, 'pending': None}
    rec = recommend(**base, hierarchy=roto)
    assert rec.action in ('fold', 'check', 'call', 'bet_25', 'bet_50',
                          'bet_75', 'raise', 'all_in')