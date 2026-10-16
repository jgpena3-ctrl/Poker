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
    """(nombre, puesto) del rival cuya conducta se evalua en el corte.

    SON DOS DECISIONES DISTINTAS, y aqui solo la primera:

      1. QUIEN es el rival. Eso es lo que decide esta funcion.
      2. COMO se construye su rango a partir de las alternativas del spot.
         Eso es `rango_del_villano`, y es otra funcion.

    Con subida previa al corte, el rival es el ultimo que subio: es quien
    obliga al hero a responder. No se busca por puesto fijo, porque el
    puesto del villano cambia de mano a mano; usar uno fijo fue el error de
    `prob_vec_player('BB')`.

    SIN subida previa (spot `no_raise`), el ultimo que subio no existe, y
    antes esta funcion devolvia `None`, lo que descartaba la mano entera.
    Medido: 6 de 23 cortes preflop de validacion. Su decision SI tiene
    rival, y quedarse sin nombrarlo es una ausencia que no dice por que.

    Aqui el rival es **el primer jugador que actua DESPUES del hero**: es a
    quien tiene que decidir la subida del hero. Hay mas de una respuesta
    legitima (el mas tight, el agregado de todos los que quedan) y las tres
    dan numeros distintos. Se elige esta porque es la unica que nombra a un
    rival concreto, y se escribe para que se pueda cambiar.

    Que el rango del spot sea la union de `open` y `limp` NO resuelve quien
    es el rival. Son dos preguntas y aqui solo se contesta la primera.
    """
    acts = ((h.get('streets') or {}).get(calle) or {}).get('actions') or []
    posteriores = acts[idx + 1:] if idx is not None else []

    previas = acts[:idx] if idx is not None else acts
    vpos = None
    for a in previas:
        if a.get('pos') != hero and a.get('action') in ('b', 'r'):
            vpos = a.get('pos')

    if vpos is None:
        # sin subida previa: el primer rival que actua despues del hero
        for a in posteriores:
            if a.get('pos') != hero:
                vpos = a.get('pos')
                break

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


def exige_pesos_validos(w, donde):
    """Falla si algun peso no es finito o es negativo.

    `revision_2` §4: validar solo la suma POSITIVA no basta. `rng.choice`
    con `p=` exige que la suma sea positiva Y que cada peso sea finito y no
    negativo; un `-0.0` o un `inf` pasan la suma y revientan dentro.
    """
    a = np.asarray(w, dtype=float)
    malos = np.where(~np.isfinite(a) | (a < 0.0))[0]
    if malos.size:
        raise ValueError(
            '%d peso(s) no valido(s) en %s, en los indices %s: finitos y no '
            'negativos, por favor.'
            % (malos.size, donde, list(malos[:8])))
    if float(a.sum()) <= 0.0:
        raise ValueError('%s no tiene masa: la suma de pesos es %.3g'
                         % (donde, float(a.sum())))
    return a


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
        g = exige_pesos_validos(
            modelo.prob_vec_player(nombre, spot, a),
            'el rango de %s para %s en %s' % (nombre, a, spot))
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
    ap.add_argument('--solo-recaudo', action='store_true',
                    help='imprimir la poblacion etapa a etapa y salir sin '
                         'calcular ninguna equity. Para auditar quien entra '
                         'y quien se cae, sin 3 h de calculo')
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
    sp_cortes = collections.Counter()
    for hid, y in sorted(etiqueta.items()):
        h = por_id[hid]
        hero = eqm.hero_pos_de(h)
        if not hero or y == 0.5:
            continue
        calle, idx = eqm.corte_de_decision(h, hero)
        if calle != 'preflop':
            continue
        # el spot se cuenta ANTES de cualquier filtro: es el denominador
        sp_cortes[mano_del_spot(h, calle, hero, idx)] += 1
        mc = cartas_de(h, hero)
        if not mc:
            sin_rango['sin cartas del hero'] += 1
            continue
        nombre, vpos = villano_del_corte(h, hero, calle, idx)
        if not nombre:
            sin_rango['sin villano identificado en el corte'] += 1
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
    print('   por spot, DESPUES de cada filtro:')
    print('      %-24s %6s %8s %8s'
          % ('spot', 'cortes', 'con mano', 'con rival'))
    print('      ' + '-' * 52)
    for spot in sorted(ACCIONES_SPOT):
        c0 = sp_cortes.get(spot, 0)
        c1 = sum(1 for t in trabajo if t['spot'] == spot)
        print('      %-24s %6d %8d %8d'
              % (spot, c0, c1, c1))
    print()
    print('   Y el detalle de lo que se cae, para que la poblacion sea')
    print('   auditable y no una cifra de las que se pierde el origen:')
    for k, n in sin_rango.most_common():
        print('      %-44s %3d' % (k, n))
    print()
    print('   `cartas_villano` se imprime pero NO se usa para nada. Esta ahi')
    print('   para que se vea que el rango no sale de ahi.')
    print()

    if args.manos:
        trabajo = trabajo[:args.manos]

    if args.solo_recaudo:
        print('   --solo-recaudo: no se calcula ninguna equity.')
        return

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
        try:
            wl = exige_pesos_validos(w[ids], 'el rango legal de %s' % hid)
        except ValueError as exc:
            print('   %s: %s' % (hid, exc))
            continue
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