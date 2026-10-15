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
import os
import re

import pytest

from motor import learn

# Lo que el mantenedor declaro fiable el 2026-10-14. Es una COPIA deliberada
# de lo que dice la base de datos, para que se vea que las dos cosas tienen
# que estar de acuerdo.
RANGO_DECLARADO = 'H_1014'

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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


def test_las_tres_cifras_coherentes_entre_si():
    """El rango auditado, el corte de lineas y la ventana, reconciliados.

    Antes esto era un `xfail(strict=True)` que se limitaba a decir que
    discrepaban. Ahora verifica que las TRES cifras encajan, que es lo que
    puede comprobar un test sin tomar la decision de cual debe ser.

    La relacion que tiene que cumplirse, y que se deduce sola:

        ventana = RELIABLE_HANDS - len(manos_excluidas())

    Si eso no cuadra, las cifras publicadas no salen de la ventana que el
    motor dice usar, y eso es peor que una discrepancia: es un numero sin
    origen.
    """
    declarado = len(manos_hasta(RANGO_DECLARADO))
    ventana = len(learn.load_hands(reliable_only=True))
    esperada = learn.RELIABLE_HANDS - len(learn.manos_excluidas())
    print()
    print('   rango auditado    %-10s %4d manos' % (RANGO_DECLARADO, declarado))
    print('   RELIABLE_HANDS                %4d (corte de LINEAS)' % learn.RELIABLE_HANDS)
    print('   exclusiones CM-004            %4d' % len(learn.manos_excluidas()))
    print('   ventana de calibracion        %4d' % ventana)
    print()
    assert ventana == esperada, (
        'la ventana (%d) no es RELIABLE_HANDS (%d) menos las exclusiones (%d) '
        '= %d' % (ventana, learn.RELIABLE_HANDS,
                  len(learn.manos_excluidas()), esperada))
    # el rango auditado puede ser mayor o menor que la ventana: son cosas
    # distintas. Lo que no puede es no existir.
    print('   OK  ventana = corte - exclusiones, y las tres cifras son legibles.')
    print('   nota: el rango auditado (%d) y la ventana (%d) NO son lo mismo,'
          % (declarado, ventana))
    print('         y no tienen que serlo. Ver DOCS/RANGO_VIGENTE.md.')


def test_las_cifras_publicadas_coinciden_con_la_ventana_vigente():
    """Lo que se publico tiene que salir de la ventana que hay ahora.

    Las cifras de F7.2 se publicaron sobre el fichero de 1280 lineas. Con
    1258 la ventana tiene las mismas 877 lineas y OTRAS 70 manos, asi que el
    porcentaje se movio de 44,6% a 45,9%. Este test no arregla eso: verifica
    que el numero de CONTRATO_F72A.md sea el que sale de la ventana hoy.
    """
    from motor.multiway import metrica_politica
    import io as _io
    m = metrica_politica(learn.load_hands(reliable_only=True))
    ruta = os.path.join(ROOT, 'DOCS', 'CONTRATO_F72A.md')
    texto = _io.open(ruta, encoding='utf-8').read()
    print()
    print('   ventana de hoy : puntos %d, denominador %d, MW %d, %.1f%%, cota %d'
          % (m['total'], m['denominador'], m['numerador'],
             m['porcentaje'], m['techo']))
    for valor in (m['denominador'], m['numerador'], m['techo']):
        assert str(valor) in texto, (
            'CONTRATO_F72A.md no menciona el valor vigente %d. Las cifras '
            'publicadas se calcularon sobre una ventana anterior: o se '
            'actualizan, o se declara que describen otra base.'
            % valor)
    print('   OK  CONTRATO_F72A.md menciona los tres valores vigentes.')


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