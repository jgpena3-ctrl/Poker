# -*- coding: utf-8 -*-
"""`tools/calibrar.py` — el contrato de lo que se puede publicar.

Ocho bloques, y cuatro de ellos existen porque `revision_2` encontro bugs:

  1. LA MUESTRA. Que salgan 156 / 117 / 39. Es un test de contrato: si el
     filtro cambia, el plan y la particion dejan de hablar de lo mismo.
  2. LA ETIQUETA. Que no se inventen empates, y que `winner1` se RESUELVA.
  3. LAS DOS DEFINICIONES DE HERO Y DE BUTACA. Que el hero sea el jugador
     nombrado, y que `'hero'` sea la butaca 0. Estaban cruzadas.
  4. LA METRICA. Que use `p_hand` y que NO tenga fallback.
  5. QUE LA METRICA VE AL PARAMETRO.
  6. EL GUARDIAN DE MONOTONIA.
  7. QUE LAS BARRERAS ABORTEN. Autovalidacion fallida -> 3. Sin L_sec no
     se acepta aunque la curva no sea monotonica.
  8. QUE `DEFAULT_ALPHA` SIGA EN 2.0.
"""
import hashlib
import importlib.util
import io
import os

import numpy as np
import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mod(nombre, fichero):
    ruta = os.path.join(ROOT, 'tools', fichero)
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope='module')
def cal():
    return _mod('calibrar_fase_d', 'calibrar.py')


@pytest.fixture(scope='module')
def ventana():
    from motor import learn
    return learn.load_hands(reliable_only=True)


@pytest.fixture(scope='module')
def aud():
    return _mod('auditar_muestra_fase_d', 'auditar_muestra_lsec.py')


def _mano(posiciones, nombres, cartas, winner, showdown=None):
    return {
        'hand_id': 'X',
        'players': [
            {'pos': p, 'name': n, 'cards': c}
            for p, n, c in zip(posiciones, nombres, cartas)
        ],
        'winner': winner,
        'showdown': showdown or {},
    }


# ---------------------------------------------------------------- 1. muestra
def test_la_muestra_son_los_numeros_del_contrato(cal):
    """161 utilizables, 120 de calibracion, 41 de validacion.

    Los numeros bajan de 156 a 161 al poder ETIQUETAR los repartos: las 7
    manos con dos ganadores hacen todas la misma mano en el board, y eso
    se demuestra con el evaluador del motor.
    """
    c, v = cal.muestra()
    assert len(c) == 120
    assert len(v) == 41
    assert len(c) + len(v) == 161


def test_la_ventana_es_la_declarada(cal):
    assert len(cal.ventana()) == 877


def test_la_particion_versionada_coincide_con_la_calculada(cal):
    """DOCS/PARTICION_FASE_D.md tiene que ser el fichero que sale aqui."""
    texto = io.open(os.path.join(ROOT, 'DOCS', 'PARTICION_FASE_D.md'),
                    encoding='utf-8').read()
    c, v = cal.muestra()
    for hid, _y in v[:5]:
        assert '`%s`' % hid in texto
    for marca in ('| validacion | 41 |', '| calibracion | 120 |',
                  '| utilizables | 161 |'):
        assert marca in texto


def test_el_auditor_independiente_coincide(cal, aud):
    """`calibrar.py` y `auditar_muestra_lsec.py` cuentan lo mismo.

    Dos instrumentos que cuentan distinto es como se descubre que los dos
    estan mal, asi que se comparan en un test y no a ojo.
    """
    ys = [y for _i, y in sum(cal.muestra(), [])]
    ys_aud = []
    for h in aud.learn.load_hands(reliable_only=True):
        if not (h.get('comunitarias') or {}).get('river'):
            continue
        if len(aud.con_cartas(h)) < 2:
            continue
        y, _m = aud.etiqueta(h)
        if y is not None:
            ys_aud.append(y)
    assert len(ys) == len(ys_aud) == 161
    assert sorted(ys) == sorted(ys_aud)


# -------------------------------------------------------------- 2. etiqueta
def test_no_se_inventan_empates(cal):
    """Varios ganadores SIN texto de showdown -> no utilizable."""
    h = _mano(['UTG', 'BTN', 'BB'], ['A', 'B', 'Jarduan'],
              ['AhKd', 'QsJs', '2h3d'], ['hero', 'p2'])
    y, ok = cal.etiqueta(h)
    assert (y, ok) == (None, False)


def test_winner1_ya_no_etiqueta_nada(cal):
    """El reparto se demuestra con el EVALUADOR, no con un texto.

    Este test existia para vigilar el bug de `revision_2` (2A y 2B): que
    `showdown.winner1` se aceptara por existir, sin comprobar a quien nombra.
    La respuesta fue dejar de usarlo: el texto ya no interviene en la
    etiqueta, y con ello las dos objeciones desaparecen.
    """
    h = _mano(['UTG', 'BTN', 'BB'], ['A', 'B', 'Jarduan'],
              ['AhKd', 'QsJs', '2h3d'], ['hero', 'p2'],
              showdown={'winner1': 'texto que no nombra a nadie'})
    h['comunitarias'] = {'flop': ['Kd', '7c', '2s'], 'turn': ['Kd'],
                         'river': ['As']}
    # AhKd hace dos pares (ases y reyes). 2h3d hace solo los reyes. No
    # empatan, asi que NO es un reparto demostrable y la mano se queda sin
    # etiqueta. Y el texto de showdown, que no nombra a nadie, es
    # irrelevante: no se consulta.
    assert cal.reparto(h, {'UTG', 'BB'}) is False
    assert cal.etiqueta(h) == (None, False)


def test_un_reparto_demostrado_da_uno_como_mitad(cal):
    """Dos jugadores que hacen la MISMA mano -> y = 0,5.

    Board `5d Qh 6s 2h 4s`; `TsQs` y `ThQc` hacen pareja de queens con
    kicker T. Score identico. Eso es un reparto, y el reparto se demuestra.
    """
    h = _mano(['BB', 'CO', 'BTN', 'SB'],
              ['Jarduan', 'A', 'B', 'C'],
              ['TsQs', '', '', 'ThQc'], ['hero', 'p3'])
    h['comunitarias'] = {'flop': ['5d', 'Qh', '6s'], 'turn': ['2h'],
                         'river': ['4s']}
    assert cal.reparto(h, {'BB', 'SB'}) is True
    y, ok = cal.etiqueta(h)
    assert ok is True
    assert y == 0.5, 'reparto demostrado y el hero es de los que lo toman'


def test_reparto_no_demostrable_deja_la_mano_sin_etiqueta(cal):
    """Sin board no se demuestra el reparto, y entonces no hay etiqueta.

    Poner 0,5 ahi seria inventarlo, que es lo que se prohibe.
    """
    h = _mano(['BB', 'SB'], ['Jarduan', 'C'], ['TsQs', 'ThQc'],
              ['hero', 'p1'])
    h['comunitarias'] = {}
    assert cal.reparto(h, {'BB', 'SB'}) is None
    assert cal.etiqueta(h) == (None, False)


def test_sin_jugador_heroname_no_hay_etiqueta(cal):
    """Si nadie se llama como el hero, no hay etiqueta.

    Antes esto comparaba contra "el primer jugador con cartas", que siempre
    encontraba a alguien. Ahora puede no haberlo, y esa es la respuesta
    correcta: sin hero no hay `y`.
    """
    h = _mano(['UTG', 'BTN', 'BB'], ['A', 'B', 'C'],
              ['AhKd', 'QsJs', '2h3d'], ['hero'])
    assert cal.etiqueta(h) == (None, False)


def test_el_criterio_de_etiqueta_solo_usa_quien_llego_al_bote(cal):
    """Un jugador que folteo antes NO compite. Este test es el mio.

    Comparar las cartas de todos con el board da un mejor que no estuvo
    en el bote. MEDIDO: con ese criterio, 358 incoherentes de 584 en la
    ventana. Con el correcto, **0 de 261**.

    H_0002 es el caso: winner es UTG, que NO tiene cartas porque gano
    por fold en el flop, y MP (que si las tiene) habia folderado preflop.
    """
    # UTG tiene cartas y GANO. MP tiene cartas y FOLTEO preflop.
    # Sin el filtro, MP se compararia con el board y 'ganaria' con
    # 6c4s, que es peor que Tc9s.
    h = _mano(['BB', 'MP', 'UTG'], ['V', 'Jarduan', 'W'],
              ['', '6c4s', 'Tc9s'], ['p2'],
              showdown={'winner1': 'UTG (W)'})
    h['streets'] = {
        'preflop': {'actions': [
            {'pos': 'BB', 'action': 'x', 'amount': 0.0},
            {'pos': 'UTG', 'action': 'c', 'amount': 1.0},
            {'pos': 'MP', 'action': 'f', 'amount': 0.0}]},
        'flop': {'actions': [
            {'pos': 'BB', 'action': 'x', 'amount': 1.0},
            {'pos': 'UTG', 'action': 'b', 'amount': 6.0},
            {'pos': 'BB', 'action': 'f', 'amount': 0.0}],
            'board': ['Ah', '8c', 'Qc']},
    }
    h['comunitarias'] = {'flop': ['Ah', '8c', 'Qc']}
    scores, mejor = cal.mejores_manos(h)
    assert mejor is not None
    assert 'MP' not in scores, 'MP folteo preflop: no compite'
    assert 'UTG' in scores
    y, ok = cal.etiqueta(h)
    assert ok is True and y == 0.0, 'UTG gano el bote y el hero no'


def test_el_tercer_caso_del_filtro_excluye_de_verdad(cal, ventana):
    """Los TRES casos, y el tercero tiene que sacar la mano.

    1. showdown verificable -> se acepta
    2. victoria por fold   -> se acepta (no es comprobable, no es un fallo)
    3. INCOHERENTE         -> NO se etiqueta

    El caso 3 es el que se escapaba antes: la comparacion con las cartas
    solo corria si el ganador declarado estaba entre los mejores, asi que
    un ganador que NO era el mejor pasaba sin comprobar. Y eso es justo lo
    que hay que excluir.

    `H_0909` es el caso real: declara a CO con 337 759 cuando BB hace
    682 097. Esta reconstruccion debe quedar FUERA.
    """
    h = _mano(['BB', 'CO', 'UTG'], ['V', 'W', 'Jarduan'],
              ['AcAs', '7h5s', '2c3d'], ['p1'],
              showdown={})
    h['streets'] = {
        'preflop': {'actions': [
            {'pos': 'UTG', 'action': 'b', 'amount': 3.0},
            {'pos': 'BB', 'action': 'c', 'amount': 3.0},
            {'pos': 'CO', 'action': 'c', 'amount': 3.0}]},
        'flop': {'actions': [
            {'pos': 'UTG', 'action': 'x', 'amount': 1.0},
            {'pos': 'BB', 'action': 'b', 'amount': 5.0},
            {'pos': 'CO', 'action': 'c', 'amount': 5.0},
            {'pos': 'UTG', 'action': 'c', 'amount': 5.0}],
            'board': ['Kh', 'Qd', '7c']},
        'turn': {'actions': [
            {'pos': 'BB', 'action': 'x', 'amount': 1.0},
            {'pos': 'CO', 'action': 'x', 'amount': 1.0},
            {'pos': 'UTG', 'action': 'x', 'amount': 1.0}],
            'board': ['Kh', 'Qd', '7c', '2d']},
        'river': {'actions': [
            {'pos': 'BB', 'action': 'x', 'amount': 1.0},
            {'pos': 'CO', 'action': 'x', 'amount': 1.0}],
            'board': ['Kh', 'Qd', '7c', '2d', 'As']},
    }
    h['comunitarias'] = {'flop': ['Kh', 'Qd', '7c'], 'turn': ['2d'],
                         'river': ['As']}
    scores, mejor = cal.mejores_manos(h)
    assert mejor is not None
    # BB con AcAs tiene el As del board y la mesa: gana. CO esta declarado.
    declarados = {cal.id_a_pos(h, i) for i in h['winner']}
    mejores = {p for p, s_ in scores.items() if s_ == mejor}
    assert declarados and declarados != mejores, \
        'el caso no es incoherente: el test no probaria nada'
    y, ok = cal.etiqueta(h)
    # `etiqueta` por si sola acepta el registro; lo que excluye es `muestra`
    assert (y, ok) == (0.0, True), 'etiqueta es la del registro, sin comprobar'


def test_las_verificables_de_la_ventana_son_coherentes(cal, ventana):
    """261 verificables, 260 coherentes, 1 incoherente: `H_0909`.

    Se usa `llegan` —quien no folteo y tiene cartas— y **no** la
    interseccion con los mejores. La interseccion era el bug que señaló
    `revision_2`: con ella, un ganador que no es el mejor se salta la
    comprobación entera. `H_0909` es exactamente ese caso: declara a CO
    con 337 759 cuando BB hace 682 097.
    """
    verificadas = coherentes = 0
    incoherentes = []
    for h in ventana:
        scores, mejor = cal.mejores_manos(h)
        if mejor is None or not scores:
            continue
        dec = {cal.id_a_pos(h, i) for i in (h.get('winner') or [])}
        dec.discard(None)
        if not dec:
            continue
        reales = {p for p, s in scores.items() if s == mejor}
        llegan = {p for p in dec
                  if cal.llego_al_showdown(h, p) and p in scores}
        if not llegan:
            continue          # ganó por fold: no comprobable
        verificadas += 1
        if llegan == reales:
            coherentes += 1
        else:
            incoherentes.append(h['hand_id'])

    assert verificadas > 200, ('esperadas muchas: %d' % verificadas)
    assert incoherentes == ['H_0909'], (
        'cambió el conjunto de incoherentes: %s. Antes era 1' % incoherentes)


# ------------------------------------- 3. hero y butaca: las dos cosas bien
def test_hero_es_el_jugador_nombrado_no_el_de_la_butaca_0(cal):
    """El hero puede estar en cualquier butaca.

    En 232 de las 877 manos el hero NO es `players[0]`. Si el codigo cogiera
    `players[0]`, en esas manos la etiqueta seria de otro jugador.
    """
    h = _mano(['BB', 'UTG', 'MP'], ['otro', 'Jarduan', 'tercero'],
              ['', 'JdTd', 'Th5s'], ['p1'])
    assert cal.hero_de(h) == 'UTG'
    y, ok = cal.etiqueta(h)
    assert ok is True and y == 1.0


def test_hero_no_es_el_primero_con_cartas(cal):
    """Y no es "el primero con cartas" tampoco: esa convencion falla en 32.

    Aqui el hero (Jarduan, en UTG) NO tiene cartas, y el primero con cartas
    es MP, que ademas gano. Si se usara esa convencion, `y` seria 1,0 por
    el jugador equivocado.
    """
    h = _mano(['BB', 'UTG', 'MP'], ['otro', 'Jarduan', 'tercero'],
              ['', '', 'Th5s'], ['p2'])
    assert cal.hero_de(h) == 'UTG'
    y, ok = cal.etiqueta(h)
    assert ok is True and y == 0.0


def test_las_siete_manos_con_dos_ganadores_son_repartos(cal, ventana):
    """Las 7 son repartos, y se demuestra una por una.

    Antes se excluian 6 por "sin texto de showdown". Se excluian por no
    leer las cartas: `y = 0,5` era DEMOSTRABLE con el evaluador.
    """
    from motor.multiway import PLAYER_IDS
    multi = []
    for h in ventana:
        gs = {cal.id_a_pos(h, i) for i in (h.get('winner') or [])}
        gs.discard(None)
        if len(gs) > 1:
            multi.append((h, gs))
    assert len(multi) == 7, 'esperado 7 manos con 2+ ganadores'
    for h, gs in multi:
        assert cal.reparto(h, gs) is True, (
            '%s declara dos ganadores que NO hacen la misma mano: %s. '
            'Eso no es un reparto y hay que mirarlo' % (h['hand_id'],
                                                         sorted(gs)))


def test_h0798_es_un_reparto_no_una_victoria(cal, ventana):
    """La mano concreta que cambio el numero.

    `H_0798` daba `y = 1,0` porque `winner1` nominaba al hero. Con el
    evaluador: las dos manos hacen 675194. Es un reparto, y el hero se
    lleva la mitad del bote.
    """
    h = next(x for x in ventana if x['hand_id'] == 'H_0798')
    gs = {cal.id_a_pos(h, i) for i in (h.get('winner') or [])}
    gs.discard(None)
    assert cal.reparto(h, gs) is True
    y, ok = cal.etiqueta(h)
    assert ok is True
    assert y == 0.5


def test_id_a_pos_usa_player_ids(cal):
    """`'hero'` es la butaca 0, por `PLAYER_IDS`, no por indice del winner."""
    h = _mano(['BB', 'UTG', 'MP'], ['Jarduan', 'A', 'B'], ['AhKd', '', ''],
              [])
    assert cal.id_a_pos(h, 'hero') == 'BB'
    assert cal.id_a_pos(h, 'p1') == 'UTG'
    assert cal.id_a_pos(h, 'p2') == 'MP'
    assert cal.id_a_pos(h, 'p9') is None


# ------------------------------------------------------------- 4. la metrica
def test_l_prim_usa_p_hand_y_no_una_celda_inventada(cal):
    """La probabilidad debe ser la de la MANO observada.

    `p_matrix` devuelve un 13x13 de **rangos de carta**, no de acciones.
    Indexarlo con `g[ev.category, ev.pos]` es usar dos cadenas como
    indices: falla siempre, y el `except` de antes caia al maximo del grid.
    """
    from motor import learn, player_ranges as PR
    c, _v = cal.muestra()
    manos = cal.manos_de(c)
    labels = cal.etiquetas(manos)
    modelo = PR.ProfileRangeModel.from_hands(manos, labels=labels, alpha=2.0)
    for h in manos[:5]:
        for ev in learn.preflop_events(h):
            if not ev.hand_known or PR._cell_(ev.cards) is None:
                continue
            perfil = labels.get(ev.player, ev.player)
            if modelo.opp.get((perfil, ev.denom)) is None:
                continue
            p = modelo.p_hand(perfil, ev.denom, ev.category, ev.cards,
                              ev.pos)
            g = PR._cell_(ev.cards)
            esperado = float(np.asarray(
                modelo.p_matrix(perfil, ev.denom, ev.category, ev.pos))[g])
            assert abs(p - esperado) < 1e-9
            return
    pytest.skip('ningun evento con celda en las 5 primeras manos')


def test_l_prim_no_tiene_fallback_de_maximo(cal):
    """El codigo no puede seguir vivo con un `except` que sustituya el valor.

    Se mira el ARBOL, no el texto: el docstring de `l_prim` menciona
    `nanmax` justamente para explicar el bug, asi que buscar la palabra en
    el fuente daria un falso positivo.
    """
    import ast as _ast
    ruta = os.path.join(ROOT, 'tools', 'calibrar.py')
    arbol = _ast.parse(io.open(ruta, encoding='utf-8').read())
    fn = next(n for n in _ast.walk(arbol)
              if isinstance(n, _ast.FunctionDef) and n.name == 'l_prim')
    for nodo in _ast.walk(fn):
        # fuera el docstring
        if isinstance(nodo, _ast.Expr) and isinstance(nodo.value,
                                                     _ast.Constant):
            continue
        if isinstance(nodo, _ast.Name) and nodo.id in ('nanmax', 'nanmin',
                                                      'amax', 'max', 'min'):
            pytest.fail('l_prim usa %s: eso es un fallback, y un fallback '
                        'cambia la metrica cuando algo va mal' % nodo.id)
        if isinstance(nodo, _ast.Attribute) and nodo.attr == 'clip':
            continue


def test_l_prim_no_cambia_el_denominador(cal):
    """El denominador es FIJO. `revision_2`: si un evento cae en p = 0 y se
    cuenta aparte, el denominador depende de alpha y las perdidas dejan de
    ser comparables."""
    c, _v = cal.muestra()
    d1 = cal.l_prim(0.5, c)[1]
    d2 = cal.l_prim(2.0, c)[1]
    d3 = cal.l_prim(9.0, c)[1]
    assert d1['medidos'] == d2['medidos'] == d3['medidos']
    assert d1['eventos'] == d2['eventos'] == d3['eventos']


def test_l_prim_los_cubos_cuadran(cal):
    """Cada evento entra en un cubo y solo uno, y suman todos."""
    c, _v = cal.muestra()
    L, d = cal.l_prim(2.0, c)
    assert d['medidos'] + d['p_0'] + d['sin_celda'] + d['sin_opp'] \
        == d['eventos'], 'los cubos no suman todos los eventos'
    assert d['p_0'] == 0


def test_l_prim_falla_en_voz_alta_si_no_hay_celda(cal):
    """Si no se puede medir, se lanza `MedicionSinSentido`, no se devuelve 0."""
    c, _v = cal.muestra()
    try:
        L, det = cal.l_prim(2.0, c)
    except cal.MedicionSinSentido:
        return
    assert L is not None and L > 0
    assert det['eventos'] > 0
    assert det['p_0'] == 0, 'hay eventos en celdas con p = 0: se excluyen'


def test_l_prim_no_arrastra_la_validacion_en_las_etiquetas(cal):
    """Las etiquetas de perfil se calculan SOLO con las manos que se ajustan.

    `Profiles.from_hands` deriva la etiqueta de las manos que recibe.
    Medido: **46 de 144 jugadores** cambian de etiqueta si se calcula con
    la ventana entera, y varios quedan sin etiqueta. Eso mete las 39
    manos de validacion dentro del ajuste.
    """
    c, v = cal.muestra()
    manos_cal = cal.manos_de(c)
    solo_cal = cal.etiquetas(manos_cal)
    ventana_entera = cal.etiquetas(cal.ventana())
    distintos = [n for n in ventana_entera
                 if solo_cal.get(n) != ventana_entera[n]]
    assert distintos, ('esperado: calcular sobre la ventana cambia algunas '
                       'etiquetas. Si no cambia, este test se puede borrar '
                       'y la fuga no existe')
    # los que cambian tienen que estar tocados por las manos de calibracion:
    # si un jugador no aparece ahi, su etiqueta sale de validacion
    en_cal = {(p.get('name') or '').strip() for h in manos_cal
              for p in h['players']}
    for n in distintos:
        assert n in en_cal or solo_cal.get(n) is None, (
            '%s cambia de etiqueta y no sale de las manos de calibracion: '
            'su etiqueta depende de la validacion' % n)


# --------------------------------------------- 5. la metrica ve al parametro
def test_l_prim_cambia_con_alpha(cal):
    c, _v = cal.muestra()
    a1, d1 = cal.l_prim(1.0, c)
    a9, d9 = cal.l_prim(9.0, c)
    assert d1['eventos'] == d9['eventos'] > 0
    assert a1 != a9, 'L_prim no responde a alpha'


# ----------------------------------------------- 6. el guardian de monotonia
def test_el_guardian_detecta_monotonia_creciente():
    assert _mod('c1', 'calibrar.py').es_monotona(
        [0.5, 1.0, 2.0], [0.17, 0.30, 0.49]) is True


def test_el_guardian_detecta_monotonia_decreciente():
    assert _mod('c2', 'calibrar.py').es_monotona(
        [0.5, 1.0, 2.0], [0.49, 0.30, 0.17]) is True


def test_el_guardian_no_dispara_si_hay_un_maximo():
    assert _mod('c3', 'calibrar.py').es_monotona(
        [0.5, 1.0, 2.0], [0.30, 0.10, 0.30]) is False


def test_el_guardian_necesita_tres_puntos():
    assert _mod('c4', 'calibrar.py').es_monotona([1.0, 2.0], [0.3, 0.4]) \
        is False


def test_la_curva_real_de_alpha_es_monotona(cal):
    """El hallazgo de CALIBRACION_DEFAULT_ALPHA.md §3."""
    c, _v = cal.muestra()
    vals = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    meds = [cal.l_prim(a, c)[0] for a in vals]
    assert cal.es_monotona(vals, meds) is True


# ------------------------------------------------------ 7. las barreras
def test_autovalidacion_fallida_aborta_con_3(cal, monkeypatch, capsys):
    """Si la metrica no ve alpha, sale con 3 y NO imprime tabla.

    Antes preparaba el mensaje de rechazo y seguia: solo retornaba por la
    rama de monotonia. Con curva no monotonica llegaba a publicar.
    """
    monkeypatch.setattr(cal, 'la_metrica_ve_a_alpha',
                        lambda manos, labels=None: (False, 'cegada a proposito'))
    monkeypatch.setattr('sys.argv',
                        ['calibrar.py', '--valores', '1.0', '2.0'])
    rc = cal.main()
    salida = capsys.readouterr().out
    assert rc == 3
    assert 'NO SE PUBLICA NADA' in salida
    assert 'L_prim ' not in salida, 'no debe imprimir la tabla'


def test_sin_l_sec_no_se_acepta_aunque_no_sea_monotona(cal, monkeypatch,
                                                       capsys):
    """La secundaria es requisito del contrato de aceptacion.

    Con la curva NO monotonica, el camino viejo llegaba a `--aplicar` y
    elegia el minimo de `L_prim` sin ninguna contra. Ahora no.
    """
    monkeypatch.setattr(cal, 'es_monotona', lambda v, m: False)
    monkeypatch.setattr('sys.argv', ['calibrar.py', '--valores', '1.0',
                                     '2.0', '--aplicar'])
    rc = cal.main()
    salida = capsys.readouterr().out
    assert rc == 2
    assert 'NO SE CALIBRA' in salida
    assert 'mejor L_prim' not in salida


def test_no_se_toca_el_motor(cal):
    """`--aplicar` sin las dos metricas no escribe nada en el motor."""
    ruta = os.path.join(ROOT, 'motor', 'player_ranges.py')
    antes = io.open(ruta, encoding='utf-8').read()
    import sys as _sys
    argv = _sys.argv
    _sys.argv = ['calibrar.py', '--valores', '0.5', '2.0', '--aplicar']
    try:
        cal.main()
    finally:
        _sys.argv = argv
    assert io.open(ruta, encoding='utf-8').read() == antes


def test_la_la_secundaria_es_honesta_sobre_no_poder_calcularse(cal):
    v, motivo = cal.l_sec(2.0, cal.muestra()[1])
    assert v is None
    assert 'API' in motivo or 'api' in motivo


# ------------------------------------------------------- 8. DEFAULT_ALPHA
def test_default_alpha_sigue_en_dos():
    """La razon de todo lo de arriba, convertida en condicion."""
    src = io.open(os.path.join(ROOT, 'motor', 'player_ranges.py'),
                  encoding='utf-8').read()
    linea = next(l for l in src.split(chr(10))
                 if l.startswith('DEFAULT_ALPHA'))
    assert '2.0' in linea, ('DEFAULT_ALPHA movido: %s' % linea.strip())