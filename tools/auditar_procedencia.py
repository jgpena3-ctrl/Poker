# -*- coding: utf-8 -*-
"""Auditoría P0-4: procedencia y compatibilidad de modelos (sombra)."""
import argparse
import contextlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

with contextlib.redirect_stdout(io.StringIO()):
    from motor.provenance_contract import (audit_provenance, all_envelopes,
                                           compatibility_matrix, cache_inventory)

import hashlib


def _sha256(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return None
    h = hashlib.sha256()
    with open(full, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    result = audit_provenance()
    # Añadir hashes de artefactos clave (solo lectura).
    result['artifact_hashes'] = {
        'profile_ranges.json': _sha256('data/profile_ranges.json'),
        'postflop_ranges.json': _sha256('data/postflop_ranges.json'),
        'behavior.json': _sha256('data/behavior.json'),
        'preflop_matrices.json': _sha256('data/preflop_matrices.json'),
        'hands_db.jsonl': _sha256('data/hands_db.jsonl'),
    }
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0
    print('P0-4 · PROCEDENCIA Y COMPATIBILIDAD (sombra)')
    print('commit:', result['code_commit'], 'dirty:', result['code_dirty'])
    print('base hash:', result['database_hash'])
    print('manos fiables:', result['reliable_hands'])
    print()
    print('== ENVELOPES ==')
    for e in result['envelopes']:
        print('  %-22s %-12s %-14s class=%-16s missing=%s' % (
            e['component'], e['origin'], e['status'],
            e.get('classification') or '-',
            ','.join(e['missing_fields']) or '-'))
        if e['notes']:
            for n in e['notes']:
                print('      -', n)
    print()
    print('== COMPATIBILIDAD ==')
    for row in result['compatibility']:
        print('  %s vs %s -> %s: %s' % (
            row['left'], row['right'], row['compatible'], row['reason']))
    print()
    print('== CACHES ==')
    for c in result['caches']:
        print('  %s: key=%s; invalidar por %s' % (
            c['cache'], c['key'], c['invalidation_needed']))
    print()
    print('== PREFLOP MATRICES ==')
    pm = next(e for e in result['envelopes']
              if e['component'] == 'preflop_matrices')
    for n in pm['notes']:
        print('  -', n)
    print('  hash:', result['artifact_hashes']['preflop_matrices.json'])
    print()
    print('Nota: modo sombra; no se bloquean consultas live.')
    return 0


if __name__ == '__main__':
    raise SystemExit(run())