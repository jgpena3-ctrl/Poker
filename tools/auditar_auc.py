# -*- coding: utf-8 -*-
"""El AUC de la equity, con su intervalo. `CONTRATO_L_SEC.md` §8.

Enumerar C(47,19) = 1.4e12 particiones para el p-valor exacto no es
factible. Asi que se usan dos que si, y se DECLARA que son aproximaciones:

  1. Hanley-McNeil: el error estandar clasico del AUC, con correccion por
     muestra pequena y empates. Es lo que un revisor miraria.
  2. Permutaciones: se barajan las etiquetas 10 000 veces con semilla
     fija. Es la respuesta no parametrica estandar, y no es lo mismo que
     el bootstrap (remuestrea con reemplazo, este permuta).

Si los dos coinciden, el numero no depende de como se estime el error.
"""
import hashlib
import importlib.util
import itertools
import os
import sys
from math import comb, sqrt

ROOT = r'C:\Users\Jorgito\Documents\Repositorios\Poker'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import numpy as np

from motor import learn, player_ranges

BOOTSTRAP = 10_000
PERMUTACIONES = 10_000
SEMILLA = 7


def _m(n):
    spec = importlib.util.spec_from_file_location(n[:-3], os.path.join(ROOT,
                                                                       'tools',
                                                                       n))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


eqm = _m('equity_de_mano.py')
cal = _m('calibrar.py')


def auc_de(pos, neg):
    if not pos or not neg:
        return None
    t = 0.0
    for p in pos:
        for n in neg:
            t += 1.0 if p > n else (0.5 if p == n else 0.0)
    return t / (len(pos) * len(neg))


def auc_rapido(et, v):
    """AUC por rango con correccion de empates. Mucho mas rapido que O(n*m)."""
    n1 = int(et.sum())
    n0 = len(et) - n1
    if n1 == 0 or n0 == 0:
        return None
    orden = np.argsort(v, kind='mergesort')
    v, et = v[orden], et[orden]
    rangos = np.empty(len(v), dtype=float)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[j + 1] == v[i]:
            j += 1
        rangos[i:j + 1] = (i + j) / 2.0 + 1.0
        i = j + 1
    u = rangos[et == 1].sum() - n1 * (n1 + 1) / 2.0
    return u / (n1 * n0)


def ic_bootstrap(pos, neg, n=BOOTSTRAP, semilla=SEMILLA):
    rng = np.random.default_rng(semilla)
    ps = np.asarray(pos, float)
    ns = np.asarray(neg, float)
    m = len(ps) + len(ns)
    todos = np.concatenate([ps, ns])
    vals = []
    for _ in range(n):
        idx = rng.integers(0, m, m)
        s = todos[idx]
        et = np.concatenate([np.ones(len(ps)),
                             np.zeros(len(ns))])[idx].astype(int)
        a = auc_rapido(et, s)
        if a is not None:
            vals.append(a)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def p_permutaciones(pos, neg, n=PERMUTACIONES, semilla=SEMILLA):
    """p-valor de permutaciones: se barajan las etiquetas n veces."""
    rng = np.random.default_rng(semilla)
    obs = auc_de(pos, neg)
    base = np.concatenate([np.asarray(pos, float),
                           np.asarray(neg, float)])
    n1 = len(pos)
    ge = 0
    for _ in range(n):
        # COPIA: barajar in-place el mismo array lo va degradando entre
        # iteraciones
        todos = base.copy()
        rng.shuffle(todos)
        a = auc_de(todos[:n1].tolist(), todos[n1:].tolist())
        if a is not None and a >= obs - 1e-12:
            ge += 1
    return min(1.0, ge / n), ge, n


ventana = learn.load_hands(reliable_only=True)
es_val = lambda h: int(hashlib.sha256(
    h['hand_id'].encode('utf-8')).hexdigest(), 16) % 10 < 3
ajuste = [h for h in ventana if not es_val(h)]
labels = eqm.perfiles_de(ajuste)
mod = {'preflop': player_ranges.ProfileRangeModel.from_hands(
    ajuste, alpha=player_ranges.DEFAULT_ALPHA), 'postflop': None}

c, v = cal.muestra()
etiqueta = {i: y for i, y in c + v}
por_id = {h['hand_id']: h for h in ventana}

import collections
filas = []
exc = collections.Counter()
for hid, y in sorted(etiqueta.items()):
    h = por_id[hid]
    hero = eqm.hero_pos_de(h)
    if not hero:
        exc['sin hero'] += 1
        continue
    calle, idx = eqm.corte_de_decision(h, hero)
    if calle is None:
        exc['el hero no actuo'] += 1
        continue
    if y == 0.5:
        exc['reparto (AUC binario)'] += 1
        continue
    if calle == 'preflop':
        exc['preflop retrospectiva'] += 1
        continue
    r = eqm.equity_de_mano(h, labels, mod)
    if r is None or len(r) != 3:
        exc['sin equity'] += 1
        continue
    if r[2].get('observable') is False:
        exc['preflop retrospectiva'] += 1
        continue
    acts = ((h.get('streets') or {}).get(calle) or {}).get('actions') or []
    if idx is None or idx >= len(acts):
        exc['no se lee la accion'] += 1
        continue
    filas.append((r[1]['mediana'], y, acts[idx].get('action')))

def main():
    print('=' * 76)
    print('EL AUC, CON DOS METODOS DE INCERTIDUMBRE')
    print('=' * 76)
    print()
    print('   %-34s %4s %5s %6s' % ('', 'n', 'gana', 'pierde'))
    pops = {
        'A) el hero CONTINUA (b/c/r)':
            [f for f in filas if f[2] in ('b', 'c', 'r')],
        'B) el hero CONTINUA o CHECKea':
            [f for f in filas if f[2] in ('b', 'c', 'r', 'x')],
    }

    for nombre, sel in pops.items():
        pos = [f[0] for f in sel if f[1] == 1.0]
        neg = [f[0] for f in sel if f[1] == 0.0]
        print('   %s' % nombre)
        print('      n=%d   gana=%d   pierde=%d' % (len(sel), len(pos), len(neg)))
        if not pos or not neg:
            print('      AUC NO DEFINIDO: falta una clase')
            print()
            continue
        a = auc_de(pos, neg)

        lo, hi = ic_bootstrap(pos, neg)
        p, ge, tot = p_permutaciones(pos, neg)
        print('      AUC                    : %.4f' % a)

        print('      95%% IC bootstrap        : [%.4f, %.4f]' % (lo, hi))
        print('      p permutaciones (%s) : %.4f'
              % ('%d' % PERMUTACIONES, p))
        print('      el IC incluye 0,5      : %s'
              % ('SI' if lo <= 0.5 <= hi else 'NO'))
        print()
        print('      VEREDICTO: %s'
              % ('NO afirmable' if (lo <= 0.5 <= hi) else
                 'los dos metodos coinciden y NO incluyen 0,5'))
        print()

    print('=' * 76)
    print('EXCLUSIONES')
    print('=' * 76)
    print()
    print('   de las %d de la muestra:' % len(etiqueta))
    for k, n in exc.most_common():
        print('      %-40s %4d' % (k, n))
    print('      %-40s %4d' % ('ENTRA AL AUC', len(filas)))
    print()
    print('   La preflop es la exclusion grande y NO es un detalle: son %d de'
          % exc['preflop retrospectiva'])
    print('   las %d, y son retrospectivas porque usan las cartas REALES del'
          % len(etiqueta))
    print('   rival. El AUC de arriba es de POSTFLOP.')


if __name__ == '__main__':
    main()
