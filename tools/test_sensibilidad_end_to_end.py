# -*- coding: utf-8 -*-
"""LOS TRES CASOS DE ROTURA, END-TO-END, Y EL UMBRAL A 3

QUE HACE, Y POR QUE ESTA SEPARADO

Los tres tests anteriores comprueban que los AUXILIARES reaccionan. Eso esta
bien y no basta: un auxiliar que cae dice poco, porque el test de aceptacion
puede tener otra comprobacion que siga dando verde.

R2 lo dice:

    Un test de aceptacion podria seguir pasando por otra ruta. ... basta con
    probar el comportamiento que se afirma garantizar.

Asi que aqui se ejecuta el FICHERO DE TESTS REAL, en un subproceso, contra
una copia de DOCS con el documento deliberadamente roto:

    1. se copia DOCS entero a un temporal
    2. se altera lo que se quiere romper
    3. se ejecuta `pytest tools/test_causa_no_validez.py` con
       `POKER_DOCS_DIR` apuntando al temporal
    4. y se comprueba que FALLA

Que es end-to-end: el test real, ejecutado, no su helper.

Y POR QUE SE COPIA DOCS ENTERO

Porque el fichero de aceptacion comprueba cosas de VARIOS documentos —la
tesis en QUE_REPRESENTA, el contrato en CONTRATO_L_SEC, las cinco cifras en
los tres— y si el temporal solo tuviera el documento roto, los otros fallarian
por falta de fichero y el test pasaria por la razon equivocada.

UMBRAL A 3, Y POR QUE

El test conjunto terminaba con `assert caidas >= 2`, con tres casos
declarados. R2:

    Aunque el texto explica tres tipos de rotura, ese umbral permite que una
    de las tres no sea detectada.

Y tiene razon, y es un defecto con nombre: un umbral debil **acepta el
defecto en vez de senalarlo**. Tres casos declarados y un umbral de dos es
decir «dos de tres me valen», que es exactamente lo que hace que un test
de sensibilidad se relaje sin que nadie lo note.

Ahora exige las tres. Y si una dejara de caer, el test lo dice Y DICE CUAL.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import ejecutar_pytest as ep
import retraccion_scan as rs                                   # noqa: E402

DOCS = os.path.join(ROOT, 'DOCS')
FICHERO_DE_ACEPTACION = os.path.join(ROOT, 'tools',
                                     'test_causa_no_validez.py')

# Las tres roturas, y por que cada una es una contradiccion CONCRETA — que
# es lo que R2 pide: no un verificador universal, sino sensibilidad a lo que
# ya se encontro.
ROTURAS = (
    ('ninguna cifra con su condicion',
     'sin el filtro', 'en la medicion',
     'las cifras no dicen a que condicion pertenecen'),
    ('la asignacion invertida',
     '| con el filtro de partición | 11 | **0,7667** — el publicado |',
     '| sin el filtro de partición | 11 | **0,7667** — el publicado |',
     '0,7667 aparece junto a la condicion CONTRARIA'),
    ('la polaridad de la tesis',
     'Eso **no** está demostrado, y no lo puede',
     'Eso **sí** está demostrado, y lo puede',
     'la tesis pasa de "no esta demostrado" a "si esta demostrado"'),
)


def _docs_rotos(viejo, nuevo, todas=True, nombre=None):
    """Copia de DOCS con una sustitucion hecha. None si el texto no estaba.

    `todas=True` cambia TODAS las apariciones, y por defecto.

    Y eso no es un detalle: una version anterior cambiala PRIMERA, y con eso
    el caso «ninguna cifra con su condicion» NO CAIA, porque el documento
    tiene mas de una mencion de «sin el filtro» y quedaban sitios bien
    asociados. El detector los encontraba, con razon.

    O sea que la rotura no era la que decia ser. «Cambiar la primera
    aparicion» no es «dejar de asociar la cifra con su condicion», y esa
    distincion es la que separa una rotura de un cambio de redaccion.

    Y por defecto `todas=True`, porque una rotura que solo cambia la primera
    aparicion es, casi siempre, un cambio de redaccion y no una
    contradiccion."""
    tmp = tempfile.mkdtemp(prefix='opencode_e2e_')
    destino = os.path.join(tmp, 'DOCS')
    shutil.copytree(DOCS, destino)
    ruta = os.path.join(destino, 'QUE_REPRESENTA_LA_PREDICCION.md')
    with io.open(ruta, encoding='utf-8') as f:
        texto = f.read()
    if viejo not in texto:
        shutil.rmtree(tmp, ignore_errors=True)
        return None
    cambiado = texto.replace(viejo, nuevo) if todas else \
        texto.replace(viejo, nuevo, 1)
    # Y por `escribir_documento`, que ademas la MARCA como sin probar.
    #
    # Y el ambito es POR TEST, no por funcion: `_docs_rotos()` se llama desde
    # el test y el subproceso se lanza desde el mismo test. Habia escrito que
    # este fichero no podia usar el invariante «porque escribe en una funcion
    # y ejecuta en otra», y es verdad para un ambito por FUNCION y falso
    # aqui. No se comprueba una limitacion antes de mirar si existe.
    ep.escribir_documento(
        ruta, cambiado,
        que='«%s»' % (nombre if nombre else (viejo[:44] + '…')))
    return destino


def _ejecutar_aceptacion(docs_dir):
    """El exit code de pytest sobre el fichero de aceptacion.

    Y el codigo YA DESCARTADO como 4 —«no se ha ejecutado nada»— y como 5
    —«no se ha encontrado ningun test»—, que es lo que hace
    `ejecutar_pytest.correr` antes de devolver.

    Que no es una Kedada: los tres tests de rotura de este fichero vivian
    sobre `!= 0`, y un `!= 0` aprueba un 4 en verde. Si alguna vez el
    selector se descoloca, estos tres darian verde diciendo «algo ha
    caido» sin que se haya ejecutado nada. Que es el error mas caro que
    ha tenido este repositorio."""
    env = dict(os.environ)
    env[rs.DIR_DE_DOCUMENTOS] = docs_dir
    env['PYTHONPATH'] = os.path.join(ROOT, 'tools')
    return ep.correr(FICHERO_DE_ACEPTACION, None, env=env, cwd=ROOT)


# ==================================================== el control
def test_sin_romper_nada_el_fichero_de_aceptacion_pasa():
    """La precondicion, y sin ella los tres tests de abajo no dicen nada: si
    el fichero ya fallara de base, caeria con cualquier rotura y por la
    razon equivocada."""
    salida = _ejecutar_aceptacion(DOCS)
    assert salida[0] == 0, (
        'el fichero de aceptacion ya falla SIN romper nada:\n%s'
        % salida[1][-1500:])


# ==================================================== las tres roturas
@pytest.mark.parametrize('nombre,viejo,nuevo,por_que', ROTURAS,
                         ids=[r[0] for r in ROTURAS])
def test_el_fichero_de_aceptacion_falla_si_se_rompe(nombre, viejo, nuevo,
                                                    por_que):
    """END-TO-END: el fichero real, ejecutado, contra el documento roto.

    Y EL LIMITE DE ESTA PRUEBA, aqui mismo y no en otro fichero. R2 lo pide,
    y la razon no es de estilo: este fichero es el que dice «estos tests son
    sensibles», y si el limite vive en el comentario de otro, aqui se leeria
    mas cobertura de la que tiene. Aqui es donde se va a leer.

    **Lo que demuestra:** que los tests de aceptacion de
    `test_causa_no_validez.py` CAEN cuando el documento se rompe de TRES
    maneras concretas. Una proteccion de UN fichero contra TRES
    contradicciones concretas.

    **Lo que NO demuestra:** que el escaner detecte cualquier afirmacion. No
    es un verificador de prosa y no se le atribuye mas cobertura: comprueba
    cadenas en un documento concreto.

    Que es la distincion de la que R2 habla al final — el criterio tiene que
    detectar la contradiccion REAL, no encontrar las palabras correctas en
    algun sitio — y la unica forma de saber si lo hace es romper el documento
    y mirar."""
    destino = _docs_rotos(viejo, nuevo, nombre=nombre)
    if destino is None:
        pytest.skip('el texto %r no esta en el documento: hay que '
                    'actualizar este test, que es lo que comprueba' % viejo)
    try:
        # Y `afirmar_caida`, no un `!= 0`: exige el codigo CONCRETO y ademas
        # que la salida traiga el RECUENTO de fallos. Sin lo segundo, un 1
        # por un `import` roto contaria como «la rotura ha funcionado», y no
        # lo es: el fichero de aceptacion no llego a ejecutarse.
        salida = ep.afirmar_caida(
            FICHERO_DE_ACEPTACION, None, env=dict(
                os.environ, **{
                    rs.DIR_DE_DOCUMENTOS: destino,
                    'PYTHONPATH': os.path.join(ROOT, 'tools')}),
            cwd=ROOT,
            cuando=('EL FICHERO DE ACEPTACION NO HA CAIDO con la rotura '
                    '«%s».\nEs decir: %s\n\nY eso significa que el test de '
                    'aceptacion tiene otra comprobacion que sigue dando '
                    'verde, y que este fichero NO protege esa relacion. R2 lo '
                    'dijo: un test de aceptacion puede seguir pasando por '
                    'otra ruta.' % (nombre, por_que)))
        # Y la mutacion se ha probado: escrita y ejecutada. Un test puede
        # escribir una rotura, comprobar que cae, y que la rotura no llegue
        # a mirar el documento que dice estar mirando.
        pendientes = ep.sin_probar()
        assert not pendientes, (
            'se ha escrito una rotura y no ha llegado a ningun test:\n%s'
            % chr(10).join('   - %s' % que for que, _ in pendientes))
    finally:
        shutil.rmtree(os.path.dirname(destino), ignore_errors=True)


def test_los_tres_casos_caen_y_el_umbral_lo_exige():
    """Los TRES, y el umbral es 3.

    El umbral era `>= 2` con tres casos declarados, y eso es decir «dos de
    tres me valen». Que es lo que hace que un test de sensibilidad se relaje
    sin que nadie lo note: uno deja de caer, el umbral lo absorbe, y el test
    sigue verde.

    Y el fallo dice cual, porque «ha caido menos de tres» no dice cual."""
    caidas, detalle = 0, []
    for nombre, viejo, nuevo, _por_que in ROTURAS:
        destino = _docs_rotos(viejo, nuevo, nombre=nombre)
        if destino is None:
            detalle.append('%s: el texto no esta, no se puede comprobar'
                           % nombre)
            continue
        try:
            codigo, _salida = _ejecutar_aceptacion(destino)
        finally:
            shutil.rmtree(os.path.dirname(destino), ignore_errors=True)
        # Y aqui SI se cuenta en vez de afirmar, porque el fallo tiene que
        # decir QUE CASO no ha caido. Pero se cuenta SOLO el 1: un 4 o un 5
        # ya los ha descartado `correr`, y cualquier otro se cuenta como lo
        # que es —una interrupcion— y no como «una rotura que ha roto».
        if codigo == 1:
            caidas += 1
        else:
            detalle.append('%s: NO HA CAIDO (codigo %d, %s)'
                           % (nombre, codigo,
                              ep.QUE_SIGNIFICA.get(codigo, '?')))
    # Y antes de mirar el recuento: todo lo que se ha escrito, probado.
    # En un bucle, y el fallo tiene que decir CUAL de los tres.
    # Y ANTES de mirar pendientes, que se ha registrado algo.
    #
    # Sin esta linea, «nada pendiente» no significa NADA: un `sin_probar()`
    # vacio es lo mismo cuando todo lo escrito llego a un test y cuando este
    # test ha dejado de escribir por la puerta. Y esa segunda es el fallo del
    # bloque anterior, un nivel mas abajo.
    #
    # Que es la PRECONDICION de la comprobacion. Y que `Registrado()` exista y
    # no lo use nadie seria un mecanismo decorativo: uno que solo existe para
    # que una prueba lo mire.
    assert ep.Registrado(), (
        'este test dice que no queda nada sin probar, pero no ha registrado '
        'NADA. O no escribio ninguna mutacion —y entonces no tiene nada que '
        'probar—, o la escribio por la puerta equivocada, y en ese caso su '
        '`sin_probar()` no dice nada')
    pendientes = ep.sin_probar()
    assert not pendientes, (
        'de los %d casos, estos no han llegado a ningun test:\n%s'
        % (len(ROTURAS),
           chr(10).join('   - %s' % que for que, _ in pendientes)))
    assert caidas == len(ROTURAS), (
        'de los %d casos de rotura han caído %d:\\n   %s\\n\\nEl umbral es '
        '%d de %d, y no %d. Un umbral por debajo del numero de casos acepta '
        'el defecto en vez de señalarlo.'
        % (len(ROTURAS), caidas, '\n   '.join(detalle),
           len(ROTURAS), len(ROTURAS), caidas - 1))


# ==================== y el limite, que R2 pide que este declarado
def test_el_limite_de_cobertura_esta_escrito_aqui():
    """R2, punto 4: el escaner comprueba cadenas en UN documento. Eso no es
    una garantia general.

    Y el limite tiene que estar ESCRITO en este fichero, porque este
    fichero es el que dice «estos tests son sensibles». Si el limite se queda
    solo en el comentario de otro fichero, aqui se leeria mas cobertura de la
    que tiene."""
    fuente = io.open(os.path.abspath(__file__), encoding='utf-8').read()
    assert 'proteccion especifica' in fuente.lower() or \
        'especifico' in fuente.lower() or \
        'un documento' in fuente.lower(), (
        'este fichero no declara que su alcance es UN documento concreto')
    # Y el limite tiene que estar JUNTO al test que afirma la sensibilidad, no
    # en el comentario de cabecera. Una version anterior lo buscaba 2500
    # caracteres ANTES del def —o sea, en el sitio equivocado— y por eso el
    # limite, que estaba en el docstring de la funcion, no lo encontraba.
    #
    # Y esa es la misma clase de error de la ventana de 1400 caracteres: mirar
    # en un lado cuando el texto esta en el otro.
    i = fuente.find('def test_el_fichero_de_aceptacion_falla_si_se_rompe')
    assert i > 0
    cuerpo = fuente[i:i + 2200]
    assert ('documento' in cuerpo and
            ('concreto' in cuerpo or 'especifico' in cuerpo
             or 'UN fichero' in cuerpo)), (
        'el limite no esta en el cuerpo del test que afirma la '
        'sensibilidad, y un limite lejos no se lee')


# ==================== y la estrategia textual, que R2 tambien senala
def test_la_orbita_aguanta_las_cuatro_variantes_documentadas():
    """Las CUATRA, y construidas con las cadenas que el docstring declara.

    R2 lo senalo:

        la documentacion enumera cuatro variantes, pero los casos
        construidos no reproducen exactamente las cuatro

    Y tiene razon: las construidas eran cuatro CIERRES sueltos, no las cuatro
    frases. Un test que dice «cuatro variantes» y prueba cuatro cadenas que no
    son las documentadas esta probando algo, y no es lo que dice que prueba.

    Y faltaba la cuarta de verdad: la SIN marcado Markdown, que no estaba
    representada en absoluto.

    O sea: un caso de formato que no se cubre es un caso que nadie sabe que
    existe. Y el de la sin marcado es el mas comun.
    """
    from test_causa_no_validez import _orbita_de_la_tesis

    # (nombre, texto completo de la frase, polaridad que debe verse)
    VARIANTES = (
        ('punto y prosa seguida',
         '**El filtro es el CORRECTO.** Eso **no** esta demostrado', 'no'),
        ('punto, thesis sola',
         '**El filtro es el CORRECTO**.\nEso **no** esta demostrado', 'no'),
        ('raya, misma frase',
         '**El filtro es el CORRECTO** - Eso **no** esta demostrado', 'no'),
        ('sin marcado',
         'El filtro es el CORRECTO. Eso **no** esta demostrado', 'no'),
        ('punto y cola larga',
         '**El filtro es el CORRECTO.** Eso **no** esta demostrado, y no lo '
         'puede estar con esta prueba.', 'no'),
        ('con la polaridad al reves, para el contraste',
         '**El filtro es el CORRECTO.** Eso **si** esta demostrado', 'si'),
    )

    malas = []
    for nombre, frase, debe in VARIANTES:
        texto = ('relleno\n\n'
                 '### 4.3 Y lo que esta prueba NO demuestra\n\n'
                 '%s, y sigue.\n' % frase)
        orb = _orbita_de_la_tesis(texto.lower())
        if not orb:
            malas.append('%s: orbita vacia' % nombre)
        elif debe == 'no' and 'no' not in orb:
            malas.append('%s: la orbita no lleva la polaridad -> %r'
                        % (nombre, orb))
        elif debe == 'si' and 'no' in orb:
            malas.append('%s: la orbita dice «no» donde decia «si» -> %r'
                        % (nombre, orb))
    assert not malas, (
        'la orbita falla en estos formatos, que son todos legitimos:\n   '
        + '\n   '.join(malas))


def test_si_la_negacion_esta_en_otro_parrafo_no_se_le_atribuye():
    """LA FRONTERA ES EL PARRAFO. Y el codigo ya lo hacia bien: lo que estaba
    mal era este docstring, que decia otra cosa.

    LA REGLA, y por que es el parrafo y no el punto

    El documento real escribe:

        **El filtro es el CORRECTO.** Eso **no** esta demostrado, y no lo
        puede estar con esta prueba.

    con un PUNTO entre la tesis y su negacion. Y esta bien escrito.

      - Si la frontera fuera el PUNTO, ese documento —el bueno— dejaria de
        ser detectable. Una frase puede llevar punto sin cambiar de oracion
        que la quiero.

      - Y al reves: con el punto, CUALQUIER frase con «no» del parrafo
        siguiente contaria como negacion de la tesis. Eso es un falso positivo
        esperando, y este bloque lleva veintiseis rondas quitandolos.

    O sea: el parrafo es el punto en el que un lector deja de leer «esto
    corrige lo de arriba» y empieza a leer «esto es otra cosa». Por debajo del
    parrafo todo es ruido.

    Y MEDIDO, con saltos de verdad

        punto + salto simple     la polaridad se le atribuye
        punto + PARRAFO          orbita vacia
        sin punto + salto simple la polaridad se le atribuye
        sin punto + PARRAFO      orbita vacia

    Con chr(10), y NO con barras invertidas en el literal: una medicion
    anterior de este bloque las uso, y a traves de un heredoc producen
    caracteres `\` y `n` en vez de saltos. Se probo `\` `n` `\` `n`, que no es
    un parrafo, y salio que el parrafo SI propagaba.

    Y LO QUE NO SE HACE CON ESTE CASO: no se tolera

    El test de aceptacion exige `assert orb`, o sea que una negacion en
    parrafo separado no la deja pasar: falla, diciendo que la negacion tiene
    que estar pegada a la tesis.

    Un caso raro TOLERADO en silencio es un caso que nadie sabe que existe.
    Un caso raro que falla diciendo por que, se puede arreglar.
    """
    from test_causa_no_validez import _orbita_de_la_tesis
    NL = chr(10)                    # y NO barras invertidas: ver arriba
    texto = ('relleno' + NL + NL +
             '### 4.3 Y lo que esta prueba NO demuestra' + NL + NL +
             '**El filtro es el CORRECTO**.' + NL + NL +
             'Eso **no** esta demostrado.' + NL)
    orb = _orbita_de_la_tesis(texto.lower())
    assert not orb or 'no' not in orb, (
        'la orbita ha cogido una negacion que NO es de la tesis. Y si lo '
        'hace, dos afirmaciones incompatibles pasan por una sola comprobacion. '
        'Orbita: %r' % orb)

# ================ Y LA FRONTERA, QUE NO ES UNA ROTURA MAS
def test_la_aceptacion_rechaza_la_negacion_en_otro_parrafo():
    """La SEGUNDA mitad de la frontera, y no es un caso mas de los tres.

    El otro test de la frontera —`..._en_otro_parrafo_no_se_le_atribuye`—
    mira el HELPER: comprueba que la orbita se vacia. Y eso es una prueba
    unitaria correcta, y R2 tiene razon en que no demuestra lo que el
    docstring del helper afirma.

    Que es: que el TEST DE ACEPTACION rechaza ese texto. El helper no es el
    objeto que tiene que caer; el objeto es el fichero de aceptacion, que
    tiene mas comprobaciones y podria tener alguna que siga dando verde.

    Y es el MISMO fallo que el de `test_tareas_r1.py`, con distinta ropa: un
    docstring que afirma algo cierto que nadie ha comprobado, y un comentario
    de doce lineas sobre una funcion que no llamaba a nada.

    MEDIDO, antes de escribir este test:

        documento con la negacion en OTRO PARRAFO
        -> assert ''
        -> AssertionError: no se encuentra la orbita de la tesis
        -> FAILED ...::test_la_tesis_de_no_validez_se_afirma_como_no_demostrada

    O sea que cae por `assert orb`, que es exactamente lo que dice el
    docstring. Y ahora esta comprobado, que es lo que no estaba.

    Y POR QUE NO ES UNA CUARTA ROTURA DE LAS TRES

    Los tres casos de `ROTURAS` miden SENSIBILIDAD —¿el escaner detecta
    estas tres contradicciones concretas?— y el umbral del test que los
    cuenta es `len(ROTURAS)`. Anadir un caso sube un numero declarado que
    este bloque no toca sin motivo, y ademas mezcla dos preguntas: que el
    escaner sea sensible, y que la negacion tenga que ir pegada a la tesis.

    Y la segunda no la responde el escaner. La responde el fichero de
    aceptacion, y es la que se comprueba aqui."""
    texto = ('**El filtro es el CORRECTO.** Eso **no** está demostrado')
    partido = ('**El filtro es el CORRECTO.**' + chr(10) + chr(10)
               + 'Eso **no** está demostrado')
    destino = _docs_rotos(texto, partido, nombre='la negacion en otro parrafo')
    if destino is None:
        pytest.skip('el texto %r no esta en el documento' % texto)
    try:
        env = dict(os.environ)
        env[rs.DIR_DE_DOCUMENTOS] = destino
        env['PYTHONPATH'] = os.path.join(ROOT, 'tools')
        ep.afirmar_caida(
            FICHERO_DE_ACEPTACION,
            'test_la_tesis_de_no_validez_se_afirma_como_no_demostrada',
            env=env, cwd=ROOT,
            cuando='la negacion en OTRO PARRAFO no la ha hecho fallar el '
                    'test de aceptacion. O sea que la frontera NO esta en el '
                    'sitio que dice el docstring, y un documento puede '
                    'afirmar una cosa y corregirla en la siguiente sin que '
                    'nadie lo note.')
    finally:
        shutil.rmtree(os.path.dirname(destino), ignore_errors=True)
