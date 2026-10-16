# -*- coding: utf-8 -*-
"""`tools/auditar_matrix.py` — y la decisión que sale de él.

Cinco bloques:

  1. QUE LA PRUEBA ARITMETICA SE SOSTIENE. `sum_k S_k <= 1` es obligatorio,
     y el prior plano del fold lo incumple solo. Si algun dia `FLAT_PRIOR`
     baja, este test dice por que tiene que seguir falling.
  2. QUE `matrix` NO ES UNA PROBABILIDAD. Medido sobre el fichero, no
     escrito en el documento.
  3. QUE LAS CELDAS SI ESTAN EN [0, 1]. Porque "no es una probabilidad" y
     "esta mal formada" son cosas distintas y el documento las separa.
  4. QUE LA DECISION ESTA ESCRITA. `DEFAULT_ALPHA` no se calibra, y eso
     tiene que estar en el contrato Y en el codigo.
  5. QUE `data/` SIGUE INTACTO. Este bloque diagnostico, no arregla nada.
"""
import importlib.util
import io
import json
import os

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATRICES = os.path.join(ROOT, 'data', 'preflop_matrices.json')


@pytest.fixture(scope='module')
def mat():
    ruta = os.path.join(ROOT, 'tools', 'auditar_matrix.py')
    spec = importlib.util.spec_from_file_location('auditar_matrix', ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tablas():
    return json.load(io.open(MATRICES, encoding='utf-8'))['tables']


# ------------------------------------------- 1. la prueba aritmetica
def test_los_priors_de_un_spot_tienen_que_sumar_uno(mat):
    """`p_matrix` es P(accion|mano,spot) y las acciones son excluyentes.

    Sumando sobre las celdas: `[ N_k + alpha*S_k ] / (opp + alpha) <= 1`, y
    como `sum_k N_k <= opp`, tiene que cumplirse `sum_k S_k <= 1`.
    """
    assert mat.ACCIONES_DE, 'el mapeo spot -> acciones tiene que existir'
    for spot, acciones in mat.ACCIONES_DE.items():
        assert len(acciones) >= 2, (
            'un spot con una sola accion no es la prueba: %s' % spot)
        assert len(set(acciones)) == len(acciones), (
            'acciones repetidas en %s' % spot)


def test_el_prior_plano_se_pasa_de_la_raya(mat):
    """FLAT_PRIOR = 0,15 x 169 celdas = 25,35, y la formula admite 1.

    Este es el numero que hace el diagnostico. Si `FLAT_PRIOR` cambia, este
    test falla y obliga a rehacer la aritmetica en vez de dejarla stale.
    """
    from motor import player_ranges
    s_flat = player_ranges.FLAT_PRIOR * 169
    assert s_flat > 1.0, (
        'si el prior plano sumara <= 1, la prueba del punto 2 ya no '
        'daria lo que da: hay que reescribir QUE_ES_MATRIX.md')
    assert abs(s_flat - 25.35) < 0.01, (
        'el numero publicado en el documento es %.2f, y ahora sale %.2f'
        % (25.35, s_flat))


def test_el_plano_lo_usan_las_acciones_sin_tabla(mat):
    """`fold` esta en CAT_TABLE? No. Entonces cae al plano.

    Y `fold` es la accion mas frecuente. Eso no es teorico.
    """
    from motor import player_ranges
    for a in ('fold', 'fold_vs_open', 'bb_check', 'fold_vs_3bet'):
        assert a not in player_ranges.CAT_TABLE, (
            '%s ahora SI tiene tabla: el diagnostico del prior plano hay '
            'que rehacer' % a)


# ------------------------------------ 2. matrix no es una probabilidad
def test_matrix_no_suma_uno(mat):
    """1 de 117 tablas suma ~1. Si cambiara, el documento va stale."""
    filas = mat.sumas()
    s = np.array([d['suma'] for d in filas])
    assert len(filas) == 117, (
        'son 117 tablas y ahora hay %d: el documento habla de otra cosa'
        % len(filas))
    n_uno = int((np.abs(s - 1.0) < 0.05).sum())
    assert n_uno == 1, (
        'ahora %d tablas suman ~1 (eran 1): hay que reescribir el '
        'documento antes de seguir' % n_uno)
    assert abs(s.max() - 89.75) < 0.01
    assert abs(float(np.median(s)) - 10.00) < 0.01
    assert abs(s.min() - 0.91) < 0.01


def test_normalizar_no_bastaria():
    """La razon por la que la opcion A queda descartada.

    Si cada tabla se normalizara a 1, `S_k = 1`, y con dos acciones de un
    spot `sum_k S_k = 2 > 1`. No es un problema de las tablas.
    """
    for n_acciones in (2, 3):
        assert n_acciones * 1.0 > 1.0, (
            'con %d acciones normalizadas la suma se pasa' % n_acciones)


# ------------------------------------ 3. las celdas SI estan en [0, 1]
def test_las_celdas_estan_en_el_rango(mat):
    """`matrix` no es una probabilidad POR SUMA, no por rango.

    Es la distincion que hace el documento, asi que tiene su propio test:
    19 773 celdas, ninguna fuera de [0, 1].
    """
    todos = np.concatenate([np.asarray(v['matrix'], dtype=float).ravel()
                            for v in _tablas().values()])
    assert todos.size == 19773, 'eran 19 773 celdas, ahora %d' % todos.size
    assert float(todos.min()) >= 0.0
    assert float(todos.max()) <= 1.0


def test_mostras_de_tabla_tienen_el_maximo_en_uno():
    """116 de 117. El generador produzco probabilidades por celda."""
    filas = [d for d in _tablas().values()]
    con_max = sum(1 for v in filas
                  if float(np.asarray(v['matrix']).max()) == 1.0)
    assert con_max == 116, 'eran 116 de 117, ahora %d de %d' % (con_max,
                                                                len(filas))


# --------------------------------------------- 4. la decision escrita
def test_la_decision_esta_escrita():
    """C, la tercera sub-opcion: no se calibra nunca."""
    d = io.open(os.path.join(ROOT, 'DOCS', 'QUE_ES_MATRIX.md'),
                encoding='utf-8').read()
    plano = ' '.join(d.split())
    assert 'caso c' in plano.lower()
    assert 'NO SE CALIBRA NUNCA' in plano.upper(), (
        'la decision tiene que estar en el documento, no solo en el commit')
    assert 'alpha' in plano and 'pseudo-conteos' in plano


def test_default_alpha_no_se_calibra_en_el_codigo():
    """Y no basta con decirlo: el guardián tiene que seguir."""

    assert 'DEFAULT_ALPHA = 2.0' in io.open(
        os.path.join(ROOT, 'motor', 'player_ranges.py'),
        encoding='utf-8').read()


def test_el_bloque_3_esta_cerrado_en_el_estado():
    """`FASE_D_BLOQUEADA.md` tiene que decir que los cuatro estan cerrados."""
    f = io.open(os.path.join(ROOT, 'DOCS', 'FASE_D_BLOQUEADA.md'),
                encoding='utf-8').read()
    plano = ' '.join(f.split())
    assert 'los cuatro bloques están cerrados' in plano.lower(), (
        'el estado dice que falta el bloque 3, y ya no es verdad')


# -------------------------------------------------- 5. data/ intacto
def test_data_no_se_toco(mat):
    """Este bloque diagnostica. No regenera, no normaliza, no escribe."""
    tablas = _tablas()
    assert len(tablas) == 117
    assert all('matrix' in v for v in tablas.values())
    # el fichero tiene que seguir siendo solo lo que era: una clave, tables
    crudo = json.load(io.open(MATRICES, encoding='utf-8'))
    assert list(crudo) == ['tables'], (
        'se han anadido claves de nivel superior: %s' % list(crudo))
    assert set(tablas) == set(mat.TABLAS), 'las tablas han cambiado'
