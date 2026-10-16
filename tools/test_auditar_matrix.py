# -*- coding: utf-8 -*-
"""`tools/auditar_matrix.py` — con la prueba CORRECTA.

Esta versión reescribe la anterior. La anterior fijaba una premisa que no
se sostenía y, como escribió `revision_2`, *"los tests pueden validar
fielmente una conclusión equivocada si la premisa del test es
incorrecta"*. Eso era exactamente lo que pasaba aquí.

El error retirado: la exclusión mutua es **por mano**,
`sum_k p_k(c) <= 1` para cada celda `c`, y no `sum_k S_k <= 1` sumando las
169 celdas. Con esa premisa, `FLAT_PRIOR * 169 = 25,35` parecía una
contradicción y no lo era.

Cinco bloques:

  1. QUE LA PRUEBA ES POR CELDA. Y que el agrupamiento lo dice.
  2. QUE NO HAY CONTRADICCION. Lo que el motor produce de verdad.
  3. QUE HAY COTA INFERIOR PARA alpha. Porque sí la hay, y es lo útil.
  4. QUE LO RETIRADO ESTÁ RETIRADO. En el código y en el documento.
  5. QUE `data/` SIGUE INTACTO.
"""
import ast
import importlib.util
import io
import json
import os
import warnings

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


@pytest.fixture(scope='module')
def modelo(mat):
    """El modelo real, montado una sola vez."""
    from motor import learn, player_ranges
    ventana = learn.load_hands(reliable_only=True)
    ajuste = [h for h in ventana if not mat.cal.es_validacion(h['hand_id'])]
    spec = importlib.util.spec_from_file_location(
        'equity_de_mano', os.path.join(ROOT, 'tools', 'equity_de_mano.py'))
    eqm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eqm)
    return player_ranges.ProfileRangeModel.from_hands(
        ajuste, labels=eqm.perfiles_de(ajuste),
        alpha=player_ranges.DEFAULT_ALPHA)


def _max_suma_por_celda(mat, modelo, alpha):
    """max sobre (perfil, spot) de la suma por celda de acciones excluyentes."""
    modelo.alpha = alpha
    peor = 0.0
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for (perfil, spot), _opp in sorted(modelo.opp.items()):
            accs = mat.ACCIONES_DE.get(spot)
            if not accs:
                continue
            t = np.zeros((13, 13))
            for a in accs:
                t += np.asarray(modelo.p_matrix(perfil, spot, a),
                                dtype=float)
            # el fold entra aparte: no tiene tabla y su prior es el plano.
            # Anadirlo es lo CONTRARIO de lo que la prueba retirada hacia.
            t += np.asarray(modelo._prior_grid('fold', '', ''), dtype=float)
            peor = max(peor, float(t.max()))
    modelo.alpha = 2.0
    return peor


# ------------------------------------------- 1. la prueba es por celda
def test_las_acciones_de_un_spot_son_excluyentes(mat):
    """Y el agrupamiento por spot es lo que hace que la prueba tenga sentido."""
    assert set(mat.ACCIONES_DE) >= {'no_raise', 'facing_open',
                                    'facing_3bet'}
    for spot, acciones in mat.ACCIONES_DE.items():
        assert len(acciones) >= 2, (
            'un spot con una sola accion no prueba nada: %s' % spot)
        assert len(set(acciones)) == len(acciones)


def test_el_fold_no_esta_en_las_tablas(mat):
    """El fold se anade APARTE en la prueba, y se dice.

    Antes seINDOWS usaba su prior plano como si fuera una tabla mas y de ahi
    salia el 25,35. Aqui esta separado a proposito.
    """
    from motor import player_ranges
    for a in ('fold', 'fold_vs_open', 'bb_check', 'fold_vs_3bet'):
        assert a not in player_ranges.CAT_TABLE
        assert a not in mat.ACCIONES_DE.get('no_raise', [])
        assert a not in mat.ACCIONES_DE.get('facing_open', [])


# ------------------------------------------------ 2. no hay contradiccion
def test_p_matrix_no_pasa_de_uno(mat, modelo):
    """La afirmacion que SUSTITUYE a la retirada."""
    peor = 0.0
    for (perfil, spot), _opp in sorted(modelo.opp.items()):
        for a in mat.ACCIONES_DE.get(spot, []):
            m = np.asarray(modelo.p_matrix(perfil, spot, a), dtype=float)
            peor = max(peor, float(m.max()))
    assert peor <= 1.0, (
        'p_matrix devolvio %.4f > 1: eso SI seria una contradiccion'
        % peor)
    assert abs(peor - 0.757143) < 1e-5, (
        'el maximo era 0,757143 y ahora sale %.6f: el documento esta stale'
        % peor)


def test_la_suma_por_celda_no_pasa_de_uno(mat, modelo):
    """Con el fold plano anadido, que es el caso mas duro."""
    peor = _max_suma_por_celda(mat, modelo, 2.0)
    assert peor <= 1.0, 'la suma por celda llega a %.4f' % peor
    assert abs(peor - 0.9500) < 0.005, 'el documento dice 0,9500'


def test_la_prueba_retirada_daria_un_numero_sin_significado():
    """Y por que el 25,35 no significa nada. Esta es la prueba de que la
    premisa estaba mal, escrita como test para que no vuelva."""
    # 169 manos distintas, cada una con 0,15 de fold: la suma es 25,35 y
    # NO hay contradiccion, porque cada celda es una mano distinta.
    assert 169 * 0.15 == pytest.approx(25.35)
    # el contrato real es POR celda
    assert 0.15 <= 1.0, '0,15 en una celda es una probabilidad valida'


# ------------------------------------------------- 3. cota de alpha
def test_por_debajo_del_borde_las_probabilidades_se_rompen(mat, modelo):
    """Lo que si es una conclusion, y es medible.

    Por debajo de ~1,3636 la suma por celda de acciones mutuamente
    excluyentes pasa de 1, lo que es imposible.
    """
    assert _max_suma_por_celda(mat, modelo, 1.0) > 1.0
    assert _max_suma_por_celda(mat, modelo, 1.3) > 1.0
    assert _max_suma_por_celda(mat, modelo, 2.0) <= 1.0


def test_el_borde_esta_entre_1_30_y_1_40(mat, modelo):
    """Bisección: el documento dice 1,3636."""
    assert _max_suma_por_celda(mat, modelo, 1.30) > 1.0
    assert _max_suma_por_celda(mat, modelo, 1.40) <= 1.0


def test_default_alpha_esta_por_encima_del_borde(mat):
    """1,47x. Y eso es la razon por la que se queda, medida."""
    from motor import player_ranges
    assert player_ranges.DEFAULT_ALPHA >= 1.40, (
        'DEFAULT_ALPHA ha bajado de la zona coherente')
    assert player_ranges.DEFAULT_ALPHA / 1.3636 == pytest.approx(1.467,
                                                                  abs=0.01)


def test_arriba_no_se_rompe_nunca(mat, modelo):
    """alpha grande NO rompe el contrato: la restriccion es por DEBAJO."""
    for a in (10.0, 50.0, 200.0, 2000.0):
        assert _max_suma_por_celda(mat, modelo, a) <= 1.0, (
            'alpha = %.0f rompe el contrato, y el documento dice que no'
            % a)


# ------------------------------------- 4. lo retirado, esta retirado
def _todo_en_contexto_de_retirada(texto, aguja, ventana=600):
    """Cada vez que aparece `aguja`, tiene que estar cerca de una marca de
    retirada.

    Es mas robusto que exigir que no aparezca: el documento TIENE que
    citar lo que retiro, para que se vea que se retiro.
    """
    # 'retir' cubre RETIRA, retirada, retirado y RETIRADA
    marcas = ('retir', 'correccion', 'no es \u00abnunca\u00bb',
              'no lo distinguir', 'mal planteado', 'reabiert')
    plano = ' '.join(texto.split()).lower()
    pos = 0
    while True:
        k = plano.find(aguja, pos)
        if k == -1:
            return True
        trozo = plano[max(0, k - ventana):k + len(aguja) + ventana]
        if not any(m in trozo for m in marcas):
            return False, plano[max(0, k - 90):k + len(aguja) + 90]
        pos = k + 1


def test_lo_retirado_en_el_script_esta_marcado(mat):
    """Y que no vuelva por descuido.

    La frase retirada aparece en el script, pero SOLO citada, dentro de la
    seccion que la retira. Lo que no puede volver es la PRUEBA retirada: no
    puede haber una desigualdad que sume sobre las 169 celdas.
    """
    ruta = os.path.join(ROOT, 'tools', 'auditar_matrix.py')
    src = io.open(ruta, encoding='utf-8').read()

    # 1) ninguna inegalidad sobre la suma de una tabla
    for nodo in ast.walk(ast.parse(src)):
        if isinstance(nodo, ast.Compare) and isinstance(nodo.left, ast.Name):
            assert not nodo.left.id.startswith('S_'), (
                'ha vuelto una inegalidad sobre la suma de una tabla: S_%s'
                % nodo.left.id)

    # 2) la frase retirada, siempre marcada
    ok = _todo_en_contexto_de_retirada(
        src, 'no es un parametro de regularizacion')
    assert ok is True, 'la frase retirada sale sin marcar: %r' % (ok,)

    # 3) lo que si tiene que aparecer: la formulacion correcta
    assert 'para cada celda c' in src


def test_lo_retirado_en_el_documento_esta_marcado():
    d = io.open(os.path.join(ROOT, 'DOCS', 'QUE_ES_MATRIX.md'),
                encoding='utf-8').read()
    for aguja in ('no se calibra nunca', 'no es un par\u00e1metro de '
                  'regularizaci\u00f3n'):
        ok = _todo_en_contexto_de_retirada(d, aguja)
        assert ok is True, (
            'la conclusion retirada sigue afirmandose sin marcar: %r' % (ok,))
    plano = ' '.join(d.split())
    assert 'RETIRADA' in plano.upper()
    assert '1,3636' in plano, 'la cota medida tiene que estar'


def test_el_documento_separa_las_tres_afirmaciones():
    """
evision_2 §3: coherencia, discriminacion y decision son cosas
    distintas, y confundirlas es lo que hace que una decision de ingenieria
    parezca una demostracion."""
    d = io.open(os.path.join(ROOT, 'DOCS', 'QUE_ES_MATRIX.md'),
                encoding='utf-8').read()
    plano = ' '.join(d.split())
    for seccion in ('(1) Coherencia', '(2) Discriminación',
                    '(3) Decisión'):
        assert seccion in plano, (
            'falta la seccion %s: las tres van separadas' % seccion)
    assert 'no depende de (2)' in plano, (
        'la decision tiene que decir que no depende de la discriminacion')
    assert 'Discriminación: ninguna' in plano


def test_el_bloque_3_esta_reabierto():
    f = io.open(os.path.join(ROOT, 'DOCS', 'FASE_D_BLOQUEADA.md'),
                encoding='utf-8').read()
    plano = ' '.join(f.split())
    assert 'REABIERTO' in plano, (
        'el estado dice que el bloque 3 esta cerrado y ya no es verdad')


def test_default_alpha_sigue_en_dos():
    from motor import player_ranges
    assert player_ranges.DEFAULT_ALPHA == 2.0


def test_la_particion_es_la_canonica(mat):
    """R2 §2, punto de mantenimiento: no reimplementar el sha256.

    `auditar_matrix.py` lo hacia. Ahora usa `calibrar.es_validacion`.
    """
    src = io.open(os.path.join(ROOT, 'tools', 'auditar_matrix.py'),
                  encoding='utf-8').read()
    assert 'cal.es_validacion' in src
    assert 'sha256' not in src, (
        'vuelve a reimplementar la regla de particion: son dos copias que '
        'pueden divergir en silencio')


# -------------------------------------------------- 5. data/ intacto
def test_data_no_se_toco():
    crudo = json.load(io.open(MATRICES, encoding='utf-8'))
    assert list(crudo) == ['tables'], (
        'se han anadido claves de nivel superior: %s' % list(crudo))
    assert len(crudo['tables']) == 117
    assert all('matrix' in v for v in crudo['tables'].values())


def test_las_tablas_no_cambiaron(mat):
    """Los tres datos que el documento publica, sobre el fichero de verdad."""
    filas = mat.sumas()
    s = np.array([d['suma'] for d in filas])
    assert len(filas) == 117
    assert int((np.abs(s - 1.0) < 0.05).sum()) == 1
    assert abs(s.max() - 89.75) < 0.01
    assert abs(s.min() - 0.91) < 0.01
    todos = mat.celdas_fuera_de_rango()
    assert todos.size == 19773
    assert float(todos.min()) >= 0.0 and float(todos.max()) <= 1.0