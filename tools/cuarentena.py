# -*- coding: utf-8 -*-
"""Cuarentena de la copia de trabajo: las manos que NO se usan mientras se
revisan.

La cuarentena NO toca `data/hands_db.jsonl` ni `motor/learn.py`. Es una lista
externa y una copia filtrada para seguir trabajando sin las manos pendientes:

    trabajo/cuarentena.jsonl              una linea por mano: motivos
    trabajo/hands_db_sin_cuarentena.jsonl copia sin esas manos

Motivos (salen de `trabajo/botes_aritmetica_revision.jsonl`):

  * `STACK`             alguna accion supera el stack
  * `NADA`              el bote no coincide con ninguna lectura
  * `ACCION_AMBIGUA:*`  bote unico pero acciones no unicas (con su causa)

Y, con `--desde-auditoria`, los defectos de estado de jugadores que no se
pueden reconstruir sin inventar la accion que falta:

  * `AUDITORIA:ACTIVO_SIN_ACCION`        nunca actua, ni foldea ni va all-in
  * `AUDITORIA:ACTIVO_SIN_ACCION_CALLE`  desaparece en una calle con acciones
  * `AUDITORIA:INACTIVO_QUE_ACTUA`        inactivo con acciones (H_0294)

Por que no se mete en `EXCLUSIONES_VENTANA_FABLE`: esa lista cambia la ventana
fiable de 877 manos y con ella las cifras publicadas. Adoptar la cuarentena en
el motor es una decision posterior a la revision, no un efecto de este script.

Uso:
    python tools/cuarentena.py --resumen
    python tools/cuarentena.py --escribir
    python tools/cuarentena.py --verificar
    python tools/cuarentena.py --desde-auditoria trabajo/auditoria_jugadores.json \
        --clases ACTIVO_SIN_ACCION,ACTIVO_SIN_ACCION_CALLE,INACTIVO_QUE_ACTUA \
        --escribir
"""
import argparse
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, 'trabajo', 'hands_db_edicion.jsonl')
TRAZA = os.path.join(ROOT, 'trabajo', 'botes_aritmetica_revision.jsonl')
SALIDA = os.path.join(ROOT, 'trabajo', 'cuarentena.jsonl')
SALIDA_DB = os.path.join(ROOT, 'trabajo', 'hands_db_sin_cuarentena.jsonl')


def cargar(path):
    with io.open(path, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def num(hid):
    m = re.match(r'H_(\d+)$', hid or '')
    return int(m.group(1)) if m else 0


def motivos(d):
    """Motivos de cuarentena de una entrada de `botes_aritmetica.jsonl`."""
    out = []
    if d.get('stack_violations'):
        out.append('STACK')
    if d.get('clase') == 'NADA':
        out.append('NADA')
    if d.get('clase') == 'ACCION_AMBIGUA':
        out.append('ACCION_AMBIGUA:%s' % (d.get('causa') or '?'))
    return out


def construir(traza, incluir=(), excluir=(), auditoria=None, clases=()):
    q = {}
    for d in traza:
        ms = motivos(d)
        if not ms:
            continue
        hid = d.get('hand_id')
        q[hid] = {
            'hand_id': hid,
            'motivos': ms,
            'clase': d.get('clase'),
            'causa': d.get('causa'),
        }
    for hid in incluir:
        if hid in excluir:
            continue
        q.setdefault(hid, {'hand_id': hid, 'motivos': ['MANUAL'],
                          'clase': None, 'causa': None})
    if auditoria:
        for clase in clases:
            for caso in (auditoria.get('clases') or {}).get(clase) or []:
                hid = caso.get('hand_id')
                if not hid or hid in excluir:
                    continue
                e = q.setdefault(hid, {
                    'hand_id': hid,
                    'motivos': [],
                    'clase': clase,
                    'causa': 'ausencia de accion no reconstruible',
                })
                motivo = 'AUDITORIA:%s' % clase
                if motivo not in e['motivos']:
                    e['motivos'].append(motivo)
    for hid in excluir:
        q.pop(hid, None)
    for e in q.values():
        e['motivos'] = sorted(set(e['motivos']))
    return q


def escribir(q, db=DB, salida=SALIDA, salida_db=SALIDA_DB):
    ids = set(q)
    with io.open(salida, 'w', encoding='utf-8', newline='\n') as f:
        for hid in sorted(ids, key=num):
            f.write(json.dumps(q[hid], ensure_ascii=False) + '\n')
    kept = removed = 0
    with io.open(db, encoding='utf-8') as src, \
            io.open(salida_db, 'w', encoding='utf-8', newline='\n') as dst:
        for line in src:
            if not line.strip():
                continue
            hid = json.loads(line).get('hand_id')
            if hid in ids:
                removed += 1
                continue
            dst.write(line if line.endswith('\n') else line + '\n')
            kept += 1
    return {'cuarentena': len(ids), 'quedan': kept, 'quitadas': removed,
            'salida': salida, 'salida_db': salida_db}


def resumen(q):
    cuentas = {}
    for d in q.values():
        for m in d['motivos']:
            clave = m.split(':', 1)[0]
            cuentas[clave] = cuentas.get(clave, 0) + 1
    total = len(q)
    print('CUARENTENA: %d manos' % total)
    for clave in ('STACK', 'NADA', 'ACCION_AMBIGUA', 'AUDITORIA', 'MANUAL'):
        if clave in cuentas:
            print('  %-16s %4d' % (clave, cuentas[clave]))
    causas = {}
    auditadas = {}
    for d in q.values():
        for m in d['motivos']:
            if m.startswith('ACCION_AMBIGUA:'):
                c = m.split(':', 1)[1]
                causas[c] = causas.get(c, 0) + 1
            elif m.startswith('AUDITORIA:'):
                c = m.split(':', 1)[1]
                auditadas[c] = auditadas.get(c, 0) + 1
    if causas:
        print('  ACCION_AMBIGUA por causa:')
        for c in sorted(causas):
            print('    %-12s %4d' % (c, causas[c]))
    if auditadas:
        print('  AUDITORIA por clase:')
        for c in sorted(auditadas):
            print('    %-28s %4d' % (c, auditadas[c]))
    return total


def verificar(q, db=DB, salida=SALIDA, salida_db=SALIDA_DB):
    ids = set(q)
    lista = cargar(salida)
    lids = {x.get('hand_id') for x in lista}
    filtradas = cargar(salida_db)
    fids = [h.get('hand_id') for h in filtradas]
    total = len(cargar(db))
    repetidas = len(fids) - len(set(fids))
    solapan = sorted(ids & set(fids))
    faltan = sorted(ids - lids)
    suma = len(ids) + len(fids)
    print('VERIFICACION')
    print('  en cuarentena        : %d' % len(ids))
    print('  en la copia filtrada : %d' % len(fids))
    print('  suma                 : %d (base: %d)' % (suma, total))
    print('  repetidas en filtrada: %d' % repetidas)
    print('  solapadas            : %d %s' % (len(solapan), solapan[:5]))
    print('  en lista y no en jsonl: %d %s' % (len(faltan), faltan[:5]))
    ok = (not repetidas and not solapan and not faltan and suma == total)
    print('  RESULTADO: %s' % ('OK' if ok else 'FALLA'))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', default=DB)
    ap.add_argument('--traza', default=TRAZA)
    ap.add_argument('--salida', default=SALIDA)
    ap.add_argument('--salida-db', default=SALIDA_DB)
    ap.add_argument('--incluir', default='',
                    help='ids extra separados por comas')
    ap.add_argument('--excluir', default='',
                    help='ids que salen de la cuarentena separados por comas')
    ap.add_argument('--desde-auditoria', default='',
                    help='JSON de auditar_rango.py con clases de jugadores')
    ap.add_argument('--clases', default='ACTIVO_SIN_ACCION,'
                                       'ACTIVO_SIN_ACCION_CALLE,'
                                       'INACTIVO_QUE_ACTUA',
                    help='clases de la auditoria que entran en cuarentena')
    ap.add_argument('--resumen', action='store_true')
    ap.add_argument('--escribir', action='store_true')
    ap.add_argument('--verificar', action='store_true')
    args = ap.parse_args(argv)

    incluir = [x.strip() for x in args.incluir.split(',') if x.strip()]
    excluir = [x.strip() for x in args.excluir.split(',') if x.strip()]
    clases = [x.strip() for x in args.clases.split(',') if x.strip()]
    auditoria = None
    if args.desde_auditoria:
        with io.open(args.desde_auditoria, encoding='utf-8') as f:
            auditoria = json.load(f)
    q = construir(cargar(args.traza), incluir, excluir, auditoria, clases)

    if args.verificar:
        return verificar(q, args.db, args.salida, args.salida_db)
    resumen(q)
    if args.escribir:
        r = escribir(q, args.db, args.salida, args.salida_db)
        print()
        print('ESCRITO')
        print('  lista    : %s' % r['salida'])
        print('  copia    : %s  (%d manos)' % (r['salida_db'], r['quedan']))
        print('  quitadas : %d' % r['quitadas'])
    else:
        print()
        print('  (sin --escribir: no se ha tocado ningun fichero)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
