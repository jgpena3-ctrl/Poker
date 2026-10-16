# -*- coding: utf-8 -*-
"""`tools/equity_de_mano.py` — equity historica, y sus limites.

Cinco bloques:

  1. QUE CORRE. Sobre una mano conocida, devuelve equity. Sin partida y sin
     captura: eso es lo que la hace historica.
  2. QUE ES LA DEL MOTOR. Que use la misma cadena que `asistente_live`:
     rango preflop -> blockers -> refinado postflop -> `situation`.
  3. QUE LA EQUITY NO USA EL BOTE. Es lo que permite que la herramienta
     exista sin resolver la aritmetica de las apuestas (que no converge).
  4. QUE DICE POR QUE NO PUEDE. Un instrumento que traga el motivo hace que
     96 fallos distintos parezcan uno.
  5. QUE SE PUEDE FALLAR. Sin esto seria un generador de numeros.
"""
import importlib.util
import os

import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def eq():
    ruta = os.path.join(ROOT, 'tools', 'equity_de_mano.py')
    spec = importlib.util.spec_from_file_location('equity_de_mano', ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope='module')
def modelos(eq):
    from motor import learn, player_ranges
    ventana = learn.load_hands(reliable_only=True)
    return {'preflop': player_ranges.ProfileRangeModel.from_hands(
        ventana, alpha=player_ranges.DEFAULT_ALPHA), 'postflop': None}


@pytest.fixture(scope='module')
def ventana():
    from motor import learn
    return learn.load_hands(reliable_only=True)


@pytest.fixture(scope='module')
def labels(eq, ventana):
    return eq.perfiles_de(ventana)


# --------------------------------------------------------------- 1. que corre
def test_corre_sobre_una_mano_conocida(eq, labels, modelos, ventana):
    h = next(x for x in ventana if x['hand_id'] == 'H_0798')
    r = eq.equity_de_mano(h, labels, modelos)
    assert r is not None
    assert len(r) == 3, 'sin equity: %s' % r[1]
    eqs, det, detalle = r
    assert eqs, 'no hay ningun rival con equity'
    for pos, v in eqs.items():
        assert 0.0 <= v <= 1.0, 'equity fuera de rango: %r' % v
    assert det['calle'] in ('preflop', 'flop', 'turn', 'river')
    assert detalle['combos'] > 0, 'no evaluo ningun combo'


def test_una_mano_sin_hero_no_inventa_etiqueta(eq, labels, modelos):
    h = {'hand_id': 'X', 'players': [
        {'pos': 'UTG', 'name': 'A', 'cards': 'AhKd'},
        {'pos': 'BB', 'name': 'B', 'cards': 'QsJs'}],
        'streets': {'preflop': {'actions': [
            {'pos': 'UTG', 'action': 'r', 'amount': 3.0},
            {'pos': 'BB', 'action': 'f', 'amount': 0.0}]}},
        'winner': ['hero'], 'showdown': {}, 'comunitarias': {}}
    eqs, motivo = eq.equity_de_mano(h, labels, modelos)
    assert eqs is None
    assert 'hero' in motivo


def test_una_mano_sin_cartas_no_da_equity(eq, labels, modelos):
    h = {'hand_id': 'X', 'players': [
        {'pos': 'UTG', 'name': 'Jarduan', 'cards': ''},
        {'pos': 'BB', 'name': 'B', 'cards': 'QsJs'}],
        'streets': {'preflop': {'actions': [
            {'pos': 'UTG', 'action': 'f', 'amount': 0.0}]}},
        'winner': [], 'showdown': {}, 'comunitarias': {}}
    eqs, motivo = eq.equity_de_mano(h, labels, modelos)
    assert eqs is None
    assert 'cartas' in motivo


# ---------------------------------------------------------- 2. que es la del
def test_usa_la_cadena_del_motor_vivo(eq, ventana, labels, modelos):
    """`_preflop_spot` decide el punto del rango, como en `asistente_live`."""
    import motor.asistente_live as A
    h = next(x for x in ventana if x['hand_id'] == 'H_0798')
    hero = eq.hero_pos_de(h)
    rivales = eq.candidatos(h, hero, 'river')
    assert rivales, 'H_0798 deberia tener rival vivo en river'
    spot, action = A._preflop_spot(h, rivales[0])
    assert spot in ('no_raise', 'facing_open', 'facing_3bet')
    assert action


def test_el_perfil_se_saca_del_nombre_del_rival(eq, ventana, labels,
                                                 modelos):
    h = next(x for x in ventana if x['hand_id'] == 'H_0798')
    hero = eq.hero_pos_de(h)
    r = eq.equity_de_mano(h, labels, modelos)
    assert r is not None and len(r) == 3
    _eqs, _det, detalle = r
    assert detalle['perfil'] in ('PEZ', 'TIBURON')


# ---------------------------------------------------- 3. la equity y el bote
def test_la_equity_no_usa_el_bote(eq, labels, modelos, ventana):
    """Cambiar el bote no cambia la equity. Por eso esta herramienta existe.

    `situation()` calcula `equity = wins + 0.5*ties` desde las cartas y el
    rango. El bote solo alimenta `pot_odds` y `spr`. Si esto fallara, habria
    que reconstruir las apuestas, y esa aritmetica NO converge (medido: 26
    de 877 coinciden con `final_pot`).
    """
    from motor.situation import situation
    hero = ['As', 'Kd']
    board = ['Qc', 'Jh', 'Ts']
    s1 = situation(hero, board, pot_before_call=10.0, to_call=5.0)
    s2 = situation(hero, board, pot_before_call=999.0, to_call=1.0)
    assert s1.equity == s2.equity
    assert s1.pot_odds != s2.pot_odds, 'el pot si cambia el pot_odds'


def test_el_evaluador_no_tiene_camino_preflop():
    """POR QUE `L_sec` no sale, y esta escrito antes de que se pregunte.

    `hand_evaluator.evaluate_batch` declara board de **3 a 5** cartas, y sus
    subsets son para manos de 5, 6 y 7 cartas. Con board vacio no hay
    subset, y preflop son **96 de las 156** manos de la muestra.
    """
    from motor import hand_evaluator as HE
    assert sorted(HE._SUBSETS.keys()) == [5, 6, 7]
    with pytest.raises(KeyError):
        HE.evaluate_batch([[0, 1]], [])


# --------------------------------------------- 4. que dice por que no puede
def test_el_motivo_del_fallo_no_se_traga(eq, labels, modelos, ventana):
    """96 manos fallan por lo mismo. Si el motivo se tragara, 96 fallos
    distintos parecerian uno y nadie podria distinguirlos."""
    h = next(x for x in ventana if x['hand_id'] == 'H_0038')
    hero = eq.hero_pos_de(h)
    assert eq.punto_de_decision(h, hero) == 'preflop'
    eqs, motivo = eq.equity_de_mano(h, labels, modelos)
    assert eqs is None
    assert motivo and motivo != 'ningun rival dio equity'
    assert 'situation fallo' in motivo or 'KeyError' in motivo


# ------------------------------------------------------ 5. que se puede fallar
def test_la_equity_ordena_ganar_contra_perder(eq, labels, modelos,
                                              ventana):
    """La comprobacion externa: mas equity tiene que asociarse a ganar.

    Sin esto la herramienta seria un generador de numeros con docstring.
    """
    import hashlib
    from motor import learn
    cal_spec = importlib.util.spec_from_file_location(
        'cal', os.path.join(ROOT, 'tools', 'calibrar.py'))
    cal = importlib.util.module_from_spec(cal_spec)
    cal_spec.loader.exec_module(cal)
    c, v = cal.muestra()
    etiqueta = {i: y for i, y in c + v}
    por_id = {h['hand_id']: h for h in ventana}

    gana, pierde = [], []
    for hid, y in etiqueta.items():
        r = eq.equity_de_mano(por_id[hid], labels, modelos)
        if r is None or len(r) != 3:
            continue
        (gana if y == 1.0 else pierde).append(r[1]['mediana'])

    assert len(gana) >= 15, 'muestra de victorias demasiado pequena: %d' \
        % len(gana)
    assert len(pierde) >= 25, 'muestra de derrotas demasiado pequena: %d' \
        % len(pierde)
    media_g = sum(gana) / len(gana)
    media_p = sum(pierde) / len(pierde)
    assert media_g > media_p, (
        'la equity NO ordena: gana %.4f, pierde %.4f. Si esto falla, la '
        'herramienta no sirve' % (media_g, media_p))


def test_la_cobertura_esta_sesgada_y_eso_se_declara(eq, labels, modelos,
                                                    ventana):
    """La cobertura no es neutra, y por eso `L_sec` no es usable aun.

    Cubre 20 de 21 victorias (95 %) y 38 de 135 derrotas (28 %). Medir
    `L_sec` sobre lo cubierto seria medir sobre una muestra que es casi
    solo de manos ganadas.
    """
    cal_spec = importlib.util.spec_from_file_location(
        'cal2', os.path.join(ROOT, 'tools', 'calibrar.py'))
    cal = importlib.util.module_from_spec(cal_spec)
    cal_spec.loader.exec_module(cal)
    c, v = cal.muestra()
    etiqueta = {i: y for i, y in c + v}
    por_id = {h['hand_id']: h for h in ventana}

    cub = {'gana': 0, 'pierde': 0}
    tot = {'gana': 0, 'pierde': 0}
    for hid, y in etiqueta.items():
        tot['gana' if y == 1.0 else 'pierde'] += 1
        r = eq.equity_de_mano(por_id[hid], labels, modelos)
        if r is not None and len(r) == 3:
            cub['gana' if y == 1.0 else 'pierde'] += 1

    assert tot['gana'] == 21 and tot['pierde'] == 135
    tasa_g = cub['gana'] / tot['gana']
    tasa_p = cub['pierde'] / tot['pierde']
    assert tasa_g > 3 * tasa_p, (
        'esperado: la cobertura de victorias es mucho mayor que la de '
        'derrotas (%.2f vs %.2f). Si ya no se cumple, el sesgo cambio y '
        'hay que reescribir la conclusion' % (tasa_g, tasa_p))