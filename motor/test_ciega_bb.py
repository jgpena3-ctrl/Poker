# -*- coding: utf-8 -*-
"""Tests de la correccion de `_es_ciega_bb` (causa B).

La funcion pedia `amount <= bb` con `bb` = constante nominal (`learn.BB` = 1.0).
Medido sobre la ventana fiable, eso rechazaba 4 manos cuya ciega real era
2.5-92.0 y cuyo `BB b` estaba en el indice 0: el motor las creditaba con una
SUBIDA (`rol`/`squeeze`/`3bet`/`open`) que probablemente no ocurrio.

La condicion era ademas redundante: si no hubo ninguna accion voluntaria
previa, un `BB b` no puede ser una subida.
"""
import pytest

from motor import learn


def _seq(hand):
    return learn._preflop_sequence(hand)


def _hand(preflop, flop=True):
    """Mano minima con las acciones preflop dadas."""
    h = {'hand_id': 'T', 'players': {}, 'streets': {
        'preflop': {'actions': [{'pos': p, 'action': a, 'amount': m}
                                for p, a, m in preflop]}}}
    if flop:
        h['streets']['flop'] = {'board': ['2h', '7d', '9c'], 'actions': []}
    return h


# --- el contrato que se arregla -------------------------------------------

@pytest.mark.parametrize('importe', [2.5, 3.0, 5.0, 92.0])
def test_ciega_sobre_la_ciega_nominal_sigue_siendo_ciega(importe):
    """Una ciega de 92.0 con BB nominal 1.0 es ciega, no una subida.

    Antes `_es_ciega_bb` la rechazaba por `amount <= bb`, y el BB quedaba
    creditado con una subida que no consta en los datos.
    """
    assert learn.BB == 1.0, 'el test asume la ciega nominal 1.0'
    assert learn._es_ciega_bb(0, 'BB', 'b', importe, False, False) is True


def test_bb_con_sobreciega_no_emite_accion():
    """El BB que solo posto una sobreciega no genera ningun evento."""
    h = _hand([('UTG', 'f', 0.0), ('BB', 'b', 5.0)])
    evs = [e for e in learn.preflop_events(h) if e.pos == 'BB']
    assert evs == [], 'el BB solo posto la ciega: %s' % evs


# --- los contratos que NO deben romperse ----------------------------------

def test_ciega_tras_limp_no_es_ciega():
    """Tras un limp el BB si puede estar subiendo: el importe ya no decide,
    pero `voluntary_before` sigue decidiendo."""
    h = _hand([('MP', 'c', 1.0), ('BB', 'b', 6.0)])
    evs = [e for e in learn.preflop_events(h) if e.pos == 'BB']
    assert evs, 'con un limp previo el BB ha actuado'
    assert evs[0].category in ('rol', 'limp'), evs[0].category


def test_marca_explicita_gana():
    assert learn._es_ciega_bb(0, 'BB', 'b', 5.0, True, True) is True


def test_no_es_ciega_si_no_es_bb():
    assert learn._es_ciega_bb(0, 'UTG', 'b', 1.0, False, False) is False


# --- los casos agudos que blindan el fix ----------------------------------
#
# ATENCIÓN sobre qué test discrimina el cambio y cuál no.
#
# La regla VIEJA era:
#     is_blind or (pos=='BB' and act=='b' and not voluntary_before
#                  and amount <= bb)
#
# El importe era un AND ADEMÁS de `voluntary_before`: nunca lo sustituía. Por
# eso los casos con acción voluntaria previa se rechazaban igual antes y
# después. Esos tests fijan el CONTRATO pero NO detectarían una reversión del
# fix. Los que sí discriminan son los que combinan ciega alta (importe por
# encima de la nominal) con ausencia de acción voluntaria previa.

@pytest.mark.parametrize('importe', [1.0, 2.5, 92.0])
def test_ciega_bb_tras_folds_previos_sigue_siendo_ciega(importe):
    """Los folds NO ponen dinero, luego no activan `voluntary_before`.

    Parametrizado con ciega alta porque con 1.0 la regla vieja también lo
    aceptaba: ese caso no distinguiría una reversión del fix.
    """
    h = _hand([('UTG', 'f', 0.0), ('MP', 'f', 0.0), ('CO', 'f', 0.0),
              ('BTN', 'f', 0.0), ('SB', 'f', 0.0), ('BB', 'b', importe)])
    evs = [e for e in learn.preflop_events(h) if e.pos == 'BB']
    assert evs == [], 'el BB solo posto la ciega: %s' % evs


def test_bb_b_mismo_importe_tras_limp_no_es_ciega():
    """CONTRATO, no discrimina el fix: tras un limp el BB ha actuado.

    El importe es la ciega nominal exacta, 1.0, y la regla vieja también lo
    rechazaba porque `voluntary_before` ya era True. Lo que este test fija es
    que manda el limp, no que el importe deje de mandar.
    """
    assert learn.BB == 1.0, 'el caso depende de la ciega nominal 1.0'
    h = _hand([('UTG', 'c', 1.0), ('BB', 'b', 1.0)])
    evs = [e for e in learn.preflop_events(h) if e.pos == 'BB']
    assert len(evs) == 1, 'el BB ha actuado: %s' % evs
    assert evs[0].category in ('rol', 'limp'), evs[0].category


def test_bb_b_mismo_importe_sin_limp_si_es_ciega():
    """CONTRATO, no discrimina el fix: mismo importe, sin limp antes."""
    h = _hand([('UTG', 'f', 0.0), ('BB', 'b', 1.0)])
    evs = [e for e in learn.preflop_events(h) if e.pos == 'BB']
    assert evs == [], 'sin limp previo el BB solo posted la ciega: %s' % evs


def test_ciega_alta_se_detecta_y_no_depende_del_importe():
    """DISCRIMINA el fix: con ciega alta, el importe ya no puede decidir.

    Con la regla vieja, las tres primeras aserciones fallaban.
    """
    for importe in (1.0, 2.5, 92.0):
        assert learn._es_ciega_bb(0, 'BB', 'b', importe, False, False) is True
    # una subida registrada como 'r' nunca es ciega, importe que sea
    assert learn._es_ciega_bb(0, 'BB', 'r', 92.0, False, False) is False
    assert learn._es_ciega_bb(0, 'BB', 'r', 1.0, False, False) is False
    # y con acción voluntaria previa tampoco, aunque el importe sea la ciega
    assert learn._es_ciega_bb(1, 'BB', 'b', 92.0, False, True) is False


def test_guardia_el_fix_sigue_cubierto():
    """Falla si el fix `amount <= bb` se revierte.

    Si alguien simplifica la suite y deja solo casos con `voluntary_before`
    True, la condición eliminada podría volver sin que nada lo notara.
    """
    h = _hand([('UTG', 'f', 0.0), ('BB', 'b', 92.0)])
    evs = [e for e in learn.preflop_events(h) if e.pos == 'BB']
    assert evs == [], ('ciega de 92.0 leida como subida: el fix se ha '
                       'revertido. eventos: %s' % evs)


# --- la limitacion medida, fijada como test -------------------------------

def test_el_respaldo_estructural_no_tapa_una_decision_del_bb():
    """El riesgo real del cambio: que una SUBIDA del BB se lea como ciega.

    Una subida es accion 'r', y la regla exige 'b', asi que nunca se confunden.
    Este test lo fija sobre los datos reales: el respaldo nunca acepta como
    ciega una entrada que no sea un 'b' del BB.

    CORRECCION DE UNA MEDICION PREVIA: un script mio afirmaba "0 casos de BB
    subiendo tras solo folds" y era FALSO, por un error del script (contaba
    `BB r` tras folds, que la rechaza bien porque es 'r' y no 'b'; era H_0139).
    El riesgo medido de verdad es el de este test, y son 0 casos.
    """
    manos = learn.load_hands(reliable_only=True)
    sospechosos = []
    for h in manos:
        vb = False
        for i, (pos, act, amount, is_blind) in enumerate(_seq(h)):
            es_ciega = learn._es_ciega_bb(i, pos, act, amount, is_blind,
                                          vb, learn.BB)
            if es_ciega and act != 'b' and not is_blind:
                sospechosos.append(
                    (h.get('hand_id'), i, pos, act, amount))
            if act in ('b', 'r', 'c'):
                vb = True
    assert sospechosos == [], (
        'el respaldo acepto como ciega una entrada que no es ciega: %s'
        % sospechosos[:10])


def test_no_hay_dos_ciegas_del_bb_reconocidas():
    """El respaldo no puede marcar dos entradas distintas como ciega."""
    manos = learn.load_hands(reliable_only=True)
    duplicadas = []
    for h in manos:
        vb = False
        n = 0
        for i, (pos, act, amount, is_blind) in enumerate(_seq(h)):
            if learn._es_ciega_bb(i, pos, act, amount, is_blind, vb, learn.BB):
                n += 1
                if act in ('b', 'r', 'c'):
                    vb = True
                continue
            if act in ('b', 'r', 'c'):
                vb = True
        if n > 1:
            duplicadas.append((h.get('hand_id'), n))
    assert duplicadas == [], 'mas de una ciega reconocida: %s' % duplicadas[:10]
