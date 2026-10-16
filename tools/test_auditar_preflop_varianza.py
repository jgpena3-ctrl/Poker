# -*- coding: utf-8 -*-
"""`tools/auditar_preflop_varianza.py` — las dos decisiones del contrato.

Cinco bloques:

  1. QUE EL AUC ES EL QUE DIGA. Contra una version lenta y obvia.
  2. QUE LA CURVA DE ERROR ES 1/sqrt(n). Si no lo es, la decision 1 del
     contrato esta escrita sobre una suposicion.
  3. QUE LA INTERPOLACION DEL MOVIMIENTO NO SE INVENTA NADA.
  4. QUE LAS DOS DECISIONES ESTAN ESCRITAS EN EL CONTRATO. Un numero
     medido que no llega al contrato no decide nada.
  5. QUE `DEFAULT_RUNOUT_COMBOS` NO SE HA BAJADO A 40.
"""
import importlib.util
import io
import os
import re

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def var():
    ruta = os.path.join(ROOT, 'tools', 'auditar_preflop_varianza.py')
    spec = importlib.util.spec_from_file_location('auditar_preflop_varianza',
                                                  ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------- 1. el AUC es el que
def _auc_lento(a, b):
    if not len(a) or not len(b):
        return None
    t = 0.0
    for x in a:
        for y in b:
            t += 1.0 if x > y else (0.5 if x == y else 0.0)
    return t / (len(a) * len(b))


def test_el_auc_rapido_coincide_con_el_lento(var):
    rng = np.random.default_rng(5)
    for _ in range(6):
        et = np.concatenate([np.ones(9), np.zeros(13)]).astype(int)
        x = rng.normal(size=22).round(1)          # redondeado: hay empates
        a = _auc_lento(x[et == 1], x[et == 0])
        assert abs(a - var.auc_rapido(et, x)) < 1e-9


def test_el_auc_no_esta_definido_sin_una_clase(var):
    assert var.auc_rapido(np.ones(5, dtype=int), np.ones(5)) is None
    assert var.auc_rapido(np.zeros(5, dtype=int), np.zeros(5)) is None


def test_la_curva_de_error_baja(var):
    """El estimador tiene que mejorar cuando hay mas combos."""
    rng = np.random.default_rng(9)
    vals = rng.normal(0.5, 0.25, 40).round(3)
    pes = np.full(40, 0.05)
    ref = float((vals * pes).sum() / pes.sum())
    c = var.curva_de_error(vals, pes, ref, reps=300)
    assert c[40][0] < c[5][0], 'mas combos, menos error: %r' % c
    assert c[40][1] < c[5][1]


def test_la_curva_de_error_es_un_sobre_raiz_de_n(var):
    """1/sqrt(n), no otra cosa.

    La decision 1 del contrato dice "cuadruplicar los combos solo parte el
    error en dos". Si la curva fuera de otra forma, esa frase seria falsa y
    el coste de mas combos estaria mal escrito.
    """
    rng = np.random.default_rng(21)
    vals = rng.normal(0.5, 0.25, 40).round(3)
    pes = np.full(40, 0.05)
    ref = float((vals * pes).sum() / pes.sum())
    c = var.curva_de_error(vals, pes, ref, reps=1500)
    # sigma de 10 frente a 40: deberia ser justo el doble
    razon = c[10][1] / c[40][1]
    assert 1.7 < razon < 2.3, 'esperaba ~2,0, salio %.2f' % razon


# ------------------------------------------------- 3. la interpolacion
def test_la_interpolacion_es_lineal_entre_medidas(var):
    c = {0.01: 0.1, 0.02: 0.2}
    assert var._interp_movimiento(c, 0.015) == pytest.approx(0.15)
    # fuera de rango: extrapola por escala, no inventa un cero
    assert var._interp_movimiento(c, 0.005) == pytest.approx(0.1)
    assert var._interp_movimiento(c, 0.04) > 0.2


def test_la_interpolacion_declara_su_limite(var):
    """Fuera del rango medido extrapola en lineal, y a 500x lo
    underestimate. Por eso el veredicto no se apoya en un sigma que
    este fuera de la tabla."""
    c = {0.01: 0.1, 0.02: 0.2}
    # sigma = 0,04 es el doble del ultimo medido, y el movimiento tambien
    assert var._interp_movimiento(c, 0.04) == pytest.approx(0.4)
    # 500x el ultimo medido: el valor crece, no se queda clavado en 0,2
    assert var._interp_movimiento(c, 10.0) > 1.0


# --------------------------------------- 4. las decisiones, en el contrato
def _contrato():
    return io.open(os.path.join(ROOT, 'DOCS', 'CONTRATO_PREFLOP.md'),
                   encoding='utf-8').read()


def test_la_decision_1_esta_escrita_con_su_sigma():
    t = _contrato()
    assert 'Decisión 1 — **muestreado**' in t
    assert 'σ(n = 40) = 0,0934' in t, 'el sigma medido tiene que estar escrito'


def test_la_decision_2_declara_la_vara_antes_del_numero():
    """La vara va ANTES del numero, que es lo que hace que no sea
    una justificacion a posteriori."""
    t = _contrato()
    i_vara = t.index('El criterio: el ruido del estimador')
    i_num = t.index('0,26')
    assert i_vara < i_num, 'la vara tiene que declararse antes del resultado'


def test_el_contrato_dice_que_la_vara_mala_es_el_hueco_minimo():
    """Es la parte que casi importa: si alguien vuelve a plantear la
    pregunta por el hueco minimo, el contrato dice por que no vale."""
    t = _contrato()
    assert '0,0004' in t
    assert '337 308' in t
    plano = ' '.join(t.split())
    assert 'no las distingue ninguna métrica' in plano


def test_la_trampa_del_puesto_esta_escrita():
    t = _contrato()
    assert 'prob_vec_player' in t
    assert 'nombre de jugador' in t
    assert 'prior plano' in t


def test_la_firma_propuesta_no_se_ha_tocado():
    """El contrato dice que lo que no cambia despues es el contrato. La
    firma tiene que seguir siendo la que se escribio."""
    t = _contrato()
    m = re.search(r'def equity_preflop_rango\((.*?)\):', t, re.S)
    assert m, 'la firma propuesta tiene que seguir en el contrato'
    assert 'hero_codes' in m.group(1)
    assert 'villain_reach' in m.group(1)


# --------------------------------------- 5. lo que NO se toco, declarado
def test_default_runout_combos_no_se_bajo_a_40():
    """El contrato declara un desacuerdo con `decision.py` y dice que NO
    se baja. Si alguien lo baja, este test lo para."""
    from motor import decision
    assert decision.DEFAULT_RUNOUT_COMBOS != 40, (
        'el contrato declara que NO se baja a 40: '
        'DECISO_COMBOS_NO_ES_40 en CONTRATO_PREFLOP.md')
    assert '**no** se cambia a 40' in _contrato()


def test_no_se_toco_subsets():
    """`_SUBSETS` es el diagnostico del bloque 1. Sigue igual: nada se ha
    implementado todavia, y el contrato no se adelanta a lo escrito."""
    from motor import hand_evaluator
    assert set(hand_evaluator._SUBSETS) == {5, 6, 7}, (
        'algo toco _SUBSETS: el camino preflop se implemento sin '
        'actualizar CONTRATO_PREFLOP.md antes')