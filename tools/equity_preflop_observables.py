# -*- coding: utf-8 -*-
"""Calcula la equity preflop OBSERVABLE de las manos de validacion.

Esto NO escribe conclusiones. Solo calcula el numero, que despues se mide.

Tres reglas, y las tres importan:

  1. El rango del rival se construye desde `ProfileRangeModel`, NO desde sus
     cartas reales. Si el rango se construye con las cartas del rival la
     equity es retrospectiva y no cuenta: es una fuga de informacion que no
     se nota en el numero, solo en que el numero es demasiado bueno.

  2. `n_combos = 40` explicito. El default del motor es 200 y el contrato
     declara que NO se baja a 40 sin medir el postflop.

  3. Cache en disco por par (hero, rival). Un par sale una vez y se paga
     solo. El motor no cachea: el motor calcula, el instrumento guarda.

Uso:
    python tools/equity_preflop_observables.py          # las de validacion
    python tools/equity_preflop_observables.py --manos 3
"""
import argparse
import collections
import hashlib
import importlib.util
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import numpy as np

from motor import learn, player_ranges
from motor.hand_evaluator import equity_preflop_contra_combo
from motor.ranges import COMBO0, COMBO1

N_COMBOS = 40
SEMILLA = 7
# Con VERSION, como la cache de equity_preflop.py. Subirla la invalida.
VERSION = 1
CACHE = os.path.join(ROOT, 'data',
                     '_cache_equity_observable.json.v%d.json' % VERSION)

# Acciones por spot: el rango del rival depende de QUE hizo, y hay que
# pedir el rango del villano para ESA accion en ESE spot.
ACCION_POR_SPOT = {
    'no_raise': 'call_open',
    'facing_open': 'call_open',
    'facing_3bet': 'call_3bet',
}


def _m(nombre):
    ruta = os.path.join(ROOT, 'tools', nombre)
    spec = importlib.util.spec_from_file_location(nombre[:-3], ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


eqm = _m('equity_de_mano.py')
cal = _m('calibrar.py')


def cache_abrir():
    try:
        with io.open(CACHE, encoding='utf-8') as f:
            d = json.load(f)
        if (isinstance(d, dict) and d.get('VERSION') == VERSION
                and isinstance(d.get('v'), dict)):
            return d['v']
    except (OSError, ValueError):
        pass
    return {}


def cache_guardar(d):
    tmp = CACHE + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'VERSION': VERSION, 'v': d}, f)
    os.replace(tmp, CACHE)


def cartas_de(h, pos):
    for p in h.get('players') or []:
        if p.get('pos') == pos:
            cc = p.get('cards')
            if isinstance(cc, str) and len(cc) == 4:
                return cc
    return None


def villano_del_corte(h, hero, calle, idx):
    """(nombre, puesto) del ultimo que subio antes de la accion del hero.

    Se busca en el RECORRIDO, no por puesto fijo: el puesto del villano
    cambia de mano a mano, y usar uno fijo seria el error de
    `prob_vec_player('BB')`.
    """
    acts = ((h.get('streets') or {}).get(calle) or {}).get('actions') or []
    vpos = None
    for a in acts[:idx]:
        if a.get('pos') != hero and a.get('action') in ('b', 'r'):
            vpos = a.get('pos')
    if vpos is None:
        return None, None
    for p in h.get('players') or []:
        if p.get('pos') == vpos:
            return p.get('name'), vpos
    return None, vpos


def mano_del_spot(h, calle, hero):
    """El spot del hero en esa calle: no_raise / facing_open / facing_3bet."""
    if calle != 'preflop':
        return None
    acts = ((h.get('streets') or {}).get(calle) or {}).get('actions') or []
    subidas = sum(1 for a in acts if a.get('action') in ('b', 'r'))
    if subidas == 0:
        return 'no_raise'
    return 'facing_open'


def main():
    ap = argparse.ArgumentParser(prog='equity_preflop_observables.py')
    ap.add_argument('--manos', type=int, default=0,
                    help='cuantas manos calcular (0 = todas)')
    ap.add_argument('--validacion', action='store_true',
                    help='solo la particion de validacion (por defecto)')
    ap.add_argument('--todo', action='store_true',
                    help='calibracion y validacion')
    args = ap.parse_args()

    ventana = learn.load_hands(reliable_only=True)
    ajuste = [h for h in ventana if not cal.es_validacion(h['hand_id'])]
    labels = eqm.perfiles_de(ajuste)
    model = player_ranges.ProfileRangeModel.from_hands(
        ajuste, labels=labels, alpha=player_ranges.DEFAULT_ALPHA)

    cal_, val_ = cal.muestra()
    universo = list(val_) if not args.todo else list(val_) + list(cal_)
    etiqueta = dict(universo)
    por_id = {h['hand_id']: h for h in ventana}

    # --------------- que manos son las que el camino preflop mete
    trabajo = []
    sin_rango = collections.Counter()
    for hid, y in sorted(etiqueta.items()):
        h = por_id[hid]
        hero = eqm.hero_pos_de(h)
        if not hero or y == 0.5:
            continue
        calle, idx = eqm.corte_de_decision(h, hero)
        if calle != 'preflop':
            continue
        mc = cartas_de(h, hero)
        if not mc:
            sin_rango['sin cartas del hero'] += 1
            continue
        nombre, vpos = villano_del_corte(h, hero, calle, idx)
        if not nombre:
            sin_rango['sin villano identificado'] += 1
            continue
        spot = mano_del_spot(h, calle, hero)
        accion = ACCION_POR_SPOT.get(spot)
        if accion is None:
            sin_rango['spot sin accion declarada'] += 1
            continue
        if nombre not in model.perfil:
            sin_rango['villano sin perfil: cae al prior plano'] += 1
            continue
        trabajo.append({'id': hid, 'y': y, 'hero': mc, 'villano': nombre,
                        'vpos': vpos, 'spot': spot, 'accion': accion,
                        'cartas_villano': cartas_de(h, vpos)})

    print('=' * 78)
    print('MANOS QUE EL CAMINO PREFLOP METE')
    print('=' * 78)
    print()
    print('   universo de la particion      : %d' % len(etiqueta))
    print('   cortes preflop con todo listo : %d' % len(trabajo))
    for k, n in sin_rango.most_common():
        print('      sin computo: %-44s %3d' % (k, n))
    print()
    print('   Y un aviso: `cartas_villano` se imprime pero NO se usa para')
    print('   nada. Esta ahi para que se vea que el rango no sale de ahi.')
    print()

    if args.manos:
        trabajo = trabajo[:args.manos]

    cache = cache_abrir()
    rng = np.random.default_rng(SEMILLA)
    hechos = 0
    t0 = time.time()

    for i, t in enumerate(trabajo, 1):
        hid = t['id']
        if hid in cache and 'equity' in cache[hid]:
            continue

        # EL RANGO: del modelo, por perfil y spot. Nunca de las cartas.
        try:
            w = np.asarray(model.prob_vec_player(t['villano'], t['spot'],
                                                 t['accion']), dtype=float)
        except Exception as exc:                       # pragma: no cover
            print('   %s: rango no disponible (%r)' % (hid, exc))
            continue

        mask = 0
        from motor.cards import card_id
        # la mano es un string de 4 chars ('Jh7d'), NO una lista: hay que
        # cortar por pares. Iterarlo letra a letra daba codigos de 1 char.
        for _k in (0, 2):
            mask |= (1 << card_id(t['hero'][_k:_k + 2]))
        from motor.ranges import HAND_MASKS
        ids = np.where((HAND_MASKS & mask) == 0)[0]
        wl = w[ids]
        tot = float(wl.sum())
        if not np.isfinite(tot) or tot <= 0:
            print('   %s: el rango no tiene masa legal' % hid)
            continue
        n = int(min(N_COMBOS, len(ids)))
        elegidos = rng.choice(len(ids), size=n, replace=False, p=wl / tot)

        hero_ids = np.array([card_id(t['hero'][0:2]),
                             card_id(t['hero'][2:4])], dtype=np.intp)
        acc = 0.0
        peso = 0.0
        nuevos = 0
        for k in elegidos:
            j = int(ids[int(k)])
            rival = np.array([COMBO0[j], COMBO1[j]], dtype=np.intp)
            clave = '%s|%d,%d' % (t['hero'], int(rival[0]), int(rival[1]))
            eq = cache.get(clave)
            if eq is None:
                eq = equity_preflop_contra_combo(hero_ids, rival)
                cache[clave] = eq
                nuevos += 1
            acc += eq * wl[int(k)]
            peso += wl[int(k)]

        cache[hid] = {'equity': acc / peso, 'n_combos': n,
                      'villano': t['villano'], 'spot': t['spot'],
                      'accion': t['accion'], 'y': t['y'],
                      'hero': t['hero'], 'seed': SEMILLA}
        hechos += 1
        mins = (time.time() - t0) / 60.0
        print('   [%3d/%3d] %-9s %-4s vs %-14s %-14s eq %.4f  '
              '(%d equities nuevas, %.1f min, media %.1f min/mano)'
              % (i, len(trabajo), hid, t['hero'], t['villano'], t['spot'],
                 acc / peso, nuevos, mins, mins / hechos), flush=True)
        if hechos % 5 == 0:
            cache_guardar(cache)

    cache_guardar(cache)
    print()
    print('   manos nuevas calculadas : %d' % hechos)
    print('   entradas en la cache    : %d' % len(cache))
    print('   cache                   : %s'
          % os.path.relpath(CACHE, ROOT))
    print('   tiempo total            : %.1f min' % ((time.time() - t0) / 60))


if __name__ == '__main__':
    main()