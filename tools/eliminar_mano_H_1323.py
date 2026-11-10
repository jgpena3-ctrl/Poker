# -*- coding: utf-8 -*-
"""Elimina H_1323 de la base canonica.

H_1323 es la mano fantasma que crea el recorder al arrancar en un frame de
resultado (ver `recorder/recorder_live.py`, comentario de H_1323). No tiene
ganador, su bote es 1.0 y repite la mesa, el tablero y los stacks de H_1322:
es una duplicacion de la captura de H_1322, no una mano jugada.

La mano se guarda en `data/_eliminadas/H_1323.jsonl` antes de quitarla, y la
base completa queda en el backup. Con `--restore` vuelve a entrar.

Uso:
    python tools/eliminar_mano_H_1323.py            # dry-run
    python tools/eliminar_mano_H_1323.py --apply    # escribe con backup
    python tools/eliminar_mano_H_1323.py --restore  # vuelve al backup
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, 'data', 'hands_db.jsonl')
BACKUP_DIR = os.path.join(ROOT, 'data', '_backup_eliminar_H_1323')
BACKUP_PATH = os.path.join(BACKUP_DIR, 'hands_db.jsonl')
ELIMINADAS_DIR = os.path.join(ROOT, 'data', '_eliminadas')
ELIMINADA_PATH = os.path.join(ELIMINADAS_DIR, 'H_1323.jsonl')
HAND_ID = 'H_1323'
DUPLICADA_DE = 'H_1322'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def leer_lineas(path):
    with io.open(path, encoding='utf-8') as f:
        return f.readlines()


def buscar(lineas, hand_id):
    for i, linea in enumerate(lineas):
        if not linea.strip():
            continue
        h = json.loads(linea)
        if h.get('hand_id') == hand_id:
            return i, h
    return None, None


def resumen(h):
    return {
        'date': h.get('date'),
        'winner': h.get('winner'),
        'final_pot': h.get('final_pot'),
        'players': [(p.get('pos'), p.get('name')) for p in
                    (h.get('players') or [])],
        'acciones': sum(len((d or {}).get('actions') or [])
                        for d in (h.get('streets') or {}).values()),
    }


def verificar_duplicacion(h1322, h1323):
    if h1323.get('winner'):
        raise ValueError('H_1323 ya tiene ganador; no parece la mano fantasma')
    if not (h1323.get('recorder_audit') or {}).get('fold_win'):
        raise ValueError('H_1323 no esta marcada como fold_win; revisar')
    if h1322 is None:
        raise ValueError('no encuentro H_1322, la mano de la que H_1323 '
                         'seria duplicado')
    if h1322.get('comunitarias') != h1323.get('comunitarias'):
        raise ValueError('H_1322 y H_1323 no comparten tablero; revisar')
    p2 = {(p.get('pos'), p.get('name')) for p in (h1322.get('players') or [])}
    p3 = {(p.get('pos'), p.get('name')) for p in (h1323.get('players') or [])}
    if p2 != p3:
        raise ValueError('H_1322 y H_1323 no comparten jugadores; revisar')


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


def aplicar(lineas, idx, h1323, linea_original):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(ELIMINADAS_DIR, exist_ok=True)
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
    with io.open(ELIMINADA_PATH, 'w', encoding='utf-8', newline='\n') as f:
        f.write(linea_original if linea_original.endswith('\n')
                else linea_original + '\n')
    salida = [linea for i, linea in enumerate(lineas) if i != idx]
    tmp = escribir_atomico(salida, DB_PATH)
    try:
        os.replace(tmp, DB_PATH)
    except Exception:
        os.remove(tmp)
        shutil.copy2(BACKUP_PATH, DB_PATH)
        raise
    print('archivo   : %s' % os.path.relpath(ELIMINADA_PATH, ROOT))
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

    lineas = leer_lineas(DB_PATH)
    idx, h1323 = buscar(lineas, HAND_ID)
    _, h1322 = buscar(lineas, DUPLICADA_DE)

    print('=' * 78)
    print('ELIMINAR %s (duplicado de %s)' % (HAND_ID, DUPLICADA_DE))
    print('=' * 78)
    if idx is None:
        print('%s no esta en la base: nada que eliminar.' % HAND_ID)
        return 0
    verificar_duplicacion(h1322, h1323)
    print('manos en la base: %d' % len([l for l in lineas if l.strip()]))
    print()
    print('  %-7s %s' % (DUPLICADA_DE, resumen(h1322)))
    print('  %-7s %s' % (HAND_ID, resumen(h1323)))
    print()
    print('  se quitara %s; queda una copia en %s'
          % (HAND_ID, os.path.relpath(ELIMINADA_PATH, ROOT)))
    print()
    if not args.apply:
        print('dry-run: no se ha escrito nada. Usa --apply para aplicar.')
        return 0
    return 0 if aplicar(lineas, idx, h1323, lineas[idx]) else 1


if __name__ == '__main__':
    raise SystemExit(main())
