# -*- coding: utf-8 -*-
"""Los dos puntos que `revision_2` senalo en los tests, y uno es mio.

1. LA ASIMETRIA DEL GUARDIA. El test comparaba `if r.y is not None and
   r.y != real`, o sea que una etiqueta que DESAPARECIA —`muestra()` dice
   1.0 y `resto_de_muestra()` devuelve None— pasaba sin fallar.

   `revision_2` propone el contrato estricto, y tiene razon. Medido antes de
   aceptarlo: hoy 0 etiquetas inventadas, 0 distorsionadas y 0 perdidas, de
   modo que el contrato estricto pasaria. Pasaria por SUERTE: en cuanto una
   mano etiquetada fuera no viable, se perderia en silencio.

   La correccion de fondo es que `y` y `motivo` ya no estan acoplados: `y`
   es la etiqueta y no depende del juicio de viabilidad. Con eso el
   contrato estricto se sostiene por construccion. Y el test nuevo exige
   las tres partes del contrato, incluida la que faltaba: si la etiqueta
   existia y `y` sale None, el motivo tiene que explicar por que.

2. LA PRUEBA DEL BOARD. Miraba `comunitarias.river` y de ahi concluyo "no
   hay board". Pero el propio informe documenta 2 manos con el board en
   `streets.*.board` y `comunitarias` vacio. Convertir una inconsistencia
   del registro en evidencia de que no se repartieron cartas es justo lo
   que no hay que hacer.

   Ahora se miran LAS DOS representaciones y se separan los tres casos.
"""
import collections
import importlib.util
import io
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _mod(nombre, donde='tools'):
    ruta = os.path.join(ROOT, donde, nombre)
    spec = importlib.util.spec_from_file_location(
        nombre[:-3].replace('.', '_'), ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope='module')
def ar():
    return _mod('auditar_representatividad.py')


@pytest.fixture(scope='module')
def ins():
    return _mod('equity_preflop_observables.py')


@pytest.fixture(scope='module')
def ventana(ins):
    from motor import learn
    return dict((h['hand_id'], h) for h in learn.load_hands(reliable_only=True))


# ============================================ 1. el contrato, entero
def test_la_etiqueta_se_lee_igual_a_muestra_en_todas_las_manos(ar, ins,
                                                              ventana):
    """LAS TRES PARTES DEL CONTRATO, sobre TODAS las manos.

    1. si `muestra()` no tiene etiqueta, o es reparto: `y` es None
    2. si `y` no es None: es EXACTAMENTE el de `muestra()`
    3. si `y` es None pero la etiqueta existia: el motivo lo explica

    La parte 3 es la que faltaba, y es la que convierte "se perdio" en "no
    se puede perder": con `y` desacoplado de `motivo`, no hay forma de que
    la etiqueta se pierda sin dejar rastro.
    """
    cal_, val_ = ins.cal.muestra()
    ETIQUETA = dict(cal_ + val_)
    perdidos, sin_explicacion, inventadas, distorsionadas = [], [], [], []
    for hid, h in sorted(ventana.items()):
        pos = ins.eqm.hero_pos_de(h)
        if not pos:
            continue
        r = ar.resto_de_muestra(ins.cal, h, pos)
        real = ETIQUETA.get(hid)
        if real is None:
            if r.y is not None:
                inventadas.append((hid, r.y))
            continue
        if real == 0.5:
            if r.y is not None:
                inventadas.append((hid, 'reparto como %r' % r.y))
            continue
        # 2. si hay etiqueta, sale exacta
        if r.y is not None and r.y != real:
            distorsionadas.append((hid, r.y, real))
        # 3. y si sale None, el motivo lo dice
        if r.y is None:
            perdidos.append(hid)
            if r.motivo in ('ok', None, ''):
                sin_explicacion.append((hid, r.motivo))
    assert not inventadas, 'etiquetas INVENTADAS: %r' % inventadas[:6]
    assert not distorsionadas, 'etiquetas DISTINTAS: %r' % distorsionadas[:6]
    assert not sin_explicacion, (
        'etiquetas perdidas SIN motivo: %r. Con `y` desacoplado de `motivo` '
        'no puede pasar, y si pasa es que alguien los volvio a acoplar'
        % sin_explicacion[:6])
    # y hoy, ademas, no se pierde ninguna: se deja escrito como dato
    assert perdidos == [], (
        'hoy no se pierde ninguna etiqueta. Si esta lista crece, o ha '
        'aparecido una observacion etiquetada y no viable, o la etiqueta '
        'se ha vuelto a acoplar al motivo. El motivo de cada una: %r'
        % [(h, ar.resto_de_muestra(ins.cal, ventana[h],
                                   ins.eqm.hero_pos_de(ventana[h])).motivo)
           for h in perdidos[:6]])


def test_la_etiqueta_no_depende_del_juicio_de_viabilidad(ar, ins, ventana):
    """La separacion, probada. Si una mano esta etiquetada, `y` no es None
    NUNCA, diga lo que diga `motivo`."""
    cal_, val_ = ins.cal.muestra()
    ETIQUETA = dict(cal_ + val_)
    for hid, h in sorted(ventana.items()):
        if ETIQUETA.get(hid) in (None, 0.5):
            continue
        pos = ins.eqm.hero_pos_de(h)
        if not pos:
            continue
        r = ar.resto_de_muestra(ins.cal, h, pos)
        assert r.y is not None, (
            '%s tiene etiqueta %r en `muestra()` y `resto_de_muestra` '
            'devuelve None (motivo %r). La etiqueta no puede depender de si '
            'la observacion es viable.' % (hid, ETIQUETA[hid], r.motivo))


def test_el_fuente_no_tiene_una_etiqueta_literal(ar):
    """Y que no vuelva a haberla. Una etiqueta escrita a mano en un `Resto`
    es una etiqueta inventada esperando a que haya una mano para ella."""
    fuente = io.open(ar.__file__, encoding='utf-8').read()
    i = fuente.index('def resto_de_muestra')
    j = fuente.index('\ndef ', i + 5)
    cuerpo = fuente[i:j]
    for linea in cuerpo.split('\n'):
        code = linea.strip()
        if code.startswith('#') or code.startswith('"""'):
            continue
        if 'Resto(' in code and ('1.0' in code or '0.0' in code):
            raise AssertionError('etiqueta literal: %s' % code)
    assert 'y_real' in cuerpo, 'y la etiqueta sale de una variable, no de un'


def test_contar_observaciones_pide_las_dos_cosas(ar, ins, ventana):
    """Un filtro con etiqueta y no viable no es una observacion. Y eso lo
    dice el codigo con `viable`, no con `y is not None` a secas."""
    filas = ar.medir_todas_calles(ins, ventana, 'ultima')
    con = [f for f in filas if f['jugada'] and f['y'] is not None]
    viable = [f for f in con if f['viable']]
    assert len(con) == len(viable), (
        'hoy coinciden (%d), porque no hay etiqueta no viable. Si divergen, '
        'el filtro de `medir_*` tiene que usar `viable` y no solo `y`'
        % len(con))


# ============================================ 2. el board, las dos fuentes


def _board_en(ar, ins, ventana):
    """(con etiqueta en comunitarias, con board solo en streets, sin board).

    LAS DOS representational. `board_completo()` lee `comunitarias.river`, y
    hay manos con el board en `streets.*.board` y `comunitarias` vacio. De ahi
    que mirar solo una de las dos convierte una INCONSISTENCIA DEL REGISTRO
    en evidencia de que no se repartieron cartas.

    `revision_2`: "una prueba no deberia convertir una inconsistencia del
    registro en evidencia de que no se repartieron cartas".
    """
    filas = ar.medir_todas_calles(ins, ventana, 'ultima')
    pre = [f for f in filas if f['jugada'] and f['calle'] == 'preflop']
    a = b = c = 0
    ids_b = []
    for f in pre:
        h = ventana[f['id']]
        en_com = bool((h.get('comunitarias') or {}).get('river') or [])
        reales = []
        st = h.get('streets') or {}
        for calle in ('flop', 'turn', 'river'):
            reales += list((st.get(calle) or {}).get('board') or [])
        if en_com:
            a += 1
        elif reales:
            b += 1
            ids_b.append(f['id'])
        else:
            c += 1
    return (a, b, c), ids_b


def test_el_board_se_mira_en_las_dos_representaciones(ar, ins, ventana):
    (a, b, c), ids_b = _board_en(ar, ins, ventana)
    total = a + b + c
    assert total == 76, 'cortes preflop de poblacion B: %d' % total
    assert a == 2, (
        'con board en `comunitarias`: %d. Son H_0080 y H_0223, las dos que '
        'la adopcion trajo con board y etiqueta' % a)
    assert c >= 72, (
        'sin board en NINGUNA parte: %d de %d. Y esa es la afirmacion que '
        'sostiene que la mano no llego a repartirse' % (c, total))
    assert b == 2, (
        'con board solo en `streets`: %d  %s. Estas NO son "manos sin '
        'board": son un registro con dos representaciones y una vacia. '
        'Contarlas como "no se repartieron cartas" seria usar una '
        'inconsistencia como evidencia' % (b, ids_b))
    # y ningun test puede afirmar "sin board" mirando una sola de las dos
    assert a + b + c == total


def test_el_motivo_real_de_los_76_cortes(ar, ins, ventana):
    """Las dos que tienen board SOLO en `streets` y ninguna etiqueta: son
    el resto del problema, y no el mismo que las 72 sin board. Las dos de
    `comunitarias` —H_0080 y H_0223— si tienen etiqueta, y por eso no
    entran aqui."""
    (a, b, c), ids_b = _board_en(ar, ins, ventana)
    cal_, val_ = ins.cal.muestra()
    ETIQUETA = dict(cal_ + val_)
    con_y = [i for i in ids_b if i in ETIQUETA]
    assert len(ids_b) == 2, 'las que tienen board en streets: %s' % ids_b
    assert len(con_y) == 0, (
        'y de esas, con etiqueta: %s. Si una ya lo tiene, el problema de los '
        '76 cortes no es solo "la mano no llego a board".' % con_y)