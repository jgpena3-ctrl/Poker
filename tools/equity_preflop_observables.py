# -*- coding: utf-8 -*-
"""Equity preflop OBSERVABLE de las manos de validacion.

Esto no escribe conclusiones. Calcula numeros.

Lo que `revision_2` §1 corrigio en la version anterior, y esta escrito aqui
para que no se vuelva a perder:

1.C  DOBLE PONDERADO. Se sorteaba con probabilidad proporcional al peso Y
     luego se ponderaba por el peso otra vez. El muestreo ya favorece los
     combos pesados; ponderarlos de nuevo empuja la equity hacia ellos.

     Aqui: extracciones i.i.d. con p_i = w_i / sum_j w_j, y MEDIA SIMPLE.
     Insesgado para sum_i p_i * equity_i. Con reemplazo a proposito: con
     reemplazo la media simple es exactamente insesgada, y los combos
     repetidos salen de la cache sin coste.

1.A  EL SPOT. Antes `mano_del_spot` nunca devolvia `facing_3bet` y contaba
     TODAS las subidas de la calle, no las anteriores al corte. Eso cambia
     el rango que se consulta, y con el, la equity.

     Aqui: se cuentan solo `acts[:idx]` y se distinguen los tres spots.

     Y el rango del villano en un spot es la UNION de las dos
     alternativas excluyentes, a igual masa de prior. Es una eleccion de
     modelado y esta DECLARADA. Lo que no es admisible es elegir una de las
     dos en silencio, que es lo que hacia antes.

1.B  LA SEMILLA. Antes salia de un generador compartido, o sea que la
     muestra de una mano dependia del ORDEN en que se procesaron las
     anteriores, y con `--manos` el numero cambiaba.

     Aqui: la semilla sale de `sha256(hand_id | VERSION | n_combos)`.

Y el resto de las reglas, que ya estaban:

  - El rango sale de `ProfileRangeModel` por NOMBRE de jugador. Nunca de
    las cartas reales del rival: eso seria una fuga de informacion que no
    se nota en el numero, solo en que el numero es demasiado bueno.
  - `n_combos = 40` explicito. El default del motor es 200 y el contrato
    declara que NO se baja a 40 sin medir el postflop.

VERSION 2: el estimador cambio. Las equities POR COMBO siguen valiendo
(dependen solo de las dos manos) y se reutilizan; las AGREGADAS de la
version 1 son sesgadas y no se reutilizan.

Uso:
    python tools/equity_preflop_observables.py
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
from motor.ranges import COMBO0, COMBO1, HAND_MASKS

N_COMBOS = 40
VERSION = 2
CACHE = os.path.join(ROOT, 'data',
                     '_cache_equity_observable.json.v%d.json' % VERSION)

# Las acciones MUTUAMENTE EXCLUYENTES de cada spot. Son dos: el villano O
# llama O sube. El rango es la union de las dos.
ACCIONES_SPOT = {
    'no_raise': ('open', 'limp'),
    'facing_open': ('call_open', '3bet'),
    'facing_3bet': ('call_3bet', '4bet'),
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
    """(nombre, puesto) del ultimo que subio ANTES de la accion del hero.

    Se busca en el recorrido, no por puesto fijo: el puesto del villano
    cambia de mano a mano. Usar uno fijo fue el error de
    `prob_vec_player('BB')`, y costo 6 de 41 manos.
    """
    acts = ((h.get('streets') or {}).get(calle) or {}).get('actions') or []
    previas = acts[:idx] if idx is not None else acts
    vpos = None
    for a in previas:
        if a.get('pos') != hero and a.get('action') in ('b', 'r'):
            vpos = a.get('pos')
    if vpos is None:
        return None, None
    for p in h.get('players') or []:
        if p.get('pos') == vpos:
            return p.get('name'), vpos
    return None, vpos


def mano_del_spot(h, calle, hero, idx):
    """`no_raise` / `facing_open` / `facing_3bet`, por el corte.

    ⚠️ Solo se cuentan las acciones ANTERIORES a `idx`. Antes se contaba
    toda la calle, y eso puede clasificar una mano segun una accion
    posterior al momento que se quiere evaluar.
    """
    if calle != 'preflop':
        return None
    acts = ((h.get('streets') or {}).get(calle) or {}).get('actions') or []
    previas = acts[:idx] if idx is not None else acts
    subidas = sum(1 for a in previas if a.get('action') in ('b', 'r'))
    if subidas == 0:
        return 'no_raise'
    if subidas == 1:
        return 'facing_open'
    return 'facing_3bet'


def rango_del_villano(modelo, nombre, spot):
    """(1326,) con la union de las alternativas del spot, renormalizada.

    Cada alternativa aporta lo que el modelo dice que el villano hace con
    esa mano en ESE spot, a masa 1 antes de sumar. Declarado, no escondido.
    """
    alternativas = ACCIONES_SPOT.get(spot)
    if not alternativas:
        raise ValueError('spot sin alternativas declaradas: %r' % (spot,))
    total = np.zeros(1326)
    for a in alternativas:
        g = np.asarray(modelo.prob_vec_player(nombre, spot, a), dtype=float)
        s = float(g.sum())
        if s <= 0 or not np.isfinite(s):
            continue
        total += g / s
    if total.sum() <= 0:
        raise ValueError('el villano %s no tiene rango en %s' % (nombre, spot))
    return total / total.sum()


def semilla_de(hand_id):
    """Estable por mano. `revision_2` §1.B.

    Con un generador compartido la muestra dependia del ORDEN de
    procesamiento, y `--manos` cambiaba el numero de una mano que ya se
    habia calculado en otra corrida.
    """
    return int(hashlib.sha256(
        ('%s|v%d|%d' % (hand_id, VERSION, N_COMBOS)).encode('utf-8')
    ).hexdigest()[:8], 16)


def main():
    ap = argparse.ArgumentParser(prog='equity_preflop_observables.py')
    ap.add_argument('--manos', type=int, default=0,
                    help='cuantas manos calcular (0 = todas)')
    ap.add_argument('--todo', action='store_true',
                    help='calibracion y validacion (por defecto: validacion)')
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
            sin_rango['sin villano identificado antes del corte'] += 1
            continue
        spot = mano_del_spot(h, calle, hero, idx)
        if spot is None or spot not in ACCIONES_SPOT:
            sin_rango['spot sin alternativas declaradas'] += 1
            continue
        if nombre not in model.perfil:
            sin_rango['villano sin perfil: cae al prior plano'] += 1
            continue
        trabajo.append({'id': hid, 'y': y, 'hero': mc, 'villano': nombre,
                        'vpos': vpos, 'spot': spot,
                        'semilla': semilla_de(hid),
                        'cartas_villano': cartas_de(h, vpos)})

    print('=' * 78)
    print('MANOS QUE EL CAMINO PREFLOP METE   (VERSION %d, iid-media-simple)'
          % VERSION)
    print('=' * 78)
    print()
    print('   universo de la particion      : %d' % len(etiqueta))
    print('   cortes preflop con todo listo : %d' % len(trabajo))
    for k, n in sin_rango.most_common():
        print('      sin computo: %-44s %3d' % (k, n))
    print()
    print('   por spot:')
    for k, n in collections.Counter(t['spot'] for t in trabajo).items():
        print('      %-14s %3d' % (k, n))
    print()
    print('   `cartas_villano` se imprime pero NO se usa para nada. Esta ahi')
    print('   para que se vea que el rango no sale de ahi.')
    print()

    if args.manos:
        trabajo = trabajo[:args.manos]

    cache = cache_abrir()
    hechos = 0
    t0 = time.time()

    from motor.cards import card_id

    for i, t in enumerate(trabajo, 1):
        hid = t['id']
        if hid in cache and 'equity' in cache[hid]:
            continue
        try:
            w = rango_del_villano(model, t['villano'], t['spot'])
        except Exception as exc:                       # pragma: no cover
            print('   %s: rango no disponible (%r)' % (hid, exc))
            continue

        mask = 0
        # la mano es un string de 4 chars ('Jh7d'), no una lista: hay que
        # cortar por pares
        for k in (0, 2):
            mask |= (1 << card_id(t['hero'][k:k + 2]))
        ids = np.where((HAND_MASKS & mask) == 0)[0]
        wl = w[ids]
        tot = float(wl.sum())
        if not np.isfinite(tot) or tot <= 0:
            print('   %s: el rango no tiene masa legal' % hid)
            continue

        n = int(min(N_COMBOS, len(ids)))
        rng = np.random.default_rng(t['semilla'])
        elegidos = rng.choice(len(ids), size=n, replace=True, p=wl / tot)

        hero_ids = np.array([card_id(t['hero'][0:2]),
                             card_id(t['hero'][2:4])], dtype=np.intp)
        acc = 0.0
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
            acc += eq

        cache[hid] = {'equity': acc / n, 'n_combos': n,
                      'villano': t['villano'], 'spot': t['spot'],
                      'y': t['y'], 'hero': t['hero'],
                      'semilla': t['semilla'],
                      'estimador': 'iid-media-simple'}
        hechos += 1
        mins = (time.time() - t0) / 60.0
        print('   [%3d/%3d] %-9s %-4s vs %-14s %-14s eq %.4f  '
              '(%d nuevas, %.1f min, %.1f min/mano)'
              % (i, len(trabajo), hid, t['hero'], t['villano'], t['spot'],
                 acc / n, nuevos, mins, mins / hechos), flush=True)
        if hechos % 5 == 0:
            cache_guardar(cache)

    cache_guardar(cache)
    print()
    print('   manos nuevas calculadas : %d' % hechos)
    print('   manos agregadas en cache: %d'
          % sum(1 for v in cache.values()
                if isinstance(v, dict) and 'equity' in v))
    print('   equities por combo      : %d'
          % sum(1 for v in cache.values() if isinstance(v, float)))
    print('   cache                   : %s' % os.path.relpath(CACHE, ROOT))
    print('   tiempo total            : %.1f min' % ((time.time() - t0) / 60))


if __name__ == '__main__':
    main()