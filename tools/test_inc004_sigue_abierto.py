# -*- coding: utf-8 -*-
"""R1 tarea 5: INC-004 tiene que seguir ABIERTO y VISIBLE.

No basta con que el .md exista. Lo que hay que comprobar es que el fallo no
se ha silenciado por ninguna de las tres vias que existen:

  - `pytest.mark.xfail` en el test
  - `pytest.mark.skip` o `skipif` en el test
  - editar el test o el dato para que pase

Y que sigue fallando de verdad, y que el .md sigue diciendo que esta
ABIERTO y no resuelto.

La razon de que esto tenga test: un silencio es facil y no se ve. Un
`xfail` puesto para que la suite salga verde es el sintoma de que la suite
verde se ha confundido con el trabajo hecho.
"""
import io
import os
import subprocess
import sys
import ejecutar_pytest as ep  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST = os.path.join(ROOT, 'motor', 'test_cm004.py')
DOC = os.path.join(ROOT, 'DOCS', 'INC-004_H_1196.md')
ALVADO = 'test_ninguna_mano_tiene_una_bb_b_que_no_pueda_ser_la_ciega'


def _git(*args):
    return subprocess.run(['git'] + list(args), cwd=ROOT,
                          capture_output=True).stdout.decode('utf-8')


def _fuente():
    with io.open(TEST, encoding='utf-8') as f:
        return f.read()


# --------------------------------------------------- no esta silenciado
def test_el_test_no_esta_marcado_como_xfail():
    s = _fuente()
    i = s.index('def ' + ALVADO)
    # los decoradores estan justo encima del def
    arriba = s[:i].rsplit('\n\n', 1)[-1]
    for marca in ('xfail', 'skip'):
        assert marca not in arriba, (
            'el test tiene %r encima: un %s puesto para que la suite salga '
            'verde es perdida de informacion' % (marca, marca))


def test_el_test_no_tiene_skip_dentro():
    s = _fuente()
    i = s.index('def ' + ALVADO)
    cuerpo = s[i:i + 1200]
    assert 'pytest.skip' not in cuerpo
    assert 'pytest.xfail' not in cuerpo


def test_el_test_no_se_ha_tocado_por_este_bloque():
    """Prueba de atribucion: si el fichero no aparece en el historial de
    este bloque, el fallo no es de aqui."""
    log = _git('log', '--format=%h %s', '-20', '--', 'motor/test_cm004.py')
    assert log.strip(), 'el fichero tiene que tener historial'
    # el ultimo commit que lo toco tiene que ser la revision manual
    primero = log.strip().split('\n')[0]
    assert primero.split()[0] == 'dfef471', (
        'el ultimo que toco test_cm004.py es %s, y se esperaba dfef471'
        % primero.split()[0])


def test_data_y_motor_no_estan_tocados():
    """Lo que hace que el fallo sea de otra linea. Si esto dejara de ser
    vacio, el diagnostico entero de INC-004 habria que rehacerlo."""
    salida = _git('diff', '--name-only', 'HEAD', '--', 'data/', 'motor/')
    assert salida.strip() == '', (
        'data/ o motor/ tienen cambios sin commitear: %r' % salida.strip())


# -------------------------------------------------- sigue fallando de verdad
def test_el_test_sigue_fallando():
    """Lo ejecuta. No basta con leer que no hay xfail: hay que ver que
    FALLA."""
    # Y por `ejecutar_pytest`, no con un `subprocess.run` propio.
    #
    # MEDIDO, y no por estilo: un subproceso propio no corta el 4 —
    # «no se ha ejecutado nada»—, no comprueba que la salida nombre el test
    # que quiero, y aqui se compensa con un `!= 0` y un `H_1196` que se
    # comprueba DESPUES. O sea que hacia el trabajo a mano, y a mano se
    # queda.
    #
    # Y `afirmar_caida` exige el codigo 1 CONCRETO y que la salida traiga
    # `FAILED ...::test_nombre`: las dos mitades de una vez, y no una de
    # ellas mas un parche.
    #
    # Y `-x` se conserva aunque con UN solo test seleccionado sea inerte: si
    # pasa no hace nada, y si falla ya no hay nada mas que parar. Quitarlo
    # seria cambiar el comportamiento de un test que funciona, sin motivo.
    salida = ep.afirmar_caida(
        os.path.join(ROOT, 'motor', 'test_cm004.py'), ALVADO, cwd=ROOT,
        extra=('-x',),
        cuando='el test PASA. O se ha arreglado la mano por otra linea, o '
                'se ha tocado el test. En los dos casos INC-004 hay que '
                'cerrarlo y este documento, no.')
    assert 'H_1196' in salida, (
        'y tiene que seguir siendo H_1196, no otro:\n%s' % salida[-800:])


# ---------------------------------------------------- el .md dice ABIERTO
def test_el_documento_declara_que_esta_abierto():
    with io.open(DOC, encoding='utf-8') as f:
        s = f.read()
    baja = s.lower()
    assert 'abierto' in baja, (
        'INC-004 tiene que declarar que sigue ABIERTO, no resuelto: un '
        'incidente derivation que se lee como cerrado es un incidente '
        'perdido')
    assert 'deriva' in baja or 'otra linea' in baja or 'otra línea' in baja


def test_el_documento_no_declara_estado_cerrado():
    """No se buscan palabras sueltas: el documento dice "no resuelto" y
    "quien lo arregla", que es lo correcto. Lo que se comprueba es la
    DECLARACION, que es la unica linea que cambia cuando algo se cierra."""
    with io.open(DOC, encoding='utf-8') as f:
        s = f.read()
    declaracion = [l for l in s.split('\n') if 'ESTADO:' in l.upper()]
    assert len(declaracion) == 1, (
        'tiene que haber UNA declaracion de estado, y no %d: %r'
        % (len(declaracion), declaracion))
    assert 'ABIERTO' in declaracion[0].upper(), (
        'y tiene que decir ABIERTO: %r' % declaracion[0])
    for cerrado in ('ESTADO: CERRADO', 'ESTADO: RESUELTO'):
        assert cerrado not in s.upper(), (
            'el documento declara %s, y no se ha resuelto' % cerrado)


def test_el_documento_dice_quien_lo_arregla():
    with io.open(DOC, encoding='utf-8') as f:
        s = f.read()
    assert 'data/' in s and 'motor/' in s, (
        'tiene que decir quien lo arregla, que es lo unico que convierte '
        'un fallo en una tarea con dueno')