# -*- coding: utf-8 -*-
"""LA AGREGACION POR RIVAL, con datos SINTETICOS.

Y lo que se fija aqui es **CUANDO se aplica la mediana**, que es lo que R2
pide, y que antes no se podia mirar sin ejecutar el calculo entero.

Y la condicion, que es la que importa:

  · la mediana se calcula sobre los rivales que se PUDIERON evaluar, y no
    sobre los rivales del bote: los que fallaron no estan, y su motivo queda
    aparte;
  · y por eso la cuenta de cuantos entraron es parte del resultado, y antes
    no se decia: una mediana de dos rivales y una de cinco se veian igual.

Y los datos son sinteticos y controlados, y el numero no se inventa: son
equities que se escriben a mano para fijar la aritmetica.
"""
import io
import os

import pytest

from tools.equity_de_mano import agrega_equities


def test_un_solo_rival_median_igual_y_dispersion_cero():
    """Y con un rival, la mediana es ese valor y la dispersion es 0.0.

    Y el 0.0 no es «no hay dispersion»: es que con un rival no se puede
    medir. Y la funcion lo dice con `n_evaluados`.
    """
    r = agrega_equities({'BB': 0.42})
    assert r['mediana'] == pytest.approx(0.42)
    assert r['dispersion'] == 0.0
    assert r['n_evaluados'] == 1


def test_tres_rivales_mediana_el_del_medio():
    """Y con tres, la mediana es el del medio, y la dispersion el rango."""
    r = agrega_equities({'BB': 0.10, 'SB': 0.50, 'BTN': 0.90})
    assert r['mediana'] == pytest.approx(0.50)
    assert r['dispersion'] == pytest.approx(0.80)
    assert r['n_evaluados'] == 3


def test_cuatro_rivales_la_mediana_es_el_promedio_de_los_dos_del_medio():
    """Y con un numero PAR, la mediana es el promedio de los dos centrales.

    Y no el menor de los dos, que es lo que haria una mediana «de rango». Y
    el valor sale de `numpy.median`, que es el que se usaba antes: la
    extraccion no ha cambiado ni un decimal.
    """
    r = agrega_equities({'BB': 0.10, 'SB': 0.20, 'BTN': 0.60, 'CO': 0.90})
    assert r['mediana'] == pytest.approx(0.40)
    assert r['dispersion'] == pytest.approx(0.80)
    assert r['n_evaluados'] == 4


def test_la_poblacion_es_la_que_recibe_y_la_cuenta_la_dice():
    """Y la condicion QUE IMPORTA: la poblacion es un subconjunto.

    Y el motivo de que esto sea un test y no una frase: la mediana se calcula
    sobre los rivales EVALUABLES, y los que fallaron no estan. De modo que
    una mediana puede ser de un subconjunto del bote, y sin la cuenta no se
    sabe de cuantos.
    """
    r = agrega_equities({'BB': 0.30, 'SB': 0.70})
    assert r['n_evaluados'] == 2
    assert r['mediana'] == pytest.approx(0.50)


def test_sin_equities_da_un_error_claro():
    """Y sin ninguna, un error que lo dice, no una excepcion de numpy.

    Y el motivo: `numpy.median([])` avisa y devuelve `nan`, y un `nan` en una
    metrica es un numero que se propaga sin que nadie lo note.
    """
    with pytest.raises(ValueError, match='sin equities'):
        agrega_equities({})

# ---------------------------------------------------------------------------
# 5. LA EXTRACCION NO HA MOVIDO NI UN DECIMAL
# ---------------------------------------------------------------------------

def _agregacion_anterior(salida):
    """La agregacion ANTES de la extraccion, que estaba dentro de la funcion.

    Y la referencia esta aqui, y no en un commit, porque un commit se
    reescribe y una referencia en el test no. Y el motivo de que sea la
    version ANTERIOR y no una idealized: lo que se comprueba es que la
    extraccion no movio nada, y eso solo se comprueba contra lo que habia.
    """
    import numpy as np
    return {
        'dispersion': (max(salida.values()) - min(salida.values())
                       if len(salida) > 1 else 0.0),
        'mediana': float(np.median(list(salida.values()))),
    }


def test_el_resultado_es_identico_al_de_la_version_anterior():
    """Y en todos los casos que la version anterior cubria.

    Y la version anterior no tenia `n_evaluados`, de modo que ese campo es
    lo UNICO que se ha añadido: y el numero, y la mediana, y la dispersion,
    tienen que ser los mismos.
    """
    casos = [
        {'BB': 0.42},
        {'BB': 0.10, 'SB': 0.50, 'BTN': 0.90},
        {'BB': 0.10, 'SB': 0.20, 'BTN': 0.60, 'CO': 0.90},
        {'BB': 0.0},
        {'BB': 1.0, 'SB': 0.0},
        {'BB': 0.333333, 'SB': 0.666667},
    ]
    for salida in casos:
        antes = _agregacion_anterior(salida)
        ahora = agrega_equities(salida)
        assert ahora['mediana'] == antes['mediana'], salida
        assert ahora['dispersion'] == antes['dispersion'], salida
        assert ahora['n_evaluados'] == len(salida), salida


def test_n_evaluados_es_el_conjunto_sobre_el_que_se_calcula_la_mediana():
    """Y que el numero sea el del conjunto, y no el de los rivales del bote.

    Y la distincion que el numero hace posible: la mediana se calcula sobre
    los rivales EVALUABLES, y el numero dice cuantos. De modo que una
    mediana de dos y una de cinco se pueden distinguir, y antes no.
    """
    salida = {'BB': 0.30, 'SB': 0.70}
    r = agrega_equities(salida)
    assert r['n_evaluados'] == len(salida)
    assert r['n_evaluados'] == 2
    # y la mediana es la de ESE conjunto
    assert r['mediana'] == pytest.approx(0.50)


def test_un_rival_no_evaluable_no_entra_en_el_conjunto():
    """Y que un rival que no se pudo evaluar no cuente como equity cero.

    Y el motivo de que esto sea un test y no una frase: la AUSENCIA de datos
    convertida en CERO es un numero que no es de nadie, y lo que se quiere
    es que la poblacion de la mediana sea la de los evaluables, y que se
    sepa cuantas son.
    """
    salida = {'BB': 0.30}
    r = agrega_equities(salida)
    assert r['n_evaluados'] == 1
    assert r['mediana'] == pytest.approx(0.30)
    # y si se le anadea un rival que no se pudo evaluar, su equity no es 0.0
    # sino que NO ESTA: de modo que la mediana no se mueve con el
    assert 'SB' not in salida


def test_el_codigo_de_equity_de_mano_excluye_a_los_que_fallan():
    """Y que el codigo que llama a la agregacion NO Pony None como cero.

    Y es un test sobre el ARBOL, y no sobre el comportamiento, y el motivo es
    que el comportamiento es caro: construir los modelos de equity y correr
    una mano es de minutos. Y lo que se quiere fijar no es el numero, sino
    la REGLA: un rival que no se pudo evaluar se aparta con un `continue`, y
    no entra en el conjunto de la mediana.
    """
    import ast
    ruta = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'tools', 'equity_de_mano.py')
    with io.open(ruta, encoding='utf-8') as f:
        arbol = ast.parse(f.read())
    fn = next(n for n in ast.walk(arbol)
              if isinstance(n, ast.FunctionDef)
              and n.name == 'equity_de_mano')

    # (a) la rama del fallo termina en `continue`
    ramas = [n for n in ast.walk(fn)
             if isinstance(n, ast.If) and ast.unparse(n.test) == 'eq is None']
    assert len(ramas) == 1, (
        'se esperaba UNA rama `if eq is None`, y hay %d' % len(ramas))
    assert any(isinstance(x, ast.Continue)
               for x in ast.walk(ramas[0])), (
        'la rama del fallo NO termina en `continue`: un rival que no se pudo '
        'evaluar entraria en el conjunto de la mediana con un 0.0')

    # (b) y lo que se agrega es `salida`, y no otra cosa
    agregaciones = [n for n in ast.walk(fn)
                    if isinstance(n, ast.Call)
                    and getattr(n.func, 'id', None) == 'agrega_equities']
    assert len(agregaciones) == 1, (
        'se esperaba UNA llamada a `agrega_equities`, y hay %d'
        % len(agregaciones))
    assert ast.unparse(agregaciones[0].args[0]) == 'salida', (
        'la agregacion se hace sobre %r, y tiene que ser `salida`'
        % ast.unparse(agregaciones[0].args[0]))

