# -*- coding: utf-8 -*-
"""Retira de las notas las ambiguedades que solo describen inferencias.

La base ya fue revisada a mano: las acciones inferidas se comprobaron y se
corrigieron los errores. A partir de aqui las notas historicas no deben seguir
avisando de reconstrucciones normales. El recorder SIGUE escribiendo estos
avisos en las manos nuevas, porque sirven para revisar posibles errores.

Se elimina:

- entradas de `recorder_audit.ambiguous_actions` marcadas con `inferred`;
- ambiguedades cuyo `code` es una reconstruccion (acciones inferidas desde el
  stack, orden bet/call inferido, call pendiente liquidado en la calle previa);
- la marca `ambiguous` de las acciones que solo eran ambiguas por ser inferidas.

Se conserva `inferred: true` en las acciones: es la procedencia de la accion y
los consumidores la usan. Tambien se conservan los desajustes reales
(`pot_read_vs_*`, `bet_read_vs_recorded`, `bet_vs_stack_disagreement`).

Uso:
    python tools/limpiar_notas_inferidas.py            # dry-run
    python tools/limpiar_notas_inferidas.py --apply    # escribe con backup
    python tools/limpiar_notas_inferidas.py --restore  # vuelve al backup
"""
import argparse
import copy
import hashlib
import io
import json
import os
import shutil
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, 'data', 'hands_db.jsonl')
BACKUP_DIR = os.path.join(ROOT, 'data', '_backup_limpiar_notas_inferidas')
BACKUP_PATH = os.path.join(BACKUP_DIR, 'hands_db.jsonl')
INFERENCE_CODES = frozenset((
    'street_actions_inferred_from_stack_delta',
    'street_inferred_from_stack_delta',
    'bet_call_order_inferred',
    'pending_call_settled_on_previous_street',
))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def leer_lineas(path):
    with io.open(path, encoding='utf-8') as f:
        return f.readlines()


def limpiar_hand(hand):
    """Devuelve (cambio, detalle)."""
    audit = hand.get('recorder_audit')
    if not isinstance(audit, dict):
        return False, None

    ambiguities = audit.get('ambiguities') or []
    ambiguous_actions = audit.get('ambiguous_actions') or []
    nuevas_amb = [a for a in ambiguities
                  if not (isinstance(a, dict)
                          and a.get('code') in INFERENCE_CODES)]
    nuevas_acc = [a for a in ambiguous_actions
                  if not (isinstance(a, dict) and a.get('inferred'))]

    acciones_limpiadas = 0
    for data in ((hand.get('streets') or {}).values()):
        for action in (data or {}).get('actions') or []:
            if action.get('ambiguous') and action.get('inferred'):
                del action['ambiguous']
                acciones_limpiadas += 1

    if (len(nuevas_amb) == len(ambiguities)
            and len(nuevas_acc) == len(ambiguous_actions)
            and acciones_limpiadas == 0):
        return False, None

    quitadas_amb = len(ambiguities) - len(nuevas_amb)
    quitadas_acc = len(ambiguous_actions) - len(nuevas_acc)
    audit['ambiguities'] = nuevas_amb
    audit['ambiguous_actions'] = nuevas_acc
    audit['ambiguous'] = bool(nuevas_amb or nuevas_acc)
    return True, {
        'hand_id': hand.get('hand_id'),
        'ambiguedades_inferidas': quitadas_amb,
        'acciones_inferidas': quitadas_acc,
        'marcas_ambiguous': acciones_limpiadas,
    }


def construir_plan(db_path=DB_PATH):
    lineas = leer_lineas(db_path)
    nuevas = [None] * len(lineas)
    cambios = []
    for i, linea in enumerate(lineas):
        if not linea.strip():
            continue
        hand = json.loads(linea)
        original = copy.deepcopy(hand)
        cambio, detalle = limpiar_hand(hand)
        if cambio and hand != original:
            nuevas[i] = hand
            cambios.append(detalle)
    return lineas, nuevas, cambios


def escribir_atomico(lineas, destino):
    d = os.path.dirname(destino)
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.hands_db_', suffix='.tmp')
    os.close(fd)
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        for linea in lineas:
            f.write(linea if linea.endswith('\n') else linea + '\n')
    with io.open(tmp, encoding='utf-8') as f:
        for n, linea in enumerate(f, 1):
            if linea.strip():
                try:
                    json.loads(linea)
                except ValueError as exc:
                    os.remove(tmp)
                    raise ValueError('temporal invalido en linea %d: %s'
                                     % (n, exc))
    return tmp


def aplicar(lineas, nuevas):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if os.path.exists(BACKUP_PATH):
        print('backup    : %s (existente, se conserva)'
              % os.path.relpath(BACKUP_PATH, ROOT))
        print('sha256    : %s' % sha256(BACKUP_PATH))
    else:
        shutil.copy2(DB_PATH, BACKUP_PATH)
        h_orig, h_back = sha256(DB_PATH), sha256(BACKUP_PATH)
        print('backup    : %s' % os.path.relpath(BACKUP_PATH, ROOT))
        print('sha256    : %s' % h_orig)
        print('verificado: %s' % ('OK, coinciden' if h_orig == h_back
                                 else 'FALLO, NO coinciden'))
        if h_orig != h_back:
            raise RuntimeError('el backup no coincide con el original; '
                               'abortando')
    salida = [linea if nuevas[i] is None
              else json.dumps(nuevas[i], ensure_ascii=False) + '\n'
              for i, linea in enumerate(lineas)]
    tmp = escribir_atomico(salida, DB_PATH)
    try:
        os.replace(tmp, DB_PATH)
    except Exception:
        os.remove(tmp)
        shutil.copy2(BACKUP_PATH, DB_PATH)
        raise
    print()
    print('aplicado. nuevo sha256: %s' % sha256(DB_PATH))
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true',
                    help='escribe los cambios (sin esto solo muestra el plan)')
    ap.add_argument('--restore', action='store_true',
                    help='restaura hands_db.jsonl desde el backup')
    args = ap.parse_args(argv)

    if args.restore:
        if not os.path.exists(BACKUP_PATH):
            raise SystemExit('no existe el backup: %s' % BACKUP_PATH)
        shutil.copy2(BACKUP_PATH, DB_PATH)
        print('restaurado %s' % DB_PATH)
        print('sha256: %s' % sha256(DB_PATH))
        return 0

    lineas, nuevas, cambios = construir_plan()
    print('=' * 78)
    print('LIMPIEZA DE NOTAS DE INFERENCIA')
    print('=' * 78)
    print('manos que cambian: %d' % len(cambios))
    print('ambiguedades inferidas quitadas: %d'
          % sum(c['ambiguedades_inferidas'] for c in cambios))
    print('acciones inferidas quitadas de ambiguous_actions: %d'
          % sum(c['acciones_inferidas'] for c in cambios))
    print('marcas ambiguous retiradas de acciones: %d'
          % sum(c['marcas_ambiguous'] for c in cambios))
    print()
    if not cambios:
        print('nada que cambiar: las notas ya estan limpias.')
        return 0
    if not args.apply:
        print('dry-run: no se ha escrito nada. Usa --apply para aplicar.')
        return 0
    return 0 if aplicar(lineas, nuevas) else 1


if __name__ == '__main__':
    raise SystemExit(main())
