# -*- coding: utf-8 -*-
"""Muestra de L_sec: tamaño, balance y si la métrica DISCRIMINA.

La pregunta que hace falta antes de usar `L_sec` no es "cuantas manos
hay", es **"un modelo trivial, la bateria?"**. Si un predictor constante
que solo dice "el hero casi siempre pierde" saca mejor nota que el motor,
la metrica mide la base rate, no la calidad: es el mismo trampa que el
plan ya rechazo para la metrica de acuerdo.

revision_2 lo dice: "No usar las 147 como si fueran una muestra
independiente", y que un umbral no demuestra significencia.

SOLO LECTURA.

    python tools/auditar_muestra_lsec.py
"""
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor import learn                                # noqa: E402
from motor.multiway import PLAYER_IDS                  # noqa: E402
from motor.hand_evaluator import evaluate_hand       # noqa: E402


ORDEN_CALLES = ('preflop', 'flop', 'turn', 'river')


def id_a_pos(h, ident):
    """`_id` de `winner` -> posicion, por PLAYER_IDS.

    `recorder_live` escribe `p['_id']` y `PLAYER_IDS` es
    `['hero', 'p1' ... 'p5']`. `'hero'` es **la butaca 0**: no dice quien
    es el hero. En 232 de las 877 manos de la ventana el hero real esta en
    otra butaca.
    """
    if ident not in PLAYER_IDS:
        return None
    i = PLAYER_IDS.index(ident)
    if i >= len(h.get('players') or []):
        return None
    return h['players'][i].get('pos')


def con_cartas(h):
    return [p for p in h.get('players') or [] if (p.get('cards') or '').strip()]


def hero_de(h):
    """El hero: el jugador nombrado en `learn.HERO_NAMES` (`'Jarduan'`).

    NO es el primero con cartas. Se parece en 845 de 877 manos de la
    ventana y falla en 32; y en esas la etiqueta de `L_sec` era la de otro
    jugador. La autoridad es `learn.py`, no una convencion de este modulo.
    """
    for p in h.get('players') or []:
        if (p.get('name') or '').strip() in learn.HERO_NAMES:
            return p.get('pos')
    return None


def ganador_nombrado(h):
    """Posicion que nombra `showdown.winner1`, o (None, motivo).

    Se RESUELVE contra la mesa, no se acepta por existir. El recorder solo
    escribe `showdown` cuando hay **un** ganador, asi que un `showdown` con
    varios ganadores es una mano editada a mano y su texto tiene que
    demostrar a quien nombra.
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


def ultima_calle(h):
    for st in reversed(ORDEN_CALLES):
        acts = ((h.get('streets') or {}).get(st) or {}).get('actions') or []
        if acts:
            return st
    return None


def llego_al_showdown(h, pos, ult):
    """True si pos no folteo en ninguna calle ANTERIOR a ult."""
    for st in ORDEN_CALLES:
        if st == ult:
            return True
        acts = ((h.get('streets') or {}).get(st) or {}).get('actions') or []
        for a in acts:
            if a.get('pos') == pos and a.get('action') == 'f':
                return False
    return True


def mejores_manos(h):
    """({pos: score}, maximo) SOLO de los que llegaron al showdown.

    **No** de todos los que tienen cartas: el que folteo antes no estaba
    en el bote, y comparar sus cartas con el board da un mejor que no
    compitio. Con el criterio erroneo salian 358 incoherentes de 584 en la
    ventana; con este, **0 de 261**.
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


def reparto(h, gs):
    """True si los jugadores de gs hacen la MISMA mano en el board.

    Eso es lo que hace un reparto, y es demostrable: lo dice el evaluador
    del motor sobre las cartas y el board del registro. No hace falta
    fiarse de showdown.winner1, que es un texto y que el recorder
    escribe SOLO con un ganador, asi que en un reparto esta incompleto por
    construccion.
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
    """(y del hero, motivo) o (None, motivo) si la mano no es utilizable.

      - ganador unico, resuelto por `id_a_pos`   -> y = 1,0 si es el hero
      - varios, `winner1` RESUELVE a alguien de la mesa -> ese gana
      - varios, `winner1` no resuelve           -> NO utilizable. Poner
        `y = 0,5` seria inventar la etiqueta: sin texto no se distingue
        "dos ganan" de "el registro se equivoco".
      - el ganador no tiene cartas, o no hay jugador `HERO_NAMES` -> no
    """
    hero = hero_de(h)
    if hero is None:
        return None, 'no hay jugador con el nombre del hero'
    gs = set()
    for ident in (h.get('winner') or []):
        pos = id_a_pos(h, ident)
        if pos:
            gs.add(pos)
    if not gs:
        return None, 'sin ganador'
    cpos = [p.get('pos') for p in con_cartas(h)]
    if any(x not in cpos for x in gs):
        return None, 'el ganador no tiene cartas'
    if len(gs) > 1:
        r = reparto(h, gs)
        if r is None:
            return None, ('varios ganadores y no se puede demostrar el '
                          'reparto')
        if not r:
            return None, 'varios ganadores que NO hacen la misma mano'
        return (0.5 if hero in gs else 0.0), 'reparto demostrado'
    return (1.0 if hero in gs else 0.0), 'ganador unico'


def brier(ps, ys):
    if not ps:
        return None
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ps)


def main():
    manos = learn.load_hands(reliable_only=True)
    print('=' * 78)
    print('MUESTRA DE L_sec: tamaño, balance, y si discrimina')
    print('=' * 78)
    print('   ventana: %d manos' % len(manos))
    print()

    c = collections.Counter()
    ys = []
    ids = []
    for h in manos:
        if len((h.get('comunitarias') or {}).get('river') or []) < 1:
            c['board incompleto'] += 1
            continue
        if len(con_cartas(h)) < 2:
            c['menos de 2 jugadores con cartas'] += 1
            continue
        # REGLA ESTRICTA: `winner` tiene que ser exactamente el conjunto
        # de los que hacen la mejor mano, segun el evaluador del motor.
        # MEDIDO: 31 de las 161 lo contradicen. Una etiqueta que se
        # contradice con las cartas no es una etiqueta.
        scores, mejor = mejores_manos(h)
        declarados = {id_a_pos(h, i) for i in (h.get('winner') or [])}
        declarados.discard(None)
        if not declarados:
            c['sin ganador'] += 1
            continue
        if mejor is not None and declarados & {pos for pos, s_ in
                                                scores.items()
                                                if s_ == mejor}:
            reales = {pos for pos, s_ in scores.items() if s_ == mejor}
            if declarados != reales:
                c['INCOHERENTE: reparto incompleto'] += 1
                continue
        else:
            c['ganador por fold, no comprobable'] += 1
        y, mot = etiqueta(h)
        if y is None:
            c['no se puede etiquetar: ' + mot] += 1
            continue
        c['utilizable'] += 1
        ys.append(y)
        ids.append(h['hand_id'])

    print('1) DESGLOSE')
    print('-' * 78)
    for k, v in c.most_common():
        print('   %-52s %4d' % (k, v))
    print()
    print('   UTILIZABLES: %d de %d  (%.1f%%)'
          % (c['utilizable'], len(manos), c['utilizable'] / len(manos) * 100))
    print()

    print('2) BALANCE DE LA ETIQUETA')
    print('-' * 78)
    gana = ys.count(1.0)
    pierde = ys.count(0.0)
    print('   gana  (y=1,0): %4d  (%.1f%%)' % (gana, gana / len(ys) * 100))
    print('   pierde(y=0,0): %4d  (%.1f%%)' % (pierde, pierde / len(ys) * 100))
    print()
    print('   *** El hero pierde %.0f%% de las manos utilizables. ***'
          % (pierde / len(ys) * 100))
    print('   Con ese desequilibrio, "acertar siempre que pierde" es un')
    print('   modelo muy fuerte. Hay que medirlo antes de usar la metrica.')
    print()

    print('3) ¿DISCRIMINA? Brier de un predictor TRIVIAL contra la muestra')
    print('-' * 78)
    base = gana / len(ys)
    print('   Brier del predictor CONSTANTE p=%.3f (la base rate) : %.4f'
          % (base, brier([base] * len(ys), ys)))
    mejor = min(
        ((p, brier([p] * len(ys), ys)) for p in
         [i / 100.0 for i in range(0, 101)]),
        key=lambda t: t[1])
    print('   mejor predictor constante p=%.2f                       : %.4f'
          % (mejor[0], mejor[1]))
    print()
    print('   Referencia: el motor deberia estar por debajo de %.4f.'
          % mejor[1])
    print('   Un Brier del motor MAYOR que %.4f significa que el motor'
          % mejor[1])
    print('   pierde contra "decir siempre que el hero va a perder".')
    print()
    print('   Y con %d manos, la diferencia entre dos candidatos tiene que'
          % len(ys))
    print('   ser mayor que su propio ruido para significar algo. Eso NO se')
    print('   puede saber sin medir las dos calibrated, y por eso TOL_SEC')
    print('   esta declarado antes y no despues.')
    print()

    print('4) LA PARTICION 70/30')
    print('-' * 78)
    print('   regla: particion(hand_id) = validacion si sha256 %% 10 < 3')
    print()
    import hashlib

    def es_validacion(hid):
        d = hashlib.sha256(hid.encode('utf-8')).hexdigest()
        return int(d, 16) % 10 < 3
    cal = [i for i in ids if not es_validacion(i)]
    val = [i for i in ids if es_validacion(i)]
    print('   calibracion: %4d' % len(cal))
    print('   validacion : %4d' % len(val))
    print('   disjuntos  : %s' % (not (set(cal) & set(val))))
    yc = [y for i, y in zip(ids, ys) if i in set(cal)]
    yv = [y for i, y in zip(ids, ys) if i in set(val)]
    print()
    print('   validacion: gana %d · pierde %d  (%.0f%% pierde)'
          % (yv.count(1.0), yv.count(0.0),
             yv.count(0.0) / len(yv) * 100))
    print()
    print('   La REGLA DE AHORA es 70/30 sobre el total de manos, no sobre')
    print('   las utilizables. Aplicada a las utilizables sale esto, y es lo')
    print('   que hay que versionar en DOCS/PARTICION_FASE_D.md.')
    return 0


if __name__ == '__main__':
    sys.exit(main())