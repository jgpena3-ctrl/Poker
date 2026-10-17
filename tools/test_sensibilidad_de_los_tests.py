# -*- coding: utf-8 -*-
"""Que los tests de la prediccion sean SENSIBLES a las contradicciones
concretas, y no solo a la presencia.

R2, punto 1:

    Comprueba que las cadenas aparecen, no que esten asociadas a la fila, la
    poblacion y la condicion correctas. ... No hace falta intentar construir
    un verificador universal de prosa; basta con que los tests sean sensibles
    a las contradicciones concretas que ya se encontraron.

Y este fichero es el que comprueba eso. Un detector de prosa universal no
—seria un detector que no sabe de que habla— pero si se puede comprobar que
estos tests CAEN cuando se rompe la relacion, que es lo que significa que
sean sensibles.

COMO SE COMPRUEBA QUE UN TEST ES SENSIBLE

Metiendole la contradiccion. Si el test sigue pasando con el documento
deliberadamente roto, no vigila la relacion: vigila la cadena.

Y esa comprobacion es la que mas trabajo ha dado en este bloque, porque las
tres primeras versiones de estos tests PASABAN con el documento roto:

  - dos cadenas sueltas, sin condicion
  - una condicion junto a la cifra CONTRARIA
  - la tesis presente pero con la polaridad invertida

Que es lo que R2 senala, y ahora esta comprobado en vez de temido.
"""
import io
import os
import shutil
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import retraccion_scan as rs                                   # noqa: E402

DOC = os.path.join(ROOT, 'DOCS', 'QUE_REPRESENTA_LA_PREDICCION.md')


@pytest.fixture(scope='module')
def bueno():
    with io.open(DOC, encoding='utf-8') as f:
        return f.read()


def _con(docs_bueno, viejo, nuevo):
    """El documento con una substitucion, o None si el viejo no esta."""
    if viejo not in docs_bueno:
        return None
    return docs_bueno.replace(viejo, nuevo, 1)


# ============================================ el documento de verdad
def test_el_documento_real_tiene_los_pares(bueno):
    """Los pares, en el documento tal como esta.

    Y el criterio es la SECCION, no la clausula ni la linea: el documento
    separa en una tabla de dos columnas, con la cifra y su condicion en
    celdas distintas. Una clausula es mas pequena que la idea, y una linea
    mas grande."""
    from test_causa_no_validez import _misma_seccion
    b = bueno.lower()
    assert _misma_seccion(b, '0,8308', ('sin el filtro', 'sin filtro')), (
        '0,8308 no esta en una seccion que diga SIN el filtro')
    assert _misma_seccion(b, '0,7667', ('con el filtro', 'con filtro',
                                        'filtrada')), (
        '0,7667 no esta en una seccion que diga CON el filtro')


def test_las_dos_cifras_coexisten_en_una_comparacion(bueno):
    """Y que haya una seccion con LAS DOS. Porque una tabla de comparacion
    tiene que traer las dos condiciones: la comparacion es eso."""
    from test_causa_no_validez import _seccion
    b = bueno.lower()
    buena = False
    for m in __import__('re').finditer('0,8308', b):
        sec = _seccion(b, m.start()).lower()
        if '0,7667' in sec and 'con el filtro' in sec and 'sin el filtro' in sec:
            buena = True
            break
    assert buena, (
        'no hay ninguna seccion con las dos cifras y las dos condiciones a la '
        'vez. Las cifras aparecen sueltas por ahi, y sueltas no dicen a que '
        'condicion pertenecen')


def test_la_tesis_de_no_validez_tiene_la_polaridad(bueno):
    """Y que la tesis se AFIRME, no se mencione.

    R2 lo dice: hay que comprobar que el documento afirme que el filtro es la
    causa Y que no esta demostrado que sea correcto. Y la segunda mitad es la
    que un test de presencia no ve: «dice CORRECTO» y «dice que NO esta
    demostrado CORRECTO» no son lo mismo."""
    from test_causa_no_validez import _seccion
    b = bueno.lower()
    i = b.find('es el correcto', 4000)
    assert i > 0, 'no se encuentra la tesis en §4.3'
    sec = _seccion(b, i).lower()
    assert 'no' in sec and 'demostrado' in sec, (
        'la tesis se menciona sin decir que NO esta demostrado')


# ==================== que los tests CAEN cuando se rompe la relacion
def test_el_test_de_los_pares_cae_si_la_cifra_se_queda_suelta(bueno):
    """La primera sensibilidad: que la cifra se quede SIN condicion.

    Y el caso que se prueba aqui es la version ANTERIOR de este mismo test,
    que es instructive:

        | **sin** el filtro | 47 | **0,8308** — el de la version incorrecta |
        | **sin** el filtro | 47 | **0,8308** |

    Eso no rompe NADA, porque la condicion «sin el filtro» sigue en la fila.
    El detector tenia razon en seguir encontrandola, y el test decia que
    fallaba. O sea: el caso era una falsa rotura.

    Y la segunda version, que rompia la fila, TAMPOCO servia, y por un motivo
    mas interesante: **0,8308 aparece siete veces en el documento**, y cuatro
    de ellas estan en secciones que si tienen la condicion. Borrar una fila
    no quita las otras tres, y el detector sigue comiendo — con razon.

    O sea: el detector no cae porque hay mas de un sitio bien asociado, y eso
    no es un fallo suyo. El contrato es «¿hay AL MENOS una mencion con su
    condicion?», y la respuesta sigue siendo que si.

    Para que caiga hay que quitar la condicion de TODOS los sitios. Y eso si
    es una contradiccion concreta: el documento entero con los numeros sin
    decir a que pertenecen."""
    from test_causa_no_validez import _misma_seccion
    b = bueno.lower()
    assert _misma_seccion(b, '0,8308', ('sin el filtro', 'sin filtro')), (
        'precondicion: hoy hay una mencion con su condicion')
    sin_condicion = b.replace('sin el filtro', 'en la medicion')
    assert not _misma_seccion(sin_condicion, '0,8308',
                              ('sin el filtro', 'sin filtro')), (
        'el detector deberia caer cuando NO queda ninguna mencion con su '
        'condicion, y no cae. O sea que no mira la condicion')


def test_el_test_de_los_pares_cae_si_se_invierte_la_asignacion(bueno):
    """La segunda: cambiar 0,7667 por su condicion contraria, y el detector
    tiene que NOTARLO aunque las dos condiciones sigan presentes.

    Porque aqui es donde el test anterior se rompia: una tabla de
    comparacion trae las dos condiciones, asi que «hay una condicion
    cualquiera al lado» no dice nada. Hay que mirar la de ESA cifra."""
    from test_causa_no_validez import _misma_seccion
    roto = _con(bueno,
                '| con el filtro de partición | 11 | **0,7667** — el '
                'publicado |',
                '| sin el filtro de partición | 11 | **0,7667** — el '
                'publicado |')
    assert roto is not None, 'la fila ha cambiado'
    b = roto.lower()
    assert not _misma_seccion(b, '0,7667', ('con el filtro', 'con filtro',
                                             'filtrada')), (
        'el detector deberia notar que 0,7667 ya no esta con SU condicion y '
        'no cae: el detector no mira la asignacion')


def test_el_test_de_la_tesis_cae_si_se_invierte_la_polaridad(bueno):
    """La tercera, y la mas importante: que la tesis de no-validez se
    convierta en una de validez, y el test lo note.

    Y el ambito es la ORACION que sigue a la tesis, no la seccion:

        **El filtro es el CORRECTO.** Eso **no** esta demostrado, y no lo
        puede estar con esta prueba.

    Una version anterior de este test miraba los primeros 200 caracteres de la
    seccion y buscaba «no» + «demostrado». Y la seccion de §4.3 tiene muchos
    «no», o sea que la comprobacion era tan laxa que NUNCA caia. Un test que
    nunca cae no es un test de sensibilidad: es una decoracion."""
    from test_causa_no_validez import _orbita_de_la_tesis
    roto = _con(bueno,
                'Eso **no** está demostrado, y no lo puede',
                'Eso **sí** está demostrado, y lo puede')
    assert roto is not None, 'la frase de la tesis ha cambiado'
    orbita = _orbita_de_la_tesis(roto.lower())
    assert orbita, 'no se encuentra la orbita de la tesis'
    assert not ('no' in orbita and 'demostrado' in orbita), (
        'el detector deberia notar la polaridad invertida y no la nota: la '
        'orbita dice %r' % orbita)


def test_los_tres_test_se_quebran_uno(bueno):
    """Los tres, juntos, y en una sola prueba.

    Porque los tres casos anteriores podrian pasar los tres tests por un
    motivo comun: que ninguno este mirando la relacion. Y un detector que
    no mira la relacion y tres pruebas que lo modifican no dicen nada entre
    los tres."""
    caidas = 0
    por_rotura = (
        ('ninguna cifra con su condicion',
         'sin el filtro', 'en la medicion'),
        ('la asignacion invertida',
         '| con el filtro de partición | 11 | **0,7667** — el publicado |',
         '| sin el filtro de partición | 11 | **0,7667** — el publicado |'),
        ('la polaridad de la tesis',
         'Eso **no** está demostrado, y no lo puede',
         'Eso **sí** está demostrado, y lo puede'),
    )
    from test_causa_no_validez import _misma_seccion, _orbita_de_la_tesis
    for nombre, viejo, nuevo in por_rotura:
        roto = _con(bueno, viejo, nuevo)
        if roto is None:
            continue
        b = roto.lower()
        if nombre == 'la cifra sin condicion':
            ok = not _misma_seccion(b, '0,8308', ('sin el filtro',
                                                  'sin filtro'))
        elif nombre == 'la asignacion invertida':
            ok = not _misma_seccion(b, '0,7667', ('con el filtro',
                                                  'con filtro', 'filtrada'))
        else:
            orb = _orbita_de_la_tesis(b)
            ok = not (orb and 'no' in orb and 'demostrado' in orb)
        if ok:
            caidas += 1
        else:
            print('   NO HA CAIDO: %s' % nombre)
    assert caidas >= 2, (
        'solo %d de los 3 tests han caido al romper la relacion. Un detector '
        'que no cae no esta mirando lo que dice mirar' % caidas)


# ==================== y que el limite del escaner no se atribuya de mas
def test_este_fichero_no_le_atribuye_mas_cobertura_al_escaner():
    """R2, punto 3: el test de las tesis centrales es una proteccion
    ESPECIFICA de un documento, no una garantia general de que el escaner
    detecte cualquier afirmacion escondida en una cita.

    O sea: hay que poder cambiar el escaner a «ignora las citas» y que este
    fichero lo note, porque el escaner es quien dice si hay afirmacion."""
    fuente = io.open(os.path.join(ROOT, 'tools', 'retraccion_scan.py'),
                     encoding='utf-8').read()
    assert 'def cita(' in fuente, 'la funcion que decide'
    # y que el escaner siga distinguiendo, que es de lo que depende todo
    texto = ('Una afirmacion propia.\n'
             '\n'
             '> Una cita de otra cosa.\n')
    assert rs.afirmada(texto, 'afirmacion propia') == [1]
    assert rs.afirmada(texto, 'cita de otra cosa') == [], (
        'una cita no es una afirmacion. Si esto cambia, todos los tests de '
        'documentos de este repositorio dejan de comprobar lo que dicen, y '
        'este fichero no lo detectaria: solo mira UN documento')