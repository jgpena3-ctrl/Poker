# -*- coding: utf-8 -*-
"""`tools/auditar_auc.py` — el AUC y, sobre todo, cómo se mide su error.

Cuatro bloques:

  1. QUE EL AUC ES EL QUE DICE. Con datos sinteticos donde se sabe la
     respuesta.
  2. QUE LOS DOS METODOS COINCIDEN. El bootstrap y las permutaciones
     tienen que dar el mismo veredicto, o no se publica ninguno.
  3. QUE EL p DE PERMUTACIONES ESTA BIEN. El bug que hizo falta para que
     este modulo existiera: con AUC = 1,0 el p tiene que ser diminuto.
  4. QUE LAS REGLAS DEL CONTRATO SE CUMPLEN. Reparto excluido y contado,
     y solo validacion.
"""
import importlib.util
import io
import os

import numpy as np
import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def auc():
    ruta = os.path.join(ROOT, 'tools', 'auditar_auc.py')
    spec = importlib.util.spec_from_file_location('auditar_auc', ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------ 1. el AUC
def test_auc_con_separacion_perfecta(auc):
    pos = [0.80 + 0.01 * i for i in range(8)]
    neg = [0.20 + 0.01 * i for i in range(17)]
    assert auc.auc_de(pos, neg) == 1.0


def test_auc_sin_separacion_va_a_cinco_decimas(auc):
    """Los MISMOS valores, repartidos al azar: el AUC cae a ~0,5.

    Eso demuestra que el AUC ve el ORDEN y no la escala: el conjunto de
    valores es identico al caso de separacion perfecta, y lo unico que
    cambia es quien quedo arriba.
    """
    rng = np.random.default_rng(5)
    pos = [0.8 + 0.01 * i for i in range(8)]
    neg = [0.2 + 0.01 * i for i in range(17)]
    assert auc.auc_de(pos, neg) == 1.0
    todos = pos + neg
    rng.shuffle(todos)
    p2, n2 = todos[:8], todos[8:]
    a = auc.auc_de(p2, n2)
    assert abs(a - 0.5) < 0.15, 'barajado deberia caer a ~0,5: %r' % a


def test_auc_rapido_coincide_con_el_lento(auc):
    """La version con rangos tiene que dar lo mismo que la doble."""
    rng = np.random.default_rng(3)
    for _ in range(5):
        n1, n2 = 7, 11
        v = rng.normal(size=n1 + n2).round(1)
        et = np.concatenate([np.ones(n1), np.zeros(n2)]).astype(int)
        lento = auc.auc_de(v[et == 1].tolist(), v[et == 0].tolist())
        rapido = auc.auc_rapido(et, v)
        assert abs(lento - rapido) < 1e-9


def test_auc_sin_una_clase_no_esta_definido(auc):
    assert auc.auc_de([0.5], []) is None
    assert auc.auc_de([], [0.5]) is None


# ------------------------------------- 2. los dos metodos coinciden
def test_el_bootstrap_y_las_permutaciones_coinciden(auc):
    """Si uno dice que hay efecto y el otro que no, no se publica nada.

    Es la condicion del contrato §10.
    """
    rng = np.random.default_rng(11)
    pos = list(rng.normal(1.0, 0.4, 15).round(3))
    neg = list(rng.normal(0.0, 0.4, 22).round(3))
    lo, hi = auc.ic_bootstrap(pos, neg, n=2000)
    p, _ge, _n = auc.p_permutaciones(pos, neg, n=2000)
    incluye = lo <= 0.5 <= hi
    afirma = p < 0.05
    assert incluye != afirma, (
        'los metodos se contradicen: IC incluye 0,5 = %s, p = %.4f'
        % (incluye, p))


def test_sin_efecto_los_dos_dicen_que_no(auc):
    rng = np.random.default_rng(12)
    todos = list(rng.normal(0.0, 0.4, 30).round(3))
    pos, neg = todos[:15], todos[15:]
    lo, hi = auc.ic_bootstrap(pos, neg, n=2000)
    p, _ge, _n = auc.p_permutaciones(pos, neg, n=2000)
    assert lo <= 0.5 <= hi or p >= 0.05, (
        'con datos sin efecto los dos deberian ser incapaces de afirmarlo')


# ----------------------------------- 3. el p de permutaciones, bien hecho
def test_el_p_de_permutaciones_es_pequeno_con_separacion(auc):
    """El bug que motivo este modulo.

    La primera version usaba `|AUC - obs| >= |0.5 - obs|`, que con un
    observado de 1,0 contaba las permutaciones con AUC <= 0,5: LA MITAD.
    Daba p = 0,51 con separacion perfecta, y el script de arriba afirmaba
    que los tres metodos coincidian.

    Se caza con este caso, que no puede tener otra respuesta.
    """
    pos = [0.80 + 0.01 * i for i in range(8)]
    neg = [0.20 + 0.01 * i for i in range(17)]
    assert auc.auc_de(pos, neg) == 1.0
    p, ge, n = auc.p_permutaciones(pos, neg, n=2000)
    assert p < 0.01, 'con AUC = 1,0 el p tiene que ser diminuto: %.4f' % p
    assert ge < n * 0.01


def test_la_semilla_es_fija(auc):
    """Mismo par, mismo p. Si cambia, no se puede comparar con nada."""
    pos = [0.7, 0.72, 0.68, 0.75, 0.71, 0.69, 0.73, 0.74]
    neg = [0.2, 0.25, 0.3, 0.22, 0.28, 0.26, 0.24, 0.21, 0.27, 0.23]
    a = auc.p_permutaciones(pos, neg, n=1000)
    b = auc.p_permutaciones(pos, neg, n=1000)
    assert a == b


# ------------------------------------------- 4. las reglas del contrato
def test_la_muestra_es_la_declarada(auc):
    """La medicion se hace sobre la particion de validacion y solo ella.

    El modelo se ajusta en calibracion; evaluar en la misma muestra con la
    que se ajusta seria medir recuerdo. Y eso no lo comprueba nadie salvo
    que se compruebe.
    """
    src = io.open(os.path.join(ROOT, 'tools', 'auditar_auc.py'),
                  encoding='utf-8').read()
    assert 'es_val' in src
    i = src.index('ajuste = [h for h in ventana if not es_val(h)]')
    assert i > 0, 'el ajuste tiene que ser SOLO calibracion'


def test_el_reparto_no_se_convierte_en_victoria(auc):
    """`y = 0,5` se excluye, no se pasa a 1 ni a 0."""
    src = io.open(os.path.join(ROOT, 'tools', 'auditar_auc.py'),
                  encoding='utf-8').read()
    assert "exc['reparto (AUC binario)'] += 1" in src
    assert 'continue' in src[src.index('reparto (AUC binario)'):
                             src.index('reparto (AUC binario)') + 200]
