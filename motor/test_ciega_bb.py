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
