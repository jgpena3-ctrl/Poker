# -*- coding: utf-8 -*-
"""R2 §1: la huella del rango efectivo, y el `n` pedido frente al efectivo.

El motivo de que esto exista no es teorico. `dfef471` reescribio 212 de las
1258 manos; de las 41 del universo de validacion cambio UNA, `H_0173`, y su
cambio estaba en el PREFLOP: dos `r` pasaron a `c`. Los SIETE campos de la
condicion de reutilizacion no lo detectaron, y `HANDS_DB_SHA256` —que si
cambio— no estaba en la condicion.

Asi que lo que hace falta no es un octavo campo declarado, que es
justamente lo que ya existe en `motor/learn.py` y ya ha dejado pasar esto.
Es una huella calculada sobre el rango que se esta usando.
"""
import importlib.util
import os

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def ins():
    ruta = os.path.join(ROOT, 'tools', 'equity_preflop_observables.py')
    spec = importlib.util.spec_from_file_location('eqpobs_h', ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ================================================= la huella, en sustancia
def _huella(ins, hero='AsKd', ids=None, wl=None, semilla=7, n=40, y=1.0):
    if ids is None:
        ids = np.arange(5, dtype=np.intp)
    if wl is None:
        wl = np.linspace(0.1, 0.5, len(ids))
    return ins.huella_de(hero, ids, wl, semilla, n, y)


def test_la_huella_es_determinista(ins):
    assert _huella(ins) == _huella(ins)


@pytest.mark.parametrize('cambio', [
    {'hero': 'QsJd'},          # las cartas del heroe
    {'ids': None},             # el enumerado legal (abajo, aparte)
    {'semilla': 8},            # el generador
    {'n': 39},                 # cuantos se muestrearon
    {'y': 0.0},                # la ETIQUETA, que no viene del rango
])
def test_la_huella_cambia_si_cambia_algo_que_la_determina(ins, cambio):
    """Cada cosa que entra en la equity tiene que cambiar la huella. Si
    alguna no lo hiciera, el parametro estaria en la huella de mentira."""
    if cambio == {'ids': None}:
        otro = dict(ids=np.arange(6, dtype=np.intp),
                    wl=np.linspace(0.1, 0.5, 6))
    else:
        otro = cambio
    base = dict(hero='AsKd', ids=None, wl=None, semilla=7, n=40, y=1.0)
    base.update(otro)
    b = ins.huella_de(
        base['hero'],
        base['ids'] if base['ids'] is not None else np.arange(5, dtype=np.intp),
        base['wl'] if base['wl'] is not None else np.linspace(0.1, 0.5, 5),
        base['semilla'], base['n'], base['y'])
    assert b != _huella(ins), (
        'cambiar %r no cambio la huella: ese parametro esta de adorno'
        % list(cambio))


def test_la_huella_cambia_si_cambia_el_peso_de_un_solo_combo(ins):
    """El caso que importa: la base cambia, el modelo cambia, el rango se
    mueve un pelo, y el numero viejo deja de valer. Un peso distinto en UN
    combo tiene que notarse."""
    wl = np.linspace(0.1, 0.5, 5)
    ids = np.arange(5, dtype=np.intp)
    antes = ins.huella_de('AsKd', ids, wl, 7, 40, 1.0)
    wl2 = wl.copy()
    wl2[3] += 1e-12
    despues = ins.huella_de('AsKd', ids, wl2, 7, 40, 1.0)
    assert antes != despues, (
        'una diferencia de 1e-12 no puede quedar fuera de la huella, o el '
        'rango puede cambiar sin que la cache se entere')


def test_la_huella_no_depende_de_la_longitud_del_rango_entero(ins):
    """No tiene por que: el rango del villano tiene ~1326 combos y lo que
    entra en la equity son los legales. Pero el enumerado entra."""
    ids = np.arange(5, dtype=np.intp)
    wl = np.linspace(0.1, 0.5, 5)
    a = ins.huella_de('AsKd', ids, wl, 7, 40, 1.0)
    b = ins.huella_de('AsKd', np.arange(5, 9, dtype=np.intp), wl, 7, 40, 1.0)
    assert a != b, 'un enumerado distinto es un rango distinto'


# ============================================ la condicion la exige
def test_la_condicion_de_reutilizacion_exige_la_huella(ins):
    texto = open(ins.__file__, encoding='utf-8').read()
    i = texto.index("entrada = cache.get(hid)")
    cuerpo = texto[i:i + 1800]
    assert "entrada.get('huella') == huella" in cuerpo, (
        'sin la huella, los otros siete campos siguen sin notar que la base '
        'ha cambiado')
    assert 'huella = huella_de(' in texto, 'y la huella tiene que existir'


def test_el_rango_se_calcula_ANTES_de_decidir_si_se_reutiliza(ins):
    """El orden importa: para comparar la identidad del rango hay que
    tenerlo delante. Si se reutiliza primero y se calcula despues, la
    huella no existe todavia."""
    texto = open(ins.__file__, encoding='utf-8').read()
    i_huella = texto.index('huella = huella_de(')
    i_cache = texto.index("entrada = cache.get(hid)")
    assert i_huella < i_cache, 'la huella se calcula antes de comparar'


def test_el_rechazo_dice_que_no_coincide(ins):
    """Recalcular sin decir por que obliga a releer el codigo entero."""
    texto = open(ins.__file__, encoding='utf-8').read()
    i = texto.index("entrada = cache.get(hid)")
    assert 'porque_no_reutilizable' in texto[i:i + 1200]
    assert ins.porque_no_reutilizable.__doc__.count('NO coincide') == 1


def test_el_motivo_nombra_las_que_no_coinciden(ins):
    t = {'semilla': 7, 'villano': 'X', 'spot': 'no_raise', 'hero': 'AsKd'}
    buena = {'version': ins.VERSION, 'estimador': ins.ESTIMADOR,
             'semilla': 7, 'n_combos': ins.N_COMBOS, 'villano': 'X',
             'spot': 'no_raise', 'hero': 'AsKd', 'huella': 'abc'}
    assert ins.porque_no_reutilizable(buena, ins.VERSION, ins.ESTIMADOR, t,
                                     ins.N_COMBOS, 'abc') == '', (
        'si todo coincide no hay motivo: seria un fallo')
    mala = dict(buena, hero='QsJd', huella='xyz')
    m = ins.porque_no_reutilizable(mala, ins.VERSION, ins.ESTIMADOR, t,
                                   ins.N_COMBOS, 'abc')
    assert 'hero' in m and 'huella' in m
    assert 'seed' not in m, 'solo los que fallan, no los que casan'


# ============================== `n` pedido y `n` efectivo, por separado
def test_n_combos_guarda_lo_pedido_y_no_lo_efectivo(ins):
    """Con `n_combos = n` (el efectivo) y la condicion comparando con
    `N_COMBOS`, una mano cuyo rango legal tenga menos combos no se
    reutilizaba NUNCA: el calculo se repetia para siempre sin decir nada.
    """
    texto = open(ins.__file__, encoding='utf-8').read()
    i = texto.index('cache[hid] = {')
    cuerpo = texto[i:i + 700]
    assert "'n_combos': N_COMBOS" in cuerpo, (
        'lo comparable entre versiones es lo PEDIDO')
    assert "'n_muestreados': n" in cuerpo, (
        'y lo que se divide de verdad es el EFECTIVO, con su nombre')
    assert "'n_combos': n," not in cuerpo


def test_el_desajuste_entre_pedido_y_efectivo_se_avisa(ins):
    texto = open(ins.__file__, encoding='utf-8').read()
    assert 'if n != N_COMBOS:' in texto
    i = texto.index('if n != N_COMBOS:')
    assert 'se han muestreado' in texto[i:i + 500], (
        'no es un error, pero tiene que quedar escrito en el informe: si no '
        'parece que se calculara con menos de lo pedido sin avisar')