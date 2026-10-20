# -*- coding: utf-8 -*-
"""La acción `p`: una posta que no es una decisión.

Y el contrato es `DOCS/CONTRATO_ACCION_P.md`, y estas son sus pruebas.

Y son manos **SINTÉTICAS y pequeñas**, y no la base, por una razón que ya se
ha pagado: la base de hoy no tiene ni una `p`, de modo que un caso tomado de
ella no probaría nada de la semántica nueva. Y una prueba de contrato que
solo se puede construir con la base que todavía no es la canónica no es una
prueba: es una promesa.

Y lo que se prueba, en una línea: **una posta pone dinero, no es una
decisión, y no sube el nivel.** Y las tres cosas por separado, porque las tres
se pueden equivocar por separado.
"""
import collections
import io
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor import learn   # noqa: E402


def _hand(preflop):
    """Mano mínima con las acciones preflop dadas."""
    return {'hand_id': 'T', 'players': {}, 'streets': {
        'preflop': {'actions': [{'pos': p, 'action': a, 'amount': m}
                                for p, a, m in preflop]},
        'flop': {'board': ['2h', '7d', '9c'], 'actions': []}}}


def _eventos(hand, pos=None):
    evs = list(learn.preflop_events(hand))
    if pos is not None:
        evs = [e for e in evs if e.pos == pos]
    return evs


# --- 1. la ciega del BB, grabada como `p` ----------------------------------

def test_la_ciega_del_bb_grabada_como_p_se_reconoce():
    """Una `BB p` es la ciega del BB, y no una subida.

    Y el caso discriminante: con la codificacion vieja, un `BB b` de 1.0 SIN
    acciones volatiles antes es la ciega; y con la nueva, un `BB p` de 1.0 lo
    es igual. De modo que la regla reconoce las dos.
    """
    h = _hand([('BB', 'p', 1.0), ('UTG', 'b', 2.5)])
    assert learn._es_ciega_bb(0, 'BB', 'p', 1.0, False, False) is True, (
        'un `BB p` sin acciones volatiles antes es la ciega del BB')
    # y con la codificacion vieja, la misma cosa
    assert learn._es_ciega_bb(0, 'BB', 'b', 1.0, False, False) is True


def test_un_bb_p_tras_accion_voluntaria_no_es_ciega():
    """Y DESPUES de una accion voluntaria, ya no es la ciega.

    Y esta es la analogia de CM-004 en la codificacion nueva: una ciega
    puesta tarde.
    """
    h = _hand([('UTG', 'b', 2.5), ('BB', 'p', 1.0)])
    assert learn._es_ciega_bb(1, 'BB', 'p', 1.0, False, True) is False
    rechazos = learn.entradas_bb_rechazadas(h)
    assert rechazos, 'una `BB p` tarde tiene que salir como rechazo'
    assert rechazos[0][2] == learn.CAUSA_ORDEN, rechazos


# --- 2. una posta NO es una decision ---------------------------------------

def test_una_p_sola_no_es_ninguna_decision():
    """El jugador que postea SIGUE sin decidir.

    Y el caso discriminante, MEDIDO: en la codificacion vieja, una `SB b` de
    0.5 SI produce un evento —de categoria `limp`, porque una apuesta de 0.5 BB
    o menos es un limp corto—. Y con la `p`, no: una posta no es una
    decision, de modo que el SB no ha decidido nada.
    """
    h = _hand([('SB', 'p', 0.5)])
    assert _eventos(h, 'SB') == [], (
        'una posta no es una decision: %r' % (_eventos(h, 'SB'),))
    # y el contraste, con la codificacion vieja
    h_vieja = _hand([('SB', 'b', 0.5)])
    assert _eventos(h_vieja, 'SB'), (
        'con la codificacion vieja, el `SB b` de 0.5 SI decide. Y por eso la '
        'diferencia entre las dos codificaciones no es de escritura: es de '
        'CUENTO.')
    assert _eventos(h_vieja, 'SB')[0].category == 'limp'


def test_la_ciega_del_sb_grabada_como_p_no_es_un_limp():
    """Y el caso de la copia, con las dos ciegas posteadas.

    MEDIDO sobre la copia normalizada: el SB aparece como `call_open` —su
    primera DECISION— y no como un limp.
    """
    h = _hand([('SB', 'p', 0.5), ('BB', 'p', 1.0), ('UTG', 'b', 2.5),
               ('MP', 'c', 2.5)])
    assert _eventos(h, 'SB') == [], 'el SB solo posteo: %r' % (
        _eventos(h, 'SB'),)
    assert _eventos(h, 'MP')[0].category == 'call_open'


# --- 3. una posta NO sube el nivel -----------------------------------------

def test_la_codificacion_es_neutra_para_la_misma_mesa():
    """Que cambiar COMO se escribe una ciega no cambie lo que pasó.

    Y este es el punto, y es el que hace que el cambio sea preparatorio: la
    misma mesa, escrita de las dos maneras, tiene que dar las mismas
    categorias. Y el caso lo dice comparando las dos.

    Y lo que se compara es el NOMBRE de la categoria y la posicion, no el
    importe: el importe de la ciega no cambia, y lo que se compara es lo que
    el motor AFIRMA que pasó.
    """
    vieja = _hand([('BB', 'b', 1.0), ('UTG', 'b', 2.5), ('MP', 'b', 6.0),
                   ('CO', 'f', 0.0)])
    nueva = _hand([('BB', 'p', 1.0), ('UTG', 'b', 2.5), ('MP', 'b', 6.0),
                   ('CO', 'f', 0.0)])
    a = [(e.pos, e.category, e.denom) for e in learn.preflop_events(vieja)]
    b = [(e.pos, e.category, e.denom) for e in learn.preflop_events(nueva)]
    assert a == b, (
        'la misma mesa, escrita de las dos maneras, da %r y %r. Y eso no puede '
        'ser: cambiar como se escribe una ciega no puede cambiar lo que pasó.'
        % (a, b))
    # y el contenido, para que el caso no sea trivial
    assert a, 'la mesa tiene que tener eventos, o el caso no prueba nada'
    assert ('UTG', 'open', 'no_raise') in a, a


def test_una_p_no_es_un_limp_para_los_demas():
    """Y una posta no cuenta como limp en el contador de los demas.

    Y el motivo de que esto importe: `limps` es un contador GLOBAL de la
    mesa, de modo que una ciega contada como limp cambia la categoria de los
    que vienen despues. Y por eso el SB importa, y no el BB: la ciega del BB
    la reconoce `_es_ciega_bb` en las dos codificaciones, y la del SB no.

    Y aqui hay un DEFECTO DEL MOTOR ACTUAL, que este caso deja a la vista y
    que NO se arregla en este bloque:

    > una apuesta de 0.5 BB o menos se CLASIFICA como `limp` —y el
    > docstring de `classify_first_action` dice que «no se cuenta como subida
    > real»— pero el contador de `preflop_events` la cuenta como subida de
    > todas maneras. Las dos cosas no pueden ser verdad.

    MEDIDO: 52 de 1258 manos, y **43 de las 877 de la ventana fiable**, que
    es la que alimenta las cifras publicadas. De modo que arreglarlo las
    mueve, y eso es una recalibracion que no se hace aqui. Ver
    `DOCS/CONTRATO_ACCION_P.md` §9.
    """
    h_nueva = _hand([('SB', 'p', 0.5), ('UTG', 'b', 2.5)])
    cat_nueva = [(e.pos, e.category) for e in learn.preflop_events(h_nueva)]
    assert cat_nueva == [('UTG', 'open')], cat_nueva
    # y el caso viejo, con el DEFECTO a la vista, y sin afirmarlo: el test
    # afirma el contrato, y el defecto esta declarado en el contrato.
    h_vieja = _hand([('SB', 'b', 0.5), ('UTG', 'b', 2.5)])
    cat_vieja = [(e.pos, e.category) for e in learn.preflop_events(h_vieja)]
    assert cat_vieja[0] == ('SB', 'limp'), cat_vieja


def test_una_p_no_es_una_decision_para_classify_first_action():
    """Y `classify_first_action` sigue LANZANDO ante una `p`.

    Y por que lanza, y no es un descuido: `classify_first_action` clasifica
    una DECISION, y una posta no lo es. Lo que se hace es SALTAR las posts
    antes de llegar ahi, y eso lo decide el CONSUMIDOR —`preflop_events`—, no
    esta funcion.

    Y el error que evita: si `classify_first_action` aceptase la `p` y le
    devolviese una categoria, el motor tendria que inventar una categoria que
    no existe, y ese numero se publicaria.
    """
    with pytest.raises(ValueError):
        learn.classify_first_action('p', 0.5, 0, 0)


# --- 4. lo que NO cambia, y es lo que hace el cambio preparatorio -----------

def test_una_b_normal_se_clasifica_igual_que_antes():
    """Y la codificacion vieja no cambia ni un pelo."""
    assert learn.classify_first_action('b', 2.5, 0, 0) == ('open', 'no_raise')
    assert learn.classify_first_action('b', 3.0, 0, 1) == ('rol', 'no_raise')
    assert learn.classify_first_action('c', 1.0, 0, 0) == ('limp', 'no_raise')
    assert learn.classify_first_action('f', 0, 0, 0) == ('fold', 'no_raise')


def test_la_base_de_hoy_no_se_mueve():
    """Que el cambio sea PREPARATORIO y no una recalibración.

    Y el modo de comprobarlo: la base de hoy no tiene ni una `p`, de modo que
    ningun numero puede moverse. Y eso se comprueba, no se supone.
    """
    manos = learn.load_hands(reliable_only=False)
    assert manos, 'la base tiene que estar'
    con_p = 0
    for h in manos:
        for calle in ('preflop', 'flop', 'turn', 'river'):
            for a in ((h.get('streets', {}) or {}).get(calle, {}) or {}).get(
                    'actions', []) or []:
                if a.get('action') == 'p':
                    con_p += 1
    assert con_p == 0, (
        'la base canonica tiene %d acciones `p`, y el cambio que este fichero '
        'prueba es para la codificacion NUEVA. Si la base ya tiene `p`, este '
        'test ya no es el control de «nada se mueve».' % con_p)
