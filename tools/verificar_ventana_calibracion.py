# -*- coding: utf-8 -*-
"""Verifica de solo lectura la ventana de calibracion congelada.

Lee `data/calibration_window.json` y comprueba, sin escribir nada, que:

- el SHA-256 de la base coincide con el declarado;
- las primeras 900 lineas fisicas siguen dando el mismo conjunto valido;
- las 23 exclusiones CM-004 siguen siendo las mismas;
- los 877 IDs seleccionados y sus hashes de linea no han cambiado;
- el hash agregado de las lineas seleccionadas no ha cambiado.

Uso:
    python tools/verificar_ventana_calibracion.py
    python tools/verificar_ventana_calibracion.py --snapshot RUTA --db RUTA

Codigo de salida: 0 si todo coincide, 1 si hay cualquier diferencia.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = ROOT / 'data' / 'calibration_window.json'
DEFAULT_DB = ROOT / 'data' / 'hands_db.jsonl'


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _line_hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _build_window(db_bytes, snapshot):
    lines = db_bytes.splitlines(keepends=True)
    limit = int(snapshot['window']['reliable_hands_limit'])
    window = lines[:limit]
    excluded_ids = set(snapshot['window']['excluded_ids'])
    valid = []
    invalid = []
    selected = []
    excluded = []
    for line_no, raw in enumerate(window, 1):
        text = raw.decode('utf-8').strip()
        if not text:
            invalid.append({'line': line_no, 'reason': 'blank'})
            continue
        try:
            hand = json.loads(text)
        except Exception as exc:  # noqa: BLE001 - el verificador debe informar
            invalid.append({'line': line_no, 'reason': 'json', 'error': str(exc)})
            continue
        if 'players' not in hand or 'streets' not in hand:
            invalid.append({'line': line_no, 'reason': 'missing players/streets'})
            continue
        rec = {'hand_id': hand['hand_id'], 'line': line_no, 'sha256': _line_hash(raw)}
        valid.append(rec)
        if hand['hand_id'] in excluded_ids:
            excluded.append(rec)
        else:
            selected.append(rec)
    selected_raw = b''.join(window[r['line'] - 1] for r in selected)
    return {
        'lines_total': len(lines),
        'bytes': len(db_bytes),
        'base_sha256': _sha(db_bytes),
        'valid': valid,
        'invalid': invalid,
        'selected': selected,
        'excluded': excluded,
        'selected_count': len(selected),
        'selected_lines_sha256': _sha(selected_raw),
    }


def _compare(name, got, exp, problems):
    if got != exp:
        problems.append('%s: esperado %r, obtenido %r' % (name, exp, got))


def verify(snapshot_path, db_path):
    snapshot = json.loads(Path(snapshot_path).read_text(encoding='utf-8'))
    db_bytes = Path(db_path).read_bytes()
    got = _build_window(db_bytes, snapshot)
    base = snapshot['base']
    win = snapshot['window']
    problems = []

    _compare('base.sha256', got['base_sha256'], base['sha256'], problems)
    _compare('base.bytes', got['bytes'], base['bytes'], problems)
    _compare('base.lines_total', got['lines_total'], base['lines_total'], problems)

    exp_ids = list(win['selected_ids'])
    got_ids = [r['hand_id'] for r in got['selected']]
    _compare('window.selected_count', got['selected_count'], win['selected_count'], problems)
    if got_ids != exp_ids:
        first = next((i for i, (a, b) in enumerate(zip(got_ids, exp_ids)) if a != b),
                     min(len(got_ids), len(exp_ids)))
        problems.append('window.selected_ids: primera diferencia en indice %d '
                        '(esperado %r, obtenido %r)' %
                        (first, exp_ids[first:first + 3], got_ids[first:first + 3]))

    exp_excl = list(win['excluded_ids'])
    got_excl = [r['hand_id'] for r in got['excluded']]
    _compare('window.excluded_ids', got_excl, exp_excl, problems)
    _compare('window.invalid_lines', got['invalid'], win.get('invalid_lines', []), problems)

    exp_hashes = win['selected_line_hashes']
    got_hashes = {r['hand_id']: r['sha256'] for r in got['selected']}
    if got_hashes != exp_hashes:
        changed = [hid for hid in exp_ids if got_hashes.get(hid) != exp_hashes.get(hid)]
        problems.append('window.selected_line_hashes: %d linea(s) cambiada(s): %s' %
                        (len(changed), ', '.join(changed[:12])))

    exp_excl_hashes = win.get('excluded_line_hashes', {})
    got_excl_hashes = {r['hand_id']: r['sha256'] for r in got['excluded']}
    if got_excl_hashes != exp_excl_hashes:
        changed = [hid for hid in exp_excl if got_excl_hashes.get(hid) != exp_excl_hashes.get(hid)]
        problems.append('window.excluded_line_hashes: %d linea(s) cambiada(s): %s' %
                        (len(changed), ', '.join(changed[:12])))

    _compare('window.selected_lines_sha256', got['selected_lines_sha256'],
             win['selected_lines_sha256'], problems)
    return snapshot, got, problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--snapshot', default=str(DEFAULT_SNAPSHOT))
    ap.add_argument('--db', default=str(DEFAULT_DB))
    args = ap.parse_args(argv)
    snapshot, got, problems = verify(args.snapshot, args.db)
    print('VENTANA DE CALIBRACION: %s' % snapshot.get('status', 'sin estado'))
    print('  base      : %s' % got['base_sha256'])
    print('  lineas    : %d' % got['lines_total'])
    print('  validas   : %d' % len(got['valid']))
    print('  excluidas : %d' % len(got['excluded']))
    print('  ventana   : %d' % got['selected_count'])
    print('  hash      : %s' % got['selected_lines_sha256'])
    if problems:
        print('FALLO: la ventana o su procedencia han cambiado')
        for p in problems:
            print('  - %s' % p)
        return 1
    print('OK: la ventana coincide con el snapshot')
    return 0


if __name__ == '__main__':
    sys.exit(main())
