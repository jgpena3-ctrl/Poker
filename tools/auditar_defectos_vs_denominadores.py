# -*- coding: utf-8 -*-
"""¿Los defectos sistémicos que quedan dentro de la ventana tocan lo que se
va a calibrar?

revision_1 Tarea 1 y revision_2 §2.

POR QUÉ NO SE MIDE «CUANTAS MANOS QUITAN»
------------------------------------------
La primera versión de este script quitaba las manos defectuosas de la ventana
y comparaba los totales. Daba que las cuatro clases «cambian» todo. **Eso es
aritmética, no contaminación**: quitar 25 manos baja los totales aunque las
25 fueran perfectas.

La pregunta que importa es otra: **¿el DEFECTO cambia lo que la calibración
ve de ESA mano?** Para eso la mano se queda, y lo que se neutraliza es el
defecto. Si el resultado es el mismo, el defecto no toca esa entrada por muy
defectuosa que sea la mano.

MÉTODO
------
Para cada mano defectuosa, dos versiones:

  · ORIGINAL  — tal cual está
  · NEUTRALIZADA — con el defecto corregido en el sitio que lo produce:
      IMPORTE_SUBIDA     el importe de la subida pasa a superar el suelo
      ACCION_FANTASMA   se retiran las acciones de posiciones sin jugador
      WINNER_FOLDEO     `winner` deja de incluir a quien foldeó
      SHOWDOWN_SIN_WINNER  `winner` pasa a ser el que nombra `showdown`

Y se compara, sobre esa mano y solo esa mano: los eventos preflop que salen,
categoría por categoría; los jugadores aparecen; las celdas de `cnt`/`opp` que
aporta; y las observaciones.

Se hace una clase cada vez, para poder decir QUÉ toca y no solo «algo».

Uso:
    python tools/auditar_defectos_vs_denominadores.py
"""
import collections
import copy
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from motor.learn import load_hands, preflop_events, BB          # noqa: E402
from motor.observations import extract_hands                    # noqa: E402
from motor.player_ranges import _cell_                         # noqa: E402
import auditar_rango as A                                       # noqa: E402

CLASES = ('IMPORTE_SUBIDA', 'ACCION_FANTASMA',
          'WINNER_FOLDEO', 'SHOWDOWN_SIN_WINNER')
DETECTORES = {n: f for n, _d, f, _t in A.CLASES if n in CLASES}


# ------------------------------------------------------------------ mutadores
def _calles(hand):
    st = hand.get('streets') or {}
    return [s for s in ('preflop', 'flop', 'turn', 'river')
            if (st.get(s) or {}).get('actions')]


def neutraliza(hand, clase):
    """La mano con SU defecto corregido, en el sitio que lo produce."""
    h = copy.deepcopy(hand)

    if clase == 'IMPORTE_SUBIDA':
        # El suelo de una calle: en preflop la ciega grande SIEMPRE.
        for s in _calles(h):
            maximo = BB if s == 'preflop' else 0.0
            for a in ((h['streets'][s] or {}).get('actions') or []):
                try:
                    imp = float(a.get('amount') or 0.0)
                except (TypeError, ValueError):
                    imp = 0.0
                if a.get('action') == 'r':
                    if imp <= maximo:
                        a['amount'] = round(maximo + max(1.0, maximo * 0.5), 2)
                        imp = float(a['amount'])
                    maximo = max(maximo, imp)
                elif a.get('action') in ('b', 'c'):
                    maximo = max(maximo, imp)
        return h

    if clase == 'ACCION_FANTASMA':
        activos = {p.get('pos') for p in (h.get('players') or [])
                   if p.get('active') and p.get('pos')}
        for s in _calles(h):
            acc = (h['streets'][s] or {}).get('actions') or []
            h['streets'][s]['actions'] = [
                a for a in acc
                if not (a.get('pos') and a.get('pos') not in activos)]
        return h

    if clase == 'WINNER_FOLDEO':
        folds = {a.get('pos') for _s, a in A.todas_las_acciones(h)
                 if a.get('action') == 'f'}
        pid_pos = A.PID
        jugadores = h.get('players') or []
        nuevo = []
        for w in h.get('winner') or []:
            pos = None
            if w in pid_pos and pid_pos.index(w) < len(jugadores):
                pos = jugadores[pid_pos.index(w)].get('pos')
            if pos not in folds:
                nuevo.append(w)
        h['winner'] = nuevo
        return h

    if clase == 'SHOWDOWN_SIN_WINNER':
        sd = (h.get('showdown') or {}).get('winner1') or ''
        m = re.search(r'\(([^)]+)\)\s*$', sd)
        if m:
            nombre = m.group(1).strip()
            for i, p in enumerate(h.get('players') or []):
                if p.get('name') == nombre:
                    h['winner'] = ['hero' if nombre == 'Jarduan'
                                   else 'p%d' % i]
                    break
        return h

    raise ValueError(clase)


# -------------------------------------------------------------- que se mide
def firma(hand):
    """Todo lo que la calibración ve de UNA mano, en forma comparable."""
    eventos = []
    for ev in preflop_events(hand):
        eventos.append((ev.player, ev.denom, ev.category,
                        ev.hand_known, bool(ev.cards)))
    celdas = collections.Counter()
    labels = {}
    from motor.profile import Profiles
    for p in Profiles.from_hands([hand]).profiles.items():
        labels[p[0]] = p[1].label
    for ev in preflop_events(hand):
        if not (ev.hand_known and ev.cards):
            continue
        celda = _cell_(ev.cards)
        perfil = labels.get(ev.player)
        if celda is None or perfil is None:
            continue
        celdas[('opp', perfil, ev.denom, celda)] += 1
        celdas[('cnt', perfil, ev.denom, ev.category, celda)] += 1
    return {
        'eventos': sorted(eventos),
        'jugadores': sorted({e[0] for e in eventos}),
        'celdas': dict(celdas),
        'observaciones': len(extract_hands([hand])),
    }


def _dif(a, b):
    out = []
    if a['eventos'] != b['eventos']:
        sa, sb = set(a['eventos']), set(b['eventos'])
        out.append('eventos: %d -> %d (solo antes: %s | solo despues: %s)'
                   % (len(sa), len(sb),
                      sorted(sa - sb)[:3], sorted(sb - sa)[:3]))
    if a['jugadores'] != b['jugadores']:
        out.append('jugadores: %s -> %s'
                   % (a['jugadores'], b['jugadores']))
    if a['celdas'] != b['celdas']:
        dif = [k for k in set(a['celdas']) | set(b['celdas'])
               if a['celdas'].get(k) != b['celdas'].get(k)]
        out.append('celdas cnt/opp distintas: %d (p.ej. %s)'
                   % (len(dif), dif[:3]))
    if a['observaciones'] != b['observaciones']:
        out.append('observaciones: %d -> %d'
                   % (a['observaciones'], b['observaciones']))
    return out


def main():
    ventana = load_hands(reliable_only=True)
    ids_ventana = {h['hand_id'] for h in ventana}
    por_id = {h['hand_id']: h for h in ventana}

    print('=' * 78)
    print('¿EL DEFECTO CAMBIA LO QUE LA CALIBRACION VE?')
    print('=' * 78)
    print()
    print('  Ventana: %d manos.  Para cada mano defectuosa se comparan dos' % len(ventana))
    print('  versiones de ELLA: la original, y la misma con el defecto')
    print('  neutralizado. Si dan lo mismo, el defecto no toca esa entrada.')
    print()

    resumen = {}
    for clase in CLASES:
        ids = [h['hand_id'] for h in load_hands(reliable_only=False)
               if DETECTORES[clase](h) and h['hand_id'] in ids_ventana]
        print('-' * 78)
        print('%s  —  %d manos en la ventana' % (clase, len(ids)))
        print('-' * 78)
        tocan, detalles = [], {}
        for hid in ids:
            dif = _dif(firma(por_id[hid]), firma(neutraliza(por_id[hid], clase)))
            if dif:
                tocan.append(hid)
                detalles[hid] = dif
        if not tocan:
            print('  Ninguna mano cambia. El defecto NO toca las entradas.')
        else:
            print('  %d de %d cambian:' % (len(tocan), len(ids)))
            for hid in tocan:
                print('    %s' % hid)
                for d in detalles[hid]:
                    print('        %s' % d)
        resumen[clase] = (len(ids), tocan, detalles)
        print()

    print('=' * 78)
    print('CLASIFICACION  (el encargo pide cero "no verificado")')
    print('=' * 78)
    print()
    print('  %-22s %6s %-14s %s' % ('clase', 'manos', 'que tocan', 'que toca'))
    print('  ' + '-' * 74)
    for clase in CLASES:
        n, tocan, det = resumen[clase]
        if not tocan:
            veredicto = 'NO TOCA NADA'
        else:
            campos = sorted({d.split()[0].rstrip(':') for v in det.values()
                             for d in v})
            veredicto = ', '.join(campos)
        print('  %-22s %6d %-14s %s'
              % (clase, n, len(tocan), veredicto))

    print()
    sucias = [c for c, (n, t, _d) in resumen.items() if t]
    if not sucias:
        print('  Las cuatro clases NO alteran las entradas de calibracion.')
        print('  Los 42 casos que quedan dentro de la ventana son defectuosos')
        print('  para el LECTOR del dato, no para el denominador.')
    else:
        print('  Las clases que SI alteran algo: %s' % ', '.join(sucias))
    return 0


if __name__ == '__main__':
    sys.exit(main())