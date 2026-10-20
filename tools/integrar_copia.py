# -*- coding: utf-8 -*-
"""EL PROCEDIMIENTO DE INTEGRACION, y su test.

Y esto NO se ejecuta contra la copia real hasta que A1 cierre la revision de
las 203 manos. Y la razon esta en el propio script: **el umbral de ciegas de
la copia no se puede fijar desde aqui**, porque sale de datos que A1 todavia
no ha validado. De modo que el script, sin umbral, dice que la ejecucion esta
INCOMPLETA y sale con codigo distinto de cero.

Y el intercambio de la base es con restauracion GARANTIZADA, y verificada por
sha: se copia el original a memoria, se escribe el otro, y en el `finally` se
vuelve a escribir el original y se comprueba su sha. Y si el sha no cuadra,
el script dice que no cuadra, en vez de callarse.
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_REL = 'data/hands_db.jsonl'
COPIA_REL = 'trabajo/hands_db_edicion.jsonl'

# Los valores de control de la base CANONICA, que es lo que se compara.
# MEDIDO, y estan en `DOCS/CONTRATO_ACCION_P.md` y en
# `motor/test_cm004.py`.
CONTROL_CIEGAS = 921
CONTROL_VIOLACIONES = 0

# Las doce categorias de la primera decision, y su recuento en la base
# canonica. MEDIDO, y es el valor contra el que se compara la copia.
CONTROL_CATEGORIAS = {
    '3bet': 95, '4bet': 2, 'bb_check': 340, 'call_3bet': 17,
    'call_limp': 315, 'call_open': 603, 'fold': 2146, 'fold_vs_3bet': 142,
    'fold_vs_open': 1501, 'limp': 571, 'open': 595, 'rol': 254, 'squeeze': 33,
}


def _sha(bruto):
    return hashlib.sha256(bruto).hexdigest()


def _cargar(ruta):
    manos = []
    with io.open(ruta, encoding='utf-8') as f:
        for l in f:
            if l.strip():
                import json
                manos.append(json.loads(l))
    return manos


def medir(ruta_db):
    """Lo que el motor dice de una base: errores, ciegas, violaciones y
    categorias.

    Y los errores se CUENTAN, no se propagan: lo que se busca es saber
    cuantos hay, y un error en la primera mano no puede impedir medir las
    demas.
    """
    sys.path.insert(0, ROOT)
    from motor import learn
    import collections

    manos = _cargar(ruta_db)
    errores = []
    categorias = collections.Counter()
    ciegas = 0
    for h in manos:
        try:
            for e in learn.preflop_events(h):
                categorias[e.category] += 1
        except Exception as e:                   # noqa: BLE001
            errores.append((h.get('hand_id'), type(e).__name__, str(e)[:80]))
        seq = learn._preflop_sequence(h)
        if any(learn._es_ciega_bb(i, p, a, m, b, False)
               for i, (p, a, m, b) in enumerate(seq)):
            ciegas += 1
    violaciones = learn.manos_con_orden_ciega_malo(manos)
    return {
        'manos': len(manos),
        'errores': errores,
        'ciegas': ciegas,
        'violaciones': len(violaciones),
        'categorias': dict(categorias),
    }


def _guardianes(destino):
    """Los dos guardianes, y solo si el destino es la base canonica.

    Y el motivo de la condicion: los dos guardianes leen SIEMPRE
    `data/hands_db.jsonl`, de modo que contra otro destino no se puede
    comprobar nada. Y es mejor decirlo que ejecutarlos en balde.
    """
    canonico = os.path.abspath(os.path.join(ROOT, *DB_REL.split('/')))
    if os.path.abspath(destino) == canonico:
        destino_ = canonico
    else:
        # Y los guardianes PUEDEN mirar otro destino, con `POKER_DB_PATH`.
        destino_ = os.path.abspath(destino)
    salida = []
    entorno = dict(os.environ)
    entorno['POKER_DB_PATH'] = destino_
    for etiqueta, args in (
            ('vocabulario', ['motor/test_canal_manual.py::'
                             'test_la_base_no_usa_acciones_que_el_motor_no_conoce']),
            ('no vacuidad', ['motor/test_cm004.py::'
                             'test_el_invariante_de_cm004_puede_dispararse'])):
        r = subprocess.run([sys.executable, '-m', 'pytest'] + args + ['-q'],
                           cwd=ROOT, capture_output=True, text=True,
                           env=entorno)
        salida.append((etiqueta, 'OK' if r.returncode == 0 else
                       'FALLO (codigo %d)' % r.returncode))
    return salida


def integrar(origen, destino=None, umbral_ciegas=None, sha_esperada=None):
    """El procedimiento entero, y devuelve el informe.

    Y el `finally` es lo que garantiza la restauracion: se escribe el
    original SIEMPRE, se comprueba su sha, y si no cuadra se dice.

    Y el umbral de ciegas de la copia es OPCIONAL y, si no se da, el
    informe dice que la ejecucion esta incompleta. Porque el umbral sale de
    datos que todavia no son canonicos, y un umbral inventado seria un numero
    que nadie ha medido.

    Y el sha esperado de la CANDIDATA se comprueba ANTES del intercambio, de
    modo que una candidata que no es la que se cree falla **sin tocar la
    base**. Y si no se da, no se comprueba: que el parametro es opcional, y
    que su ausencia se dice.
    """
    destino = destino or os.path.join(ROOT, *DB_REL.split('/'))
    origen = origen or os.path.join(ROOT, *COPIA_REL.split('/'))
    original = io.open(destino, 'rb').read()

    if sha_esperada is not None:
        real = _sha(io.open(origen, 'rb').read())
        if real != sha_esperada:
            return {
                'completo': False,
                'restaurado': True,
                'sha_correcta': False,
                'sha_de_la_candidata': real,
                'sha_esperada': sha_esperada,
                'intercambio': False,
            }
    sha_original = _sha(original)
    informe = {'completo': umbral_ciegas is not None, 'restaurado': False}
    try:
        shutil.copyfile(origen, destino)
        m = medir(destino)
        informe.update(m)
        informe['guardianes'] = _guardianes(destino)
        informe['categorias_iguales'] = (m['categorias'] == CONTROL_CATEGORIAS)
        informe['umbral_ciegas'] = umbral_ciegas
        if umbral_ciegas is not None:
            informe['ciegas_suficientes'] = m['ciegas'] >= umbral_ciegas
    finally:
        with io.open(destino, 'wb') as f:
            f.write(original)
        sha_tras = _sha(io.open(destino, 'rb').read())
        informe['restaurado'] = (sha_tras == sha_original)
        informe['sha_original'] = sha_original
        informe['sha_tras'] = sha_tras
    return informe


# Los codigos de salida, y lo que significan. Y estan aqui, y no en el
# `--help`, porque un codigo de salida que hay que mirar en un sitio es un
# codigo de salida que no se mira.
#
#   0  la integracion ha pasado todos los controles
#   1  ha fallado un control: errores, ciegas insuficientes o categorias
#   3  GRAVE: la base no se ha restaurado
#   4  la candidata no es la que se creia, y no se ha tocado la base
CODIGO_OK = 0
CODIGO_FALLO = 1
CODIGO_INCOMPLETA = 2
CODIGO_NO_RESTAURADA = 3
CODIGO_CANDIDATA_OTRA = 4


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='integrar_copia.py',
                                 description='Integra una base candidata y '
                                             'restaura la canonica. NO se '
                                             'ejecuta contra la copia real '
                                             'sin el visto bueno de A1.')
    ap.add_argument('--origen', default=None, help='la base candidata')
    ap.add_argument('--destino', default=None,
                    help='donde escribirla; por defecto la canonica')
    ap.add_argument('--umbral-ciegas', type=int, default=None,
                    help='el minimo de ciegas que la copia tiene que '
                         'reconocer. Lo fija A1 al cerrar las 203 manos, y '
                         'SIN el la ejecucion esta incompleta.')
    ap.add_argument('--sha-esperada', default=None,
                    help='el sha256 que la candidata tiene que tener. Se '
                         'comprueba ANTES de tocar la base.')
    args = ap.parse_args(argv)
    informe = integrar(args.origen, args.destino, args.umbral_ciegas,
                       args.sha_esperada)
    print('INFORME DE INTEGRACION')
    for k in ('completo', 'manos', 'errores', 'ciegas', 'violaciones',
              'categorias_iguales', 'ciegas_suficientes', 'restaurado'):
        if k in informe:
            print('   %-20s %r' % (k, informe[k]))
    if informe.get('errores'):
        print('   los primeros errores:')
        for e in informe['errores'][:5]:
            print('      %r' % (e,))
    # Y el MOTIVO, antes de decidir. Y el motivo de que el motivo vaya
    # primero: un informe que dice «un guardian ha fallado» sin decir cual no
    # dice nada, y quien lo lee tiene que volver a ejecutar para saber que
    # paso. Y aqui se sabe: los errores de clasificacion, con la mano.
    if informe.get('errores'):
        print('   ERRORES de clasificacion: %d' % len(informe['errores']))
        for e in informe['errores'][:5]:
            print('      %r' % (e,))
    for etiqueta, texto in informe.get('guardianes', []):
        print('   guardian %-14s %s' % (etiqueta, texto))

    # ------------------------------------------------------------------
    # Y EL ORDEN, y son TRES CLASES, y el criterio es: lo mas grave y lo
    # mas temprano primero, y lo que INVALIDA el veredicto antes que el
    # veredicto.
    # ------------------------------------------------------------------

    # 1. DE LA ENTRADA: la candidata no es la que se creia. Y es una negacion
    #    DEFINIDA, de modo que va antes que «incompleta». Y la base no se ha
    #    tocado: el sha se comprueba ANTES del intercambio.
    if informe.get('sha_correcta') is False:
        print('   LA CANDIDATA NO ES LA QUE SE CREIA.')
        print('   sha de la candidata: %s' % informe.get('sha_de_la_candidata'))
        print('   sha esperado        : %s' % informe.get('sha_esperada'))
        print('   Y la base NO se ha tocado: el sha se comprueba ANTES del '
              'intercambio.')
        return CODIGO_CANDIDATA_OTRA

    # 2. DEL INSTRUMENTO, y lo mas grave primero: la base no se ha restaurado.
    if not informe['restaurado']:
        print('   LA BASE NO SE HA RESTAURADO. El sha antes y despues no '
              'cuadran. ESTO ES GRAVE.')
        return CODIGO_NO_RESTAURADA

    # 3. DEL INSTRUMENTO, y lo que invalida el veredicto: sin el umbral de
    #    ciegas NO SE PUEDE DECIR si la copia vale, y eso es cierto aunque un
    #    guardian falle. Y al reves: dar un veredicto de «no vale» cuando lo
    #    que falta es un DATO llevaria a alguien a buscar un fallo que no esta
    #    en la candidata.
    if not informe['completo']:
        print('   INCOMPLETA: falta el umbral de ciegas, que lo fija A1. Y '
              'sin el, la ejecucion no puede decir si la copia es valida.')
        return CODIGO_INCOMPLETA

    # 4. DE LA CANDIDATA. Y un guardian que FALLA hace fallar la integracion:
    #    no se bendice una candidata que tripsa un guardian.
    #
    #    Y el caso del guardian de no vacuidad, que es el que va a fallar
    #    mientras la base y su constante no coincidan: y eso es DEL DISENO, y no
    #    un fallo. El 921 es el control de la base de HOY, de modo que contra una
    #    candidata con otro numero de ciegas falla, y tiene que fallar.
    if any(t.startswith('FALLO') for _e, t in informe.get('guardianes', [])):
        print('   UN GUARDIAN HA FALLADO, y la integracion no se da por buena.')
        return CODIGO_FALLO
    if informe.get('errores'):
        return CODIGO_FALLO
    if not informe.get('ciegas_suficientes', False):
        print('   EL NUMERO DE CIEGAS ES INSUFICIENTE para el umbral '
              'declarado.')
        return CODIGO_FALLO
    if not informe['categorias_iguales']:
        print('   LAS CATEGORIAS NO SON LAS DE CONTROL.')
        return CODIGO_FALLO
    return CODIGO_OK


if __name__ == '__main__':
    sys.exit(main())
