# -*- coding: utf-8 -*-
"""Lo que `revision_2` §2, §3 y §4 pidio, ya cerrado.

  §2  El spot `no_raise` era INALCANZABLE: `villano_del_corte()` exigia una
      subida previa y `mano_del_spot()` devuelve `no_raise` justamente cuando
      no hay ninguna. Medido: 6 de 23 cortes preflop de validacion.

  §3  "Mas alpha es menos probabilidad de cualquier accion, porque el prior
      pesa menos" es al reves.

  §4  El sigma del docstring del motor estaba desactualizado (0,09 por
      0,0099), y los pesos del rango solo se validaban en la suma.
"""
import importlib.util
import io
import os

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def ins():
    ruta = os.path.join(ROOT, 'tools', 'equity_preflop_observables.py')
    spec = importlib.util.spec_from_file_location('eqpobs', ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope='module')
def he():
    from motor import hand_evaluator
    return hand_evaluator


# ------------------------------------------------- §2 el spot inalcanzable
def _mano(acciones, hero='SB'):
    # los NOMBRES importan: illano_del_corte busca por puesto y luego
    # saca el nombre del jugador. Una mano sin nombres devuelve (None, pos).
    return {'players': [{'pos': hero, 'name': 'Jarduan'},
                        {'pos': 'BB', 'name': 'DominoSaurio'},
                        {'pos': 'MP', 'name': 'Juanmabm'}],
            'streets': {'preflop': {'actions': acciones}}}


def test_no_raise_tiene_rival(ins):
    """El heroe abre sin subida previa: hay rival, es el siguiente en actuar.

    Antes devolvia None y la mano se caia entera. Eso no es descartar manos
    sin decision: es descartar manos CUYA decision si tiene rival y quedarse
    sin nombrarlo.
    """
    h = _mano([{'pos': 'SB', 'action': 'r'},        # el hero abre (idx 0)
               {'pos': 'BB', 'action': 'f'}])
    assert ins.mano_del_spot(h, 'preflop', 'SB', 0) == 'no_raise'
    nombre, vpos = ins.villano_del_corte(h, 'SB', 'preflop', 0)
    assert nombre is not None, (
        'un no_raise SI tiene rival: el primero que actua despues del hero')
    assert vpos == 'BB'


def test_con_subida_previa_manda_el_que_subio(ins):
    """El rival sigue siendo quien obliga, no el siguiente en hablar."""
    h = _mano([{'pos': 'MP', 'action': 'r'},
               {'pos': 'SB', 'action': 'c'},       # idx 1
               {'pos': 'BB', 'action': 'f'}])
    nombre, vpos = ins.villano_del_corte(h, 'SB', 'preflop', 1)
    assert vpos == 'MP', 'con subida previa manda el ultimo que subio'
    assert nombre == 'Juanmabm'


def test_el_rango_de_no_raise_se_usa_de_verdad(ins):
    """Un rango declarado y nunca consultado es documentacion que miente."""
    assert 'no_raise' in ins.ACCIONES_SPOT
    assert len(ins.ACCIONES_SPOT['no_raise']) == 2
    src = io.open(os.path.join(ROOT, 'tools',
                               'equity_preflop_observables.py'),
                  encoding='utf-8').read()
    i = src.index('def rango_del_villano')
    assert 'ACCIONES_SPOT.get(spot)' in src[i:i + 400]


def test_la_poblacion_es_auditable(ins):
    """R2 §2 pide el recuento por spot ANTES de cada filtro. Sin eso, una
    cifra de la que se pierde el origen."""
    src = io.open(os.path.join(ROOT, 'tools',
                               'equity_preflop_observables.py'),
                  encoding='utf-8').read()
    assert 'sp_cortes' in src, 'hay que contar por spot antes de filtrar'
    assert '--solo-recaudo' in src, (
        'sin una salida de solo recuento, auditar la poblacion cuesta 3 h '
        'de calculo')
    # y el recuento es ANTES de exigir villano
    # dentro del CUERPO de main(), no en los docstrings
    cuerpo = src[src.index('def main():'):]
    i = cuerpo.index('sp_cortes[spot] += 1')
    j = cuerpo.index('villano_del_corte(h, hero, calle, idx)')
    assert i < j, 'el recuento por spot tiene que ir antes del filtro'


# ----------------------------------------------------- §3 la monotonia
def test_la_afirmacion_de_monotonia_esta_corregida():
    """Dice al reves: en p_k = (N_k + a*S_k)/(opp+a) el prior pesa MAS."""
    d = io.open(os.path.join(ROOT, 'DOCS', 'QUE_ES_MATRIX.md'),
                encoding='utf-8').read()
    # la condicion analitica, que es lo que hace falta para deducir
    assert 'α·(S − 1) ≤ opp − N' in d or \
        'S(c) ≤ 1' in d, (
        'la condicion celda a celda es lo que sostiene la afirmacion')
    assert 'Deducida' in d and 'Medida, no deducida' in d, (
        'las dos tiene que quedar separadas: confundir eso es el error')
    assert 'No hay regla general' in d, (
        'para cada accion no hay regla general, y hay que decirlo')
    assert '1,30' in d, (
        'con las tablas de posicion no_raise llega a S = 1,30, y eso es lo '
        'que hace que la afirmacion universal sea mas fuerte que la '
        'evidencia: tiene que estar escrito')


def test_la_coherencia_para_todo_alpha_es_medida_no_deducida():
    """Haria falta tambien S(c) <= 1, y las tablas no suman 1."""
    d = io.open(os.path.join(ROOT, 'DOCS', 'QUE_ES_MATRIX.md'),
                encoding='utf-8').read()
    assert 'medición sobre estos datos' in d, (
        'presentar como deducido lo que es medido es el error de este bloque')
    assert 'no suman 1' in d
    assert 'si S(c) > 1' in d or 'solo mientras' in d, (
        'con S > 1 la coherencia depende de alpha, y hay que decirlo')


def test_no_queda_la_tabla_de_la_medicion_del_bug():
    """La tabla con 1,1231 venia de sumar el prior crudo del fold."""
    d = io.open(os.path.join(ROOT, 'DOCS', 'QUE_ES_MATRIX.md'),
                encoding='utf-8').read()
    assert '1,1231' not in d, (
        'queda la tabla de la medicion con el bug del fold: mide algo que el '
        'motor no produce')


# ------------------------------------------------------- §4 el contrato
def test_el_sigma_del_docstring_es_el_del_estimador_que_corre(he):
    """0,09 era de otro esquema. `revision_2` §4."""
    src = io.open(os.path.join(ROOT, 'motor', 'hand_evaluator.py'),
                  encoding='utf-8').read()
    i = src.index('def equity_preflop_rango')
    doc = src[i:src.index('"""', src.index('"""', i) + 3) + 3]
    assert '0,0099' in doc, 'el sigma del estimador actual tiene que estar'
    # el 0,09 PUEDE quedar, pero solo marcado como del esquema anterior.
    # Ojo: '0,0099' contiene '0,09' como subcadena, asi que la comprobacion
    # tiene que mirar la frase, no la subcadena.
    assert '0,09 que aparecia antes' in doc, (
        'el 0,09 del esquema anterior tiene que quedar MARCADO como tal: '
        'si no, se lee como propiedad del estimador que corre')
    assert 'esquema' in doc.lower() and 'anterior' in doc.lower()


def test_los_pesos_se_validan_uno_a_uno(he):
    """Una suma positiva NO garantiza que todos sean finitos y no negativos,
    que es lo que `rng.choice(p=...)` exige."""
    w = np.full(1326, 1.0 / 1326)
    w[7] = -0.001          # suma sigue positiva
    with pytest.raises(ValueError) as e:
        he.equity_preflop_rango(['As', 'Kd'], w, n_combos=2)
    assert 'negativo' in str(e.value) or 'no finito' in str(e.value)

    w2 = np.full(1326, 1.0 / 1326)
    w2[9] = np.inf          # suma positiva: +inf
    with pytest.raises(ValueError):
        he.equity_preflop_rango(['As', 'Kd'], w2, n_combos=2)

    w3 = np.full(1326, 1.0 / 1326)
    w3[11] = np.nan
    with pytest.raises(ValueError):
        he.equity_preflop_rango(['As', 'Kd'], w3, n_combos=2)


def test_una_suma_negativa_no_pasa(he):
    w = np.full(1326, 1.0 / 1326)
    w[3] = -2.0
    with pytest.raises(ValueError):
        he.equity_preflop_rango(['As', 'Kd'], w, n_combos=2)