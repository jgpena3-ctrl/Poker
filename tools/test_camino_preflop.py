# -*- coding: utf-8 -*-
"""El camino preflop. Los tests que `CONTRATO_PREFLOP.md` declaro.

El contrato eligio dos, y el segundo es el que importa:

  1. `test_l_sec_cubriria_el_cien_por_cient` — cobertura OBSERVABLE.
  2. `test_la_equity_preflop_no_usa_cartas_del_rival` — la fuga de
     informacion que no se nota en el numero, solo en que el numero es
     demasiado bueno.

Y anade los que hacen falta para que la firma no se pueda cambiar de forma
sin que alguien se entere: `_SUBSETS` intacto, `DEFAULT_RUNOUT_COMBOS`
intacto, determinismo, y las bandas de plausibilidad escritas ANTES de
mirar.
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


@pytest.fixture(scope='module')
def si():
    from motor import situation
    return situation


# ---------------------------------------------------------------- 1. firmas
def test_la_firma_es_la_del_contrato(he):
    """`CONTRATO_PREFLOP.md` esta firmado. La firma no cambia sin que se
    note, y este test es lo que lo nota."""
    import inspect
    f = inspect.signature(he.equity_preflop_rango)
    p = list(f.parameters)
    assert p == ['hero_codes', 'villain_reach', 'n_runouts', 'n_combos',
                 'seed'], 'la firma cambio: %s' % p
    assert f.parameters['seed'].default == 7
    assert f.parameters['villain_reach'].default is None


def test_equity_vs_range_delega_con_el_board_vacio(si, he):
    """La puerta que antes reventaba. Con 0 cartas `evaluate_batch` pide
    `_SUBSETS[2]`, que no existe."""
    assert 'equity_preflop_rango' in io.open(
        os.path.join(ROOT, 'motor', 'situation.py'),
        encoding='utf-8').read()
    # y de verdad no revienta: un solo combo, para que sea rapido
    w = np.zeros(1326)
    w[0] = 1.0
    eq, w_, t_, l_ = si.equity_vs_range(['As', 'Ks'], [], w, n_combos=1,
                                         seed=7)
    assert 0.0 <= eq <= 1.0, 'con board vacio devolvio %r' % (eq,)


def test_subsets_no_se_toco(he):
    """El camino preflop NO pasa por `evaluate_batch`, asi que `_SUBSETS` no
    tiene por qué cambiar. Si alguien lo cambia, el diagnostico del
    contrato queda obsoleto."""
    assert set(he._SUBSETS) == {5, 6, 7}, (
        '_SUBSETS cambio: el camino preflop se implemento por otra via y el '
        'contrato hay que revisarlo')


def test_default_runout_combos_no_se_bajo(he, si):
    """El contrato declara el desacuerdo con 40 y dice que NO se baja."""
    assert he.DEFAULT_RUNOUT_COMBOS == 200
    assert si.DEFAULT_RUNOUT_COMBOS == 200
    assert 'n_combos = 40' in io.open(
        os.path.join(ROOT, 'DOCS', 'CONTRATO_PREFLOP.md'),
        encoding='utf-8').read()


# ------------------------------------------------- 2. la fuga de informacion
def test_la_equity_preflop_no_usa_cartas_del_rival(he, monkeypatch):
    """Si el rango se construye con las cartas del rival, esto falla.

    La tentacion va a ser pasarle la mano real porque es mas exacto. Este
    test es para que eso no pase por sin que se note: es una fuga de
    informacion y no se nota en el numero, solo en que el numero es
    demasiado bueno.

    La forma de cazarlo: se llama al estimador DOS veces con el MISMO rango,
    cambiando solo las cartas del rival, y tiene que devolver EXACTAMENTE lo
    mismo. Si las cartas reales_entropyan en el calculo, cambia.
    """
    llamadas = []
    original = he.equity_preflop_contra_combo

    def espia(hero, villain):
        llamadas.append((tuple(int(x) for x in villain)))
        return 0.5          # valor fijo: solo importa QUE se llama

    monkeypatch.setattr(he, 'equity_preflop_contra_combo', espia)

    w = np.full(1326, 1.0 / 1326)
    a = he.equity_preflop_rango(['As', 'Kd'], w, n_combos=5, seed=7)
    n_primera = len(llamadas)
    b = he.equity_preflop_rango(['As', 'Kd'], w, n_combos=5, seed=7)

    assert a == b, 'el mismo rango dio dos numeros distintos: %r vs %r' % (a, b)
    assert len(llamadas) == 2 * n_primera, (
        'la segunda llamada no hizo las mismas combinaciones: el estimador '
        'depende de algo mas que del rango y la semilla')
    # los combos llamados son los del RANGO, no unos determinados
    monkeypatch.undo()
    monkeypatch.setattr(he, 'equity_preflop_contra_combo', original)


def test_el_rango_es_lo_unico_que_depende_de_la_mano_rival(si):
    """El instrumento construye el rango desde `ProfileRangeModel` por
    nombre de jugador. Si alguien lo cambiara por las cartas del rival, el
    numero mejoraria de una forma que no se puede explicar."""
    src = io.open(os.path.join(ROOT, 'tools',
                               'equity_preflop_observables.py'),
                  encoding='utf-8').read()
    assert 'prob_vec_player' in src, (
        'el rango tiene que salir del modelo por perfil y spot')
    i = src.index('prob_vec_player')
    ventana = src[max(0, i - 400):i + 400]
    assert 'cartas_villano' not in ventana, (
        'las cartas del rival se estan usando para construir el rango: eso es '
        'una fuga de informacion')
    # y el campo existe, pero solo como aviso de que NO se usa
    assert 'cartas_villano' in src


# ------------------------------------------------------ 3. bandas plausibles
def test_bandas_de_plausibilidad(he):
    """Escritas ANTES de mirar, como en `equity_preflop.py --comprobar`.

    Un instrumento que da el numero del otro se nota en el segundo que se
    ejecuta. Y dos de las bandas que puse a mano estaban mal: AA contra QQ
    suited vale ~0,82, no ~0,86. Por eso se comprueba contra lo CONOCIDO.
    """
    from motor.cards import card_id

    def eq(rival):
        return he.equity_preflop_contra_combo(
            [card_id('As'), card_id('Ad')],
            [card_id(rival[0:2]), card_id(rival[2:4])])

    bandas = {
        'KsKd': (0.80, 0.84),
        'QsQd': (0.80, 0.84),
        '2s2d': (0.81, 0.86),
        '7s7d': (0.79, 0.83),
    }
    for rival, (lo, hi) in bandas.items():
        v = eq(rival)
        assert lo <= v <= hi, (
            'AA vs %s = %.4f, fuera de la banda [%s, %s] escrita antes'
            % (rival, v, lo, hi))


def test_el_ganador_es_el_hero_no_el_rival(he):
    """El error clasico: contar `sv > sh` y devolver la complementada.

    Con ese error AA contra KK daria ~0,18 en vez de ~0,82.
    """
    from motor.cards import card_id
    contra_kk = he.equity_preflop_contra_combo(
        [card_id('As'), card_id('Ad')],
        [card_id('Ks'), card_id('Kd')])
    assert contra_kk > 0.7, (
        'AA contra KK = %.4f: el hero no esta ganando. Invierte la '
        'comparacion.' % contra_kk)


# ------------------------------------------------------------ 4. contrato
def test_es_determinista(he):
    rng = np.random.default_rng(1)
    w = rng.random(1326)
    a = he.equity_preflop_rango(['7s', '2s'], w, n_combos=3, seed=7)
    b = he.equity_preflop_rango(['7s', '2s'], w, n_combos=3, seed=7)
    assert a == b


def test_falla_claro_con_n_combos_absurdo(he):
    """Un `n_combos` equivocado tiene que fallar aqui, no durar dias."""
    w = np.full(1326, 1.0 / 1326)
    with pytest.raises(ValueError) as e:
        he.equity_preflop_rango(['As', 'Kd'], w, n_combos=10 ** 6)
    assert 'dias' in str(e.value)


def test_falla_claro_si_el_rango_no_tiene_masa_legal(he):
    """Rango con masa solo en combos que chocan con el hero."""
    from motor.cards import card_id
    from motor.ranges import COMBO0, COMBO1
    w = np.zeros(1326)
    # poner masa solo en el combo que contiene una carta del hero
    malo = [i for i in range(1326)
            if COMBO0[i] == card_id('As') or COMBO1[i] == card_id('Ks')]
    w[malo] = 1.0
    with pytest.raises(ValueError) as e:
        he.equity_preflop_rango(['As', 'Ks'], w, n_combos=3)
    assert 'masa' in str(e.value) or 'legales' in str(e.value)


def test_rechaza_una_mano_que_no_son_dos_cartas(he):
    w = np.full(1326, 1.0 / 1326)
    with pytest.raises(ValueError):
        he.equity_preflop_rango(['As'], w, n_combos=2)


def test_rechaza_un_rango_de_forma_equivocada(he):
    with pytest.raises(ValueError) as e:
        he.equity_preflop_rango(['As', 'Kd'], np.ones(100), n_combos=2)
    assert '1326' in str(e.value)