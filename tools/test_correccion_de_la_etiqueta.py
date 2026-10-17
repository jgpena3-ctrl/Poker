# -*- coding: utf-8 -*-
"""Tarea 1: la correccion de la ETIQUETA esta escrita en los tres .md.

QUE COMPRUEBA, Y POR QUE HACE FALTA

El arreglo de fondo de los cuatro bloques fue de CODIGO: `resto_de_muestra()`
dejo de acoplar `y` con `motivo`. Y un arreglo de codigo que no esta escrito
es un arreglo que el proximo que lea los documentos no puede ver.

Medido antes de escribir: ninguno de los tres documentos decia ninguna de las
nueve cosas. Lo que si aparecia eran tres cosas que NO son la correccion:

  - "el AUC preflop no se calcula"  — es otra cosa: el AUC, no la etiqueta
  - "se caen al leer la etiqueta"  — es una consecuencia, no el contrato
  - "`y = 0` por construccion"      — es de los folds

O sea que el documento y el codigo contaban historias distintas sobre la misma
cosa, que es exactamente el defecto que este bloque lleva cuatro rondas
corrigiendo.

Y LA NOVENA COSA ES LA IMPORTANTE

Los ceros —0 inventadas, 0 distorsionadas, 0 perdidas— SIN el matiz se leen
como una garantia. Y no lo son: son lo que habia ANTES del cambio, y por eso
el contrato estricto pasaba por suerte. El matiz ("pasaba por suerte", "por
construccion") es lo que convierte una medicion en un contrato.

Un test que comprobara solo los ceros dejaria pasar el documento que dice
"0 perdidas" y suena a garantia, que es el documento que hace dano.

Y ADEMAS, UNA AFIRMACION TIENE QUE ESTAR EN SU PROPIA ORACION

No es estilo: es comprobabilidad. «La etiqueta se lee, y no se calcula» son dos
afirmaciones, y el filtro de polaridad del escaner las descarta las dos
porque ve el «no». Separadas, cada una se comprueba, se cita y se edita sola.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from retraccion_scan import afirmada_sin_negar, leer          # noqa: E402

LOS_TRES = ('DECISION_OBJETIVO_AUC.md', 'LIMITACION_PREFLOP_AUC.md',
            'REPRESENTATIVIDAD_23.md')

# Las nueve, con las formas que se aceptan para cada una. Varias por idea,
# porque un test que exige una sola obliga a escribir el documento como el
# test —que es lo que este bloque lleva cuatro rondas corrigiendo—.
NUEVE = (
    ('la etiqueta se lee', ('la etiqueta se lee',)),
    ('no se calcula', ('no se calcula',)),
    ('se leia, en vez de leerse', ('no se leía', 'no se leia')),
    ('y y motivo independientes', ('independientes',)),
    ('estaban acoplados', ('acoplados',)),
    ('0 inventadas', ('0 inventadas',)),
    ('0 distorsionadas', ('0 distorsionadas',)),
    ('0 perdidas', ('0 perdidas',)),
    ('el contrato pasaba por suerte', ('por suerte',)),
    ('y se sostiene por construccion', ('por construcción',)),
)


def _alguna(texto, formas):
    return any(afirmada_sin_negar(texto, f) for f in formas)


def test_los_tres_dicen_las_nueve_cosas():
    """Las nueve, en los tres. Y el fallo dice CUAL falta y en cual, que es
    lo que hace falta para poder arreglarlo."""
    faltan = []
    for n in LOS_TRES:
        texto = leer(n)
        for etiqueta, formas in NUEVE:
            if not _alguna(texto, formas):
                faltan.append('%s: %s' % (n, etiqueta))
    assert not faltan, (
        'la correccion de la etiqueta NO esta escrita en los tres .md:\n   '
        + '\n   '.join(faltan))


def test_los_tres_dicen_el_matiz_de_los_ceros():
    """Y en la MISMA oracion, o cerca, que los ceros. Porque `0 perdidas` sin
    `por suerte` al lado se lee como una garantia, y no lo es."""
    for n in LOS_TRES:
        texto = leer(n)
        ceros = set()
        for f in ('0 inventadas', '0 distorsionadas', '0 perdidas'):
            ceros.update(afirmada_sin_negar(texto, f))
        suerte = set(afirmada_sin_negar(texto, 'por suerte'))
        construccion = set(afirmada_sin_negar(texto, 'por construcción'))
        assert ceros and (suerte or construccion), (
            '%s dice los ceros y no el matiz' % n)
        # La distancia que importa es al matiz MAS CERCANO, no al mas lejano.
        # En LIMITACION hay un "por construccion" en la linea 32, que es una
        # tabla sobre folds, y otro en la 221, que es el matiz de verdad. Una
        # version anterior de este test comparaba contra el mas lejano y decia
        # que el matiz estaba a ciento ochenta lineas.
        matiz = suerte | construccion
        mas_cerca = min(abs(c - m) for c in ceros for m in matiz)
        assert mas_cerca <= 12, (
            '%s: el cero mas cercano esta a %d lineas de su matiz. A esa '
            'distancia el matiz no acompaña al cero, y "0 perdidas" se lee '
            'como una garantia' % (n, mas_cerca))


def test_una_afirmacion_esta_en_su_propia_oracion():
    """Y una comprobacion de estructura, no de vocabulario.

    «La etiqueta se lee, y no se calcula» son dos afirmaciones en una, y el
    filtro de polaridad descarta las dos porque ve el «no» de la segunda. La
    afirmacion central tiene que poder comprobarse sola.

    Y los TITULOS quedan fuera, y no por conveniencia: un titulo es una
    etiqueta, no una afirmacion, y por definicion es una sola linea. La regla
    es para la prosa. Ademas el filtro de polaridad no juzga un titulo, asi
    que la afirmacion de verdad se encuentra en el cuerpo.
    """
    for n in LOS_TRES:
        texto = leer(n)
        lineas = texto.split('\n')
        for i, linea in enumerate(lineas, 1):
            if linea.lstrip().startswith('#'):
                continue                    # un titulo es una etiqueta
            b = linea.lower()
            if 'se lee' not in b or 'no se calcula' not in b:
                continue
            raise AssertionError(
                '%s:%d tiene las dos afirmaciones en la misma linea: %s. '
                'Separadas, cada una se comprueba sola'
                % (n, i, linea.strip()[:60]))


# ============================ y el codigo, para que el texto no mienta
def test_el_codigo_cumple_lo_que_los_documentos_dicen():
    """Un documento que describe una herramienta se miente en cuanto la
    herramienta cambia. Esto comprueba que la descripcion sigue siendo
    cierta."""
    ruta = os.path.join(ROOT, 'tools', 'auditar_representatividad.py')
    fuente = io.open(ruta, encoding='utf-8').read()
    i = fuente.index('def resto_de_muestra')
    j = fuente.index('\ndef ', i + 5)
    cuerpo = fuente[i:j]

    # 1. la etiqueta se lee AL PRINCIPIO, antes de los filtros
    assert cuerpo.index('y_real = etiq.get') < cuerpo.index('declarados ='), (
        'la etiqueta ya no se lee primero: los filtros se adelantan otra vez')
    # 2. los filtros no tocan `y`
    assert 'y_real' in cuerpo, 'y la etiqueta no sale de una variable'
    # 3. los retornos de motivo la conservan
    for linea in cuerpo.split('\n'):
        c = linea.strip()
        if not c.startswith('return Resto('):
            continue
        if "'sin etiqueta" in c or "'reparto" in c:
            continue          # estas dos SÍ devuelven None, y está bien
        assert 'y_real' in c, (
            'este retorno de motivo devuelve None sin decirlo: %s' % c)
    # 4. y que el docstring diga que son independientes
    assert 'INDEPENDIENTES' in cuerpo.upper(), (
        'el docstring no dice que `y` y `motivo` son independientes, y el '
        'documento dice que lo son')