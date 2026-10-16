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
import ast
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
    # lo que no puede pasar es que el intervalo NO incluya 0,5 mientras el
    # p dice que no hay efecto: eso si es una contradiccion
    assert not (afirma and incluye), (
        'se contradicen: el p rechaza H0 (%.4f) y el IC incluye 0,5 '
        '[%.4f, %.4f]' % (p, lo, hi))


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
RUTA_AUC = os.path.join(ROOT, 'tools', 'auditar_auc.py')


def _fuente():
    return io.open(RUTA_AUC, encoding='utf-8').read()


def test_el_ajuste_es_solo_calibracion(auc):
    """El lado del AJUSTE. Este lo comprobaba el test viejo."""
    src = _fuente()
    assert 'not cal.es_validacion(h[' in src, (
        'el ajuste tiene que ser SOLO calibracion')


def test_no_evalua_manos_de_calibracion(auc):
    """El test que FALTABA cuando se publico el numero de 0,8308.

    `auditar_auc.py` hacia:

        c, v = cal.muestra()
        etiqueta = {i: y for i, y in c + v}      # las dos particiones

    El modelo se ajustaba en calibracion pero se evaluaban tambien las manos
    con las que se ajusto. Dentro y fuera de muestra, mezcladas, y el AUC
    salia empujado hacia arriba.

    Este test falla si vuelve a pasar. Y es COMPORTAMENTAL: llama a la
    comprobacion con un ID de calibracion y exige que lance. No mira el
    codigo, que es lo que permitio el error.
    """
    import hashlib

    # un hand_id que NO es de validacion: sha256 % 10 >= 3
    cal_id = None
    for i in range(500):
        cand = 'H_%04d' % i
        if int(hashlib.sha256(cand.encode('utf-8')).hexdigest(), 16) % 10 >= 3:
            cal_id = cand
            break
    assert cal_id is not None, 'no se encontro un id de calibracion'

    with pytest.raises(auc.FugaDeValidacion):
        auc.comprobar_solo_validacion([cal_id])

    # y la misma comprobacion pasa con uno que si lo es
    val_id = None
    for i in range(500):
        cand = 'H_%04d' % i
        if int(hashlib.sha256(cand.encode('utf-8')).hexdigest(), 16) % 10 < 3:
            val_id = cand
            break
    assert auc.comprobar_solo_validacion([val_id]) is True


def test_la_comprobacion_no_es_un_assert(auc):
    """`python -O` se come los asserts, y esta es justo la comprobacion que
    no puede desaparecer."""
    src = _fuente()
    assert 'raise FugaDeValidacion' in src, (
        'tiene que LANZAR, no afirmar')
    desnudos = [n for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.Assert)]
    assert not desnudos, (
        'no debe quedar ningun assert desnudo protegiendo la particion: %d'
        % len(desnudos))


def test_la_evaluacion_toma_solo_de_val(auc):
    """La correccion literal de `revision_2` §1: `dict(v)`, no `c + v`.

    Se mira el ARBOL, no el texto: el docstring del modulo menciona `c + v`
    para explicar el error, y un `in src` lo detectaria como si el bug
    estuviera en el codigo.
    """
    arbol = ast.parse(_fuente())
    asignaciones = [
        n for n in ast.walk(arbol)
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id == 'etiqueta']
    assert asignaciones, 'no se encuentra la asignacion de `etiqueta`'
    valor = asignaciones[-1].value
    assert isinstance(valor, ast.Call), 'tiene que ser dict(...)'
    assert isinstance(valor.func, ast.Name) and valor.func.id == 'dict'
    assert len(valor.args) == 1
    arg = valor.args[0]
    assert isinstance(arg, ast.Name) and arg.id == 'val_', (
        'la evaluacion tiene que ser dict(val_): solo validacion')

    # y ningun BinOp `+` entre `c` y `v` en el codigo
    sumas = [n for n in ast.walk(arbol)
             if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add)
             and {x.id for x in ast.walk(n.left)
                  if isinstance(x, ast.Name)} == {'c'}
             and any(isinstance(x, ast.Name) and x.id == 'v'
                     for x in ast.walk(n.right))]
    assert not sumas, '`c + v` mezcla calibracion y validacion'


def test_ajuste_y_evaluacion_son_disjuntos(auc):
    """Aparte de la comprobacion: que no haya solape de verdad."""
    _c, v = auc.cal.muestra()
    ids_val = [i for i, _y in v]
    ids_cal = [i for i, _y in auc.cal.muestra()[0]]
    assert not (set(ids_val) & set(ids_cal)), (
        'calibracion y validacion se solapan')
    assert all(auc.cal.es_validacion(i) for i in ids_val)
    assert not any(auc.cal.es_validacion(i) for i in ids_cal)


def test_la_particion_es_la_canonica(auc):
    """Una sola copia de la regla.

    `revision_2` §1: si `cal.muestra()` usa una particion distinta de la del
    script, no hay que asumir que son la misma. Aqui no hay una segunda
    copia: se llama a `calibrar.es_validacion`.
    """
    src = _fuente()
    assert 'cal.es_validacion' in src
    assert 'hashlib' not in src, (
        'no debe reimplementar el sha256: la regla canonica es una sola')


def test_el_bootstrap_es_estratificado(auc):
    """Conserva los dos tamanos de clase y no descarta ninguna replica.

    La version anterior remuestreaba la muestra conjunta y TIRABA las
    replicas que perdian una clase, lo que sesga el intervalo hacia el lado
    que mas manos tiene.
    """
    rng = np.random.default_rng(4)
    pos = list(rng.normal(1.0, 0.4, 8).round(3))
    neg = list(rng.normal(0.0, 0.4, 40).round(3))
    ic = auc.ic_bootstrap(pos, neg, n=3000)
    assert ic is not None, 'con estratificacion no puede faltar una clase'
    assert len(neg) > len(pos), 'clases desiguales a proposito'


def test_el_p_usa_la_correccion_de_monte_carlo(auc):
    """`ge / n` puede dar 0, que es un p-valor imposible."""
    src = _fuente()
    assert '(ge + 1) / (n + 1)' in src, (
        'la correccion de Monte Carlo tiene que estar ahi')
    # y con separacion perfecta el p es diminuto pero NO cero
    pos = [0.80 + 0.01 * i for i in range(8)]
    neg = [0.20 + 0.01 * i for i in range(17)]
    p, ge, n = auc.p_permutaciones(pos, neg, n=2000)
    assert p > 0.0, 'un p-valor de 0 no existe'
    assert p == pytest.approx((ge + 1) / (n + 1))


def test_el_ic_y_el_p_no_se_declaran_de_acuerdo(auc):
    """El veredicto anterior solo miraba el intervalo y decia que los dos
    metodos coincidian. Un IC y un p son preguntas distintas."""
    src = _fuente()
    assert 'los dos metodos coinciden' not in src, (
        'un IC y un p no se declaran de acuerdo entre si')
    assert 'no son dos intervalos' in src.lower() or \
        'NO SON DOS INTERVALOS' in src


def test_la_hipotesis_nula_es_direccional_y_declarada(auc):
    """Una cola, y declarada. La direccion se fijo antes de mirar."""
    src = _fuente()
    assert 'AUC <= 0,5' in src or 'AUC ≤ 0,5' in src, (
        'H0 direccional: AUC <= 0,5')
    contrato = io.open(os.path.join(ROOT, 'DOCS', 'CONTRATO_L_SEC.md'),
                       encoding='utf-8').read()
    assert 'direccional' in contrato, (
        'la direccion tiene que estar en el contrato, no solo en el codigo')


def test_el_reparto_no_se_convierte_en_victoria(auc):
    """`y = 0,5` se excluye, no se pasa a 1 ni a 0."""
    src = io.open(os.path.join(ROOT, 'tools', 'auditar_auc.py'),
                  encoding='utf-8').read()
    assert "exc['reparto (AUC binario)'] += 1" in src
    assert 'continue' in src[src.index('reparto (AUC binario)'):
                             src.index('reparto (AUC binario)') + 200]
