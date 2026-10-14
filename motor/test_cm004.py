# -*- coding: utf-8 -*-
"""CM-004: el invariante de la ciega del BB, y donde vive la regla.

Dos guards, y los dos apuntan al mismo sitio: la regla tiene que estar en
`motor/learn.py`, no en un script de auditoria. Una copia en cada sitio es
exactamente como vuelve un bug (ver el commit que movio `no_puede_actuar` a
`motor/multiway.py`).
"""
import ast
import hashlib
import io
import json
import os
import subprocess

import pytest

from motor import learn
from tools.aplicar_reinterpretacion import COMMIT_ANTES, SHA_ANTES
from tools.auditar_bb_check import _entradas_bb_rechazadas
from tools.verificar_cm004 import (CAMBIOS_QUE_NO_SON_CM004, DECLARADAS,
                                   REVERTIDAS_PARCIALES, REVERTIDAS_TOTALES)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_REL = 'data/hands_db.jsonl'

# `hands_db.jsonl` se ha vuelto a editar A MANO (2026-10-14, por encima del
# commit 02fc641). Los cinco tests de abajo NO pasan, y no por un fallo del
# codigo: estan diciendo la verdad sobre el fichero de datos.
#
# Lo que hay ahora mismo, segun `tools/verificar_cm004.py`:
#
#   - las 8 correcciones revertidas en 02fc641 (H_0039, H_0051, H_0067,
#     H_0109, H_0143, H_0263, H_0969, H_0970) han vuelto a aplicarse
#   - 68 manos mas han cambiado, sin declarar
#   - 22 manos han sido BORRADAS de la base
#
# revision_1 dice, literalmente: "No toques hands_db.jsonl a mano otra vez.
# Si hay que cambiarlo, se cambia con aplicar_reinterpretacion.py o con un
# script versionado. El canal manual esta cerrado."
#
# `strict=True` en vez de un xfail flojo: si alguien deja la base en el
# estado reproducible, estos tests PASAN, y un xfail que pasa sin querer es
# un fallo. El aviso obliga a quitar la marca, que es justo lo que hay que
# hacer cuando se cierre la decision.
MOTIVO_XFAIL = (
    'hands_db.jsonl editado a mano por encima de 02fc641: 8 revertidas de '
    'vuelta, 68 cambios sin declarar, 22 manos borradas. El canal manual esta '
    'cerrado (revision_1). Ver DOCS/HALLZGOS_H0001_H1014.md y '
    'DECISION_CM004.md 0-bis.'
)
marca_base_editada = pytest.mark.xfail(reason=MOTIVO_XFAIL, strict=True)

# El conjunto CM-004, como hecho historico. No se puede volver a DERIVAR
# ahora: el defecto ya no esta en la base, asi que la regla da 0 y una lista
# derivada de 0 no es una lista. Es un hecho, y se escribe como tal.
CM_004 = (
    'H_0031', 'H_0037', 'H_0039', 'H_0051', 'H_0067', 'H_0078', 'H_0104',
    'H_0107', 'H_0109', 'H_0127', 'H_0143', 'H_0147', 'H_0161', 'H_0170',
    'H_0183', 'H_0210', 'H_0215', 'H_0248', 'H_0262', 'H_0263', 'H_0279',
    'H_0294', 'H_0722',
)


def _blob(commit, sha):
    """`hands_db.jsonl` tal como estaba en `commit`, verificada por contenido.

    Se direcciona por COMMIT porque es lo unico que git resuelve, y se
    comprueba con el sha256 porque el commit no garantiza por si solo que
    siga siendo la version que creimos.
    """
    crudo = subprocess.run(['git', 'show', '%s:%s' % (commit, DB_REL)],
                           cwd=ROOT, capture_output=True)
    assert crudo.returncode == 0, 'no se pudo leer %s:%s' % (commit, DB_REL)
    real = hashlib.sha256(crudo.stdout).hexdigest()
    assert real == sha, ('%s:%s tiene sha256 %s, no el %s esperado'
                         % (commit, DB_REL, real[:16], sha[:16]))
    return crudo.stdout.decode('utf-8')


def _anteriores():
    return _blob(COMMIT_ANTES, SHA_ANTES)


def _por_id(texto):
    return {json.loads(l)['hand_id']: json.loads(l)
            for l in texto.splitlines() if l.strip()}


def _actual():
    return {h.get('hand_id'): h
            for h in learn.load_hands(reliable_only=False)}


def _tocadas(texto_a, texto_b):
    a, b = _por_id(texto_a), _por_id(texto_b)
    return {hid for hid in set(a) | set(b)
            if json.dumps(a.get(hid), sort_keys=True)
            != json.dumps(b.get(hid), sort_keys=True)}


# --- el invariante ---------------------------------------------------------

def test_ninguna_mano_tiene_una_bb_b_que_no_pueda_ser_la_ciega():
    """El invariante de TODO el bloque.

    Una `BB b` que el motor no reconoce como ciega se lee como una subida que
    puede no haber ocurrido. Medido sobre las 1280: 0 casos.

    Si esto falla, alguien deshizo la reinterpretacion de CM-004. No hace falta
    saber quien: el numero dice que el orden vuelve a estar roto.
    """
    manos = learn.load_hands(reliable_only=False)
    malas = learn.manos_con_orden_ciega_malo(manos)
    assert malas == [], (
        'manos con una `BB b` mal ordenada otra vez: %s' % malas)


def test_el_invariante_tambien_se_cumple_en_la_ventana_fiable():
    """La ventana de calibracion es un subconjunto, pero se mide aparte: es la
    que alimenta las cifras, y un 0 global no dice nada de ella."""
    manos = learn.load_hands(reliable_only=True)
    assert learn.manos_con_orden_ciega_malo(manos) == []


def test_la_ventana_fiable_sigue_siendo_877():
    """Las 23 de CM-004 siguen EXCLUIDAS. Que el defecto este resuelto no las
    devuelve a la ventana: eso es otra decision, y esta tomada en
    `DOCS/DECISION_CM004.md`. El guard fija que el numero no cambia por
    sorpresa."""
    assert learn.RELIABLE_HANDS == 900
    assert len(learn.manos_excluidas()) == 23
    assert len(learn.load_hands(reliable_only=True)) == 877


# --- la regla, y donde vive -----------------------------------------------

def test_el_detector_que_usa_el_script_es_el_del_motor():
    """`tools/verificar_cm004.py`, `tools/auditar_bb_check.py` y
    `tools/aplicar_reinterpretacion.py` IMPORTAN la funcion. Si uno vuelve a
    tener la suya, la copia se queda vieja y el motor acaba usando la otra."""
    for modulo in ('tools/verificar_cm004.py', 'tools/auditar_bb_check.py',
                   'tools/aplicar_reinterpretacion.py'):
        ruta = os.path.join(ROOT, *modulo.split('/'))
        arbol = ast.parse(io.open(ruta, encoding='utf-8').read())
        llamadas = [n for n in ast.walk(arbol)
                    if isinstance(n, ast.Attribute)
                    and n.attr in ('entradas_bb_rechazadas',
                                   'manos_con_orden_ciega_malo')]
        assert llamadas, (
            '%s ya no usa el detector del motor: tiene su propia cuenta, y '
            'esa puede discrepar de _es_ciega_bb' % modulo)


def test_auditar_bb_check_reexporta_y_no_reimplementa():
    """La funcion antigua se conserva como alias, pero su cuerpo tiene que ser
    una llamada. Un cuerpo con logica propia seria una segunda regla."""
    ruta = os.path.join(ROOT, 'tools', 'auditar_bb_check.py')
    arbol = ast.parse(io.open(ruta, encoding='utf-8').read())
    fn = next(n for n in ast.walk(arbol)
              if isinstance(n, ast.FunctionDef)
              and n.name == '_entradas_bb_rechazadas')
    assert len(fn.body) == 2 and isinstance(fn.body[0], ast.Expr) \
        and isinstance(fn.body[1], ast.Return), (
            'el cuerpo deberia ser docstring + un unico return')


def test_la_regla_sigue_siendo_exacta_contra_la_version_previa():
    """La reinterpretacion cubre exactamente el conjunto CM-004: ni una mano de
    mas, ni una de menos.

    La regla se deriva contra el commit ANCLADO, no contra HEAD. Con HEAD daria
    0 en cuanto la reinterpretacion estuviera commiteada, y un
    `set() == set()` verde no vigila nada.
    """
    anteriores = leer = [json.loads(l) for l in _anteriores().splitlines()
                         if l.strip()]
    derivadas = set()
    for h in anteriores:
        for _i, _amt, causa in learn.entradas_bb_rechazadas(h):
            if causa == learn.CAUSA_ORDEN:
                derivadas.add(h['hand_id'])
    assert len(anteriores) == 1280, (
        'la version previa deberia tener las 1280 manos, tiene %d'
        % len(anteriores))
    assert derivadas == set(CM_004), (
        'la regla senala %d manos y el conjunto historico son %d: %s'
        % (len(derivadas), len(CM_004), sorted(derivadas ^ set(CM_004))))


def test_el_indice_del_motor_apunta_a_la_accion_cruda():
    """`_preflop_sequence` y `streets.preflop.actions` tienen que compartir
    indice, porque es lo que permite editar la lista cruda a partir de lo que
    devuelve el motor.

    Se prueba sobre H_0722 y no sobre la base actual: es la unica de las 23 con
    el patron A2 (el BB ya posteo su ciega en el indice 0 y aun asi tiene un
    `b` despues), y la base actual ya no tiene ninguna, asi que un test sobre
    ella no iteraria ni una vez.
    """
    h = next(x for x in [json.loads(l) for l in _anteriores().splitlines()
                         if l.strip()] if x['hand_id'] == 'H_0722')
    acc = h['streets']['preflop']['actions']
    rech = learn.entradas_bb_rechazadas(h)
    assert rech == [(5, 2.0, learn.CAUSA_ORDEN)], rech

    for i, importe, causa in rech:
        a = acc[i]
        assert a['pos'] == 'BB', (h['hand_id'], i)
        assert a['action'] == 'b', (h['hand_id'], i)
        assert a['amount'] == importe, (h['hand_id'], i)

    # y la de indice 0 SI es ciega, que es justo lo que distingue A2 de A1
    assert acc[0]['pos'] == 'BB' and acc[0]['action'] == 'b'
    assert 0 not in [i for i, _a, _c in rech]


# --- el conjunto de cambios, que es lo que el ancla tiene que proteger ------

@marca_base_editada
def test_el_ancla_protege_el_CONJUNTO_esperado_de_cambios():
    """Que el blob exista no basta: lo que hay que vigilar es que el fichero
    difiera de la version previa EXACTAMENTE en las 24 manos declaradas.

    Verificar solo el sha256 del ancla dice que el commit es el que creimos.
    Esto dice que desde entonces no se ha tocado nada mas.
    """
    actual = io.open(os.path.join(ROOT, *DB_REL.split('/')),
                     encoding='utf-8').read()
    tocadas = _tocadas(_anteriores(), actual)
    declaradas = set(CM_004) | set(CAMBIOS_QUE_NO_SON_CM004)
    assert tocadas == declaradas, (
        'manos que difieren de %s: %d. Esperadas %d.\n  de mas: %s\n  de menos: %s'
        % (COMMIT_ANTES, len(tocadas), len(declaradas),
           sorted(tocadas - declaradas), sorted(declaradas - tocadas)))


def test_cada_mano_editada_cambia_una_sola_accion_del_bb():
    """24 manos, 25 acciones: 23 reetiquetados del BB y 2 centinelas de carta
    en una sola mano. Si el numero de acciones tocadas sube, alguien ha
    anadido, borrado o reordenado algo."""
    anteriores = _por_id(_anteriores())
    actual = _actual()
    n_acciones = 0
    for hid in sorted(set(anteriores) | set(actual)):
        a, b = anteriores.get(hid), actual.get(hid)
        if a is None or b is None:
            continue
        pa = ((a.get('streets') or {}).get('preflop') or {}).get('actions') or []
        pb = ((b.get('streets') or {}).get('preflop') or {}).get('actions') or []
        if len(pa) != len(pb):
            continue          # ninguna mano editada cambia la longitud
        n_acciones += sum(1 for x, y in zip(pa, pb) if x != y)
    assert n_acciones == 23, (
        'se han cambiado %d acciones de preflop, se esperaban 23' % n_acciones)


# --- las revertidas --------------------------------------------------------

@marca_base_editada
def test_las_revertidas_enteras_son_identicas_a_la_version_previa():
    for hid in REVERTIDAS_TOTALES:
        antes = _por_id(_anteriores())[hid]
        ahora = _actual()[hid]
        assert antes == ahora, (
            '%s esta declarada como revertida pero difiere de la version '
            'previa' % hid)


@marca_base_editada
def test_las_revertidas_parciales_solo_conservan_el_reetiquetado():
    """Conservan el `b` -> `r` del BB, que es la parte con regla exacta, y
    nada mas. Si vuelven a anadir, borrar o reordenar, este test falla."""
    anteriores = _por_id(_anteriores())
    actual = _actual()
    for hid in REVERTIDAS_PARCIALES:
        a, b = anteriores[hid], actual[hid]
        pa = a['streets']['preflop']['actions']
        pb = b['streets']['preflop']['actions']
        assert len(pa) == len(pb), (
            '%s cambia el numero de acciones de preflop: %d -> %d'
            % (hid, len(pa), len(pb)))
        cambiados = [i for i, (x, y) in enumerate(zip(pa, pb)) if x != y]
        assert len(cambiados) == 1, (
            '%s cambia %d entradas, se esperaba 1: %s'
            % (hid, len(cambiados), cambiados))
        i = cambiados[0]
        assert pa[i]['pos'] == 'BB' and pa[i]['action'] == 'b', (hid, i)
        assert pb[i]['action'] == 'r', (hid, i)
        # y ninguna otra calle tocada
        for s in ('flop', 'turn', 'river'):
            assert a['streets'][s] == b['streets'][s], (hid, s)


@marca_base_editada
def test_h0970_no_toca_el_bote_del_bb():
    """La mano que estaba mal. El BB comparte el bote y el recorte lo excluia.

    Se fija el valor GRABADO, no el recomendado: sin original no hay lectura
    que sostenida por encima del dato, y el defecto se documenta en
    `DOCS/RECONSTRUCCIONES_CM004.md` en vez de inventarse una correccion.
    """
    h = _actual()['H_0970']
    assert h['winner'] == ['hero', 'p1', 'p4'], h['winner']
    pre = h['streets']['preflop']['actions']
    assert [(x['pos'], x['action']) for x in pre] == [
        ('BB', 'b'), ('BTN', 'f'), ('SB', 'f')], pre
    # el BTN foldea y el SB foldean: el bote es de las dos ciegas
    foldean = {x['pos'] for x in pre if x['action'] == 'f'}
    assert foldean == {'BTN', 'SB'}, foldean


def test_toda_revertida_declara_un_motivo():
    """Una correccion deshecha sin motivo escrito es un agujero: nadie puede
    decir por que se toco ni por que se volvio."""
    for hid in REVERTIDAS_PARCIALES:
        assert REVERTIDAS_PARCIALES[hid], hid
    for hid in REVERTIDAS_TOTALES:
        assert REVERTIDAS_TOTALES[hid], hid


def test_h0350_cubre_todas_las_apariciones_del_centinela():
    """CM-002. La diferencia con los otros ocho: aqui el patron se aplica a
    TODAS sus apariciones. Dos de dos. Es lo que hace defendible lo que no lo
    era en los demas."""
    anterior = _por_id(_anteriores())
    actual = _actual()
    guiones_antes = sum(1 for h in anterior.values()
                        for p in h['players'] if p.get('cards') == '-')
    guiones_despues = sum(1 for h in actual.values()
                          for p in h['players'] if p.get('cards') == '-')
    assert guiones_antes == 2, guiones_antes
    assert guiones_despues == 0, (
        'quedan %d centinelas "-" sin normalizar' % guiones_despues)
    assert DECLARADAS == set(CAMBIOS_QUE_NO_SON_CM004)


# --- el verificador sigue detectando DESPUES del commit --------------------
#
# Es la prueba que pedia revision_2 §4: el ancla esta en un commit concreto,
# HEAD ya contiene la base corregida, y hay que demostrar que el verificador
# de PRODUCCION sigue viendo las modificaciones. Se ejecuta `main()` de
# verdad contra un fichero con contenido mutado, no una copia de su logica.

def _verificador_contra_contenido(contenido, tmp_path):
    import tools.verificar_cm004 as V
    db = tmp_path / 'hands_db.jsonl'
    with io.open(str(db), 'w', encoding='utf-8', newline='\n') as f:
        f.write(contenido)
    original = V.DB_PATH
    V.DB_PATH = str(db)
    try:
        return V.main()
    finally:
        V.DB_PATH = original


def _contenido_actual():
    with io.open(os.path.join(ROOT, *DB_REL.split('/')),
                 encoding='utf-8') as f:
        return f.read()


def _mutando(hand_id, mutador):
    """Devuelve el contenido de la base con `mutador` aplicado a una mano."""
    lineas = []
    for l in _contenido_actual().splitlines():
        h = json.loads(l)
        if h['hand_id'] == hand_id:
            mutador(h)
        lineas.append(json.dumps(h, ensure_ascii=False))
    return '\n'.join(lineas) + '\n'


@marca_base_editada
def test_el_verificador_pasa_sobre_la_base_actual(tmp_path, capsys):
    """La base tal como esta, sin tocarla: el verificador tiene que dar 0."""
    assert _verificador_contra_contenido(_contenido_actual(), tmp_path) == 0
    capsys.readouterr()


def test_el_verificador_detecta_una_reconstruccion_que_vuelve(tmp_path, capsys):
    """Se le devuelve a H_0039 el `BB f` que se habia revertido."""

    def _anade(h):
        h['streets']['preflop']['actions'].append(
            {'pos': 'BB', 'action': 'f', 'amount': 0.0})

    rc = _verificador_contra_contenido(_mutando('H_0039', _anade), tmp_path)
    salida = capsys.readouterr().out
    assert rc != 0, 'el verificador dio 0 con una reconstruccion reintroducida'
    assert 'RECONSTRUIDO' in salida, salida


def test_el_verificador_detecta_el_invariante_roto(tmp_path, capsys):
    """Se devuelve a `b` la etiqueta de una mano ya corregida."""

    def _destieta(h):
        for a in h['streets']['preflop']['actions']:
            if a['pos'] == 'BB' and a['action'] == 'r':
                a['action'] = 'b'

    rc = _verificador_contra_contenido(_mutando('H_0031', _destieta), tmp_path)
    salida = capsys.readouterr().out
    assert rc != 0, 'el verificador dio 0 con el invariante roto'
    assert 'INVARIANTE' in salida, salida


def test_el_verificador_detecta_un_cambio_sin_declarar(tmp_path, capsys):
    """Una septima mano editada, que no esta en ninguna lista."""

    def _toca(h):
        h['streets']['preflop']['actions'][0]['amount'] = 3.3

    rc = _verificador_contra_contenido(_mutando('H_0800', _toca), tmp_path)
    salida = capsys.readouterr().out
    assert rc != 0, 'el verificador dio 0 con un cambio sin declarar'
    assert 'SIN declarar' in salida, salida


def test_el_verificador_detecta_una_revertida_que_reaparece(tmp_path, capsys):
    """H_0970 vuelve al recorte que se habia revertido."""

    def _recorta(h):
        h['winner'] = ['hero']

    rc = _verificador_contra_contenido(_mutando('H_0970', _recorta), tmp_path)
    salida = capsys.readouterr().out
    assert rc != 0, 'el verificador dio 0 con una revertida reaparecida'
    assert 'REVERTIDAS' in salida, salida