# -*- coding: utf-8 -*-
"""Auditoría P0-4: procedencia y compatibilidad de modelos (sombra).

Solo lectura. No construye modelos, no bloquea consultas y no escribe datos.
Uso:
    python tools/auditar_procedencia.py
    python tools/auditar_procedencia.py --json
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

with contextlib.redirect_stdout(io.StringIO()):
    from motor.provenance_contract import audit_provenance  # noqa: E402


ARTIFACTS = (
    'profile_ranges.json',
    'postflop_ranges.json',
    'preflop_stats.json',
    'player_stats.json',
    'profiles.json',
    'behavior.json',
    'observations.json',
    'preflop_matrices.json',
    'hands_db.jsonl',
)


def _sha256(path):
    full = os.path.join(ROOT, 'data', path)
    if not os.path.exists(full):
        return None
    h = hashlib.sha256()
    with open(full, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _fmt_compatible(value):
    if value is True:
        return 'compatible'
    if value is False:
        return 'INCOMPATIBLE'
    return 'unknown'


def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    result = audit_provenance()
    result['artifact_hashes'] = {name: _sha256(name) for name in ARTIFACTS}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0

    print('P0-4 · PROCEDENCIA Y COMPATIBILIDAD (sombra)')
    print('commit:', result['code_commit'],
          'dirty:', result['code_dirty'])
    print('base hash:', result['database_hash'])
    print('manos fiables:', result['reliable_hands'])
    window = result['window']
    print('ventana:', window['window_id'], 'hash:', window['window_hash'])
    cw = result['calibration_window']
    print('calibration_window.status:', cw['calibration_window_status'])
    print('calibration_window.provenance_status:',
          cw['calibration_provenance_status'])
    print()

    print('== ENVELOPES ==')
    for e in result['envelopes']:
        print('  %-20s %-26s %-12s class=%-16s missing=%s' % (
            e['component'], e['origin'], e['status'],
            e.get('classification') or '-',
            ','.join(e['missing_fields']) or '-'))
        if e.get('artifact_hash_matches') is not None:
            print('      hash artefacto coincide con canonico:',
                  e['artifact_hash_matches'])
        if e['notes']:
            for note in e['notes']:
                print('      -', note)
    print()

    print('== MATRIZ DE COMPATIBILIDAD ==')
    for row in result['compatibility']:
        print('  %-20s vs %-20s -> %-13s scope=%s' % (
            row['left'], row['right'],
            _fmt_compatible(row['compatible']), row['scope']))
        print('      ', row['reason'])
    print()

    print('== CASOS DE MEZCLA (REPRODUCIBLES) ==')
    for case in result['mixture_cases']:
        print('  %-42s verdict=%-13s block=%s warn=%s' % (
            case['case'], case['verdict'],
            case['would_block'], case['would_warn']))
        for pair in case['pairs']:
            if pair['compatible'] is not True:
                print('      %s vs %s: %s (%s)' % (
                    pair['left'], pair['right'],
                    _fmt_compatible(pair['compatible']), pair['reason']))
    print()

    print('== HERRAMIENTAS AUXILIARES ==')
    for row in result['auxiliary_tools']:
        print('  %-22s class=%-16s apta_actual=%s separation=%s' % (
            row['tool'], row['classification'],
            row['suitable_for_current_analysis'],
            row['separation_of_modes']))
        for note in row['notes']:
            print('      -', note)
    print()

    print('== LECTORES DE ARTEFACTOS ==')
    for row in result['readers']:
        print('  %-30s %-32s checks=%s drops_oracle=%s' % (
            row['reader'], row['artifact'],
            row['checks_provenance'], row['drops_oracle']))
    print()

    print('== CACHES ==')
    for c in result['caches']:
        print('  %-42s key=%s' % (c['cache'], c['key']))
        print('      invalidar por:', c['invalidation_needed'])
    print()

    print('== PREFLOP MATRICES ==')
    pm = next(e for e in result['envelopes']
              if e['component'] == 'preflop_matrices')
    for note in pm['notes']:
        print('  -', note)
    print('  hash:', result['artifact_hashes']['preflop_matrices.json'])
    print()

    print('== HASHES DE ARTEFACTOS ==')
    for name, value in result['artifact_hashes'].items():
        print('  %-26s %s' % (name, value))
    print()
    print('Nota: modo sombra; no se bloquean consultas live.')
    return 0


if __name__ == '__main__':
    raise SystemExit(run())
