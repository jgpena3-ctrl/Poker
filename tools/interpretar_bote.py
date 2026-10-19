# -*- coding: utf-8 -*-
"""Interprete de apuestas: convierte las acciones de una mano en el bote.

QUE HACE
--------
Las acciones guardan `amount` como la cantidad ABSOLUTA que cada jugador
tiene comprometida en la calle. Ese valor NO se corrige nunca: es el que
sirve para SPR, VPIP y demas estadisticas.

Lo que NO se puede hacer es sumar los `amount` para obtener el bote, por dos
motivos:

  1. Una apuesta NO COMPLETADA devuelve el exceso. Si un jugador sube a 113.0
     y el siguiente completa hasta 22.8, al que subio se le devuelven 90.2.
     Esos 90.2 nunca estuvieron en el bote.

  2. Un all-in CORTO aporta menos que la apuesta viva. Si la viva son 182.4
     y el que llama pone 27.9 porque no tiene mas, aporta 27.9, no 182.4.

REGLAS
------
En cada calle:
  1. se guarda cuanto compromete cada jugador (`amount` es absoluto)
  2. se identifica al ULTIMO que subio (apuesta `b` o subida `r`)
  3. `nivel` = lo mas alto que alcanzo cualquier OTRO jugador
     - si nadie subio, `nivel` es la apuesta viva (las ciegas)
  4. cada jugador aporta  min(lo que puso, nivel)
  5. el bote es la suma de las calles, menos la comision

Comision = min(5% del bote, 2.5). Es el tope que se ha confirmado en las
grabaciones: cuando el 5% pasa de 2.5, se cobra 2.5 y no mas.

EJEMPLOS COMPROBADOS
--------------------
H_0906  BB stack 22.8, queda con 1+3+18.8 = 22.8 exactos (all-in).
        CO sube a 113 y solo se igualan 22.8.
        bote = 0.5 + 22.8 + 4.0 + 22.8 + 1.0 - 2.5 = 48.6  (pot: 48.5)

H_0963  CO se va all-in con 182.4; MP solo tiene 27.9 y completa.
        al CO se le devuelven 154.5.
        bote = 4.0 (preflop) + 27.9 + 27.9 - 2.5 = 57.3  (pot: 57.3)
"""
import io
import json

STREETS = ('preflop', 'flop', 'turn', 'river')
COMISION_TOPE = 2.5
COMISION_PORC = 0.05


def comision(bote):
    return min(COMISION_PORC * bote, COMISION_TOPE)


def calle_igualada(acciones):
    """(fichas que quedan en el bote de la calle, nivel igualado)"""
    com = {}
    ultimo_subio = None
    for a in acciones or []:
        pos = a.get('pos')
        acc = a.get('action')
        v = a.get('amount') or 0.0
        if acc in ('f', 'x'):
            continue
        if acc not in ('p', 'b', 'c', 'r'):
            continue
        com[pos] = v
        if acc in ('b', 'r'):
            ultimo_subio = pos
    if not com:
        return 0.0, 0.0
    if ultimo_subio is None:
        nivel = max(com.values())
    else:
        otros = [c for p, c in com.items() if p != ultimo_subio]
        nivel = max(otros) if otros else 0.0
    return sum(min(c, nivel) for c in com.values()), nivel


def acciones_mano(mano, calle=None):
    """Todas las acciones de la mano, con su calle. Si `calle`, solo esa."""
    for st in STREETS:
        if calle and st != calle:
            continue
        for a in ((mano.get('streets', {}) or {}).get(st, {}) or {}).get(
                'actions', []) or []:
            yield st, a


def fichas_iguales(mano):
    """Fichas que se quedan en el bote, antes de comision."""
    return sum(calle_igualada([a for _, a in acciones_mano(mano, st)])[0]
               for st in STREETS)


def bote(mano, con_comision=True):
    t = fichas_iguales(mano)
    return t - comision(t) if con_comision else t


def comprobar(mano, tol=0.36):
    """Compara el bote calculado con el `final_pot` de la mano."""
    pot = mano.get('final_pot') or 0.0
    calc = bote(mano)
    return calc - pot, calc, pot


def cargar(ruta):
    with io.open(ruta, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


if __name__ == '__main__':
    import os
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    ruta = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.getcwd(), 'trabajo', 'hands_db_edicion.jsonl')
    manos = cargar(ruta)
    bien = 0
    for h in manos:
        d, calc, pot = comprobar(h)
        if abs(d) <= 0.36:
            bien += 1
    print('%d de %d botes cuadran con el pot registrado' % (bien, len(manos)))