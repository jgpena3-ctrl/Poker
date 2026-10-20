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
