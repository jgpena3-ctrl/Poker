# -*- coding: utf-8 -*-
"""Tarea 3: el modulo tiene TRES ALCANCES, y cada uno con su funcion.

Y R1 lo pide de una forma que conviene comprobar: "el modulo tiene tres
funciones separadas". Y el detalle no es el numero de funciones: es que
esten SEPARADAS.

Que no es lo mismo, y hay un caso en el que no lo fue. Al principio
`afirmada_sin_negar()` hacia:

    if lleva_polaridad(frase):
        return afirmada(texto, frase)      # ATRAJO

y con ese atajo se perdia el alcance de retraccion, que es lo unico que
vigila las frases retiradas que llevan polaridad dentro —«no esta vacia:
esta bloqueada»—.

O sea: eran dos preguntas y una sola condicion las contestaba, y una de las
dos se perdia. Las funciones separadas son la forma de que no vuelva a pasar.

LOS TRES, Y QUE CADA UNO SIGNIFIQUE ALGO DISTINTO

  1. POLARIDAD — de la clausula. «no», «ninguna», «tampoco». Una frase
     retirada dentro de una negacion no es una afirmacion.
  2. RETRACCION — del parrafo. Una retraccion escribe lo que retira en el
     parrafo entero, y a veces con dos puntos DENTRO de la frase retirada.
  3. NUMEROS — comparados enteros. `2 270` no es `270`, y `378` no es `78`.

Y se comprueba que estan separados de verdad: que quitar uno no quite otro.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import retraccion_scan as rs                                # noqa: E402


FUENTE = io.open(rs.__file__, encoding='utf-8').read()


# ================================== 1. que existen, y con nombre propio
def test_los_tres_alcances_existen_como_funciones():
    for nombre in ('Polaridad', 'en_retiracion', 'es_frase_numerica'):
        assert hasattr(rs, nombre), 'falta %s' % nombre
        assert 'def %s(' % nombre in FUENTE, (
            '%s esta definida dentro de otra cosa' % nombre)
    # y que la polaridad se mire en la clausula, no en la linea
    assert '_DELIMITADORES_CLAUSULA' in FUENTE, 'los delimitadores'
    assert ',' in rs._DELIMITADORES_CLAUSULA, (
        'la coma tiene que ser delimitador de clausula: sin ella, «hay cero '
        'derrotas, y eso hace que no se pueda» descarta la afirmacion')
    assert ',' not in rs._DELIMITADORES_ORACION, (
        'y la coma NO es delimitador de oracion, o los dos alcances son el '
        'mismo y no hay tres sino uno')


def test_la_polaridad_es_de_clausula_y_no_de_linea():
    """Y que se comporta como clausula en los dos sentidos.

    El primero: la negacion de una clausula no alcanza a la siguiente.
    El segundo: la negacion de una clausula ALCANZA a la suya. Un filtro
    que hiciera las dos cosas no seria un filtro."""
    afirmativa = ('En preflop hay cero derrotas, y eso es lo que hace que el '
                  'AUC no se pueda calcular ahi.')
    _a = afirmativa.lower()
    assert not rs.Polaridad(rs._oracion_que_rodea(
        _a, _a.index('cero derrotas'))), (
        'la clausula de «cero derrotas» se lee como negada por el «no» de la '
        'siguiente')
    negativa = 'No hay cero derrotas.'
    _n = negativa.lower()
    assert rs.Polaridad(rs._oracion_que_rodea(
        _n, _n.index('cero derrotas'))), (
        'pero la suya si se lee como negada: sin esto el filtro no filtra '
        'nada')


# ================================== 2. que estan separados de verdad
def test_los_tres_alcances_responden_distinto():
    """La misma frase, con los tres filtros, y tres respuestas distintas.

    Y el caso que lo delata: una frase que lleva POLARIDAD y esta en un
    parrafo que RETIRA. Con un atajo —«si lleva polaridad, saltate el
    filtro»— el alcance de retraccion se pierde, y con el se pierde la
    consigna de que una frase citada no es una afirmacion."""
    solo_polaridad = 'Hay cero derrotas en preflop.\n'
    solo_retirada = ('Una correccion.\n\n'
                     '> Antes decia cero derrotas. Retirado.\n')
    ambos = ('Una correccion.\n\n'
             '> Antes se decia que no habia cero derrotas, y eso se retira.\n')
    assert rs.afirmada_sin_negar(solo_polaridad, 'cero derrotas') == [1]
    assert rs.afirmada_sin_negar(solo_retirada, 'cero derrotas') == []
    assert rs.afirmada_sin_negar(ambos, 'cero derrotas') == [], (
        'una frase con polaridad dentro de un parrafo que retira: los DOS '
        'filtros tienen que aplicar, no uno')


def test_el_alcance_de_retraccion_es_el_parrafo():
    """Y que es el parrafo, no la linea ni el documento. Tres casos con la
    misma cifra y distinto contexto, y tienen que salir distinto:
    un parrafo que retira, uno contiguo que no, y un documento entero con
    un marcador en otro sitio."""
    texto = ('| con etiqueta | 270 | afirmada aqui\n'
             '\n'
             'se retira lo anterior: 270 era la cifra de la replica\n'
             '\n'
             'otra tabla\n'
             '| con etiqueta | 270 | y esta otra es distinta\n')
    assert rs.afirmada_sin_negar(texto, '270') == [6], (
        'si el alcance fuera el documento entero, la linea 6 tambien se '
        'dispensaria: %r' % rs.afirmada_sin_negar(texto, '270'))


def test_el_alcance_de_numeros_es_el_numero_entero():
    """Y que se comparan enteros, no por limites de token."""
    assert rs.afirmada_sin_negar(
        '| cortes postflop de la poblacion | 2 270 |\n', '270') == [], (
        'ha encontrado 270 dentro de 2 270')
    assert rs.afirmada_sin_negar(
        '| cortes preflop de poblacion B | 83 |\n| con etiqueta | **270** |\n',
        '270') == [2], 'pero un 270 de verdad si se ve'


# ================================== 3. los tres falsos positivos, aqui
def test_los_tres_falsos_positivos_estan_como_casos_de_test():
    """R1 lo pide: "como casos de test, no como exclusiones".

    Y hay una diferencia que importa. Una exclusion es «este numero no es el
    que buscas», puesta en el escaner, y se pierde en cuanto el numero
    cambia: el 270 de un contrato pasa a ser 271 y la exclusion dice otra
    cosa. Un caso de test es un documento con la forma exacta del fallo, y
    se queda aunque los numeros cambien.

    Y hay una comprobacion mas: que esten en el fichero de casos y no
    repartidos. Repartidos tambien son copias, y dos sitios divergen."""
    ruta = os.path.join(ROOT, 'tools', 'test_falsos_positivos.py')
    casos = io.open(ruta, encoding='utf-8').read()
    for marca, que in (
            ('**TOTAL** | **78**', 'un total de defectos'),
            ('perfil con mas muestra', 'el tamano de un perfil'),
            ('2 270 millones', 'un numero con espacio de millar')):
        assert marca in casos, (
            'el falso positivo de %s no esta como caso de test' % que)
    # y que NO sea una exclusion en el escaner
    assert 'def es_frase_numerica' in FUENTE
    assert 'excluir' not in FUENTE.lower().split('def ')[0], (
        'el escaner no lleva una lista de exclusiones: los casos van en tests')


def test_los_falsos_positivos_no_viven_en_dos_ficheros():
    """Y que no se hayan repartido. Antes `test_barrido_documentos.py` tenia
    tres de estos casos y `test_falsos_positivos.py` los otros tres: la misma
    regla en dos ficheros."""
    ruta = os.path.join(ROOT, 'tools', 'test_barrido_documentos.py')
    otro = io.open(ruta, encoding='utf-8').read()
    for nombre in ('test_un_total_de_defectos_no_es_un_total_de_observaciones',
                   'test_el_tamanio_de_un_perfil_no_es_un_corte_postflop',
                   'test_una_mano_con_etiqueta_sigue_siendo_una_observacion'):
        assert ('def %s(' % nombre) not in otro, (
            '%s sigue duplicado en test_barrido_documentos.py' % nombre)