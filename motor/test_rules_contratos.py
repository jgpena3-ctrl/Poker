# -*- coding: utf-8 -*-
"""F5 — Contratos de `rules.py`.

revision_2 pide definir contratos ANTES de cambiar implementaciones. Aqui se
formaliza lo que `plan()` y `select_best()` prometen, y se comprueba.

La mayoria de estos tests documentan el comportamiento ACTUAL (incluidos
defectos conocidos). No se cambia la implementacion en este bloque: se fija
lo que hay, para que un cambio posterior sea deliberado y detectable.

Referencia: DOCS/CONTRATOS_RULES.md
"""
import numpy as np
import pytest

from motor import rules
from motor.decision import EvTable

FLOP = ['Qh', '7s', '2c']
TURN = ['Qh', '7s', '2c', 'Jd']
RIVER = ['Qh', '7s', '2c', 'Jd', '9h']


def _ev(**kw):
    base = {'fold': 0.0, 'check': 1.0, 'call': 0.5, 'all_in': 2.0,
            'bet_25': 0.8, 'bet_50': 1.2, 'bet_75': 1.6}
    base.update(kw)
    return EvTable(ev=dict(base), pot=10.0, hero_equity=0.5)


# ===========================================================================
# CONTRATO 1 — board_class
# ===========================================================================

def test_c1_board_class_devuelve_None_si_faltan_cartas():
    """board_class(board) es None con board incompleto: no inventa textura."""
    assert rules.board_class([]) is None
    assert rules.board_class(None) is None
    assert rules.board_class(['Qh', '7s']) is None


def test_c1_board_class_solo_devuelve_valores_del_dominio():
    """El dominio es exactamente {'DRY','SEMI_DRY','WET', None}."""
    dominio = {'DRY', 'SEMI_DRY', 'WET', None}
    tableros = [
        ['Ah', 'Kd', '2c'],                       # rainbow
        ['As', 'Ks', 'Qs'],                       # monotone
        ['9h', '8h', '7h'],                       # monotone corrido
        ['Jh', 'Td', '9s'],                       # straight run
        ['9d', '8h', '7h'],                       # two tone
        ['Ah', '7d', '2c', '3s', '5h'],           # river rainbow
    ]
    for b in tableros:
        assert rules.board_class(b) in dominio, b


def test_c1_board_class_es_idempotente():
    for b in (FLOP, TURN, RIVER):
        assert rules.board_class(b) == rules.board_class(list(b))


# ===========================================================================
# CONTRATO 2 — plan(): precondiciones
# ===========================================================================

def test_c2_plan_rechaza_preflop():
    """CONTRATO: `street='preflop'` lanza ValueError.

    Es el contrato vigente. recommend_loop lo captura y pone rp=None, con lo
    que se pierde TODO el filtrado de reglas; por eso el defecto esta
    documentado en PROYECTO.md 6.1. Este test lo fija para que cambiarlo sea
    deliberado.
    """
    with pytest.raises(ValueError):
        rules.plan(street='preflop', hero_initiator=False, to_call=0,
                   board_codes=FLOP, pot=10.0, stack=50.0, n_players=2,
                   facing_raise=False, hero_bet_flop=False, hero_oop=False,
                   flop_checked=True, villain_bet_flop=False)


def test_c2_plan_rechaza_street_desconocida():
    with pytest.raises((ValueError, KeyError)):
        rules.plan(street='turno', hero_initiator=False, to_call=0,
                   board_codes=FLOP, pot=10.0, stack=50.0, n_players=2,
                   facing_raise=False, hero_bet_flop=False, hero_oop=False,
                   flop_checked=True, villain_bet_flop=False)


def test_c2_plan_siempre_devuelve_un_RulePlan():
    """Con street valida y board completo, plan() nunca devuelve None."""
    for street, board in (('flop', FLOP), ('turn', TURN), ('river', RIVER)):
        rp = rules.plan(street=street, hero_initiator=False, to_call=0.0,
                        board_codes=board, pot=10.0, stack=50.0, n_players=2,
                        facing_raise=False, hero_bet_flop=False,
                        hero_oop=True, flop_checked=True, villain_bet_flop=False)
        assert rp is not None, street
        assert isinstance(rp, rules.RulePlan), street


# ===========================================================================
# CONTRATO 3 — RulePlan: invariantes
# ===========================================================================

def _plan(**kw):
    base = dict(street='flop', hero_initiator=False, to_call=0.0,
                board_codes=FLOP, pot=10.0, stack=50.0, n_players=2,
                facing_raise=False, hero_bet_flop=False, hero_oop=True,
                flop_checked=True, villain_bet_flop=False)
    base.update(kw)
    return rules.plan(**base)


def test_c3_candidates_siempre_es_una_tupla_no_vacia():
    """INVARIANTE: `candidates` nunca vacio.

    Si se vaciara, `select_best` solo tendria 'fold' y devolveria un fold
    silencioso sin explicar por que (PROYECTO.md 6.1).
    """
    escenarios = [
        dict(),                                                    # check
        dict(to_call=5.0),                                         # facing bet
        dict(hero_initiator=True, to_call=0.0),                     # cbet
        dict(to_call=5.0, facing_raise=True),                       # facing raise
        dict(n_players=4, to_call=0.0),                             # multiway
        dict(street='turn', board_codes=TURN),
        dict(street='river', board_codes=RIVER),
    ]
    for kw in escenarios:
        rp = _plan(**kw)
        assert rp.candidates, 'candidates vacio con %s' % kw
        assert isinstance(rp.candidates, tuple), kw


def test_c3_candidates_contiene_fold_solo_cuando_hay_to_call():
    """INVARIANTE: con to_call == 0 no tiene sentido la accion 'fold'."""
    for kw in (dict(), dict(hero_initiator=True),
               dict(n_players=3, hero_initiator=True)):
        rp = _plan(**kw)
        assert 'fold' not in rp.candidates, kw


def test_c3_bet_sizes_siempre_en_intervalo_valido():
    """INVARIANTE: cada bet_size es un float dentro del rango util.

    Las etiquetas (`bet_25`, `bet_50`, ...) las genera `decision._bet_label`
    a partir de la fraccion, asi que basta con que esten en (0, 1.5].
    """
    for kw in (dict(hero_initiator=True),
               dict(hero_initiator=True, street='turn', board_codes=TURN),
               dict(hero_initiator=False, to_call=0.0, hero_bet_flop=True)):
        rp = _plan(**kw)
        for bs in rp.bet_sizes:
            assert isinstance(bs, float), (kw, type(bs))
            assert 0 < bs <= 1.5, (kw, bs)


def test_c3_plan_es_determinista():
    """INVARIANTE: mismas entradas -> mismo plan (sin azar ni reloj)."""
    kw = dict(hero_initiator=True, to_call=0.0)
    a, b = _plan(**kw), _plan(**kw)
    assert a.candidates == b.candidates
    assert a.bet_sizes == b.bet_sizes
    assert a.spot == b.spot


# ===========================================================================
# CONTRATO 4 — select_best()
# ===========================================================================

def test_c4_sin_plan_devuelve_el_mejor_global():
    """CONTRATO: rp=None equivale a evs.best() sobre todas las acciones."""
    evs = _ev()
    label, value = rules.select_best(evs, None)
    assert label == 'all_in'
    assert value == pytest.approx(2.0)


def test_c4_respeta_las_candidatas_del_plan():
    """INVARIANTE: la accion devuelta esta siempre en rp.candidates."""
    evs = _ev()
    rp = _plan(hero_initiator=True, to_call=0.0)
    label, _v = rules.select_best(evs, rp)
    assert label in rp.candidates


def test_c4_fold_es_el_baseline_real_no_ceros():
    """CONTRATO: el baseline del fold es su EV real, no 0.

    Con TODAS las acciones por debajo del fold, `select_best` debe devolver
    'fold' con SU valor real (negativo). Si devolviera 0.0 estaria
    inventando un numero.
    """
    evs = _ev(fold=-5.0, check=-9.0, call=-9.0, all_in=-9.0,
             bet_25=-9.0, bet_50=-9.0, bet_75=-9.0)
    rp = _plan(to_call=5.0)
    label, value = rules.select_best(evs, rp)
    assert label == 'fold'
    assert value == pytest.approx(-5.0), 'el fold debe valer su EV real'


def test_c4_ignora_acciones_no_calculadas():
    """INVARIANTE: una clave ausente en ev no se elige (no inventa valor)."""
    evs = EvTable(ev={'fold': 0.0, 'check': 1.0}, pot=10.0, hero_equity=0.5)
    rp = _plan()
    label, value = rules.select_best(evs, rp)
    assert label == 'check'
    assert value == pytest.approx(1.0)


NAN = float('nan')
INF = float('inf')


def _evs(**kw):
    return EvTable(ev=dict(kw), pot=10.0, hero_equity=0.5)


# --- las tres ramas que pedia revision_1 Tarea 4 ---------------------------

def test_c4_evs_vacio_lanza_ev_invalido():
    """No hay datos para decidir. Antes devolvia ('fold', 0.0): un numero
    inventado que se leia como "fold es break-even"."""
    with pytest.raises(rules.EvInvalido):
        rules.select_best(_evs(), None)


def test_c4_todos_nan_lanza_ev_invalido():
    """Un NaN no es un EV. Antes devolvia ('fold', nan): devolvia el
    numero que no existe como si fuera la decision."""
    with pytest.raises(rules.EvInvalido):
        rules.select_best(_evs(fold=NAN, check=NAN, all_in=NAN), None)


def test_c4_un_solo_elemento_valido():
    """Debe funcionar: si hay un solo EV real, ese es el mejor."""
    label, value = rules.select_best(_evs(check=2.0), None)
    assert (label, value) == ('check', 2.0)
    label, value = rules.select_best(_evs(fold=-1.5), None)
    assert (label, value) == ('fold', -1.5)


# --- el defecto que No era solo de informe -------------------------------

def test_c4_fold_nan_no_hace_perder_a_la_alternativa_real():
    """Comparar contra NaN siempre da False, asi que el bucle entero se
    quedaba sin mejorar y devolvia ('fold', nan) teniendo 'check' con 3.0.

    Es el caso mas grave de los tres: no era un numero inventado en el
    informe, era una decision equivocada."""
    label, value = rules.select_best(_evs(fold=NAN, check=3.0), None)
    assert (label, value) == ('check', 3.0)


def test_c4_infinito_se_ignora():
    """+inf no es un EV: es un numero que no puede existir."""
    label, value = rules.select_best(_evs(fold=0.0, all_in=INF), None)
    assert (label, value) == ('fold', 0.0)
    label, value = rules.select_best(_evs(fold=0.0, all_in=-INF), None)
    assert (label, value) == ('fold', 0.0)


def test_c4_todos_infinito_lanza():
    with pytest.raises(rules.EvInvalido):
        rules.select_best(_evs(fold=INF, check=INF), None)


# --- el motivo de la decision --------------------------------------------

def test_c4_el_motivo_dice_que_no_hay_datos():
    """El mensaje tiene que distinguir 'no hay datos' de 'fold es la mejor'."""
    with pytest.raises(rules.EvInvalido) as ei:
        rules.select_best(_evs(check=NAN), None)
    msg = str(ei.value)
    assert 'ninguna accion tiene un EV finito' in msg
    assert 'no hay datos para decidir' in msg.lower()
    # y nombra las claves que hubo, para poder diagnosticar
    assert 'check' in msg


def test_c4_ev_invalido_es_valueerror():
    """El contrato dice ValueError; la subclase lo cumple sin romper a
    quien capture el tipo generico."""
    assert issubclass(rules.EvInvalido, ValueError)


# --- determinismo ---------------------------------------------------------

def test_c4_empate_gana_el_primero():
    """Empate: gana el primero, y el fold se considera siempre primero.
    La comparacion es estricta, asi que el resultado es determinista."""
    evs = _evs(fold=1.0, check=1.0, call=1.0)
    assert rules.select_best(evs, None)[0] == 'fold'
    evs = _evs(fold=-1.0, check=2.0, call=2.0)
    assert rules.select_best(evs, None)[0] == 'check'


def test_c4_ninguna_accion_legal_tambien_lanza():
    """Si el plan no ofrece nada evaluable, es el caso de 'sin datos'."""
    rp = _plan(to_call=5.0)
    with pytest.raises(rules.EvInvalido):
        rules.select_best(_evs(fold=NAN, call=NAN), rp)


def test_c4_las_candidatas_ausentes_no_se_inventan():
    """Una clave que no esta en ev no tiene EV: no se elige."""
    label, value = rules.select_best(_evs(fold=0.0, check=1.0), _plan())
    assert label == 'check'
    assert value == pytest.approx(1.0)


# ===========================================================================
# CONTRATO 5 — compatibilidad con los consumidores reales
# ===========================================================================

def test_c5_consumidor_recommend_loop_acepta_el_plan():
    """El contrato de plan() es el que espera recommend_loop.

    recommend_loop hace `rp.candidates`, `rp.bet_sizes`, `rp.raise_to`,
    `rp.note`, `rp.spot`, `rp.bet_sizes` — todos deben existir siempre.
    """
    rp = _plan(hero_initiator=True, to_call=0.0)
    for attr in ('candidates', 'bet_sizes', 'raise_to', 'note', 'spot',
                 'paired', 'structure', 'n_players', 'raise_all_in'):
        assert hasattr(rp, attr), attr


def test_c5_panel_usa_note_y_spot():
    """panel.format_insight lee rp.note y rp.spot: ambos deben ser str."""
    rp = _plan(hero_initiator=True, to_call=0.0)
    assert isinstance(rp.note, str)
    assert isinstance(rp.spot, str)