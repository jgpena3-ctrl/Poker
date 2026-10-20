# -*- coding: utf-8 -*-
"""El REGISTRO de que esta hecho, que sigue abierto y que depende de A1.

Y el motivo de que tenga un test: un registro que nadie vigila es un informe
que se queda viejo. Y de este hay tres cosas que tienen que seguir siendo
ciertas, y las tres se pueden comprobar:

  1. que nombra a quien depende de cada bloque abierto;
  2. que dice que la base canonica NO se toca, y que la copia no se declara
     canonica sin la revision de A1;
  3. que el procedimiento de integracion existe, y que sin el umbral la
     ejecucion se declara incompleta.
"""
import io
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'DOCS', 'ESTADO_DEL_TRABAJO.md')
SCRIPT = os.path.join(ROOT, 'tools', 'integrar_copia.py')


def _registro():
    with io.open(DOC, encoding='utf-8') as f:
        return f.read()


def test_el_registro_existe_y_nombra_los_cuatro_bloques_abiertos():
    """Y los cuatro, con su dueno.

    Y el motivo de nombrarlos: un bloqueo sin dueno es deuda, y un registro
    que no dice de quien es cada cosa es una lista.
    """
    reg = _registro()
    for ancla in ('matrix', 'board divergente', 'preflop', 'rival'):
        assert ancla in reg, (
            'el registro no nombra el bloqueo de %r, y un bloqueo sin nombre '
            'no se puede retomar' % ancla)
    assert 'de A1' in reg, (
        'y el registro tiene que decir quien tiene las 203 manos, que es de '
        'quien las revisa')


def test_el_registro_dice_que_la_copia_no_es_canonica():
    """Y que la adopcion no es de este trabajo.

    Y el motivo: el cierre tecnico y la autorizacion de la adopcion son dos
    cosas distintas, y confundirlas hace que un trabajo que acaba se da por
    terminado como si el otro tambien.
    """
    reg = _registro()
    assert 'NO equivale a autorizar' in reg, (
        'el registro tiene que decir que el cierre tecnico no es la autorizacion '
        'de la adopcion')
    assert 'A1' in reg


def test_el_procedimiento_de_integracion_sin_umbral_dice_incompleta():
    """Y que el procedimiento EXISTE y que sin umbral no se declara completo.

    Y esto no se comprueba leyendo el codigo: se ejecuta, y se mira el codigo
    de salida. Que es la unica forma de que un «dice que esta incompleta» sea
    algo y no una frase.
    """
    assert os.path.isfile(SCRIPT), 'el procedimiento de integracion no existe'
    # Y el destino es TEMPORAL, y no la base canonica. Y el motivo: este test
    # intercambia la base, y la base canonica no es de este trabajo. Y la
    # restauracion es garantizada, pero «garantizada» no es «imposible que
    # pase»: si el proceso muere entre el intercambio y la restauracion, la
    # base se queda cambiada. Y eso no lo decide un test.
    import tempfile
    with tempfile.TemporaryDirectory() as alta:
        destino = os.path.join(alta, 'destino.jsonl')
        shutil.copyfile(os.path.join(ROOT, 'data', 'hands_db.jsonl'), destino)
        r = subprocess.run([sys.executable, SCRIPT, '--destino', destino],
                           cwd=ROOT, capture_output=True, text=True)
    # Sin umbral, el procedimiento tiene que salir con codigo DISTINTO de cero
    # y decir por que. Y el codigo 2 es el de «incompleta».
    assert r.returncode == 2, (
        'sin umbral de ciegas la ejecucion tiene que declarar que esta '
        'INCOMPLETA, y salir con el codigo 2. Salio con %d. Y el motivo: el '
        'umbral lo fija A1, y sin el no se puede decir si la copia vale.'
        % r.returncode)
    assert 'INCOMPLETA' in r.stdout, r.stdout[-400:]
