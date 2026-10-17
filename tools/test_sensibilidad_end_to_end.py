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


def _docs_rotos(viejo, nuevo, todas=True):
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
    with io.open(ruta, 'w', encoding='utf-8', newline='') as f:
        f.write(cambiado)
    return destino


def _ejecutar_aceptacion(docs_dir):
    """El exit code de pytest sobre el fichero de aceptacion."""
    env = dict(os.environ)
    env[rs.DIR_DE_DOCUMENTOS] = docs_dir
    env['PYTHONPATH'] = os.path.join(ROOT, 'tools')
    r = subprocess.run(
        [sys.executable, '-m', 'pytest', FICHERO_DE_ACEPTACION, '-q',
         '--no-header', '-p', 'no:cacheprovider'],
        cwd=ROOT, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    return r.returncode, r.stdout.decode('utf-8', 'replace')


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
    destino = _docs_rotos(viejo, nuevo)
    if destino is None:
        pytest.skip('el texto %r no esta en el documento: hay que '
                    'actualizar este test, que es lo que comprueba' % viejo)
    try:
        codigo, salida = _ejecutar_aceptacion(destino)
        assert codigo != 0, (
            'EL FICHERO DE ACEPTACION NO HA CAIDO con la rotura «%s».\n'
            'Es decir: %s\n\nY eso significa que el test de aceptacion tiene '
            'otra comprobacion que sigue dando verde, y que este fichero '
            'NO protege esa relacion. R2 lo dijo: un test de aceptacion '
            'puede seguir pasando por otra ruta.\n\nSalida:\n%s'
            % (nombre, por_que, salida[-1500:]))
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
        destino = _docs_rotos(viejo, nuevo)
        if destino is None:
            detalle.append('%s: el texto no esta, no se puede comprobar'
                           % nombre)
            continue
        try:
            codigo, _salida = _ejecutar_aceptacion(destino)
        finally:
            shutil.rmtree(os.path.dirname(destino), ignore_errors=True)
        if codigo != 0:
            caidas += 1
        else:
            detalle.append('%s: NO HA CAIDO' % nombre)
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


def test_si_un_punto_separa_la_tesis_de_su_negacion_no_se_vigila():
    """Y el caso que NO tiene que funcionar, porque no es un formato: es otro
    documento.

        **El filtro es el CORRECTO.**
        Eso **no** esta demostrado.

    Si el punto cierra la frase de la tesis, la negacion ya no es de la
    tesis: es de otra cosa. Y entonces el documento AFIRMA la tesis y NIEGA
    algo mas, que es exactamente la contradiccion 200/238 en otra forma — dos
    afirmaciones que se parecen y no son la misma.

    Y por eso merece su propio test y no una variante mas: un formato
    ilegitimo que la orbita no cubre no es un fallo de la orbita, es una
    cosa que el documento no deberia escribir. Y hay que poder decir eso.

    O sea: la orbita es deliberadamente ESTRICTA, y esto es lo que declara su
    limite. Un filtro laxo que aceptara este caso no detectaria el
    documento que separa la tesis de su negacion."""
    from test_causa_no_validez import _orbita_de_la_tesis
    texto = ('relleno\n\n'
             '### 4.3 Y lo que esta prueba NO demuestra\n\n'
             '**El filtro es el CORRECTO**.\n\n'
             'Eso **no** esta demostrado.\n')
    orb = _orbita_de_la_tesis(texto.lower())
    assert not orb or 'no' not in orb, (
        'la orbita ha cogido una negacion que NO es de la tesis. Y si lo '
        'hace, dos afirmaciones incompatibles pasan por una sola comprobacion. '
        'Orbita: %r' % orb)
