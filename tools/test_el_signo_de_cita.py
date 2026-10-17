# -*- coding: utf-8 -*-
"""El `>` de este proyecto se usa para TRAS cosas, y solo una es mala.

Un detector de «ninguna afirmacion propia empieza por `>`» dio 31 lineas, y
casi todas eran correctas:

  - CITA DE RETRACCION   «> Antes decia 78 con etiqueta... Retirado»
  - CITA DE CODIGO       «> No se puede hacer mejor con estos datos», que es
                         el docstring de equity_de_mano.py
  - NOTA DE CABECERA     el aviso de los primeros lineas del documento

Las tres son «`>` = esto no lo afirma este documento», que es justo lo que
necesita el escaner. Solo la cuarta —subrayar— es mala.

Y esa cuarta no se puede distinguir de las tres por forma: un `>` delante de
una frase no dice de donde sale la frase. Markdown no la diferencia, y quien
la escribe no se entera hasta que un detector le avisa.

O sea: un detector de «ningun `>` propio» no distingue lo malo de lo bueno. Y
un detector que no distingue senala documentos correctos, que es el TERCER
falso positivo de este bloque y el tercero de la misma forma: el numero o la
marca coincide y el sujeto no.

Lo que se comprueba, y SI es comprobable:

  1. las afirmaciones centrales del documento tienen que ser AFIRMACIONES y
     no citas. Por el contenido, no por la marca.
  2. las retracciones tienen que seguir siendo citas, para que arreglar (1)
     no se haga vaciando el fichero.

Y queda escrito el limite en `cita()`, porque un limite declarado se puede
discutir y uno no declarado se descubre tarde.

EL CASO REAL QUE SI SE ARREGLO

`QUE_REPRESENTA_LA_PREDICCION.md` tenia sus tres tesis principales —el
filtro es la CAUSA de la diferencia, NO es el CORRECTO, no es una
coincidencia— marcadas con `>`. O sea: marcadas como cita, e invisibles al
escaner. El fallo parecia del test y era del documento.

Es el fallo que el escaner existe para detectar, en el documento que mas
sufría de el.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from retraccion_scan import afirmada, citada, leer            # noqa: E402

# Las afirmaciones centrales, POR CONTENIDO. Si el documento no las dice, no
# las dice, diga lo que diga la marca.
CENTRALES = (
    'QUE_REPRESENTA_LA_PREDICCION.md',
    ('CAUSA de la diferencia',
     'es el CORRECTO',
     'no es una coincidencia',
     'no una consecuencia',
     'no lo detecta'),
)


def test_las_afirmaciones_centrales_son_afirmaciones_y_no_citas():
    """Y el fallo dice cual. Un documento puede tener sus tesis principales
    marcadas como cita y entonces no las esta defendiendo: las esta
    atribuyendo a otro."""
    doc = leer(CENTRALES[0])
    malos = [k for k in CENTRALES[1] if not afirmada(doc, k)]
    assert not malos, (
        'afirmaciones centrales que no son afirmaciones del documento, o '
        'estan marcadas como cita y por eso el escaner no las ve:\\n   '
        + '\n   '.join(malos))


def test_y_las_retracciones_siguen_siendo_citas():
    """La otra mitad, y es la que impide arreglar lo anterior vaciando el
    fichero de citas. Un `>` de mas y uno de menos, y el escaner se convierte
    en ruido."""
    for n in ('LIMITACION_PREFLOP_AUC.md', 'REPRESENTATIVIDAD_23.md',
              'FASE_D_BLOQUEADA.md', 'DECISION_OBJETIVO_AUC.md'):
        doc = leer(n)
        assert (citada(doc, 'se retira') or citada(doc, 'Retirado')
                or citada(doc, 'antes decia')
                or citada(doc, 'Antes decía')), (
            '%s ya no cita ninguna retraccion: puede que le hayan quitado el '
            '`>` a todo para tapar el problema del test anterior' % n)


def test_el_limite_esta_declarado_en_la_funcion_que_decide():
    """Que `cita()` diga que `>` significa «esto no lo afirma este documento»,
    y que nombre los usos legitimos. Porque el nombre es lo que hace que el
    proximo que escriba un `>` se lo piense."""
    fuente = io.open(os.path.join(ROOT, 'tools', 'retraccion_scan.py'),
                     encoding='utf-8').read()
    # El bloque que explica la marca va INMEDIATAMENTE antes de `def cita(`,
    # asi que se extrae andando hacia atras por las lineas de comentario. Una
    # version anterior usaba una ventana de 1400 caracteres hacia atras, y se
    # rompio dos veces: al anadir una frase al bloque, la ventana se quedaba
    # corta. Una ventana por longitud es un acoplamiento con el tamaño.
    lineas = fuente.split('\n')
    k = next(i for i, l in enumerate(lineas) if l.startswith('def cita('))
    arriba = k - 1
    while arriba >= 0 and lineas[arriba].lstrip().startswith('#'):
        arriba -= 1
    bloque = '\n'.join(lineas[arriba + 1:k + 4])
    assert bloque.strip(), 'el comentario se ha perdido'
    # Cualquiera de las variantes, no todas. El comentario escribe CODIGO sin
    # tilde, y una version anterior de este test exigia cada variante por
    # separado —o sea, exigia tambien la acentuada— y por eso fallaba con el
    # comentario correcto delante. Un test que exige una forma concreta
    # obliga a escribir el codigo como el test.
    for formas in (('código', 'codigo'), ('cabecera',), ('nota',)):
        assert any(u in bloque.lower() for u in formas), (
            'el comentario no nombra el uso legitimo de %r. Hay que nombrar '
            'los tres, o el cuarto —subrayar— parece el unico que hay'
            % (formas[0],))
    assert 'subrayar' in bloque.lower() or 'SUBRAYAR' in bloque, (
        'y no dice cual es el uso que ROMPE')
    assert '>' in bloque, 'ni menciona la marca'