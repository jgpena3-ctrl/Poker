# -*- coding: utf-8 -*-
"""EL AMBITO DE «ESCRITO Y SIN PROBAR», uno por test.

Y por que esta aqui y no en los ficheros: el ambito tiene que ABRIRSE solo.
Si lo abriera cada test que lo usa, bastaria con que uno se olvidara, y el
que se olvidara tendria `sin_probar()` sin registro — que devuelve la lista
vacia, o sea VERDE. Un invariante que se desactiva por olvido y no dice
nada es peor que no tenerlo.

Y `cerrar_ambito()` va en el `finally` por lo mismo, en espejo: sin el, el
test siguiente hereda lo que dejo este, y con un solo test que deje algo a
pendientes todos los de produccion caen por lo que hizo un test que no va
con ellos.

MEDIDO, que es lo que obliga a hacerlo asi: con el registro global de
modulo, un test que dejaba pendiente lo hacia caer al siguiente, y el
siguiente era de otro fichero. Un invariante que depende del orden de los
tests es una carrera con pasos extra.

Y lo que NO hace este fichero: nada de su. No recoge tests, no cambia
filtros, no toca la red. Solo abre y cierra un ambito.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ejecutar_pytest as ep                             # noqa: E402


@pytest.fixture(autouse=True)
def _ambito_de_lo_escrito():
    ep.abrir_ambito()
    try:
        yield
    finally:
        ep.cerrar_ambito()
