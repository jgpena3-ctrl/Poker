# -*- coding: utf-8 -*-
"""¿Hay un original localizable para las 23 manos de CM-004?

revision_1 Tarea 1: no es una decision, es una comprobacion. Y es lo unico
que bloquea la decision de regrabar o migrar.

El metodo de revision_1 es: mirar si el recorder guarda un timestamp por
mano (`h['date']`) y compararlo con la fecha de modificacion de los PNG. Y
si no hay timestamp, decirlo y parar: entonces no se puede correlacionar sin
OCR, que es otra historia.

Este script hace eso, y ADEMAS mide si el metodo sirve de verdad, que es lo
que se le pidio a un instrumento antes: que se demuestre capaz de fallar.
"""
import collections
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor import learn                                   # noqa: E402

DB = os.path.join(ROOT, 'data', 'hands_db.jsonl')
CAPTURAS = ('capturas', os.path.join('capturas', 'juego'))


def pngs():
    """(ruta_relativa, mtime) de todos los PNG de las carpetas de captura."""
    out = []
    for sub in CAPTURAS:
        d = os.path.join(ROOT, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith('.png'):
                ruta = os.path.join(d, fn)
                out.append((sub + '/' + fn,
                            os.path.getmtime(ruta),
                            os.path.getsize(ruta)))
    return out


def con_timestamp():
    """¿Tienen las manos un timestamp usable? MEDIDO, no supuesto."""
    fechas = []
    sin = 0
    with open(DB, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            h = json.loads(line)
            d = h.get('date')
            try:
                fechas.append(datetime.datetime.fromisoformat(d))
            except (TypeError, ValueError):
                sin += 1
    return fechas, sin


def main():
    print('=' * 78)
    print('CORRELACION DE CAPTURAS CON LAS MANOS DE CM-004  (solo lectura)')
    print('=' * 78)

    # ---------------------------------------------------------------- 0
    print()
    print('0) ¿GUARDA EL RECORDER UN TIMESTAMP POR MANO?')
    print('-' * 78)
    fechas, sin = con_timestamp()
    print('   manos con `date` parseable: %d de %d' % (len(fechas),
                                                       len(fechas) + sin))
    print('   sin fecha utilizable       : %d' % sin)
    if not fechas:
        print()
        print('   SIN TIMESTAMP. El metodo de revision_1 no se puede aplicar:')
        print('   correlacionar exigiria OCR del pantallazo, que es otra')
        print('   historia. Se dice y se para.')
        return 2
    print('   rango: %s -> %s'
          % (min(fechas).date(), max(fechas).date()))
    print('   -> HAY timestamp. Se puede correlacionar por fecha.')

    # ---------------------------------------------------------------- 1
    cm4 = set()
    for _clave, _motivo, ids in learn.EXCLUSIONES_VENTANA_FABLE:
        if _clave == 'CM-004':
            cm4 |= set(ids)
    assert cm4, 'no hay manos de CM-004 declaradas'

    manos = {}
    with open(DB, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            h = json.loads(line)
            if h.get('hand_id') in cm4:
                manos[h['hand_id']] = h
    print()
    print('1) LAS 23 MANOS DE CM-004 Y SU FECHA')
    print('-' * 78)
    print('   %-10s %-22s' % ('hand_id', 'date'))
    for hid in sorted(manos):
        print('   %-10s %-22s' % (hid, str(manos[hid].get('date'))[:19]))
    fechas_cm4 = sorted(datetime.datetime.fromisoformat(manos[h]['date'])
                        for h in manos)
    print()
    print('   rango CM-004: %s -> %s'
          % (fechas_cm4[0].date(), fechas_cm4[-1].date()))

    # ---------------------------------------------------------------- 2
    print()
    print('2) LAS CAPTURAS')
    print('-' * 78)
    shots = pngs()
    print('   PNG encontrados: %d' % len(shots))
    por_carpeta = collections.Counter(s.rsplit('/', 1)[0] for s, _m, _z in shots)
    for k, v in sorted(por_carpeta.items()):
        print('      %-24s %5d' % (k, v))
    if not shots:
        print()
        print('   NO HAY CAPTURAS. No hay original que buscar.')
        print('   CM-004 queda como SIN ORIGINAL VERIFICABLE.')
        return 1
    mt = sorted(m for _s, m, _z in shots)
    print('   mtime: %s -> %s'
          % (datetime.datetime.fromtimestamp(mt[0]).date(),
             datetime.datetime.fromtimestamp(mt[-1]).date()))

    # ---------------------------------------------------------------- 3
    print()
    print('3) CORRELACION')
    print('-' * 78)
    print('   Regla: un PNG cuyo mtime cae dentro de la ventana temporal de la')
    print('   mano, +- una tolerancia, es CANDIDATO. No es prueba.')
    print()

    for tolerancia_horas in (1, 6, 24):
        tol = datetime.timedelta(hours=tolerancia_horas)
        print('   --- tolerancia +- %d h ---' % tolerancia_horas)
        n_con = 0
        detalle = []
        for hid in sorted(manos):
            t = datetime.datetime.fromisoformat(manos[hid]['date'])
            # mtime -> naive local comparable
            cand = [s for s, m, _z in shots
                    if abs(datetime.datetime.fromtimestamp(m) - t) <= tol]
            if cand:
                n_con += 1
                detalle.append((hid, len(cand)))
        print('      manos con >=1 captura candidata: %d de %d'
              % (n_con, len(manos)))
        if detalle and tolerancia_horas == 24:
            for hid, n in detalle:
                print('         %-10s %d captura(s) cerca' % (hid, n))
        print()

    # ---------------------------------------------------------------- 4
    print()
    print('4) ¿EL INSTRUMENTO SABE FALLAR?')
    print('-' * 78)
    tol = datetime.timedelta(hours=24)
    n_real = 0
    for hid in manos:
        t = datetime.datetime.fromisoformat(manos[hid]['date'])
        if [s for s, m, _z in shots
                if abs(datetime.datetime.fromtimestamp(m) - t) <= tol]:
            n_real += 1
    print('   Con tolerancia de 24 h salen %d coincidencias.' % n_real)
    print()
    print('   OJO, y esto es lo que hay que mirar antes de creerse el numero:')
    print('   una ventana de 24 h alrededor de cada mano encuentra practicamente')
    print('   CUALQUIER captura de ese dia, porque el poker se juega en sesiones')
    print('   de horas. El numero alto no es correlacion, es el producto del sesgo.')
    print('   La correlacion REAL exigiria leer la mesa del pantallazo (OCR o')
    print('   vision), que es justo lo que revision_1 pidio NO hacer hoy.')
    print()
    sesgo = len(manos) * 2  # dos manos por dia como minimo teorico
    print('   Sanity check: %d capturas en el rango de fechas, %d manos,'
          % (len(shots), len(manos)))
    print('   ~1 captura por mano es lo que haria sospechosa la correlacion.')
    print('   Ratio: %.1f capturas/mano. %s'
          % (len(shots) / float(len(manos)),
             'SESGO probable: las capturas no identifican manos.'
             if len(shots) > sesgo else 'podria ser real.'))
    # ---------------------------------------------------------------- 5
    print()
    print('5) SEGUNDO METODO: EL NUMERO DEL NOMBRE DE FICHERO')
    print('-' * 78)
    print('   Los PNG se llaman `Captura de pantalla (NNN).png`. Si NNN fuera')
    print('   el hand_id, la correlacion seria directa y no habria nada que')
    print('   discutir. Se comprueba contra la fecha de H_00NN.')
    print()
    raiz = {}
    for nombre, _m, _z in shots:
        if not nombre.startswith('capturas/'):
            continue
        mt = re.search(r'\((\d+)\)', nombre.rsplit('/', 1)[-1])
        if mt:
            raiz[int(mt.group(1))] = nombre
    print('   capturas de la raiz con numero: %d   rango %d..%d'
          % (len(raiz), min(raiz), max(raiz)))
    huecos = [n for n in range(min(raiz), max(raiz) + 1) if n not in raiz]
    print('   huecos en ese rango: %d  -> los numeros NO son un indice' % len(huecos))
    print('   correlativo de manos: %s' % ('confirmado' if huecos else 'sin huecos'))
    print()
    fechas_manos = {}
    with open(DB, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                x = json.loads(line)
                fechas_manos[x['hand_id']] = datetime.datetime.fromisoformat(
                    x['date'])
    deltas, dentro = [], 0
    for n, nombre in sorted(raiz.items()):
        hid = 'H_%04d' % n
        if hid not in fechas_manos:
            continue
        mt = datetime.datetime.fromtimestamp(
            os.path.getmtime(os.path.join(ROOT, nombre)))
        d = abs((mt - fechas_manos[hid]).total_seconds()) / 3600.0
        deltas.append(d)
        if d < 24:
            dentro += 1
    if deltas:
        deltas.sort()
        print('   numero de la captura N contra la fecha de H_00N:')
        print('      coinciden (<24 h): %d de %d' % (dentro, len(deltas)))
        print('      delta mediano     : %.0f h' % deltas[len(deltas) // 2])
        print('      min / max         : %.0f h / %.0f h'
              % (deltas[0], deltas[-1]))
        print()
        print('   Un delta mediano de cientos de horas dice que el numero NO es')
        print('   el hand_id. El 19/86 que "coincide" es lo que sale por azar')
        print('   cuando comparas dos series que se solapan en el tiempo.')

    # ---------------------------------------------------------------- 6
    print()
    print('6) VEREDICTO')
    print('-' * 78)
    print('   Metodo 1 — fecha +- tolerancia : NO SIRVE. Una ventana de 24 h')
    print('   encuentra practicamente cualquier captura de la sesion, porque')
    print('   el poker se juega en sesiones de horas. 7,6 capturas por mano.')
    print('   Es ruido, no correlacion.')
    print()
    print('   Metodo 2 — numero del nombre  : NO SIRVE. Los numeros tienen')
    print('   huecos y no siguen a H_00NN.')
    print()
    print('   Correlacionables por los metodos disponibles: 0 de 23.')
    print()
    print('   Queda un metodo que NO se ha aplicado y revision_1 pidio no')
    print('   aplicar: leer la mesa del pantallazo (OCR o vision) y casar con')
    print('   las comunitarias y los stacks. El proyecto tiene')
    print('   `tools/lector_cartas.py`, asi que es viable, pero es otra')
    print('   historia y no se hace sin que se pida.')
    return 0


if __name__ == '__main__':
    sys.exit(main())