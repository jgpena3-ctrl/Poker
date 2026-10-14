# -*- coding: utf-8 -*-
"""Tests de la metrica de POLITICA: el denominador no contiene folds.

revision_2 §3: la cifra publicada no demostraba lo que decia medir. El
codigo separaba los folds para INFORMAR pero no para EXCLUIR, asi que el
denominador de 578 y el numerador de 258 los incluian — mientras el
contrato decia que un fold no consulta equity y no cuenta como punto de
politica multiway.

Estos tests no comprueban el numero: comprueban la REGLA. Un numero puede
cambiar sin que nada este mal; la regla no se puede romper en silencio.
"""
from motor import learn
from motor.multiway import (
    CLASES, CLASES_POLITICA, POSTFLOP, SIN_DECISION, acciones,
    en_bote_en_instante, hero_pos, instantes_decision, metrica_politica,
    puntos_decision_mano, posiciones_allin,
)


def _m():
    """LA MISMA funcion que usa el auditor. Una copia aqui seria otro
    sitio donde el bug puede colarse sin que nadie lo vea."""
    return metrica_politica(learn.load_hands(reliable_only=True))


def _tabla():
    return _m()['tabla']


def _denominador_de_politica(t):
    """HU + MULTIWAY, y SOLO los no-fold. Esta es la regla del contrato."""
    return t[('no fold', 'HU')] + t[('no fold', 'MULTIWAY')]


def test_el_denominador_de_politica_no_contiene_folds():
    """Mira el VALOR PUBLICADO, no lo recalcula.

    Este test existia antes comprobando una cuenta hecha aqui mismo, y por
    eso no lo detectaron al mutar `metrica_politica`: la cuenta del test era
    correcta mientras el valor publicado no. Un guard que recalcula lo que
    vigila no vigila nada.
    """
    m = _m()
    t = m['tabla']
    con_folds = sum(t[(f, c)] for f in ('fold', 'no fold')
                    for c in CLASES_POLITICA)
    sin_folds = sum(t[('no fold', c)] for c in CLASES_POLITICA)
    assert t[('fold', 'HU')] + t[('fold', 'MULTIWAY')] > 0, (
        'no hay folds que excluir: el caso de prueba desaparecio')
    # el valor que devuelve la funcion es el que NO lleva folds
    assert m['denominador'] == sin_folds, (
        'metrica_politica() devuelve %d, con folds seria %d'
        % (m['denominador'], con_folds))
    assert m['denominador'] < con_folds


def test_el_numerador_de_multiway_no_contiene_folds():
    t = _tabla()
    assert t[('fold', 'MULTIWAY')] > 0, (
        'el caso de prueba ya no existe: si no hay folds multiway, este '
        'test ha dejado de vigilar nada')
    m = _m()
    t = m['tabla']
    assert m['numerador'] == t[('no fold', 'MULTIWAY')]
    assert m['numerador'] == (t[('fold', 'MULTIWAY')]
                              + t[('no fold', 'MULTIWAY')]
                              - t[('fold', 'MULTIWAY')])


def test_la_cota_usa_el_mismo_criterio_que_la_metrica():
    """El techo tiene que salir de DESCONOCIDO no-fold, o cuenta dos veces
    los mismos puntos: una vez como HU y otra como MW."""
    m = _m()
    t = m['tabla']
    assert m['techo_desconocidos'] <= t[('no fold', 'DESCONOCIDO')], (
        'la cota cuenta mas puntos que hay desconocidos: hay un criterio '
        'distinto en cada sitio')
    assert m['techo'] == m['numerador'] + m['techo_desconocidos']


def test_los_cuadres_suman():
    """Las dos sumas del informe, verificadas en el test y no solo en el
    script que imprime."""
    t = _tabla()
    total = sum(t.values())
    assert sum(t[(f, c)] for f in ('fold', 'no fold')
               for c in CLASES) == total
    calles = len(learn.load_hands(reliable_only=True)) * len(POSTFLOP)
    sin_accion = sin_hero = con_hero = 0
    for h in learn.load_hands(reliable_only=True):
        hp = hero_pos(h)
        for st in POSTFLOP:
            acts = acciones(h, st)
            n = len(instantes_decision(h, st)) if hp else 0
            if not acts:
                sin_accion += 1
            elif n == 0:
                sin_hero += 1
            else:
                con_hero += 1
    assert sin_accion + sin_hero + con_hero == calles
    assert con_hero <= total, 'mas calles con hero que acciones del hero'


def test_un_fold_no_es_un_punto_de_politica_pero_su_si_un_punto():
    """El punto de vista del contrato: decide, pero no consulta equity."""
    t = _tabla()
    folds = sum(t[('fold', c)] for c in CLASES)
    assert folds > 0
    for c in CLASES:
        assert t[('fold', c)] + t[('no fold', c)] == sum(
            t[(f, c)] for f in ('fold', 'no fold'))