# -*- coding: utf-8 -*-
"""El rango que se declara fiable tiene que estar DECLARADO en el motor.

No es cosmetica. `hands_db.jsonl` se ha editado a mano y el rango
"H_0001..H_1014, los datos minimamente fiables" vive en un mensaje y en
`RANGO_DECLARADO`, no en `learn.py`. Mientras sea asi:

  - las cifras publicadas se calculan sobre una ventana que ya no es la que
    el mantenedor considera fiable,
  - y el motor no tiene forma de saber que existe un rango fiable nuevo.

Un rango que solo existe en un chat no es un rango. Y cambiar
`RELIABLE_HANDS` sin recalcular las cifras y regenerar los derivados seria
publicar numeros que no salen de la ventana que se dice usar, que es
exactamente el fallo que el proyecto lleva cinco bloques evitando.
"""
import re

import pytest

from motor import learn

# Lo que el mantenedor declaro fiable el 2026-10-14. Es una COPIA deliberada
# de lo que dice la base de datos, para que se vea que las dos cosas tienen
# que estar de acuerdo.
RANGO_DECLARADO = 'H_1014'

MOTIVO = (
    'el rango declarado (%s = %d manos) y el del motor (%d) no coinciden. '
    'Cambiarlo es una DECISION: recalcula todas las cifras de F7.2 y obliga a '
    'regenerar los derivados. Ver DOCS/HALLZGOS_H0001_H1014.md.'
    % (RANGO_DECLARADO, 991, learn.RELIABLE_HANDS))


def _num(hid):
    return int(re.match(r'H_(\d+)$', hid).group(1))


def manos_hasta(hasta):
    return [h for h in learn.load_hands(reliable_only=False)
            if _num(h['hand_id']) <= _num(hasta)]


@pytest.mark.xfail(reason=MOTIVO, strict=True)
def test_el_rango_fiable_esta_declarado_en_el_motor():
    """`RELIABLE_HANDS` tiene que ser el rango que el mantenedor declara.

    Hoy son 900 y el rango declarado es H_1014. Estan desalineados, y este
    test es el que lo dice. Con `strict=True`, resolverlo —cambiando
    `RELIABLE_HANDS`, recalculando las cifras y regenerando los derivados—
    hace que el test pase y obliga a quitar la marca.
    """
    declarado = len(manos_hasta(RANGO_DECLARADO))
    ventana = len(learn.load_hands(reliable_only=True))
    print()
    print('   rango declarado   %-10s %d manos'
          % (RANGO_DECLARADO, declarado))
    print('   RELIABLE_HANDS              %d' % learn.RELIABLE_HANDS)
    print('   exclusiones CM-004          %d' % len(learn.manos_excluidas()))
    print('   ventana real                %d' % ventana)
    print()
    assert learn.RELIABLE_HANDS == _num(RANGO_DECLARADO), (
        'las cifras publicadas salen de %d manos y el rango declarado tiene '
        '%d' % (ventana, declarado))
    assert ventana == declarado, (
        'la ventana excluye %d manos del rango declarado; si es a proposito, '
        'la exclusion necesita su motivo escrito'
        % (declarado - ventana))


def test_el_rango_declarado_apunta_a_manos_que_existen():
    """Lo que SI se puede comprobar sin tomar ninguna decision.

    Que `H_1014` exista de verdad y que el rango no apunte al vacio. Un
    rango declarado mal escrito daria 0 manos y nadie se enteraria.
    """
    declaradas = [h['hand_id'] for h in manos_hasta(RANGO_DECLARADO)]
    assert declaradas, 'el rango declarado no contiene ninguna mano'
    assert declaradas[-1] == RANGO_DECLARADO, (
        'el rango declarado termina en %s, no en %s'
        % (declaradas[-1], RANGO_DECLARADO))
    assert all(_num(a) < _num(b)
               for a, b in zip(declaradas, declaradas[1:])), (
                   'el rango declarado sale de orden')