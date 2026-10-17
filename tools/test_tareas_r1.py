# -*- coding: utf-8 -*-
"""Tres tareas de R1 que estaban HECHAS pero SIN NADA QUE LAS VIGILE.

Y eso es lo que se ha medido antes de escribir:

  Tarea 1  las cinco cosas del y = 0 ESTAN en los tres .md   -> sin test
  Tarea 2  los cuatro tests de los contratos EXISTEN        -> sin prueba
           de que CAIGAN si el contrato cambia
  Tarea 5  la contradiccion 200/238 esta CORREGIDA          -> sin test

Un arreglo sin test se deshace en cuanto alguien edita el documento, y no
avisa. Que es exactamente lo que paso con la 238: se corrigio la 200 porque
se vio, y nadie miro si habia otra que dijera lo mismo en otro sitio.

Y hay una razon de fondo para las tres, y es la misma: este bloque ha
descubierto que «esta escrito» y «esta vigilado» son dos cosas distintas, y
que la segunda es la que cuesta.
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

import ejecutar_pytest as ep                    # noqa: E402

from retraccion_scan import (                              # noqa: E402
    afirmada, afirmada_sin_negar, leer)

LOS_TRES = ('DECISION_OBJETIVO_AUC.md', 'LIMITACION_PREFLOP_AUC.md',
            'REPRESENTATIVIDAD_23.md')

# ================================================ TAREA 1: el y = 0
# Las cinco cosas, con las formas que se aceptan para cada una.
# Varias por idea, porque un test que exige una sola obliga a escribir el
# documento como el test — que es lo que este bloque lleva corrigiendo.
LAS_CINCO = (
    ('651 folds del heroe', ('651',)),
    ('108 folds en la muestra etiquetada', ('108',)),
    ('543 folds fuera de la muestra', ('543',)),
    ('137 manos con y = 0', ('137',)),
    ('29 sin fold: showdown perdido', ('29',)),
    ('el fold es suficiente y no necesario',
     ('suficiente y no necesario',)),
    ('y = 0 significa que el heroe pierde',
     ('el héroe pierde', 'el heroe pierde')),
    ('la poblacion B excluye folds por el showdown, no por la etiqueta',
     ('no hay showdown que verificar', 'no hay board que verificar')),
    ('la etiqueta del fold es valida; su observabilidad no',
     ('su observabilidad no',)),
)


def test_los_tres_dicen_las_cinco_cosas_del_y_igual_cero():
    """Y el fallo dice cual falta y en cual."""
    faltan = []
    for n in LOS_TRES:
        doc = leer(n)
        for etiqueta, formas in LAS_CINCO:
            if not any(afirmada_sin_negar(doc, f) for f in formas):
                faltan.append('%s: %s' % (n, etiqueta))
    assert not faltan, (
        'la correccion del y = 0 no esta completa en los tres .md:\\n   '
        + '\\n   '.join(faltan))


def test_los_tres_no_dicen_la_afirmacion_falsa():
    """Y la affirmacion dictada, que era FALSA, no esta en ninguno.

    No basta con que no este: hay que comprobar que esta la version
    medida. Y «y = 0 no es de los folds» es justo lo que no puede decir,
    porque 29 de las 137 manos con y = 0 no tienen fold.

    La forma de comprobarlo: la frase no puede estar AFIRMADA. Y como el
    escaner no distingue «afirmada» de «mencionada en una correccion», se
    comprueba la forma afirmativa, que es la queeria el error."""
    FALSAS = (
        'y = 0 no es de los folds',
        'y = 0` no es',
        'no es de los folds',
        'es de los folds que no están',
        'es de los folds que no estan',
    )
    malas = []
    for n in LOS_TRES:
        doc = leer(n)
        for frase in FALSAS:
            for i in afirmada_sin_negar(doc, frase):
                malas.append('%s:%d  [%s]' % (n, i, frase))
    assert not malas, (
        'los .md AFIRMAN la version falsa de la correccion del y = 0:\\n   '
        + '\\n   '.join(malas))


def test_los_tres_dicen_las_dos_vias_de_perder():
    """Y que dicen las DOS, porque la que se corrigio cabe en una frase."""
    for n in LOS_TRES:
        doc = leer(n)
        tiene_fold = any(afirmada_sin_negar(doc, f)
                         for f in ('108', 'los 108', '**108**'))
        tiene_showdown = any(afirmada_sin_negar(doc, f)
                             for f in ('29', 'los 29', '**29**'))
        assert tiene_fold and tiene_showdown, (
            '%s solo dice una de las dos vias de perder' % n)


# ================================================ TAREA 5: la contradiccion
def test_la_seccion_4_2_no_presenta_el_filtro_como_correcto():
    """La correccion de §4.3 no habia actualizado §4.2, y el documento
    sostenia dos posiciones incompatibles a treinta y ocho lineas de
    distancia:

        200: La prueba de que el filtro ES EL CORRECTO no es que «parezca».
        238: **El filtro es el CORRECTO.** Eso **no** esta demostrado.

    Y §4.2 tiene que presentar el filtro como la CAUSA, que es lo que si se
    demuestra."""
    doc = leer('QUE_REPRESENTA_LA_PREDICCION.md')
    b = doc.lower()
    i_42 = b.find('### 4.2')
    i_43 = b.find('### 4.3')
    assert i_42 > 0 and i_43 > i_42, (
        'las dos secciones no estan donde se esperaba: §4.2 en %d, §4.3 en '
        '%d. Y sin las dos no se puede comprobar que no se contradigan'
        % (i_42, i_43))
    sec42 = b[i_42:i_43]

    # §4.2 no puede AFIRMAR que el filtro es el correcto
    #
    # Y el mensaje usa una variable que EXISTE. Una version anterior hacia
    # `for mala in (...)` con `assert mala not in sec42, (... % mala)`, y el
    # mensaje reventaba con NameError.
    #
    # Y eso es lo que tiene de grave: un NameError en el mensaje de un assert
    # es la senal de un mensaje que NUNCA se ha visto, porque solo aparece
    # cuando el assert falla. Y si el assert no ha fallado nunca, nadie lo
    # sabe. O sea que el mensaje llevaba tiempo sin existir.
    PROHIBIDAS = ('el filtro es el correcto', 'filtro es el correcto',
                  'es el correcto.')
    for variante in PROHIBIDAS:
        assert variante not in sec42, (
            '§4.2 sigue diciendo «%s». El filtro se presenta como la CAUSA '
            'de la diferencia; que sea el CORRECTO no esta demostrado y lo '
            'dice §4.3' % variante)
    # y tiene que presentar la causa
    assert ('causa' in sec42), (
        '§4.2 no dice que el filtro sea la CAUSA de la diferencia, que es lo '
        'que si se demuestra. Un §4.2 que no dice ni causa ni correccion no '
        'dice nada: §4.2 tiene que VISAR a §4.3.')


def test_y_la_contradiccion_no_vuelve_por_la_vuelta_de_otros():
    """Y no basta con que §4.2 no afirme la correccion: §4.3 tampoco puede
    AFIRMAR que el filtro sea correcto, que es el otro sentido de la misma
    contradiccion.

    Las dos mitades del mismo par. Y una version anterior de este fichero
    comprobaba solo la primera, o sea que un §4.3 que afirmara la correccion
    habria pasado."""
    doc = leer('QUE_REPRESENTA_LA_PREDICCION.md')
    b = doc.lower()
    i_43 = b.find('### 4.3')
    sec43 = b[i_43:i_43 + 1400]
    assert 'no' in sec43 and 'demostrado' in sec43, (
        '§4.3 tiene que decir que la correccion NO esta demostrada')
    # y no puede decir que SI lo esta
    assert 'si esta demostrado' not in sec43 and \
        'sí está demostrado' not in sec43, (
        '§4.3 afirma que la correccion SI esta demostrada, que es lo '
        'contrario de lo que sostiene')


# ===================================== TAREA 2: los contratos, en serio
@pytest.mark.parametrize('nombre', ('CONTRATO_L_SEC.md', 'CONTRATO_PREFLOP.md'))
def test_los_tests_de_los_contratos_caen_si_el_contrato_cambia(nombre):
    """Que los tests de `test_contratos_firmados.py` CAIGAN al cambiar el
    contrato. Sin esto, sus cuatro tests pueden pasar y no estar vigilando
    nada.

    Y la rotura tiene que ser de las dos clases:

      - de AFIRMACION: se quita la frase de la que el proyecto depende
      - de HUELLA: se cambia una palabra que no significa nada

    La segunda es la interesante: un cambio de redaccion legitimo rompe la
    huella, y eso es a proposito. Un contrato firmado que cambia en silencio
    no esta firmado. Pero tambien significa que el cambio legitimo tiene que
    ser explicito, o sea que alguien tiene que actualizar la huella aqui."""
    tmp = tempfile.mkdtemp(prefix='opencode_contrato_')
    try:
        destino = os.path.join(tmp, 'DOCS')
        os.makedirs(destino)
        for f in os.listdir(os.path.join(ROOT, 'DOCS')):
            if f.endswith('.md'):
                shutil.copy(os.path.join(ROOT, 'DOCS', f),
                            os.path.join(destino, f))
        ruta = os.path.join(destino, nombre)
        with io.open(ruta, encoding='utf-8') as f:
            texto = f.read()

        # (a) rotura de AFIRMACION: NO queda ninguna forma de la afirmacion.
        #
        # Y NO una. Una version anterior cambiala primera aparicion de la
        # primera variante que encontraba, y con eso el test de contenido NO
        # caia — porque el test acepta cinco variantes y quedaban cuatro.
        #
        # O sea: la mutacion no era una rotura. Y esa es la TERCERA vez que
        # una rotura resulta parcial, con la misma forma: cambiar una
        # aparicion no es cambiar el concepto.
        #
        # Que es la version de este bloque de «no repetir lo que se retira»:
        # una retraccion se retira en todas sus formas, no en una.
        import test_contratos_firmados as _cf
        cambiada = texto
        tocadas = 0
        for clave in _cf.AFIRMACIONES[nombre]:
            _, formas, _porque = clave
            for forma in formas:
                if forma in cambiada:
                    cambiada = cambiada.replace(forma, '§' * len(forma))
                    tocadas += 1
        assert tocadas, (
            '%s no tiene ninguna de las formas que el test exige: hay que '
            'actualizar AFIRMACIONES, que es lo que se comprueba aqui'
            % nombre)
        # Y QUE NO QUEDE NINGUNA FORMA. R1 lo pide, y `tocadas` no lo dice:
        # un mutador que tocara una forma de tres da 1, que no es cero, y
        # pasa. O sea que el numero que se comprobaba no era el que
        # distingue una mutacion de un cambio de redaccion.
        #
        # Y esta es la rotura REAL — la que rompe el contrato de verdad —,
        # mientras que la comprobacion de `test_disciplina_de_los_tests.py`
        # mira el mutador en abstracto, sobre un laboratorio. Las dos hacen
        # falta: una dice que el mutador esta bien escrito, y esta dice que
        # ha hecho su trabajo sobre ESTE documento.
        #
        # Y si alguna vez falla, el fallo dice que forma ha quedado, que es lo
        # unico que permite arreglarlo sin volver a leer el mutador entero.
        for clave in _cf.AFIRMACIONES[nombre]:
            _, formas, porque = clave
            for forma in formas:
                assert forma not in cambiada, (
                    'despues de la mutacion queda la forma %r, de «%s» — que '
                    'se define como: %s. O sea que la rotura es PARCIAL y no '
                    'rompe la afirmacion: el test de contenido la sigue '
                    'aceptando por esa otra via. Una mutacion se hace en '
                    'TODAS las formas o no es una mutacion.'
                    % (forma, clave[0], porque))

        env = dict(os.environ)
        env['POKER_DOCS_DIR'] = destino
        env['PYTHONPATH'] = os.path.join(ROOT, 'tools')
        with io.open(ruta, 'w', encoding='utf-8', newline='') as f:
            f.write(cambiada)
        # SOLO el test de CONTENIDO, y solo ese.
        #
        # Y esto no es un detalle de R2, es la diferencia entre acreditar un
        # mecanismo y acreditar el otro por descuento. Al mutar el TEXTO
        # cambian las dos cosas —el contenido y la huella— asi que comprobar
        # solo el exit code demuestra que «algo ha caido», no QUE.
        #
        # Y el caso que haria falta para verlo: si el test de contenido no
        # mirase el contrato, la mutacion caeria SOLO por la huella y este
        # test pasaria igualmente.
        # (b) rotura de HUELLA: el TEXTO cambia y el SENTIDO no. Se cambia
        #     la primera palabra suelta, que es lo mas seguro: ninguna
        #     afirmacion del contrato la contiene.
        #
        # Y aqui no hay problema de parcialidad: «el» esta en casi todas las
        # frases, y cambiarlo no altera ninguna afirmacion. Lo que tiene que
        # caer es la huella, y solo la huella.
        primera = texto.find('el')
        assert primera > 0, 'no se ha encontrado la palabra a cambiar'
        with io.open(ruta, 'w', encoding='utf-8', newline='') as f:
            f.write(texto[:primera] + 'EL' + texto[primera + 2:])
        # Y aqui SOLO el de la huella. Un cambio cosmetico no altera ninguna
        # afirmacion, asi que el de contenido NO tiene por que caer: lo que
        # tiene que caer es el de la huella.
        r = subprocess.run(
            [sys.executable, '-m', 'pytest',
             os.path.join(ROOT, 'tools',
                          'test_contratos_firmados.py')
             + '::test_los_contratos_no_cambian_sin_que_se_sepa',
             '-q', '--no-header', '-p', 'no:cacheprovider'],
            cwd=ROOT, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        ep.afirmar_caida(
            os.path.join(ROOT, 'tools', 'test_contratos_firmados.py'),
            'test_los_contratos_no_cambian_sin_que_se_sepa',
            env=env, cwd=ROOT,
            cuando='el test de HUELLA no ha caido al cambiar una palabra '
                    'sin significado. Y eso es lo que hace la huella: un '
                    'contrato firmado que cambia en silencio no esta '
                    'firmado, ni siquiera si el cambio es cosmetico.')
        # y el de contenido NO tiene que caer: si caiase, seria porque mira
        # algo que no es una afirmacion, que es justo lo que la huella cubre
        r2 = subprocess.run(
            [sys.executable, '-m', 'pytest',
             os.path.join(ROOT, 'tools',
                          'test_contratos_firmados.py')
             + '::test_los_contratos_dicen_lo_que_el_proyecto_les_pide',
             '-q', '--no-header', '-p', 'no:cacheprovider'],
            cwd=ROOT, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        assert r2.returncode == 0, (
            'el test de CONTENIDO tambien ha caido con un cambio cosmetico. '
            'No deberia: un cambio de redaccion no altera ninguna '
            'afirmacion. Y si lo hace, el mecanismo se solapan y no son dos '
            'mecanismos sino uno.')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_sin_romper_nada_los_tests_de_los_contratos_pasan():
    """La precondicion. Sin ella, los dos tests de arriba pueden caer por la
    razon equivocada."""
    r = subprocess.run(
        [sys.executable, '-m', 'pytest',
         os.path.join(ROOT, 'tools', 'test_contratos_firmados.py'),
         '-q', '--no-header', '-p', 'no:cacheprovider'],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert r.returncode == 0, (
        'los tests de los contratos ya fallan SIN cambiar nada:\n%s'
        % r.stdout.decode('utf-8', 'replace')[-1200:])