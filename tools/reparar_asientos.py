# -*- coding: utf-8 -*-
"""Repara el contrato de asientos roto por la normalizacion de la base.

`winner`, `allin` y `btn_player` guardan ids de asiento (`hero`, `p1`..`p5`)
que se resuelven como indice en `players[]`. Ese contrato exige SIEMPRE seis
posiciones, en el orden de `motor.multiway.PLAYER_IDS`, y lo comprueba
`motor.multiway.contrato_orden_ok`.

La base adoptada el 2026-10-24 elimino los asientos sobrantes de 60 manos
(53 con cinco jugadores y 7 con cuatro). El resultado: ids fuera de rango y
posiciones resueltas contra el jugador equivocado. Esta herramienta devuelve
esos asientos desde una referencia anterior, sin tocar el resto de la mano.

No escribe la base canonica: el canal manual esta cerrado. Genera una
candidata y un informe para que A1 la revise y autorice su adopcion.
"""
import argparse
import hashlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor.multiway import PLAYER_IDS, contrato_orden_ok  # noqa: E402

DB_REL = os.path.join('data', 'hands_db.jsonl')
REF_REL = os.path.join('data', 'hands_db.jsonl.bak')
DEST_REL = os.path.join('trabajo', 'hands_db_reparada.jsonl')
INFO_REL = os.path.join('trabajo', 'reparacion_asientos.json')


def _sha(bruto):
    return hashlib.sha256(bruto).hexdigest()


def leer_lineas(ruta):
    with io.open(ruta, encoding='utf-8') as f:
        return [l.rstrip('\n') for l in f if l.strip()]


def cargar_manos(lineas):
    return [json.loads(l) for l in lineas]


def ids_fuera_de_rango(hand):
    malos = []
    ps = hand.get('players') or []
    for campo in ('btn_player', 'winner', 'allin'):
        valor = hand.get(campo)
        valores = valor if isinstance(valor, list) else [valor]
        for x in valores:
            if x is None:
                continue
            if x not in PLAYER_IDS or PLAYER_IDS.index(x) >= len(ps):
                malos.append((campo, x))
    return malos


def verificar(manos):
    problemas = []
    for h in manos:
        hid = h.get('hand_id')
        if not contrato_orden_ok(h):
            problemas.append((hid, 'jugadores=%d' % len(h.get('players') or [])))
            continue
        for campo, x in ids_fuera_de_rango(h):
            problemas.append((hid, '%s=%s fuera de rango' % (campo, x)))
    return problemas


def _reparar_mano(hand, ref):
    ps = hand.get('players') or []
    if len(ps) == len(PLAYER_IDS):
        return hand, 0
    if len(ps) > len(PLAYER_IDS):
        raise ValueError('%s tiene %d jugadores' % (hand.get('hand_id'), len(ps)))
    ref_ps = ref.get('players') or []
    if len(ref_ps) != len(PLAYER_IDS):
        raise ValueError('%s: la referencia no tiene seis asientos'
                         % hand.get('hand_id'))
    nombres = [p.get('name') for p in ps]
    if len(set(nombres)) != len(nombres):
        raise ValueError('%s: nombres repetidos en la mano'
                         % hand.get('hand_id'))
    ref_names = [p.get('name') for p in ref_ps]
    nuevo = [None] * len(PLAYER_IDS)
    for p in ps:
        nombre = p.get('name')
        if ref_names.count(nombre) != 1:
            raise ValueError('%s: %r no esta una sola vez en la referencia'
                             % (hand.get('hand_id'), nombre))
        nuevo[ref_names.index(nombre)] = p
    for i, p in enumerate(ref_ps):
        if nuevo[i] is None:
            nuevo[i] = json.loads(json.dumps(p))
    reparada = dict(hand)
    reparada['players'] = nuevo
    return reparada, len(PLAYER_IDS) - len(ps)


def reparar(lineas_base, lineas_ref):
    base = cargar_manos(lineas_base)
    ref = {h.get('hand_id'): h for h in cargar_manos(lineas_ref)}
    salida = []
    reparadas = []
    huecos = {1: 0, 2: 0}
    for linea, hand in zip(lineas_base, base):
        if len(hand.get('players') or []) == len(PLAYER_IDS):
            salida.append(linea)
            continue
        hid = hand.get('hand_id')
        if hid not in ref:
            raise ValueError('%s no esta en la referencia' % hid)
        reparada, n = _reparar_mano(hand, ref[hid])
        if n not in huecos:
            huecos[n] = 0
        huecos[n] += 1
        reparadas.append(hid)
        salida.append(json.dumps(reparada, ensure_ascii=False))
    candidata = cargar_manos(salida)
    antes = verificar(base)
    despues = verificar(candidata)
    if despues:
        raise ValueError('la candidata no verifica: %r' % (despues[:5],))
    return salida, {
        'manos': len(candidata),
        'reparadas': reparadas,
        'huecos': {str(k): v for k, v in sorted(huecos.items())},
        'problemas_antes': len(antes),
        'problemas_despues': len(despues),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog='reparar_asientos.py')
    ap.add_argument('--base', default=DB_REL)
    ap.add_argument('--referencia', default=REF_REL)
    ap.add_argument('--destino', default=DEST_REL)
    ap.add_argument('--informe', default=INFO_REL)
    args = ap.parse_args(argv)

    destino = os.path.abspath(args.destino)
    canonica = os.path.abspath(DB_REL)
    referencia = os.path.abspath(args.referencia)
    if destino in (canonica, referencia):
        print('EL DESTINO NO PUEDE SER LA BASE NI LA REFERENCIA', file=sys.stderr)
        return 2

    lineas_base = leer_lineas(args.base)
    lineas_ref = leer_lineas(args.referencia)
    try:
        salida, informe = reparar(lineas_base, lineas_ref)
    except ValueError as e:
        print('ERROR: %s' % e, file=sys.stderr)
        return 2

    bruto = ('\n'.join(salida) + '\n').encode('utf-8')
    informe.update({
        'sha_base': _sha(io.open(args.base, 'rb').read()),
        'sha_referencia': _sha(io.open(args.referencia, 'rb').read()),
        'sha_candidata': _sha(bruto),
        'lineas': len(salida),
    })
    with io.open(args.destino, 'w', encoding='utf-8', newline='\n') as f:
        f.write(bruto.decode('utf-8'))
    with io.open(args.informe, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(informe, f, ensure_ascii=False, indent=1)
    print(json.dumps(informe, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
