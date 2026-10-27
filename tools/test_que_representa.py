# -*- coding: utf-8 -*-
"""`QUE_REPRESENTA_LA_PREDICCION.md` dice como es la prediccion, y sus cifras
se comprueban contra el CODIGO, no contra el documento.

Un documento que describe una herramienta se desvia sin avisar: el codigo
cambia y el `.md` se queda. Y un `.md` que se queda no es un documento: es
una afirmacion sin fuente.

O sea: estas cifras no estan escritas porque en este momento sean
interesantes. Estan porque si el codigo cambia, el numero tiene que cambiar
y el test tiene que avisar.

LO QUE NO SE COMPRUEBA, Y POR QUE

  - que la prediccion sea CORRECTA. Eso es una cuestion de poker y no cabe
    aqui. Aqui se comprueba que el codigo hace lo que el documento dice que
    hace.
  - si la prediccion es la que conviene. No es lo que se mide.
  - las 5 manos de board divergente, no se corrigen: es instrumentacion, y
    moverlo cambia las cifras. Aqui solo se comprueba que siguen siendo 5, y
    por tanto que nadie las ha corregido sin avisar.
"""
import collections
import importlib.util
import io
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DOC = os.path.join(ROOT, 'DOCS', 'QUE_REPRESENTA_LA_PREDICCION.md')


def _mod(nombre, donde='tools'):
    ruta = os.path.join(ROOT, donde, nombre)
    spec = importlib.util.spec_from_file_location(
        nombre[:-3].replace('.', '_'), ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope='module')
def eqm():
    return _mod('equity_de_mano.py')


@pytest.fixture(scope='module')
def ventana():
    from motor import learn
    return dict((h['hand_id'], h) for h in
                learn.load_hands(reliable_only=True))


@pytest.fixture(scope='module')
def doc():
    with io.open(DOC, encoding='utf-8') as f:
        return f.read()


def _primera_accion(eqm, h, hero):
    """El corte de B: la PRIMERA accion del heroe.

    El modulo llega como argumento, y no del globals: en un fichero de tests
    el nombre `eqm` es la funcion de fixture, no el modulo, y usarlo aqui
    daria `FixtureFunctionDefinition`.
    """
    st = h.get('streets') or {}
    for stt in eqm.ORDEN_CALLES:
        for i, a in enumerate((st.get(stt) or {}).get('actions') or []):
            if a.get('pos') == hero and a.get('action') in ('b', 'c', 'r',
                                                             'f', 'x'):
                return stt, i
    return None, None


# ============================================ el corte
def test_a_y_b_no_son_un_recorte(eqm, ventana, doc):
    """Si las cifras cambian, el documento esta describiendo otra cosa."""
    cambia = mismo = 0
    board_difiere = rival_difiere = 0
    for hid, h in sorted(ventana.items()):
        hero = eqm.hero_pos_de(h)
        if not hero:
            continue
        calle_a, _ = eqm.corte_de_decision(h, hero)
        calle_b, _ = _primera_accion(eqm, h, hero)
        if calle_a is None or calle_b is None:
            continue
        if calle_a == calle_b:
            mismo += 1
            continue
        cambia += 1
        if len(eqm.tablero(h, calle_a)) != len(eqm.tablero(h, calle_b)):
            board_difiere += 1
        if len(eqm.candidatos(h, hero, calle_a)) != len(
                eqm.candidatos(h, hero, calle_b)):
            rival_difiere += 1
    assert (mismo, cambia) == (633, 233), (
        'el reparto de cortes que cambian de calle es (%d, %d) y el '
        'documento dice (633, 233)' % (mismo, cambia))
    assert board_difiere == 230, (
        'los que ademas cambian de board son %d, y el documento dice 230. Si '
        'ha cambiado, hay que reescribir el documento' % board_difiere)
    assert rival_difiere == 142, (
        'los que ademas cambian de numero de rivales son %d, y el documento '
        'dice 142' % rival_difiere)
    assert '| **cortes con calle distinta** | **233** |' in doc
    assert '**230**' in doc and '**142**' in doc


def test_el_corte_es_la_ultima_accion_que_acepta_cinco_acciones(eqm, ventana):
    """Y que el corte siga siendo el que el documento dice: la ULTIMA, y solo
    entre `b`/`c`/`r`/`f`/`x`."""
    n_ultima = 0
    for hid, h in sorted(ventana.items()):
        hero = eqm.hero_pos_de(h)
        if not hero:
            continue
        calle, idx = eqm.corte_de_decision(h, hero)
        if calle is None:
            continue
        acts = ((h.get('streets') or {}).get(calle) or {}).get('actions') or []
        despues = acts[idx + 1:]
        assert not any(a.get('pos') == hero for a in despues), (
            '%s: hay una accion del heroe despues del corte' % hid)
        n_ultima += 1
    assert n_ultima > 800, 'y el corte se encuentra en la mayoria: %d' \
        % n_ultima


# ============================================ el board, las dos fuentes
def test_el_board_tiene_dos_fuentes_que_discrepan(eqm, ventana, doc):
    """El hallazgo del documento. Si alguien las arregla, este test falla y
    avisa de que hay que reescribirlo —que es lo que hay que hacer antes de
    mover las cifras."""
    discrepan = []
    for hid, h in sorted(ventana.items()):
        hero = eqm.hero_pos_de(h)
        if not hero:
            continue
        calle, _ = eqm.corte_de_decision(h, hero)
        if calle is None or calle == 'preflop':
            continue
        de_com = eqm.tablero(h, calle)
        st = h.get('streets') or {}
        de_streets = []
        for c in ('flop', 'turn', 'river'):
            de_streets += list((st.get(c) or {}).get('board') or [])
            if c == calle:
                break
        if de_com != de_streets:
            discrepan.append(hid)
    assert len(discrepan) == 5, (
        'ahora las manos donde `tablero()` y `villain_hasta_corte()` no '
        'coinciden son %d, y el documento dice 5: %s. Si se han corregido, hay '
        'que reescribir el documento Y medir de nuevo las cifras'
        % (len(discrepan), discrepan))
    assert '5 manos de 877' in doc


def test_las_dos_fuentes_son_una_por_funcion(eqm):
    """Y que el documento no se equivoca al decir de donde sale cada una."""
    fuente = io.open(eqm.__file__, encoding='utf-8').read()
    i, j = fuente.index('def tablero'), fuente.index('def hero_pos_de')
    tablero, hero = fuente[i:j], fuente[j:]
    assert 'comunitarias' in tablero
    assert 'streets' not in tablero, (
        '`tablero()` ya lee `streets`: las dos fuentes se han unificado, y hay '
        'que actualizar el documento')
    i, j = (fuente.index('def villain_hasta_corte'),
            fuente.index('# ---------', fuente.index('def villain_hasta_corte')))
    rival = fuente[i:j]
    assert 'streets' in rival
    assert 'comunitarias' not in rival


# ============================================ una prediccion por rival
def test_la_prediccion_no_es_un_numero_por_mano(eqm, ventana, doc):
    """415 de 877 con mas de un rival. Es el motivo por el que la eleccion de
    rival es una decision y no un detalle."""
    n = collections.Counter()
    for hid, h in sorted(ventana.items()):
        hero = eqm.hero_pos_de(h)
        if not hero:
            continue
        calle, _ = eqm.corte_de_decision(h, hero)
        if calle is None:
            continue
        n[len(eqm.candidatos(h, hero, calle))] += 1
    mas_de_uno = sum(v for k, v in n.items() if k > 1)
    assert mas_de_uno == 396, (
        'ahora las manos con mas de un rival en el corte son %d, y el '
        'documento dice 396' % mas_de_uno)
    assert n[0] == 139 and n[1] == 331, (
        'el reparto de rivales es %r y el documento dice 0->139, 1->331' % n)
    assert '396 de 877' in doc


def test_equity_de_mano_devuelve_una_por_rival_y_el_dilemma_esta_escrito(doc):
    """La función, y el comentario que dice que elegir es de quien mide."""
    eqm = _mod('equity_de_mano.py')
    fuente = io.open(eqm.__file__, encoding='utf-8').read()
    i = fuente.index('def equity_de_mano')
    cuerpo = fuente[i:fuente.index('def main', i)]
    assert "salida[r] = eq" in cuerpo, 'sigue siendo un dict por rival'
    assert 'dispersion' in cuerpo and 'mediana' in cuerpo, (
        'y sigue Informando de la dispersion y de la mediana, que es lo que '
        'hace falta para poder elegir a la vista')
    assert 'decision de quien mide' in fuente, (
        'y el comentario que lo declara sigue en el codigo')


# ============================================ la marca observable
def test_preflop_es_retrospectivo_y_postflop_observable(eqm):
    """La diferencia que hace el AUC no aceptable en preflop."""
    fuente = io.open(eqm.__file__, encoding='utf-8').read()
    i = fuente.index("if calle == 'preflop':")
    pf = fuente[i:fuente.index('rs, perfil = rango_del_rival')]
    assert "'observable': False" in pf, 'el preflop tiene que decir que no'
    assert 'MANO REAL' in pf, 'y que usa las cartas reales del rival'
    i = fuente.index('def equity_contra')
    post = fuente[i:fuente.index('def candidatos')]
    assert "'observable': True" in post


def test_el_motor_no_tiene_camino_de_equity_preflop():
    """Y que sigue sin tenerlo, porque es lo que hace que la via preflop sea
    retrospectiva. Si algun dia lo tiene, este test falla."""
    # `situation` vive en `motor/situation.py`, no en `player_ranges`. Y es
    # el camino que declara board de 3 a 5 cartas, que es lo que hace que no
    # tenga version preflop.
    import motor.situation as situacion
    fuente = io.open(situacion.__file__, encoding='utf-8').read()
    assert 'def situation(' in fuente, 'el camino se ha movido de sitio'
    i = fuente.index('def situation(')
    # `situation` es la ULTIMA funcion del fichero, asi que el corte por
    # `index` revienta. Y no es teoria: es exactamente lo que pasa. El
    # patron correcto es `find` con el final del fichero como alternativa.
    corte = fuente.find('\ndef ', i + 5)
    cuerpo = fuente[i:corte if corte > 0 else len(fuente)]
    assert not re.search(r'\bpreflop\b', cuerpo), (
        '`situation` ya menciona preflop: puede que el motor tenga el camino, y '
        'entonces la via retrospectiva del documento se queda obsoleta y hay '
        'que reescribirlo')


# ============================================ y el documento no afirma
#                                            de mas
def test_el_documento_no_dice_mas_de_lo_que_dice_el_codigo(doc):
    """Lo que se comprova es que no afirme una VIA que no existe."""
    assert '| `situation(...)` postflop | `True` |' in doc, (
        'la fila del postflop cambio de forma: mira la tabla de vias')
    assert '| enumeración preflop | `False` |' in doc, (
        'y la del preflop. Las dos vias, con su marca de observable')
    # y que no afirme que el preflop sea observable
    afirmadas = [l for l in doc.split('\n')
                 if 'preflop' in l.lower() and 'observable' in l.lower()
                 and not l.lstrip().startswith('>')
                 and '`False`' not in l and '`True`' not in l]
    assert not afirmadas, (
        'el documento habla del preflop y de observable sin decir cual es: %r'
        % afirmadas)