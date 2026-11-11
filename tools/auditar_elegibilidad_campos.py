# -*- coding: utf-8 -*-
"""Auditoría P0-2: elegibilidad por campo y por observación, en sombra.

Lee `data/hands_db.jsonl` (ventana fiable de 877 por defecto, o base completa
con `--base`) y responde, sin tocar datos ni modelos:

  - qué campo está válido/inválido/ausente/derivado/ambiguo;
  - qué consumidor usa cada observación;
  - cuántas observaciones pasarían la política y cuántas no;
  - el desglose individual de las 126 observaciones Oracle de las 10 manos
    con acciones restringidas;
  - las 13 secuencias imposibles, por acción y por dependencia;
  - el caso H_0926 y el limp corto H_0832;
  - qué datos no se pueden determinar (y por tanto NO se activan);
  - la comparación marginal vs granular.

No escribe en `data/`. `--json` emite el informe completo. `--verify-no-change`
construye `build_models()` dos veces (con y sin hook de sombra) y compara los
hashes de los tres modelos.

Uso:
    python tools/auditar_elegibilidad_campos.py
    python tools/auditar_elegibilidad_campos.py --base
    python tools/auditar_elegibilidad_campos.py --json
    python tools/auditar_elegibilidad_campos.py --verify-no-change
"""
import argparse
import contextlib
import io
import json
import os
import sys
from collections import Counter

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

# `motor.asistente_live` imprime un resumen de plantillas al importarse. En
# modo `--json` eso contaminaría la salida.
with contextlib.redirect_stdout(io.StringIO()):
    from motor.asistente_live import build_models
    from motor.field_eligibility import (
        CONSUMER_ECONOMIC, CONSUMER_ORACLE_GRANULAR,
        CONSUMER_ORACLE_MARGINAL, CONSUMER_POSTFLOP_RANGE,
        CONSUMER_PREFLOP_STATS, CONSUMER_PROFILE_RANGE,
        CONSUMER_SHOWDOWN, CONSUMER_STACK, EligibilityShadow,
        collect_counts, field_summary, load_declared, model_fingerprint)
    from motor.learn import load_hands
    from motor.profile import Profiles

# Las 10 manos con acciones restringidas dentro de la ventana 877. Su desglose
# Oracle suma exactamente 126 observaciones.
ORACLE_126 = (
    'H_0005', 'H_0059', 'H_0214', 'H_0226', 'H_0327',
    'H_0357', 'H_0832', 'H_0834', 'H_0925', 'H_0926',
)


def _jsonable(obj):
    if isinstance(obj, Counter):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, set):
        return sorted(obj)
    return obj


def _consumer_rows(counts):
    rows = []
    for name in (CONSUMER_ORACLE_MARGINAL, CONSUMER_ORACLE_GRANULAR,
                 CONSUMER_POSTFLOP_RANGE, CONSUMER_PROFILE_RANGE,
                 CONSUMER_PREFLOP_STATS, CONSUMER_SHOWDOWN,
                 CONSUMER_STACK, CONSUMER_ECONOMIC):
        c = counts['consumers'].get(name) or {}
        rows.append((name, c))
    return rows


def _print_field_inventory(counts, declared):
    print('== CAMPOS: ESTADO POR MANO ==')
    for field, statuses in sorted(counts.get('field_summary', {}).items()):
        parts = ', '.join('%s=%d' % (k, v)
                          for k, v in sorted(statuses.items()))
        print('  %-20s %s' % (field, parts))
    print()
    print('== DEFECTOS DECLARADOS (B1-E) Y CONSUMIDORES ==')
    field_consumers = {
        'acciones': 'preflop_stats, profile_range, oracle, postflop_range',
        'bote': 'economic (EV/ROI/pot odds)',
        'tablero': 'oracle_granular, postflop_range, equity',
        'stack': 'stack_mean/label PEZ-TIBURON, oracle, rangos',
        'allin': 'EV/SPR futuro; NO usado por modelos actuales',
        'asientos': 'players_active; NO usado por Oracle/postflop actuales',
        'showdown_texto': 'W$SD; NO usado por Oracle/rangos',
        'recorder_audit': 'procedencia; NO usado por modelos',
    }
    for field, ids in sorted(
            (declared.field_level_exclusions or {}).items()):
        print('  %-18s %3d manos  -> %s'
              % (field, len(ids), field_consumers.get(field, '?')))
    print()


def _print_consumers(counts):
    print('== CONSUMIDORES: ANTES / DESPUÉS (sombra) ==')
    print('  %-22s %8s %8s %10s' % ('consumidor', 'antes', 'después',
                                    'restringidas'))
    for name, c in _consumer_rows(counts):
        before = c.get('before')
        after = c.get('after')
        restr = c.get('restricted')
        if before is None:
            continue
        print('  %-22s %8s %8s %10s' % (name, before, after, restr))
    post = counts['consumers'][CONSUMER_POSTFLOP_RANGE]
    print('    postflop: conocidas con cartas=%s, descartadas por board '
          'ausente=%s, contradicción streets/comunitarias=%s'
          % (post.get('known_with_cards'), post.get('dropped_by_absent_board'),
             post.get('contradiction_warning')))
    stack = counts['consumers'][CONSUMER_STACK]
    print('    stack: filas sin stack=%s, manos con algún nulo=%s, '
          'manos declaradas activas=%s, jugadores con nulo=%s'
          % (stack.get('restricted'), stack.get('null_stack_hands'),
             stack.get('declared_active_null_hands'),
             stack.get('players_with_null_stack')))
    print()


def _print_stats(counts):
    print('== TRANSITIONSTATS: SOLO LO QUE CAMBIA ==')
    any_row = False
    for stat, v in sorted(counts.get('stats', {}).items()):
        if not v.get('restricted'):
            continue
        any_row = True
        print('  %-14s antes=%-6s después=%-6s restringidas=%s'
              % (stat, v['before'], v['after'], v['restricted']))
    if not any_row:
        print('  (sin cambios)')
    print()


def _print_oracle_breakdown(counts):
    rows = counts.get('oracle_breakdown', {})
    total = Counter()
    print('== 126 OBSERVACIONES ORACLE: 10 MANOS CON ACCIONES RESTRINGIDAS ==')
    for hid in ORACLE_126:
        b = rows.get(hid)
        if not b:
            continue
        print('  %-8s total=%-3d directas=%-2d dependientes=%-2d '
              'codigo_restr=%-2d ambiguas=%-2d independientes=%-3d'
              % (hid, b['total'], b['directas'], b['dependientes'],
                 b['codigo_restringido'], b['ambiguas_no_activadas'],
                 b['independientes']))
        for k in ('total', 'directas', 'dependientes', 'codigo_restringido',
                  'ambiguas_no_activadas', 'independientes'):
            total[k] += b[k]
    print('  %-8s total=%-3d directas=%-2d dependientes=%-2d '
          'codigo_restr=%-2d ambiguas=%-2d independientes=%-3d'
          % ('TOTAL', total['total'], total['directas'],
             total['dependientes'], total['codigo_restringido'],
             total['ambiguas_no_activadas'], total['independientes']))
    others = sorted(set(rows) - set(ORACLE_126))
    if others:
        print('  Otras manos declaradas fuera de la ventana: %s'
              % ', '.join(others))
        other_total = sum(rows[h]['total'] for h in others)
        print('  Observaciones Oracle de esas manos: %d (no forman parte '
              'del desglose de 126).' % other_total)
    print()


def _print_hard_sequences(declared, counts, hands_by_id):
    from motor.field_eligibility import assess_hand
    print('== 13 SECUENCIAS IMPOSIBLES: ACCIÓN Y DEPENDENCIA ==')
    for hid in sorted(declared.hard_sequence):
        d = declared.hard_sequence[hid]
        h = hands_by_id.get(hid)
        print('  %-8s %-7s idx_declarado=%-2s %s'
              % (hid, d.get('street'), d.get('index'),
                 d.get('evidence', '')))
        if h is None:
            print('      -> (fuera del alcance de esta corrida)')
            continue
        he = assess_hand(h, declared)
        issues = [i for i in he.issues if i.severity == 'invalid']
        for i in issues:
            print('      -> %s idx_resuelto=%s %s (%s), dependientes=%d'
                  % (i.street, i.index, i.code, i.source,
                     sum(1 for x in he.dependent if x.root is i)))
    print()


def _print_boards(declared, counts, hands_by_id):
    print('== TABLERO: CONTRADICCIÓN / AUSENCIA ==')
    for hid in sorted(set(declared.board_contradiction)
                      | set(declared.board_missing)):
        h = hands_by_id.get(hid)
        if h is None:
            continue
        from motor.field_eligibility import assess_hand
        he = assess_hand(h, declared)
        parts = []
        for st in ('flop', 'turn', 'river'):
            b = he.boards[st]
            parts.append('%s:%s%s' % (
                st, b.status, '/contra' if b.contradiction else ''))
        print('  %-8s %s' % (hid, ' '.join(parts)))
    print()


def _print_special_cases(counts):
    print('== CASOS ESPECIALES ==')
    for hid in ('H_0926', 'H_0832'):
        b = counts.get('oracle_breakdown', {}).get(hid)
        if b:
            print('  %s: total=%d directas=%d dependientes=%d '
                  'codigo_restr=%d independientes=%d'
                  % (hid, b['total'], b['directas'], b['dependientes'],
                     b['codigo_restringido'], b['independientes']))
    print('  H_0926: solo se restringe la SB x de turn; el resto de sus '
          'observaciones siguen en Oracle/rangos.')
    print('  H_0832: el CO b 1.0 se lee como limp corto. En Oracle se '
          'restringe la celda preflop b; en preflop_stats/ProfileRange se '
          'usa como limp. No se descarta la mano.')
    print()


def _print_undetermined(counts):
    print('== DATOS NO DETERMINADOS (NO SE ACTIVAN) ==')
    c = Counter()
    for u in counts.get('undetermined', []):
        c[(u['code'], u['source'])] += 1
    for (code, source), n in sorted(c.items()):
        print('  %-28s %-16s %d' % (code, source, n))
    print('  Total: %d observaciones/acciones no determinadas.'
          % len(counts.get('undetermined', [])))
    print()


def _print_marginal_vs_granular(counts):
    m = counts['consumers'][CONSUMER_ORACLE_MARGINAL]
    g = counts['consumers'][CONSUMER_ORACLE_GRANULAR]
    print('== MARGINAL vs GRANULAR ==')
    print('  Oracle por_facing: antes=%s después=%s restringidas=%s'
          % (m['before'], m['after'], m['restricted']))
    print('    preflop=%s postflop=%s | directas=%s dependientes=%s '
          'código=%s'
          % (m.get('restricted_preflop', 0),
             m.get('restricted_postflop', 0),
             m.get('restricted_direct', 0),
             m.get('restricted_dependent', 0),
             m.get('restricted_code', 0)))
    print('  Oracle granular   : antes=%s después=%s restringidas=%s'
          % (g['before'], g['after'], g['restricted']))
    print('    acción postflop=%s sin tablero=%s'
          % (g.get('restricted_action', 0),
             g.get('restricted_board', 0)))
    print('  Granular no incluye preflop (acción/código); frente al marginal '
          'postflop agrega las observaciones sin tablero válido y mantiene '
          'las mismas restricciones de acción postflop.')
    print()


def _verify_no_change():
    """Construye los modelos dos veces y compara hashes."""
    print('== PRUEBA DE NO-CAMBIO (build_models) ==')
    a = build_models(verbose=False)
    fp_a = model_fingerprint(a.range_model, a.oracle, a.postflop_model)
    shadow = EligibilityShadow()
    b = build_models(verbose=False, eligibility_shadow=shadow)
    fp_b = model_fingerprint(b.range_model, b.oracle, b.postflop_model)
    # Recalcular el hash del primer build después del segundo: el hook de la
    # sombra no debe mutar modelos ya construidos.
    fp_a_after = model_fingerprint(a.range_model, a.oracle, a.postflop_model)
    for key in fp_a:
        same = fp_a[key] == fp_b[key]
        print('  %-26s %s  %s' % (key, 'IGUAL' if same else 'DISTINTO',
                                  fp_a[key]))
        if not same:
            raise SystemExit('La sombra cambió %s' % key)
        if fp_a[key] != fp_a_after[key]:
            raise SystemExit('La sombra mutó el primer build: %s' % key)
    print('  Los tres modelos son idénticos con y sin hook de sombra.')
    print('  El primer build tampoco cambia al construir el segundo.')
    print('  Informe de la sombra: %d observaciones Oracle, %d restringidas.'
          % (shadow.report['consumers'][CONSUMER_ORACLE_MARGINAL]['before'],
             shadow.report['consumers'][CONSUMER_ORACLE_MARGINAL][
                 'restricted']))
    print()
    return {'fingerprints': fp_a, 'same': True}


def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', action='store_true',
                    help='usar la base completa de 1344, no la ventana 877')
    ap.add_argument('--json', action='store_true', help='salida JSON')
    ap.add_argument('--verify-no-change', action='store_true',
                    help='construir modelos con/sin hook y comparar hashes')
    args = ap.parse_args(argv)

    hands = load_hands(reliable_only=not args.base)
    labels = {name: p.label
              for name, p in Profiles.from_hands(hands).profiles.items()}
    declared = load_declared()
    counts = collect_counts(hands, labels, declared)
    counts['field_summary'] = field_summary(hands, declared)
    counts['scope'] = 'base_1344' if args.base else 'ventana_877'
    counts['declared_counts'] = {
        k: len(v) for k, v in declared.field_level_exclusions.items()}
    # Las tablas declaradas (13 secuencias, 11 tableros) se analizan sobre la
    # base completa, aunque el alcance sea la ventana 877.
    all_hands = load_hands(reliable_only=False)
    hands_by_id = {h.get('hand_id'): h for h in all_hands}

    proof = None
    if args.verify_no_change:
        proof = _verify_no_change()

    payload = {'scope': counts['scope'], 'counts': _jsonable(counts),
               'declared_counts': counts['declared_counts'],
               'proof': proof}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print('P0-2 · ELEGIBILIDAD POR CAMPO · %s · %d manos'
          % (counts['scope'], len(hands)))
    print('Inventario: %s' % declared.path)
    print('Observaciones Oracle totales: %d' % counts['oracle_total'])
    print()
    _print_field_inventory(counts, declared)
    _print_consumers(counts)
    _print_stats(counts)
    _print_marginal_vs_granular(counts)
    _print_oracle_breakdown(counts)
    _print_hard_sequences(declared, counts, hands_by_id)
    _print_boards(declared, counts, hands_by_id)
    _print_special_cases(counts)
    _print_undetermined(counts)
    if proof:
        print('Prueba de no-cambio: %s' % ('OK' if proof['same'] else 'FALLO'))
    print('Nota: los conteos "después" son la proyección de la política; '
          'no se aplican a los modelos efectivos.')
    return 0


if __name__ == '__main__':
    raise SystemExit(run())
