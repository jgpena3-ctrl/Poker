# -*- coding: utf-8 -*-
"""El procedimiento de integracion, contra una copia sintetica COMPLETA.

Y lo que se prueba, y en que orden:

  · el camino de EXITO, contra las 1258 manos de la copia sintetica, con un
    umbral declarado PARA EL FIXTURE (que no es el de la copia real);
  · el camino de FALLO por un error de clasificacion inyectado;
  · el camino de FALLO por ciegas insuficientes;
  · que no deja RASTRO: ni el sha de la base, ni un fichero temporal;
  · que un sha de candidata que no cuadra falla SIN tocar la base;
  · y que el codigo de «incompleta» no se puede leer como una integracion
    satisfactoria.

Y los dos caminos de FALLO van contra un destino TEMPORAL, y no contra la
base canonica. Y el camino de EXITO tambien, gracias a `POKER_DB_PATH`, que
permite que los guardianes miren otro destino.

Y en ninguno de los dos se toca la base canonica, y hay un test que lo
comprueba DESPUES de cada uno.
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import fixture_copia_sintetica as FIX   # noqa: E402

CANON = os.path.join(ROOT, 'data', 'hands_db.jsonl')
SCRIPT = os.path.join(ROOT, 'tools', 'integrar_copia.py')


def _sha(ruta):
    with io.open(ruta, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def _candidata(inyectar_error=False):
    """La copia sintetica completa, y su informe.

    Y con `inyectar_error`, se le mete a UNA mano una accion que el motor no
    conoce, para que la clasificacion falle. Y el fallo tiene que ser real: si
    el motor no la rechazara, el camino de fallo no existiria.
    """
    alta = tempfile.mkdtemp(prefix='fixture_copia_')
    destino = os.path.join(alta, 'candidata.jsonl')
    informe = FIX.construir(destino)
    if inyectar_error:
        with io.open(destino, encoding='utf-8') as f:
            lineas = [l for l in f if l.strip()]
        # Y la accion va SUSTITUYENDO a la de un jugador que ya decidio, y
        # que no es el BB ni el SB —para no tocar la ciega—. Y el motivo de
        # que se SUSTITUYA y no que se AÑADA: el motor solo CLASIFICA la
        # primera accion de cada jugador, de modo que una accion de mas, de
        # un jugador que ya decidio, no la mira nadie. Y ese es el detalle que
        # hacia que la primera version de esta inyeccion no produjera
        # ningun error.
        inyectado = False
        for k, l in enumerate(lineas):
            h = json.loads(l)
            pre = ((h.get('streets', {}) or {}).get('preflop', {}) or {}).get(
                'actions', []) or []
            cuentas = {}
            for a in pre:
                cuentas[a.get('pos')] = cuentas.get(a.get('pos'), 0) + 1
            for j, a in enumerate(pre):
                if (a.get('pos') not in ('BB', 'SB')
                        and cuentas.get(a.get('pos')) == 1):
                    pre[j] = {'pos': a.get('pos'), 'action': 'z', 'amount': 0.0}
                    lineas[k] = json.dumps(h, ensure_ascii=False) + '\n'
                    inyectado = True
                    break
            if inyectado:
                break
        assert inyectado, 'no hay ninguna accion que sustituir'
        with io.open(destino, 'w', encoding='utf-8', newline='\n') as f:
            f.writelines(lineas)
        informe['inyectado'] = True
    return alta, destino, informe


def _correr(destino, candidata, *args):
    cmd = [sys.executable, SCRIPT, '--destino', destino, '--origen', candidata]
    cmd.extend(args)
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def test_el_flujo_completo_pasa_contra_la_copia_sintetica_completa():
    """El camino de exito, con las 1258 manos y los dos guardianes.

    Y el umbral es el del FIXTURE, medido, y no el de la copia real: porque el
    921 es el control de la base de HOY, y el fixture recodifica las ciegas
    SIN cambiar cuantas manos tienen ciega, de modo que el numero coincide.
    """
    alta, candidata, informe = _candidata()
    try:
        assert informe['manos'] == 1258, informe
        assert informe['revisadas_disponibles'] == 1055, informe
        assert informe['recodificadas'] > 0, informe
        # Y las 203 PENDIENTES quedan intactas, que es lo que significa
        # «recodificar solo las revisadas». Y el numero de manos que quedan
        # sin tocar es MAYOR que 203, porque hay revisadas que no tienen la
        # ciega grabada y por tanto no se pueden recodificar.
        #
        # MEDIDO: 802 se recodifican, y 456 quedan: 203 por no revisadas, y
        # 253 revisadas sin ciega grabada. Y el fixture NO AÑADE las ciegas
        # que faltan, que es lo que hace la copia real: el fixture es mas
        # SUAVE, y por eso el numero de ciegas que reconoce es el de hoy.
        with io.open(CANON, encoding='utf-8') as f:
            canonicas = {json.loads(l)['hand_id']: json.loads(l)
                         for l in f if l.strip()}
        with io.open(candidata, encoding='utf-8') as f:
            sinteticas = {json.loads(l)['hand_id']: json.loads(l)
                          for l in f if l.strip()}
        sin_revisar = set(canonicas) - FIX.revisadas()
        assert len(sin_revisar) == 203, len(sin_revisar)
        intactas = [h for h in sin_revisar
                    if canonicas[h] == sinteticas[h]]
        assert len(intactas) == 203, (
            'de las 203 sin revisar, %d han cambiado. Y el fixture solo puede '
            'tocar las revisadas.' % (203 - len(intactas)))
        assert informe['dejadas'] == 456, informe['dejadas']

        destino = os.path.join(alta, 'destino.jsonl')
        shutil.copyfile(CANON, destino)
        antes = io.open(destino, 'rb').read()

        r = _correr(destino, candidata, '--umbral-ciegas', '921')
        assert r.returncode == 0, (
            'el camino de exito ha fallado con el codigo %d:\n%s'
            % (r.returncode, r.stdout[-1500:]))
        assert 'INCOMPLETA' not in r.stdout, r.stdout[-800:]
        assert io.open(destino, 'rb').read() == antes, (
            'la base destino no ha vuelto a ser la que era')
        # y los DOS guardianes han corrido, y han pasado
        assert 'vocabulario' in r.stdout and 'no vacuidad' in r.stdout, r.stdout
        assert 'OMITIDO' not in r.stdout, (
            'los guardianes se han omitido, y con un destino temporal ya no '
            'hace falta omitirlos: %s' % r.stdout[-800:])
    finally:
        shutil.rmtree(alta, ignore_errors=True)


def test_un_error_de_clasificacion_inyectado_hace_fallar_y_restaura():
    """Y un fallo de clasificacion real, inyectado.

    Y la inyeccion es una accion que el motor NO conoce, de modo que el
    fallo es del motor y no del script. Y el script tiene que salir con
    FALLO y devolver la base.
    """
    alta, candidata, _informe = _candidata(inyectar_error=True)
    try:
        destino = os.path.join(alta, 'destino.jsonl')
        shutil.copyfile(CANON, destino)
        antes = io.open(destino, 'rb').read()

        r = _correr(destino, candidata, '--umbral-ciegas', '921')
        assert r.returncode == 1, (
            'con un error de clasificacion inyectado el script tiene que '
            'fallar, y ha salido con %d:\n%s' % (r.returncode, r.stdout[-1200:]))
        assert 'ERRORES de clasificacion' in r.stdout, r.stdout[-800:]
        assert 'H_0001' in r.stdout, (
            'y el informe tiene que NOMBRAR la mano, que es lo que permite '
            'saber que paso sin volver a ejecutar: %s' % r.stdout[-800:])
        assert io.open(destino, 'rb').read() == antes, (
            'la base destino no ha vuelto a ser la que era, y con un fallo de '
            'clasificacion encima')
    finally:
        shutil.rmtree(alta, ignore_errors=True)


def test_menos_ciegas_que_el_umbral_hace_fallar_y_restaura():
    """Y un umbral que no se cumple, que es el otro fallo que importa.

    Y el motivo de que este caso sea el importante: es el que atrapa a una
    copia que el motor lee, pero a la que le faltan ciegas. Y el 921 es el
    control de la base de HOY, de modo que el umbral de la copia es OTRO, y
    lo pone A1.
    """
    alta, candidata, _informe = _candidata()
    try:
        destino = os.path.join(alta, 'destino.jsonl')
        shutil.copyfile(CANON, destino)
        antes = io.open(destino, 'rb').read()

        r = _correr(destino, candidata, '--umbral-ciegas', '1258')
        assert r.returncode == 1, (
            'con un umbral de 1258 y unas ciegas de menos, el script tiene que '
            'fallar, y ha salido con %d:\n%s' % (r.returncode, r.stdout[-1200:]))
        assert 'INSUFICIENTE' in r.stdout, r.stdout[-800:]
        assert io.open(destino, 'rb').read() == antes
    finally:
        shutil.rmtree(alta, ignore_errors=True)


def test_la_ejecucion_no_deja_rastro():
    """Ni el sha de la base, ni un fichero temporal.

    Y el rastro se mira en DOS sitios: el contenido de la base destino, que
    tiene que ser el de antes byte a byte, y el CONTENIDO de `data/` y de la
    raiz del repo, que tiene que ser el de antes.
    """
    def _listado(d):
        return sorted(os.listdir(d))

    antes_raiz = _listado(ROOT)
    antes_data = _listado(os.path.join(ROOT, 'data'))
    antes_sha = _sha(CANON)

    alta, candidata, _informe = _candidata()
    try:
        destino = os.path.join(alta, 'destino.jsonl')
        shutil.copyfile(CANON, destino)
        _correr(destino, candidata, '--umbral-ciegas', '921')
        # Y un camino de FALLO, que es donde mas se puede dejar rastro.
        _correr(destino, candidata, '--umbral-ciegas', '99999')
    finally:
        shutil.rmtree(alta, ignore_errors=True)

    assert _listado(ROOT) == antes_raiz, (
        'han quedado ficheros en la raiz: %r'
        % (set(_listado(ROOT)) - set(antes_raiz),))
    assert _listado(os.path.join(ROOT, 'data')) == antes_data, (
        'han quedado ficheros en `data/`: %r'
        % (set(_listado(os.path.join(ROOT, 'data'))) - set(antes_data),))
    assert _sha(CANON) == antes_sha, 'el sha de la base canonica ha cambiado'


def test_un_sha_que_no_cuadra_falla_limpiamente_sin_tocar_la_base():
    """Y una candidata que no es la que se cree, que falla ANTES de tocar nada.

    Y el motivo de que se compruebe ANTES del intercambio: una candidata
    equivocada no debe dejar la base ni un instante en un estado raro. Y el
    codigo de salida es otro, que es el de «la candidata no es la que se
    creia».
    """
    alta, candidata, _informe = _candidata()
    try:
        destino = os.path.join(alta, 'destino.jsonl')
        shutil.copyfile(CANON, destino)
        antes = io.open(destino, 'rb').read()

        r = _correr(destino, candidata, '--sha-esperada', '0' * 64)
        assert r.returncode == 4, (
            'con un sha que no cuadra el script tiene que fallar con el codigo '
            '4, y ha salido con %d:\n%s' % (r.returncode, r.stdout[-1200:]))
        assert 'NO ES LA QUE SE CREIA' in r.stdout, r.stdout[-800:]
        assert io.open(destino, 'rb').read() == antes
    finally:
        shutil.rmtree(alta, ignore_errors=True)


def test_el_codigo_de_incompleta_no_es_una_integracion_satisfactoria():
    """Y que el codigo 2 no se puede leer como un exito.

    Y el motivo: sin el umbral, el procedimiento NO puede decir si la copia
    vale. Y un codigo de salida que significa «no se puede saber» y que
    devuelve cero, es un codigo que alguien va a leer como «todo bien».
    """
    alta, candidata, _informe = _candidata()
    try:
        destino = os.path.join(alta, 'destino.jsonl')
        shutil.copyfile(CANON, destino)
        antes = io.open(destino, 'rb').read()

        r = _correr(destino, candidata)
        assert r.returncode == 2, (
            'sin umbral el codigo tiene que ser el 2, y ha salido con %d'
            % r.returncode)
        assert 'INCOMPLETA' in r.stdout, r.stdout[-800:]
        assert io.open(destino, 'rb').read() == antes
    finally:
        shutil.rmtree(alta, ignore_errors=True)
