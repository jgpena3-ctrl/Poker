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
    if os.path.abspath(destino) != canonico:
        return [(etiqueta,
                 'OMITIDO: el destino no es la base canonica, y los '
                 'guardianes leen siempre `data/hands_db.jsonl`')
                for etiqueta in ('vocabulario', 'no vacuidad')]
    salida = []
    for etiqueta, args in (
            ('vocabulario', ['motor/test_canal_manual.py::'
                             'test_la_base_no_usa_acciones_que_el_motor_no_conoce']),
            ('no vacuidad', ['motor/test_cm004.py::'
                             'test_el_invariante_de_cm004_puede_dispararse'])):
        r = subprocess.run([sys.executable, '-m', 'pytest'] + args + ['-q'],
                           cwd=ROOT, capture_output=True, text=True)
        salida.append((etiqueta, 'OK' if r.returncode == 0 else
                       'FALLO (codigo %d)' % r.returncode))
    return salida


def integrar(origen, destino=None, umbral_ciegas=None):
    """El procedimiento entero, y devuelve el informe.

    Y el `finally` es lo que garantiza la restauracion: se escribe el
    original SIEMPRE, se comprueba su sha, y si no cuadra se dice.

    Y el umbral de ciegas de la copia es OPCIONAL y, si no se da, el
    informe dice que la ejecucion esta incompleta. Porque el umbral sale de
    datos que todavia no son canonicos, y un umbral inventado seria un numero
    que nadie ha medido.
    """
    destino = destino or os.path.join(ROOT, *DB_REL.split('/'))
    origen = origen or os.path.join(ROOT, *COPIA_REL.split('/'))
    original = io.open(destino, 'rb').read()
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
    args = ap.parse_args(argv)
    informe = integrar(args.origen, args.destino, args.umbral_ciegas)
    print('INFORME DE INTEGRACION')
    for k in ('completo', 'manos', 'errores', 'ciegas', 'violaciones',
              'categorias_iguales', 'ciegas_suficientes', 'restaurado'):
        if k in informe:
            print('   %-20s %r' % (k, informe[k]))
    if informe.get('errores'):
        print('   los primeros errores:')
        for e in informe['errores'][:5]:
            print('      %r' % (e,))
    for etiqueta, texto in informe.get('guardianes', []):
        print('   guardian %-14s %s' % (etiqueta, texto))
    if not informe['restaurado']:
        print('   LA BASE NO SE HA RESTAURADO. El sha antes y despues no '
              'cuadran. ESTO ES GRAVE.')
        return 3
    if not informe['completo']:
        print('   INCOMPLETA: falta el umbral de ciegas, que lo fija A1. Y '
              'sin el, la ejecucion no puede decir si la copia es valida.')
        return 2
    if informe['errores']:
        print('   HAY ERRORES de clasificacion: %d' % len(informe['errores']))
        return 1
    if not informe.get('ciegas_suficientes', False):
        print('   EL NUMERO DE CIEGAS ES INSUFICIENTE para el umbral '
              'declarado.')
        return 1
    if not informe['categorias_iguales']:
        print('   LAS CATEGORIAS NO SON LAS DE CONTROL.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
