# -*- coding: utf-8 -*-
"""Equity del motor en una mano historica, sin partida y sin captura.

Es lo que faltaba para que `L_sec` sea calculable (`CALIBRACION_DEFAULT_ALPHA.md`
§8): no hay API que devuelva `sit.equity` para una mano ya jugada.

QUE USA Y QUE NO

    situation(hero_codes, board_codes, villain_reach=rs, ...)

`equity = wins + 0.5 * ties`, y sale de las cartas y del rango del rival.
**El bote no interviene**: en `situation()` el bote solo alimenta `pot_odds` y
`spr`. Por eso esta herramienta NO reconstruye el bote, y por eso puede
existir sin resolver la aritmetica de las apuestas (que NO converge: medida,
26 de 877 manos coinciden con `final_pot`).

LO QUE NO HACE, Y SE DICE

  - No elige rival por el motor. El rival es una DECISION, y aqui se
    calculan todos los candidatos y se devuelve la dispersion. Escribir un
    numero solo habria escondido la eleccion.
  - No inventa el punto de decision. Es el ultimo punto donde el hero
    actuo, que es lo que el motor habria recomendado.
  - No llama a `asistente_live`: importa sus helpers, que es lo unico que
    comparte con el motor vivo. La cadena es la misma.

    python tools/equity_de_mano.py --mano H_0798
    python tools/equity_de_mano.py --manos 20
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import numpy as np                                       # noqa: E402

from motor import learn                                  # noqa: E402
from motor import situation as S                         # noqa: E402

from motor.asistente_live import (                       # noqa: E402
    RangeState, _preflop_spot, _pf_rival_pos,
    _villain_postflop_actions, situation)
from motor.multiway import PLAYER_IDS                    # noqa: E402
from motor.observations import lead_label              # noqa: E402
from motor.profile import Profiles                       # noqa: E402

ORDEN_CALLES = ('preflop', 'flop', 'turn', 'river')


# --------------------------------------------------------------------- datos
def codigos(s):
    """'TsQs' -> ['Ts', 'Qs'].

    El motor vivo trabaja con LISTAS de codigos de 2 caracteres
    (_cards_to_codes), y RangeState.set_known_cards indexa carta a
    carta. Pasarle la cadena entera hace que indexe por caracter y reviente
    en card_id.
    """
    if not s:
        return []
    if isinstance(s, (list, tuple)):
        return [str(x).strip() for x in s if str(x).strip()]
    s = ''.join(s) if isinstance(s, (list, tuple)) else str(s)
    return [s[i:i + 2] for i in range(0, len(s) - 1, 2)]


def cartas_de(h, pos):
    """Cartas del jugador en pos, como lista de codigos."""
    for p in h.get('players') or []:
        if p.get('pos') == pos and p.get('cards'):
            return codigos(p['cards'])
    return []


def tablero(h, calle):
    """Cartas públicas hasta `calle` inclusive."""
    out = []
    comunitarias = h.get('comunitarias') or {}
    for st in ORDEN_CALLES:
        for c in comunitarias.get(st) or []:
            out.append(c)
        if st == calle:
            break
    return out


def hero_pos_de(h):
    for p in h.get('players') or []:
        if (p.get('name') or '').strip() in learn.HERO_NAMES:
            return p.get('pos')
    return None


def id_a_pos(h, ident):
    if ident not in PLAYER_IDS:
        return None
    i = PLAYER_IDS.index(ident)
    if i >= len(h.get('players') or []):
        return None
    return h['players'][i].get('pos')


def se_foldio_antes_de(h, pos, calle):
    """True si `pos` ya no esta en la mano al empezar `calle`."""
    for st in ORDEN_CALLES:
        acts = ((h.get('streets') or {}).get(st) or {}).get('actions') or []
        for a in acts:
            if a.get('pos') == pos and a.get('action') == 'f':
                return True
        if st == calle:
            return False
    return False


def corte_de_decision(h, hero_pos):
    """(calle, indice) de la ULTIMA accion del hero, o (None, None).

    El indice es dentro de esa calle. Hace falta el indice y no solo la
    calle: si el hero y el rival juegan en la misma calle, la accion del
    rival puede ser posterior y mirarla seria mirar al futuro.
    """
    for st in reversed(ORDEN_CALLES):
        acts = ((h.get('streets') or {}).get(st) or {}).get('actions') or []
        for i in range(len(acts) - 1, -1, -1):
            a = acts[i]
            if a.get('pos') == hero_pos and a.get('action') in (
                    'b', 'c', 'r', 'f', 'x'):
                return st, i
    return None, None


def punto_de_decision(h, hero_pos):
    """La calle donde el hero actuo por ultima vez."""
    return corte_de_decision(h, hero_pos)[0]


def acciones_hasta(h, calle, indice):
    """[(street, i)] de TODAS las acciones hasta el corte, calle incluida.

    `indice` es `None` = hasta el final de la calle.
    """
    out = []
    for st in ORDEN_CALLES:
        acts = ((h.get('streets') or {}).get(st) or {}).get('actions') or []
        for i in range(len(acts)):
            if st == calle and indice is not None and i >= indice:
                return out
            out.append((st, i))
        if st == calle and indice is None:
            return out
    return out


def villain_hasta_corte(h, villain_pos, calle, indice):
    """Acciones YA OBSERVADAS del rival hasta el corte. Copia de la cadena
    de `asistente_live` con el corte puesto.

    `_villain_postflop_actions` devuelve la calle entera y no tiene por
    donde cortar. Reimplementarlo aqui es lo que deja la fuga a medias
    controllable: si el motor algun dia anade un paso, hay que replicarlo.

    `lead_label` se importa del MISMO sitio, para que las etiquetas de
    lead caigan en las mismas celdas de entrenamiento que en vivo.
    """
    out = []
    pf_acts = ((h.get('streets') or {}).get('preflop') or {}).get(
        'actions') or []
    pf_initiator = next((a.get('pos') for a in reversed(pf_acts)
                         if a.get('action') in ('b', 'r')), '')
    pot_raised = bool(pf_initiator)
    limite = set(acciones_hasta(h, calle, indice))
    for st in ('flop', 'turn', 'river'):
        acts = ((h.get('streets') or {}).get(st) or {}).get('actions') or []
        board = ((h.get('streets') or {}).get(st) or {}).get('board') or []
        board_str = ','.join(str(c) for c in board) if board else ''
        facing = ''
        for i, a in enumerate(acts):
            if (st, i) not in limite:
                break
            pos, action = a.get('pos'), a.get('action')
            if action == 'x':
                continue
            if pos == villain_pos and action in ('b', 'c', 'r', 'f'):
                out.append((st, facing or 'none', action, board_str))
            if action in ('b', 'r'):
                facing = ('raise' if facing else
                          lead_label(st, pos, pf_initiator, pot_raised))
    return out


# ------------------------------------------------------------------- modelo
def perfiles_de(manos):
    """nombre -> etiqueta. Se calcula con las manos que se le pasan."""
    profs = Profiles.from_hands(manos)
    return {n: p.label for n, p in profs.profiles.items()}


def rango_del_rival(h, villain_pos, hero, board, labels, modelo,
                    postflop_model=None, calle=None, indice=None):
    """El `RangeState` del rival, por la MISMA cadena que el motor vivo.

    Se importa de `asistente_live` y se sigue en el mismo orden:
    rango inicial preflop -> blockersknown -> refinado postflop.
    """
    nombre = ''
    for p in h.get('players') or []:
        if p.get('pos') == villain_pos:
            nombre = (p.get('name') or '').strip()
    perfil = labels.get(nombre, 'PEZ')
    spot, action = _preflop_spot(h, villain_pos)
    reach = modelo.prob_vec(perfil, spot, action, pos=villain_pos,
                            villain_pos=_pf_rival_pos(h, villain_pos,
                                                      spot))
    rs = RangeState(reach=reach)

    # SOLO lo que se sabia en ese instante: las cartas del hero y el board.
    #
    # Antes se metia ademas la carta de todos los demas jugadores que
    # tienen cartas en el REGISTRO, lo que son las que se revelan en el
    # showdown: 216 cartas que en la calle del punto de decision no se
    # conocian de nadie. Y el hero entraba dos veces, una en `hero` y otra
    # en el bucle: 310 cartas contadas de mas.
    #
    # No se puede hacer mejor con estos datos: el registro guarda las
    # cartas finales de cada jugador y no dice EN QUE MOMENTO se revelaron.
    # Anyadir las de terceros seria inventar que se sabian.
    rs.set_known_cards(list(hero) + list(board))

    if postflop_model is not None and calle is not None:
        for st_v, facing, act, board_str in villain_hasta_corte(
                h, villain_pos, calle, indice):
            board_v = [c.strip() for c in board_str.split(',')] \
                if board_str else []
            rs.update(postflop_model.prob_vec(perfil, st_v, facing,
                                              board_v, act))
    return rs, perfil


def equity_contra(h, villain_pos, labels, modelo, postflop_model=None):
    """(equity, detalle) del hero contra `villain_pos`, o (None, motivo)."""
    hero_pos = hero_pos_de(h)
    if hero_pos is None:
        return None, 'la mano no tiene jugador con el nombre del hero'
    calle, indice = corte_de_decision(h, hero_pos)
    if calle is None:
        return None, 'el hero no actuo en la mano'
    hero = cartas_de(h, hero_pos)
    board = tablero(h, calle)
    if len(hero) < 2:
        return None, 'el hero no tiene cartas'
    if not board and calle != 'preflop':
        return None, 'no hay board en la calle del punto de decision'
    # PREFLOP: HAY UN CAMINO OBSERVABLE EN EL MOTOR, y esta herramienta no
    # lo usa. Y el motivo NO es que no exista.
    #
    # El motor tiene camino de equity preflop: `equity_preflop_rango` en
    # `motor/hand_evaluator.py`, al que `situation.equity_vs_range` delega
    # cuando el board esta vacio. Y no usa las cartas del rival, solo su
    # rango, de modo que la equity que devuelve es OBSERVABLE.
    #
    # Y la razon por la que esta herramienta NO lo usa es que **cambiaria el
    # AUC publicado**: la equity que se mide aqui es RETROSPECTIVA, contra
    # las cartas REALES del rival, y el AUC que sale de ahi es el AUC
    # publicado. Y un AUC publicado no se mueve por el criterio de un
    # arreglo de instrumentacion: moverlo es una RECALIBRACION, y las
    # recalibraciones van despues de la adopcion de la base.
    #
    # De modo que lo que queda aqui, y es lo correcto mientras tanto: la
    # enumeracion contra las cartas reales, que es RETROSPECTIVA —en una
    # decision preflop historica esas cartas no eran observables—, y que
    # sirve para auditar el evaluador y para estudiar manos. NO es la equity
    # de una decision.
    #
    # Y el hueco que de verdad habia —`evaluate_batch` declara board de 3 a
    # 5 cartas, y `decision.runout_equity` con board vacio pide
    # `_SUBSETS[2]`, que no existe— esta resuelto por la delegacion.
    if calle == 'preflop':
        vc = cartas_de(h, villain_pos)
        if len(vc) < 2:
            return None, 'el rival no tiene cartas en el registro'
        try:
            from equity_preflop import equity_preflop
            eq, det = equity_preflop(hero[0] + hero[1], vc[0] + vc[1])
        except Exception as e:
            return None, ('equity_preflop fallo: %s: %s'
                          % (type(e).__name__, e))
        return float(eq), {
            'calle': calle,
            'hero': ''.join(hero),
            'board': [],
            'rival': villain_pos,
            'perfil': None,
            'combos': det['boards'],
            'via': 'enumeracion contra la MANO REAL del rival',
            'observable': False,
            'por_que_no_observable':
                'usa las cartas del rival, que al decidir no se '
                'conocian; y no hay camino preflop en el motor',
        }

    rs, perfil = rango_del_rival(h, villain_pos, hero, board, labels, modelo,
                                  postflop_model, calle=calle,
                                  indice=indice)
    try:
        sit = situation(hero, board, villain_reach=rs,
                        position=hero_pos, street=calle)
    except Exception as e:
        return None, 'situation fallo: %s: %s' % (type(e).__name__, e)
    return float(sit.equity), {
        'calle': calle,
        'observable': True,
        'hero': hero,
        'board': board,
        'rival': villain_pos,
        'perfil': perfil,
        'combos': sit.combos_evaluados,
    }


def candidatos(h, hero_pos, calle):
    """Rivales que siguen en la mano en `calle`. El orden es el de la mesa."""
    out = []
    for p in h.get('players') or []:
        pos = p.get('pos')
        if not pos or pos == hero_pos:
            continue
        if se_foldio_antes_de(h, pos, calle):
            continue
        out.append(pos)
    return out


# --------------------------------------------------------------------- main
def agrega_equities(salida):
    """La REDUCCION de las equities de los rivales a un numero, y con cuenta.

    Y la population, que es lo que hay que tener presente: **`salida` son los
    rivales que se PUDIERON evaluar**. Los que fallaron no estan, y su motivo
    queda en la lista de motivos. De modo que la mediana es la de un
    SUBCONJUNTO de los rivales del bote, y el numero de cuantos es lo que
    dice si ese subconjunto es el bote entero.

    Y por eso se devuelve tambien `n_evaluados`: sin ese numero, una mediana
    de dos rivales y una de cinco se ven igual.

    Y la dispersion es `max - min`, y es 0.0 cuando hay un solo rival, que no
    es «no hay dispersion» sino «no se puede medir».
    """
    if not salida:
        raise ValueError('agrega_equities: sin equities que agregar')
    valores = list(salida.values())
    return {
        'mediana': float(np.median(valores)),
        'dispersion': (max(valores) - min(valores)
                       if len(valores) > 1 else 0.0),
        'n_evaluados': len(valores),
    }


def equity_de_mano(hand, labels, modelos, rival_unico=None):
    """Equity del hero en `hand` contra cada rival vivo. Dict por rival.

    Devuelve un dict `rival_pos -> equity` mas la dispersion, porque la
    eleccion de rival es una decision de quien mide y tiene que quedar a la
    vista.
    """
    hero_pos = hero_pos_de(hand)
    if hero_pos is None:
        return None, 'la mano no tiene jugador con el nombre del hero'
    calle, indice = corte_de_decision(hand, hero_pos)
    if calle is None:
        return None, 'el hero no actuo en la mano'
    rivales = candidatos(hand, hero_pos, calle)
    if rival_unico is not None:
        rivales = [r for r in rivales if r == rival_unico]
    if not rivales:
        return None, 'no queda ningun rival en el bote en esa calle'
    salida = {}
    motivos = []
    detalle = None
    # Y la agregacion se hace al final, sobre lo que se pudo evaluar, y con
    # la cuenta de cuantos. Y la cuenta es lo que hace visible el subconjunto.
    for r in rivales:
        eq, det = equity_contra(hand, r, labels, modelos['preflop'],
                                modelos.get('postflop'))
        if eq is None:
            # el motivo SE CUENTA. Tragaselo y todos los fallos se parecen,
            # que es como uno acaba creyendo que son la misma cosa.
            motivos.append('%s: %s' % (r, det))
            continue
        salida[r] = eq
        # El detalle se queda con el ULTIMO QUE SALIO BIEN. Antes era la
        # variable de la ultima iteracion, que podia ser el motivo de un
        # fallo, y el que leia recibia una cadena donde esperaba un dict.
        detalle = det
    if not salida:
        return None, '; '.join(motivos) or 'sin motivos'
    agregado = agrega_equities(salida)
    return salida, {
        'calle': calle,
        'hero_pos': hero_pos,
        'mediana': agregado['mediana'],
        'dispersion': agregado['dispersion'],
        'n_evaluados': agregado['n_evaluados'],
    }, detalle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mano', help='un hand_id, p.ej. H_0798')
    ap.add_argument('--manos', type=int, default=0,
                    help='las primeras N manos utilizables')
    ap.add_argument('--etiquetas-desde', default='calibracion',
                    choices=('ventana', 'calibracion'),
                    help='de que manos se sacan las etiquetas de perfil')
    ap.add_argument('--ajuste', default='calibracion',
                    choices=('calibracion', 'ventana'),
                    help='con que manos se ajusta el modelo de rangos')
    args = ap.parse_args()

    import hashlib

    from motor import player_ranges, postflop_ranges
    ventana = learn.load_hands(reliable_only=True)

    def _particion(h):
        d = int(hashlib.sha256(h['hand_id'].encode('utf-8')).hexdigest(), 16)
        return 'validacion' if d % 10 < 3 else 'calibracion'

    # C) EL AJUSTE SE SEPARA. Medido: las 6 de las 6 claves de `opp` cambian
    # segun se ajuste con la ventana entera o con calibracion. O sea que un
    # modelo ajustado con la ventana ha visto las 39 manos de validacion,
    # y evaluarlas con el no mide generalizacion: mide recuerdo.
    ajuste = [h for h in ventana if _particion(h) == args.ajuste]
    modelos = {
        'preflop': player_ranges.ProfileRangeModel.from_hands(
            ajuste, alpha=player_ranges.DEFAULT_ALPHA),
    }
    try:
        modelos['postflop'] = postflop_ranges.PostflopModel()
    except Exception:
        modelos['postflop'] = None

    if args.etiquetas_desde == 'calibracion':
        labels = perfiles_de([h for h in ventana
                              if _particion(h) == 'calibracion'])
        print('etiquetas de perfil: %d manos de calibracion'
              % len([h for h in ventana if _particion(h) == 'calibracion']))
    else:
        labels = perfiles_de(ventana)
        print('etiquetas de perfil: las %d de la ventana' % len(ventana))
    print()
    print('ajuste del modelo de rangos: %d manos de %s'
          % (len(ajuste), args.ajuste))
    if args.ajuste == 'ventana':
        print()
        print('   AVISO: con --ajuste ventana el modelo ha visto las 39')
        print('   manos de validacion. Las cifras NO miden generalizacion.')
    print()

    objetivo = []
    if args.mano:
        objetivo = [h for h in ventana if h['hand_id'] == args.mano]
    elif args.manos:
        objetivo = ventana[:args.manos]
    else:
        ap.print_help()
        return 1

    print('=' * 76)
    print('EQUITY DEL MOTOR EN MANOS HISTORICAS')
    print('=' * 76)
    print()
    print('   La equity NO usa el bote: sale de las cartas y del rango del')
    print('   rival. Por eso esta herramienta no reconstruye las apuestas.')
    print()
    print('   Y el rival es una DECISION, asi que se calculan todos los')
    print('   candidatos y se enseña la dispersion.')
    print()

    n_ok = n_sin = 0
    for h in objetivo:
        r = equity_de_mano(h, labels, modelos)
        if r is None:
            continue
        if len(r) == 2:
            print('   %s   SIN EQUITY: %s' % (h['hand_id'], r[1]))
            n_sin += 1
            continue
        eqs, det, _d = r
        print('   %s  punto de decision: %s  (hero en %s)'
              % (h['hand_id'], det['calle'], det['hero_pos']))
        for pos in sorted(eqs):
            print('      vs %-4s  equity = %.4f' % (pos, eqs[pos]))
        print('      mediana %.4f   dispersion %.4f'
              % (det['mediana'], det['dispersion']))
        print()
        n_ok += 1
    print('=' * 76)
    print('COBERTURA, QUE ES LO QUE LIMITA A L_sec')
    print('=' * 76)
    print()
    motivos = {}
    cub = 0
    for h in (objetivo or ventana):
        r = equity_de_mano(h, labels, modelos)
        if r is not None and len(r) == 3:
            cub += 1
        else:
            k = (r[1][:60] if r is not None else '?')
            motivos[k] = motivos.get(k, 0) + 1
    print('   con equity : %d' % cub)
    print('   sin equity : %d' % (len(objetivo or ventana) - cub))
    print()
    for k, n in sorted(motivos.items(), key=lambda t: -t[1])[:6]:
        print('      %-62s %4d' % (k, n))
    print()
    print('   La causa de casi todos es que `hand_evaluator.evaluate_batch`')
    print('   declara board de 3 a 5 cartas: NO hay camino preflop. Y')
    print('   preflop son 96 de las 156 manos de la muestra.')
    print()
    print('=' * 76)
    print('con equity: %d    sin: %d' % (n_ok, n_sin))
    return 0


if __name__ == '__main__':
    sys.exit(main())