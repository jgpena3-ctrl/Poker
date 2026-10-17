# -*- coding: utf-8 -*-
"""R2 parrafo 1: tests de regresion para los DOS casos que importan.

No son el mismo comportamiento, y por eso van por separado:

  H_0043  el heroe apuesta, TODOS foldean, gana por fold, y no hay board.
          No puede tener etiqueta con el orden de filtros ACTUAL, porque
          `board_completo()` se comprueba antes del camino de fold. Pero
          `gano_por_fold()` lo acepta: la victoria es verificable SIN las
          cartas de los demas. Es el caso que demuestra que la poblacion
          esta BLOQUEADA y no vacia.

  H_0485  el heroe CALL, hay board, y el showdown es verificable. Este si
          tiene etiqueta posible, y es el UNICO y=1 de los 78 que no viene
          por fold. Protege el otro camino: el de showdown, que si necesita
          las cartas de los demas.

Y el tercero, que es el que mas cuesta creer:

  0 derrotas entre las 78. La razon es estructural —el corte es la ULTIMA
  accion del heroe, y para que sea jugada en preflop la mano tiene que
  terminar ahi—. Si esto cambia, el AUC preflop vuelve a ser una pregunta, y
  hay que enterarse por un test y no por un error de dos meses.
"""
import collections
import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


@pytest.fixture(scope='module')
def ins():
    ruta = os.path.join(ROOT, 'tools', 'equity_preflop_observables.py')
    spec = importlib.util.spec_from_file_location('eqpobs_reg', ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope='module')
def ventana(ins):
    from motor import learn
    ws = learn.load_hands(reliable_only=True)
    return dict((h['hand_id'], h) for h in ws)


@pytest.fixture(scope='module')
def continuaciones(ins, ventana):
    out = []
    for hid in sorted(ventana):
        h = ventana[hid]
        pos = ins.eqm.hero_pos_de(h)
        if not pos:
            continue
        calle, idx = ins.eqm.corte_de_decision(h, pos)
        if calle != 'preflop':
            continue
        acts = ((h.get('streets') or {}).get(calle) or {}).get('actions') or []
        acc = acts[idx]['action'] if idx is not None and idx < len(acts) else '?'
        if acc in ins.ACCIONES_JUGADAS:
            out.append(hid)
    return out


# ============================================================ H_0043
def test_h_0043_no_pasa_el_filtro_de_board(ins, ventana):
    """La mano existe, es una victoria por fold, y no llega a etiquetarse:
    `board_completo()` se comprueba antes."""
    h = ventana['H_0043']
    assert not ins.cal.board_completo(h), (
        'si esto pasara, el caso que demuestra el bloqueo habria dejado de '
        'demostrarlo')
    assert not (h.get('comunitarias') or {}).get('river')


def test_h_0043_tiene_victoria_por_fold_verificable(ins, ventana):
    """Y ese es el punto: el camino de fold NO necesita las cartas de los
    demas, y por eso hace sombra a los dos filtros de arriba."""
    h = ventana['H_0043']
    declarados = {ins.cal.id_a_pos(h, i) for i in (h.get('winner') or [])}
    declarados.discard(None)
    assert declarados, 'tiene ganador declarado'
    ok, mot = ins.cal.gano_por_fold(h, declarados)
    assert ok, 'y la victoria por fold tiene que ser verificable: %r' % (mot,)
    assert len(ins.cal.con_cartas(h)) == 1, (
        'y solo tiene cartas el heroe: por eso el filtro de las dos cartas '
        'tambien lo deja fuera')


def test_h_0043_solo_tiene_cartas_del_heroe(ventana):
    h = ventana['H_0043']
    con_cartas = [p for p in h['players'] if (p.get('cards') or '').strip()]
    assert len(con_cartas) == 1
    assert con_cartas[0]['name'] == 'Jarduan'


# ============================================================ H_0485
def test_h_0485_tiene_board_en_streets_y_no_en_comunitarias(ins, ventana):
    """La segunda mitad del hallazgo: dos representational del mismo campo."""
    h = ventana['H_0485']
    st = h.get('streets') or {}
    reales = []
    for calle in ('flop', 'turn', 'river'):
        reales += list((st.get(calle) or {}).get('board') or [])
    assert reales, 'el board esta en streets'
    assert not (h.get('comunitarias') or {}).get('river'), (
        'y comunitarias.river esta vacio, que es lo que lee el filtro')
    assert not ins.cal.board_completo(h)


def test_h_0485_es_el_unico_showdown_verificable(ins, ventana):
    """Es el camino del showdown, que SI necesita las cartas de los demas, y
    es UNO de los 83. Protege que no se confunda con el de fold."""
    h = ventana['H_0485']
    declarados = {ins.cal.id_a_pos(h, i) for i in (h.get('winner') or [])}
    declarados.discard(None)
    scores, mejor = ins.cal.mejores_manos(h)
    llegan = {p for p in declarados
              if ins.cal.llego_al_showdown(h, p) and scores and p in scores}
    assert llegan, 'alguien llega al showdown'
    assert len(ins.cal.con_cartas(h)) >= 2, 'y hay cartas de los demas'


def test_h_0485_es_el_showdown_verificable_de_la_poblacion(ins, ventana,
                                                            continuaciones):
    """Medido: de las 83, una sola tiene showdown verificable. Si mañana hay
    dos, este test avisa antes de que nadie mire el AUC."""
    n = 0
    for hid in continuaciones:
        h = ventana[hid]
        declarados = {ins.cal.id_a_pos(h, i) for i in (h.get('winner') or [])}
        declarados.discard(None)
        if not declarados:
            continue
        scores, mejor = ins.cal.mejores_manos(h)
        llegan = {p for p in declarados
                  if ins.cal.llego_al_showdown(h, p) and scores and p in scores}
        if llegan and len(ins.cal.con_cartas(h)) >= 2:
            mejores = {p for p, s_ in scores.items() if s_ == mejor}
            if llegan == mejores:
                n += 1
                assert hid == 'H_0485', (
                    'hay un segundo showdown verificable, %s' % hid)
    assert n == 1, 'medido: exactamente uno'


# ================================================= la clase, que es el nudo
def test_las_78_que_se_desbloquearian_son_todas_victorias(ins, ventana,
                                                         continuaciones):
    """El numero que hace que no haya AUC, y el que mas cuesta creer.

    Con el orden de filtros ACTUAL la poblacion B preflop esta vacia. Si se
    saltaran los dos filtros que se adelantan al camino de fold, habria 78
    con etiqueta — y CERO con y = 0.

    El AUC binario daria 1,0 por definicion. No es un AUC malo: es que no
    hay la clase negativa.
    """
    clases = collections.Counter()
    for hid in continuaciones:
        h = ventana[hid]
        pos = ins.eqm.hero_pos_de(h)
        _m, y = _etiqueta_posible(ins, h, pos)
        if y is not None:
            clases[y] += 1
    assert clases.get(0.0, 0) == 0, (
        'HAY %d derrotas. Si las hay, el AUC preflop vuelve a ser una '
        'pregunta y hay que rehacer el documento' % clases.get(0.0))
    assert clases.get(1.0, 0) == 78, 'y 78 victorias: %r' % dict(clases)


def test_la_poblacion_esta_bloqueada_y_no_vacia(ins, ventana,
                                               continuaciones):
    """Las tres cosas juntas, que es lo que el documento afirma:
    83 decisiones, 0 con etiqueta HOY, 78 si se desbloquea.

    "Hoy" no se replica con una funcion propia —eso ya lo hace
    `_etiqueta_posible()`, que ademas se salta los dos filtros y por eso no
    puede servir para contar "hoy"—. "Hoy" es la pertenencia REAL a
    `muestra()`, que es la unica forma de no medir una copia del filtro en
    vez del filtro.
    """
    assert len(continuaciones) == 83
    cal_, val_ = ins.cal.muestra()
    en_la_muestra = set(hid for hid, _y in cal_ + val_)
    con_y = len([h for h in continuaciones if h in en_la_muestra])
    posibles = 0
    for hid in continuaciones:
        _m, y = _etiqueta_posible(ins, ventana[hid],
                                  ins.eqm.hero_pos_de(ventana[hid]))
        posibles += y is not None
    assert con_y == 0, 'hoy: %d tienen etiqueta' % con_y
    assert posibles == 78, 'desbloqueada: %d' % posibles


def _etiqueta_posible(ins, h, hero_pos):
    cal = ins.cal
    declarados = {cal.id_a_pos(h, i) for i in (h.get('winner') or [])}
    declarados.discard(None)
    if not declarados:
        return 'sin ganador declarado', None
    scores, mejor = cal.mejores_manos(h)
    llegan = {p for p in declarados
              if cal.llego_al_showdown(h, p) and scores and p in scores}
    if not llegan:
        ok, _mot = cal.gano_por_fold(h, declarados)
        return ('ok', 1.0) if ok else ('fold no verificable', None)
    if len(cal.con_cartas(h)) < 2:
        return 'showdown sin cartas de los demas', None
    mejores = {p for p, s_ in scores.items() if s_ == mejor}
    if llegan != mejores:
        return 'ganadores que no son los mejores', None
    return 'ok', (1.0 if hero_pos in llegan else 0.0)


# ------------------------- y el filtro, que es donde esta el bloqueo
def test_el_bloqueo_es_de_ORDEN_no_de_datos(ins, ventana):
    """Los dos filtros van ANTES del camino de fold en `muestra()`. Eso se
    lee del codigo, y se lee porque es la razon entera del hallazgo."""
    import inspect
    src = inspect.getsource(ins.cal.muestra)
    i_board = src.index('board_completo(h)')
    i_cartas = src.index('con_cartas(h)')
    i_fold = src.index('gano_por_fold')
    assert i_board < i_fold, 'board_completo va antes del camino de fold'
    assert i_cartas < i_fold, (
        'y el de las dos cartas tambien: los dos hacen sombra al unico '
        'camino que acepta una victoria sin showdown')