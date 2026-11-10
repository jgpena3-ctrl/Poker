# -*- coding: utf-8 -*-
"""Aclara las anotaciones de bote de H_1303, H_1327 y H_1351.

Las tres manos tienen lecturas de mesa que ya no describen el cierre real:

- H_1303: se quito la accion repetida `CO r 6.2` del turn. El bote vivo queda
  en 29.0 (gross-rake), pero el bote adjudicado del showdown es 26.7 porque
  2.3 quedaron sin igualar. La lectura final 26.6 confirma 26.7.
- H_1327: UTG foldea voluntariamente en el turn sin apuesta; BTN es el unico
  vivo y no tiene que actuar. El audit seguia con los aportes de antes del
  fold y una nota de bote obsoleta. Se recalcula: 10.7 bruto, 10.4 de bote.
- H_1351: el calculo con las acciones es correcto (67.3). La lectura 50.4 se
  tomo antes de que terminaran las apuestas; se guarda como lectura
  incompleta, no como discrepancia ambigua.

No se toca `final_pot` ni las acciones. Las notas de bote se sustituyen por
`audit_notes` donde hace falta explicar la diferencia.

Uso:
    python tools/corregir_anotaciones_20261110.py            # dry-run
    python tools/corregir_anotaciones_20261110.py --apply    # escribe con backup
    python tools/corregir_anotaciones_20261110.py --restore  # vuelve al backup
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
BACKUP_DIR = os.path.join(ROOT, 'data', '_backup_corregir_anotaciones_20261110')
BACKUP_PATH = os.path.join(BACKUP_DIR, 'hands_db.jsonl')

sys.path.insert(0, ROOT)
from tools.corregir_resultados_20261104 import (  # noqa: E402
    calcular_bote, redondear2)

POT_CODES = ('pot_read_vs_calculated', 'pot_read_vs_contributions')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def leer_lineas(path):
    with io.open(path, encoding='utf-8') as f:
        return f.readlines()


def _actualizar_audit(hand, fold_win):
    audit = hand.get('recorder_audit') or {}
    breakdown = calcular_bote(hand, fold_win=fold_win)
    antes = {k: audit.get(k) for k in breakdown}
    for campo, valor in breakdown.items():
        audit[campo] = valor
    cambios = []
    if any(abs(float(antes.get(k) or 0.0) - float(v or 0.0)) > 0.001
           for k, v in breakdown.items()):
        cambios.append('audit')
    return audit, breakdown, cambios


def _quitar_notas_bote(audit):
    antes = list(audit.get('ambiguities') or [])
    audit['ambiguities'] = [n for n in antes
                            if not (isinstance(n, dict)
                                    and n.get('code') in POT_CODES)]
    audit['ambiguous'] = bool(audit['ambiguities']
                              or audit.get('ambiguous_actions'))
    return antes != audit['ambiguities']


def _poner_nota(audit, nota):
    notas = list(audit.get('audit_notes') or [])
    nuevas = [n for n in notas
              if not (isinstance(n, dict)
                      and n.get('code') == nota.get('code'))]
    nuevas.append(nota)
    if nuevas == notas:
        return False
    audit['audit_notes'] = nuevas
    return True


def _resolucion(audit, calc):
    read = audit.get('pot_read')
    tol = float(audit.get('ambiguity_tolerance') or 0.2)
    if not isinstance(read, (int, float)):
        return 'calculated'
    if abs(float(read) - calc) <= tol:
        return 'read_confirms_calculated'
    return 'ambiguous_read_mismatch'


def corregir_h1303(hand):
    audit, breakdown, cambios = _actualizar_audit(hand, fold_win=False)
    resolucion = _resolucion(audit, breakdown['pot_calculated'])
    if audit.get('pot_resolution') != resolucion:
        audit['pot_resolution'] = resolucion
        cambios.append('pot_resolution')
    if _quitar_notas_bote(audit):
        cambios.append('notas de bote')
    nota = {
        'code': 'pot_live_vs_awarded',
        'pot_live_calculated': breakdown['pot_live_calculated'],
        'pot_calculated': breakdown['pot_calculated'],
        'uncalled': breakdown['uncalled'],
        'pot_read': audit.get('pot_read'),
        'note': ('final_pot conserva el bote vivo (gross-rake); el bote '
                 'adjudicado del showdown es pot_calculated porque la parte '
                 'sin igualar se devuelve'),
    }
    if _poner_nota(audit, nota):
        cambios.append('audit_notes')
    return cambios


def corregir_h1327(hand):
    audit, breakdown, cambios = _actualizar_audit(hand, fold_win=True)
    resolucion = _resolucion(audit, breakdown['pot_calculated'])
    if audit.get('pot_resolution') != resolucion:
        audit['pot_resolution'] = resolucion
        cambios.append('pot_resolution')
    if _quitar_notas_bote(audit):
        cambios.append('notas de bote')
    return cambios


def corregir_h1351(hand):
    audit, breakdown, cambios = _actualizar_audit(hand, fold_win=False)
    if audit.get('pot_resolution') != 'read_incomplete_before_close':
        audit['pot_resolution'] = 'read_incomplete_before_close'
        cambios.append('pot_resolution')
    if audit.get('pot_read_quality') != 'incomplete':
        audit['pot_read_quality'] = 'incomplete'
        cambios.append('pot_read_quality')
    if _quitar_notas_bote(audit):
        cambios.append('notas de bote')
    nota = {
        'code': 'pot_read_incomplete_before_close',
        'street': 'river',
        'pot_read': audit.get('pot_read'),
        'pot_calculated': breakdown['pot_calculated'],
        'difference': redondear2(abs(float(audit.get('pot_read') or 0.0)
                                     - breakdown['pot_calculated'])),
        'note': ('la lectura se tomo antes de que terminaran las apuestas; '
                 'el calculo con las acciones es el correcto'),
    }
    if _poner_nota(audit, nota):
        cambios.append('audit_notes')
    return cambios


CORRECTORES = {
    'H_1303': corregir_h1303,
    'H_1327': corregir_h1327,
    'H_1351': corregir_h1351,
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
    print('ANOTACIONES DE BOTE: H_1303, H_1327, H_1351')
    print('=' * 78)
    print('manos que cambian: %d' % len(cambios))
    print()
    for d in cambios:
        print('  %-7s %s' % (d['hand_id'], ', '.join(d['cambios'])))
    print()
    if not cambios:
        print('nada que cambiar: las anotaciones ya estan claras.')
        return 0
    if not args.apply:
        print('dry-run: no se ha escrito nada. Usa --apply para aplicar.')
        return 0
    return 0 if aplicar(lineas, nuevas) else 1


if __name__ == '__main__':
    raise SystemExit(main())
