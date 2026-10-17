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

# El nombre del estimador va en la cache. Sin el, dos procedimientos
# distintos con la misma VERSION serian indistinguibles, y eso ya paso.
ESTIMADOR = 'iid-media-simple'


def huella_de(hero, ids, wl, semilla, n, y):
    """Huella determinista de lo que DETERMINA la equity agregada.

    Se calcula sobre los objetos que se usan, no sobre constantes que
    alguien tenga que acordarse de subir. Concretamente:

      hero      las dos cartas del heroe: el enumerado legal sale de ahi
      ids       el enumerado legal, no solo su longitud
      wl        los pesos del rango sobre ese enumerado
      semilla   el generador: sin esto dos resultados son incomparables
      n         cuantos se muestrearon de verdad
      y         la ETIQUETA, que no viene del rango y por eso hay que
                meterla a mano

    Y el rango carries la base de datos sin nombrarla: si `hands_db.jsonl`
    cambia y eso cambia el rango de este villano, `wl` cambia y la huella
    cambia. Lo que no cambia este rango no puede cambiar esta equity.

    `revision_2` §1: la condicion de reutilizacion exigia version, estimador,
    semilla, n_combos, villano, spot y hero. Siete campos, y ninguno era
    esto. Medido: `dfef471` cambio la base, HANDS_DB_SHA256 cambio, y los
    siete campos siguieron coincidiendo.
    """
    h = hashlib.sha256()
    h.update(('|'.join((str(VERSION), ESTIMADOR, hero, str(semilla),
                        str(n), repr(y)))).encode('utf-8'))
    h.update(np.ascontiguousarray(ids, dtype=np.intp).tobytes())
    h.update(np.ascontiguousarray(wl, dtype=np.float64).tobytes())
    return h.hexdigest()[:16]
CACHE = os.path.join(ROOT, 'data',
                     '_cache_equity_observable.json.v%d.json' % VERSION)

# Lo que hace el heroe en EL CORTE. El corte es su ULTIMA accion
# (`corte_de_decision`), y eso incluye los folds.
#
# La poblacion del AUC es B: "el hero CONTINUA o CHECKEA"
# (`CONTRATO_L_SEC.md` §8). Un fold no es ninguna de las dos cosas, y
# ademas tiene y = 0 por construccion: el que foldea no puede ganar. Con
# estas dentro, el AUC no mide la equity: mide la regla de seleccion.
#
# MEDIDO en la ventana de 877 manos: la ultima accion del heroe cae en
# preflop 637 veces — 554 folds, 81 jugables, 2 checks — y de las 81
# jugables NINGUNA tiene etiqueta. Las 98 con etiqueta son todas folds.
ACCIONES_JUGADAS = ('b', 'c', 'r', 'x')

# Clave estable del descarte por fold. El informe la busca por NOMBRE: una
# clave que hay que reconstruir adivinando una cadena es una clave que se
# rompe sin avisar.
CLAVE_FOLD = 'el heroe FOLDEA en el corte'

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


def id_desconocido(hid, por_id):
    """Un hand_id de la particion que no esta en la ventana.

    `revision_2`: `h = por_id[hid]` presupone que todos los IDs de la
    particion estan en `ventana`. Puede ser una invariante legitima, pero
    reventar con un KeyError sin contexto no lo demuestra: deja claro QUE
    falta y nada mas.
    """
    raise KeyError(
        'la particion trae el hand_id %r y no esta en la ventana fiable. '
        'O la particion y la ventana no se construyeron del mismo sitio, o '
        'hay una mano fiable que se perdio por el camino. Sin esto no se '
        'puede saber cual de las dos es.' % (hid,))


def porque_no_reutilizable(entrada, version, estimador, t, n_combos, huella):
    """La lista de lo que NO coincide. Para no tener que releer el codigo."""
    if not isinstance(entrada, dict):
        return 'no es una entrada'
    esperado = (('version', version), ('estimador', estimador),
                ('semilla', t['semilla']), ('n_combos', n_combos),
                ('villano', t['villano']), ('spot', t['spot']),
                ('hero', t['hero']), ('huella', huella))
    return ', '.join('%s=%r != %r' % (k, entrada.get(k), v)
                     for k, v in esperado if entrada.get(k) != v)


def seleccionar_manos(etiqueta, por_id, model):
    """Las manos preflop que el camino preflop mete, con el recuento POR
    ETAPA y por spot.

    `revision_2` §1: esto estaba dentro de `main()` y por eso los
    contadores no se podian PROBAR, solo leer. Una refactorizacion podia
    conservar los nombres de las variables y volver a romper la auditoria
    sin que nada se notara. Aqui hay manos sinteticas que fallan en cada
    etapa y comprueban el recuento.

    Devuelve (trabajo, etapas, sin_rango, sp_cortes).
    """
    eqm = _m('equity_de_mano.py')
    trabajo = []
    sin_rango = collections.Counter()
    sp_cortes = collections.Counter()
    etapas = collections.defaultdict(collections.Counter)

    def _pasa(spot, etapa):
        etapas[etapa][spot] += 1
        etapas[etapa]["__total__"] += 1

    for hid, y in sorted(etiqueta.items()):
        if hid not in por_id:
            id_desconocido(hid, por_id)
        h = por_id[hid]
        hero = eqm.hero_pos_de(h)
        if not hero or y == 0.5:
            continue
        calle, idx = eqm.corte_de_decision(h, hero)
        if calle != 'preflop':
            continue

        # El SPOT se cuenta ANTES de mirar lo que hace el heroe, porque el
        # corte existe aunque luego se caiga. Si se cuentan las etapas
        # primero, la tabla enseña ceros donde hay manos, y una tabla de
        # ceros parece una poblacion vacia en vez de una poblacion
        # descartada. Que se vea DONDE se pierde es justamente el motivo de
        # que la tabla exista.
        spot = mano_del_spot(h, calle, hero, idx)
        sp_cortes[spot] += 1
        if spot is None or spot not in ACCIONES_SPOT:
            sin_rango['spot sin alternativas declaradas'] += 1
            continue
        _pasa(spot, '1_corte_preflop')

        # ETAPA 0: lo que el heroe HACE en el corte. Decide si la mano
        # pertenece a la poblacion del AUC, y va aqui y no antes porque el
        # corte tiene que estar CONTADO para que el descarte se vea.
        acts = ((h.get('streets') or {}).get(calle) or {}).get('actions') or []
        accion = acts[idx]['action'] if idx is not None \
            and idx < len(acts) else None
        if accion not in ACCIONES_JUGADAS:
            sin_rango[CLAVE_FOLD if accion == 'f' else
                      'el heroe hace %s, fuera de la poblacion B'
                      % (accion or 'nada')] += 1
            continue
        # DESPUES del descarte, como las demas: el contador dice las que
        # PASAN, no las que llegan. Ponerlo antes contaba 23 jugadas y
        # descartaba 23 por no jugar, en la misma fila.
        _pasa(spot, '0_accion_jugada')

        # ETAPA 1: el corte es preflop y el spot es uno de los tres.

        # ETAPA 2: las dos cartas del hero son legibles.
        mc = cartas_de(h, hero)
        if not mc:
            sin_rango['sin cartas del hero'] += 1
            continue
        _pasa(spot, '2_cartas_hero')

        # ETAPA 3: hay un rival identificable en el corte.
        nombre, vpos = villano_del_corte(h, hero, calle, idx)
        if not nombre:
            sin_rango['sin villano identificado en el corte'] += 1
            continue
        _pasa(spot, '3_rival')

        # ETAPA 4: el villano tiene perfil en el modelo.
        if nombre not in model.perfil:
            sin_rango['villano sin perfil: cae al prior plano'] += 1
            continue
        _pasa(spot, '4_perfil')

        trabajo.append({'id': hid, 'y': y, 'hero': mc, 'villano': nombre,
                        'vpos': vpos, 'spot': spot,
                        'semilla': semilla_de(hid),
                        'cartas_villano': cartas_de(h, vpos)})

    return trabajo, etapas, sin_rango, sp_cortes


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

    trabajo, etapas, sin_rango, sp_cortes = seleccionar_manos(
        etiqueta, por_id, model)

    print('   universo de la particion      : %d' % len(etiqueta))
    print('   cortes preflop con todo listo : %d' % len(trabajo))
    for k, n in sin_rango.most_common():
        print('      sin computo: %-44s %3d' % (k, n))
    n_fold = sin_rango.get(CLAVE_FOLD, 0)
    if n_fold:
        print()
        print('   %d cortes preflop quedan FUERA porque el heroe FOLDEA en el'
              % n_fold)
        print('   corte. Un fold tiene y = 0 por construccion —el que foldea')
        print('   no puede ganar—, asi que esas manos NO SON de la poblacion B')
        print('   del AUC. Meterlas mediria la regla de seleccion, no la')
        print('   equity. Es lo que pasaba antes de este filtro: 23 de 23 con')
        print('   y = 0, y las 75 de calibracion tambien.')
    print()
    print('   POR SPOT Y POR ETAPA. Cada etapa es un filtro DISTINTO y')
    print('   acumulado, asi que las columnas pueden bajarse: ahi se ve')
    print('   donde se pierde la poblacion.')
    print()
    print('      %-14s %6s %8s %7s %7s %7s %8s %9s'
          % ('spot', 'corte', 'juega', 'cartas', 'rival', 'perfil', 'ADMIT.',
             'calculada'))
    print('      ' + '-' * 75)
    hechos = cache_abrir()

    def calculadas_para(spot):
        """SOLO las admitidas, con equity, y de ESTA version.

        `revision_2`: contar cualquier diccionario con el spot coincide mete
        manos de otra VERSION y manos que ya no se admiten. Y el texto decia
        "de esta VERSION", que el filtro NO garantizaba.

        `spot=None` cuenta el TOTAL, con el mismo filtro. Es lo que evita
        que la fila TOTAL diga 0 con subtotales positivos.
        """
        n = 0
        for x in trabajo:
            if spot is not None and x['spot'] != spot:
                continue
            e = hechos.get(x['id'])
            if (isinstance(e, dict) and 'equity' in e
                    and e.get('version') == VERSION):
                n += 1
        return n

    # El TOTAL se cuenta con la MISMA funcion de validacion que los
    # subtotales. Antes se inicializaba a 0 y nunca se incrementaba, o sea
    # que la fila TOTAL decia 0 con subtotales positivos: `revision_2`.
    total_calc = calculadas_para(None)
    for spot in sorted(ACCIONES_SPOT):
        adm = sum(1 for x in trabajo if x['spot'] == spot)
        n_calc = calculadas_para(spot)
        print('      %-14s %6d %8d %7d %7d %7d %8d %9d'
              % (spot, sp_cortes.get(spot, 0),
                 etapas['0_accion_jugada'][spot],
                 etapas['2_cartas_hero'][spot], etapas['3_rival'][spot],
                 etapas['4_perfil'][spot], adm, n_calc))
    print('      %-14s %6d %8d %7d %7d %7d %8d %9d'
          % ('TOTAL', sum(sp_cortes.values()),
             etapas['0_accion_jugada']['__total__'],
             etapas['2_cartas_hero']['__total__'],
             etapas['3_rival']['__total__'],
             etapas['4_perfil']['__total__'], len(trabajo),
             total_calc))
    print()
    print('   ADMIT. son las que pasan las CINCO etapas. juega = el heroe no')
    print('   foldea en el corte, que es la condicion de la poblacion B.')
    print('   calculada es lo que ya esta en la cache de esta VERSION.')
    print()
    extras = [k for k in sp_cortes if k not in ACCIONES_SPOT]
    if extras:
        print('   Spots NO reconocidos (se cuentan aparte, con su clave):')
        for k in extras:
            print('      %-14r %6d' % (k, sp_cortes[k]))
        print('   Se cuentan porque verlos es el punto: un spot desconocido')
        print('   tiene que verse, no desaparecer.')
    else:
        print('   Spots no reconocidos: ninguno. Los tres declarados cubren')
        print('   todos los cortes.')
    print()
    print('   Motivos de descarte:')
    for k, n in sin_rango.most_common():
        print('      %-44s %3d' % (k, n))
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
        # ⚠️ Reciclar la AGREGADA exige que coincidan TODOS los parametros
        # que la determinan: version del procedimiento, estimador, semilla,
        # numero de combos, villano, spot y mano del hero. `revision_2` §2:
        # el `if hid in cache and 'equity' in cache[hid]` de antes ignoraba
        # todo eso, y hacia que el INFORME contara una version mientras el
        # CALCULO usaba otra. Informe y calculo tienen que mirar lo mismo.
        #
        # La equity POR COMBO, en cambio, se reutiliza sin comprobar nada:
        # `equity_preflop_contra_combo` es una funcion pura de las dos
        # manos, no depende del estimador ni de la VERSION.
        # El rango se calcula ANTES de decidir nada. Es lo que hace posible
        # la huella: comparar la identidad del rango exige tenerlo delante.
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
        huella = huella_de(t['hero'], ids, wl, t['semilla'], n, t['y'])

        entrada = cache.get(hid)
        if isinstance(entrada, dict) and 'equity' in entrada:
            if entrada.get('version') == VERSION \
                    and entrada.get('estimador') == ESTIMADOR \
                    and entrada.get('semilla') == t['semilla'] \
                    and entrada.get('n_combos') == N_COMBOS \
                    and entrada.get('villano') == t['villano'] \
                    and entrada.get('spot') == t['spot'] \
                    and entrada.get('hero') == t['hero'] \
                    and entrada.get('huella') == huella:
                continue
            # no coincide: se recalcula y se AVISA, no se reutiliza en
            # silencio. Y se dice POR QUE, que es lo que hace falta para
            # arreglarlo sin volver a leer todo el codigo.
            print('   %s: la entrada en cache no es reutilizable (%s); '
                  'se recalcula.'
                  % (hid, porque_no_reutilizable(entrada, VERSION, ESTIMADOR,
                                                 t, N_COMBOS, huella)))
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

        if n != N_COMBOS:
            # No es un error: el rango legal puede tener menos de N_COMBOS
            # combos. Lo que era un error es que la entrada guardara el
            # efectivo y la condicion comparara con el pedido, con lo que
            # una mano asi no se reutilizaba NUNCA. Se guardan los dos, con
            # sus nombres, y el aviso para que no pase por el dato previsto.
            print('   %s: el rango legal tiene %d combos y se han muestreado '
                  '%d, no %d (N_COMBOS). Se guarda el efectivo aparte.'
                  % (hid, len(ids), n, N_COMBOS))
        cache[hid] = {'equity': acc / n,
                      # lo PEDIDO, que es lo comparable entre versiones
                      'n_combos': N_COMBOS,
                      # lo EFECTIVO, que es lo que se divide de verdad
                      'n_muestreados': n,
                      'villano': t['villano'], 'spot': t['spot'],
                      'y': t['y'], 'hero': t['hero'],
                      'semilla': t['semilla'], 'version': VERSION,
                      'estimador': ESTIMADOR, 'huella': huella}
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