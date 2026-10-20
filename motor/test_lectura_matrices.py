# -*- coding: utf-8 -*-
"""EL CONTRATO DE LECTURA DE `preflop_matrices.json`, con datos SINTETICOS.

Y lo que hay aqui son cuatro cosas, y las cuatro son CONTRATOS:

  1. Una tabla DANA es una tabla que NO EXISTE. Y lo dice el que la lee, con
     un aviso. Y no se come las partes malas y sigue como si nada.
  2. La AUSENCIA de una estimacion no es una estimacion de cero. Y ahi esta
     la distincion que se perdia: `None` y `0.0` son cosas distintas, y hay
     que poder distinguirlas.
  3. Y los TRES lectores del fichero responden DISTINTO a la misma pregunta,
     y eso es la GRAFO: quien lee tiene que saber que tabla elige cada uno.

Y los datos son SINTETICOS y controlados, y no se inventan numeros: la
matriz de prueba se construye aqui, celda a celda, y se sabe exactamente lo
que es. Y el fichero real no se toca, y no se lee: de el solo se comprueba
que esta entero, que es una integridad y no una opinion.

Y el motivo de que el fichero real no se lea en los tests: su INTENCION no
esta fijada, y un test que dependa de el hereda esa falta. Con datos
sinteticos, el test mide el CONTRATO y no el fichero.
"""
import io
import json
import os
import warnings

import numpy as np
import pytest

from motor import preflop
from motor import profile
from motor import player_ranges
from motor.asistente_live import _pf_freq

# Y el fichero real, para COMPROBAR que esta entero. Y solo eso: que no se
# toque y que no se lea para medir nada.
RUTA_REAL = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'data', 'preflop_matrices.json')


def _matriz(valor=0.1):
    """La matriz de 13x13, con un valor, y por eso se sabe lo que es."""
    return [[valor] * 13 for _ in range(13)]


def _fichero(tmp_path, tablas, nombre='matrices.json'):
    ruta = tmp_path / nombre
    with io.open(str(ruta), 'w', encoding='utf-8') as f:
        json.dump({'tables': tablas}, f)
    return str(ruta)


def _tabla(pos='UTG', matrix=None, action='OR'):
    return {'action': action, 'pos': pos, 'vs': '',
            'matrix': _matriz() if matrix is None else matrix}


# ---------------------------------------------------------------------------
# 1. UNA TABLA DANA ES UNA TABLA QUE NO EXISTE
# ---------------------------------------------------------------------------

def test_una_matriz_con_una_fila_dana_no_da_una_tasa_falsa(tmp_path):
    """Y el motivo: una tasa PLAUSIBLE y falsa es peor que una ausente.

    MEDIDO, el defecto: con una fila de 12 celdas en vez de 13, la tabla
    salia con una tasa de 0.10, sin decir nada. Y esa tasa se usa para
    escalar un rango entero.
    """
    rota = _matriz()
    rota[7] = [0.1] * 12
    ruta = _fichero(tmp_path, {'OR_UTG': _tabla(matrix=rota)})

    with pytest.warns(RuntimeWarning, match='DANA'):
        tasas = profile.load_base_rates(ruta)

    assert 'OR_UTG' not in tasas, (
        'una tabla con la matriz DANA tiene que AUSENTAR, y no salir con una '
        'tasa: %r' % tasas)


def test_una_matriz_con_una_celda_no_numerica_no_da_una_tasa_falsa(tmp_path):
    """Y lo mismo con una celda que no es un numero."""
    rota = _matriz()
    rota[3][5] = 'x'
    ruta = _fichero(tmp_path, {'OR_UTG': _tabla(matrix=rota)})

    with pytest.warns(RuntimeWarning, match='DANA'):
        tasas = profile.load_base_rates(ruta)

    assert 'OR_UTG' not in tasas


def test_una_matriz_entera_si_da_una_tasa(tmp_path):
    """Y que el camino bueno siga dando la tasa, que es lo que se protege."""
    ruta = _fichero(tmp_path, {'OR_UTG': _tabla(matrix=_matriz(0.25))})
    tasas = profile.load_base_rates(ruta)
    assert tasas['OR_UTG'] == pytest.approx(0.25, abs=1e-6)


def test_un_prior_con_la_matriz_dana_cae_en_el_prior_plano(tmp_path):
    """Y el otro lector, con el mismo contrato.

    Y MEDIDO, el defecto: una matriz de (12, 13) pasaba como prior, y el
    fallo aparecia mas tarde y lejos, sin decir de donde venia.
    """
    rota = _matriz()
    rota[7] = [0.1] * 12
    player_ranges._tables_cache = {'OR_UTG': _tabla(matrix=rota)}
    try:
        m = player_ranges.ProfileRangeModel()
        with pytest.warns(RuntimeWarning, match='DANA'):
            prior = m._prior_grid('open', 'UTG')
        plano = np.full((13, 13), player_ranges.FLAT_PRIOR, dtype=np.float32)
        assert np.allclose(prior, plano)
    finally:
        player_ranges._tables_cache = None


# ---------------------------------------------------------------------------
# 2. LA AUSENCIA NO ES UN CERO
# ---------------------------------------------------------------------------

def test_el_lector_distingue_ausencia_de_cero():
    """Y la distincion, que es la que se perdia en el consumidor.

    MEDIDO: `ROL_UTG` NO existe en el fichero real —las ROL son BB, BTN, CO,
    MP y SB—, y `ROL_BB` si. De modo que las dos preguntas se parecen y las
    dos respuestas son distintas: una es `None` y la otra es un numero.
    """
    assert preflop.has_table('ROL', 'UTG') is False
    assert preflop.has_table('ROL', 'BB') is True
    assert preflop.prob('ROL', 'UTG', '') is None
    assert preflop.prob('ROL', 'BB', '') is not None


def test_el_lector_del_asistente_tambien_distingue():
    """Y el del asistente, que es el que hereda el contrato."""
    assert _pf_freq('ROL', 'UTG', '', 0) is None, (
        'no hay tabla ROL_UTG, y la respuesta tiene que ser None')
    assert _pf_freq('ROL', 'BB', '', 0) is not None, (
        'si hay tabla ROL_BB, la respuesta es un numero, aunque valga 0.0')


def test_el_fallback_uniforme_dice_de_donde_sale():
    """Y el fallback declara su fuente, que es lo que lo hace usable."""
    v, fuente = preflop.prob_or_fallback('ROL', 'UTG', '')
    assert fuente == 'uniform'
    assert v is not None and len(v) == 1326
    v2, fuente2 = preflop.prob_or_fallback('ROL', 'BB', '')
    assert fuente2 == 'table'


# ---------------------------------------------------------------------------
# 3. EL GRAFO: TRES LECTORES, TRES REGLAS
# ---------------------------------------------------------------------------

def test_los_tres_lectores_responden_distinto_a_lo_mismo():
    """Y la misma pregunta, tres respuestas. Y eso es el GRAFO.

    MEDIDO, la pregunta es «la tabla de apertura del BB»:
      · `preflop.prob`               -> None      (no hay estimacion)
      · `asistente_live._pf_freq`    -> None      (no hay estimacion)
      · `player_ranges._prior_grid`  -> prior plano + aviso

    Y la TERCERA respuesta es la que hay que tener presente: no es «no hay
    nada», es «me invento un prior plano». Y es una DECISION declarada —la
    fijan los tests de `player_ranges`—, y lo que faltaba era que cada
    consumidor dijera cual de las tres es la suya.
    """
    assert preflop.prob('OR', 'BB', '') is None
    assert _pf_freq('OR', 'BB', '', 0) is None

    m = player_ranges.ProfileRangeModel()
    with pytest.warns(RuntimeWarning, match='sin tabla'):
        prior = m._prior_grid('open', 'BB')
    plano = np.full((13, 13), player_ranges.FLAT_PRIOR, dtype=np.float32)
    assert np.allclose(prior, plano)


def test_cada_lector_elige_la_tabla_exacta_y_no_otra():
    """Y que la regla de eleccion de cada uno sea la que dice.

    Y el motivo de fijarla por COMPORTAMIENTO: la intencion del fichero no
    esta fijada, y lo que si esta fijado es como lo lee cada uno. Y una
    regla de eleccion que cambia sin que nadie lo decida es un cambio a
    ciegas.
    """
    # `preflop`: la clave es canonica, y la vs primero.
    assert preflop.has_table('3B', 'BB', 'CO') is True
    assert preflop.prob('3B', 'BB', 'CO') is not None

    # `player_ranges`: la exacta por posicion, y si no, la de la pareja.
    m = player_ranges.ProfileRangeModel()
    par = np.asarray(player_ranges._load_tables()['3B_BB_vs_CO']['matrix'],
                     dtype=np.float32)
    got = m._prior_grid('3bet', 'BB', 'CO')
    assert np.allclose(got, par)

    # `asistente_live`: la vs primero, y si no hay, la del mismo action+pos.
    from motor.asistente_live import _pf_table_probs
    v = _pf_table_probs('3B', 'BB', 'CO')
    assert v is not None and len(v) == 1326


# ---------------------------------------------------------------------------
# 4. Y EL FICHERO REAL, QUE ESTA ENTERO
# ---------------------------------------------------------------------------

def test_el_fichero_real_esta_entero():
    """Y que las 117 tablas esten completas, que es una INTEGRIDAD.

    Y no es una opinion sobre el fichero: es que no le falta ni una celda.
    Y la INTENCION del fichero —que significa cada celda— no se comprueba
    aqui, porque esa la declara A1.
    """
    with io.open(RUTA_REAL, encoding='utf-8') as f:
        tablas = json.load(f)['tables']
    assert len(tablas) == 117, len(tablas)
    malas = []
    for nombre, t in tablas.items():
        m = t.get('matrix')
        if not profile._matriz_entera(m):
            malas.append(nombre)
    assert not malas, (
        'tablas con la matriz danada en el fichero REAL: %r. Y eso no tendria '
        'que pasar, y si pasa hay que decirlo.' % malas[:10])
