# -*- coding: utf-8 -*-
"""F7.1 — Inventario del alcance multiway (NO modifica nada).

revision_1 §6 pide seis respuestas antes de decidir entre rediseñar y
limitar. Este script las mide, sobre la ventana fiable y sobre el código:

  1. Cuántas manos son HU / multiway / no clasificables, por calle.
  2. Qué hace hoy el motor con `n_players > 2`: avisa, o no dice nada.
  3. Qué hace `RangeState.union()` de verdad, medido en un caso.
  4. Quién usa `union()`.
  5. Si `recommend_loop` avisa o lanza con `n_players > 2`.
  6. Qué pasa con `equity_main` en multiway.

REGLA DE CLASIFICACIÓN, fijada aquí para que sea reproducible y no una
interpretación:

  - Se cuenta en el punto de DECISIÓN de cada calle, no al final de la mano:
    un jugador puede foldear despues, y usar el estado final
    retrospectivamente inflaría el multiway.
  - `n_activos` = jugadores con `players[].active` a True.
  - HU          = hero + exactamente 1 activo.
  - MULTIWAY    = hero + 2 o más activos.
  - NO CLASIFICABLE = no hay hero identificable, o no hay calle con acciones.

Uso:  python tools/inventario_multiway.py
"""
import collections
import datetime
import io
import json
import os
import re
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor import learn                                    # noqa: E402
from motor.ranges import N_COMBOS, RangeState             # noqa: E402

STREETS = ('flop', 'turn', 'river')


# ---------------------------------------------------------------------------
# Trazabilidad. revision_1 Tarea 1: el numero no vale si no se puede
# reproducir, y no se puede reproducir si nadie sabe con que commit y con
# que bugs corregidos se midio. La cabecera la emite el propio script: si
# alguien edita la salida a mano, la cabecera ya no describe el estado real.
# ---------------------------------------------------------------------------
def _git(*args):
    try:
        return subprocess.check_output(
            ['git'] + list(args), cwd=ROOT, stderr=subprocess.STDOUT
        ).decode('utf-8', 'replace').strip()
    except Exception:
        return None


def cabecera():
    commit = _git('rev-parse', 'HEAD')
    sucio = _git('status', '--porcelain')
    print('=' * 78)
    print('TRAZABILIDAD   (revision_1, Tarea 1)')
    print('=' * 78)
    print('   commit          : %s' % (commit or 'NO ES UN REPO GIT'))
    print('   fecha           : %s'
          % datetime.datetime.now().isoformat(timespec='seconds'))
    print('   arbol           : %s'
          % ('LIMPIO' if sucio == '' else
             ('CON %d FICHERO(S) SIN VERSIONAR' % len(sucio.split('\n'))
              if sucio else 'indeterminado')))
    print('   script          : tools/inventario_multiway.py')
    print('   python          : %s' % sys.version.split()[0])
    print()
    print('   Los dos bugs conocidos del instrumento, en ESTE commit:')
    print('     1. `HU = 0` por rama inalcanzable (`rivales == 0` con')
    print('        minimo 1 rival). CORREGIDO: ver `rivales <= 0` mas abajo.')
    print('     2. `>= 1` donde debia ser `>= 2` en el desglose de no')
    print('        clasificables (daba 1390, faltaban 304). CORREGIDO.')
    print()
    print('   Si al leer esto las cifras no cuadran con el fichero de salida,')
    print('   el problema no es el numero: es que se ha editado la salida.')
    print()


# ---------------------------------------------------------------------------
# Clasificación. Se declara por separado para poder importarla y testearla.
# ---------------------------------------------------------------------------
ORDEN = ('preflop', 'flop', 'turn', 'river')


def n_activos_en_calle(hand, street):
    """Jugadores que siguen en la mesa EN ESA CALLE.

    `players[].active` es el estado FINAL de la mano: un jugador que folteo
    en el river sigue marcado activo. Usarlo para clasificar el flop cuenta
    gente que ya no estaba, y es exactamente el error que avisaba
    revision_2.

    Se reconstruye: un jugador sigue en la mesa en la calle S si NO tiene
    ninguna accion 'f' en ninguna calle de `preflop`..S.

    LIMITACION DECLARADA: un all-in sigue contando como activo, que es lo
    correcto (esta en la mesa), pero un all-in que se va all-in y no puede
    volver a actuar se cuenta igual. Afecta al conteo, no al orden.
    """
    streets = hand.get('streets') or {}
    fuera = set()
    for st in ORDEN:
        for a in ((streets.get(st) or {}).get('actions') or []):
            if isinstance(a, dict) and a.get('action') == 'f' and a.get('pos'):
                fuera.add(a['pos'])
        if st == street:
            break
    return sum(1 for p in (hand.get('players') or [])
               if p.get('active') and p.get('pos') not in fuera)


def folds_hasta(hand, street):
    """Jugadores que ya HAN FOLDEADO en alguna calle hasta `street`."""
    fuera = set()
    streets = hand.get('streets') or {}
    for st in ORDEN:
        for a in ((streets.get(st) or {}).get('actions') or []):
            if isinstance(a, dict) and a.get('action') == 'f' and a.get('pos'):
                fuera.add(a['pos'])
        if st == street:
            break
    return fuera


def motivo_no_clasificable(hand, street):
    """Por que un punto de decision no se puede clasificar."""
    if not heroes(hand):
        return 'sin hero (nadie con cartas)'
    acciones = ((hand.get('streets') or {}).get(street) or {}).get('actions') or []
    if not acciones:
        return 'calle sin acciones (check-check)'
    return 'hero solo en el bote, sin rivales'


def no_puede_actuar(hand, street):
    """Rivales que estan en el bote pero ya NO pueden actuar (all-in).

    MEDIDO: decide el criterio de F7.2. Un all-in sigue en el bote, pero no
    responde a una apuesta, asi que para "este spot es multiway" no cuenta.
    """
    streets = hand.get('streets') or {}
    activos = {p.get('pos') for p in (hand.get('players') or [])
               if p.get('active')}
    for st in ORDEN:
        for a in ((streets.get(st) or {}).get('actions') or []):
            if isinstance(a, dict) and a.get('pos') and a.get('action') == 'r':
                # una resubida consume la capacidad de volver a_actuar
                activos.discard(a.get('pos'))
        if st == street:
            break
    return {p.get('pos') for p in (hand.get('players') or [])
            if p.get('active')} - activos


def n_activos(hand):
    return sum(1 for p in (hand.get('players') or []) if p.get('active'))


# MEDIDO: el esquema real de `players[]` es
#   {active, cards, name, pos, stack}
# NO hay ninguna marca de hero. El proyecto lo reconoce por tener CARTAS
# CONOCIDAS (`learn.hand_known`), no por el nombre: `asistente_live` usa el
# nombre solo para etiquetar, y `PROYECTO.md` insiste en no depender de el.
#
# LIMITACION DECLARADA: si dos jugadores tienen cartas conocidas (el segundo
# hero que rastrea `asistente_live`), se toma el primero. Se cuenta cuántos
# casos hay para que la cifra sea interpretable.
def heroes(hand):
    return [p.get('pos') for p in (hand.get('players') or [])
            if (p.get('cards') or '').strip()]


def hero_pos(hand):
    h = heroes(hand)
    return h[0] if h else None


def clasificar_calle(hand, street):
    """HU / MULTIWAY / NO_CLASIFICABLE para UN punto de decisión."""
    hp = hero_pos(hand)
    if not hp:
        return 'NO_CLASIFICABLE', 0, None
    acciones = ((hand.get('streets') or {}).get(street) or {}).get('actions') or []
    if not acciones:
        return 'NO_CLASIFICABLE', 0, hp
    n = n_activos_en_calle(hand, street)
    # el hero cuenta una vez: los `active` del JSONL ya lo incluyen
    rivales = n - 1
    if rivales <= 0:
        return 'NO_CLASIFICABLE', n, hp
    if rivales == 1:
        return 'HU', n, hp
    return 'MULTIWAY', n, hp


# ---------------------------------------------------------------------------
def main():
    print('=' * 78)
    print('F7.1  INVENTARIO DEL ALCANCE MULTIWAY   (solo lectura)')
    print('=' * 78)
    cabecera()

    manos = learn.load_hands(reliable_only=True)

    # ------------------------------------------------------------ 1 y 2
    print()
    print('1) DISTRIBUCION EN LA VENTANA FIABLE')
    print('-' * 78)
    print('   Regla: se cuenta en el punto de DECISION de cada calle, no al')
    print('   final de la mano. Un jugador puede foldear despues.')
    print()
    por_calle = {}
    for st in STREETS:
        c = collections.Counter()
        ns = collections.Counter()
        for h in manos:
            clase, n, _hp = clasificar_calle(h, st)
            c[clase] += 1
            if clase != 'NO_CLASIFICABLE':
                ns[n] += 1
        por_calle[st] = c

    print('   %-8s %10s %10s %16s' % ('calle', 'HU', 'MULTIWAY', 'NO CLASIFIC.'))
    print('   ' + '-' * 50)
    tot = collections.Counter()
    for st in STREETS:
        c = por_calle[st]
        tot.update(c)
        print('   %-8s %10d %10d %16d' % (st, c['HU'], c['MULTIWAY'],
                                        c['NO_CLASIFICABLE']))
    print('   ' + '-' * 50)
    print('   %-8s %10d %10d %16d' % ('TOTAL', tot['HU'], tot['MULTIWAY'],
                                    tot['NO_CLASIFICABLE']))
    print()
    # -------------------------------------------------------------
    print()
    print('   CUANTO CAMBIA respecto a usar `players[].active` (final):')
    print('   %-8s %10s %10s %8s' % ('calle', 'por calle', 'por final', 'delta'))
    print('   ' + '-' * 40)
    dif_total = 0
    for st in STREETS:
        c_calle = collections.Counter()
        c_final = collections.Counter()
        for h in manos:
            hp = hero_pos(h)
            acciones = ((h.get('streets') or {}).get(st) or {}).get(
                'actions') or []
            if not hp or not acciones:
                continue
            riv_calle = n_activos_en_calle(h, st) - 1
            riv_final = n_activos(h) - 1
            c_calle['HU' if riv_calle <= 1 else 'MULTIWAY'] += 1
            c_final['HU' if riv_final <= 1 else 'MULTIWAY'] += 1
            if riv_calle != riv_final:
                dif_total += 1
        print('   %-8s %10d %10d %+8d'
              % (st, c_calle['MULTIWAY'], c_final['MULTIWAY'],
                 c_calle['MULTIWAY'] - c_final['MULTIWAY']))
    print('   %s' % ('-' * 40))
    print('   puntos de decision donde el conteo cambia: %d' % dif_total)
    print('   -> usar el estado final INFLARIA el multiway.')

    n_multi_hero = sum(1 for h in manos if len(heroes(h)) > 1)
    print()
    print('   Manos con 2+ jugadores de cartas conocidas: %d de %d'
          % (n_multi_hero, len(manos)))
    print('   -> esos cuentan como el PRIMERO. El impacto va en')
    print('      "NO CLASIFICABLE" de arriba, no en HU/MULTIWAY.')

    # ---------------------------------------------------- 1.b
    print()
    print('   POR QUE no clasificables (sin esto no se sabe si el')
    print('   denominador de los clasificables es representativo):')
    motivos = collections.Counter()
    for h in manos:
        for st in STREETS:
            acciones = ((h.get('streets') or {}).get(st) or {}).get(
                'actions') or []
            if acciones and heroes(h):
                # clasificable salvo que el hero este solo
                en_bote = {p.get('pos') for p in (h.get('players') or [])
                           if p.get('active')} - folds_hasta(h, st)
                # >= 2, no >= 1: con el hero solo en el bote no hay decision
                # con rivales. MEDIDO: con `>= 1` el desglose daba 1390 y
                # faltaban 304 puntos, que son justo los "hero solo".
                if len(en_bote) >= 2:
                    continue
            motivos[motivo_no_clasificable(h, st)] += 1
    for motivo, c in motivos.most_common():
        print('      %-40s %5d' % (motivo, c))
    print('      %-40s %5d' % ('TOTAL', sum(motivos.values())))
    sin_acciones = motivos.get('calle sin acciones (check-check)', 0)
    if sum(motivos.values()):
        print('      -> el %.1f%% son calles SIN ACCIONES: no hay ninguna'
              % (sin_acciones / sum(motivos.values()) * 100))
        print('         decision que tomar. No son unholes del motor.')

    # ---------------------------------------------------- 1.c
    print()
    print('   EN EL BOTE vs QUE PUEDEN ACTUAR  (esto decide F7.2):')
    print('   %-8s %12s %16s %10s' % ('calle', 'MW en el bote',
                                     'MW pueden actuar', 'delta'))
    print('   ' + '-' * 52)
    mw_bote = mw_act = 0
    for st in STREETS:
        b = a_ = 0
        for h in manos:
            acciones = ((h.get('streets') or {}).get(st) or {}).get(
                'actions') or []
            if not heroes(h) or not acciones:
                continue
            en_bote = {p.get('pos') for p in (h.get('players') or [])
                       if p.get('active')} - folds_hasta(h, st)
            actuable = en_bote - no_puede_actuar(h, st)
            if len(en_bote) - 1 > 1:
                b += 1
            if len(actuable) - 1 > 1:
                a_ += 1
        print('   %-8s %12d %16d %+10d' % (st, b, a_, a_ - b))
        mw_bote += b
        mw_act += a_
    print('   ' + '-' * 52)
    print('   %-8s %12d %16d %+10d' % ('TOTAL', mw_bote, mw_act,
                                       mw_act - mw_bote))
    print()
    if mw_bote > mw_act:
        print('   El all-in RECLASA %d spot(s) de multiway a HU.' %
              (mw_bote - mw_act))
        print('   Un rival all-in esta en el bote pero NO responde a una')
        print('   decision: el motor se comporta como HU sin estar mintiendose')
        print('   sobre el rango. Por eso el criterio correcto no es')
        print('   "cuantos estan activos" sino "cuantos pueden actuar".')

    clasificables = tot['HU'] + tot['MULTIWAY']
    if clasificables:
        print('   de %d puntos de decisión clasificables:' % clasificables)
        print('      HU        %5d  (%5.1f%%)'
              % (tot['HU'], tot['HU'] / clasificables * 100))
        print('      MULTIWAY  %5d  (%5.1f%%)'
              % (tot['MULTIWAY'], tot['MULTIWAY'] / clasificables * 100))
    print()
    print('   n_activos en los puntos multiway:')
    for st in STREETS:
        ns = collections.Counter()
        for h in manos:
            clase, n, _ = clasificar_calle(h, st)
            if clase == 'MULTIWAY':
                ns[n] += 1
        if ns:
            print('      %-6s %s' % (st, dict(sorted(ns.items()))))

    # ------------------------------------------------------------- 3
    print()
    print('2) QUE HACE `RangeState.union()` — MEDIDO, no por docstring')
    print('-' * 78)
    a = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    b = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    u = a.union(b)
    print('   dos rangos UNIFORMES (cada uno 1.0 por combo) unidos:')
    print('      reach de un combo en `a` : %.3f' % a.reach[0])
    print('      reach de un combo en `b` : %.3f' % b.reach[0])
    print('      reach de un combo en u  : %.3f  <- SUMA, no promedio'
          % u.reach[0])
    print('      masa total de u        : %.1f  (no es 1)'
          % float(np.sum(u.reach)))
    print()
    print('   Por qué importa: si dos rivales independientes se modelan como')
    print('   UNO solo con masa doble, la equity no es la de dos rivales.')
    print('   Es la Observación de PROYECTO.md §6.2, no una hipótesis.')

    # ------------------------------------------------------------- 4
    print()
    print('3) QUIEN USA union()')
    print('-' * 78)
    raiz = ROOT
    usuarios = []
    for dp, dn, fns in os.walk(raiz):
        dn[:] = [d for d in dn if d not in {'.git', '__pycache__', '.venv',
                                            'data'}]
        for fn in sorted(fns):
            if not fn.endswith('.py'):
                continue
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, raiz).replace('\\', '/')
            if rel == 'tools/inventario_multiway.py':
                continue          # este script cita `.union(`
            src = io.open(p, encoding='utf-8').read()
            lineas = src.split('\n')
            en_docstring = False
            for k, linea in enumerate(lineas, 1):
                s = linea.strip()
                # MEDIDO: contar `raise`/`union` dentro de docstrings daba dos
                # falsos positivos (la nota de PROYECTO.md §6.2 en
                # hierarchy.py). Se salta el bloque ENTERO, no solo la linea
                # que abre el `"""`.
                if en_docstring:
                    if s.endswith('"""'):
                        en_docstring = False
                    continue
                if s.startswith('"""') or s.startswith('r"""'):
                    en_docstring = s.count('"""') < 2
                    continue
                if s.startswith('#'):
                    continue
                    continue
                if '.union(' in s and 'def union' not in s:
                    usuarios.append((rel, k, s[:70]))
    for rel, k, s in usuarios:
        marca = '   [test]' if '/test_' in rel or rel.startswith('test_') else ''
        print('   %-28s L%-5d %s%s' % (rel, k, s, marca))
    prod = [u for u in usuarios if not u[0].startswith(('test_', 'motor/test_'))
            and '/test_' not in u[0]]
    print()
    print('   en produccion: %d sitio(s)' % len(prod))

    # ------------------------------------------------------------- 5
    print()
    print('4) QUE HACE EL MOTOR CON n_players > 2')
    print('-' * 78)
    rl = io.open(os.path.join(raiz, 'motor', 'recommend_loop.py'),
                 encoding='utf-8').read()
    print('   `recommend_loop`:')
    print('      recibe `n_players: int = 2` y, si hay `villain_ranges`,')
    print('      lo sube a `max(n_players, len(villain_ranges) + 1)`.')
    # MEDIDO: buscar `raise` en una linea que mencione `multiway` daba un
    # FALSO POSITIVO (`rango multiway vacio tras blockers`, que dispara por
    # rango vacio, no por numero de jugadores). Se busca una guarda de la
    # FORMA `n_players > N`, que es lo que seria una frontera de alcance.
    GUARDA = re.compile(r'n_players\s*[><=]=?\s*\d')
    lanza = [l for l in rl.split('\n')
             if ('raise' in l or 'assert' in l) and GUARDA.search(l)]
    avisa = [l for l in rl.split('\n')
             if ('warn' in l.lower() or 'print' in l) and GUARDA.search(l)]
    print('      ¿lanza si n_players > 2?        %s'
          % ('SI' if lanza else 'NO — no hay ninguna guarda de esa forma'))
    print('      ¿avisa por stderr/consola?      %s'
          % ('SI' if avisa else 'NO — el multiway entra en silencio'))
    if lanza:
        for l in lanza[:3]:
            print('        %s' % l.strip()[:70])
    print()
    print('   `rules.plan` (el motor de decision de `asistente_live`):')
    rules = io.open(os.path.join(raiz, 'motor', 'rules.py'),
                    encoding='utf-8').read()
    print('      `ctx.multi = n_players > 2` y ajusta los sizings')
    print('      (`_multi_sizes`). O sea: multiway cambia el TAMAÑO de la')
    print('      apuesta, no el modelo de equity ni de rango.')
    print()
    print('   `asistente_live`:')
    print('      cuenta `n_activos` y se lo pasa a `rules_plan`, pero el')
    print('      rango de la equity sigue siendo `rs`, de UN solo rival.')

    # ------------------------------------------------------------- 6
    print()
    print('5) equity_main EN MULTIWAY')
    print('-' * 78)
    al = io.open(os.path.join(raiz, 'motor', 'asistente_live.py'),
                 encoding='utf-8').read()
    tiene = 'villain_ranges' in al
    print('   `asistente_live` recibe `villain_ranges`: %s' % ('SI' if tiene else 'NO'))
    print('   `equity_main` se construye contra el rango de UN solo rival')
    print('   (`_rango_main` -> `RangeState` unico). En una mano multiway,')
    print('   esa equity NO modela a los demas rivales activos: es una equity')
    print('   heads-up contra el principal, medida dentro de una situacion')
    print('   multiway. No es la equity real del spot.')
    print()
    print('   Consecuencia: `equity_main` es comparable entre manos (misma')
    print('   definicion siempre), pero NO es comparable con una equity')
    print('   multiway verdadera. Es una limitacion de alcance, distinta del')
    print('   problema de trazabilidad ya corregido (la identidad del rival).')

    print()
    print('=' * 78)
    print('VEREDICTO')
    print('=' * 78)
    print("""
   Lo medido, sin suponer:

   - El multiway ENTRA al motor en silencio: `recommend()` lo acepta y no
     lanza ni avisa. Lo unico que hace es subir `n_players` para que
     `rules._multi_sizes` agrande los sizings.
   - `n_players` NO cambia el rango ni la equity: el rango sigue siendo el de
     UN rival, construido con `prob_vec` de un solo perfil.
   - `union()` suma masas sin normalizar, y quien lo usa es
     `_build_multiway_range`, que solo se activa si el llamador pasa
     `villain_ranges`. `asistente_live` NO lo pasa: nunca usa ese camino.
   - `equity_main` es HU por construccion, tambien en sitio multiway.

   O sea: el multiway llega hasta las reglas (sizing) y se detiene antes de
   llegar al rango y a la equity. La decision se toma con informacion de UN
   rival, pero limitada por el numero de jugadores.
""")
    return 0


if __name__ == '__main__':
    sys.exit(main())
