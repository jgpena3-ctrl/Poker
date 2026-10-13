import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.hierarchy import (classify_villains, penalty_source, shadow_equity)
from motor.learn import load_hands
from motor.observations import _texture_class

SRC = collections = None
import collections  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

src = collections.Counter()
muestras = collections.Counter()

for h in load_hands(reliable_only=True):
    hp = None
    for p in h.get('players') or []:
        if str(p.get('name', '')).strip().lower() == 'jarduan':
            hp = p.get('pos')
            break
    if not hp:
        continue
    activos = [p.get('pos') for p in h.get('players', []) if p.get('active')]
    streets = h.get('streets') or {}
    for st in ('flop', 'turn', 'river'):
        acts = (streets.get(st) or {}).get('actions') or []
        if not acts or not any(a.get('pos') == hp for a in acts):
            continue
        acted = {a.get('pos') for a in acts if a.get('pos')}
        pend = [p for p in activos if p and p != hp and p not in acted]
        jer = classify_villains(acts, hp, pending_positions=pend)
        if not jer.get('main'):
            continue
        board = [c for c in ((h.get('comunitarias') or {}).get('flop') or [])]
        if len(board) < 3:
            continue
        s = shadow_equity(0.5, board, st, jer, equity_source=jer['main'])
        src[s['penalty_source']] += 1
        if s['penalty_source'] == 'anchor_match':
            muestras[(st, tuple(sorted(jer.get('checkers') or ())),
                      tuple(sorted(jer.get('pending') or ())),
                      bool(jer.get('hero_bet')),
                      len(jer.get('aggressors') or ()))] += 1

print('REPARTO REAL POR PENALTY_SOURCE (antes: 199 measured / 409 extrapolated)')
print()
for k, v in src.most_common():
    print('   %-18s %4d' % (k, v))
print('   %-18s %4d' % ('TOTAL', sum(src.values())))
print()
anchor = src.get('anchor_match', 0)
antes = 199
print('registros que SOPORTABAN el ancla antes (turn+rainbow a pelo): %d' % antes)
print('registros que lo SOPORTAN de verdad (6 condiciones):         %d' % anchor)
if antes:
    print('reduccion: %.0f%%' % (100.0 * (antes - anchor) / antes))