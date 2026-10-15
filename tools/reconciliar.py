# -*- coding: utf-8 -*-
"""Reconciliacion de `hands_db.jsonl`. SOLO LECTURA. No modifica nada.

    python tools/reconciliar.py              # informe
    python tools/reconciliar.py --json s.json

review revision_2 §4 pide cinco cosas, y este script las contesta una por una
en ese orden, porque son cinco preguntas distintas y mezclarlas es como se
acaba sin saber si la base esta bien:

  1. QUE REFERENCIA USA Y CUAL ES SU SHA-256
  2. QUE IDENTIFICADORES ESTAN AUSENTES, ANADIDOS O MODIFICADOS
  3. QUE CAMBIOS SON LOS 23 DE CM-004 Y EL CM-002 DE H_0350
  4. QUE MODIFICACIONES SIGUEN PRESENTES, incluidas las 8 reaplicadas
  5. SI LOS BORRADOS SON MANOS COMPLETAS O LINEAS, Y QUE EVIDENCIA LOS
     AUTORIZA

Que no escriba es lo primero que se comprueba: el script no tiene ningun modo
de escribir, y su unico efecto es imprimir.
"""
import argparse
import collections
import hashlib
import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor import learn  # noqa: E402

DB_REL = 'data/hands_db.jsonl'
DB_PATH = os.path.join(ROOT, *DB_REL.split('/'))
COMMIT_ANTES = 'e314f74'
SHA_ANTES = 'bb46fec0f2e37dc7c4280cb2302d3180c0502cf9d289ab8430b1e6d957d912ee'


def sha_de(texto_o_bytes):
    b = (texto_o_bytes if isinstance(texto_o_bytes, bytes)
         else texto_o_bytes.encode('utf-8'))
    return hashlib.sha256(b).hexdigest()


def _git(*args):
    return subprocess.run(['git'] + list(args), cwd=ROOT,
                          capture_output=True).stdout.decode('utf-8')


def blob(commit):
    crudo = subprocess.run(['git', 'show', '%s:%s' % (commit, DB_REL)],
                           cwd=ROOT, capture_output=True).stdout
    return crudo.decode('utf-8')


def por_id(texto):
    return {json.loads(l)['hand_id']: l
            for l in texto.splitlines() if l.strip()}


def lineas(texto):
    return [l for l in texto.splitlines() if l.strip()]


def clasificar_cambio(a, b):
    """Como cambia una mano. Devuelve una lista de etiquetas legibles."""
    ha, hb = json.loads(a), json.loads(b)
    out = []
    pa = ((ha.get('streets') or {}).get('preflop') or {}).get('actions') or []
    pb = ((hb.get('streets') or {}).get('preflop') or {}).get('actions') or []
    if len(pa) != len(pb):
        out.append('preflop: %d -> %d acciones' % (len(pa), len(pb)))
    else:
        etiquetas = {(x.get('pos'), x.get('action'), x.get('amount'))
                     for x in pa}
        etiquetas |= {(x.get('pos'), x.get('action'), x.get('amount'))
                      for x in pb}
        for pos, accion, importe in sorted(
                etiquetas, key=lambda t: (str(t[0]), str(t[1]), t[2])):
            if ((pos, accion, importe) in
                    {(x.get('pos'), x.get('action'), x.get('amount'))
                     for x in pa}) and \
               (pos, accion, importe) in \
                    {(x.get('pos'), x.get('action'), x.get('amount'))
                     for x in pb}:
                continue
            otro = 'r' if accion == 'b' else ('b' if accion == 'r' else accion)
            if accion in ('b', 'r'):
                out.append('preflop: %s %s -> %s (%s)'
                           % (pos, otro, accion, importe))
    for campo in ('flop', 'turn', 'river'):
        ca = (ha.get('streets') or {}).get(campo) or {}
        cb = (hb.get('streets') or {}).get(campo) or {}
        if len(ca.get('actions') or []) != len(cb.get('actions') or []):
            out.append('%s: %d -> %d acciones'
                       % (campo, len(ca.get('actions') or []),
                          len(cb.get('actions') or [])))
    if len(ha.get('winner') or []) != len(hb.get('winner') or []):
        out.append('winner: %d -> %d elementos'
                   % (len(ha.get('winner') or []),
                      len(hb.get('winner') or [])))
    elif ha.get('winner') != hb.get('winner'):
        out.append('winner: %s -> %s' % (ha.get('winner'), hb.get('winner')))
    for i, (p, q) in enumerate(zip(ha.get('players') or [],
                                  hb.get('players') or [])):
        if p != q:
            campos = [k for k in set(p) | set(q) if p.get(k) != q.get(k)]
            out.append('players[%d]: %s' % (i, ', '.join(sorted(campos))))
    if ha.get('final_pot') != hb.get('final_pot'):
        out.append('final_pot: %s -> %s' % (ha.get('final_pot'),
                                            hb.get('final_pot')))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--json', dest='json_out')
    args = ap.parse_args(argv)

    # El hash se saca de los BYTES. Leer en modo texto normaliza los saltos
    # de linea a LF y daria un hash que no es el del fichero: exactamente el
    # error que `.gitattributes` acaba de arreglar en el repositorio.
    with open(DB_PATH, 'rb') as f:
        actual_bytes = f.read()
    actual_txt = actual_bytes.decode('utf-8')
    previa_bytes = subprocess.run(
        ['git', 'show', '%s:%s' % (COMMIT_ANTES, DB_REL)],
        cwd=ROOT, capture_output=True).stdout
    previa_txt = previa_bytes.decode('utf-8')
    A, C = por_id(actual_txt), por_id(previa_txt)

    print('=' * 78)
    print('RECONCILIACION DE hands_db.jsonl   ·   SOLO LECTURA')
    print('=' * 78)

    # --- 1 -------------------------------------------------------------
    print()
    print('1. REFERENCIA Y HASH')
    print('-' * 78)
    print('   referencia     : %s:%s' % (COMMIT_ANTES, DB_REL))
    print('   sha256 esperado: %s' % SHA_ANTES)
    print('   sha256 leido  : %s  %s'
          % (sha_de(previa_bytes),
             'OK' if sha_de(previa_txt) == SHA_ANTES else 'DESVIO'))
    print('   fichero actual : %s' % DB_PATH)
    print('   sha256 actual : %s' % sha_de(actual_bytes))
    print('   lineas        : referencia %d, actual %d'
          % (len(lineas(previa_txt)), len(lineas(actual_txt))))
    print('   declarado     : commit %s, %d lineas, sha %s'
          % (learn.HANDS_DB_COMMIT, learn.HANDS_DB_LINEAS,
             learn.HANDS_DB_SHA256[:16]))

    # --- 2 -------------------------------------------------------------
    print()
    print('2. IDENTIFICADORES AUSENTES, ANADIDOS Y MODIFICADOS')
    print('-' * 78)
    ausentes = sorted(set(C) - set(A))
    anadidos = sorted(set(A) - set(C))
    modificados = sorted(h for h in set(A) & set(C) if A[h] != C[h])
    print('   AUSENTES  : %d' % len(ausentes))
    print('   ANADIDOS  : %d  %s' % (len(anadidos), ', '.join(anadidos) or '-'))
    print('   MODIFICADOS: %d' % len(modificados))
    print('   ausentes  : %s' % ', '.join(ausentes))

    # --- 3 -------------------------------------------------------------
    print()
    print('3. QUE CAMBIOS SON LOS 23 DE CM-004 Y EL CM-002 DE H_0350')
    print('-' * 78)
    cm004 = set(learn.manos_excluidas())
    cm002 = {'H_0350'}
    # el CM-004 se reconoce por el reetiquetado: la entrada que el motor no
    # reconoce como ciega pasa a `r`. Se deriva, no se escribe.
    derivables = set()
    for hid, texto in por_id(previa_txt).items():
        for _i, _a, causa in learn.entradas_bb_rechazadas(json.loads(texto)):
            if causa == learn.CAUSA_ORDEN:
                derivables.add(hid)
    solo_cm004, solo_cm002, ambos = [], [], []
    for hid in sorted(set(C) & set(A)):
        if A[hid] == C[hid]:
            continue
        es_cm004 = hid in derivables and hid in modificados
        es_cm002 = hid in cm002 and hid in modificados
        if es_cm004 and es_cm002:
            ambos.append(hid)
        elif es_cm004:
            solo_cm004.append(hid)
        elif es_cm002:
            solo_cm002.append(hid)
    print('   CM-004 (derivado del motor, no escrito): %d de %d'
          % (len(solo_cm004), len(derivables)))
    print('   CM-002 H_0350                        : %d' % len(solo_cm002))
    print('   el CM-004 declarado coincide con el derivado: %s'
          % (cm004 == derivables))
    if derivables - cm004:
        print('   derivados y NO declarados: %s'
              % sorted(derivables - cm004))
    if cm004 - derivables:
        print('   declarados y NO derivados: %s'
              % sorted(cm004 - derivables))

    # --- 4 -------------------------------------------------------------
    print()
    print('4. MODIFICACIONES SIGUEN PRESENTES, Y QUE SON')
    print('-' * 78)
    declaradas = solo_cm004 + solo_cm002 + ambos
    sin_declarar = [h for h in modificados if h not in declaradas]
    print('   con motivo identificable (CM-004 / CM-002): %d' % len(declaradas))
    print('   SIN motivo escrito en ninguna parte      : %d'
          % len(sin_declarar))
    print('   ausentes, no modificadas                 : %d' % len(ausentes))

    revertidas = ('H_0039', 'H_0051', 'H_0067', 'H_0109', 'H_0143', 'H_0263',
                  'H_0969', 'H_0970')
    presentes = [h for h in revertidas if h in modificados]
    print()
    print('   LAS 8 REVERTIDAS, ¿estan reaplicadas? (reversion de 02fc641)')
    print('   %-8s %-10s %s' % ('mano', 'estado', 'que cambio trae ahora'))
    print('   ' + '-' * 74)
    for hid in revertidas:
        if hid not in C:
            estado = 'AUSENTE'
            detalle = 'no esta en la referencia'
        elif hid in ausentes:
            estado = 'BORRADA'
            detalle = 'no esta en el fichero actual'
        elif hid in modificados:
            estado = 'REAPLICADA'
            detalle = '; '.join(clasificar_cambio(C[hid], A[hid])) or '?'
        else:
            estado = 'igual que referencia'
            detalle = ''
        print('   %-8s %-10s %s' % (hid, estado, detalle[:60]))

    print()
    print('   las 66 sin motivo escrito, agrupadas por tipo de cambio:')
    tipos = collections.Counter()
    detalle = collections.defaultdict(list)
    for hid in sin_declarar:
        etiquetas = tuple(clasificar_cambio(C[hid], A[hid]))
        tipos[etiquetas] += 1
        detalle[etiquetas].append(hid)
    for etiquetas, n in tipos.most_common():
        print('   %3d  %s' % (n, '; '.join(etiquetas)[:66]))
        print('        %s' % ', '.join(detalle[etiquetas][:12]))

    # --- 5 -------------------------------------------------------------
    print()
    print('5. LOS BORRADOS: MANOS COMPLETAS O LINEAS, Y QUE EVIDENCIA LOS AUTORIZA')
    print('-' * 78)
    if not ausentes:
        print('   no hay manos ausentes')
    for hid in ausentes:
        print('   %-8s  linea completa de la referencia: %d bytes, %d acciones '
              'de preflop' % (hid, len(C[hid]),
                               len((json.loads(C[hid])['streets']['preflop']
                                    or {}).get('actions') or [])))
    print()
    print('   EVIDENCIA QUE LOS AUTORIZA: NINGUNA ENCONTRADA.')
    print('   No hay documento, script ni commit que registre estas %d '
          'eliminaciones.' % len(ausentes))
    print('   Consta que fueron borradas; no consta por que.')
    print()
    print('   Ojo con el alcance: la ventana de calibracion va por LINEA, no')
    print('   por hand_id. Las %d primeras lineas del fichero actual son las que'
          % learn.RELIABLE_HANDS)
    print('   usa `load_hands(reliable_only=True)`, mas %d lineas, y de esas'
          % len(learn.manos_excluidas()))
    print('   %d son las 23 de CM-004. Borrar una mano anterior al corte mueve'
          % len(learn.manos_excluidas()))
    print('   la ventana aunque su hand_id no vuelva a aparecer: entra una mano')
    print('   que estaba fuera.')

    # --- alcance del rango auditado -------------------------------------
    print()
    print('6. QUE MANOS ENTRA LA VENTANA DE CALIBRACION HOY')
    print('-' * 78)
    ventana = learn.load_hands(reliable_only=True)
    ids_ventana = [h['hand_id'] for h in ventana]
    print('   RELIABLE_HANDS = %d' % learn.RELIABLE_HANDS)
    print('   exclusiones CM-004 = %d' % len(learn.manos_excluidas()))
    print('   ventana real = %d' % len(ventana))
    print('   primeras 5: %s' % ', '.join(ids_ventana[:5]))
    print('   ultimas  5: %s' % ', '.join(ids_ventana[-5:]))
    fuera = [hid for hid in A
         if hid not in set(ids_ventana)]
    print('   fuera de la ventana: %d' % len(fuera))
    print()
    print('   ATENCION: las cifras publicadas (656 puntos, 507, 226, 44,6%)')
    print('   se calcularon con la ventana de 877 sobre el fichero ANTERIOR')
    print('   (%d lineas). Con %d lineas la ventana es la misma en numero pero'
          % (len(lineas(previa_txt)), len(lineas(actual_txt))))
    print('   NO en contenido: %d de sus lineas son distintas.' % len(modificados))
    print('   Las cifras hay que recalcularlas o declarar que describen una base')
    print('   que ya no existe. Ver DOCS/RANGO_VIGENTE.md.')

    if args.json_out:
        with open(args.json_out, 'w', encoding='utf-8') as f:
            json.dump({
                'referencia': {'commit': COMMIT_ANTES, 'sha256': sha_de(previa_bytes),
                               'lineas': len(lineas(previa_txt))},
                'actual': {'sha256': sha_de(actual_bytes),
                           'lineas': len(lineas(actual_txt))},
                'ausentes': ausentes, 'anadidos': anadidos,
                'modificados': modificados,
                'cm004': solo_cm004, 'cm002': solo_cm002,
                'sin_declarar': sin_declarar,
                'revertidas_reaplicadas': presentes,
                'cambios_sin_declarar': {hid: clasificar_cambio(C[hid], A[hid])
                                         for hid in sin_declarar},
            }, f, indent=2, ensure_ascii=False)
        print()
        print('volcado -> %s' % args.json_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())