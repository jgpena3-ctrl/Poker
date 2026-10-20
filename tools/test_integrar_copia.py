# -*- coding: utf-8 -*-
"""El procedimiento de integracion, probado en seco.

Y «en seco» significa dos cosas, y las dos importan:

  1. **contra una COPIA SINTETICA REDUCIDA**, y no contra la copia real. La
     copia real la valida A1, y este test no tiene nada que ver con eso.
  2. **contra un DESTINO TEMPORAL**, y no contra `data/hands_db.jsonl`. De
     modo que el test **no toca la base canonica ni un instante**, que es la
     unica manera de que un test de intercambio sea aceptable.

Y lo que se comprueba:

  - que el intercambio ocurre, y que lo que se mide es de la base CANDIDATA;
  - que la base se restaura, **byte a byte**, y que su sha cuadra;
  - que sin el umbral de ciegas la ejecucion se declara INCOMPLETA, porque el
    umbral lo fija A1 y no se puede inventar;
  - que la fase de los guardianes se OMITE contra un destino que no es la
    base canonica, y se dice, en vez de ejecutarse en balde.
"""
import io
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import integrar_copia as IC   # noqa: E402

CANON = os.path.join(ROOT, 'data', 'hands_db.jsonl')


def _copia_reducida(destino, n=6):
    """Las primeras n manos de la base, en un fichero aparte.

    Y son las primeras de VERDAD, y no inventadas: el procedimiento tiene que
    medirse sobre manos de verdad, aunque sean pocas.
    """
    with io.open(CANON, encoding='utf-8') as f:
        lineas = [l for l in f if l.strip()][:n]
    with io.open(destino, 'w', encoding='utf-8') as f:
        f.writelines(lineas)
    return destino


def test_el_intercambio_mide_la_candidata_y_restaura_la_destino():
    """Y que la restauracion es byte a byte, y con el sha comprobado."""
    with tempfile.TemporaryDirectory() as alta:
        origen = _copia_reducida(os.path.join(alta, 'candidata.jsonl'))
        destino = os.path.join(alta, 'destino.jsonl')
        shutil.copyfile(CANON, destino)
        antes = io.open(destino, 'rb').read()

        informe = IC.integrar(origen, destino)

        despues = io.open(destino, 'rb').read()
        assert despues == antes, (
            'la base destino no ha vuelto a ser la que era. Y un procedimiento '
            'que se come la base es peor que no tener procedimiento.')
        assert informe['restaurado'], (
            'el script dice que no ha restaurado, y el sha no cuadra: %r'
            % (informe,))
        assert informe['sha_original'] == informe['sha_tras'], informe
        # y lo que se ha medido es de la CANDIDATA: seis manos, no 1258
        assert informe['manos'] == 6, informe['manos']
        assert informe['completo'] is False, (
            'sin umbral de ciegas la ejecucion tiene que declararse '
            'INCOMPLETA, porque el umbral lo fija A1')


def test_sin_umbral_la_ejecucion_esta_incompleta():
    """Y que el motivo se dice, y no se inventa un numero.

    Y el motivo: el umbral de ciegas de la copia sale de datos que A1 todavia
    no ha validado, de modo que un umbral puesto aqui seria un numero que
    nadie ha medido.
    """
    with tempfile.TemporaryDirectory() as alta:
        origen = _copia_reducida(os.path.join(alta, 'candidata.jsonl'))
        destino = os.path.join(alta, 'destino.jsonl')
        shutil.copyfile(CANON, destino)
        informe = IC.integrar(origen, destino)
        assert informe['completo'] is False
        assert informe['umbral_ciegas'] is None
        assert 'ciegas_suficientes' not in informe, (
            'sin umbral no se puede decir que las ciegas bastan, y no se '
            'puede INVENTAR un umbral: %r' % (informe,))


def test_con_umbral_la_ejecucion_es_completa():
    """Y que con umbral, la ejecucion se declara completa.

    Y el umbral se toma del MEDIDO, y no de un numero escrito: el umbral que
    se prueba es uno por encima de las ciegas que la copia tiene, de modo que
    la puerta se ve CERRAR y abrir.
    """
    with tempfile.TemporaryDirectory() as alta:
        origen = _copia_reducida(os.path.join(alta, 'candidata.jsonl'))
        destino = os.path.join(alta, 'destino.jsonl')
        shutil.copyfile(CANON, destino)
        medir = IC.integrar(origen, destino)
        ciegas = medir['ciegas']

        justo = IC.integrar(origen, destino, umbral_ciegas=ciegas)
        assert justo['completo'] is True
        assert justo['ciegas_suficientes'] is True, justo

        justo_mas = IC.integrar(origen, destino, umbral_ciegas=ciegas + 1)
        assert justo_mas['completo'] is True
        assert justo_mas['ciegas_suficientes'] is False, (
            'la puerta tiene que cerrarse cuando las ciegas no bastan, que es '
            'justo para lo que sirve: %r' % (justo_mas,))


def test_los_guardianes_se_omiten_contra_un_destino_que_no_es_la_canonica():
    """Y que se DIGA, en vez de ejecutarlos en balde.

    Y el motivo: los dos guardianes leen SIEMPRE `data/hands_db.jsonl`, de
    modo que contra otro destino no se puede comprobar nada. Y un guardian que
    se ejecuta contra un sitio que no mira no vigila nada, y parece que vigila.
    """
    with tempfile.TemporaryDirectory() as alta:
        origen = _copia_reducida(os.path.join(alta, 'candidata.jsonl'))
        destino = os.path.join(alta, 'destino.jsonl')
        shutil.copyfile(CANON, destino)
        informe = IC.integrar(origen, destino)
        etiquetas = [e for e, _t in informe['guardianes']]
        assert len(etiquetas) == 2, informe['guardianes']
        for _etiqueta, texto in informe['guardianes']:
            assert 'OMITIDO' in texto, (
                'los guardianes se deberian omitir contra un destino que no '
                'es la base canonica, y se dice por que: %r' % (texto,))


def test_la_base_canonica_no_se_toca():
    """Y que la base canonica sigue como estaba.

    Y este test es el que hace que los otros sean aceptables: si el
    procedimiento escribiese en la canonica, un fallo a mitad dejaria la base
    cambiada, y la base es de otro.
    """
    antes = io.open(CANON, 'rb').read()
    with tempfile.TemporaryDirectory() as alta:
        origen = _copia_reducida(os.path.join(alta, 'candidata.jsonl'))
        destino = os.path.join(alta, 'destino.jsonl')
        shutil.copyfile(CANON, destino)
        IC.integrar(origen, destino)
    despues = io.open(CANON, 'rb').read()
    assert despues == antes, 'la base canonica ha cambiado. NO DEBE.'
