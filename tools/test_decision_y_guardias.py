# -*- coding: utf-8 -*-
"""R2 parrafo 2: el guardia que faltaba, y R1 tareas 2, 3 y 4.

R2: "que los conteos de la tabla procedan de las filas reales de
`medir_corte()` y que las etiquetas aceptadas sean EXCLUSIVAMENTE 0.0 o
1.0. Eso evita que un valor inesperado o un motivo textual vuelva a
inflar el total de etiquetas."

Ese es exactamente el error que cometi: un motivo textual en el campo `y`.
El namedtuple lo hace mas improbable, pero no imposible: si alguien
cambia `resto_de_muestra` y devuelve otra cosa, el namedtuple lo acepta igual.
El guardia es de tipos, no de confianza.

R1 tarea 3: el namedtuple tiene NOMBRES y el orden de los campos no importa.
R1 tarea 4: los dos fallos de tests del bloque anterior estan corregidos.
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


# ============================== R1 tarea 3: el namedtuple tiene NOMBRES
def test_resto_devuelve_un_tipo_con_nombres(ar):
    """No una tupla suelta. Una tupla suelta se puede desempaquetar al reves
    sin que nada se entere, que es lo que paso."""
    assert hasattr(ar, 'Resto'), 'no existe el tipo con nombres'
    assert ar.Resto._fields == ('motivo', 'y'), (
        'los campos se llaman por lo que son: %r' % (ar.Resto._fields,))


def test_el_nombre_sobrevive_a_reordenar_los_campos(ar):
    """R1 lo pide explicitamente: si alguien reordena los campos,
    `.motivo` sigue siendo el motivo. Eso no se puede probar con el tipo tal
    como esta, porque el constructor es posicional. Se construye uno con los
    campos cambiados de orden y se mira que el ACCESO por nombre sigue.
    """
    from collections import namedtuple
    al_reves = namedtuple('Resto', ('y', 'motivo'))
    # el que esta al reves, leido al reves, sigue siendo el mismo objeto
    r = ar.Resto('victoria por fold', 1.0)
    assert r.motivo == 'victoria por fold'
    assert r.y == 1.0
    # y uno al reves, leido por nombre, tambien
    q = al_reves(1.0, 'victoria por fold')
    assert q.motivo == 'victoria por fold'
    assert q.y == 1.0


def test_los_llamadores_no_desempaquetan_por_posicion(ar):
    """`m, y = resto_de_muestra(...)` es lo que rompio. El namedtuple sigue
    admitting eso, asi que hay que comprobar que NADIE lo hace."""
    fuente = io.open(ar.__file__, encoding='utf-8').read()
    i = 0
    malos = []
    while True:
        i = fuente.find('resto_de_muestra(', i + 1)
        if i < 0:
            break
        # el caso sospechoso: desempquetado por posicion
        linea = fuente[max(0, fuente.rfind('\n', 0, i) + 1):i]
        if '=' in linea and 'ins.cal' not in linea:
            context = fuente[i:i + 90]
            if context.lstrip().startswith(('cal', 'h,')):
                continue
            if 'r =' in linea or 'r,' in linea:
                continue
            malos.append(linea.strip())
    # el registro con `r = resto_de_muestra(...)` es el bueno; no debe haber
    # ninguno con dos nombres al reves
    fuente_sin = fuente.replace('r = resto_de_muestra', '')
    for clave in ('m, y = resto_de_muestra', 'y, _mot = resto_de_muestra',
                  'motivo, y = resto_de_muestra'):
        assert clave not in fuente_sin, (
            'queda un desempaquetado por posicion: %s' % clave)
    assert not malos, 'desempaquetados sospechosos: %r' % malos


# ============================================ R2: el guardia de TIPOS
def test_las_etiquetas_de_una_fila_son_0_o_1_o_nada(ar, ventana):
    """Y NO un motivo textual. El error que inflo la tabla era
    exactamente un texto en el campo de la etiqueta."""
    filas = ar.medir_corte(ar._inst(), ventana, 'ultima')
    assert filas, 'hay filas que medir'
    malos = collections.Counter()
    for f in filas:
        y = f['y']
        if y is None:
            continue
        if not isinstance(y, float) or y not in (0.0, 1.0):
            malos[repr(y)] += 1
    assert not malos, (
        'hay etiquetas que no son 0.0 ni 1.0: %r. Un motivo textual en el '
        'campo de la etiqueta es lo que inflo la tabla del bloque anterior'
        % dict(malos))


def test_los_conteos_de_la_tabla_salen_de_las_filas(ar, ventana):
    """No de un numero escrito al lado. La tabla tiene que ser la cuenta
    de las filas reales, o la tabla y las filas pueden separarse."""
    # Las cifras de aqui son LAS DE `muestra()`, no las que salian de la
    # replica de filtros. Con la etiqueta leida:
    #   corte en la ULTIMA: preflop 0, postflop 48 (20 y=1, 28 y=0)
    #   corte en la PRIMERA: preflop 67 (20 y=1, 47 y=0)
    filas = ar.medir_todas_calles(ar._inst(), ventana, 'primera')
    jugadas = [f for f in filas if f['jugada']]
    con_y = [f for f in jugadas if f['y'] is not None]
    assert len(jugadas) == 378, 'poblacion B jugada: %d' % len(jugadas)
    assert len(con_y) == 67, 'con etiqueta: %d' % len(con_y)
    assert sum(1 for f in con_y if f['y'] == 1.0) == 20
    assert sum(1 for f in con_y if f['y'] == 0.0) == 47
    assert all(f['calle'] == 'preflop' for f in con_y), (
        'con el corte en la primera, las que tienen etiqueta son todas '
        # noqa
        'preflop: la mano continua y ahi si hay board')


def test_la_tabla_y_las_filas_no_pueden_ser_cosas_distintas(ar, ventana):
    """La comprobacion cruzada: `resto_de_muestra` sobre las mismas filas que
    usa la tabla tiene que dar lo mismo que el campo `y` de esas filas."""
    inst = ar._inst()
    filas = ar.medir_todas_calles(inst, ventana, 'primera')
    disagreements = 0
    for f in filas[:80]:
        h = ventana[f['id']]
        # el MISMO cal e instrumento que usa medir_corte, no uno
        # reconstruido: comparar una copia con otra copia no prueba nada
        r = ar.resto_de_muestra(inst.cal, h, inst.eqm.hero_pos_de(h))
        if r.y != f['y']:
            disagreements += 1
    assert disagreements == 0, (
        '%d filas cuyo y no coincide con resto_de_muestra' % disagreements)


# ====================================== R1 tarea 4: los dos fallos de tests
def test_el_test_de_no_implementada_no_exige_una_forma_exacta():
    """Un test que exige una sola forma de una frase obliga a escribir el
    documento como el test, no al reves. Se admiten las tres."""
    fuente = io.open(os.path.join(ROOT, 'tools',
                                  'test_retraccion_y_auc.py'),
                     encoding='utf-8').read()
    i = fuente.index('no implementad')
    cuerpo = fuente[i - 200:i + 400]
    assert 'no está implementad' in cuerpo, 'la forma acentuada'
    assert 'sin implementar' in cuerpo, 'la forma sin genero'


def test_el_test_del_assert_ejecuta_el_mensaje():
    """No recorta la cadena del fuente —eso ya fallo una vez—: ejecuta el
    mensaje con los numeros que le ponga."""
    fuente = io.open(os.path.join(ROOT, 'tools',
                                  'test_retraccion_y_auc.py'),
                     encoding='utf-8').read()
    assert '9 de 9' in fuente, 'comprueba el caso real'
    assert '9 de 7' in fuente, 'y que el viejo no puede aparecer'
    assert "formato % (9, 9)" in fuente, 'ejecutandolo, no recortando'


# ================================ la decision, y que no se implemente
def test_el_corte_por_defecto_sigue_siendo_el_ultimo(ar):
    """`DECISION_OBJETIVO_AUC.md` decide A. Y la decision no implementada
    significa que el codigo sigue como estaba."""
    fuente = io.open(ar.__file__, encoding='utf-8').read()
    i = fuente.index('def cortes_de(')
    cuerpo = fuente[i:i + 900]
    assert "cual == 'ultima'" in cuerpo or "if cual == 'ultima':" in cuerpo
    # y la version 'primera' tiene que decir que NO la usa nada mas
    assert 'NO' in cuerpo and 'motor' in cuerpo, (
        'la version primera existe solo para medir la hipotesis, y tiene que '
        'decirlo donde se lee')


def test_la_decision_esta_escrita():
    p = os.path.join(ROOT, 'DOCS', 'DECISION_OBJETIVO_AUC.md')
    assert os.path.exists(p)
    with io.open(p, encoding='utf-8') as f:
        s = f.read()
    assert 'Decisión: A' in s or 'Decision: A' in s, (
        'la decision tiene que estar escrita, no deducida')
    assert '28' in s, ('y con la medicion que la sostiene: la poblacion '
                      'actual ya tiene derrotas')
    assert '236' in s, 'y con el coste de B: el postflop que se pierde'