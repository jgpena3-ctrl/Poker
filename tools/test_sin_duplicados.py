# -*- coding: utf-8 -*-
"""No hay dos tests con el MISMO nombre en ficheros distintos.

POR QUE ESTO ES UN TEST Y NO UNA BUENA COSTUMBRE

Dos tests con el mismo nombre en dos ficheros son **la misma regla en dos
sitios**. Y dos sitios divergen: en este bloque los he corregido distintas
veces, y no siempre los dos.

Ya paso de verdad. `test_barrido_documentos.py` y `test_falsos_positivos.py`
tenian tres copias de los falsos positivos del barrido. Es el mismo error que
una copia de la logica de filtros dentro de un test, y con el mismo coste:
cuando la regla cambie, cambiara en un sitio, y el otro seguira diciendo que
el documento esta mal.

Y LO QUE LO HACE NECESARIO: **pytest no avisa**. Dos tests con el mismo
nombre en ficheros distintos se ejecutan los dos, los dos pasan, y el color
es verde. No hay nada en la salida que diga que hay una copia.

Lo que NO se busca:

  - el mismo nombre en el MISMO fichero, que es un error de sintaxis
  - helpers con el mismo nombre en ficheros distintos, porque un helper puede
    ser legitimo: dos modulos con su propio `_leer` no son una copia
"""
import collections
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ('tools', 'motor', 'recorder')


# La familia donde "un nombre repetido ES una copia": los ficheros que
# importan la REGLA. Ahi, un test repetido en dos ficheros es la misma regla
# en dos sitios, que es lo que este bloque lleva cuatro rondas corrigiendo.
FAMILIA_DE_LA_REGLA = 'retraccion_scan'


def _definiciones(solo_familia=False):
    """[(nombre_del_test, fichero)] de los tests del repositorio.

    Con `solo_familia`, solo los ficheros que importan `retraccion_scan`.
    """
    out = []
    for d in DIRS:
        ruta = os.path.join(ROOT, d)
        if not os.path.isdir(ruta):
            continue
        for n in sorted(os.listdir(ruta)):
            if not (n.startswith('test_') and n.endswith('.py')):
                continue
            with io.open(os.path.join(ruta, n), encoding='utf-8') as f:
                texto = f.read()
            if solo_familia and FAMILIA_DE_LA_REGLA not in texto:
                continue
            for m in re.finditer(r'^def (test_[A-Za-z0-9_]+)\s*\(',
                                 texto, re.MULTILINE):
                out.append((m.group(1), '%s/%s' % (d, n)))
    return out


def test_no_hay_dos_tests_con_el_mismo_nombre_en_la_familia_de_la_regla():
    """Acotado, y el acotamiento es lo que hace la regla VALIDA.

    Una version anterior de este test buscaba duplicados en TODO el
    repositorio y dio once pares. La mayoria NO son copias:

        test_pot_odds en test_implied_odds.py y test_situation.py
        test_save_load_roundtrip en test_player_ranges.py y
                                   test_postflop_ranges.py
        test_default_alpha_sigue_en_dos en CUATRO ficheros

    Esos son ficheros que prueban la misma COSA desde ficheros distintos, que
    es una forma normal de organizar tests. «No repitas nombres» no distingue
    una copia de una coincidencia, y una regla que no distingue no vale.

    Lo que si es una copia, y es lo unico comprobable de verdad: dos ficheros
    de la familia de la retraccion, que es donde vive la REGLA. Ahi un nombre
    repetido si es la misma regla en dos sitios.
    """
    donde = collections.defaultdict(list)
    for nombre, fichero in _definiciones(solo_familia=True):
        donde[nombre].append(fichero)
    repetidos = dict((k, v) for k, v in donde.items() if len(v) > 1)
    assert not repetidos, (
        'tests con el mismo nombre en ficheros de la familia de la regla:\n   '
        + '\n   '.join('%s  ->  %s' % (k, ', '.join(v))
                        for k, v in sorted(repetidos.items())))


def test_la_familia_de_la_regla_no_esta_vacia():
    """Que el acotamiento no vacie el detector. Si `retraccion_scan` deja de
    importarse en los tests, esto no miraria nada y pasaria siempre."""
    assert len(_definiciones(solo_familia=True)) >= 20, (
        'la familia de la regla tiene %d tests. Si baja mucho, el detector '
        'no esta mirando lo que cree que mira'
        % len(_definiciones(solo_familia=True)))


def test_este_test_no_se_declara_duplicado():
    """Comprobacion de que el detector funciona: su propio nombre tiene que
    aparecer una sola vez.

    Con el nombre NUEVO. Una version anterior buscaba el nombre viejo, que ya
    no existe, y por eso el contador daba cero —que tambien es un fallo, pero
    uno que no dice nada. Un detector que apunta a un nombre que ya no esta
    no vigila nada en silencio.
    """
    cuenta = collections.Counter(n for n, _f in _definiciones())
    mio = [n for n in cuenta if n.startswith('test_no_hay_dos_tests')]
    assert mio, 'este test ya no se llama lo que el detector busca'
    assert cuenta[mio[0]] == 1, 'y aparece %d veces' % cuenta[mio[0]]


def test_el_recorrido_ve_los_ficheros_de_test_de_verdad():
    """Y que recorra el repositorio, no una lista escrita a mano. Una lista
    escrita a mano se queda vieja y el test sigue pasando."""
    vistos = set(f for _n, f in _definiciones())
    reales = set()
    for d in DIRS:
        ruta = os.path.join(ROOT, d)
        if not os.path.isdir(ruta):
            continue
        for n in os.listdir(ruta):
            if n.startswith('test_') and n.endswith('.py'):
                reales.add('%s/%s' % (d, n))
    assert reales, 'no hay ningun fichero de test: el recorrido esta roto'
    assert len(vistos) >= 20, (
        'solo ha visto %d ficheros con tests. Si el numero baja mucho, el '
        'recorrido no esta leyendo el repositorio' % len(vistos))
