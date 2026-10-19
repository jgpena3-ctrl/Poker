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
import re
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


# ==================== 1. los tres pares, y no dos cadenas sueltas
#
# «0,8308 aparece en el documento» no es «0,8308 es el numero SIN el filtro».
# Si los dos numeros estuvieran en un parrafo sobre otra cosa, los dos
# asserts pasan.
#
# Y no hace falta un verificador universal de prosa. Basta con que el test sea
# sensible a las contradicciones CONCRETAS que ya se encontraron, que son tres,
# y cada una es un PAR: cifra <-> condicion.
#
# El criterio del par: cifra y condicion tienen que estar en la MISMA clausula,
# o en clausulas contiguas. No es que tengan que estar en la misma linea —un
# documento bien escrito parte las frases— sino que no puede haber otras cosas
# en medio.
def _seccion(doc, desde):
    """La SECCION que contiene la posicion `desde`: del ultimo encabezado
    anterior hasta el siguiente.

    Y el criterio del par es la SECCION, no la clausula. Uno anterior exigia
    la misma clausula, y el documento separa en una tabla de dos columnas,
    con la cifra y su condicion en celdas distintas. La clausula es mas
    pequena de lo que la idea, y mas grande de lo que la linea.

    Y la seccion tiene que ser la QUE CONTIENE la posicion, no la que empieza
    en ella. Una version empezaba en `desde` y por eso no encontraba la
    condicion, que en el documento va ANTES de la cifra:

        | con el filtro de particion | 11 | **0,7667** |

    La condicion esta a la izquierda, en la misma fila, y una ventana que
    empieza en la cifra no la ve nunca.
    """
    cab = None
    for m in re.finditer(r'\n#{2,4} ', doc):
        if m.start() < desde:
            cab = m.start()
        else:
            fin = m.start()
            break
    else:
        fin = len(doc)
    ini = cab if cab is not None else 0
    return doc[ini:fin]


def _misma_seccion(doc, cifra, condiciones):
    """True si la cifra esta ASOCIADA a su condicion. Y «asociada» depende de
    donde este escrita:

      - en una FILA DE TABLA, la condicion tiene que estar en esa misma fila.
        En una tabla, la condicion y el valor son la misma linea: por eso la
        tabla de §4.2 dice «| con el filtro | 11 | 0,7667 |».

      - en PROSA, basta con la misma seccion. En prosa la condicion puede
        estar dos frases antes, y exigir la misma linea seria exigir que el
        documento este escrito como el test.

    POR QUE NO «CUALQUIER MENCION CON UNA CONDICION»

    Porque una version anterior hacia eso, y no era sensible: el documento
    tiene siete menciones de 0,7667, y romper una no la tumba. Los tres tests
    de sensibilidad de `test_sensibilidad_de_los_tests.py` PASABAN con el
    documento deliberadamente roto, y por eso los tres se escribieron.

    O sea: «esta en algun sitio con una condicion» no es «esta con SU
    condicion». Y esa distincion es la que hace que el test sea un detector
    y no una busqueda.

    Y no se trata «con la condicion contraria» como una contradiccion: una
    tabla de comparacion trae las DOS condiciones, porque la comparacion es
    eso. Eso fue el TERCER falso positivo de este bloque.
    """
    b = doc.lower()
    for m in re.finditer(re.escape(cifra), b):
        ini = b.rfind('\n', 0, m.start()) + 1
        fin = b.find('\n', m.start())
        linea = b[ini:fin if fin > 0 else len(b)]
        if linea.lstrip().startswith('|'):
            # fila de tabla: la condicion va en la fila
            if any(c in linea for c in condiciones):
                return True
        else:
            if any(c in _seccion(b, m.start()).lower() for c in condiciones):
                return True
    return False


def test_los_numeros_no_estan_sueltos_y_su_condicion_no():
    """0,8308 SIN el filtro, y 0,7667 CON el. Cada cifra con su condicion."""
    doc = leer('QUE_REPRESENTA_LA_PREDICCION.md').lower()
    pares = (
        ('0,8308', ('sin el filtro', 'sin filtro', 'no filtrar'), 'el malo'),
        ('0,7667', ('con el filtro', 'filtrada', 'con filtro'), 'el bueno'),
    )
    sueltos = []
    for cifra, condiciones, quien in pares:
        if not _misma_seccion(doc, cifra, condiciones):
            sueltos.append('%s (%s) no aparece junto a su condicion' % (
                cifra, quien))
    assert not sueltos, (
        'las cifras aparecen pero sin su condicion:\n   '
        + '\n   '.join(sueltos) + '\n\n   O sea: estan sueltas en el '
        'documento, y un numero suelto no dice a que condicin pertenece.')


def test_la_relacion_de_validez_no_esta_suelta():
    """Y lo que R2 senala en el mismo punto: que las DOS afirmaciones esten,
    y que la relacion este escrita.

    «Dice CONTRATO_L_SEC» mas «dice no es una consecuencia» son dos
    afirmaciones que pueden estar en paginas distintas. Lo que las une es que
    la segunda las alcance."""
    doc = leer('QUE_REPRESENTA_LA_PREDICCION.md').lower()
    # La relacion vive en §4.3, NO en la primera mencion del nombre del
    # contrato, que esta en §5. Y eso lo dijo el fallo de este test: estaba
    # midiendo la relacion en el sitio equivocado del documento, que es lo
    # mismo que no medirla.
    i, _sec = _indice_de_la_tesis_43(doc)
    assert i > 0, (
        'no se encuentra la tesis en §4.3. Y si no esta, el §4.3 no esta o '
        'la tesis se ha movido: las dos cosas hay que saberlas antes de '
        'seguir')
    sec = _seccion(doc, i)
    assert 'no una consecuencia' in sec or 'no es una consecuencia' in sec, (
        'la relacion —la validez NO es consecuencia del AUC bonito— no esta '
        'en la seccion de la tesis. Y las dos formas valen: el documento '
        'escribe una, y un test que exige una sola senala el documento que '
        'esta bien')
    assert 'contrato_l_sec' in sec, (
        'y el contrato no se menciona en la seccion de la tesis, que es '
        'justo donde tiene que estar: la validez sale de ahi')


# ==================== 2. la polaridad de las tesis
# La seccion donde vive la tesis de §4.3. Y se busca por ENCABEZADO y no por
# offset: un `find(frase, 4000)` funciona mientras el documento no crezca por
# encima, y en cuanto crece cae en el sitio equivocado. Un numero magico
# posicionado es un `offset` disfrazado de estructura.
#
# Y si la seccion no esta, se dice. Una funcion que devuelve cadena vacia
# porque no ha encontrado lo que buscaba hace que el test falle por un motivo
# que no dice nada — que es como se rompio esto la primera vez.
SECCION_DE_LA_TESIS = '### 4.3'


def _indice_de_la_tesis_43(doc):
    """(indice, seccion) de la primera mencion de la tesis en §4.3.

    Devuelve (indice, seccion) del par. Si la seccion no existe, (-1, '')."""
    b = doc.lower()
    i_sec = b.find(SECCION_DE_LA_TESIS.lower())
    if i_sec < 0:
        return -1, ''
    m = re.search(r'\n#{2,4} ', b[i_sec + 1:])
    sec = b[i_sec:i_sec + 1 + (m.start() if m else len(b))]
    i = sec.find('es el correcto')
    return (i_sec + i if i >= 0 else -1), sec


def _orbita_de_la_tesis(doc):
    """La clausula que sigue a la tesis del CORRECTO, en §4.3.

    Y no la seccion. Una version anterior de este comprobador miraba los
    primeros 200 caracteres de la seccion, y §4.3 tiene muchos «no», o sea
    que la comprobacion era tan laxa que nunca caia. Y un test que nunca cae
    no es un test de sensibilidad.

    La orbita es la clausula: en

        **El filtro es el CORRECTO.** Eso **no** esta demostrado, y no lo
        puede estar con esta prueba.

    lo que lleva la polaridad es «Eso **no** esta demostrado».

    Y HAY QUE SALTAR LA PUNTUACION del principio. Una version anterior
    tomaba lo que venia despues de «es el correcto» hasta el primer
    delimitador, y el primer delimitador era el punto que cierra la tesis.
    O sea: la orbita salia VACIA, y el test que la usa fallaba sin decir por
    que. Un comprobador que devuelve cadena vacia no es un comprobador: hay
    que devolver lo que hay despues de la puntuacion, que es justo lo que
    lleva la polaridad.
    """
    b = doc.lower()
    i, _sec = _indice_de_la_tesis_43(b)
    if i < 0:
        return ''
    j = i + len('es el correcto')
    # Se salta lo que CIERRA la frase anterior: puntuacion, espacios y
    # MARCADO DE EMPATIS. El marcado no es contenido, y si no se salta, un
    # `**` seguido de salto de linea corta la orbita ahi y devuelve `**`.
    #
    # Que es lo que pasaba con la variante legitima mas comun de Markdown:
    #
    #     El filtro es el correcto**
    #     Eso **no** esta demostrado, y no lo puede estar.
    #
    # Y eso se vio porque el test de formatos existia y miraba. Un caso de
    # formato que no se cubre es un caso que nadie sabe que existe.
    while j < len(b) and b[j] in '. \t-*_`>':
        j += 1
    # Y AQUI ESTA LA FRONTERA: un SALTO DE PARRAFO. No se salta, y no es un
    # matiz: es lo que separa «la negacion es de la tesis» de «la negacion
    # es de otra cosa».
    #
    #     **El filtro es el CORRECTO.** Eso **no** esta demostrado
    #     -> una frase, dos clausulas: la negacion es de la tesis
    #
    #     **El filtro es el CORRECTO**.
    #
    #     Eso **no** esta demostrado
    #     -> dos parrafos: la negacion es de otra cosa, y el documento
    #        AFIRMA la tesis mientras niega otra cosa. Que es la
    #        contradiccion 200/238 en otra forma.
    #
    # Un salto SIMPLE si se salta, porque en Markdown un salto simple es un
    # corte visual y no una frontera de oracion.
    if b[j:j + 2] == '\n\n':
        return ''
    while j < len(b) and b[j] == '\n':
        j += 1
    m = re.search(r'[.;:\n]', b[j:])
    return b[j:j + (m.start() if m else 200)]


def test_la_tesis_de_causa_se_afirma_y_no_se_niega():
    """Que `afirmada()` no acepte la NEGACION de la tesis.

    «el filtro NO es la causa» pasa un test de presencia y es justo lo
    contrario de lo que el §4.3 sostiene."""
    doc = leer('QUE_REPRESENTA_LA_PREDICCION.md')
    for negation in ('no es la causa', 'No es la causa',
                     'no es la CAUSA'):
        assert not afirmada_sin_negar(doc, negation), (
            'el documento NIEGA la tesis de causa con %r. El §4.3 dice lo '
            'contrario, y una tesis que se afirma y se niega en el mismo '
            'documento no es una tesis' % negation)


def test_la_tesis_de_no_validez_se_afirma_como_no_demostrada():
    """Y lo mismo al reves: que el documento diga que NO esta demostrado que
    el filtro sea el correcto.

    Y que lo diga de una forma que un test pueda distinguir de «esta
    demostrado». Que es el punto entero: «dice CORRECTO» y «dice que NO esta
    demostrado CORRECTO» no son lo mismo, y un test de presencia no lo ve."""
    doc = leer('QUE_REPRESENTA_LA_PREDICCION.md')
    b = doc.lower()
    # La tesis se mide en §4.3. Buscando la PRIMERA mencion, el test cae en
    # la de §4.2, que es otra cosa: §4.2 habla de la prueba de la CAUSA.
    i, _sec = _indice_de_la_tesis_43(b)
    assert i > 0, (
        'no se encuentra la tesis en §4.3. Y si no esta, el §4.3 no esta o '
        'la tesis se ha movido: las dos cosas hay que saberlas antes de '
        'seguir')
    # Y aqui va la ORBITA, no los primeros 600 caracteres de la seccion.
    #
    # Con los 600 caracteres, esta comprobacion NO CAIA al invertir la
    # polaridad de la tesis: §4.3 tiene muchos «no», y con que hubiera uno en
    # los primeros 600 daba por buena la tesis invertida.
    #
    # Y eso es exactamente lo que R2 senala: un test de aceptacion que sigue
    # pasando por otra ruta. Aqui la otra ruta era una comprobacion floja del
    # mismo test — o sea, no hacia falta ni un segundo test para ocultarla.
    orb = _orbita_de_la_tesis(b)
    assert orb, 'no se encuentra la orbita de la tesis'
    assert ('no' in orb and 'demostrado' in orb), (
        'la tesis del CORRECTO se menciona en §4.3 sin decir que NO esta '
        'demostrada. La orbita dice: %r' % orb)
    # y que no afirme lo contrario
    for mala in ('esta demostrado que sea el correcto',
                 'está demostrado que sea el correcto'):
        assert not afirmada_sin_negar(doc, mala), (
            'el documento AFIRMA %r, que es lo contrario de lo que sostiene '
            'el §4.3' % mala)


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