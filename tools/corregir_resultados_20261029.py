# -*- coding: utf-8 -*-
"""Corrige dos victorias por fold mal marcadas como showdown (29/10).

- H_1314: el BB se juega el stack (150.8), MP/CO/BTN foldean y el SB no
  aparece. El bote final es el inflado (160.8) y el ganador es el BB, asi que
  el SB tuvo que foldear: falta su fold y `fold_win` debe ser true, no false.
- H_1324: en el turn UTG apuesta 7.7 y BTN y SB foldean; el ganador es UTG.
  El audit lo tenia como showdown (`fold_win: false`) y el bote final era el
  no inflado (23.2). Es una victoria por fold: `fold_win: true`, sin casilla
  `showdown`, bote inflado 30.9.

Se recalculan aportes, rake, bote y notas desde las acciones, con la misma
regla que `tools/corregir_resultados_20261104.py`.

Uso:
    python tools/corregir_resultados_20261029.py            # dry-run
    python tools/corregir_resultados_20261029.py --apply    # escribe con backup
    python tools/corregir_resultados_20261029.py --restore  # vuelve al backup
"""
import argparse
import copy
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, 'data', 'hands_db.jsonl')
BACKUP_DIR = os.path.join(ROOT, 'data', '_backup_corregir_resultados_20261029')
BACKUP_PATH = os.path.join(BACKUP_DIR, 'hands_db.jsonl')

sys.path.insert(0, ROOT)
from tools.corregir_resultados_20261104 import (  # noqa: E402
    calcular_bote, limpiar_notas, live_positions)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def leer_lineas(path):
    with io.open(path, encoding='utf-8') as f:
        return f.readlines()


def _aplicar_breakdown(hand, cambios):
    audit = hand.get('recorder_audit') or {}
    breakdown = calcular_bote(hand, fold_win=True)
    antes = {k: audit.get(k) for k in breakdown}
    for campo, valor in breakdown.items():
        audit[campo] = valor
    if any(abs(float(antes.get(k) or 0.0) - float(v or 0.0)) > 0.001
           for k, v in breakdown.items()):
        cambios.append('audit')
    notas_antes = copy.deepcopy(audit.get('ambiguities'))
    limpiar_notas(hand, breakdown)
    if audit.get('ambiguities') != notas_antes:
        cambios.append('notas')
    return breakdown


def corregir_h1314(hand):
    cambios = []
    pre = ((hand.get('streets') or {}).get('preflop') or {}).get(
        'actions') or []
    if not any(a.get('pos') == 'SB' and a.get('action') == 'f' for a in pre):
        pre.append({
            'pos': 'SB', 'action': 'f', 'amount': 0.0,
            'amount_type': 'observed', 'inferred': True})
        cambios.append('SB fold preflop')
    audit = hand.get('recorder_audit') or {}
    if audit.get('fold_win') is not True:
        audit['fold_win'] = True
        cambios.append('fold_win -> true')
    if hand.get('showdown'):
        hand['showdown'] = {}
        cambios.append('showdown -> vacio')
    live, _folded = live_positions(hand)
    if len(live) != 1:
        raise ValueError('H_1314: se esperaba un unico vivo, hay %s' % live)
    breakdown = _aplicar_breakdown(hand, cambios)
    if hand.get('final_pot') != breakdown['pot_calculated']:
        hand['final_pot'] = breakdown['pot_calculated']
        cambios.append('final_pot')
    return cambios


def corregir_h1324(hand):
    cambios = []
    audit = hand.get('recorder_audit') or {}
    if audit.get('fold_win') is not True:
        audit['fold_win'] = True
        cambios.append('fold_win -> true')
    if hand.get('showdown'):
        hand['showdown'] = {}
        cambios.append('showdown -> vacio')
    live, _folded = live_positions(hand)
    if len(live) != 1:
        raise ValueError('H_1324: se esperaba un unico vivo, hay %s' % live)
    breakdown = _aplicar_breakdown(hand, cambios)
    if hand.get('final_pot') != breakdown['pot_calculated']:
        hand['final_pot'] = breakdown['pot_calculated']
        cambios.append('final_pot')
    return cambios


CORRECTORES = {
    'H_1314': corregir_h1314,
    'H_1324': corregir_h1324,
}


def corregir_mano(hand):
    fn = CORRECTORES.get(hand.get('hand_id'))
    if fn is None:
        return None
    original = copy.deepcopy(hand)
    cambios = fn(hand)
    if hand == original:
        return None
    return {'hand_id': hand.get('hand_id'), 'cambios': cambios}


def construir_plan(db_path=DB_PATH):
    lineas = leer_lineas(db_path)
    nuevas = [None] * len(lineas)
    cambios = []
    for i, linea in enumerate(lineas):
        if not linea.strip():
            continue
        hand = json.loads(linea)
        detalle = corregir_mano(hand)
        if detalle is not None:
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
    print('RESULTADOS DE LA SECCION 2026-10-29')
    print('=' * 78)
    print('manos que cambian: %d' % len(cambios))
    print()
    for d in cambios:
        print('  %-7s %s' % (d['hand_id'], ', '.join(d['cambios'])))
    print()
    if not cambios:
        print('nada que cambiar: las dos manos ya estan corregidas.')
        return 0
    if not args.apply:
        print('dry-run: no se ha escrito nada. Usa --apply para aplicar.')
        return 0
    return 0 if aplicar(lineas, nuevas) else 1


if __name__ == '__main__':
    raise SystemExit(main())
