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
          tiene etiqueta posible, y protege el otro camino: el de showdown,
          que si necesita las cartas de los demas.

  H_0080  el heroe gana (y=1) y su ultima accion es preflop, pero la mano
          siguio y tiene board y ganador verificable. Es una de las dos
          preflop con etiqueta.

  H_0223  el heroe pierde (y=0), tambien con la ultima accion en preflop y
          la mano continuada. Desmonta la afirmacion estructural de que
          «entre los cortes preflop no hay derrotas»: no era estructural,
          era un dato de la base anterior.

Y el conjunto medido sobre la base canonica de 1253: 76 cortes preflop,
2 con etiqueta (H_0080 y H_0223) y 3 con showdown verificable (H_0080,
H_0223 y H_0485). Si mañana cambia, el test avisa antes de que nadie mire
el AUC, y el que lo cambie tiene que mirar POR QUE.
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
    demas, y por eso hace sombra a los dos filtros de arriba.

    Esta es la prueba de la funcion`gano_por_fold`: el test la llama porque lo que prueba ES
    que la funcion acepta esta mano. Un test que la llamara sin decirlo
    seria una copia de la logica, y `test_sin_copias.py` no lo dejaria
    pasar."""
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


def test_h_0485_es_uno_de_los_showdowns_verificables(ins, ventana):
    """Es el camino del showdown, que SI necesita las cartas de los demas, y
    es uno de los 76 cortes preflop. Protege que no se confunda con el de
    fold."""
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
    """Medido: de las 76, tres tienen showdown verificable. Si mañana hay
    una cuarta, este test avisa antes de que nadie mire el AUC.

    Y el conjunto medido sobre la base canonica de 1253 es
    {H_0080, H_0223, H_0485}: la adopcion trajo dos manos con board y
    ganador verificable que antes no estaban en la ventana, y por eso el
    guardia pasa de «exactamente uno» a «exactamente estos tres».
    """
    ids = []
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
                ids.append(hid)
    assert set(ids) == {'H_0080', 'H_0223', 'H_0485'}, (
        'los showdowns verificables de la poblacion son %r, y el conjunto '
        'medido es {H_0080, H_0223, H_0485}' % (ids,))


# ================================================= la clase, que es el nudo
def test_los_76_cortes_preflop_solo_dos_tienen_etiqueta(ins, ventana,
                                                        continuaciones):
    """La afirmacion RETIRADA era "las 78 desbloqueadas son todas
    victorias". En la base canonica de 1253 hay 76 cortes y solo DOS con
    etiqueta, y las dos tienen board y ganador verificable —H_0080 (y=1) y
    H_0223 (y=0)—: el corte es la ultima accion del heroe, y que sea
    preflop NO obliga a que la mano termine ahi, porque los demas pueden
    seguir jugando.

    El 78 salia de una replica local del etiquetado, dentro del propio
    test, que contaba como positivas manos que no estan en `muestra()`.
    Este test ya no tiene copia: usa la funcion de la herramienta.
    """
    assert len(continuaciones) == 76, 'cortes preflop de poblacion B'
    con_y = [h for h in continuaciones if h in ventana
             and ventana[h]['hand_id'] in _etiquetas(ins)]
    assert set(con_y) == {'H_0080', 'H_0223'}, (
        'HAY %d cortes preflop con etiqueta: %s. Si el conjunto cambia, la '
        'poblacion preflop cambio de verdad, y hay que mirar POR QUE antes '
        'de cambiar ningun numero' % (len(con_y), con_y[:6]))


def test_el_motivo_de_no_tener_etiqueta_es_que_la_mano_no_tiene_board(
        ins, ventana, continuaciones):
    """Y no es un filtro que se pueda mover. Si el heroe juega y la mano se
    acaba en el preflop, no se repartieron cartas, y sin board no hay
    ganador verificable."""
    sin_board = 0
    con_board_sin_y = 0
    con_board_con_y = []
    for hid in continuaciones:
        h = ventana[hid]
        riv = ((h.get('comunitarias') or {}).get('river') or [])
        if not riv:
            sin_board += 1
        elif hid not in _etiquetas(ins):
            con_board_sin_y += 1
        else:
            con_board_con_y.append(hid)
    assert (sin_board + con_board_sin_y + len(con_board_con_y)
            == len(continuaciones))
    assert sin_board == 74, (
        'casi todas las manos jugadas en preflop terminan ahi: %d de %d sin '
        'board' % (sin_board, len(continuaciones)))
    # y de las que SI tienen board, cuántas tienen etiqueta: dos —H_0080 y
    # H_0223—, y el resto del problema es que el corte en la primera trae
    # mas manos con board.
    assert con_board_sin_y == 0, (
        'y las que tienen board y no etiqueta son %d. Si suben mucho, hay '
        'otra causa y hay que medirla' % con_board_sin_y)
    assert set(con_board_con_y) == {'H_0080', 'H_0223'}, (
        'las que tienen board y etiqueta son %r' % (con_board_con_y,))


def test_el_corte_en_la_primera_si_tiene_etiqueta(ins, ventana):
    """La otra mitad: con el corte en la PRIMERA decision, la mano continua,
    se reparten cartas, y aparece la etiqueta. No es un filtro distinto: es
    que la mano no se acaba."""
    import importlib.util
    ruta = os.path.join(ROOT, 'tools', 'auditar_representatividad.py')
    spec = importlib.util.spec_from_file_location('ar_primera', ruta)
    ar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ar)
    filas = ar.medir_todas_calles(ins, ventana, 'primera')
    pre = [f for f in filas if f['jugada'] and f['calle'] == 'preflop'
           and f['y'] is not None]
    assert len(pre) == 61, 'preflop con etiqueta, corte en la primera: %d' % len(pre)
    assert sum(1 for f in pre if f['y'] == 1.0) == 21
    assert sum(1 for f in pre if f['y'] == 0.0) == 40, (
        'y con las dos clases, que es lo que hace que el corte en la primera '
        'traiga algo que el actual no trae')


def test_el_postflop_si_tiene_las_dos_clases(ins, ventana):
    """Y el motivo por el que el AUC se calcula hoy: no es que le falte una
    clase a la poblacion. El postflop las tiene."""
    import importlib.util
    ruta = os.path.join(ROOT, 'tools', 'auditar_representatividad.py')
    spec = importlib.util.spec_from_file_location('ar_post', ruta)
    ar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ar)
    filas = ar.medir_todas_calles(ins, ventana, 'ultima')
    post = [f for f in filas if f['jugada'] and f['calle'] != 'preflop'
            and f['y'] is not None]
    assert len(post) == 48, 'postflop con etiqueta: %d' % len(post)
    assert sum(1 for f in post if f['y'] == 1.0) == 20
    assert sum(1 for f in post if f['y'] == 0.0) == 28


def _etiquetas(ins):
    cal_, val_ = ins.cal.muestra()
    return dict(cal_ + val_)


def _etiqueta_posible(ins, h, hero_pos):
    """YA NO HAY COPIA. Se usa la funcion de la herramienta.

    Este test tenia su propia replica de los filtros de
    `muestra()`, y afirmaba 78 victorias y cero derrotas con
    una logica que ya no es la de la herramienta. Seguiria
    dando verde con el error dentro, porque no comparte codigo
    con lo que prueba. Eso es un test que no prueba.
    """
    ar = _mod_ar()
    r = ar.resto_de_muestra(ins.cal, h, hero_pos)
    return r.motivo, r.y


def _mod_ar():
    import importlib.util
    ruta = os.path.join(ROOT, 'tools',
                        'auditar_representatividad.py')
    spec = importlib.util.spec_from_file_location(
        'ar_desde_bloqueo', ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
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