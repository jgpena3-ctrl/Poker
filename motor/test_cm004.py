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
import os
import subprocess

import pytest

from motor import learn
from tools.auditar_bb_check import _entradas_bb_rechazadas
from tools.verificar_cm004 import (COMMIT_ANTES, DECLARADAS, RECONSTRUCCIONES,
                                   SHA_ANTES)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_REL = 'data/hands_db.jsonl'

# El conjunto CM-004, como hecho historico. No se puede volver a DERIVAR
# ahora: el defecto ya no esta en la base, asi que la regla da 0 y una lista
# derivada de 0 no es una lista. Es un hecho, y se escribe como tal.
#
# Lo que si se comprueba, y es lo que importa, es que la lista sigue
# cuadrando con `EXCLUSIONES_VENTANA_FABLE` y que ninguna de esas 23 viola el
# invariante.
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
    return [__import__('json').loads(l)
            for l in crudo.stdout.decode('utf-8').splitlines() if l.strip()]


def _anteriores():
    return _blob(COMMIT_ANTES, SHA_ANTES)


# --- el invariante ---------------------------------------------------------

def test_ninguna_mano_tiene_una_bb_b_que_no_pueda_ser_la_ciega():
    """El invariant de TODO el bloque.

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
    """`tools/verificar_cm004.py` y `tools/auditar_bb_check.py` IMPORTAN la
    funcion. Si uno de los dos vuelve a tener la suya, la copia se queda vieja
    y el motor acaba usando la otra."""
    for modulo in ('tools/verificar_cm004.py', 'tools/auditar_bb_check.py'):
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

    La regla se deriva contra el blob ANCLAZADO por SHA, no contra HEAD. Con
    HEAD daria 0 en cuanto la reinterpretacion estuviera commiteada, y un
    `set() == set()` verde no vigila nada. Anclarlo a `HEAD~1` tampoco vale:
    en cuanto se commitee, `HEAD~1` seria la version ya corregida.
    """
    anteriores = _anteriores()
    derivadas = set()
    for h in anteriores:
        for _i, _amt, causa in learn.entradas_bb_rechazadas(h):
            if causa == learn.CAUSA_ORDEN:
                derivadas.add(h['hand_id'])
    assert len(anteriores) == 1280, (
        'el blob previo deberia tener las 1280 manos, tiene %d: o el SHA no '
        'es el de la version previa, o la base se toco de otra manera'
        % len(anteriores))
    assert derivadas == set(CM_004), (
        'la regla senala %d manos y el conjunto historico son %d: %s'
        % (len(derivadas), len(CM_004), sorted(derivadas ^ set(CM_004))))


def test_el_conjunto_historico_cuadra_con_la_exclusion():
    """Las dos listas que nombran las mismas 23 manos tienen que seguir siendo
    la misma. Si una se actualiza y la otra no, ya no se sabe cual manda."""
    declaradas = {i for _c, _m, ids in learn.EXCLUSIONES_VENTANA_FABLE
                  for i in ids}
    assert declaradas == set(CM_004), (
        'EXCLUSIONES_VENTANA_FABLE y el conjunto historico han divergido: %s'
        % sorted(declaradas ^ set(CM_004)))


def test_ninguna_de_las_23_viola_el_invariante():
    """Las 23 en concreto, no solo el total de la base. Una de ellas
    reintroducida se veria aqui por su nombre."""
    por_id = {h.get('hand_id'): h
              for h in learn.load_hands(reliable_only=False)}
    faltan = [i for i in CM_004 if i not in por_id]
    assert not faltan, 'estas 23 ya no estan en la base: %s' % faltan
    malas = [i for i in CM_004 if learn.defecto_orden_ciega_bb(por_id[i])]
    assert malas == [], 'de las 23, estas vuelven a estar mal ordenadas: %s' % malas


def test_el_indice_del_motor_apunta_a_la_accion_cruda():
    """`_preflop_sequence` y `streets.preflop.actions` tienen que compartir
    indice, porque es lo que permite editar la lista cruda a partir de lo que
    devuelve el motor. Sin esto, `tools/verificar_cm004.py` editaria la accion
    equivocada.

    Se prueba sobre H_0722 y no sobre la base actual: es la unica de las 23
    con el patron A2 (el BB ya posteo su ciega en el indice 0 y aun asi tiene
    un `b` despues), y la base actual ya no tiene ninguna, asi que un test
    sobre ella no iteraria ni una vez.
    """
    h = next(x for x in _anteriores() if x['hand_id'] == 'H_0722')
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


# --- el manifiesto ---------------------------------------------------------

def test_toda_reconstruccion_declara_motivo_y_estado():
    """Una reconstruccion sin motivo escrito es un cambio sin explicar, que es
    justo lo que hace este bloque digan su valor."""
    for hid, d in RECONSTRUCCIONES.items():
        assert d.get('motivo'), hid
        assert d.get('estado'), hid
        assert 'revisar' in d['estado'] or d.get('recomendado'), (
            '%s esta aplicada pero no dice ni que revisar ni que valor '
            'corresponde' % hid)


def test_una_pendiente_declara_el_valor_recomendado():
    """Si algo queda pendiente, tiene que decir cual es el valor bueno. Sin
    eso, "pendiente" es una excusa, no una tarea."""
    for hid, d in DECLARADAS.items():
        if d['estado'].startswith('PENDIENTE'):
            assert d.get('recomendado'), (
                '%s queda pendiente y no dice que valor corresponde' % hid)


def test_h0970_no_coincide_con_lo_recomendado_y_eso_es_lo_que_se_declara():
    """El caso que hizo falta el manifiesto.

    La copia de trabajo trae `['hero']`, y el valor correcto es `['hero','p1']`:
    el BB comparte el bote. Mientras no se revise la grabacion, el recorte se
    queda como esta, y este test deja constancia de que la diferencia es
    CONOCIDA y no un descuido.
    """
    manos = {h['hand_id']: h for h in
             learn.load_hands(reliable_only=False)}
    d = DECLARADAS['H_0970']
    assert d['recomendado'] == ['hero', 'p1']
    assert manos['H_0970']['winner'] != d['recomendado'], (
        'H_0970 ya coincide con lo recomendado: entonces hay que quitarlo de '
        'las pendientes y aplicar el cambio, no dejar el test mintiendo')