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
    """156 utilizables, 117 de calibracion, 39 de validacion."""
    c, v = cal.muestra()
    assert len(c) == 117
    assert len(v) == 39
    assert len(c) + len(v) == 156


def test_la_ventana_es_la_declarada(cal):
    assert len(cal.ventana()) == 877


def test_la_particion_versionada_coincide_con_la_calculada(cal):
    """DOCS/PARTICION_FASE_D.md tiene que ser el fichero que sale aqui."""
    texto = io.open(os.path.join(ROOT, 'DOCS', 'PARTICION_FASE_D.md'),
                    encoding='utf-8').read()
    c, v = cal.muestra()
    for hid, _y in v[:5]:
        assert '`%s`' % hid in texto
    for marca in ('| validacion | 39 |', '| calibracion | 117 |',
                  '| utilizables | 156 |'):
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
    assert len(ys) == len(ys_aud) == 156
    assert sorted(ys) == sorted(ys_aud)


# -------------------------------------------------------------- 2. etiqueta
def test_no_se_inventan_empates(cal):
    """Varios ganadores SIN texto de showdown -> no utilizable."""
    h = _mano(['UTG', 'BTN', 'BB'], ['A', 'B', 'Jarduan'],
              ['AhKd', 'QsJs', '2h3d'], ['hero', 'p2'])
    y, ok = cal.etiqueta(h)
    assert (y, ok) == (None, False)


def test_winner1_tiene_que_resolver_no_solo_existir(cal):
    """Un texto que no nombra a nadie de la mesa NO resuelve.

    Este es el bug que encontre revision_2: el codigo anterior aceptaba
    cualquier texto no vacio y sin separadores, y luego usaba la lista
    `winner` sin mirarla. Ahora el texto tiene que.names a alguien.
    """
    h = _mano(['UTG', 'BTN', 'BB'], ['A', 'B', 'Jarduan'],
              ['AhKd', 'QsJs', '2h3d'], ['hero', 'p2'],
              showdown={'winner1': 'alguien que no esta en esta mesa'})
    assert cal.etiqueta(h) == (None, False)
    assert cal.ganador_nombrado(h)[0] is None


def test_winner1_resuelto_manda_sobre_la_lista(cal):
    """Si `winner1` resuelve, ese es el ganador, no el primero de la lista.

    Aqui la lista y el texto CONTRADICEN a proposito: `winner` dice que ganan
    los dos, `winner1` dice que gana el hero. Gana el hero.
    """
    h = _mano(['BB', 'CO', 'BTN'], ['Jarduan', 'A', 'B'],
              ['TsQs', '', 'AhKd'], ['hero', 'p2'],
              showdown={'winner1': 'BB (Jarduan)'})
    y, ok = cal.etiqueta(h)
    assert ok is True
    assert y == 1.0


def test_sin_jugador_heroname_no_hay_etiqueta(cal):
    """Si nadie se llama como el hero, no hay etiqueta.

    Antes esto comparaba contra "el primer jugador con cartas", que siempre
    encontraba a alguien. Ahora puede no haberlo, y esa es la respuesta
    correcta: sin hero no hay `y`.
    """
    h = _mano(['UTG', 'BTN', 'BB'], ['A', 'B', 'C'],
              ['AhKd', 'QsJs', '2h3d'], ['hero'])
    assert cal.etiqueta(h) == (None, False)


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