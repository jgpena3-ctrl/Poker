# -*- coding: utf-8 -*-
"""El procedimiento de integracion, contra dos copias sinteticas.

Y lo que se prueba, y en que orden:

  · el camino de EXITO, contra el fixture SUAVE —que solo recodifica— y
    contra el fixture DURO —que ademas anade las ciegas que faltaban—, cada
    uno con SU umbral, que es el que el propio fixture mide;
  · que el umbral de uno NO sirve para el otro, en los dos sentidos, y que
    cuando se pone el equivocado el script no da verde;
  · el camino de FALLO por un error de clasificacion inyectado;
  · que no deja RASTRO: ni el sha de la base, ni un fichero temporal;
  · que un sha de candidata que no cuadra falla SIN tocar la base;
  · y que el codigo de «incompleta» no se puede leer como un exito.

Y los dos caminos de FALLO van contra un destino TEMPORAL, y no contra la
base canonica. Y el camino de EXITO tambien, gracias a `POKER_DB_PATH`, que
permite que los guardianes miren otro destino.

Y en ninguno de los dos se toca la base canonica, y hay un test que lo
comprueba DESPUES de cada uno.

## Y EL UMBRAL NO ES UNA CONSTANTE GLOBAL

Y esto no es un detalle de estilo: el fixture suave reconoce 921 ciegas y el
duro 1258, y un unico numero para los dos seria un numero que no distingue
nada. Y el numero de cada uno **lo mide el fixture** y lo dice en su informe,
y el test lo pasa como parametro explicito. Y por eso hay un test que
comprueba que los dos umbrales son DISTINTOS: si alguien los unificara, el
control dejaria de discriminar.
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


def _candidata(dureza=FIX.DUREZA_SUAVE, inyectar_error=False):
    """La copia sintetica del grado pedido, y su informe.

    Y con `inyectar_error`, se le mete a UNA mano una accion que el motor no
    conoce, para que la clasificacion falle. Y el fallo tiene que ser real: si
    el motor no la rechazara, el camino de fallo no existiria.
    """
    alta = tempfile.mkdtemp(prefix='fixture_copia_')
    destino = os.path.join(alta, 'candidata.jsonl')
    informe = FIX.construir(destino, dureza=dureza)
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


def _destino_temporal(alta):
    destino = os.path.join(alta, 'destino.jsonl')
    shutil.copyfile(CANON, destino)
    return destino


def test_el_flujo_completo_pasa_contra_el_fixture_suave():
    """El camino de exito, con las 1258 manos y los dos guardianes.

    Y el umbral es el del FIXTURE, medido por el propio fixture, y no el de la
    copia real: porque el 921 es el control de la base de HOY, y el fixture
    suave recodifica las ciegas SIN cambiar cuantas manos tienen ciega, de
    modo que el numero coincide.
    """
    alta, candidata, informe = _candidata(FIX.DUREZA_SUAVE)
    try:
        assert informe['manos'] == 1258, informe
        assert informe['revisadas_disponibles'] == 1055, informe
        assert informe['tocadas'] > 0, informe
        # Y el umbral sale de aqui, y no de una constante.
        assert informe['ciegas_reconocidas'] == 921, informe

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

        destino = _destino_temporal(alta)
        antes = io.open(destino, 'rb').read()

        r = _correr(destino, candidata,
                    '--ciegas-esperadas', str(informe['ciegas_reconocidas']))
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


def test_el_flujo_completo_pasa_contra_el_fixture_duro():
    """El mismo flujo, contra la copia que se parece a la REAL.

    Y el motivo de que este test exista: el fixture suave reconoce 921
    ciegas, y la copia real reconoce 1258. De modo que el procedimiento solo
    se ha probado contra una candidata que se parece a la base de HOY, y no
    contra una que se parece a la que va a entrar.

    Y el fixture duro, MEDIDO: 1258 ciegas, 0 errores, 0 violaciones, y las
    doce categorias de control —que es lo que hace que el cambio de
    codificacion sea neutro—.
    """
    alta, candidata, informe = _candidata(FIX.DUREZA_DURA)
    try:
        assert informe['manos'] == 1258, informe
        # Y el numero que importa: TODAS las manos con ciega reconocida.
        assert informe['ciegas_reconocidas'] == 1258, informe
        assert informe['tocadas'] == 1258, informe
        assert informe['dejadas'] == 0, informe

        destino = _destino_temporal(alta)
        antes = io.open(destino, 'rb').read()

        r = _correr(destino, candidata,
                    '--ciegas-esperadas', str(informe['ciegas_reconocidas']))
        assert r.returncode == 0, (
            'el camino de exito con el fixture DURO ha fallado con el codigo '
            '%d:\n%s' % (r.returncode, r.stdout[-1500:]))
        assert 'INCOMPLETA' not in r.stdout, r.stdout[-800:]
        assert io.open(destino, 'rb').read() == antes
    finally:
        shutil.rmtree(alta, ignore_errors=True)


def test_los_dos_fixtures_tienen_umbrales_distintos():
    """Y que el umbral NO sea una constante global, que es el punto.

    Y el motivo: si los dos fixtures tuvieran el mismo numero de ciegas, el
    control no distinguiria una candidata de la otra, y el parametro no
    estaria haciendo nada. Y un parametro que no puede cambiar el resultado
    no es un parametro.
    """
    alta_s, _c_s, inf_s = _candidata(FIX.DUREZA_SUAVE)
    try:
        alta_d, _c_d, inf_d = _candidata(FIX.DUREZA_DURA)
        try:
            assert inf_s['ciegas_reconocidas'] == 921, inf_s
            assert inf_d['ciegas_reconocidas'] == 1258, inf_d
            assert inf_s['ciegas_reconocidas'] != inf_d['ciegas_reconocidas']
        finally:
            shutil.rmtree(alta_d, ignore_errors=True)
    finally:
        shutil.rmtree(alta_s, ignore_errors=True)


def test_el_umbral_del_suave_no_sirve_para_el_duro():
    """Y que el umbral equivocado NO da verde.

    Y el caso concreto: el 921 del fixture suave aplicado al fixture duro.
    Y el motivo de que sea el caso mas importante: el 921 es un numero REAL,
    de una base real, y el error mas probable es exactamente este: pillar un
    numero que se sabe de memoria y aplicarlo donde no toca.

    Y el numero es EXACTO y no un minimo, y por eso falla: con un minimo,
    1258 ciegas exceeding 921 darian verde, y un control que no puede fallar
    no es un control.
    """
    alta, candidata, _informe = _candidata(FIX.DUREZA_DURA)
    try:
        destino = _destino_temporal(alta)
        antes = io.open(destino, 'rb').read()

        r = _correr(destino, candidata, '--ciegas-esperadas', '921')
        assert r.returncode == 1, (
            'con el umbral del fixture suave en el duro, el script tiene que '
            'fallar, y ha salido con %d:\n%s' % (r.returncode, r.stdout[-1200:]))
        assert 'NUMERO DE CIEGAS' in r.stdout, r.stdout[-800:]
        assert io.open(destino, 'rb').read() == antes
    finally:
        shutil.rmtree(alta, ignore_errors=True)


def test_el_umbral_del_duro_no_sirve_para_el_suave():
    """Y al reves, que tambien es un caso real.

    Y el motivo: el mismo numero, al reves, es el error de tratar el umbral
    como si fuera un minimo. Y en el caso del fixture suave, el resultado es
    que el motor reconoce MENOS ciegas de las declaradas, que es exactamente
    lo que un umbral minimo dejaria pasar.
    """
    alta, candidata, _informe = _candidata(FIX.DUREZA_SUAVE)
    try:
        destino = _destino_temporal(alta)
        antes = io.open(destino, 'rb').read()

        r = _correr(destino, candidata, '--ciegas-esperadas', '1258')
        assert r.returncode == 1, (
            'con el umbral del fixture duro en el suave, el script tiene que '
            'fallar, y ha salido con %d:\n%s' % (r.returncode, r.stdout[-1200:]))
        assert 'NUMERO DE CIEGAS' in r.stdout, r.stdout[-800:]
        assert io.open(destino, 'rb').read() == antes
    finally:
        shutil.rmtree(alta, ignore_errors=True)


def test_un_error_de_clasificacion_inyectado_hace_fallar_y_restaura():
    """Y un fallo de clasificacion real, inyectado.

    Y la inyeccion es una accion que el motor NO conoce, de modo que el
    fallo es del motor y no del script. Y el script tiene que salir con
    FALLO y devolver la base.
    """
    alta, candidata, _informe = _candidata(FIX.DUREZA_SUAVE, inyectar_error=True)
    try:
        destino = _destino_temporal(alta)
        antes = io.open(destino, 'rb').read()

        r = _correr(destino, candidata, '--ciegas-esperadas', '921')
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

    alta, candidata, _informe = _candidata(FIX.DUREZA_DURA)
    try:
        destino = _destino_temporal(alta)
        _correr(destino, candidata, '--ciegas-esperadas', '1258')
        # Y un camino de FALLO, que es donde mas se puede dejar rastro.
        _correr(destino, candidata, '--ciegas-esperadas', '99999')
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
    alta, candidata, _informe = _candidata(FIX.DUREZA_SUAVE)
    try:
        destino = _destino_temporal(alta)
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

    Y el motivo: sin el numero de ciegas, el procedimiento NO puede decir si
    la copia vale. Y un codigo de salida que significa «no se puede saber» y
    que devuelve cero, es un codigo que alguien va a leer como «todo bien».
    """
    alta, candidata, _informe = _candidata(FIX.DUREZA_SUAVE)
    try:
        destino = _destino_temporal(alta)
        antes = io.open(destino, 'rb').read()

        r = _correr(destino, candidata)
        assert r.returncode == 2, (
            'sin umbral el codigo tiene que ser el 2, y ha salido con %d'
            % r.returncode)
        assert 'INCOMPLETA' in r.stdout, r.stdout[-800:]
        assert io.open(destino, 'rb').read() == antes
    finally:
        shutil.rmtree(alta, ignore_errors=True)
