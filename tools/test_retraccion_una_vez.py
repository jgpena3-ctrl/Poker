# -*- coding: utf-8 -*-
"""La retraccion del y = 0 esta UNA VEZ y en CITA. Y R2 la encontro dos veces.

QUE PASÓ

Los tres .md tenían el bloque de retraccion DOS VECES:

    227  ### Y `y = 0`: las manos que el heroe pierde, por dos vías
    229  > **Lo que se decía, y lo que se retira:**      <- 1ª, HUERFANA
    231  > «y = 0 no es de los folds...»
    233  Y un encabezado como el de arriba es el PEOR sitio...   <- NO LA INTRODUCE
    249  > **Lo que se decía, y lo que se retira:**      <- 2ª, la buena
    253  Y las dos mitades se caen:

COMO: dos parches. El primero metio la cita donde toca —justo antes de «Y las
dos mitades se caen»—. El segundo cambio el encabezado, y como el encabezado
llevaba la cita dentro, puso OTRA por encima. No vio la de debajo.

Y lo grave no es que esten dos: es que **el propio documento decia que tiene
que estar una**, a cuatro lineas:

    > Y una cosa de forma, que sale de arreglar esto: el enunciado se escribe
    > **una vez, y como cita**.

Un principio que se ve incumplido en la misma pagina es la forma mas rapida de
que nadie se lo crea. Y es peor que no escribirlo.

QUE VIGILA ESTE TEST

Tres cosas, y la tercera es la que R2 pidio implicitamente:

  1. la cita aparece UNA vez
  2. y esta en bloque citado
  3. y NO esta en un encabezado, que es el peor sitio posible

Lo tercero tiene su propio motivo y no es el mismo que el primero: un
encabezado se lee antes que el cuerpo, y si el titulo afirma lo que el
cuerpo retira, el documento afirma lo contrario de lo que sostiene con solo
leer la primera linea.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from retraccion_scan import citada, leer                       # noqa: E402

LOS_TRES = ('LIMITACION_PREFLOP_AUC.md', 'REPRESENTATIVIDAD_23.md',
            'DECISION_OBJETIVO_AUC.md')

LA_CITA = 'Lo que se decía, y lo que se retira'
LA_FRASE = 'no es de los folds'


def test_la_cita_de_la_retraccion_esta_una_sola_vez():
    """Y el fallo dice cuantas hay y en que lineas.

    «Una vez, y como cita» lo dice el propio documento. Y un principio que
    el documento incumple a cuatro lineas no es un principio."""
    demasiadas = []
    for n in LOS_TRES:
        doc = leer(n)
        c = doc.count(LA_CITA)
        if c != 1:
            lineas = [i for i, l in enumerate(doc.split('\n'), 1)
                      if LA_CITA in l]
            demasiadas.append('%s: %d veces, en las lineas %s'
                              % (n, c, lineas))
    assert not demasiadas, (
        'la cita de la retraccion tiene que estar UNA vez, y el propio '
        'documento lo dice:\n   ' + '\n   '.join(demasiadas))


def test_y_la_frase_retirada_tambien_una_sola_vez():
    """Y la frase, que es lo que el principio protege.

    Con dos citas hay dos frases, y basta que una se quede sin marcar para que
    el documento afirme lo que dice retirar. Que es lo que paso con el
    encabezado."""
    demasiadas = []
    for n in LOS_TRES:
        doc = leer(n)
        c = doc.count(LA_FRASE)
        if c != 1:
            demasiadas.append('%s: %d veces' % (n, c))
    assert not demasiadas, (
        'la frase retirada tiene que aparecer UNA vez, en cita:\n   '
        + '\n   '.join(demasiadas))


def test_la_frase_retirada_esta_en_cita_y_no_solo_ahi():
    """Y dos mitades, porque «esta en cita» puede significar dos cosas:

      - que la frase esta en un `>`  — bien
      - y que la frase esta AFIRMADA en otra parte — mal

    La segunda es la que R2 vio en el encabezado."""
    for n in LOS_TRES:
        doc = leer(n)
        assert citada(doc, LA_FRASE), (
            '%s: la frase retirada no esta en un bloque citado. Una '
            'retraccion que no cita no deja constancia de que se corrigio'
            % n)


def test_la_frase_retirada_no_esta_en_ningun_encabezado():
    """Y lo del encabezado, que es un sitio aparte.

    Un encabezado se lee ANTES que el cuerpo, y si el titulo dice lo que el
    cuerpo retira, basta con leer la primera linea para que el documento
    afirme lo contrario de lo que sostiene.

    Y asi fue: el titulo era «### Y `y = 0` no es «de los folds»», que es
    exactamente la frase que la seccion venia a retirar."""
    malas = []
    for n in LOS_TRES:
        doc = leer(n)
        for i, linea in enumerate(doc.split('\n'), 1):
            if not linea.lstrip().startswith('#'):
                continue
            if LA_FRASE in linea.lower():
                malas.append('%s:%d  %s' % (n, i, linea.strip()[:70]))
    assert not malas, (
        'la frase retirada esta en un ENCABEZADO, que es el peor sitio '
        'posible: lo primero que se lee y lo ultimo que se olvida.\n   '
        + '\n   '.join(malas))


def test_el_encabezado_enuncia_la_conclusion():
    """Y que el encabezado diga la CONCLUSION, que es lo que tiene que estar
    en el titulo.

    Y no solo que no diga la frase retirada: que diga la afirmacion nueva. Un
    encabezado que no enuncia nada es un encabezado que ocupa sitio."""
    for n in LOS_TRES:
        doc = leer(n)
        encontrada = [l for l in doc.split('\n')
                      if l.lstrip().startswith('#') and 'y = 0' in l]
        assert encontrada, '%s: no hay encabezado sobre el y = 0' % n
        assert any('pierde' in l or 'dos vías' in l or 'dos vias' in l
                   for l in encontrada), (
            '%s: el encabezado del y = 0 no enuncia la conclusion. Dice %r. '
            'Lo que tiene que estar en el titulo es la afirmacion nueva, no '
            'la vieja' % (n, encontrada[0].strip()[:60]))