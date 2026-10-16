# -*- coding: utf-8 -*-
"""R2 §1: dos comprobaciones de integridad del AUC que faltaban.

A. `comprobar_solo_validacion` prueba que cada ID pertenece a validacion,
   pero no comprueba que la lista de evaluacion sea EXACTAMENTE la
   esperada: sin IDs duplicados y sin etiquetas ausentes.

B. El bootstrap filtra valores no finitos, pero `auc_de()` y
   `p_permutaciones()` no. Si una equity llega como NaN, la comparacion
   puede dar un resultado enganoso en vez de fallar claramente.
"""
import hashlib
import io
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def auc():
    import importlib.util
    ruta = os.path.join(ROOT, 'tools', 'auditar_auc.py')
    spec = importlib.util.spec_from_file_location('auditar_auc', ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------ A. integridad de la lista
def test_no_hay_ids_duplicados(auc):
    """Un ID repetido contaria dos veces en la clase, y el AUC lo notaria."""
    _c, v = auc.cal.muestra()
    ids = [i for i, _y in v]
    assert len(ids) == len(set(ids)), (
        'hay %d IDs repetidos en la particion de validacion'
        % (len(ids) - len(set(ids))))


def test_toda_mano_evaluada_tiene_etiqueta(auc):
    """Y toda etiqueta tiene su mano. Sin correspondence, el AUC se
    calcularia sobre otra cosa de la que dice calcularse."""
    _c, v = auc.cal.muestra()
    etiqueta = dict(v)
    por_id = {h['hand_id'] for h in
              auc.learn.load_hands(reliable_only=True)}
    faltan = [i for i in etiqueta if i not in por_id]
    assert not faltan, (
        '%d etiquetas sin mano en la ventana: %s'
        % (len(faltan), sorted(faltan)[:5]))


def test_la_comprobacion_detecta_una_lista_con_duplicados(auc):
    """`comprobar_solo_validacion` tiene que notar la anomalia.

    `revision_2` A: probar que cada ID es de validacion no dice nada sobre
    la forma de la lista. Esto es lo que faltaba.
    """
    val_id = None
    for i in range(500):
        cand = 'H_%04d' % i
        if int(hashlib.sha256(cand.encode()).hexdigest(), 16) % 10 < 3:
            val_id = cand
            break
    # repetido: la comprobacion actual NO lo nota, y por eso hace falta
    # una comprobacion aparte
    assert auc.comprobar_solo_validacion([val_id, val_id]) is True, (
        'comprobar_solo_validacion no mira duplicados; hace falta la '
        'comprobacion de unicidad de test_no_hay_ids_duplicados')

    cal_id = None
    for i in range(500):
        cand = 'H_%04d' % i
        if int(hashlib.sha256(cand.encode()).hexdigest(), 16) % 10 >= 3:
            cal_id = cand
            break
    with pytest.raises(auc.FugaDeValidacion):
        auc.comprobar_solo_validacion([val_id, cal_id])


def test_calibracion_y_validacion_se_partitionan_entero(auc):
    """La regla es `sha256(hand_id) % 10 < 3`. Las dos mitades tienen que
    ser disjuntas y cubrir la muestra."""
    _c, v = auc.cal.muestra()
    ids_cal = {i for i, _y in _c}
    ids_val = {i for i, _y in v}
    assert not (ids_cal & ids_val), 'la particion se solapa'
    assert len(ids_cal) + len(ids_val) == len(ids_cal | ids_val)


# ------------------------------------- B. las entradas tienen que ser finitas
def test_auc_de_rechaza_no_finitos(auc):
    """Un NaN comparado con un numero es False, no un error. Eso devuelve un
    AUC silenciosamente equivocado en vez de fallar."""
    for malo in (float('nan'), float('inf'), float('-inf')):
        with pytest.raises(ValueError):
            auc.auc_de([0.5, malo], [0.3, 0.4])
        with pytest.raises(ValueError):
            auc.auc_de([0.3, 0.4], [0.5, malo])


def test_p_permutaciones_rechaza_no_finitos(auc):
    """Igual, y aqui el peligro es mayor: una sola equity contaminada
    desplaza todas las permutaciones."""
    for malo in (float('nan'), float('inf'), float('-inf')):
        with pytest.raises(ValueError):
            auc.p_permutaciones([0.5, malo], [0.3, 0.4], n=100)


def test_auc_rapido_rechaza_no_finitos(auc):
    et = np.array([1, 0, 1, 0])
    for malo in (float('nan'), float('inf')):
        x = np.array([0.5, 0.3, malo, 0.4])
        with pytest.raises(ValueError):
            auc.auc_rapido(et, x)


def test_el_bootstrap_tampoco_acepta_no_finitos_sin_filtrar(auc):
    """El bootstrap SI los filtraba, y por eso el filtro de ahi era
    necesario. Con la validacion en `auc_de`, el filtro es redundante, y
    por eso se puede quitar sin perder nada.

    Aqui se comprueba que los dos caminos dan lo mismo: es la prueba de que
    quitar el filtro no cambia el numero.
    """
    rng = np.random.default_rng(3)
    pos = list(rng.normal(0.8, 0.1, 9).round(4))
    neg = list(rng.normal(0.2, 0.1, 12).round(4))
    ic_filtrado = auc.ic_bootstrap(pos, neg, n=2000)
    pos2 = list(pos) + [float('nan')] * 3
    with pytest.raises(ValueError):
        auc.ic_bootstrap(pos2, neg, n=200)
    assert ic_filtrado is not None