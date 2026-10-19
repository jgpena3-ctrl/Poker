# -*- coding: utf-8 -*-
"""R1 tarea 6: INC-004 tiene que seguir VISIBLE, y ahora CERRADO.

Y «visible» quiere decir lo mismo que cuando estaba abierto, con la palabra
cambiada: un incidente cerrado que no se puede leer es un incidente que se
vuelve a abrir, y un incidente cerrado en el que el invariante se ha
relajado es un incidente que se ha tapado.

Lo que este fichero comprueba, y son cuatro cosas distintas:

  1. QUE EL INVARIANTE SIGUE VIVO. No se ha relajado la regla para poner el
     test en verde. Y eso se comprueba con un caso INVENTADO: una mano con una
     `BB b` despues de una accion voluntaria tiene que seguir siendo un
     defecto. Si la regla se relajase, este test falla; y si la regla se
     borrase, tambien.

  2. QUE EL DATO ESTA CORREGIDO. El defecto es cero en toda la base, y no
     solo en la mano que lo tenia.

  3. QUE LA MANO NO ESTABA EN LA VENTANA. Que ninguna cifra publicada se
     moviera es la MEDICION que hace legitimo el cierre, y por eso se
     comprueba: sin ella, «cerrado» seria una afirmacion.

  4. QUE EL CIERRE ESTA ESCRITO. Que se pueda leer quien lo cerro, con que
     numeros y por que rama de la decision. Y que el manifiesto y el
     documento canonico digan lo mismo que el codigo.

Y lo que NO comprueba, y conviene decir: que la mano «se corrigiera bien». Lo
que se sabe es que el invariante se cumple y que el reparto de la mano cuadra
con la secuencia. Que sea lo que el mantenedor quiso decir es de el, y esta
la decision.
"""
import hashlib
import io
import os
import subprocess
import sys

import ejecutar_pytest as ep  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor import learn  # noqa: E402

TEST = os.path.join(ROOT, 'motor', 'test_cm004.py')
DOC = os.path.join(ROOT, 'DOCS', 'INC-004_H_1196.md')
CANONICO = os.path.join(ROOT, 'DOCS', 'CANAL_MANUAL_CERRADO.md')
ALVADO = 'test_ninguna_mano_tiene_una_bb_b_que_no_pueda_ser_la_ciega'


def _git(*args):
    return subprocess.run(['git'] + list(args), cwd=ROOT,
                          capture_output=True).stdout.decode('utf-8')


def _doc():
    with io.open(DOC, encoding='utf-8') as f:
        return f.read()


# --- 1. el invariante sigue vivo -------------------------------------------

def test_el_invariante_sigue_vivo_con_un_caso_inventado():
    """La regla NO se ha relajado. Y con un caso que nadie tiene que mirar.

    MEDIDO, por que hace falta un caso: la base ya no tiene ninguna mano que
    viole el invariante, de modo que el test de la base pasaria con CUALQUIER
    regla —incluida una que no mirase nada—. Eso es «hoy no pasa», y un
    invariante que solo se puede comprobar con un caso inventado es un
    invariante que se puede romper sin que nadie lo note.

    Y el caso es el mas minimo: una `BB b` despues de una accion voluntaria.
    """
    mano = {
        'hand_id': 'X',
        'players': [{'pos': 'BB', 'active': True},
                    {'pos': 'CO', 'active': True}],
        'streets': {'preflop': {'actions': [
            {'pos': 'BB', 'action': 'b', 'amount': 0.5},
            {'pos': 'CO', 'action': 'c', 'amount': 1.0},
            {'pos': 'BB', 'action': 'b', 'amount': 2.0},
        ]}},
    }
    assert learn.defecto_orden_ciega_bb(mano), (
        'una `BB b` despues de una accion voluntaria tiene que ser un defecto, '
        'y no lo es. O sea que el invariante se ha relajado, o se ha borrado.')

    # Y la misma mano con la subida GRABADA COMO `r` no es un defecto: que es
    # justo la diferencia entre el dato que habia y el dato que hay.
    mano_r = {
        'hand_id': 'X',
        'players': [{'pos': 'BB', 'active': True},
                    {'pos': 'CO', 'active': True}],
        'streets': {'preflop': {'actions': [
            {'pos': 'BB', 'action': 'b', 'amount': 0.5},
            {'pos': 'CO', 'action': 'c', 'amount': 1.0},
            {'pos': 'BB', 'action': 'r', 'amount': 2.0},
        ]}},
    }
    assert not learn.defecto_orden_ciega_bb(mano_r), (
        'una `BB r` no puede ser la ciega: la regla exige `act == "b"`, y una '
        'subida bien grabada nunca se lee como ciega. Y esto falla, o sea que '
        'la regla ha cambiado.')


def test_el_test_de_cm004_sigue_en_la_suite_y_no_esta_silenciado():
    """No se ha puesto un `xfail` ni un `skip`, y el test sigue ahi.

    Y que ademas PASE de verdad, y no por una marca: se ejecuta.
    """
    with io.open(TEST, encoding='utf-8') as f:
        s = f.read()
    i = s.index('def ' + ALVADO)
    arriba = s[:i].rsplit('\n\n', 1)[-1]
    for marca in ('xfail', 'skip'):
        assert marca not in arriba, (
            'el test tiene %r encima: un %s puesto para que la suite salga '
            'verde es perdida de informacion' % (marca, marca))
    cuerpo = s[i:i + 1200]
    assert 'pytest.skip' not in cuerpo
    assert 'pytest.xfail' not in cuerpo

    # Y que pase DE VERDAD, ejecutandolo. Por `ejecutar_pytest`, y no con un
    # `subprocess.run` propio: la puerta comun corta el 4 y el 5, que son
    # «no se ha ejecutado nada».
    ep.afirmar_verde(TEST, ALVADO, cwd=ROOT,
                     extra=('-x',))


# --- 2. el dato esta corregido ----------------------------------------------

def test_el_defecto_es_cero_en_toda_la_base():
    """No solo en la mano que lo tenia: en las 1258.

    Y esta es la repasa que pedia el expediente: «se repasa si hay mas manos
    con el mismo defecto». La repasa se HACE y sale cero.
    """
    manos = learn.load_hands(reliable_only=False)
    assert learn.manos_con_orden_ciega_malo(manos) == [], (
        'la violacion de CM-004 es cero en toda la base, y no lo es. Si vuelve '
        'a aparecer, la correccion de `H_1196` no era la unica.')


# --- 3. ninguna cifra publicada se movio -----------------------------------

def test_la_mano_no_esta_en_la_ventana_fiable():
    """Lo que hace legitimo el cierre: que la mano corregida NO estaba dentro
    de la ventana de calibracion.

    MEDIDO: `H_1196` esta en la linea 1172 de 1258, y la ventana fiable corta
    en la linea `RELIABLE_HANDS`. O sea que es POSTERIOR a la ventana.

    Y por que esto es un TEST y no una nota: sin el, «cerrado» seria una
    afirmacion. Y una afirmacion sobre si el cierre mueve las cifras es
    justamente la que no se puede fiscalizar.
    """
    manos = learn.load_hands(reliable_only=False)
    posiciones = [i for i, h in enumerate(manos, 1)
                  if h.get('hand_id') == 'H_1196']
    assert posiciones, 'H_1196 no esta en la base'
    linea = posiciones[0]
    assert linea > learn.RELIABLE_HANDS, (
        'H_1196 esta en la linea %d, y la ventana fiable corta en la %d. O sea '
        'que la mano esta DENTRO de la ventana, y entonces el cierre mueve '
        'cifras publicadas y hay que rehacerlas.'
        % (linea, learn.RELIABLE_HANDS))

    # Y que tampoco esta en la lista de exclusiones: una mano excluida sigue
    # fuera de la ventana, pero por otra razon, y la confusion de esas dos
    # cosas es la que hace que un numero parezca otro.
    assert 'H_1196' not in learn.manos_excluidas(), (
        'H_1196 esta en la lista de exclusiones de la ventana. O sea que la '
        'mano no estaba en la ventana por la lista, y no por su linea, y eso '
        'cambia el motivo por el que no cuenta.')


# --- 4. el cierre esta escrito ----------------------------------------------

def test_el_documento_declara_una_sola_vez_el_estado_y_dice_cerrado():
    """UNA declaracion de estado, y que diga CERRADO.

    Y no se buscan palabras sueltas: lo que se comprueba es la DECLARACION,
    que es la unica linea que cambia cuando algo se cierra.
    """
    doc = _doc()
    declaracion = [l for l in doc.split('\n') if 'ESTADO:' in l.upper()]
    assert len(declaracion) == 1, (
        'tiene que haber UNA declaracion de estado, y no %d: %r'
        % (len(declaracion), declaracion))
    assert 'CERRADO' in declaracion[0].upper(), (
        'y tiene que decir CERRADO: %r' % declaracion[0])
    assert 'ABIERTO' not in doc.upper(), (
        'el documento dice ABIERTO en algun sitio, y ya no es verdad.')


def test_el_documento_dice_que_rama_de_la_decision_se_tomo():
    """La decision era de dos caras, y el cierre dice cual.

    Y por que tiene que decir cual, y no solo «cerrado»: las dos ramas tenian
    consecuencias distintas, y una de ellas era cambiar el invariante. Un
    cierre que no dice la rama no dice si el invariante se toco.
    """
    doc = _doc()
    baja = doc.lower()
    assert 'el registro' in baja, 'que la decision habla del registro'
    assert 'rama' in baja or 'cara' in baja, 'y que dice que rama se tomo'
    assert 'r`' in baja or "'r'" in baja, (
        'y que dice la correccion concreta, que es grabarlo como `r`')
    # Y que el invariante NO se ha relajado, dicho en el documento.
    assert 'invariante' in baja, 'y que habla del invariante'


def test_el_expediente_no_se_ha_borrado():
    """El `.md` sigue aqui, con el sintoma, la decision y las mediciones.

    Y esto es lo que distingue un incidente cerrado de un incidente perdido.
    """
    doc = _doc()
    for trozo in ('H_1196', 'CM-004', 'BB', '12c7bed'):
        assert trozo in doc, (
            'el expediente ha perdido la parte de «%s». Un incidente cerrado que '
            'no se puede leer es un incidente que se vuelve a abrir.' % trozo)


def test_el_manifiesto_y_el_documento_canonico_dicen_lo_mismo():
    """El hash y el commit de la base, en el codigo y en el documento.

    Y la razon por la que el documento tiene que decir el hash: un hash
    declarado sin documento es una afirmacion sin respaldo, y un documento
    sin hash es una descripcion de otra base.
    """
    canonico = io.open(CANONICO, encoding='utf-8').read()
    assert learn.HANDS_DB_SHA256[:16] in canonico, (
        'el documento canonico no menciona el hash vigente (%s)'
        % learn.HANDS_DB_SHA256[:16])
    assert learn.HANDS_DB_COMMIT[:7] in canonico, (
        'el documento canonico no menciona el commit vigente (%s)'
        % learn.HANDS_DB_COMMIT[:7])
    assert str(learn.HANDS_DB_LINEAS) in canonico, (
        'y tampoco el numero de manos')


def test_el_fichero_esta_commiteado_y_su_manifiesto_es_el_declarado():
    """La base esta commiteada, y el hash declarado es el del BLOB.

    Y el blob, y no el fichero suelto: porque el guard tiene que poder
    distinguir «el fichero que esta en el disco» de «el fichero que esta en
    el repositorio», y si no, un cambio sin commitear pasa por declaracion.
    """
    sucios = [l for l in _git('status', '--porcelain', '--', 'data/').split('\n')
              if l.strip()]
    assert not sucios, (
        'data/ tiene cambios SIN COMMITEAR: %r. El canal manual esta cerrado.'
        % sucios)
    ultimo = _git('log', '-1', '--format=%H', '--', 'data/hands_db.jsonl').strip()
    assert ultimo, 'data/hands_db.jsonl no tiene ningun commit'
    crudo = subprocess.run(
        ['git', 'show', '%s:data/hands_db.jsonl' % ultimo],
        cwd=ROOT, capture_output=True).stdout
    real = hashlib.sha256(crudo).hexdigest()
    assert real == learn.HANDS_DB_SHA256, (
        'el ultimo commit que toco la base (%s) tiene sha256 %s y el declarado '
        'es %s.' % (ultimo[:8], real[:16], learn.HANDS_DB_SHA256[:16]))
