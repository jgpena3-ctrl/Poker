"""Muestra multiway por escenario — la pregunta que bloquea la calibracion.

pegar_2 §6 pide saber cuantas manos hay por escenario (para decidir si la
penalizacion se puede calibrar con datos). pegar_3 §4 pide separar ademas
calle, numero de rivales, pasado vs pendiente y textura.

Salida: n por celda y win% del hero, que acota P(hero > pasivos).
"""
import collections
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.observations import _texture_class

HERO_NAME = 'jarduan'
CALLERS = collections.defaultdict(lambda: [0, 0])   # clave -> [gana, n]


def _gana(h):
    w = h.get('winner')
    if isinstance(w, str):
        return w == 'hero'
    if isinstance(w, list):
        return 'hero' in w
    sw = (h.get('showdown') or {}).get('winner1', '')
    return 'hero' in sw.lower()


def _hero_pos(h):
    for p in h.get('players') or []:
        if str(p.get('name', '')).strip().lower() == HERO_NAME:
            return p.get('pos')
    return None


n_manos = 0
for line in io.open(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'hands_db.jsonl'), encoding='utf-8'):
    h = json.loads(line)
    hp = _hero_pos(h)
    if not hp:
        continue
    n_manos += 1
    win = _gana(h)
    streets = h.get('streets') or {}

    for st in ('flop', 'turn', 'river'):
        acts = (streets.get(st) or {}).get('actions') or []
        if not acts:
            continue
        board = [c for c in ((h.get('comunitarias') or {}).get(st) or [])]
        tex = _texture_class(board) or '?'
        hero_idx = [i for i, a in enumerate(acts) if a.get('pos') == hp]
        if not hero_idx:
            continue
        i = hero_idx[-1]
        mi_accion = acts[i].get('action')
        #区分 CRÍTICA: pasar con check ≠ pasar con apuesta.
        # Un check al hero limita el rango (amenaza floja).
        # Una apuesta/raise es un agresor: es el rival principal.
        agresores, chequeadores = set(), set()
        for a in acts[:i]:
            pos = a.get('pos')
            if not pos:
                continue
            if a.get('action') in ('b', 'r'):
                agresores.add(pos)
            elif a.get('action') == 'x':
                chequeadores.add(pos)
        pending = {a.get('pos') for a in acts[i + 1:] if a.get('pos')}

        n_vivos = len(agresores | chequeadores | pending)
        if n_vivos <= 0:
            continue
        agresor = mi_accion in ('b', 'r')
        t = ('wet' if ('+pair' in tex or 'monotone' in tex)
             else ('two' if 'two_tone' in tex else 'dry'))
        clave = (st,
                 'apuesto' if agresor else 'comprobo',
                 'agres%d' % min(len(agresores), 2),
                 'check%d' % min(len(chequeadores), 3),
                 'pend%d' % min(len(pending), 2),
                 t)
        CALLERS[clave][1] += 1
        CALLERS[clave][0] += 1 if win else 0

print('Manos con hero (Jarduan) identificado:', n_manos)
print()
print('MUESTRA POR ESCENARIO  —  win% del hero acota P(hero > pasivos)')
print('n<30 = no calibrable con esta base')
print()
hdr = ('%-6s %-9s %-7s %-8s %-6s %-5s %6s %6s' %
       ('calle', 'hero', 'agresor', 'checkea', 'pend', 'text', 'n', 'win%'))
print(hdr)
print('-' * len(hdr))
for clave in sorted(CALLERS, key=lambda k: (k[0], k[2], k[3], k[4], k[5])):
    g, t = CALLERS[clave]
    flag = '' if t >= 30 else '  <-- n bajo'
    print('%-6s %-9s %-7s %-8s %-6s %-5s %6d %5.0f%%%s'
          % (clave[0], clave[1], clave[2], clave[3], clave[4], clave[5], t,
             100.0 * g / t, flag))

print()
print('RESUMEN DE MUESTRA CALIBRABLE')
tot = sum(v[1] for v in CALLERS.values())
ok = sum(v[1] for v in CALLERS.values() if v[1] >= 30)
multi = sum(v[1] for k, v in CALLERS.items() if k[3] != 'check0')
print('  celdas totales             : %d' % len(CALLERS))
print('  celdas con n>=30           : %d'
      % len([1 for v in CALLERS.values() if v[1] >= 30]))
print('  celdas con n>=100          : %d'
      % len([1 for v in CALLERS.values() if v[1] >= 100]))
print('  manos en celdas >=30       : %d de %d (%.0f%%)'
      % (ok, tot, 100.0 * ok / tot))
print('  decisiones con >=1 checker : %d de %d (%.0f%%)'
      % (multi, tot, 100.0 * multi / tot))