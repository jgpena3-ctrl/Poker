"""Auditoria del orden temporal de la reconstruccion preflop (revision_2).

RIESGO
------
`_reconstruct_preflop()` recorre las posiciones en orden fijo (UTG, MP, CO,
BTN, SB, BB) y por tanto NO reproduce el orden real en que actuaron los
jugadores. `preflop_events()` calcula raises/limps/callers a partir de las
acciones PRECEDENTES, así que un orden inferido incorrecto contamina las
categorías aunque la detección de la ciega sea correcta.

Ejemplo del fallo:
    UTG bet=5.0   (call)     <- se emite PRIMERO (posición)
    BB  bet=9.0   (raise)    <- se emite DESPUÉS
  -> preflop_events ve 'c' con raises=0 y lo clasifica `limp` cuando en
     realidad fue un `call_open`.

SEÑAL DISPONIBLE Y SU LÍMITE
-----------------------------
El `bet` observado pretende ser la contribución acumulada del jugador en la
calle, y ESA magnitud sería monótona en el tiempo (nadie aporta más que la
apuesta vigente), así que daría un orden parcial real.

Pero §6.1 de PROYECTO.md ya documenta que `amount` mezcla niveles observados y
incrementos calculados. ConAmount mezclado la señal NO es fiable, y este
script separa ambas cosas para no atribuir a "desorden temporal" lo que en
realidad es el defecto de semántica de `amount`.
"""
import collections
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_spec = importlib.util.spec_from_file_location(
    'learn', os.path.join(ROOT, 'motor', 'learn.py'))
learn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(learn)

POS_ORDER = ['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB']
BLIND_POR_POS = {'BB': 1.0, 'SB': 0.5}


def _es_delta(amt_menor, pos_menor, amt_mayor):
    """True si `amt_menor` parece un INCREMENTO, no un nivel.

    Si sumando la ciega del jugador el valor alcanza (o casi) el nivel mayor,
    entonces `amount` es un delta -> el "desorden" es un artefacto de §6.1,
    no un error de orden temporal.
    """
    ciega = BLIND_POR_POS.get(pos_menor, 0.0)
    return abs((amt_menor + ciega) - amt_mayor) <= 0.15


def main():
    hands = learn.load_hands(reliable_only=True)
    n_preflop = 0
    viola = 0
    viola_delta = 0      # explicable por amount delta (defecto §6.1)
    viola_real = 0       # desorden temporal genuino
    ejemplos_real = []
    ejemplos_delta = []

    for h in hands:
        acts = (h.get('streets', {}) or {}).get('preflop', {}) or {}
        raw = acts.get('actions') or []
        vol = [(a.get('pos'), a.get('action'), float(a.get('amount') or 0.0))
               for a in raw
               if a.get('action') in ('b', 'r', 'c')
               and a.get('pos') and float(a.get('amount') or 0.0) > 1.0
               and not a.get('blind')]
        if len(vol) < 2:
            continue
        n_preflop += 1

        orden = [v[2] for v in vol]
        if orden == sorted(orden):
            continue
        viola += 1

        # La primera inversión ¿se explica por un delta?
        primera = None
        for i in range(len(orden) - 1):
            if orden[i] > orden[i + 1]:
                primera = i
                break
        if primera is not None and _es_delta(orden[primera + 1],
                                             vol[primera + 1][0],
                                             orden[primera]):
            viola_delta += 1
            if len(ejemplos_delta) < 4:
                ejemplos_delta.append((h.get('hand_id'), vol))
        else:
            viola_real += 1
            if len(ejemplos_real) < 6:
                ejemplos_real.append((h.get('hand_id'), vol))

    print(f'manos con >=2 acciones voluntarias:            {n_preflop}')
    print(f'  orden grabado no respeta bet ascendente:     {viola}'
          f'  ({viola / n_preflop * 100:.1f}%)')
    print(f'    explicable por amount=delta (§6.1):        {viola_delta}'
          f'  ({viola_delta / n_preflop * 100:.1f}%)')
    print(f'    desorden temporal GENUINO:                 {viola_real}'
          f'  ({viola_real / n_preflop * 100:.1f}%)')

    print()
    print('--- desorden genuino (orden grabado imposible) ---')
    if ejemplos_real:
        for hid, vol in ejemplos_real:
            print(f'  {hid}: {vol}')
            print(f'      bet {[v[2] for v in vol]}')
    else:
        print('  ninguno: el orden grabado es consistente en todos los casos')

    print()
    print('--- artefactos de amount=delta (NO son desorden) ---')
    for hid, vol in ejemplos_delta:
        print(f'  {hid}: {vol}')
    return 0


if __name__ == '__main__':
    sys.exit(main())