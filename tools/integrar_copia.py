# -*- coding: utf-8 -*-
"""EL PROCEDIMIENTO DE INTEGRACION, y su test.

Y esto NO se ejecuta contra la copia real hasta que A1 cierre la revision de
las 203 manos. Y la razon esta en el propio script: **el numero de ciegas de
la copia no se puede fijar desde aqui**, porque sale de datos que A1 todavia
no ha validado. De modo que el script, sin ese numero, dice que la ejecucion
esta INCOMPLETA y sale con codigo distinto de cero.

## LOS TRES RESULTADOS, Y POR QUE NO SE MEZCLAN

Y el informe separa tres cosas, y la separacion es el punto:

  1. **INTEGRIDAD TECNICA** — el motor puede leer la candidata, los invariantes
     se evaluan y la restauracion queda verificada. Y esto es lo que el
     script MIDE por si mismo.
  2. **DIFERENCIAS SEMANTICAS** — cambian `final_pot`, importes o categorias, y
     se cuantifica donde: que manos, y cuanto se mueve cada categoria. Y esto
     es INFORMACION, y se imprime SIEMPRE, tanto en verde como en rojo.
  3. **AUTORIZACION ESTADISTICA** — las diferencias han sido revisadas y hay
     una decision explicita sobre que se acepta. Y esto NO lo decide el
     script: lo declara A1.

> Y el punto donde se puede colar el falso verde, y el motivo de que no se
> pueda: **el control de las doce categorias es BLOQUEANTE**, y no hay ninguna
> forma de volverlo informativo. Pasarlo requiere un control DECLARADO, y el
> control por defecto —el de la base de hoy— es el de NEUTRALIDAD DE LA
> CODIFICACION, que es otra cosa. De modo que convertirlo en informativo no
> es una opcion del script: es una decision de A1, y queda escrita.

Y el intercambio de la base es con restauracion GARANTIZADA, y verificada por
sha: se copia el original a memoria, se escribe el otro, y en el `finally` se
vuelve a escribir el original y se comprueba su sha. Y si el sha no cuadra,
el script dice que no cuadra, en vez de callarse.
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_REL = 'data/hands_db.jsonl'
COPIA_REL = 'trabajo/hands_db_edicion.jsonl'

# Los valores de control de la base CANONICA, que es lo que se compara por
# defecto. MEDIDO, y estan en `DOCS/CONTRATO_ACCION_P.md` y en
# `motor/test_cm004.py`.
CONTROL_CIEGAS = 921
CONTROL_VIOLACIONES = 0

# Las doce categorias de la primera decision, y su recuento en la base
# canonica. MEDIDO, y es el valor contra el que se compara una candidata que
# SOLO cambia la codificacion.
CONTROL_CATEGORIAS = {
    '3bet': 86, 'bb_check': 348, 'call_3bet': 15,
    'call_limp': 322, 'call_open': 594, 'fold': 2211, 'fold_vs_3bet': 139,
    'fold_vs_open': 1471, 'limp': 564, 'open': 587, 'rol': 275, 'squeeze': 25,
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


def _cargar_bruto(bruto):
    return [json.loads(l) for l in bruto.decode('utf-8').splitlines()
            if l.strip()]


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


def _importes_de_decision(mano):
    """Los importes de las acciones que NO son una posta ni la ciega del BB.

    Y el motivo de que la ciega se excluya: en la base de hoy esta grabada
    como `b` y en la candidata como `p`, de modo que compararla «como
    decision» compararia una codificacion con otra. Y lo que se quiere medir
    es si los IMPORTES de las DECISIONES cambian.

    Y las dos reglas son las del MOTOR —`_preflop_sequence` y
    `_es_ciega_bb`—, y no una propia: que sea el motor el que diga cual es la
    ciega es lo unico que hace que la comparacion signifique algo.
    """
    sys.path.insert(0, ROOT)
    from motor import learn
    seq = learn._preflop_sequence(mano)
    salida = []
    for i, (pos, act, amount, is_blind) in enumerate(seq):
        if act == 'p':
            continue
        if learn._es_ciega_bb(i, pos, act, amount, is_blind, False):
            continue
        salida.append((pos, act, round(float(amount or 0.0), 6)))
    return salida


def _diferencias_semanticas(original_bruto, candidata_ruta):
    """Lo que la candidata cambia DEL DATO, y donde.

    Y no lo que cambia de la codificacion: las posts y la ciega son
    codificacion, y aqui se comparan las DECISIONES y los BOTES.

    Y el resultado es una lista de manos, no un numero: «cuanto se mueve» es
    informacion de A1, y «que manos» es lo que le sirve.
    """
    base = {h.get('hand_id'): h for h in _cargar_bruto(original_bruto)}
    botes, importes = [], []
    for h in _cargar(candidata_ruta):
        hb = base.get(h.get('hand_id'))
        if hb is None:
            continue
        if (abs(float(hb.get('final_pot') or 0.0)
                - float(h.get('final_pot') or 0.0)) > 1e-6):
            botes.append(h.get('hand_id'))
        if _importes_de_decision(hb) != _importes_de_decision(h):
            importes.append(h.get('hand_id'))
    return {'botes': botes, 'importes': importes}


def _delta_categorias(mencionadas, control):
    """La diferencia categoria a categoria, y SIEMPRE.

    Y el motivo de que el delta se imprima tanto cuando el veredicto es verde
    como cuando es rojo: un control que solo dice «las categorias no son las
    de control» no dice CUALES, y quien lo lee tiene que volver a ejecutar
    para saberlo.
    """
    claves = sorted(set(mencionadas) | set(control))
    salida = []
    for k in claves:
        a = control.get(k, 0)
        b = mencionadas.get(k, 0)
        if a != b:
            salida.append((k, a, b, b - a))
    return salida


def _guardianes(destino):
    """Los dos guardianes, y los dos miran la base que se les indica.

    Y el motivo de que el destino pueda ser otro: el procedimiento tiene que
    poder probarse contra un destino TEMPORAL, sin tocar la base canonica.
    Y se les dice con `POKER_DB_PATH`, que es una VARIABLE DE ENTORNO, y no
    un argumento, porque son tests de pytest y no se les puede pasar otra cosa.

    Y el segundo guardian NO es el control del 921, y el motivo es importante:
    el 921 es el control de regresion de la base de HOY, y durante una
    integracion el sitio de la canonica lo ocupa la CANDIDATA, que tiene otro
    numero de ciegas. De modo que alli el 921 no falla: es que NO DICE NADA.
    Y lo que se comprueba en su lugar es la NO VACUIDAD, que si tiene sentido
    en cualquier base: que la regla tenga algo que mirar.
    """
    salida = []
    entorno = dict(os.environ)
    entorno['POKER_DB_PATH'] = os.path.abspath(destino)
    for etiqueta, args in (
            ('vocabulario', ['motor/test_canal_manual.py::'
                             'test_la_base_no_usa_acciones_que_el_motor_no_conoce']),
            ('no vacuidad', ['motor/test_cm004.py::'
                             'test_el_invariante_tiene_algo_que_mirar'])):
        r = subprocess.run([sys.executable, '-m', 'pytest'] + args + ['-q'],
                           cwd=ROOT, capture_output=True, text=True,
                           env=entorno)
        salida.append((etiqueta, 'OK' if r.returncode == 0 else
                       'FALLO (codigo %d)' % r.returncode))
    return salida


def integrar(origen, destino=None, ciegas_esperadas=None, sha_esperada=None,
             control_categorias=None):
    """El procedimiento entero, y devuelve el informe.

    Y el `finally` es lo que garantiza la restauracion: se escribe el
    original SIEMPRE, se comprueba su sha, y si no cuadra se dice.

    Y el numero de ciegas de la candidata es OPCIONAL y, si no se da, el
    informe dice que la ejecucion esta incompleta. Porque el numero sale de
    datos que todavia no son canonicos, y un numero inventado seria una cifra
    que nadie ha medido.

    Y el numero es EXACTO y no un minimo, y el motivo es que el control tiene
    que discriminar: si el numero fuera un minimo, poner el numero de otra
    base daria verde, y un control que no puede fallar no es un control.

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
    # Y el control de las categorias: si no se DECLARA, no hay control, y
    # sin control no se puede bendecir una candidata. Y el valor por defecto
    # —las doce categorias de la base de HOY— es el control de NEUTRALIDAD
    # DE LA CODIFICACION, que es OTRA pregunta, de modo que usarlo por
    # defecto seria responder una que nadie ha hecho.
    #
    # Y por eso NO se usa por defecto: el procedimiento exige los dos
    # controles declarados, y el que declare cada uno es quien lo ha medido.
    declarado = control_categorias is not None
    if control_categorias is None:
        control_categorias = dict(CONTROL_CATEGORIAS)
    sha_original = _sha(original)
    informe = {
        'completo': (ciegas_esperadas is not None and declarado),
        'faltan_controles': [
            x for x, falta in (('el numero de ciegas',
                                ciegas_esperadas is None),
                               ('el control de las categorias',
                                not declarado)) if falta],
        'restaurado': False,
    }
    try:
        shutil.copyfile(origen, destino)
        m = medir(destino)
        informe.update(m)
        informe['diferencias'] = _diferencias_semanticas(original, destino)
        informe['guardianes'] = _guardianes(destino)
        informe['delta_categorias'] = _delta_categorias(m['categorias'],
                                                        control_categorias)
        informe['categorias_iguales'] = (m['categorias'] == control_categorias)
        informe['control_categorias'] = control_categorias
        informe['control_categorias_declarado'] = declarado
        informe['ciegas_esperadas'] = ciegas_esperadas
        if ciegas_esperadas is not None:
            informe['ciegas_iguales'] = (m['ciegas'] == ciegas_esperadas)
        # Y LA INTEGRIDAD TECNICA, en un solo booleano, porque de eso depende
        # si la autorizacion estadistica se evalua o no: no tiene sentido
        # autorizar estadisticamente una candidata que el motor no lee.
        informe['integridad_ok'] = (
            not m['errores']
            and not any(t.startswith('FALLO')
                        for _e, t in informe.get('guardianes', []))
            and (ciegas_esperadas is None or m['ciegas'] == ciegas_esperadas)
            and m['violaciones'] == CONTROL_VIOLACIONES)
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
#   1  ha fallado un control: errores, ciegas, violaciones o categorias
#   2  INCOMPLETA: falta el numero de ciegas, que lo fija A1
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
    ap.add_argument('--ciegas-esperadas', type=int, default=None,
                    help='el numero EXACTO de ciegas que la candidata tiene '
                         'que reconocer. Lo fija A1 al cerrar las 203 manos, '
                         'y SIN el la ejecucion esta incompleta.')
    ap.add_argument('--sha-esperada', default=None,
                    help='el sha256 que la candidata tiene que tener. Se '
                         'comprueba ANTES de tocar la base.')
    ap.add_argument('--control-categorias', default=None,
                    help='un JSON con las doce categorias que la candidata '
                         'tiene que dar. Por defecto, las de la base de hoy, '
                         'que es el control de NEUTRALIDAD DE LA CODIFICACION. '
                         'Y la copia normalizada los cambia legitimamente, '
                         'porque no es solo una re-codificacion: hay que '
                         'declarar las suyas.')
    args = ap.parse_args(argv)
    control = None
    if args.control_categorias:
        with io.open(args.control_categorias, encoding='utf-8') as f:
            control = json.load(f)
    informe = integrar(args.origen, args.destino, args.ciegas_esperadas,
                       args.sha_esperada, control)

    # ------------------------------------------------------------------
    # Y EL INFORME, Y LOS TRES RESULTADOS, Y POR QUE NO SE MEZCLAN.
    # ------------------------------------------------------------------
    print('INFORME DE INTEGRACION')
    print()
    print('1. INTEGRIDAD TECNICA')
    for k in ('completo', 'manos', 'errores', 'ciegas', 'violaciones',
              'restaurado'):
        if k in informe:
            print('   %-20s %r' % (k, informe[k]))
    if informe.get('errores'):
        print('   ERRORES de clasificacion: %d' % len(informe['errores']))
        for e in informe['errores'][:5]:
            print('      %r' % (e,))
    for etiqueta, texto in informe.get('guardianes', []):
        print('   guardian %-14s %s' % (etiqueta, texto))

    print()
    print('2. DIFERENCIAS SEMANTICAS  (informacion, no veredicto)')
    dif = informe.get('diferencias') or {}
    print('   manos con el BOTE distinto : %d' % len(dif.get('botes', [])))
    print('   manos con IMPORTES distintos: %d'
          % len(dif.get('importes', [])))
    for etiqueta, lista in (('bote', dif.get('botes', [])),
                             ('importes', dif.get('importes', []))):
        if lista:
            print('      y las primeras con el %s distinto: %r'
                  % (etiqueta, lista[:8]))
    if informe.get('delta_categorias'):
        print('   las CATEGORIAS que se mueven, y CUANTO:')
        for k, esperado, obtenido, delta in informe['delta_categorias']:
            print('      %-14s esperado %6d  obtenido %6d  %+d'
                  % (k, esperado, obtenido, delta))
    else:
        print('   las CATEGORIAS que se mueven: ninguna')

    print()
    print('3. AUTORIZACION ESTADISTICA  (la decision es de A1)')
    print('   control de ciegas declarado  : %r'
          % informe.get('ciegas_esperadas'))
    print('   control de categorias        : %s'
          % ('DECLARADO' if informe.get('control_categorias_declarado')
             else 'NO DECLARADO'))
    if informe.get('integridad_ok'):
        print('   la integridad tecnica ha pasado, de modo que la '
              'autorizacion ESTA EVALUADA:')
        print('   el control de las categorias es BLOQUEANTE, y no hay ninguna')
        print('   forma de volverlo informativo: pasarlo requiere un control')
        print('   DECLARADO, y decidir cual es, es de A1.')
    else:
        print('   LA INTEGRIDAD TECNICA NO HA PASADO, de modo que la '
              'autorizacion estadistica')
        print('   NO SE EVALUA: no tiene sentido autorizar estadisticamente')
        print('   una candidata que el motor no lee.')

    # ------------------------------------------------------------------
    # Y EL ORDEN, y son TRES CLASES, y el criterio es: lo mas grave y lo
    # mas temprano primero, y lo que INVALIDA el veredicto antes que el
    # veredicto.
    # ------------------------------------------------------------------

    # 1. DE LA ENTRADA: la candidata no es la que se creia. Y es una negacion
    #    DEFINIDA, de modo que va antes que «incompleta». Y la base no se ha
    #    tocado: el sha se comprueba ANTES del intercambio.
    if informe.get('sha_correcta') is False:
        print()
        print('   LA CANDIDATA NO ES LA QUE SE CREIA.')
        print('   sha de la candidata: %s' % informe.get('sha_de_la_candidata'))
        print('   sha esperado        : %s' % informe.get('sha_esperada'))
        print('   Y la base NO se ha tocado: el sha se comprueba ANTES del '
              'intercambio.')
        return CODIGO_CANDIDATA_OTRA

    # 2. DEL INSTRUMENTO, y lo mas grave primero: la base no se ha restaurado.
    if not informe['restaurado']:
        print()
        print('   LA BASE NO SE HA RESTAURADO. El sha antes y despues no '
              'cuadran. ESTO ES GRAVE.')
        return CODIGO_NO_RESTAURADA

    # 3. DEL INSTRUMENTO, y lo que invalida el veredicto: sin el numero de
    #    ciegas NO SE PUEDE DECIR si la copia vale, y eso es cierto aunque un
    #    guardian falle. Y al reves: dar un veredicto de «no vale» cuando lo
    #    que falta es un DATO llevaria a alguien a buscar un fallo que no esta
    #    en la candidata.
    if not informe['completo']:
        print()
        print('   INCOMPLETA: falta %s. Y sin %s, la ejecucion no puede decir '
              'si la candidata es valida.'
              % (', '.join(informe.get('faltan_controles', [])) or 'los controles',
                 'ellos' if len(informe.get('faltan_controles', [])) != 1
                 else 'el'))
        print('   Y el motivo de que sea INCOMPLETA y no FALLO: «no has '
              'decidido» no es «has fallado».')
        return CODIGO_INCOMPLETA

    # 4. DE LA CANDIDATA. Y un guardian que FALLA hace fallar la integracion:
    #    no se bendice una candidata que tripsa un guardian.
    if any(t.startswith('FALLO') for _e, t in informe.get('guardianes', [])):
        print()
        print('   UN GUARDIAN HA FALLADO, y la integracion no se da por buena.')
        return CODIGO_FALLO
    if informe.get('errores'):
        return CODIGO_FALLO
    if not informe.get('ciegas_iguales', False):
        print()
        print('   EL NUMERO DE CIEGAS NO ES EL DECLARADO: %d, y se esperaban '
              '%d.' % (informe.get('ciegas', -1),
                       informe.get('ciegas_esperadas') or -1))
        print('   Y el numero es EXACTO y no un minimo, porque un control que '
              'no puede fallar no es un control.')
        return CODIGO_FALLO
    if informe.get('violaciones', 0) != CONTROL_VIOLACIONES:
        print()
        print('   HAY %d MANOS CON LA CIEGA MAL ORDENADA, y el control es 0.'
              % informe['violaciones'])
        return CODIGO_FALLO
    if not informe['categorias_iguales']:
        print()
        print('   LAS CATEGORIAS NO SON LAS DEL CONTROL DECLARADO.')
        print('   Y si la candidata cambia los datos y no solo la '
              'codificacion, el control se declara con `--control-categorias`.')
        print('   Y mientras no se declare, este control BLOQUEA, y no se '
              'puede volver informativo: esa decision no es del script.')
        return CODIGO_FALLO
    return CODIGO_OK


if __name__ == '__main__':
    sys.exit(main())
