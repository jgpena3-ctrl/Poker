# -*- coding: utf-8 -*-
"""Tests del camino preflop corregidos segun `revision_2` §1.

Los anteriores fijaban un estimador que hacia DOBLE PONDERADO: sortear por
peso y luego ponderar por peso otra vez. Este fichero fija el correcto.
"""
import importlib.util
import io
import os

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def he():
    from motor import hand_evaluator
    return hand_evaluator


# ------------------------------------------- 1.C el estimador corregido
def test_no_hay_doble_ponderado(he):
    """El texto del error es lo mas honesto que se puede comprobar.

    Sortear por peso Y ponderar por peso otra vez empuja la equity hacia
    los combos pesados. La media simple de i.i.d. no lo hace.
    """
    src = io.open(os.path.join(ROOT, 'motor', 'hand_evaluator.py'),
                  encoding='utf-8').read()
    i = src.index('def equity_preflop_rango')
    cuerpo = src[i:src.index('\ndef ', i + 10) if '\ndef ' in src[i + 10:]
                 else len(src)]
    assert 'acc += equity_preflop_contra_combo(' in cuerpo, (
        'el estimador tiene que acumular la equity SIN multiplicar por el '
        'peso: eso es el doble ponderado')
    assert 'replace=True' in cuerpo, (
        'con reemplazo y media simple es exactamente insesgado')
    assert '* w_leg[' not in cuerpo and '* w_legal[' not in cuerpo, (
        'no se vuelve a ponderar por el peso dentro del estimador')
    assert 'DOBLE PONDERADO' in cuerpo, (
        'el motivo tiene que estar escrito, que es lo que lo evita')


def test_el_estimador_es_insesgado(he, monkeypatch):
    """Medido: la media de extracciones i.i.d. tiene sesgo ~0.

    Un sigma pequeno con un sesgo systematico es estar precisamente mal,
    asi que se imprime el sesgo y se comprueba.
    """
    # equities ficticias en funcion del indice del combo
    equities = {}

    def fake(hero, villain):
        return equities[int(villain[0]) % 97] / 97.0

    monkeypatch.setattr(he, 'equity_preflop_contra_combo', fake)
    rng = np.random.default_rng(1)
    # rango concentrado en los 20 primeros ids legalizados
    w = np.zeros(1326)
    mask = 0
    for c in (0, 1):
        mask |= (1 << c)
    from motor.ranges import HAND_MASKS, COMBO0
    ids = np.where((HAND_MASKS & mask) == 0)[0][:20]
    w[ids] = rng.random(len(ids)) + 0.05
    for i, j in enumerate(ids):
        equities[int(COMBO0[j])] = float(i)

    verdad = None
    est = []
    for k in range(3000):
        a = he.equity_preflop_rango(['2c', '2d'], w, n_combos=6, seed=1000 + k)
        est.append(a)
    est = np.array(est)
    # el valor exacto: media ponderada de la equity de cada id
    verdad = float((w[ids] * np.array([equities[int(COMBO0[j])] / 97.0
                                      for j in ids])).sum() / w[ids].sum())
    sesgo = float(est.mean() - verdad)
    assert abs(sesgo) < 0.01, (
        'sesgo %.4f: la media simple de i.i.d. deberia ser insesgada, y si '
        'no lo es el estimador no hace lo que dice' % sesgo)


def test_es_determinista_con_el_mismo_seed(he, monkeypatch):
    equities = {}

    def fake(hero, villain):
        equities[int(villain[0]) % 97] = 0.5
        return 0.5

    monkeypatch.setattr(he, 'equity_preflop_contra_combo', fake)
    w = np.full(1326, 1.0 / 1326)
    a = he.equity_preflop_rango(['As', 'Kd'], w, n_combos=4, seed=3)
    b = he.equity_preflop_rango(['As', 'Kd'], w, n_combos=4, seed=3)
    assert a == b


# ---------------------------------------------- 1.A el spot del villano
def _mano(acciones, hero='SB'):
    return {'players': [{'pos': hero}, {'pos': 'BB'}],
            'streets': {'preflop': {'actions': acciones}}}


@pytest.fixture(scope='module')
def ins():
    ruta = os.path.join(ROOT, 'tools', 'equity_preflop_observables.py')
    spec = importlib.util.spec_from_file_location('eqpobs', ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_manos_previas_al_corte(ins):
    """Solo se cuentan las acciones ANTES del corte.

    Antes se contaba toda la calle, y eso puede clasificar una mano segun
    una accion posterior al momento que se quiere evaluar.
    """
    # el hero actua en 1; despues hay un 3bet del villano que no cuenta
    h = _mano([{'pos': 'BB', 'action': 'r'},
               {'pos': 'SB', 'action': 'c'},
               {'pos': 'BB', 'action': 'r'}])
    assert ins.mano_del_spot(h, 'preflop', 'SB', 1) == 'facing_open'


def test_manos_sin_subidas_previas(ins):
    h = _mano([{'pos': 'SB', 'action': 'c'}])
    assert ins.mano_del_spot(h, 'preflop', 'SB', 0) == 'no_raise'


def test_manos_con_dos_subidas_previas_es_3bet(ins):
    """Y `facing_3bet` tiene que existir. Antes nunca se devolvia, asi que
    un 3bet se clasificaba como `facing_open` y consultaba el rango
    equivocado."""
    h = _mano([{'pos': 'BB', 'action': 'r'},
               {'pos': 'SB', 'action': 'r'},
               {'pos': 'BB', 'action': 'r'},
               {'pos': 'SB', 'action': 'c'}])
    assert ins.mano_del_spot(h, 'preflop', 'SB', 3) == 'facing_3bet'


def test_los_tres_spots_declaran_sus_alternativas(ins):
    for spot in ('no_raise', 'facing_open', 'facing_3bet'):
        alts = ins.ACCIONES_SPOT[spot]
        assert len(alts) == 2, (
            'un spot con mas de dos alternativas declara una regla nueva: '
            'hay que escribirla')
        assert len(set(alts)) == 2, 'alternativas repetidas en %s' % spot


def test_el_rango_es_la_union_de_las_alternativas(ins):
    """A igual masa de prior, y declarado. Elegir una en silencio es lo que
    hacia la version anterior."""
    src = io.open(os.path.join(ROOT, 'tools',
                               'equity_preflop_observables.py'),
                  encoding='utf-8').read()
    i = src.index('def rango_del_villano')
    cuerpo = src[i:i + 1400]
    assert 'for a in alternativas' in cuerpo
    assert 'g / s' in cuerpo, 'cada alternativa tiene que ir a masa 1'
    assert 'total / total.sum()' in cuerpo, 'y renormalizar despues'


# ------------------------------------------------------ 1.B la semilla
def test_la_semilla_es_por_mano_no_por_orden(ins):
    """Con un generador compartido la muestra dependia del ORDEN, y con
    `--manos` el numero de una mano ya calculada cambiaba."""
    a = ins.semilla_de('H_0001')
    b = ins.semilla_de('H_0002')
    assert a != b, 'dos manos distintas con la misma semilla'
    assert ins.semilla_de('H_0001') == a, 'la semilla tiene que ser estable'
    # y tiene que depender de la version del estimador
    src = io.open(os.path.join(ROOT, 'tools',
                               'equity_preflop_observables.py'),
                  encoding='utf-8').read()
    assert '|v%d|%d' in src, (
        'la version del estimador tiene que entrar en la semilla: si cambia '
        'el estimador, la muestra tiene que cambiar')
    assert 'VERSION = 2' in src


# --------------------------------------------------------------- 3 contrato
def test_n_combos_valida_positividad(he):
    w = np.full(1326, 1.0 / 1326)
    for malo in (0, -1):
        with pytest.raises(ValueError) as e:
            he.equity_preflop_rango(['As', 'Kd'], w, n_combos=malo)
        assert 'n_combos' in str(e.value)


def test_n_runouts_esta_declarado_como_sin_efecto(he):
    """Se acepta y se valida, pero no cambia el calculo: contra cada combo
    se enumeran TODOS los sorteos. Y eso hay que estar escrito, porque un
    parametro publico que parece controlar el calculo y no lo hace es una
    trampa."""
    src = io.open(os.path.join(ROOT, 'motor', 'hand_evaluator.py'),
                  encoding='utf-8').read()
    i = src.index('def equity_preflop_rango')
    doc = src[i:src.index('"""', src.index('"""', i) + 3) + 3]
    assert 'n_runouts' in doc
    assert 'no cambia el calculo' in doc