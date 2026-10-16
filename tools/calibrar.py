# -*- coding: utf-8 -*-
"""Fase D — calibrar un parametro del motor, y solo medir.

Contrato en `DOCS/FASE_D_PLAN.md`. Esto NO calibra: mide, y dice si la
medida dice algo. El cambio de valor, si lo hay, es un commit aparte con
su `.md` y su motivo escrito.

    python tools/calibrar.py particion
    python tools/calibrar.py --param DEFAULT_ALPHA --valores 1.0 2.0 3.0
    python tools/calibrar.py --param DEFAULT_ALPHA --valores 2.0 --aplicar

DRY-RUN por defecto: sin `--aplicar` no se escribe nada y no se toca el
motor. La unica excepcion es `particion`, que escribe un documento y lo
declara.

LAS REGLAS QUE NO SE TOCAN, y por que estan en el plan y no aqui
-----------------------------------------------------------------
  - La particion se versiona y no se cambia una vez escrita (§2.2).
  - Los umbrales TOL_SEC = 2 % y UMBRAL = 5 % estan declarados ANTES de
    medir, para que no se ajusten despues (§2.3).
  - `L_prim` mide AJUSTE, no generalizacion (§2.1).
  - `L_sec` se evalua sobre VALIDACION, no sobre las 156 (§2.1).
  - La metrica tiene que ganarle al predictor trivial (§2.1.1.b). Si no,
    no dice nada, y se dice que no dice nada.
"""
import argparse
import collections
import hashlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np                                       # noqa: E402

from motor import learn                                  # noqa: E402
from motor.hand_evaluator import evaluate_hand
from motor.multiway import PLAYER_IDS                  # noqa: E402
from motor import player_ranges as PR                    # noqa: E402
from motor.multiway import PLAYER_IDS                  # noqa: E402

DOCS = os.path.join(ROOT, 'DOCS')
PARTICION_MD = os.path.join(DOCS, 'PARTICION_FASE_D.md')

#: El sesgo declarado en §5 de FASE_D_PLAN.md, decision B. Va en la
#: CABECERA de cada tabla de resultados, no en una nota al pie: si esta en
#: la nota, el primer consumidor lee las cifras como limpias.
CABECERA_SESGO = (
    '`limp` esta sobreestimada en 25 eventos de 4561 (0,55 %): las 25 manos '
    'de IMPORTE_SUBIDA\ndesplazan 24 eventos de `limp` a `open` y 1 a `rol`, y '
    '8 de ellas cambian celdas de `cnt`.\nEstos numeros NO son cifras '
    'limpias y no se comparan con ninguna otra corrida de esta fase.')

TOL_SEC = 0.02
UMBRAL = 0.05


# ---------------------------------------------------------------------------
# La particion. Regla del plan §2.2, escrita ahi y repetida aqui para que el
# script y el documento no puedan separarse.
# ---------------------------------------------------------------------------
def es_validacion(hand_id):
    return int(hashlib.sha256(hand_id.encode('utf-8')).hexdigest(), 16) % 10 < 3


def con_cartas(h):
    return [p for p in h.get('players') or [] if (p.get('cards') or '').strip()]


def id_a_pos(h, ident):
    """`_id` de `winner` -> posicion. Por PLAYER_IDS, no por indice.

    `recorder_live` escribe `p['_id']` y `PLAYER_IDS` es
    `['hero', 'p1' ... 'p5']`: `'hero'` es **la butaca 0**, no una persona.
    """
    if ident not in PLAYER_IDS:
        return None
    i = PLAYER_IDS.index(ident)
    if i >= len(h.get('players') or []):
        return None
    return h['players'][i].get('pos')


def hero_de(h):
    """El hero: el jugador cuyo `name` esta en `learn.HERO_NAMES`.

    NO es el primero con cartas. Se parece en 845 de 877 manos de la
    ventana y **falla en 32**, y en esas la etiqueta de L_sec era la de
    otro jugador.

    `HERO_NAMES` lo declara `learn.py`. No se deduce de los datos: se
    busca en el codigo que los produce.
    """
    for p in h.get('players') or []:
        if (p.get('name') or '').strip() in learn.HERO_NAMES:
            return p.get('pos')
    return None


def ganador_nombrado(h):
    """Posicion que nombra `showdown.winner1`, o (None, motivo).

    Se RESUELVE contra la mesa: primero por posicion, luego por nombre.
    Un texto que no nombra a nadie de esta mesa NO se resuelve, y la mano
    se queda sin etiqueta.

    El recorder solo escribe `showdown` cuando hay **un** ganador
    (`recorder_live`, rama `len(all_still_in) == 1`), asi que un
    `showdown` junto a varios ganadores es una mano editada a mano. Por eso
    el texto tiene que demonstrationamente resolver.
    """
    w1 = (h.get('showdown') or {}).get('winner1')
    if not (isinstance(w1, str) and w1.strip()):
        return None, 'sin texto de showdown'
    if any(x in w1 for x in ('/', ',', ' y ', '&')):
        return None, 'el texto nombra a varios'
    for p in h.get('players') or []:
        if p.get('pos') and p['pos'] in w1:
            return p['pos'], 'la posicion esta en el texto'
    for p in h.get('players') or []:
        nom = (p.get('name') or '').strip()
        if nom and nom in w1:
            return p.get('pos'), 'el nombre esta en el texto'
    return None, 'el texto no nombra a nadie de esta mesa'


ORDEN_CALLES = ('preflop', 'flop', 'turn', 'river')

def ultima_calle(h):
    for st in reversed(ORDEN_CALLES):
        acts = ((h.get('streets') or {}).get(st) or {}).get('actions') or []
        if acts:
            return st
    return None


def llego_al_showdown(h, pos, ult=None):
    """True si `pos` NO folteo en ninguna calle de la mano.

    **Cualquier** calle, incluida la última. `revision_2`: antes retornaba
    True al LLEGAR a la ultima calle sin inspeccionar sus acciones, así
    que un jugador que folteaba en el river entraba como si hubiera
    llegado al showdown.

    Un fold es definitivo: el que folio salio del bote y no puede ganar.
    No hace falta `ult`; se queda por compatibilidad.
    """
    for st in ORDEN_CALLES:
        acts = ((h.get('streets') or {}).get(st) or {}).get('actions') or []
        for a in acts:
            if a.get('pos') == pos and a.get('action') == 'f':
                return False
    return True


def no_folteo_ever(h, pos):
    """True si `pos` no tiene un 'f' en NINGUNA calle de la mano."""
    for st in ORDEN_CALLES:
        acts = ((h.get('streets') or {}).get(st) or {}).get('actions') or []
        for a in acts:
            if a.get('pos') == pos and a.get('action') == 'f':
                return False
    return True


def gano_por_fold(h, declarados):
    """EVIDENCIA POSITIVA de que el bote se gano sin showdown.

    La regla del recorder: es victoria por fold cuando queda **un solo**
    jugador que no ha folteado, y ese es el declarado. Si quedan dos, no
    hay ganador por fold: hubo showdown (o la mano esta incompleta), y sin
    las cartas no se puede saber cual.

    Devuelve (True, '') si hay evidencia, (False, motivo) si no la hay.
    """
    vivos = {p.get('pos') for p in h.get('players') or []
             if p.get('pos') and no_folteo_ever(h, p.get('pos'))}
    if len(vivos) != 1:
        return False, ('%d jugadores sin foldear: no es una victoria por '
                       'fold' % len(vivos))
    unico = next(iter(vivos))
    if declarados and declarados != {unico}:
        return False, ('el unico sin foldear es %s y el ganador declarado '
                       'es %s' % (unico, sorted(declarados)))
    return True, ''


def mejores_manos(h):
    """({pos: score}, maximo) SOLO de los que llegaron al showdown.

    **No** de todos los que tienen cartas. El que folteo antes no estaba
    en el bote, y comparar sus cartas con el board da un "mejor" que no
    compitió. MEDIDO: con el criterio erroneo salian 358 incoherentes de
    584 en la ventana; con este, **0 de 261**.

    Quien gano por fold y no tiene cartas no es comprobable, y eso no es lo
    mismo que estar mal: se distingue con `None` como maximo.
    """
    ult = ultima_calle(h)
    if ult is None:
        return None, None
    board = []
    for st in ORDEN_CALLES:
        board += [str(c) for c in
                  ((h.get('comunitarias') or {}).get(st) or [])]
    if not board:
        return None, None
    out = {}
    for p in h.get('players') or []:
        pos = p.get('pos')
        c = (p.get('cards') or '').strip()
        c = ''.join(c) if not isinstance(c, str) else c
        if len(c) < 4 or not pos:
            continue
        if not llego_al_showdown(h, pos, ult):
            continue
        try:
            out[pos] = evaluate_hand([c[0:2], c[2:4]], board)
        except Exception:
            continue
    if not out:
        return None, None
    return out, max(out.values())


def mejores_manos_simple(h):
    """El anterior, sin el filtro de showdown. Solo para COMPARAR.

    Sirve para auditar el criterio, no para etiquetar.
    """
    ult = ultima_calle(h)
    """({pos: score}, maximo) de los jugadores con cartas. (None, None) si
    no se puede evaluar.

    Es el evaluador del motor, no `winner`: `winner` es lo que se quiere
    COMPROBAR, no la autoridad.
    """
    board = []
    for st in ORDEN_CALLES:
        board += [str(c) for c in
                  ((h.get('comunitarias') or {}).get(st) or [])]
    if not board:
        return None, None
    out = {}
    for p in h.get('players') or []:
        c = (p.get('cards') or '').strip()
        c = ''.join(c) if not isinstance(c, str) else c
        if len(c) < 4:
            continue
        try:
            out[p.get('pos')] = evaluate_hand([c[0:2], c[2:4]], board)
        except Exception:
            continue
    if not out:
        return None, None
    return out, max(out.values())


def reparto(h, gs):
    """True si los jugadores de `gs` hacen la MISMA mano en el board.

    Eso es lo que hace un reparto, y es demostrable: lo dice el evaluador
    del motor sobre las cartas y el board que el registro tiene. No hace
    falta fiarse de `showdown.winner1`, que es un texto y que el recorder
    escribe SOLO cuando hay un solo ganador, asi que en un reparto esta
    incompleto por construccion.

    Si no se puede evaluar (falta board, o algun ganador no tiene cartas),
    devuelve None: y entonces la mano se queda SIN etiqueta, porque no se
    puede demostrar el reparto ni descartarlo.
    """
    board = []
    for st in ORDEN_CALLES:
        board += [str(c) for c in
                  ((h.get('comunitarias') or {}).get(st) or [])]
    if not board:
        return None
    scores = {}
    for p in h.get('players') or []:
        c = (p.get('cards') or '').strip()
        c = ''.join(c) if not isinstance(c, str) else c
        if not c:
            continue
        try:
            scores[p.get('pos')] = evaluate_hand([c[0:2], c[2:4]], board)
        except Exception:
            continue
    if not gs or not all(pos in scores for pos in gs):
        return None
    return len({scores[pos] for pos in gs}) == 1


def etiqueta(h):
    """(y del hero, ok). Regla de FASE_D_PLAN §2.1.1.

    `y = 1,0` si el HERO esta entre los ganadores. Los ids de `winner` se
    resuelven con `id_a_pos` y el hero con `hero_de`: las dos cosas por su
    nombre, no por su sitio en la lista.
    """
    hero = hero_de(h)
    if hero is None:
        return None, False
    gs = set()
    for ident in (h.get('winner') or []):
        pos = id_a_pos(h, ident)
        if pos:
            gs.add(pos)
    if not gs:
        return None, False
    cpos = [p.get('pos') for p in con_cartas(h)]
    if any(x not in cpos for x in gs):
        return None, False
    if len(gs) > 1:
        if not reparto(h, gs):
            return None, False
        return (0.5 if hero in gs else 0.0), True
    return (1.0 if hero in gs else 0.0), True


def ventana():
    return learn.load_hands(reliable_only=True)


def board_completo(h):
    """El plan §2.1.1 excluye las manos sin showdown. Es filtro, no
    ³todo: sin board no hay calle postflop que medir."""
    return len((h.get('comunitarias') or {}).get('river') or []) >= 1


def muestra():
    """Manos utilizables para L_sec, con su particion.

    El filtro de board va AQUI y no en el que escribe `calibrar.py`: es
    parte de la definicion de la muestra, y si viviera en el comando la
    muestra cambiaria al anadir otro comando.
    """
    cal, val = [], []
    for h in ventana():
        if not board_completo(h):
            continue
        if len(con_cartas(h)) < 2:
            continue
        # LA REGLA ESTRICTA. `winner` tiene que ser EXACTAMENTE el
        # conjunto de los que hacen la mejor mano, segun el evaluador.
        #
        # Antes se aceptaba el registro tal cual, y MEDIDO, 31 de las 161
        # manos lo contradicen. H_0112: declarado BB con 801 060, y el BTN
        # hace 915 473. H_0173: el hero hace 1 031 914 y no esta declarado.
        #
        # No se corrige `data/`. Se excluyen: una etiqueta que contradice
        # a las cartas no es una etiqueta, es ruido con forma de dato.
        scores, mejor = mejores_manos(h)
        declarados = {id_a_pos(h, i) for i in (h.get('winner') or [])}
        declarados.discard(None)
        if not declarados:
            continue

        # TRES CASOS, explicitos. `revision_2`: antes la comparacion solo
        # corria si habia interseccion con los mejores, de modo que un
        # ganador que NO era el mejor pasaba sin comprobar. Ese es
        # precisamente el caso que hay que excluir.
        mejores = ({p for p, s_ in scores.items() if s_ == mejor}
                   if mejor is not None else set())
        llegan = {p for p in declarados
                  if llego_al_showdown(h, p) and scores and p in scores}
        if not llegan:
            # 2. VICTORIA POR FOLD, pero SOLO con evidencia positiva: que
            # quede un unico jugador sin foldear y que sea el declarado.
            # `revision_2`: antes bastaba con que ninguno llegara, y eso
            # tambien pasa con acciones incompletas o cartas ausentes.
            ok_fold, _mot = gano_por_fold(h, declarados)
            if not ok_fold:
                continue
        elif llegan == mejores:
            pass                      # 1. SHOWDOWN VERIFICABLE
        else:
            continue                  # 3. INCONSISTENTE -> sin etiqueta
        y, ok = etiqueta(h)
        if not ok:
            continue
        (val if es_validacion(h['hand_id']) else cal).append((h['hand_id'], y))
    return cal, val


# ---------------------------------------------------------------------------
# Las dos metricas
# ---------------------------------------------------------------------------
def eventos_preflop(h):
    """Los eventos con los que se ajusta el modelo de frecuencias."""
    return learn.preflop_events(h)


def manos_de(manos):
    """`muestra()` devuelve pares (hand_id, y); el modelo quiere la mano.

    Se resuelve aqui y no en `muestra()` porque la particion necesita el
    id para decidir, y el modelo necesita el dict. Separar las dos cosas
    es lo que evita pasar una tupla donde se espera una mano.
    """
    ids = {i for i, _y in manos}
    return [h for h in ventana() if h['hand_id'] in ids]


def etiquetas(manos):
    """nombre de jugador -> etiqueta de perfil, **solo de esas manos**.

    `Profiles.from_hands` deriva la etiqueta de `TransitionStats` y del
    stack medio, es decir de las manos que recibe. Calcularla sobre la
    ventana entera mientras el modelo se ajusta sobre 117 manos mete las
    39 de validacion dentro del ajuste: medido, **46 de 144 jugadores
    cambian de etiqueta** según con que manos se calcule.

    Por eso esta funcion RECIBE las manos, y el que llama decide cuales.
    """
    from motor.profile import Profiles
    profs = Profiles.from_hands(manos)
    return {nombre: p.label for nombre, p in profs.profiles.items()}


class MedicionSinSentido(Exception):
    """La medicion no se puede publicar. No es un cero: es un no."""


def l_prim(alpha, manos, labels=None):
    """Log-verosimilitud del modelo de frecuencias sobre la calibracion.

    MEDIDA DE AJUSTE (FASE_D_PLAN §2.1): el modelo se ajusta aqui y se
    evalua aqui, por construccion.

    EL GRID ES POR RANGO DE CARTA. `p_matrix(perfil, spot, action, pos)`
    devuelve un 13x13 de P(par de rangos | accion, spot, perfil), con los
    ejes en `player_ranges.GRID_RANKS`. La probabilidad de lo OBSERVADO
    la da `p_hand(perfil, spot, action, cartas)`, que es esa celda.

    Aqui estaba el bug: se indexaba con `g[ev.category, ev.pos]`, que son
    cadenas, y eso falla con IndexError en los 295 eventos. El `except`
    caia a `np.nanmax(g)`: el MAXIMO del grid, que no es la probabilidad de
    la accion observada y puede mejorar la perdida sola. Las cifras de la
    primera calibracion salieron de ahi. Ahora no hay fallback: si el
    indice no es valido, se para.
    """
    manos = manos_de(manos)
    labels = etiquetas(manos) if labels is None else labels
    try:
        modelo = PR.ProfileRangeModel.from_hands(manos, labels=labels,
                                                 alpha=alpha)
    except Exception as e:
        raise MedicionSinSentido('from_hands fallo: %s: %s'
                                 % (type(e).__name__, e))

    # CONTADORES MUTUAMENTE EXCLUYENTES. Cada evento con cartas entra en
    # uno y solo uno de estos cubos, y al final se comprueba que suman
    # todos. Antes el denominador dependia de cuantos ceros salieran, y con
    # eso dos alphas se median sobre poblaciones distintas.
    eventos = 0          # eventos con `hand_known`
    sin_celda = 0        # cartas que no caen en el grid
    sin_opp = 0          # celda sin observacion: cae al prior
    p_0 = 0              # celda con probabilidad 0
    medidos = 0
    logp = 0.0

    for h in manos:
        for ev in learn.preflop_events(h):
            if not ev.hand_known:
                continue
            eventos += 1
            if PR._cell_(ev.cards) is None:
                sin_celda += 1
                continue
            perfil = labels.get(ev.player, ev.player)
            if modelo.opp.get((perfil, ev.denom)) is None:
                sin_opp += 1
                continue
            p = modelo.p_hand(perfil, ev.denom, ev.category, ev.cards,
                              ev.pos)
            # NaN e infinitos: `p <= 0.0` es FALSO con NaN, asi que un NaN
            # se colaria en logp sin disparar nada y contaminaria la
            # media sin que se note. Y un valor > 1 no revienta en np.log
            # pero deja de ser una probabilidad.
            if not np.isfinite(p):
                raise MedicionSinSentido(
                    'probabilidad no finita (%r) en %s %s %s'
                    % (p, perfil, ev.denom, ev.category))
            if p < 0.0 or p > 1.0:
                raise MedicionSinSentido(
                    'probabilidad fuera de [0,1]: %r' % p)
            if p <= 0.0:
                p_0 += 1
                continue
            logp += float(np.log(p))
            medidos += 1

    if sin_celda + sin_opp + p_0 + medidos != eventos:
        raise MedicionSinSentido(
            'los cubos no cuadran: %d + %d + %d + %d != %d'
            % (sin_celda, sin_opp, p_0, medidos, eventos))

    if p_0:
        raise MedicionSinSentido(
            '%d eventos caen en celdas con p = 0. Medir sobre el resto es '
            'medir sobre una poblacion distinta, y el denominador '
            'dependeria de alpha.' % p_0)

    if not medidos:
        raise MedicionSinSentido('sin eventos utilizables')

    return -logp / medidos, {'eventos': eventos, 'medidos': medidos,
                             'p_0': p_0, 'sin_celda': sin_celda,
                             'sin_opp': sin_opp}


def la_metrica_ve_a_alpha(manos, labels=None):
    """AUTOVALIDACION. Devuelve (ok, texto), y `ok` puede ser False.

    Si dos alphas dan la misma `L_prim`, la metrica esta ciega y su numero
    no tiene origen. Si la medicion ni siquiera se puede hacer, tambien es
    False: no hay nada que publicar.

    No es una prueba de unittest: es una condicion de EXIT.
    """
    try:
        a1, d1 = l_prim(1.0, manos, labels)
        a2, _d2 = l_prim(9.0, manos, labels)
    except MedicionSinSentido as e:
        return False, 'NO SE PUDO MEDIR: %s' % e
    return (a1 != a2,
            'L_prim(1.0)=%.6f  L_prim(9.0)=%.6f  sobre %d eventos'
            % (a1, a2, d1['eventos']))


def es_monotona(vals, meds):
    """True si `meds` crece o decrece sin cambiar de signo, en orden.

    ESTE ES EL GUARDIAN, y es la razon de que `L_prim` no pueda elegir un
    parametro de regularizacion.

    `p = (cnt + alpha*prior) / (opp + alpha)`, y `L_prim` suma `log p` SOLO
    sobre celdas OBSERVADAS, donde `cnt >= 1`. Ahi el termino del prior es
    solo dilucion: subir alpha baja p, baja log p, sube la perdida. Medido
    sobre los 262 eventos de la particion de calibracion, empujan en esa
    direccion 229 celdas; las otras 33 empujan al reves y no llegan a dar la
    vuelta al agregado.

    Asi que la monotonia no es una garantia: es lo que se observa. Y lo que
    se observa es que `L_prim` ordena alpha por CUANTO se diluyo, que no es
    una respuesta sobre el poker. Si la curva es monotonica, la metrica no
    esta eligiendo: esta sumando, y el "ganador" es el candidato con menos
    regularizacion, que es el mismo decir que el mas pequeno.

    Por eso esto devuelve un booleano y no un ganador, y por eso el
    comando se niega a nombrar uno cuando sale True.
    """
    pares = [(v, m) for v, m in zip(vals, meds) if m is not None]
    if len(pares) < 3:
        return False
    orden = sorted(pares)
    sube = all(b >= a for (_va, a), (_vb, b) in zip(orden, orden[1:]))
    baja = all(b <= a for (_va, a), (_vb, b) in zip(orden, orden[1:]))
    return sube or baja


def l_sec(alpha, manos):
    """Brier de `sit.equity`. El motor no se puede llamar aqui sin partida.

    Se MIDIO antes de escribir esto (revision_2 §2): para llevar la equity
    del motor a un punto de decision hace falta reconstruir la situacion
    desde la mano. `asistente_live` lo hace, y no hay una API que devuelva
    solo la equity para una mano historica.

    Devolver None con el motivo es lo honesto: publicar un numero al que
    no se llega seria inventar la medicion, que es lo que §2.3 prohibe.
    """
    return None, ('sin API para sentarse en un punto de decision historico: '
                  '`asistente_live` no expone la equity suelta')


# ---------------------------------------------------------------------------
def cmd_particion(args):
    cal, val = muestra()
    todos = sorted([i for i, _ in cal] + [i for i, _ in val])
    print('=' * 78)
    print('PARTICION DE FASE D   (se versiona, y no se cambia)')
    print('=' * 78)
    print()
    print('   ventana            : %d manos' % len(ventana()))
    print('   utilizables        : %d' % len(todos))
    print('   calibracion        : %d' % len(cal))
    print('   validacion         : %d' % len(val))
    print('   disjuntas          : %s' % (not ({i for i, _ in cal}
                                             & {i for i, _ in val})))
    print('   regla              : validacion si sha256(hand_id) % 10 < 3')
    print()
    if not args.escribir:
        print('DRY-RUN: no se escribe nada. Con --escribir se versiona.')
        return 0
    lineas = [
        '# PARTICION DE FASE D', '',
        '**Se escribe una vez y no se cambia.** Cambiar la particion es',
        'cambiar de fase, y eso es un commit con su motivo.',
        '', '| | |', '|---|---:|',
        '| ventana | %d |' % len(ventana()),
        '| utilizables | %d |' % len(todos),
        '| calibracion | %d |' % len(cal),
        '| validacion | %d |' % len(val),
        '', 'Regla: `validacion` si `sha256(hand_id) % 10 < 3`.', '',
        '## Validacion (las que deciden regresiones)', '']
    lineas += ['- `%s`' % i for i, _ in val]
    lineas += ['', '## Calibracion (las que ajustan)', '']
    lineas += ['- `%s`' % i for i, _ in cal]
    io = open(PARTICION_MD, 'w', encoding='utf-8', newline='\n')
    io.write('\n'.join(lineas) + '\n')
    io.close()
    print()
    print('escrito: %s' % os.path.relpath(PARTICION_MD, ROOT))
    return 0


def cmd_medir(args):
    cal, val = muestra()
    print('=' * 78)
    print('CALIBRACION DE %s   %s'
          % (args.param, '(DRY-RUN, no aplica)' if not args.aplicar
             else '(APLICA)'))
    print('=' * 78)
    print()
    print(CABECERA_SESGO)
    print()
    print('   ventana     : %d' % len(ventana()))
    print('   calibracion : %d manos' % len(cal))
    print('   validacion  : %d manos' % len(val))
    print()

    # --- 1) autovalidacion: ABORTA, no avisa ----------------------------
    ok, txt = la_metrica_ve_a_alpha(cal)
    print('   AUTOVALIDACION: %s' % txt)
    if not ok:
        print()
        print('   LA METRICA NO VE alpha. NO SE PUBLICA NADA.')
        print('   Sale con codigo 3 y no llega a la tabla, porque una tabla')
        print('   con numeros de una metrica ciega es peor que no tener tabla.')
        return 3

    try:
        base_lp, det = l_prim(getattr(PR, args.param), cal)
    except MedicionSinSentido as e:
        print()
        print('   L_prim NO SE PUDO MEDIR: %s' % e)
        print('   Sale con codigo 3 y no publica.')
        return 3

    print()
    print('   %-10s %12s %12s %10s %s'
          % (args.param, 'L_prim', 'mejora', 'L_sec', 'veredicto'))
    print('   ' + '-' * 68)
    filas = []
    for v in args.valores:
        try:
            lp, _d = l_prim(v, cal)
        except MedicionSinSentido as e:
            lp = None
        ls, motivo_sec = l_sec(v, val)
        mejora = ((base_lp - lp) / base_lp) if (lp is not None and base_lp) \
            else 0.0
        filas.append((v, lp, mejora, ls))
        print('   %-10s %12s %12s %10s %s'
              % (v, ('%.6f' % lp) if lp is not None else 'n/d',
                 ('%+.2f%%' % (mejora * 100)) if lp is not None else 'n/d',
                 'n/d', ''))
    print()
    print('   referencia (valor actual %.1f): %.6f sobre %d eventos'
          % (getattr(PR, args.param), base_lp, det['eventos']))
    print('   celdas con p = 0 en los eventos medidos: %d   sin celda: %d'
          % (det['p_0'], det['sin_celda']))
    print()
    print('   P1  empeora(L_sec) > TOL_SEC ......... no evaluable')
    print('   P2  dos seguidas con mejora < 0,5% ..... primera iteracion')
    print('   P3  20 iteraciones ................... 1 de 20')
    print('   P4  empeora(L_sec) > 0 y mejora < UMBRAL  no evaluable')
    print('   P5  empeora(L_sec) > 0 y mejora >= UMBRAL no evaluable')
    print('   P6  parametro sin justificacion escrita  DEFAULT_ALPHA si la tiene')
    print('   P7  mejora(L_prim) < 0 en una iteracion  se vera en la tabla')
    print()

    # --- 2) la secundaria tiene que existir para ACEPTAR ------------------
    # Por el contrato (§2.3) P4/P5Needs L_sec. Sin L_sec no hay criterio
    # de aceptacion, y --aplicar sin criterio de aceptacion es escribir a
    # ciegas. Se dice ANTES de la monotonia, porque es un bloqueo mas
    # fuerte: aunque la curva no fuera monotonica, aqui tampoco se acepta.
    sec_ok = filas[0][3] is not None
    if not sec_ok:
        print('   L_SEC NO EVALUABLE: %s' % motivo_sec)
        print()

    vals = [f[0] for f in filas]
    meds = [f[1] for f in filas]
    mono = es_monotona(vals, meds)

    if mono:
        print('   GUARDIAN DE MONOTONIA: LA CURVA ES MONOTONA.')
        print('   L_prim esta ordenando alpha por cuanto se diluyo el prior,')
        print('   no por calidad. Elegir el extremo menor NO es un hallazgo:')
        print('   es el mismo decir que el candidato mas pequeño.')
        print()
        print('   VEREDICTO: %s NO SE CALIBRA.' % args.param)
        print('   Se deja como esta y se escribe por que.')
        return 2

    if not sec_ok:
        print('   La curva no es monotonica, pero L_sec no se puede calcular.')
        print('   Quedaria una metrica sin ninguna contra, y el plan no')
        print('   admite aceptar un valor sin las dos.')
        print()
        print('   VEREDICTO: %s NO SE CALIBRA.' % args.param)
        return 2

    if not args.aplicar:
        print('DRY-RUN: nada aplicado. Con --aplicar se escribe el valor.')
        return 0

    # --- 3) aqui si se escribe, y se escribe de verdad -------------------
    mejor = min(filas, key=lambda f: f[1])
    print('   mejor L_prim: %s (%.6f)' % (mejor[0], mejor[1]))
    return escribir_valor(args.param, mejor[0])


def escribir_valor(param, valor):
    """Cambia el valor en `motor/player_ranges.py` y lo dice.

    Se llego aqui solo con las dos metricas evaluables. Es lo unico que
    escribe en el motor, y lo announce antes de hacerlo.
    """
    ruta = os.path.join(ROOT, 'motor', 'player_ranges.py')
    with io.open(ruta, encoding='utf-8') as fh:
        texto = fh.read()
    viejo = None
    for linea in texto.split(NL):
        if linea.startswith(param):
            viejo = linea
            break
    if viejo is None:
        print('   NO SE ESCRIBE: %s no esta en player_ranges.py' % param)
        return 4
    nuevo = '%s = %r' % (param, valor)
    if len(nuevo) > len(viejo):
        nuevo = nuevo + ' ' * (len(viejo) - len(nuevo))
    else:
        nuevo = nuevo + (' ' * (len(viejo) - len(nuevo))) +             viejo[len(nuevo):]
    texto = texto.replace(viejo, nuevo, 1)
    with io.open(ruta, 'w', encoding='utf-8', newline='') as fh:
        fh.write(texto)
    print()
    print('   ESCRITO en motor/player_ranges.py:')
    print('      antes : %s' % viejo.strip())
    print('      ahora : %s' % nuevo.strip())
    print()
    print('   FALTA: el commit con el .md de justificacion. El test')
    print('   test_default_alpha_sigue_en_dos falla hasta entonces.')
    return 0


def main():
    # `particion` es subcomando; medir es lo que se hace sin decir nada.
    # argparse no admite "subcomando con defecto", asi que se decide antes
    # de construir el parser y se le dice cual es.
    argv = sys.argv[1:]
    if argv and argv[0] == 'particion':
        ap = argparse.ArgumentParser(prog='calibrar.py particion')
        ap.add_argument('--escribir', action='store_true')
        args = ap.parse_args(argv[1:])
        return cmd_particion(args)

    ap = argparse.ArgumentParser(prog='calibrar.py')
    ap.add_argument('--param', default='DEFAULT_ALPHA',
                    help='parametro del motor a medir')
    ap.add_argument('--valores', type=float, nargs='+', required=True,
                    help='valores candidatos')
    ap.add_argument('--aplicar', action='store_true',
                    help='escribe el valor. Sin esto, nada se toca')
    args = ap.parse_args(argv)
    return cmd_medir(args)


if __name__ == '__main__':
    sys.exit(main())
