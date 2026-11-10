# -*- coding: utf-8 -*-
"""Corrige la posicion del texto de `showdown.winner1`.

En 19 manos historicas el nombre del ganador es correcto pero la posicion que
lo precede no: casi todas dicen `MP (...)` cuando el jugador es el CO, y una
dice `CO (...)` cuando es el BTN. El pid de `winner` resuelve a la posicion
real, y el nombre resuelve a un unico jugador de la mesa; cuando ambas cosas
coinciden, el unico dato equivocado es la etiqueta.

Tambien repara textos mal formados cuando el nombre se puede extraer y su
posicion es la del ganador (p. ej. H_0322, que guarda el JSON como texto).

No se toca `winner`, ni el bote, ni las acciones. Si el nombre no resuelve a
un unico jugador, o su posicion no es la del ganador, la mano se deja como
esta y se informa: no se inventa.

Uso:
    python tools/corregir_showdown_posicion.py            # dry-run
    python tools/corregir_showdown_posicion.py --apply    # escribe con backup
    python tools/corregir_showdown_posicion.py --restore  # vuelve al backup
"""
import argparse
import copy
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, 'data', 'hands_db.jsonl')
BACKUP_DIR = os.path.join(ROOT, 'data', '_backup_corregir_showdown_posicion')
BACKUP_PATH = os.path.join(BACKUP_DIR, 'hands_db.jsonl')

sys.path.insert(0, ROOT)
from motor.multiway import posicion_de_id  # noqa: E402

PATRON = re.compile(r'^\s*([A-Za-z0-9_]+)\s*\((.+)\)\s*$')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def leer_lineas(path):
    with io.open(path, encoding='utf-8') as f:
        return f.readlines()


def resolver_nombre(hand, nombre):
    """Posicion unica del jugador con ese nombre, o (None, motivo)."""
    posiciones = sorted({p.get('pos') for p in (hand.get('players') or [])
                         if (p.get('name') or '') == nombre and p.get('pos')})
    if len(posiciones) == 1:
        return posiciones[0], None
    if not posiciones:
        return None, 'el nombre no resuelve a ningun jugador con posicion'
    return None, 'el nombre resuelve a varias posiciones: %s' % posiciones


def corregir_mano(hand):
    sh = hand.get('showdown') or {}
    w1 = sh.get('winner1')
    if not isinstance(w1, str):
        return None
    m = PATRON.match(w1)
    if m:
        prefijo, nombre = m.group(1), m.group(2)
        origen = '%s (%s)' % (prefijo, nombre)
    else:
        nombres = re.findall(r'\(([^()]+)\)', w1)
        if not nombres:
            return None
        prefijo, nombre = None, nombres[-1].strip()
        origen = w1
    actual, motivo = resolver_nombre(hand, nombre)
    if actual is None:
        return {'hand_id': hand.get('hand_id'), 'estado': 'omitida',
                'detalle': motivo}
    ganadores = {posicion_de_id(hand, w) for w in (hand.get('winner') or [])}
    ganadores.discard(None)
    if actual not in ganadores:
        return {'hand_id': hand.get('hand_id'), 'estado': 'omitida',
                'detalle': 'la posicion %s no es la del ganador %s'
                           % (actual, sorted(ganadores))}
    if prefijo == actual:
        return None
    sh['winner1'] = '%s (%s)' % (actual, nombre)
    return {'hand_id': hand.get('hand_id'), 'estado': 'cambiada',
            'de': origen,
            'a': sh['winner1']}


def construir_plan(db_path=DB_PATH):
    lineas = leer_lineas(db_path)
    nuevas = [None] * len(lineas)
    cambios = []
    omitidas = []
    for i, linea in enumerate(lineas):
        if not linea.strip():
            continue
        hand = json.loads(linea)
        original = copy.deepcopy(hand)
        detalle = corregir_mano(hand)
        if detalle is None:
            continue
        if detalle['estado'] == 'omitida':
            omitidas.append(detalle)
        elif hand != original:
            nuevas[i] = hand
            cambios.append(detalle)
    return lineas, nuevas, cambios, omitidas


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

    lineas, nuevas, cambios, omitidas = construir_plan()
    print('=' * 78)
    print('POSICION DEL TEXTO DE SHOWDOWN')
    print('=' * 78)
    print('manos que cambian: %d' % len(cambios))
    print('manos omitidas  : %d' % len(omitidas))
    print()
    for d in cambios:
        print('  %-7s %-22s -> %s' % (d['hand_id'], d['de'], d['a']))
    if omitidas:
        print()
        for d in omitidas:
            print('  OMITIDA %-7s %s' % (d['hand_id'], d['detalle']))
    print()
    if not cambios:
        print('nada que cambiar: las etiquetas ya coinciden con la posicion.')
        return 0
    if not args.apply:
        print('dry-run: no se ha escrito nada. Usa --apply para aplicar.')
        return 0
    return 0 if aplicar(lineas, nuevas) else 1


if __name__ == '__main__':
    raise SystemExit(main())
