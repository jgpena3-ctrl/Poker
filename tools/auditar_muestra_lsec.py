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


def posiciones_de(h):
    return {('hero' if i == 0 else 'p%d' % i): p.get('pos')
            for i, p in enumerate(h.get('players') or [])}


def con_cartas(h):
    return [p for p in h.get('players') or [] if (p.get('cards') or '').strip()]


def hero_de(h):
    """El hero es el PRIMER jugador con cartas conocidas.

    No hay marca de hero en el JSON: el proyecto lo reconoce por tener
    cartas, no por el nombre. Es la misma convencion que `multiway`.
    """
    cc = con_cartas(h)
    return cc[0].get('pos') if cc else None


def etiqueta(h):
    """(y del hero, motivo) o (None, motivo) si la mano no es utilizable.

    REGLA, y lo que se decide en cada rama:

      - ganador unico                       -> y = 1.0 si es el hero, 0.0 si no
      - varios, `showdown.winner1` NOMBRA a uno solo
                                           -> ese es el ganador: y = 1.0/0.0
        (no es un empate: el texto lo dice)
      - varios, sin texto de showdown      -> NO utilizable. Poner y = 0.5
        seria INVENTAR la etiqueta: sin texto no se distingue "dos ganan"
        de "el registro se equivoco".
      - el ganador no tiene cartas         -> NO utilizable
    """
    m = posiciones_de(h)
    g = [m.get(i) for i in (h.get('winner') or [])]
    g = [x for x in g if x]
    if not g:
        return None, 'sin ganador'

    cc = con_cartas(h)
    con_cartas_pos = [p.get('pos') for p in cc]
    if any(x not in con_cartas_pos for x in g):
        return None, 'el ganador no tiene cartas'

    hero = hero_de(h)
    if hero is None:
        return None, 'el hero no tiene cartas'

    if len(g) > 1:
        w1 = (h.get('showdown') or {}).get('winner1')
        if not (isinstance(w1, str) and w1.strip()):
            return None, 'varios ganadores y sin showdown'
        if any(s in w1 for s in ('/', ',', ' y ', '&')):
            return None, 'showdown nombra varios: empate no resoluble'
        # el texto nombra a uno solo: se usa ese, y el motivo se declara
        # por si alguien quiere separarlas despues

    return (1.0 if hero in g else 0.0), 'etiqueta unica'


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