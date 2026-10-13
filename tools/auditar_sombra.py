"""Reejecuta la jerarquia sobre 400 manos y audita la consistencia.

pegar_3 §4 pide verificar, tras corregir, que los registros ya no sean
semanticamente incorrectos.
"""
import collections
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.hierarchy import ShadowLog, classify_villains, shadow_equity
from motor.learn import load_hands

TEMP = os.path.join('data', '_shadow_audit.jsonl')
if os.path.exists(TEMP):
    os.remove(TEMP)
lg = ShadowLog(path=TEMP)

hands = load_hands(reliable_only=True)[:400]
stats = collections.Counter()
motivos = collections.Counter()
src = collections.Counter()
pen_abs = []
problemas = []

n_caller_total = 0
for h in hands:
    hp = None
    for p in (h.get('players') or []):
        if str(p.get('name', '')).strip().lower() == 'jarduan':
            hp = p.get('pos')
            break
    if not hp:
        continue
    pos_activos = [p.get('pos') for p in h.get('players', []) if p.get('active')]
    streets = h.get('streets') or {}

    for st in ('flop', 'turn', 'river'):
        acts = (streets.get(st) or {}).get('actions') or []
        if not acts:
            continue
        acted = {a.get('pos') for a in acts if a.get('pos')}
        pendientes = [p for p in pos_activos if p and p != hp and p not in acted]
        jer = classify_villains(acts, hp, pending_positions=pendientes)
        if not jer.get('main'):
            stats['sin_principal'] += 1
            continue
        stats['con_principal'] += 1
        motivos[jer['main_reason'].split('(')[0].strip()] += 1
        board = (h.get('comunitarias') or {}).get('flop') or []
        if st != 'flop':
            board = []
        s = shadow_equity(0.50, board or ['Qh', '7s', '2c'], st, jer,
                         equity_source=jer['main'])
        src[s['penalty_source']] += 1
        if s['penalty'] > 0:
            pen_abs.append(s['penalty'])
        n_caller_total += len(jer.get('callers') or ())
        stats[st] += 1
        lg.append({'hand_id': h.get('hand_id'), 'street': st,
                   'villain_main': jer['main'],
                   'n_checker': s['n_checker'], 'n_pending': s['n_pending'],
                   'n_caller': len(jer.get('callers') or ()),
                   'penalty': s['penalty'],
                   'penalty_source': s['penalty_source']})
        # auditorias
        if hp in jer['pending']:
            problemas.append('hero en pending %s' % h.get('hand_id'))
        if hp in jer['checkers'] or hp in jer['aggressors']:
            problemas.append('hero como rival %s' % h.get('hand_id'))
        for c in jer['checkers']:
            if c in acted and any(a.get('pos') == c
                                  and a.get('action') in ('b', 'r')
                                  for a in acts):
                problemas.append('checker que tambien agresiona %s' % h.get('hand_id'))
        for pd in jer['pending']:
            if pd in acted:
                problemas.append('pendiente que ya actuo %s' % h.get('hand_id'))

print('registros con rival principal : %d' % stats['con_principal'])
print('registros sin rival principal  : %d' % stats['sin_principal'])
print()
print('motivo de la seleccion:')
for k, v in motivos.most_common():
    print('   %-45s %d' % (k, v))
print()
print('origen de la penalizacion:')
for k, v in src.most_common():
    print('   %-15s %d' % (k, v))
print()
if pen_abs:
    print('penalizaciones: min=%.4f media=%.4f max=%.4f (ABSOLUTAS)'
          % (min(pen_abs), sum(pen_abs) / len(pen_abs), max(pen_abs)))
print()
print('registros con al menos un caller: %d' % n_caller_total)
print()
print('INCOHERENCIAS DETECTADAS: %d' % len(problemas))
for p in problemas[:10]:
    print('   ' + p)
os.remove(TEMP)