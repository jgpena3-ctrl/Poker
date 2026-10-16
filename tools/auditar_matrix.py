# -*- coding: utf-8 -*-
"""QUE ES `matrix`. No es una pregunta de opinion: tiene una prueba.

La formula del motor es

    p_matrix(perfil, spot, accion) = (cnt + alpha*prior) / (opp + alpha)

`cnt` son CUENTAS de manos. `opp` son las oportunidades. `prior` es lo que
sale de `preflop_matrices.json`, con 117 tablas que suman entre 0,91 y 89,75.

Hay una consecuencia aritmetica, y es la prueba:

    sum_celdas p_matrix(spot, k) = [ N_k + alpha*S_k ] / (opp + alpha)

`p_matrix` es P(accion | mano, spot), asi que no puede pasar de 1, y las
acciones de un spot son mutuamente excluyentes. Ademas sum_k N_k <= opp,
porque una mano hace UNA sola accion. Luego la unica forma es

    sum_k S_k  <=  1

Y medido: el prior PLANO del fold ya se pasa 25 veces por si solo, sin tocar
una sola de las 117 tablas.

No se toca `data/`. No se cambia la formula. Solo se mide.

Uso:
    python tools/auditar_matrix.py
"""
import collections
import hashlib
import importlib.util
import io
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from motor import learn, player_ranges

TABLAS = json.load(io.open(os.path.join(ROOT, 'data',
                                       'preflop_matrices.json'),
                           encoding='utf-8'))['tables']

# Acciones mutuamente excluyentes por spot. No sale de CAT_TABLE sino de lo
# que significa cada spot: en `facing_open` o se hace 3bet o se hace call,
# y las dos cosas no pueden pasar a la vez.
ACCIONES_DE = {
    'no_raise': ['open', 'limp'],
    'facing_open': ['call_open', '3bet'],
    'facing_3bet': ['call_3bet', '4bet'],
}


def sumas():
    filas = []
    for clave, val in sorted(TABLAS.items()):
        m = np.asarray(val['matrix'], dtype=float)
        filas.append({'clave': clave, 'accion': val.get('action', ''),
                      'suma': float(m.sum()), 'max': float(m.max()),
                      'ceros': float((m == 0).mean())})
    return filas


def main():
    filas = sumas()
    s = np.array([d['suma'] for d in filas])

    print('=' * 78)
    print('1) LAS 117 TABLAS')
    print('=' * 78)
    print()
    print('   %-24s %8s %8s %9s' % ('tabla', 'suma', 'max', '% ceros'))
    print('   ' + '-' * 54)
    for d in filas[:4]:
        print('   %-24s %8.2f %8.2f %8.1f%%'
              % (d['clave'][:24], d['suma'], d['max'], d['ceros'] * 100))
    print('   %-24s %8s %8s %9s' % ('...', '', '', ''))
    for d in filas[-6:]:
        print('   %-24s %8.2f %8.2f %8.1f%%'
              % (d['clave'][:24], d['suma'], d['max'], d['ceros'] * 100))
    print()
    print('   suma: min %.2f · mediana %.2f · max %.2f'
          % (s.min(), float(np.median(s)), s.max()))
    print('   tablas que suman ~1: %d de %d'
          % (int((np.abs(s - 1.0) < 0.05).sum()), len(s)))
    print()

    print('=' * 78)
    print('2) LA PRUEBA: LOS PRIORS DE UN SPOT TIENEN QUE SUMAR 1')
    print('=' * 78)
    print()
    print('   sum_celdas p_matrix = [ N_k + alpha*S_k ] / (opp + alpha)')
    print()
    print('   p_matrix es P(accion|mano,spot) y las acciones de un spot son')
    print('   mutuamente excluyentes, asi que no pasa de 1. Con sum_k N_k <=')
    print('   opp, la unica forma es sum_k S_k <= 1.')
    print()
    print('   Y el prior PLANO del fold ya lo incumple:')
    print()
    print('       FLAT_PRIOR = %.2f por celda  ->  S = %.2f sobre 169 celdas'
          % (player_ranges.FLAT_PRIOR, player_ranges.FLAT_PRIOR * 169))
    print()
    print('   Sin tocar una sola de las 117 tablas. Es aritmetica de la')
    print('   formula que ya esta escrita en `player_ranges.py`.')
    print()

    print('=' * 78)
    print('3) LAS CELDAS: PROBABILIDADES SIN NORMALIZAR')
    print('=' * 78)
    print()
    todos = np.concatenate([np.asarray(v['matrix'], dtype=float).ravel()
                            for v in TABLAS.values()])
    print('   celdas totales                 : %d' % todos.size)
    print('   celdas fuera de [0, 1]         : %d'
          % int(((todos < 0.0) | (todos > 1.0)).sum()))
    print('   celdas exactamente iguales a 1 : %d  (%.1f%%)'
          % (int((todos == 1.0).sum()), 100.0 * (todos == 1.0).mean()))
    print('   tablas con celda maxima = 1    : %d de %d'
          % (sum(1 for d in filas if d['max'] == 1.0), len(filas)))
    print()
    print('   Las celdas SI estan en [0, 1]. Lo que fallo fue NORMALIZAR, no')
    print('   el rango. Y por eso normalizar NO basta: normalizadas darian')
    print('   S_k = 1, y dos acciones de un spot darian S = 2 > 1.')
    print()

    print('=' * 78)
    print('4) EL PRIOR PLANO SE USA DE VERDAD, Y PARA LO MAS FRECUENTE')
    print('=' * 78)
    print()
    es_val = lambda hid: int(hashlib.sha256(
        hid.encode('utf-8')).hexdigest(), 16) % 10 < 3
    ventana = learn.load_hands(reliable_only=True)
    ajuste = [h for h in ventana if not es_val(h['hand_id'])]
    spec = importlib.util.spec_from_file_location(
        'equity_de_mano', os.path.join(ROOT, 'tools', 'equity_de_mano.py'))
    eqm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eqm)
    model = player_ranges.ProfileRangeModel.from_hands(
        ajuste, labels=eqm.perfiles_de(ajuste),
        alpha=player_ranges.DEFAULT_ALPHA)

    accs = collections.Counter()
    sumas_cnt = collections.Counter()
    for (perfil, spot, a), c in model.cnt.items():
        accs[a] += 1
        sumas_cnt[a] += float(np.asarray(c, dtype=float).sum())

    print('   %-14s %-14s %12s'
          % ('accion', 'prior', 'suma cnt'))
    print('   ' + '-' * 44)
    for a in sorted(sumas_cnt, key=lambda k: -sumas_cnt[k]):
        print('   %-14s %-14s %12.1f'
              % (a, 'TABLA' if a in player_ranges.CAT_TABLE else 'PLANO',
                 sumas_cnt[a]))
    print()
    planas = [a for a in sumas_cnt if a not in player_ranges.CAT_TABLE]
    if planas:
        total = sum(sumas_cnt[a] for a in planas)
        print('   Acciones que caen al prior PLANO: %s' % ', '.join(planas))
        print('   suman %.0f manos, el %.0f%% de las observadas.'
              % (total, 100.0 * total / sum(sumas_cnt.values())))
        print()
        print('   El fold es la accion MAS FRECUENTE del proyecto y es la que')
        print('   mas se pasa de la raya: S = %.2f donde la formula admite 1.'
              % (player_ranges.FLAT_PRIOR * 169))
        print()

    print('=' * 78)
    print('5) LA RESOLUCION')
    print('=' * 78)
    print()
    print('   Lo que la medicion DICE, sin interpretar nada:')
    print()
    print('     1. `matrix` NO es una probabilidad sobre las 169 celdas: si lo')
    print('        fuera, cada tabla sumaria 1, y lo hace 1 de 117.')
    print('     2. Los priors de un spot NO pueden sumar 1 con esta formula.')
    print('     3. Luego (cnt + alpha*prior)/(opp + alpha) NO es un shrinkage')
    print('        hacia una probabilidad, y `alpha` no son pseudo-conteos.')
    print()
    print('   Eso es **CASO C**, y de las tres sub-opciones la **tercera**:')
    print()
    print('       `alpha` no es un parametro de regularizacion.')
    print('       NO SE CALIBRA NUNCA.')
    print()
    print('   Lo que NO se puede decidir con datos: QUE clase de cosa es. La')
    print('   medicion acota la forma, no la intencion, y "proporciones')
    print('   relativas" y "conteos con otra base" dan el mismo 89,75 con')
    print('   Remedian distinto. Eso hay que preguntar a quien lo genero.')


if __name__ == '__main__':
    main()