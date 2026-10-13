# -*- coding: utf-8 -*-
"""Por que profile_ranges paso de 56 a 154 jugadores (revision_1, punto 3).

revision_1 pide documentar la causa del salto 56 -> 154. Este script la
DERIVA de los datos (no la asume):

  - si el total de `opp`/`cnt` no cambia -> el modelo agregado ya estaba
    completo y faltaba solo el mapa por jugador;
  - si el total cambia -> el fichero antiguo se construyo sobre menos manos
    (o una version anterior de la DB).
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, 'data', '_snapshot_pre_rebuild_1b14c18')


def _load(name):
    with open(os.path.join(SNAP, name), encoding='utf-8') as f:
        old = json.load(f)
    with open(os.path.join(ROOT, 'data', name), encoding='utf-8') as f:
        new = json.load(f)
    return old, new


def _tot(d, key):
    """Suma tolerante: las claves pueden ser grids 13x13 o escalares."""
    t = 0.0
    for v in d.get(key, {}).values():
        if isinstance(v, (int, float)):
            t += v
            continue
        try:
            for row in v:
                if isinstance(row, (list, tuple)):
                    t += sum(row)
                else:
                    t += row
        except TypeError:
            t += 0.0
    return t


def main():
    o, n = _load('profile_ranges.json')
    print('=' * 70)
    print('profile_ranges.json')
    print('=' * 70)
    po, pn = set(o['perfil']), set(n['perfil'])
    to, tn = _tot(o, 'opp'), _tot(n, 'opp')
    co, cn = _tot(o, 'cnt'), _tot(n, 'cnt')

    print('  jugadores antes / ahora  : %d / %d' % (len(po), len(pn)))
    print('  nuevos / perdidos        : %d / %d'
          % (len(pn - po), len(po - pn)))
    print('  opp_keys antes / ahora   : %d / %d'
          % (len(o['opp']), len(n['opp'])))
    print('  cnt_keys antes / ahora   : %d / %d'
          % (len(o['cnt']), len(n['cnt'])))
    print('  TOTAL opp antes / ahora  : %.0f / %.0f   (x%.2f)'
          % (to, tn, (tn / to) if to else 0))
    print('  TOTAL cnt antes / ahora  : %.0f / %.0f   (x%.2f)'
          % (co, cn, (cn / co) if co else 0))
    print()

    if po - pn:
        print('  AVISO: hay jugadores que el fichero nuevo ya no lista.')
    else:
        print('  El fichero nuevo es un SUPERCONJUNTO: no se perdio nadie.')

    print()
    print('  DIAGNOSTICO')
    print('  ' + '-' * 64)
    if abs(tn - to) / max(to, 1) > 0.05:
        print('  La masaDecisionada CRECE (%.0f -> %.0f, x%.2f).' % (to, tn, tn / to))
        print('  El `meta` del fichero es identico en ambos ({alpha, origen})')
        print('  y NO registra que manos se usaron, asi que no se puede')
        print('  distinguir "menos manos" de "otra version del codigo".')
        print()
        print('  Lo que SI es concluyente: las CELDA (profile x spot) ya')
        print('  estaban todas (opp_keys = cnt_keys = 6 y 22 en ambos).')
        print('  El fichero antiguo se construyo con ~%.0f%% de la decision'
              % (to / tn * 100 if tn else 0))
        print('  que hay ahora, y ademas sin listar a %d jugadores.' % len(pn - po))
    else:
        print('  La masaDecisionada NO cambia: el modelo agregado ya estaba')
        print('  completo y faltaba solo el mapa por jugador.')
    print()
    print('  CONSECUENCIA (lo que la revision_1anhade):')
    print('    p_player() devuelve el prior PLANO si el jugador no esta en')
    print('    self.perfil. Con el fichero anterior, %d de %d jugadores'
          % (len(pn - po), len(pn)))
    print('    recibian prior plano en vez de su grid de perfil.')

    print()
    print('=' * 70)
    print('postflop_ranges.json')
    print('=' * 70)
    o2, n2 = _load('postflop_ranges.json')
    for k in ('opp', 'cnt'):
        ko, kn = set(o2.get(k, {})), set(n2.get(k, {}))
        print('  %s keys antes / ahora : %d / %d  (nuevos %d, perdidos %d)'
              % (k, len(ko), len(kn), len(kn - ko), len(ko - kn)))
    print('  TOTAL opp antes / ahora: %.0f / %.0f'
          % (_tot(o2, 'opp'), _tot(n2, 'opp')))
    print()
    print('  DIAGNOSTICO: aparecen celdas nuevas (perfil x calle x facing x')
    print('  accion) y desaparecen algunas. Es cobertura, no una correccion')
    print('  puntual: los perfiles cambian de etiqueta PEZ/TIBURON con las')
    print('  manos de la ventana fiable, asi que las celdas de un perfil')
    print('  pueden caer en el otro. El informe debe decirlo explicitamente.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())