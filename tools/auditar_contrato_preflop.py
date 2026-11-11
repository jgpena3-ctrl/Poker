"""Auditoría P0-1: contrato preflop viejo-vs-nuevo, sin escribir en data/.

Lee `data/hands_db.jsonl` (ventana fiable de 877 por defecto), recorre los
eventos históricos y los estados de serving equivalentes, y cuenta:

  - las `b` >1BB y <=1BB de la ventana;
  - la paridad del adaptador legado con `learn.preflop_events`;
  - las diferencias declaradas del contrato estricto contra el entrenamiento;
  - las diferencias de `_preflop_spot` contra la primera decisión contextual;
  - las diferencias de `_preflop_raises` + limpe contra `table_plan`.

No modifica la base ni genera logs: imprime el resumen por pantalla. `--json`
emite el mismo informe como JSON para pegarlo en un documento.
"""
import argparse
import collections
import contextlib
import io
import json
import os
import sys

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

# `motor.asistente_live` imprime un resumen de plantillas al importarse. En
# modo `--json` eso contaminaría la salida; se captura solo durante el import.
with contextlib.redirect_stdout(io.StringIO()):
    from motor.asistente_live import _preflop_raises, _preflop_spot  # noqa: E402
    from motor.learn import load_hands, preflop_events  # noqa: E402
    from motor.preflop_contract import (actions_of, first_decision,  # noqa: E402
                                        table_plan, walk_preflop)


def _old_hero_state(actions, hero_pos):
    n, vs_pos, vs_amount = _preflop_raises(actions, hero_pos)
    limp = False
    raise_seen = False
    for a in actions:
        if a.get('pos') == hero_pos:
            continue
        if a.get('action') == 'r':
            raise_seen = True
        elif a.get('action') == 'c' and not raise_seen:
            limp = True
    return n, bool(limp), vs_pos, vs_amount


def _prefix_before(actions, pos):
    prefix = []
    for a in actions:
        if a.get('pos') == pos:
            break
        prefix.append(a)
    return prefix


def informe(hands, max_examples=8):
    res = {
        'hands': len(hands),
        'events': 0,
        'b_raw': {'total': 0, 'gt_1bb': 0, 'le_1bb': 0,
                  'cats': collections.Counter()},
        'legacy_training': {'same': 0, 'different': 0},
        'strict_vs_training': {'same': 0, 'different': 0,
                               'unresolved': 0,
                               'different_pairs': collections.Counter(),
                               'unresolved_pairs': collections.Counter()},
        'old_spot_vs_contract': {'same': 0, 'different': 0,
                                 'unresolved': 0,
                                 'different_pairs': collections.Counter(),
                                 'unresolved_pairs': collections.Counter()},
        'hero_old_vs_contract': {'same': 0, 'different': 0,
                                 'unresolved': 0,
                                 'different_pairs': collections.Counter()},
        'coverage': collections.Counter(),
        'examples': collections.defaultdict(list),
    }

    for hand in hands:
        for step in walk_preflop(hand):
            if step.raw.action != 'b':
                continue
            amount = step.raw.amount or 0.0
            bucket = 'gt_1bb' if amount > 1.0 else 'le_1bb'
            res['b_raw']['total'] += 1
            res['b_raw'][bucket] += 1
            cls = step.classification
            res['b_raw']['cats'][(bucket, cls.category, cls.status)] += 1

        actions = actions_of(hand)
        for ev in preflop_events(hand):
            res['events'] += 1
            legacy = first_decision(hand, ev.pos, legacy=True)
            if (legacy.category, legacy.denom) == (ev.category, ev.denom):
                res['legacy_training']['same'] += 1
            else:
                res['legacy_training']['different'] += 1

            strict = first_decision(hand, ev.pos)
            res['coverage'][strict.range_query_status] += 1
            if not strict.resolved:
                res['strict_vs_training']['unresolved'] += 1
                pair = (ev.category, strict.category, strict.reason)
                res['strict_vs_training']['unresolved_pairs'][pair] += 1
            elif (strict.training_category, strict.training_denom) != \
                    (ev.category, ev.denom):
                res['strict_vs_training']['different'] += 1
                pair = (ev.category, strict.training_category,
                        strict.category)
                res['strict_vs_training']['different_pairs'][pair] += 1
                if len(res['examples']['strict']) < max_examples:
                    res['examples']['strict'].append({
                        'hand_id': hand.get('hand_id'), 'pos': ev.pos,
                        'old': [ev.category, ev.denom],
                        'new': strict.as_dict()})
            else:
                res['strict_vs_training']['same'] += 1

            old_spot = _preflop_spot(hand, ev.pos)
            if not strict.resolved:
                res['old_spot_vs_contract']['unresolved'] += 1
                pair = (old_spot, strict.category, strict.reason)
                res['old_spot_vs_contract']['unresolved_pairs'][pair] += 1
            elif old_spot != (strict.denom, strict.category):
                res['old_spot_vs_contract']['different'] += 1
                pair = (old_spot, (strict.denom, strict.category))
                res['old_spot_vs_contract']['different_pairs'][pair] += 1
                if len(res['examples']['spot']) < max_examples:
                    res['examples']['spot'].append({
                        'hand_id': hand.get('hand_id'), 'pos': ev.pos,
                        'old': old_spot,
                        'new': strict.as_dict()})
            else:
                res['old_spot_vs_contract']['same'] += 1

            prefix = _prefix_before(actions, ev.pos)
            old_n, old_limp, old_vs, old_amount = _old_hero_state(
                prefix, ev.pos)
            plan = table_plan(prefix, ev.pos)
            if plan.status != 'resolved':
                res['hero_old_vs_contract']['unresolved'] += 1
            elif (old_n, old_limp, old_vs) != (
                    plan.raises_before, plan.limps_before > 0, plan.vs_pos):
                res['hero_old_vs_contract']['different'] += 1
                pair = ((old_n, old_limp, old_vs),
                        (plan.raises_before, plan.limps_before > 0,
                         plan.vs_pos),
                        plan.table_raise, plan.table_call)
                res['hero_old_vs_contract']['different_pairs'][pair] += 1
                if len(res['examples']['hero']) < max_examples:
                    res['examples']['hero'].append({
                        'hand_id': hand.get('hand_id'), 'pos': ev.pos,
                        'old': {'n_raises': old_n, 'limp': old_limp,
                                'vs_pos': old_vs,
                                'vs_amount': old_amount},
                        'new': plan.as_dict()})
            else:
                res['hero_old_vs_contract']['same'] += 1

    # Contadores -> JSON estable.
    for key in ('b_raw',):
        res[key]['cats'] = [
            {'bucket': k[0], 'category': k[1], 'status': k[2], 'n': n}
            for k, n in sorted(res[key]['cats'].items())]
    for key in ('strict_vs_training', 'old_spot_vs_contract'):
        for field in ('different_pairs', 'unresolved_pairs'):
            res[key][field] = [
                {'pair': str(k), 'n': n}
                for k, n in res[key][field].most_common()]
    res['hero_old_vs_contract']['different_pairs'] = [
        {'old': str(k[0]), 'new': str(k[1]), 'table_raise': k[2],
         'table_call': k[3], 'n': n}
        for k, n in res['hero_old_vs_contract']['different_pairs'].most_common()]
    res['coverage'] = dict(sorted(res['coverage'].items()))
    res['examples'] = dict(res['examples'])
    return res


def _print_human(r):
    print('manos: %d   eventos: %d' % (r['hands'], r['events']))
    print('b crudas: total=%d  >1BB=%d  <=1BB=%d' % (
        r['b_raw']['total'], r['b_raw']['gt_1bb'], r['b_raw']['le_1bb']))
    print('  categorías:', r['b_raw']['cats'])
    print('legado vs entrenamiento: same=%d different=%d' % (
        r['legacy_training']['same'], r['legacy_training']['different']))
    s = r['strict_vs_training']
    print('estricto vs entrenamiento: same=%d different=%d unresolved=%d' % (
        s['same'], s['different'], s['unresolved']))
    print('  diferencias:', s['different_pairs'])
    print('  no resueltos:', s['unresolved_pairs'])
    o = r['old_spot_vs_contract']
    print('_preflop_spot viejo vs contrato: same=%d different=%d unresolved=%d' % (
        o['same'], o['different'], o['unresolved']))
    print('  top diferencias:', o['different_pairs'][:12])
    print('  top no resueltos:', o['unresolved_pairs'][:12])
    h = r['hero_old_vs_contract']
    print('estado héroe viejo vs table_plan: same=%d different=%d unresolved=%d' % (
        h['same'], h['different'], h['unresolved']))
    print('  top diferencias:', h['different_pairs'][:12])
    print('cobertura de categorías:', r['coverage'])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--all', action='store_true',
                    help='usar la base completa, no solo la ventana de 877')
    ap.add_argument('--json', action='store_true',
                    help='emitir el informe como JSON')
    ap.add_argument('--examples', type=int, default=8,
                    help='ejemplos por bloque (default: 8)')
    args = ap.parse_args(argv)
    hands = load_hands(reliable_only=not args.all)
    r = informe(hands, max_examples=args.examples)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(r)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
