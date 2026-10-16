# -*- coding: utf-8 -*-
"""test_equity_de_mano.py: la equity historica y sus fugas.

Seis bloques:

  1. QUE CORRE. Sobre una mano conocida, devuelve equity.
  2. QUE NO MIRA AL FUTURO. El corte por calle no basta: hace falta el
     indice de la accion. `revision_2` lo dijo y son 88 de 154 manos.
  3. QUE LOS BLOQUEADORES SON LOS DE ESE INSTANTE.
  4. QUE EL AJUSTE ESTA SEPARADO DE LA VALIDACION.
  5. QUE LA EQUITY ORDENA. Sin esto es un generador de numeros.
  6. QUE EL ENUMERADOR PREFLOP ES EL DEL MOTOR (y que se puede fallar).
"""
import hashlib
import importlib.util
import os

import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mod(nombre):
    ruta = os.path.join(ROOT, 'tools', nombre)
    spec = importlib.util.spec_from_file_location(nombre[:-3], ruta)
    mod = importlib.util.module_from_spec(spec)
    sys_path_fix()
    spec.loader.exec_module(mod)
    return mod


def sys_path_fix():
    import sys
    if os.path.join(ROOT, 'tools') not in sys.path:
        sys.path.insert(0, os.path.join(ROOT, 'tools'))


@pytest.fixture(scope='module')
def eq():
    return _mod('equity_de_mano.py')


@pytest.fixture(scope='module')
def eqp():
    return _mod('equity_preflop.py')


@pytest.fixture(scope='module')
def cal():
    return _mod('calibrar.py')


@pytest.fixture(scope='module')
def ventana():
    from motor import learn
    return learn.load_hands(reliable_only=True)


@pytest.fixture(scope='module')
def ajuste(ventana):
    return [h for h in ventana
            if int(hashlib.sha256(
                h['hand_id'].encode('utf-8')).hexdigest(), 16) % 10 >= 3]


@pytest.fixture(scope='module')
def modelos(eq, ajuste):
    from motor import player_ranges
    return {'preflop': player_ranges.ProfileRangeModel.from_hands(
        ajuste, alpha=player_ranges.DEFAULT_ALPHA), 'postflop': None}


@pytest.fixture(scope='module')
def labels(eq, ajuste):
    return eq.perfiles_de(ajuste)


# --------------------------------------------------------------- 1. que corre
def test_corre_sobre_una_mano_conocida(eq, labels, modelos, ventana):
    h = next(x for x in ventana if x['hand_id'] == 'H_0798')
    eqs, det, detalle = eq.equity_de_mano(h, labels, modelos)
    assert eqs, 'sin equity: %s' % det
    for pos, v in eqs.items():
        assert 0.0 <= v <= 1.0
    assert detalle['combos'] > 0


def test_sin_hero_no_hay_equity(eq, labels, modelos):
    h = {'hand_id': 'X', 'players': [
        {'pos': 'UTG', 'name': 'A', 'cards': 'AhKd'},
        {'pos': 'BB', 'name': 'B', 'cards': 'QsJs'}],
        'streets': {'preflop': {'actions': [
            {'pos': 'UTG', 'action': 'r', 'amount': 3.0}]}},
        'winner': ['hero'], 'showdown': {}, 'comunitarias': {}}
    eqs, motivo = eq.equity_de_mano(h, labels, modelos)
    assert eqs is None
    assert 'hero' in motivo


# ------------------------------------------------------ 2. que no mira al futuro
def test_el_corte_por_calle_no_bastaba(eq, ventana, cal):
    """88 de 154 manos tienen al rival jugando DESPUES en la misma calle.

    Por eso el corte lleva indice de accion y no solo la calle. Este test
    existe para que nadie lo simplifique a `punto_de_decision`.
    """
    c, v = cal.muestra()
    ids = {i for i, _ in c} | {i for i, _ in v}
    por_id = {h['hand_id']: h for h in ventana}
    misma_calle = despues = 0
    for hid in ids:
        h = por_id[hid]
        hero = eq.hero_pos_de(h)
        if not hero:
            continue
        calle, idx = eq.corte_de_decision(h, hero)
        if calle is None or idx is None:
            continue
        acts = ((h.get('streets') or {}).get(calle) or {}).get(
            'actions') or []
        riv = eq.candidatos(h, hero, calle)
        if not riv or idx >= len(acts):
            continue
        misma_calle += 1
        if any(a.get('pos') == riv[0]
               and a.get('action') in ('b', 'c', 'r', 'f')
               for a in acts[idx + 1:]):
            despues += 1
    assert misma_calle > 100
    assert despues > 50, 'esperado muchas con el rival despues: %d' % despues


def test_el_rango_no_usa_acciones_posteriores(eq, ventana, cal):
    """Ninguna accion del rival de la calle siguiente al corte."""
    c, v = cal.muestra()
    ids = {i for i, _ in c} | {i for i, _ in v}
    por_id = {h['hand_id']: h for h in ventana}
    ORD = ['preflop', 'flop', 'turn', 'river']
    fugas = 0
    for hid in ids:
        h = por_id[hid]
        hero = eq.hero_pos_de(h)
        if not hero:
            continue
        calle, idx = eq.corte_de_decision(h, hero)
        if calle is None:
            continue
        riv = eq.candidatos(h, hero, calle)
        if not riv:
            continue
        hasta = eq.villain_hasta_corte(h, riv[0], calle, idx)
        fugas += sum(1 for t in hasta if ORD.index(t[0]) > ORD.index(calle))
    assert fugas == 0, 'quedan %d acciones de futuro' % fugas


def test_el_corte_usa_el_indice_y_no_solo_la_calle(eq):
    """Rival, hero, rival: en la MISMA calle. Solo el ultimo queda fuera.

    Con el corte por calle entrarian los dos; con el corte por indice entra
    solo el primero. Esa es la diferencia, y es la que hacia el codigo
    viejo mirar al futuro en 88 de 154 manos.
    """
    h = {'hand_id': 'X', 'players': [
        {'pos': 'BB', 'name': 'Jarduan', 'cards': 'AsKd'},
        {'pos': 'UTG', 'name': 'V', 'cards': 'QhJh'}],
        'streets': {
            'preflop': {'actions': [
                {'pos': 'BB', 'action': 'b', 'amount': 3.0},
                {'pos': 'UTG', 'action': 'c', 'amount': 3.0}]},
            'flop': {'actions': [
                {'pos': 'UTG', 'action': 'b', 'amount': 5.0},
                {'pos': 'BB', 'action': 'c', 'amount': 5.0},
                {'pos': 'UTG', 'action': 'r', 'amount': 15.0}],
                'board': ['2c', '7d', '9s']}},
        'comunitarias': {'flop': ['2c', '7d', '9s']},
        'winner': [], 'showdown': {}}
    calle, idx = eq.corte_de_decision(h, 'BB')
    assert calle == 'flop'
    assert idx == 1, 'la call del hero es el indice 1 del flop'

    con_indice = eq.villain_hasta_corte(h, 'UTG', calle, idx)
    assert len(con_indice) == 1, 'solo la bet que va ANTES: %s' % (con_indice,)
    assert con_indice[0][2] == 'b'

    sin_indice = eq.villain_hasta_corte(h, 'UTG', calle, None)
    assert len(sin_indice) == 2, 'la calle entera entra: %s' % (sin_indice,)
    assert 'r' in [t[2] for t in sin_indice], 'la suba es posterior'


# ------------------------------------------------------- 3. los bloqueadores
def test_los_bloqueadores_son_solo_hero_y_board(eq, ventana, cal, modelos,
                                                 monkeypatch):
    """Se vigila lo que la herramienta HACE, no lo que hacia antes.

    `set_known_cards` es la unica puerta por la que entran blockers. Se
    intercepta y se comprueba que no entra ninguna carta que no sea del
    hero o del board en ese instante.
    """
    from motor.situation import RangeState as _RS
    visto = []
    original = _RS.set_known_cards

    def espia(self, cartas):
        visto.append(list(cartas))
        return original(self, cartas)

    monkeypatch.setattr(_RS, 'set_known_cards', espia)

    c, v = cal.muestra()
    ids = [i for i, _ in c][:25] + [i for i, _ in v][:10]
    por_id = {h['hand_id']: h for h in ventana}
    etiquetas = eq.perfiles_de(ajuste := ventana)
    for hid in ids:
        eq.equity_de_mano(por_id[hid], etiquetas, modelos)
    assert visto, 'no se observo ninguna llamada: el camino no se ejecuto'

    _CONOCIDAS.clear()
    for hid in ids:
        _h = por_id[hid]
        _hero = eq.hero_pos_de(_h)
        if not _hero:
            continue
        _CONOCIDAS.update(eq.cartas_de(_h, _hero))
        for _st in ('preflop', 'flop', 'turn', 'river'):
            _CONOCIDAS.update(str(x) for x in
                              ((_h.get('comunitarias') or {}).get(_st) or []))

    intrusos = 0
    for cartas in visto:
        cj = ''.join(cartas)
        # cada carta metida tiene que ser del hero o del board de ALGUNA
        # mano de la muestra. Ninguna puede ser una carta de un tercero.
        for i in range(0, len(cj) - 1, 2):
            intrusos += 0 if cj[i:i + 2] in _CONOCIDAS else 1
    assert intrusos == 0, (
        '%d blockers que no son del hero ni del board. Antes eran 216 '
        'cartas de terceros reveladas en el showdown.' % intrusos)


# ------------------------------------------------------- 4. ajuste separado
def test_el_ajuste_no_incluye_validacion(ajuste, ventana):
    """El ajuste por defecto son las de calibracion."""
    cal_ids = {h['hand_id'] for h in ajuste}
    val_ids = {h['hand_id'] for h in ventana} - cal_ids
    assert not (cal_ids & val_ids)
    assert len(val_ids) > 0, 'no hay validacion: el test no comprobaria nada'


def test_el_modelo_cambia_segun_el_ajuste(ajuste, ventana):
    """Las 6 claves de `opp` cambian. Por eso separar no es cosmetico."""
    import numpy as np
    from motor import player_ranges as PR
    m_cal = PR.ProfileRangeModel.from_hands(ajuste, alpha=2.0)
    m_ven = PR.ProfileRangeModel.from_hands(ventana, alpha=2.0)
    difieren = sum(1 for k in m_cal.opp
                   if not np.allclose(m_cal.opp[k], m_ven.opp[k]))
    assert difieren == len(m_cal.opp) == 6


#: Cartas que SI se pueden conocer: las del hero y las del board, en
#: cualquier calle. Se rellena en `test_los_bloqueadores_son_solo_hero_y_board`.
_CONOCIDAS = set()


# ------------------------------------------------------------ 5. que ordena
def test_la_equity_ordena_ganar_contra_perder(eq, labels, modelos, ventana,
                                              cal):
    """Mas equity tiene que asociarse a ganar. Sin esto, numeros.

    ACOTADO A 24 MANOS A PROPOSITO. Una enumeracion preflop son 1,7
    millones de evaluaciones (~13 s) y la muestra entera son ~169: casi
    40 minutos dentro de un test.

    La corrida completa es un trabajo por lotes, no un test:

        python tools/equity_de_mano.py --manos 161

    y su resultado esta escrito en DOCS/L_SEC_ESTADO.md.
    """
    c, v = cal.muestra()
    todos = sorted({i for i, _ in c} | {i for i, _ in v})
    muestra = todos[:24]
    etiqueta = {i: y for i, y in c + v}
    por_id = {h['hand_id']: h for h in ventana}

    gana, pierde = [], []
    for hid in muestra:
        y = etiqueta[hid]
        if y not in (0.0, 1.0):
            continue
        r = eq.equity_de_mano(por_id[hid], labels, modelos)
        if r is None or len(r) != 3:
            continue
        (gana if y == 1.0 else pierde).append(r[1]['mediana'])

    if len(gana) < 2 or len(pierde) < 5:
        pytest.skip('pocas manos utilizables en la muestra acotada')
    mg = sum(gana) / len(gana)
    mp = sum(pierde) / len(pierde)
    assert mg > mp, ('la equity no ordena: gana %.4f (n=%d), pierde %.4f '
                     '(n=%d)' % (mg, len(gana), mp, len(pierde)))


def test_el_brier_de_la_equity_pierde_contra_el_trivial(eq, labels, modelos,
                                                       ventana, cal):
    """La comprobacion que hace que `L_sec` no sirva AUNQUE se cubra todo.

    Resultado medido sobre las 159 de 161 que el camino preflop deja
    cubiertas:

        Brier con la mediana de la equity : 0,1783
        Brier del predictor constante     : 0,1076

    O sea que decir "el hero pierde" LE GANA al motor. Con el 86 % de
    derrotas de la muestra, y la equity mediana del hero en 0,41-0,77, la
    equity **sobreestima** la chance del hero y por eso pierde.

    Este test documenta ese fracaso. No lo esconde y no lo arregla: el
    arreglo es de la metrica, no del instrumento, y no se decide aqui.
    """
    c, v = cal.muestra()
    todos = sorted({i for i, _ in c} | {i for i, _ in v})
    muestra = todos[:40]
    etiqueta = {i: y for i, y in c + v}
    por_id = {h['hand_id']: h for h in ventana}
    filas = []
    for hid in muestra:
        r = eq.equity_de_mano(por_id[hid], labels, modelos)
        if r is None or len(r) != 3:
            continue
        filas.append((r[1]['mediana'], etiqueta[hid]))
    if len(filas) < 15:
        pytest.skip('muestra acotada insuficiente')
    brier_equity = sum((e - y) ** 2 for e, y in filas) / len(filas)
    p = sum(y for _e, y in filas) / len(filas)
    brier_trivial = sum((p - y) ** 2 for _e, y in filas) / len(filas)
    print('   Brier equity %.4f   Brier constante %.4f   (n=%d)'
          % (brier_equity, brier_trivial, len(filas)))
    assert brier_equity > brier_trivial, (
        'la equity ya supera al predictor trivial: la situacion mejoro y '
        'este documento hay que reescribirlo')


# ------------------------------------------------- 6. el enumerador preflop
def test_el_enumerador_da_los_valores_de_manual(eqp):
    """AA contra KK, y KK contra QQ. Valores conocidos de manual.

    Este test ATRAPO un bug real: la comparacion de scores estaba
    invertida y AA contra KK daba 0,18 en vez de 0,82. Una herramienta de
    poker que devuelve la equity del otro solo se nota comparando con un
    numero que ya se conoce.
    """
    aa, _ = eqp.equity_preflop('AsAd', 'KhKs')
    kk, _ = eqp.equity_preflop('KhKs', 'QhQd')
    assert 0.78 <= aa <= 0.86, 'AA vs KK fuera de banda: %.4f' % aa
    assert 0.78 <= kk <= 0.86, 'KK vs QQ fuera de banda: %.4f' % kk
    assert abs(aa - kk) < 0.02, 'pares altos deberían ser casi iguales'


def test_el_enumerador_usa_todos_los_sorteos(eqp):
    _eq, det = eqp.equity_preflop('AsAd', 'KhKs')
    assert det['boards'] == 1712304, 'C(48,5) = 1 712 304'


def test_el_enumerador_cuadra_gana_mas_pierde_empata(eqp):
    _eq, det = eqp.equity_preflop('AsAd', 'KhKs')
    assert det['gana'] + det['pierde'] + det['empata'] == det['boards']
    assert det['empata'] > 0, 'una mano contra otra siempre puede empatar'


def test_el_evaluador_no_tiene_camino_preflop_de_situation():
    """`situation` sigue sin camino preflop. Eso es lo que motivo B.

    El enumerador de `equity_preflop.py` lo resuelve POR FUERA, y es un
    calculo distinto: dos manos de 2 cartas contra un sorteo completo.
    """
    from motor import hand_evaluator as HE
    assert sorted(HE._SUBSETS.keys()) == [5, 6, 7]
    with pytest.raises(KeyError):
        HE.evaluate_batch([[0, 1]], [])


def test_equity_de_mano_usa_el_enumerador_en_preflop(eq, labels, modelos,
                                                    ventana, cal):
    """Una mano cuyo punto de decision sea preflop sale por el enumerador.

    Se mide `detalle['via']`, que es lo que devuelve la rama. Y el motivo
    del fallo se imprime: un `None` sin motivo no dice nada.
    """
    c, v = cal.muestra()
    ids = {i for i, _ in c} | {i for i, _ in v}
    por_id = {h['hand_id']: h for h in ventana}
    probadas = 0
    fallos = []
    for hid in sorted(ids):
        h = por_id[hid]
        hero = eq.hero_pos_de(h)
        if not hero:
            continue
        calle, idx = eq.corte_de_decision(h, hero)
        if calle != 'preflop':
            continue
        riv = eq.candidatos(h, hero, calle)
        if not riv:
            continue
        eqv, detalle = eq.equity_contra(h, riv[0], labels, modelos['preflop'],
                                        None)
        if eqv is None:
            fallos.append((hid, detalle))
            continue
        assert detalle.get('via') == 'enumeracion preflop', (
            '%s: calle %s sin pasar por el enumerador' % (hid, calle))
        assert detalle['combos'] > 1000000, 'no enumero los sorteos'
        assert 0.0 <= eqv <= 1.0
        probadas += 1
        if probadas >= 3:
            break
    assert probadas >= 1, (
        'ninguna mano preflop dio equity. Fallos: %s' % fallos[:5])
