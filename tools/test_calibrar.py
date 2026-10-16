# -*- coding: utf-8 -*-
"""`tools/calibrar.py` — el contrato de lo que se puede publicar.

Cinco bloques:

  1. LA MUESTRA. Que los numeros del contrato (156 / 117 / 39) sigan
     saliendo. Es un test de contrato, no de cuenta: si el filtro cambia,
     el documento y la herramienta dejan de hablar de lo mismo.
  2. LA ETIQUETA. Que no se inventen empates. Un `y = 0,5` puesto sin
     evidencia es exactamente el fallo que el plan prohibe.
  3. LA PARTICION. Disjunta y estable. La lista esta versionada; que sea
     reproducible es lo que hace que el diff signifique algo.
  4. QUE LA METRICA VE AL PARAMETRO. Si `L_prim` no cambia con `alpha`,
     el numero que produce no tiene origen.
  5. EL GUARDIAN DE MONOTONIA. Que se niegue a nombrar ganador cuando la
     curva es monotonica, porque en ese caso no esta eligiendo.
"""
import hashlib
import importlib.util
import os

import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cal():
    ruta = os.path.join(ROOT, 'tools', 'calibrar.py')
    spec = importlib.util.spec_from_file_location('calibrar_fase_d', ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- 1. muestra
@pytest.fixture(scope='module')
def cal():
    return _cal()


def test_la_muestra_son_los_numeros_del_contrato(cal):
    """156 utilizables, 117 de calibracion, 39 de validacion.

    FASE_D_PLAN §2.1.1 y CALIBRACION_DEFAULT_ALPHA.md §1. Si esto cambia,
    los tres documentos cambian con el.
    """
    c, v = cal.muestra()
    assert len(c) == 117
    assert len(v) == 39
    assert len(c) + len(v) == 156


def test_la_ventana_es_la_declarada(cal):
    assert len(cal.ventana()) == 877


def test_la_particion_versionada_coincide_con_la_calculada(cal):
    """DOCS/PARTICION_FASE_D.md tiene que ser el fichero que sale aqui."""
    ruta = os.path.join(ROOT, 'DOCS', 'PARTICION_FASE_D.md')
    with open(ruta, encoding='utf-8') as fh:
        texto = fh.read()
    c, v = cal.muestra()
    for hid, _y in v[:5]:
        assert '`%s`' % hid in texto, ('validacion fuera del documento: %s'
                                       % hid)
    assert '| validacion | 39 |' in texto
    assert '| calibracion | 117 |' in texto
    assert '| utilizables | 156 |' in texto


# -------------------------------------------------------------- 2. etiqueta
def test_no_se_inventan_empates(cal):
    """Varios ganadores SIN texto de showdown -> no utilizable.

    Es el caso que `revision_2`.labelo: asignar `y = 0,5` por defecto seria
    inventar la etiqueta. Se comprueba que la rama existe y que no
    devuelve una etiqueta.
    """
    h = {'hand_id': 'X', 'players': [
        {'pos': 'UTG', 'cards': 'AhKd'},
        {'pos': 'BTN', 'cards': 'QsJs'},
        {'pos': 'BB', 'cards': '2h3d'},
    ], 'winner': ['hero', 'p2'], 'showdown': {}}
    y, ok = cal.etiqueta(h)
    assert ok is False
    assert y is None


def test_showdown_que_nombra_uno_si_resuelve(cal):
    """Con `showdown.winner1` nombra a uno solo, la mano es utilizable."""
    h = {'hand_id': 'X', 'players': [
        {'pos': 'UTG', 'cards': 'AhKd'},
        {'pos': 'BTN', 'cards': 'QsJs'},
        {'pos': 'BB', 'cards': '2h3d'},
    ], 'winner': ['hero', 'p2'], 'showdown': {'winner1': 'BB'}}
    y, ok = cal.etiqueta(h)
    assert ok is True
    # el ganador es el hero, asi que y = 1,0
    assert y == 1.0


def test_el_hero_es_el_primer_jugador_con_cartas(cal):
    """No es `players[0]`: es el primero que tiene cartas.

    Si el codigo usara `players[0]`, en esta mano llamaria hero a UTG —que
    no tiene cartas— y daria `y = 0,0`. Con la convencion correcta el hero
    es MP, que es quien gano, y sale `y = 1,0`.
    """
    h = {'hand_id': 'X', 'players': [
        {'pos': 'UTG', 'cards': ''},
        {'pos': 'MP', 'cards': 'AhKd'},
        {'pos': 'BTN', 'cards': 'QsJs'},
    ], 'winner': ['p1']}
    y, ok = cal.etiqueta(h)
    assert ok is True
    assert cal.hero_de(h) == 'MP'
    assert y == 1.0


# ------------------------------------------------------------- 3. particion
def test_la_particion_es_disjunta(cal):
    c, v = cal.muestra()
    ci = {i for i, _ in c}
    vi = {i for i, _ in v}
    assert not (ci & vi)
    assert len(ci) == 117 and len(vi) == 39


def test_la_particion_es_estable(cal):
    """La misma entrada da la misma particion, siempre."""
    assert all(cal.es_validacion(h) ==
               (int(hashlib.sha256(h.encode('utf-8')).hexdigest(), 16)
                % 10 < 3)
               for h in ('H_0001', 'H_0500', 'H_1070'))


def test_la_particion_no_toca_datos(cal):
    """`particion` sin `--escribir` no escribe nada.

    El contrato dice dry-run por defecto. Si esto falla, `calibrar.py
    particion` esta escribiendo en `data/` sin que nadie lo pidiera.
    """
    antes = os.path.getmtime(os.path.join(ROOT, 'data', 'hands_db.jsonl'))
    c, v = cal.muestra()
    cal.cmd_particion(type('A', (), {'escribir': False})())
    assert os.path.getmtime(os.path.join(ROOT, 'data', 'hands_db.jsonl')) \
        == antes


# -------------------------------------------------- 4. la metrica ve a alpha
def test_l_prim_cambia_con_alpha(cal):
    """Si esto falla, `L_prim` es ciega y su numero no tiene origen."""
    c, _v = cal.muestra()
    a1, n1 = cal.l_prim(1.0, c)
    a9, n9 = cal.l_prim(9.0, c)
    assert a1 is not None and a9 is not None
    assert n1 == n9 and n1 > 0
    assert a1 != a9, 'L_prim no responde a alpha'


def test_l_prim_usa_la_etiqueta_de_perfil_y_no_el_nombre(cal):
    """`p_matrix` esta indexado por (etiqueta, spot).

    Pasar el NOMBRE del jugador hace que `opp` sea None en todos los
    eventos, y con ello que `L_prim` salga igual para todos los alpha. El
    fallo es silencioso: da numeros, y son el prior.
    """
    c, _v = cal.muestra()
    labels = cal.etiquetas()
    manos = cal.manos_de(c)
    from motor import learn, player_ranges as PR
    modelo = PR.ProfileRangeModel.from_hands(manos, labels=labels, alpha=2.0)
    con_opp = 0
    for h in manos:
        for ev in learn.preflop_events(h):
            if not ev.hand_known:
                continue
            perfil = labels.get(ev.player, ev.player)
            if modelo.opp.get((perfil, ev.denom)) is not None:
                con_opp += 1
    assert con_opp > 0, 'ningun evento cae en una celda con opp'


# ----------------------------------------------- 5. el guardian de monotonia
def test_el_guardian_detecta_monotonia_creciente():
    mod = _cal()
    assert mod.es_monotona([0.5, 1.0, 2.0], [0.17, 0.30, 0.49]) is True


def test_el_guardian_detecta_monotonia_decreciente():
    mod = _cal()
    assert mod.es_monotona([0.5, 1.0, 2.0], [0.49, 0.30, 0.17]) is True


def test_el_guardian_no_dispara_si_hay_un_maximo():
    mod = _cal()
    assert mod.es_monotona([0.5, 1.0, 2.0], [0.30, 0.10, 0.30]) is False


def test_el_guardian_necesita_tres_puntos():
    """Con dos puntos todo parece monotonico. No es una distincion."""
    mod = _cal()
    assert mod.es_monotona([1.0, 2.0], [0.3, 0.4]) is False


def test_la_curva_real_de_alpha_es_monotona(cal):
    """El hallazgo de CALIBRACION_DEFAULT_ALPHA.md §3.

    No es un test de que la metrica sea buena: es un test de que sigue
    siendo monotona, que es justo lo que la invalida para elegir un
    parametro de regularizacion. Si algun dia deja de serlo, este test
    falla y obliga a reescribir el veredicto.
    """
    c, _v = cal.muestra()
    vals = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    meds = []
    for a in vals:
        m, _n = cal.l_prim(a, c)
        assert m is not None
        meds.append(m)
    assert cal.es_monotona(vals, meds) is True


def test_la_secundaria_es_honesta_sobre_no_poder_calcularse(cal):
    """`L_sec` devuelve None CON MOTIVO, no un numero inventado."""
    v, motivo = cal.l_sec(2.0, cal.muestra()[1])
    assert v is None
    assert 'API' in motivo or 'api' in motivo


def test_el_ganador_no_se_publica_sin_secundaria(cal, capsys):
    """El comando sale con 2 y no nombra ganador."""
    import sys
    argv = sys.argv
    sys.argv = ['calibrar.py', '--param', 'DEFAULT_ALPHA',
                '--valores', '0.5', '1.0', '1.5', '2.0', '2.5', '3.0']
    try:
        rc = cal.main()
    finally:
        sys.argv = argv
    salida = capsys.readouterr().out
    assert rc == 2
    assert 'NO SE CALIBRA' in salida
    assert 'mejor L_prim' not in salida


def test_default_alpha_sigue_en_dos():
    """La razon de todo lo de arriba, convertida en condicion.

    Si alguien cambia `DEFAULT_ALPHA` sin pasar por aqui, este test falla.
    Es el test que `revision_1` pidio para la Tarea 4.
    """
    import io
    src = io.open(os.path.join(ROOT, 'motor', 'player_ranges.py'),
                  encoding='utf-8').read()
    linea = next(l for l in src.split('\n')
                 if l.startswith('DEFAULT_ALPHA'))
    assert '2.0' in linea, ('DEFAULT_ALPHA movido a otra parte: %s'
                            % linea.strip())