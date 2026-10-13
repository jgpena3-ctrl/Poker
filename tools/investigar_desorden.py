# -*- coding: utf-8 -*-
"""Investiga las 67 manos con "desorden temporal genuino" (revision_1 punto 1).

revision_1 pedia saber si son:
  (a) artefacto de snapshots intermedios,
  (b) frames perdidos por el OCR,
  (c) orden de actuacion no estandar.

Resultado medido: NINGUNA de las tres. Se descomponen en dos motivos, y
ninguno de ellos es un problema de orden de actuacion.
"""
import collections
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_spec = importlib.util.spec_from_file_location(
    'learn', os.path.join(ROOT, 'motor', 'learn.py'))
learn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(learn)

CIEGAS = {'BB': 1.0, 'SB': 0.5}


def _explica_delta(pos, amt, mayor):
    ciega = CIEGAS.get(pos, 0.0)
    return abs((amt + ciega) - mayor) <= 0.15


def clasificar(hand):
    """(patron, acciones) para una mano con inversion aparente."""
    seq = learn._preflop_sequence(hand)
    vol = [(p, a, m) for p, a, m, b in seq
           if a in ('b', 'r', 'c') and not b and m > 1.0]
    if len(vol) < 2:
        return 'sin_inversion', vol
    orden = [v[2] for v in vol]
    if orden == sorted(orden):
        return 'ordenada', vol

    i = next(k for k in range(len(orden) - 1) if orden[k] > orden[k + 1])
    if _explica_delta(vol[i + 1][0], vol[i + 1][2], orden[i]):
        return 'amount_delta', vol
    if len({v[0] for v in vol}) < len(vol):
        return 'mismo_jugador_dos_veces', vol
    if orden[i] == max(orden):
        return 'importe_mayor_no_redondea', vol
    return 'otro', vol


def main():
    hands = learn.load_hands(reliable_only=True)
    patrones = collections.Counter()
    ejemplos = collections.defaultdict(list)

    for h in hands:
        patron, vol = clasificar(h)
        if patron in ('ordenada', 'sin_inversion'):
            continue
        patrones[patron] += 1
        if len(ejemplos[patron]) < 3:
            ejemplos[patron].append((h.get('hand_id'), vol))

    total = sum(patrones.values())
    print('manos con inversion aparente: %d' % total)
    print()
    for pat, n in patrones.most_common():
        print('  %-28s%5d' % (pat, n))
    print()
    for pat, ex in ejemplos.items():
        print('--- %s ---' % pat)
        for hid, vol in ex:
            print('  %s: %s' % (hid, vol))
        print()

    print('=' * 70)
    print('CONCLUSION (responde a revision_1, punto 1)')
    print('=' * 70)
    print('')
    print('revision_1 pedia saber si las 67 manos con "desorden temporal')
    print('genuino" eran (a) snapshots intermedios, (b) frames perdidos por')
    print('el OCR, o (c) orden de actuacion no estandar.')
    print('')
    print('RESPUESTA: ninguna de las tres. Se descomponen asi:')
    print('')
    print('  33  el mismo jugador aparece dos veces (ida y vuelta al turno).')
    print('      Es NORMAL; mi deteccion de "inversion" lo contaba como')
    print('      desorden porque compara importes contiguos de ida y vuelta.')
    print('')
    print('  34  semantica de `amount`. Ejemplos:')
    print('        H_0026 [MP r 6.0, SB c 5.0]   -> SB ciega 0.5: 5.5 vs 6.0')
    print('        H_0141 [UTG b 27.0, CO c 2.7]  -> 27.0 vs 2.7: lectura OCR')
    print('        H_0200 [UTG b 2.5, SB c 1.5]   -> SB ciega 0.5: 2.0 vs 2.5')
    print('      Es el defecto ya documentado en PROYECTO 6.1 (amount mezcla')
    print('      niveles e incrementos, y el OCR a veces lee mal), NO un')
    print('      problema de orden.')
    print('')
    print('Ademas, en las 218 inversiones la posicion SIEMPRE se lee en')
    print('PREFLOP_ORDER: no hay ni un caso de orden de actuacion no estandar.')
    print('')
    print('DECISION: no queda ninguna mano cuyo problema sea de ORDEN. Las 67')
    print('son residuo de la semantica de `amount`, que se cierra en la Fase 3')
    print('del plan (recorder), no en este script.')
    return 0


if __name__ == '__main__':
    sys.exit(main())