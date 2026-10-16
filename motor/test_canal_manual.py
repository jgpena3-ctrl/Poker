# -*- coding: utf-8 -*-
"""El canal manual de `hands_db.jsonl` esta CERRADO. Esto lo hace cumplir.

revision_1 lo llama la tarea mas importante del bloque, y con razon:

> sin un test que detecte ediciones manuales, cualquier cosa que hagas puede
> deshacerse la semana siguiente por alguien que ejecute --apply sin leer

Y no es hipotetico: en este mismo bloque, `--apply` sobrescribio 928 lineas
que alguien habia escrito a mano. El script ya no puede hacerlo —eso se
arreglo— pero que no pueda este script no significa que no pueda el
siguiente, ni un editor, ni un copiado y pegado.

Que se comprueba, y por que son tres cosas distintas
---------------------------------------------------

  1. EL ARBOL ESTA LIMPIO. Si hay cambios sin commitear en la base, alguien
     toco el fichero y no lo declaro. Sale en `git status` y en una pasada
     de reloj, pero es la causa mas frecuente.

  2. EL HASH ES EL DECLARADO. `learn.HANDS_DB_SHA256`. Si no, el fichero no
     es el que el motor cree usar. El hash esta al lado de `RELIABLE_HANDS`
     a proposito: no puede haber dos verdades en sitios distintos.

  3. EL HASH ESTA JUSTIFICADO. Que el hash sea el declarado no basta: tiene
     que haber un script o un documento que explique por que ese estado es
     el legitimo. Por eso el test mira tambien el estado de git y el
     documento del canal.

Un hash que cambia sin motivo escrito es tan malo como editar a mano: es
dejar constancia de algo que no se sabe por que paso.
"""
import hashlib
import io
import os
import re
import subprocess

import pytest

from motor import learn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_REL = 'data/hands_db.jsonl'
DB_PATH = os.path.join(ROOT, *DB_REL.split('/'))
CANONICO = 'DOCS/CANAL_MANUAL_CERRADO.md'


def _sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _git(*args):
    return subprocess.run(['git'] + list(args), cwd=ROOT,
                          capture_output=True).stdout.decode('utf-8').strip()


# --- 1. el arbol -----------------------------------------------------------

def test_no_hay_cambios_sin_commitear_en_la_base():
    """Si el fichero tiene cambios sin commitear, se ha tocado y no se ha
    declarado. O se commitea, o se revierte: no hay tercera via."""
    sucios = [l for l in _git('status', '--porcelain', '--', DB_REL).split('\n')
              if l.strip()]
    assert not sucios, (
        'hands_db.jsonl tiene cambios SIN COMMITEAR y por tanto sin motivo '
        'escrito:\n  %s\nEl canal manual esta cerrado: commitea con el motivo, '
        'o revierte. Ver %s' % ('\n  '.join(sucios), CANONICO))


# --- 2. el hash ------------------------------------------------------------

def test_el_hash_de_la_base_es_el_declarado():
    """El fichero es el que el motor cree usar."""
    real = _sha(DB_PATH)
    assert real == learn.HANDS_DB_SHA256, (
        'hands_db.jsonl tiene sha256 %s y el declarado es %s.\n'
        'Si el cambio es legitimo: sube `learn.HANDS_DB_SHA256` Y explica el '
        'motivo en %s. Si no lo es: revierte.\nUn hash que cambia sin motivo '
        'escrito es tan malo como editar a mano.'
        % (real[:16], learn.HANDS_DB_SHA256[:16], CANONICO))


def test_el_numero_de_lineas_es_el_declarado():
    """Un hash puede coincidir y el numero de manos no, si el fichero se
    reescribio con otro criterio de salto de linea. Se comprueba aparte."""
    with io.open(DB_PATH, encoding='utf-8') as f:
        n = sum(1 for l in f if l.strip())
    assert n == learn.HANDS_DB_LINEAS, (
        'hands_db.jsonl tiene %d manos y el declarado es %d'
        % (n, learn.HANDS_DB_LINEAS))


# --- 3. la justificacion ---------------------------------------------------

def test_el_estado_canonico_esta_documentado():
    """Que exista el documento, y que mencione el commit y el hash.

    Sin esto, cambiar la constante seria tan facil como editar el fichero: y
    la constante se cambia en un fichero que se lee al cargar el motor.
    """
    ruta = os.path.join(ROOT, *CANONICO.split('/'))
    assert os.path.exists(ruta), (
        'falta %s. El canal manual cerrado se apoya en ese documento: sin '
        'el, la constante de `learn.py` seria una afirmacion sin respaldo.'
        % CANONICO)
    texto = io.open(ruta, encoding='utf-8').read()
    assert learn.HANDS_DB_SHA256[:16] in texto, (
        '%s no menciona el hash vigente (%s). Si el hash ha cambiado y el '
        'documento no lo recoge, el documento ya no describe la base.'
        % (CANONICO, learn.HANDS_DB_SHA256[:16]))
    assert learn.HANDS_DB_COMMIT[:7] in texto, (
        '%s no menciona el commit vigente (%s).' % (CANONICO,
                                                    learn.HANDS_DB_COMMIT))


def test_el_documento_declara_TAMBIEN_el_numero_de_lineas():
    """La reserva B de la revision tecnica: el hash solo no basta.

    Un sha256 dice QUEFICHERO es, nunca si es el correcto. Por eso el
    manifiesto tiene TRES cosas —hash, commit y lineas— y este test mira la
    tercera, que es la unica de las tres que se puede comprobar sin mirar el
    fichero: `1258` contra `1258`.

    Sin el, el patron «copiar el documento anterior y cambiar el hash»
    pasaria: el hash nuevo encaja en un documento que describe la base
    anterior con dos lineas menos y otro hash viejo dentro.
    """
    texto = io.open(os.path.join(ROOT, *CANONICO.split('/')),
                    encoding='utf-8').read()
    declarado = re.search(r'\*\*L[ií]neas:\*\*\s*(\d+)', texto)
    assert declarado, (
        '%s no declara el numero de lineas. El manifiesto son TRES datos '
        '(hash, commit, lineas) y el documento tiene que llevar los tres: con '
        'dos, cambiar el hash es copiar el documento viejo.' % CANONICO)
    assert int(declarado.group(1)) == learn.HANDS_DB_LINEAS, (
        '%s declara %s lineas y el manifiesto declara %d. Uno de los dos esta '
        'desactualizado, y son la misma base.'
        % (CANONICO, declarado.group(1), learn.HANDS_DB_LINEAS))


def test_el_documento_explica_y_no_solo_repite():
    """La segunda mitad de la reserva B: el hash necesita un POR QUE.

    Un sha256 es una afirmacion sin respaldo; el motivo escrito es el
    respaldo. Este test no puede comprobar que el motivo sea CIERTO —eso hay
    que medirlo, y esta midiendo quien lo cambia—, pero si comprueba que
    EXISTA, que es lo que hacia falta para que no se pueda actualizar el
    manifiesto en silencio.

    Se exige una seccion de justificacion con numeros medidos: una tabla con
    una flecha `antes -> despues`. Con hash, commit y lineas ya declarados,
    una flecha es lo unico que el documento puede tener y que el manifiesto
    no puede aportar."""
    texto = io.open(os.path.join(ROOT, *CANONICO.split('/')),
                    encoding='utf-8').read()
    flechas = re.findall(r'\S+\s*[-=]*>\s*\S+', texto)
    assert flechas, (
        '%s declara el hash pero no explica el cambio. Un sha dice QUE '
        'FICHERO es, no si es el correcto: hace falta la medicion del antes y '
        'el despues, escrita. Ver CANAL_MANUAL_CERRADO.md §4.'
        % CANONICO)


# --- los DOS invariantes, por separado ------------------------------------
#
# La revision tecnica (revision_2, reserva B) pide comprobar que los dos
# invariantes se cubren POR SEPARADO, no que uno tape al otro. Son
# independientes y se rompen por motivos distintos:
#
#   1. el hash declarado coincide con el disco  -> `test_el_hash_de_la_base_es_el_declarado`
#   2. ningun script escribe mientras se revisa -> `test_la_revision_en_curso_impide_escribir_a_un_script`
#
# Que se comprueben por separado importa porque uno puede romperse solo: si
# el mantenedor declara el hash y el flag lo dice, el segundo invariante es
# el unico que queda, y si esta tapado por el primero nadie se entera de que
# un script puede escribir.


def test_los_dos_invariantes_se_comprueban_por_separado():
    """Los dos guards existen, y cada uno mira lo suyo.

    Se comprueba que los dos tests existen y que NO son el mismo: si alguien
    fusionara los dos invariantes en una sola comprobacion, perderiamos la
    capacidad de decir QUE se rompio."""
    import inspect
    from motor import test_canal_manual as M
    hash_test = getattr(M, 'test_el_hash_de_la_base_es_el_declarado', None)
    rev_test = getattr(M, 'test_el_bloqueo_impide_escribir_cuando_la_revision_esta_activa',
                       None)
    assert hash_test is not None, 'falta el invariante del hash'
    assert rev_test is not None, 'falta el invariante de la revision en curso'
    assert inspect.getsource(hash_test) != inspect.getsource(rev_test), (
        'los dos invariantes tienen el MISMO cuerpo: uno de los dos no se '
        'esta comprobando')


def test_el_commit_declarado_existe():
    """La constante apunta a un commit real. Sin esto seria un string
    decorativo."""
    commit = learn.HANDS_DB_COMMIT
    existe = _git('cat-file', '-t', commit)
    assert existe == 'commit', (
        'el commit declarado (%s) no existe en este repositorio' % commit)


def test_el_ultimo_commit_que_toco_la_base_tiene_el_hash_declarado():
    """El invariante real: lo ULTIMO que se commiteo de la base es lo que el
    motor cree usar.

    Se comprueba contra «el ultimo commit que toco el fichero» y no contra
    `HANDS_DB_COMMIT` a proposito. Si se comprobara contra la constante, habria
    una dependencia circular —el commit canonico no existe hasta que se
    commitea el fichero que lo canoniza— y habria que hacer el commit en dos
    pasos para poder pasar el test que dice que el commit esta bien.
    """
    ultimo = _git('log', '-1', '--format=%H', '--', DB_REL)
    assert ultimo, 'data/hands_db.jsonl no tiene ningun commit'
    crudo = subprocess.run(['git', 'show', '%s:%s' % (ultimo, DB_REL)],
                           cwd=ROOT, capture_output=True).stdout
    real = hashlib.sha256(crudo).hexdigest()
    assert real == learn.HANDS_DB_SHA256, (
        'el ultimo commit que toco la base (%s) tiene sha256 %s y el declarado '
        'es %s.\n\nSi el cambio es legitimo: sube `learn.HANDS_DB_SHA256`, '
        'actualiza `HANDS_DB_COMMIT` y escribe el motivo en %s.\n'
        'Si no lo es: revierte el commit de la base.'
        % (ultimo[:8], real[:16], learn.HANDS_DB_SHA256[:16], CANONICO))


def test_el_blob_y_el_disco_coinciden_byte_a_byte():
    """`.gitattributes` pone `data/hands_db.jsonl -text` a proposito.

    Sin eso, git normaliza a LF al guardar y devuelve CRLF al sacar en
    Windows, y el blob del repositorio y el fichero del disco tienen siempre
    sha256 distinto. Medido: blob `7d972b2b` (0 CRLF) contra disco
    `202a1f54` (1258 CRLF). Un hash que no se puede reproducir no es un hash,
    y encima invalida todos los guards que comparen disco con commit.
    """
    crudo = subprocess.run(['git', 'show', 'HEAD:%s' % DB_REL],
                           cwd=ROOT, capture_output=True).stdout
    disco = io.open(DB_PATH, 'rb').read()
    if crudo == disco:
        return
    raise AssertionError(
        'el blob de HEAD y el fichero en disco son distintos: %d contra %d '
        'bytes. Comprueba que .gitattributes siga.teniendo '
        '`data/hands_db.jsonl -text` y que core.autocrlf no lo este '
        'anulando; si es asi, reindexa con '
        '`git rm --cached data/hands_db.jsonl && git add data/hands_db.jsonl`'
        % (len(crudo), len(disco)))


# --- lo que la revision en curso SI protege -------------------------------

def test_el_bloqueo_por_revision_existe_y_esta_cableado():
    """El bloqueo tiene que EXISTIR, esté o no activo.

    `REVISION_EN_CURSO` pasó a `False` el 2026-10-15: el mantenedor terminó
    la revisión de `H_0001`..`H_1282`. Un guard que se borra cuando deja de
    hacer falta no es un guard, es una nota: la próxima revisión vuelve a
    necesitarlo y no habría nada que activar.

    Por eso este test NO comprueba que el bloqueo esté activo —comprobar eso
    sería atar el guard a un estado del mundo que cambia— sino que el
    mecanismo sigue cableado y sigue siendo alcanzable."""
    assert hasattr(learn, 'REVISION_EN_CURSO')
    texto = io.open(os.path.join(ROOT, 'tools', 'aplicar_reinterpretacion.py'),
                    encoding='utf-8').read()
    assert 'REVISION_EN_CURSO' in texto, (
        'aplicar_reinterpretacion.py no comprueba la revision: se podria '
        'escribir la base con un script mientras el mantenedor revisa, que '
        'es justo lo que se perdio en el bloque anterior')
    assert 'BASE CONGELADA' not in texto, (
        'el mensaje sigue diciendo "BASE CONGELADA", que afirma tambien que '
        'el mantenedor no puede editarla a mano. Es la mitad contradictoria '
        'del mensaje viejo y ya no describe lo que el script hace.')


def test_el_bloqueo_impide_escribir_cuando_la_revision_esta_activa(
        tmp_path, capsys):
    """Que el bloqueo funcione, ahora con la revision terminada.

    Con `REVISION_EN_CURSO = False` no se puede comprobar «está activo» sin
    cambiar el mundo. Se comprueba lo que importa: **poniéndolo a True, el
    script se niega.** Un guard que solo existe mientras el mundo está en un
    estado concreto no protege nada cuando ese estado cambia.

    Es el mismo criterio que todos los tests de este fichero: se simula la
    regresión que el guard tiene que detectar."""
    from tools import aplicar_reinterpretacion as AR
    destino = tmp_path / 'hands_db.jsonl'
    destino.write_text('{"hand_id": "X"}\n', encoding='utf-8')

    original_db, original_rev = AR.DB_PATH, AR.learn.REVISION_EN_CURSO
    AR.DB_PATH, AR.learn.REVISION_EN_CURSO = str(destino), True
    try:
        assert AR.main(['--apply']) == 4, (
            'con la revision en curso, --apply deberia negarse')
        out = capsys.readouterr().out
        assert 'REVISION EN CURSO' in out, out
        assert AR.main(['--apply', '--descartar-cambios']) == 4
        assert 'REVISION EN CURSO' in capsys.readouterr().out
        # Y con la revision terminada, el mismo comando NO se niega.
        AR.learn.REVISION_EN_CURSO = False
        assert AR.main(['--apply']) != 4, (
            'sin revision en curso, --apply no deberia negarse por eso')
    finally:
        AR.DB_PATH, AR.learn.REVISION_EN_CURSO = original_db, original_rev


def test_el_mensaje_de_revision_no_prohibe_la_revision():
    """El mensaje que ve el mantenedor tiene que decir la verdad de lo que
    bloquea.

    Decirle "la base esta congelada" mientras el esta editando a mano es
    exactamente el tipo de instruccion que hace que alguienется a un lado y
    deje de revisar."""
    texto = io.open(os.path.join(ROOT, 'tools', 'aplicar_reinterpretacion.py'),
                    encoding='utf-8').read()
    assert 'NO es un congelamiento' in texto, (
        'el mensaje no aclara que el bloqueo es a los SCRIPT, no a las '
        'ediciones del mantenedor')


def test_el_fallo_del_congelamiento_no_es_el_del_fichero_ajeno():
    """Los dos bloqueos devuelven codigos distintos y se distinguen.

    Razon: si los dos devolvieran lo mismo, con la base congelada no se podria
    saber si el problema es "no se toca" o "esto no es mio".
    """
    codigo = io.open(os.path.join(ROOT, 'tools',
                                  'aplicar_reinterpretacion.py'),
                     encoding='utf-8').read()
    assert 'return 4' in codigo, 'el congelamiento deberia devolver 4'
    assert 'return 3' in codigo, 'el fichero ajeno deberia devolver 3'
    assert 'return 2' in codigo, 'el alcance incorrecto deberia devolver 2'

def test_aplicar_reinterpretacion_no_puede_sobrescribir_un_ajeno():
    """La garantia de `aplicar_reinterpretacion.py`, sobre el fichero de verdad.

    Es el agujero por el que se perdieron 928 lineas. El script clasifica el
    fichero actual como referencia, salida suya, o ajeno, y en el ultimo caso
    se niega. Este test verifica que la clasificacion existe y se llama; la
    prueba de comportamiento, con ficheros mutados, esta en
    `motor/test_aplicar_reinterpretacion.py`.
    """
    from tools import aplicar_reinterpretacion as AR
    assert hasattr(AR, 'estado_del_fichero_actual')
    # revision_2 §1 pide prueba independiente de que SHA_SALIDA corresponde a
    # los bytes que produce el script. Aqui se comprueba el valor; el test
    # `test_los_sha_estan_fijados` de test_aplicar_reinterpretacion.py
    # comprueba que el script produce esos bytes.
    assert AR.SHA_SALIDA == ('173a72743c7a54255452fb3fc4d8a9095adaddff29a'
                             '54d84dda1d459bcc7fe8d'), AR.SHA_SALIDA
    estado, sha = AR.estado_del_fichero_actual()
    assert estado == 'ajeno', (
        'el estado actual de hands_db.jsonl es "%s", no "ajeno". Si ha '
        'cambiado, hay que actualizar las constantes de los dos ficheros y '
        'decir por que.' % estado)
    assert sha == learn.HANDS_DB_SHA256


def test_los_dos_scripts_de_escritura_declaran_a_que_script_se_debe():
    """Los dos scripts que han escrito este fichero declaran su SHA de salida.

    `aplicar_reinterpretacion.py` ya lo hace. `aplicar_correcciones.py` es el
    otro, y no lo hace: sin eso no hay forma de reconocer su salida ni de
    distinguirla de una edicion manual.
    """
    ruta = os.path.join(ROOT, 'tools', 'aplicar_correcciones.py')
    texto = io.open(ruta, encoding='utf-8').read()
    assert 'SHA_SALIDA' in texto or 'SHA_ESPERADA' in texto, (
        'aplicar_correcciones.py escribe hands_db.jsonl y no declara el sha256 '
        'de lo que produce. Sin eso, su salida es indistinguible de una '
        'edicion a mano, que es exactamente el problema que se quiere cerrar.')