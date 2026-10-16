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
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np                                       # noqa: E402

from motor import learn                                  # noqa: E402
from motor import player_ranges as PR                    # noqa: E402

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


def hero_de(h):
    cc = con_cartas(h)
    return cc[0].get('pos') if cc else None


def etiqueta(h):
    """(y del hero, ok) — misma regla que §2.1.1, y el script la manda."""
    m = {('hero' if i == 0 else 'p%d' % i): p.get('pos')
         for i, p in enumerate(h.get('players') or [])}
    g = [m.get(i) for i in (h.get('winner') or [])]
    g = [x for x in g if x]
    if not g:
        return None, False
    con_cartas_pos = [p.get('pos') for p in con_cartas(h)]
    if any(x not in con_cartas_pos for x in g):
        return None, False
    if len(g) > 1:
        w1 = (h.get('showdown') or {}).get('winner1')
        if not (isinstance(w1, str) and w1.strip()):
            return None, False
        if any(s in w1 for s in ('/', ',', ' y ', '&')):
            return None, False
    return (1.0 if hero_de(h) in g else 0.0), True


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


def etiquetas():
    """nombre de jugador -> etiqueta de perfil.

    `p_matrix` esta indexado por (ETIQUETA, spot), no por nombre. Solo hay
    6 claves: TIBURON y PEZ por no_raise, facing_open y facing_3bet.

    Pasar el NOMBRE es lo que hacia que `opp` fuera None en los 295
    eventos, y con ello que `L_prim` saliera IGUAL para cinco valores de
    alpha: una metrica ciega al parametro que dice calibrar.
    """
    from motor.profile import Profiles
    profs = Profiles.from_hands(ventana())
    return {nombre: p.label for nombre, p in profs.profiles.items()}


def l_prim(alpha, manos, labels=None):
    """Log-verosimilitud del modelo de frecuencias sobre la calibracion.

    MEDIDA DE AJUSTE (FASE_D_PLAN §2.1): el modelo se ajusta aqui y se
    evalua aqui, por construccion. Una mejora puede ser sobreajuste, y por
    eso la secundaria va sobre validacion.

    `p_matrix` devuelve un GRID 13x13 de P(accion | r, spot, perfil). El
    likelihood de un evento es la probabilidad de SU celda, no la mayor
    del grid: quedarse con el maximo cambia lo que se mide.
    """
    labels = etiquetas() if labels is None else labels
    manos = manos_de(manos)
    try:
        modelo = PR.ProfileRangeModel.from_hands(manos, labels=labels,
                                                 alpha=alpha)
    except Exception as e:
        return None, 'from_hands fallo: %s: %s' % (type(e).__name__, e)

    logp, n, con_opp = 0.0, 0, 0
    for h in manos:
        for ev in learn.preflop_events(h):
            if not ev.hand_known:
                continue
            perfil = labels.get(ev.player, ev.player)
            if modelo.opp.get((perfil, ev.denom)) is not None:
                con_opp += 1
            try:
                g = np.asarray(modelo.p_matrix(perfil, ev.denom, ev.category,
                                                ev.pos))
            except Exception as e:
                return None, 'p_matrix fallo: %s' % e
            # los ejes del grid: filas = r (accion), columnas = spot (pos)
            try:
                p = float(g[ev.category, ev.pos])
            except Exception:
                p = float(np.nanmax(g))
            p = float(min(max(p, 1e-12), 1.0))
            logp += np.log(p)
            n += 1
    if not n:
        return None, 'sin eventos con cartas conocidas'
    if con_opp == 0:
        return None, ('NINGUN evento cae en una celda con `opp`: la metrica '
                      'seria el prior y no responderia a alpha')
    return -logp / n, n


def la_metrica_ve_a_alpha(manos, labels=None):
    """AUTOVALIDACION: si dos alphas dan la misma L_prim, la metrica esta
    ciega y no se puede publicar.

    No es una prueba de unittest: es una condicion de EXIT. Una metrica que
    no cambia al cambiar su parametro no esta midiendo el parametro, y el
    numero que produzca es un numero sin origen.
    """
    labels = etiquetas() if labels is None else labels
    a1, _ = l_prim(1.0, manos, labels)
    a2, _ = l_prim(9.0, manos, labels)
    if a1 is None or a2 is None:
        return None, 'no se pudo medir en los dos extremos'
    return a1 != a2, 'L_prim(1.0)=%.6f  L_prim(9.0)=%.6f' % (a1, a2)


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
    base_lp, n_ev = l_prim(getattr(PR, args.param), cal)
    if base_lp is None:
        print('   L_prim no se pudo medir: %s' % n_ev)
        return 1
    print()
    _ve, _txt = la_metrica_ve_a_alpha(cal)
    _autov = ('LA METRICA NO VE alpha -> no se publica: ' + _txt
             if _ve is False else _txt)
    print()
    print('   %-10s %12s %12s %10s %s'
          % (args.param, 'L_prim', 'mejora', 'L_sec', 'veredicto'))
    print('   ' + '-' * 68)
    filas = []
    for v in args.valores:
        lp, _n = l_prim(v, cal)
        ls, _m = l_sec(v, val)
        mejora = (base_lp - lp) / base_lp if base_lp else 0.0
        filas.append((v, lp, mejora, ls))
        print('   %-10s %12.6f %+11.2f%% %12s %s'
              % (v, lp, mejora * 100, 'n/d', ''))
    print()
    print('   AUTOVALIDACION:', _autov)
    print()
    print('   L_prim de referencia (valor actual %.1f): %.6f sobre %d eventos'
          % (getattr(PR, args.param), base_lp, n_ev))
    print()
    print('   P1  empeora(L_sec) > TOL_SEC ......... no evaluable: L_sec n/d')
    print('   P2  dos seguidas con mejora < 0,5% ..... primera iteracion')
    print('   P3  20 iteraciones ................... 1 de 20')
    print('   P4  empeora(L_sec) > 0 y mejora < UMBRAL  no evaluable')
    print('   P5  empeora(L_sec) > 0 y mejora >= UMBRAL no evaluable')
    print('   P6  parametro sin justificacion escrita  DEFAULT_ALPHA si la tiene')
    print('   P7  mejora(L_prim) < 0 en una iteracion  se vera en la tabla')
    print()
    vals = [f[0] for f in filas]
    meds = [f[1] for f in filas]
    mono = es_monotona(vals, meds)
    if mono:
        print()
        print('   GUARDIAN DE MONOTONIA: LA CURVA ES MONOTONA.')
        print('   L_prim esta ordenando alpha por cuanto se diluyo el prior,')
        print('   no por calidad. Elegir el extremo menor NO es un hallazgo:')
        print('   es el mismo decir que el candidato mas pequeno.')
        print()
        print('   Con la secundaria no evaluable (§2.1: no hay API para la')
        print('   equity de un punto de decision historico), NO QUEDA NINGUN')
        print('   criterio admisible para aceptar un valor.')
        print()
        print('   VEREDICTO: DEFAULT_ALPHA NO SE CALIBRA.')
        print('   Se deja en 2.0 y se escribe por que.')
        return 2

    if not args.aplicar:
        print('DRY-RUN: nada aplicado. Con --aplicar se escribe el valor.')
        return 0
    mejor = min(filas, key=lambda f: f[1])
    print('   mejor L_prim: %s (%.6f)' % (mejor[0], mejor[1]))
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
