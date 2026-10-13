# -*- coding: utf-8 -*-
"""Las 34 manos con `importe_mayor_no_redondea` (revision_1 punto 4).

revision_1 pregunta si el caso H_0141 (bet 27.0 con calls de 2.7) es:
  (a) bug del OCR (lee 2.7 como 27.0),
  (b) bug del recorder (multiplica por 10),
  (c) un caso real (stack grande, bet enorme).

Se responde mirando la MANO COMPLETA: si el resto de las acciones de esa
mano son coherentes con 2.7 y no con 27.0, es un error de una sola lectura.
"""
import collections
import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_spec = importlib.util.spec_from_file_location(
    'learn', os.path.join(ROOT, 'motor', 'learn.py'))
learn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(learn)

CIEGAS = {'BB': 1.0, 'SB': 0.5}


def _inversion(seq):
    vol = [(p, a, m) for p, a, m, b in seq
           if a in ('b', 'r', 'c') and not b and m > 1.0]
    if len(vol) < 2:
        return None
    o = [v[2] for v in vol]
    if o == sorted(o):
        return None
    i = next((k for k in range(len(o) - 1) if o[k] > o[k + 1]), None)
    if i is None:
        return None
    if abs((vol[i + 1][2] + CIEGAS.get(vol[i + 1][0], 0)) - o[i]) <= 0.15:
        return None
    if len({v[0] for v in vol}) < len(vol):
        return None
    return (vol, i) if o[i] == max(o) else None


def main():
    hands = learn.load_hands(reliable_only=True)
    casos = []
    for h in hands:
        seq = learn._preflop_sequence(h)
        inv = _inversion(seq)
        if inv:
            casos.append((h, inv))

    print('manos con importe_mayor_no_redondea: %d' % len(casos))
    print()

    veredicto = collections.Counter()
    detalle = []
    for h, (vol, i) in casos:
        mayor = vol[i]
        hid = h.get('hand_id')
        # todos los importes de la mano (todas las calles)
        todos = []
        for st, d in (h.get('streets') or {}).items():
            for a in (d or {}).get('actions', []) or []:
                try:
                    todos.append(float(a.get('amount') or 0.0))
                except (TypeError, ValueError):
                    pass
        stacks = [p.get('stack') for p in (h.get('players') or [])
                  if p.get('stack')]
        max_stack = max(stacks) if stacks else 0
        ratio = mayor[2] / max(vol[i + 1][2], 0.01) if vol[i + 1][2] else 0

        # el importe mayor es multiplo exacto de 10 del menor?
        if abs(mayor[2] / 10 - vol[i + 1][2]) < 0.15:
            v = 'OCR x10'
        elif ratio > 5:
            v = 'ratio %.1f (apuesta enorme)' % ratio
        else:
            v = 'otro'
        veredicto[v] += 1
        detalle.append((hid, mayor, vol[i + 1], v, max_stack))

    for v, n in veredicto.most_common():
        print('  %-28s %3d' % (v, n))
    print()
    print('detalle (hand, importe mayor, importe menor, veredicto, stack max):')
    for hid, may, men, v, ms in detalle[:20]:
        print('  %-9s %-18s vs %-18s %-22s stack_max=%.1f'
              % (hid, may, men, v, ms))

    print()
    print('=' * 72)
    print('CONCLUSION (revision_1, punto 4)')
    print('=' * 72)
    ocr = veredicto.get('OCR x10', 0)
    print('')
    print('Casos "OCR x10" (el mayor es exactamente 10x el menor): %d de %d'
          % (ocr, len(casos)))
    print('')
    print('Pistas para distinguir (a) de (c):')
    print('  - Si el stack del jugador es menor que el importe, no puede ser')
    print('    un bet real: es un error de lectura.')
    print('  - Si el resto de importes de la mano son del mismo orden que el')
    print('    menor, el mayor es la excepcion -> error de lectura.')
    return 0


if __name__ == '__main__':
    sys.exit(main())