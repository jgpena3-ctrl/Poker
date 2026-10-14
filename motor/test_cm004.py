# -*- coding: utf-8 -*-
"""CM-004: el invariante de la ciega del BB, y donde vive la regla.

Dos guards, y los dos apuntan al mismo sitio: la regla tiene que estar en
`motor/learn.py`, no en un script de auditoria. Una copia en cada sitio es
exactamente como vuelve un bug (ver el commit que movio `no_puede_actuar` a
`motor/multiway.py`).
"""
import ast
import io
import os
import subprocess

import pytest

from motor import learn
from tools.auditar_bb_check import _entradas_bb_rechazadas
from tools.verificar_cm004 import DECLARADAS, RECONSTRUCCIONES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_REL = 'data/hands_db.jsonl'


def _committed():
    crudo = subprocess.run(['git', 'show', 'HEAD:%s' % DB_REL], cwd=ROOT,
                           capture_output=True)
    return [__import__('json').loads(l)
            for l in crudo.stdout.decode('utf-8').splitlines() if l.strip()]


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


def test_la_regla_sigue_siendo_exacta_contra_la_version_comprometida():
    """La reinterpretacion cubre exactamente el conjunto CM-004: ni una mano de
    mas, ni una de menos.

    Se deriva contra la version COMPROMETIDA a proposito. Derivarla contra la
    copia de trabajo daria 0, porque ya esta corregida, y un guard que
    comprueba 0 no vigila nada.
    """
    derivadas = {}
    for h in _committed():
        for i, importe, causa in learn.entradas_bb_rechazadas(h):
            if causa == learn.CAUSA_ORDEN:
                derivadas.setdefault(h['hand_id'], []).append((i, importe))
    declaradas = {i for _c, _m, ids in learn.EXCLUSIONES_VENTANA_FABLE
                  for i in ids}
    assert set(derivadas) == declaradas, (
        'la regla senala %d manos y EXCLUSIONES_VENTANA_FABLE declara %d: %s'
        % (len(derivadas), len(declaradas),
           sorted(set(derivadas) ^ declaradas)))


def test_el_indice_del_motor_apunta_a_la_accion_cruda():
    """`_preflop_sequence` y `streets.preflop.actions` tienen que compartir
    indice, porque es lo que permite editar la lista cruda a partir de lo que
    devuelve el motor. Sin esto, `tools/verificar_cm004.py` editaria la accion
    equivocada."""
    for h in _committed():
        acc = ((h.get('streets') or {}).get('preflop') or {}).get('actions') or []
        for i, importe, causa in learn.entradas_bb_rechazadas(h):
            if causa != learn.CAUSA_ORDEN:
                continue
            a = acc[i]
            assert a['pos'] == 'BB' and a['action'] == 'b', (h['hand_id'], i)
            assert a['amount'] == importe, (h['hand_id'], i)


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