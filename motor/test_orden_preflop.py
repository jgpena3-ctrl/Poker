# -*- coding: utf-8 -*-
"""Tests del orden temporal de la reconstruccion preflop (T1, T2).

revision_1 §6 pide pruebas concretas para decidir si el problema del orden es
real o cosmetico. Este modulo cubre las que NO dependen de `asistente_live`
(que requiere cv2); la T3 vive en `test_asistente_live.py`.

Background medido con `tools/auditar_orden_folds.py` sobre las 900 fiables:

  entradas del BB por mano:  0 -> 23   1 -> 376   2 -> 496   3 -> 5

Es decir, el BB puede tener hasta TRES entradas (ciega + decision + reaccion).
Por eso la deteccion de la ciega no puede depender del indice, que es lo que
motivó la marca explicita `blind` y el respaldo estructural `_es_ciega_bb`.

Ademas se comprobó que el orden de un fold SI cambia su propia categoria, que
es el defecto que `_reconstruct_preflop` ya no comete.
"""
import pytest

from motor import learn

ORDEN = ['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB']


def _hand(preflop, hand_id='H_9001'):
    return {
        'hand_id': hand_id,
        'players': [{'name': 'A', 'pos': 'UTG', 'cards': ''},
                    {'name': 'J', 'pos': 'BTN', 'cards': ''}],
        'streets': {'preflop': {'actions': [
            {'pos': p, 'action': a, 'amount': v} for p, a, v in preflop]}},
    }


def _seq(acciones):
    return [(p, a, v, False) for p, a, v in acciones]


def _counters(seq):
    """(raises, limps, callers) con la regla de learn.py."""
    raises = limps = callers = 0
    voluntary = False
    for i, (pos, act, amt, blind) in enumerate(seq):
        if learn._es_ciega_bb(i, pos, act, amt, blind, voluntary):
            continue
        if act in ('b', 'r'):
            raises += 1
            voluntary = True
        elif act == 'c':
            if raises == 0:
                limps += 1
            else:
                callers += 1
            voluntary = True
    return raises, limps, callers


# ---------------------------------------------------------------------------
# T1 — el BB puede tener hasta 3 entradas; la ciega se detecta igual
# ---------------------------------------------------------------------------

def test_t1_bb_tiene_hasta_tres_entradas():
    hands = learn.load_hands(reliable_only=True)
    por_n = {}
    for h in hands:
        seq = list(learn._preflop_sequence(h))
        n = sum(1 for p, a, _m, _b in seq if p == 'BB')
        por_n[n] = por_n.get(n, 0) + 1
    assert sum(por_n.values()) == len(hands)
    assert max(por_n) == 3, 'BB con %d entradas: %s' % (max(por_n), por_n)
    assert por_n.get(3, 0) < len(hands) * 0.02, 'caso BB x3 demasiado raro'


@pytest.mark.parametrize('previa', [
    [],
    [('UTG', 'f', 0.0)],
    [('UTG', 'f', 0.0), ('MP', 'f', 0.0)],
    [('UTG', 'f', 0.0), ('MP', 'f', 0.0), ('CO', 'f', 0.0), ('BTN', 'f', 0.0),
     ('SB', 'f', 0.0)],
])
def test_t1_ciega_detectada_indistintamente_de_lo_que_venga_antes(previa):
    """Con folds antes, la ciega se sigue detectando (no usa el indice)."""
    acciones = previa + [('BB', 'b', 1.0)]
    seq = _seq(acciones)
    found = [i for i, s in enumerate(seq)
             if learn._es_ciega_bb(i, s[0], s[1], s[2], s[3], False)]
    assert found == [len(acciones) - 1], 'ciega mal detectada en %s' % (previa,)


def test_t1_marca_explicita_gana_a_la_heuristica():
    """Con `blind: True` se detecta aunque el importe no sea de ciega."""
    h = {'hand_id': 'X', 'players': [{'name': 'A', 'pos': 'BB',
                                      'cards': ''}],
         'streets': {'preflop': {'actions': [
             {'pos': 'BB', 'action': 'b', 'amount': 5.0, 'blind': True}]}}}
    seq = list(learn._preflop_sequence(h))
    assert seq[0][3] is True
    assert learn._es_ciega_bb(0, 'BB', 'b', 5.0, True, False) is True


# ---------------------------------------------------------------------------
# T2 — contadores y categorias segun el orden
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('voluntarios', [
    [('UTG', 'b', 2.5), ('BTN', 'c', 2.5)],                  # open + call
    [('UTG', 'r', 3.0), ('MP', 'c', 3.0), ('CO', 'r', 9.0)],  # open, call, 3bet
    [('MP', 'c', 1.0), ('BTN', 'b', 3.0), ('SB', 'c', 3.0)],  # limp, open, call
])
def test_t2_folds_anticipados_no_cambian_los_contadores(voluntarios):
    """Los folds NO alteran raises/limps/callers, Este sea su orden.

    Los folds se eligen en las posiciones que NO participan en `voluntarios`,
    para que la secuencia sea coherente.
    """
    usados = {a[0] for a in voluntarios}
    folds = [(p, 'f', 0.0) for p in ORDEN if p not in usados and p != 'BB']

    grabada = folds + voluntarios          # folds por delante (como era antes)
    real = sorted(folds + voluntarios, key=lambda a: ORDEN.index(a[0]))

    assert _counters(_seq(grabada)) == _counters(_seq(real))


def test_t2_el_orden_del_fold_si_cambia_su_categoria():
    """HALLAZGO: el orden del fold SÍ cambia su propia categoría.

    Un fold grabado antes de una subida sale `fold`/no_raise; si en realidad
    ocurrió después le tocaría `fold_vs_open`/facing_open. Por eso
    `_reconstruct_preflop` ya no emite los folds por delante.
    """
    base = [('BB', 'b', 1.0), ('UTG', 'b', 2.5), ('CO', 'c', 2.5)]
    h_despues = _hand(base + [('BTN', 'f', 0.0)])
    h_antes = _hand([('BTN', 'f', 0.0)] + base)

    c_despues = {e.pos: e.category for e in learn.preflop_events(h_despues)}
    c_antes = {e.pos: e.category for e in learn.preflop_events(h_antes)}

    assert c_despues['BTN'] == 'fold_vs_open'
    assert c_antes['BTN'] == 'fold'
    # el resto no se altera: solo cambia la categoría del propio fold
    assert {k: v for k, v in c_despues.items() if k != 'BTN'} == \
           {k: v for k, v in c_antes.items() if k != 'BTN'}


def test_t2_prereq_refleja_el_orden_grabado_no_el_real():
    """`prereq` es el ORDEN GRABADO, no el real: hay que declararlo.

    Este test fija esa limitación para que no cambie por accidente.
    """
    h = _hand([('BB', 'b', 1.0), ('UTG', 'b', 2.5), ('CO', 'c', 2.5)])
    ev = {e.pos: e for e in learn.preflop_events(h)}['CO']
    assert ev.prereq == ('BB:b', 'UTG:b')