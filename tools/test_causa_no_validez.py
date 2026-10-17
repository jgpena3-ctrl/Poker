# -*- coding: utf-8 -*-
"""El filtro es la CAUSA de la diferencia, y eso NO es lo mismo que sea el
CORRECTO.

LA PRECISION

`revision_2` lo dice, y es la observacion mas fina de las dos revisiones:

    La reproduccion demuestra que calculo genera cada cifra y respalda el
    filtro SI EL CONTRATO DE INCLUSION ESTA CORRECTAMENTE DEFINIDO. La
    validez del filtro depende tambien de ese contrato, no solo de que una
    cifra antigua reaparezca.

Y tiene razon. Lo que esta demostrado, y es mucho:

    sin el filtro   0,8308
    con el filtro   0,7667
    0,8308 es el numero que AUC_INTERVALO.md dice que se publico por error

Eso es una prueba **causal**: el filtro es la causa de la diferencia.

Lo que NO esta demostrado: que el filtro sea el **correcto**. Porque «el
filtro explica por que difieren» no es «el filtro esta bien», y confundir las
dos cosas es el error que este proyecto lleva cuatro bloques corrigiendo en
otro sitio.

Y POR QUE NO SE PUEDE COMPROBAR CON ESTA PRUEBA

Porque hay una consecuencia practica: si alguien cambia la definicion de la
poblacion en el contrato, el filtro **no dejara de ser la causa** —seguira
explicando por que 0,8308 y 0,7667 difieren— pero dejara de ser el correcto.

La prueba no lo detecta. Lo que lo detecta es el contrato, que esta firmado.

QUE COMPRUEBA ESTE TEST

Que el documento diga las DOS cosas, y que las separe. Un documento que solo
dice «el filtro es el correcto» esta affirmationsdo una conclusion que no
tiene; y uno que solo dice «es la causa» deja al lector sin saber de donde
sale la validez.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from retraccion_scan import afirmada_sin_negar, leer          # noqa: E402

DOC = os.path.join(ROOT, 'DOCS', 'QUE_REPRESENTA_LA_PREDICCION.md')


def test_el_documento_dice_las_dos_cosas():
    """Y el fallo dice cual falta."""
    doc = leer('QUE_REPRESENTA_LA_PREDICCION.md')
    causa = afirmada_sin_negar(doc, 'CAUSA de la diferencia')
    assert causa, (
        'el documento ya no dice que el filtro sea la CAUSA de la '
        'diferencia, que es lo que si esta demostrado')
    valido = (afirmada_sin_negar(doc, 'es el CORRECTO')
              or afirmada_sin_negar(doc, 'es el correcto'))
    assert valido, (
        'el documento ya no dice que el filtro sea el CORRECTO, que es lo '
        'que NO esta demostrado')


def test_la_validez_comes_del_contrato_y_no_del_auc():
    """Y que diga de donde sale la validez. Si saliera de que el AUC sale con
    dos decimales, estaríamos razonando al reves: el numero no valida la
    poblacion, la poblacion valida el numero."""
    doc = leer('QUE_REPRESENTA_LA_PREDICCION.md')
    assert 'CONTRATO_L_SEC' in doc, (
        'el documento no dice de donde sale la validez del filtro, que es lo '
        'unico que la hace suya')
    assert afirmada_sin_negar(doc, 'no una consecuencia'), (
        'y no dice que la validez NO es consecuencia de que el AUC salga con '
        'dos decimales: esa es la confusion exacta')


def test_el_documento_avisa_de_que_la_prueba_no_lo_detecta():
    """La consecuencia práctica, que es la parte que puede hacer daño. Si
    alguien cambia el contrato, el filtro sigue explicando la diferencia y ya
    no siendo el correcto, y sin este aviso nadie se-avisa."""
    doc = leer('QUE_REPRESENTA_LA_PREDICCION.md')
    hits = (afirmada_sin_negar(doc, 'no lo detecta')
            or afirmada_sin_negar(doc, 'La prueba que hay aquí no'))
    assert hits, (
        'el documento no advierte que esta prueba NO detecta un cambio de la '
        'poblacion. Es la parte que puede hacer dano')


def test_la_prueba_causal_sigue_en_pie():
    """Y que lo que SI se demuestra no se ha perdido al escribir lo que no.

    Un documento que corrige una cosa y quita la otra esta peor que uno que
    no corrige ninguna: ha perdido una prueba buena para ganar una
   prueba. Eso tiene que comprobarse."""
    doc = leer('QUE_REPRESENTA_LA_PREDICCION.md')
    assert '0,8308' in doc, 'el numero malo'
    assert '0,7667' in doc, 'el numero bueno'
    assert afirmada_sin_negar(doc, 'no es una coincidencia'), (
        'y que no es una coincidencia, que es lo que hace que la prueba sea '
        'causal y no correlacional. Va por el escaner y no por una cadena '
        'literal: la frase puede empezar por mayuscula y partirse entre '
        'lineas, y un test que fija las dos cosas senala el documento que '
        'esta bien')


def test_contrato_y_contradiccion_estan_declarados():
    """Que el contrato al que se apela siga firmado y sin tocar."""
    ruta = os.path.join(ROOT, 'DOCS', 'CONTRATO_L_SEC.md')
    fuente = io.open(ruta, encoding='utf-8').read()
    assert '## Población' in fuente or '## Poblaci' in fuente, (
        'el contrato ya no declara la poblacion, que es de donde sale la '
        'validez del filtro')