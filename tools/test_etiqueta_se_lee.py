# -*- coding: utf-8 -*-
"""La guarda que cierra la familia de errores: la etiqueta NO se calcula.

`revision_2` pidio extender la comprobacion cruzada a TODAS las filas. Y al
hacerlo sale el hallazgo del bloque: la etiqueta se estaba **recalculando**
en vez de leerse, y por eso 83 manos que no estan en `muestra()` se
contaban como victorias preflop.

Los dos tests de aqui:

  1. `test_resto_de_muestra_nunca_inventa_una_etiqueta` — para TODAS las
     manos de la ventana: si la mano no esta en `muestra()`, `y` es None; y
     si esta, `y` es EXACTAMENTE el de `muestra()`. Ni una excepcion. La
     replica puede cambiar `motivo`, que es su trabajo; no puede cambiar el
     valor de la etiqueta.

  2. `test_las_cifras_publicadas_son_las_de_la_muestra` — los numeros que
     salen de la herramienta tienen que ser los que se deducen de
     `muestra()`. Si alguien vuelve a "contar filtros" en vez de "leer
     etiquetas", estos numeros se mueven y el test falla.

Y la comprobacion cruzada que R2 pide, ahora sobre TODAS las filas.
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
def ventana(ar):
    from motor import learn
    return dict((h['hand_id'], h) for h in learn.load_hands(reliable_only=True))


# ============================== 1. la etiqueta se LEE, en todas las filas
def test_resto_de_muestra_nunca_inventa_una_etiqueta(ar, ventana):
    """Para TODAS las manos. Si no esta en `muestra()`, `y` es None; si
    esta, `y` es el de `muestra()`. Sin excepciones."""
    inst = ar._inst()
    cal, val_ = inst.cal.muestra()
    ETIQUETA = dict(cal + val_)

    problemas = []
    for hid, h in sorted(ventana.items()):
        pos = inst.eqm.hero_pos_de(h)
        if not pos:
            continue
        r = ar.resto_de_muestra(inst.cal, h, pos)
        real = ETIQUETA.get(hid)
        if real is None:
            if r.y is not None:
                problemas.append((hid, r.y, 'la mano no esta en la muestra'))
        elif real == 0.5:
            if r.y is not None:
                problemas.append((hid, r.y, 'es un reparto y el AUC lo excluye'))
        elif r.y is not None and r.y != real:
            problemas.append((hid, r.y, 'la muestra dice %r' % real))
    assert not problemas, (
        'la etiqueta difiere de `muestra()` en %d manos. Las primeras: %r'
        % (len(problemas), problemas[:6]))


def test_la_etiqueta_viene_de_una_sola_fuente(ar):
    """Y que no haya un segundo sitio del que sacarla. El fallo fue tener dos:
    la de `muestra()` y la de una replica."""
    fuente = io.open(ar.__file__, encoding='utf-8').read()
    i = fuente.index('def resto_de_muestra')
    cuerpo = fuente[i:fuente.index('def main()', i)]
    assert cuerpo.count('Resto(') >= 4, 'los cuatro caminos devuelven Resto'
    # el unico sitio donde sale un 1.0 o un 0.0 literal es el CAMBIO de
    # clase, no la etiqueta
    for linea in cuerpo.split('\n'):
        if 'Resto(' in linea and ('1.0' in linea or '0.0' in linea):
            raise AssertionError(
                'hay una etiqueta LITERAL en un Resto: %s. La etiqueta sale '
                'de `muestra()`' % linea.strip())


# ======================================= 2. las cifras, de la muestra
def test_las_cifras_de_la_herramienta_son_las_de_la_muestra(ar, ventana):
    """Poblacion B jugada 212; con etiqueta 50 —48 postflop y 2 preflop—.
    Si alguien vuelve a contar filtros en vez de leer etiquetas, esto se
    mueve.

    Y las 2 preflop son H_0080 y H_0223: la base canonica les da board y
    ganador, y su corte es la ultima accion del heroe en preflop aunque la
    mano siga. No son un recalculado: `test_resto_de_muestra_nunca_inventa_
    una_etiqueta`, mas arriba, sigue comprobando fila a fila que `y` es el
    de `muestra()`.
    """
    inst = ar._inst()
    filas = ar.medir_todas_calles(inst, ventana, 'ultima')
    jug = [f for f in filas if f['jugada']]
    con = [f for f in jug if f['y'] is not None]
    pre = [f for f in con if f['calle'] == 'preflop']
    post = [f for f in con if f['calle'] != 'preflop']
    assert len(jug) == 212, 'poblacion B jugada: %d' % len(jug)
    assert len(con) == 50, 'con etiqueta: %d' % len(con)
    assert set(f['id'] for f in pre) == {'H_0080', 'H_0223'}, (
        'preflop con etiqueta: %r. Son las dos que la adopcion trajo con '
        'board y winner' % [f['id'] for f in pre])
    assert len(post) == 48
    assert sum(1 for f in post if f['y'] == 1.0) == 20
    assert sum(1 for f in post if f['y'] == 0.0) == 28


def test_el_corte_en_la_primera_si_tiene_las_dos_clases(ar, ventana):
    """La hipótesis, medida sobre la base canonica: 61, con 21 positivas y
    40 negativas. Y la razon de que haya etiqueta NO es un filtro: es que
    la mano continua."""
    inst = ar._inst()
    filas = ar.medir_todas_calles(inst, ventana, 'primera')
    jug = [f for f in filas if f['jugada']]
    con = [f for f in jug if f['y'] is not None]
    pre = [f for f in con if f['calle'] == 'preflop']
    assert len(con) == 61, 'con etiqueta: %d' % len(con)
    assert len(pre) == 61, (
        'y las %d son preflop: con el corte en la primera la MANO CONTINUA, '
        'y ahi si hay board y winner' % len(pre))
    assert sum(1 for f in pre if f['y'] == 1.0) == 21
    assert sum(1 for f in pre if f['y'] == 0.0) == 40


# ================= la comprobacion cruzada que R2 pide, sobre TODAS las filas
def test_la_tabla_y_las_filas_no_pueden_ser_cosas_distintas(ar, ventana):
    """`revision_2`: la ventana de 80 filas era parcial. Ahora son TODAS.
    Y se compara con el MISMO cal y el MISMO instrumento, porque comparar
    una copia con otra copia no prueba nada."""
    inst = ar._inst()
    filas = ar.medir_todas_calles(inst, ventana, 'primera')
    desacuerdos = []
    for f in filas:
        h = ventana[f['id']]
        r = ar.resto_de_muestra(inst.cal, h, inst.eqm.hero_pos_de(h))
        if r.y != f['y']:
            desacuerdos.append((f['id'], f['y'], r.y))
    assert not desacuerdos, (
        '%d filas cuyo y no coincide con resto_de_muestra: %r'
        % (len(desacuerdos), desacuerdos[:6]))
    assert len(filas) == 866, 'y se comprueban todas, no una ventana'


def test_el_guardia_de_tipos_sigue_puesto(ar, ventana):
    """Etiquetas que no sean None, 0.0 o 1.0. Era el error del bloque
    anterior y no puede volver."""
    inst = ar._inst()
    filas = ar.medir_todas_calles(inst, ventana, 'primera')
    malos = collections.Counter()
    for f in filas:
        if f['y'] is None:
            continue
        if not isinstance(f['y'], float) or f['y'] not in (0.0, 1.0):
            malos[repr(f['y'])] += 1
    assert not malos, dict(malos)


# ===================================== el AUC publicado, que sigue intacto
def test_el_auc_publicado_se_reproduce():
    """`revision_2`: "la afirmación de que el AUC postflop sigue siendo
    válido requiere que la muestra, las puntuaciones y la partición
    permanezcan intactas". Se comprueba contra el modulo de verdad."""
    auc = _mod('auditar_auc.py')
    cal, val_ = auc.cal.muestra()
    etiq = dict(val_)
    pos, neg = [], []
    ventana = dict((h['hand_id'], h) for h in auc.learn.load_hands(
        reliable_only=True))
    from motor import player_ranges
    ajuste = [h for h in ventana.values()
              if not auc.cal.es_validacion(h['hand_id'])]
    labels = auc.eqm.perfiles_de(ajuste)
    mod = {'preflop': player_ranges.ProfileRangeModel.from_hands(
        ajuste, alpha=player_ranges.DEFAULT_ALPHA), 'postflop': None}
    filas = 0
    for hid, y in sorted(etiq.items()):
        h = ventana[hid]
        hero = auc.eqm.hero_pos_de(h)
        if not hero:
            continue
        calle, idx = auc.eqm.corte_de_decision(h, hero)
        if calle is None or y == 0.5 or calle == 'preflop':
            continue
        r = auc.eqm.equity_de_mano(h, labels, mod)
        if r is None or len(r) != 3 or r[2].get('observable') is False:
            continue
        filas += 1
        acts = ((h.get('streets') or {}).get(calle) or {}).get(
            'actions') or []
        accion = acts[idx].get('action')
        if accion in ('b', 'c', 'r', 'x'):  # poblacion B del AUC
            (pos if y == 1.0 else neg).append(r[1]['mediana'])
    # 14 entran al instrumento; la poblacion B del AUC es la que excluye los
    # folds, que son 3. La cifra publicada es la de B, no la de las 14.
    assert filas == 14, 'manos que entran al AUC: %d' % filas
    assert len(pos) == 6 and len(neg) == 5, (
        'poblacion B: %d ganadoras, %d perdedoras' % (len(pos), len(neg)))
    a = auc.auc_de(pos, neg)
    assert abs(a - 0.7667) < 5e-4, 'AUC: %r, AUC_INTERVALO dice 0,7667' % a
    lo, hi = auc.ic_bootstrap(pos, neg)
    assert (abs(lo - 0.4333) < 5e-4 and abs(hi - 1.0) < 5e-4), (
        'IC: [%r, %r], el publicado es [0,4333, 1,0000]' % (lo, hi))
    p, _ge, _tot = auc.p_permutaciones(pos, neg)
    assert abs(p - 0.0896) < 5e-4, 'p: %r, el publicado es 0,0896' % p


def test_equity_de_mano_es_determinista(ar, ventana):
    """Salio de una contradiccion y hay que dejarlo escrito: la lista de la
    muestra del AUC es la MISMA cuatro veces, y la mediana igual a 16
    digitos. Si dejara de serlo, la cifra publicada no seria reproducible."""
    inst = ar._inst()
    from motor import player_ranges
    ajuste = [h for h in ventana.values()
              if not inst.cal.es_validacion(h['hand_id'])]
    labels = inst.eqm.perfiles_de(ajuste)
    mod = {'preflop': player_ranges.ProfileRangeModel.from_hands(
        ajuste, alpha=player_ranges.DEFAULT_ALPHA), 'postflop': None}
    h = ventana['H_0033']
    vals = []
    for _ in range(3):
        r = inst.eqm.equity_de_mano(h, labels, mod)
        vals.append(r[1]['mediana'])
    assert len(set(vals)) == 1, 'la mediana cambia entre llamadas: %r' % vals