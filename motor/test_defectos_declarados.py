# -*- coding: utf-8 -*-
"""Los DEFECTOS DECLARADOS, fijados como referencia de regresion.

Y hay uno solo, y es el del contador de subidas: una apuesta de 0.5 BB o
menos se CLASIFICA como `limp` —y el docstring de `classify_first_action`
dice que «no se cuenta como subida real»— pero el contador de
`preflop_events` la cuenta como **subida** de todas maneras.

MEDIDO, y las dos cifras: **52 de 1258** manos, y **43 de las 877 de la
ventana fiable**, que es la que alimenta las cifras publicadas.

Y el motivo de que este test AFIRME el defecto, y no que no pase:

> Un defecto declarado y fijado es una cosa. Un defecto que se corrige solo,
> en un bloque que no es el de la recalibración, es otra. Y una cifra
> publicada que se mueve sin que alguien lo decida es una cifra que nadie ha
> medido.

Y la condición de activación, que es la del contrato: **se corrige cuando las
cifras publicadas se re-deriven contra la base adoptada, no antes.**
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor import learn   # noqa: E402


def _hand(preflop):
    return {'hand_id': 'T', 'players': {}, 'streets': {
        'preflop': {'actions': [{'pos': p, 'action': a, 'amount': m}
                                for p, a, m in preflop]},
        'flop': {'board': ['2h', '7d', '9c'], 'actions': []}}}


def test_el_limp_corto_se_clasifica_como_limp_y_se_cuenta_como_subida():
    """El DESACUERDO, reproducido. Y las dos mitades, por separado.

    Y la primera mitad es la del clasificador: una apuesta de 0.5 BB o menos es
    un limp corto, y el docstring dice que no cuenta como subida real.

    Y la segunda es la del contador: la siguiente accion del UTG recibe un
    `3bet`, que solo puede querer decir «estoy enfrentando una subida».
    """
    h = _hand([('SB', 'b', 0.5), ('UTG', 'b', 2.5)])

    # 1. el CLASIFICADOR
    assert learn.classify_first_action('b', 0.5, 0, 0) == ('limp', 'no_raise'), (
        'una apuesta de 0.5 BB o menos es un limp corto, y el docstring lo '
        'dice. Y si esto cambia, el defecto del contador es otro, y hay que '
        're-mirarlo.')

    # 2. el CONTADOR
    cat = [(e.pos, e.category) for e in learn.preflop_events(h)]
    assert cat == [('SB', 'limp'), ('UTG', '3bet')], cat

    # 3. y el DESACUERDO, que es el defecto: el SB es un limp, y el UTG
    #    enfrenta una subida que no hubo.
    assert cat[0] == ('SB', 'limp'), cat
    assert cat[1] == ('UTG', '3bet'), (
        'el UTG recibe un 3bet, y solo si el limp corto cuenta como subida. '
        'Y el docstring de `classify_first_action` dice que no cuenta. '
        'MEDIDO: 52 de 1258 manos, y 43 de las 877 de la ventana fiable. '
        'Y este test CAMBIA con esa medicion, cuando se recalibre contra la '
        'base adoptada, y no antes.')


def test_la_condicion_de_activacion_del_defecto_esta_escrita():
    """Y que la condicion de activacion este en el sitio donde se decide.

    Y la condicion es: se corrige cuando las cifras publicadas se re-deriven
    contra la base adoptada, y no antes. Y tiene que estar escrita, porque un
    defecto sin condicion de activacion se arregla un dia sin que nadie decida
    que ese era el dia.
    """
    con = leer('motor/test_cm004.py')
    assert 'A PARTIR DE DATOS YA' in con, (
        'la condicion de activacion tiene que estar escrita donde se decide')
    doc = leer('DOCS/CONTRATO_ACCION_P.md')
    assert 'no se arregla' in doc or 'NO se arregla' in doc, (
        'y en el contrato, que es donde se explica el defecto')
    aud = leer('DOCS/AUDITORIA_RULES.md')
    assert 'recalibra' in aud.lower(), (
        'y en la auditoria, que es donde estan los hallazgos')


def leer(rel):
    with io.open(os.path.join(ROOT, rel.replace('/', os.sep)),
                 encoding='utf-8') as f:
        return f.read()
