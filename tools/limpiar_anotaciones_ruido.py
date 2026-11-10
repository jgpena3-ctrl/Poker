# -*- coding: utf-8 -*-
"""Limpia las anotaciones de ambiguedad en data/hands_db.jsonl.

Retira el ruido que solo invita a revisar falsos positivos:

- `capture` y `capture_sha256` de cada ambiguedad y de cada entrada de
  `ambiguous_actions`. Las capturas siguen guardadas en disco y en el indice
  `pruebas/.../index.jsonl`, por lo que no se pierde evidencia.
- `award_display_ignored`: los avisos de premio mostrado ya no son errores; la
  devolucion de la apuesta no igualada se gestiona sola.

Uso:
    python tools/limpiar_anotaciones_ruido.py            # dry-run
    python tools/limpiar_anotaciones_ruido.py --apply    # escribe con backup
    python tools/limpiar_anotaciones_ruido.py --restore  # vuelve al backup
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
BACKUP_DIR = os.path.join(ROOT, 'data', '_backup_limpiar_anotaciones_ruido')
BACKUP_PATH = os.path.join(BACKUP_DIR, 'hands_db.jsonl')
RUIDO = ('capture', 'capture_sha256')
AUDIT_RUIDO = ('award_display_ignored',)


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
    audit = hand.get('recorder_audit')
    if not isinstance(audit, dict):
        return False
    cambio = False
    for k in AUDIT_RUIDO:
        if k in audit:
            del audit[k]
            cambio = True
    for amb in (audit.get('ambiguities') or []):
        if isinstance(amb, dict):
            for k in RUIDO:
                if k in amb:
                    del amb[k]
                    cambio = True
    for aa in (audit.get('ambiguous_actions') or []):
        if isinstance(aa, dict):
            for k in RUIDO:
                if k in aa:
                    del aa[k]
                    cambio = True
    return cambio


def construir_plan(db_path=DB_PATH):
    lineas = leer_lineas(db_path)
    nuevas = [None] * len(lineas)
    tocadas = 0
    for i, linea in enumerate(lineas):
        if not linea.strip():
            continue
        hand = json.loads(linea)
        original = copy.deepcopy(hand)
        if limpiar_hand(hand) and hand != original:
            nuevas[i] = hand
            tocadas += 1
    return lineas, nuevas, tocadas


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

    lineas, nuevas, tocadas = construir_plan()
    print('=' * 78)
    print('LIMPIEZA DE ANOTACIONES CON CAPTURAS/RUIDO')
    print('=' * 78)
    print('manos que cambian: %d' % tocadas)
    print()
    if not tocadas:
        print('nada que cambiar: las notas ya estan limpias.')
        return 0
    if not args.apply:
        print('dry-run: no se ha escrito nada. Usa --apply para aplicar.')
        return 0
    return 0 if aplicar(lineas, nuevas) else 1


if __name__ == '__main__':
    raise SystemExit(main())
