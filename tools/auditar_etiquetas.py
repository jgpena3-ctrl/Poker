# -*- coding: utf-8 -*-
"""Auditoría P0-5: paridad de etiquetas entrenamiento vs serving (sombra).

Solo lectura. No cambia etiquetas efectivas, modelos ni recomendaciones.

Uso:
    python tools/auditar_etiquetas.py
    python tools/auditar_etiquetas.py --json
"""
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
    from motor.label_contract import label_audit  # noqa: E402


def _print_counts(title, counts):
    print(title)
    for key in sorted(counts):
        print('  %-28s %s' % (key, counts[key]))


def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    result = label_audit()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0

    print('P0-5 · PARIDAD DE ETIQUETAS (sombra)')
    print('commit:', result['code_commit'],
          'dirty:', result['code_dirty'])
    print('manos en ventana:', result['hands_in_window'])
    print('ventana:', result['window'], 'hash:', result['window_hash'])
    print('procedencia base:', result['base_provenance_status'])
    print()

    tr = result['training']
    print('== ENTRENAMIENTO (Profiles.simple_label) ==')
    print('  jugadores:', tr['players'])
    print('  etiquetas:', tr['labels'])
    print('  estados:', tr['states'])
    print()

    h = result['historical']
    print('== HISTORICO (data/profiles.json) ==')
    print('  jugadores:', h['players'],
          'comunes:', h['common_with_current'])
    print('  etiquetas coincidentes:', h['coincident'],
          'diferentes:', h['different'])
    print('  solo historicos:', h['only_historical'])
    print('  solo actuales:', h['only_current'])
    print('  procedencia:', h['provenance_status'],
          'hash canonico:', h['artifact_hash_matches'])
    d = h['evidence_diffs']
    print('  evidencia distinta: n=%s stats=%s stack=%s' % (
        d['n_different'], d['stats_different'],
        d['stack_mean_different']))
    print('  nota:', d['note'])
    print()

    _print_counts('== SERVING CON MEDIA DE SESION ==',
                  result['serving_session_mean']['counts'])
    print()
    _print_counts('== SERVING CON STACK ACTUAL ==',
                  result['serving_current_stack']['counts'])
    print()

    print('== PARIDAD DE LA REGLA DE STACK (misma evidencia) ==')
    p = result['parity_stack_rule']
    print('  media: %s jugadores, errores=%s' % (
        p['same_evidence_mean']['players'],
        p['same_evidence_mean']['errors']))
    print('  stack actual: %s jugadores, errores=%s' % (
        p['same_evidence_last']['players'],
        p['same_evidence_last']['errors']))
    print()

    print('== MUESTRAS PEQUEÑAS SEÑALADAS ==')
    for s in result['small_samples']:
        if not s.get('available'):
            print('  %-14s NO DISPONIBLE' % s['player'])
            continue
        print('  %-14s label=%-7s state=%-18s n=%-3s mean=%-7s last=%-7s' % (
            s['player'], s['training']['label'], s['training']['state'],
            s['n_vpip_opportunities'], s['stack_mean_bb'],
            s['last_stack_bb']))
        print('      metodo:', s['training']['method'])
        print('      sesion-media:', s['comparison_session_mean']['status'],
              '-', s['comparison_session_mean']['reason'])
        print('      stack-actual:', s['comparison_current_stack']['status'],
              '-', s['comparison_current_stack']['reason'])
        print('      historico reproducible desde campos:',
              s['historical_label_reproducible_from_fields'])
    print()

    print('== DIFERENCIAS CON STACK ACTUAL (primeras 10) ==')
    for c in result['differences_current_stack'][:10]:
        print('  %-16s train=%-7s serve=%-7s %s' % (
            c['player'], c['training_label'], c['serving_label'],
            c['status']))
        print('      ', c['reason'])
    print()

    print('Nota: modo sombra; no se cambian etiquetas ni recomendaciones.')
    return 0


if __name__ == '__main__':
    raise SystemExit(run())
