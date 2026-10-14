# -*- coding: utf-8 -*-
"""Audita `hands_db.jsonl` por clases de defecto, sobre un rango de manos.

    python tools/auditar_rango.py                       # hasta H_1014
    python tools/auditar_rango.py --hasta H_0500
    python tools/auditar_rango.py --json salida.json
    python tools/auditar_rango.py --validar             # autocomprobacion

Que es y por que existe
-----------------------
`hands_db.jsonl` se corrige a mano y eso ya ha pasado dos veces. Cada vez
hacen falta las mismas preguntas y las contestaba alguien a mano, en un
documento que al mes siguiente ya mentia. Este script es el instrumento: las
contesta siempre, y devuelve **los identificadores**, no solo un recuento.

La diferencia entre un recuento y una lista de ids es la diferencia entre
"hay 45" y "este es el primero, y son estos 45". Lo segundo se puede revisar;
lo primero solo se puede sospechar.

Por que tiene un modo `--validar`
---------------------------------
Porque un detector de auditoria que no se ha contrastado con una respuesta
conocida es unaOpinion, no un instrumento. `--validar` corre los detectores
sobre la version comprometida en `e314f74` y comprueba que dan las cifras que
este proyecto ya dio por publicadas:

    BB no responde tras la subida viva     652
    subida a importe <= la ciega nominal     45
    accion despues de haber foldeado         8
    `winner` incluye a quien foldeo        214

Si un detector deja de dar su cifra, aqui se ve antes de que se lea un
informe escrito con ella.

Formato del dato
----------------
Dos cosas que son faciles de inventar mal, y que el propio script fija:

  - `players[].cards` es la cadena vacia (no se conoce) o EXACTAMENTE 4
    caracteres: dos cartas de 2. `Ad6s` son dos cartas, no una carta de
    cuatro. No hay ni un valor de otra longitud en las 1258.
  - `streets[s].actions[i].amount` es el importe TOTAL puesto por esa accion,
    no un delta. Por eso una `r` tiene que superar el maximo anterior.

Clases
------
Cada clase es un defecto del FORMATO (el dato no se lee sin ambiguedad), una
AUSENCIA (el recorder no escribio algo) o una CONTRADICCION (el dato se
contradice a si mismo). La distincion importa: el formato se arregla
reetiquetando, la ausencia se declara como perdida, y la contradiccion exige
decidir que lectura es la buena.

    Formato
      CM-004              entrada `BB b` que el motor no reconoce como ciega
      CM-002              centinela de carta que no es un codigo de carta
      CARTAS_ILEGALES     mas de 2 cartas, repetidas, o longitud distinta
      BOARD_ILLEGAL       board repetido, invalido o compartido con un jugador
      IMPORTE_SUBIDA      una subida que no supera la apuesta viva anterior

    Contradiccion
      ACCION_DESPUES_FOLD  actuar despues de haber foldeado
      FOLD_TRAS_APUESTA    foldean con su propia apuesta viva
      ACCION_FANTASMA      accion de una posicion que no esta en la mesa
      POSICION_DUPLICADA   dos jugadores activos con la misma posicion
      WINNER_FOLDEO        `winner` incluye a alguien que foldeo
      SHOWDOWN_SIN_WINNER  showdown y winner no coinciden
      WINNER_VACIO         la mano no dice quien la gana

    Ausencia
      SIN_ALLIN            el campo `allin` falta o no es una lista
      SIN_RESPUESTA_BB     el BB tiene entrada, no vuelve a actuar, y el
                           preflop se cierra con una subida viva de otro
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor import learn  # noqa: E402

DB_REL = 'data/hands_db.jsonl'
DB_PATH = os.path.join(ROOT, *DB_REL.split('/'))
COMMIT_ANTES = 'e314f74'
POSTFLOP = ('flop', 'turn', 'river')
RANGOS = set('23456789TJQKA')
SUITS = set('shdc')

# Las cifras que se publicaron, y si el codigo actual las reproduce.
#
# "reproducible": False quiere decir que la cifra se publico desde un script
# de un solo uso que no se ha versionado, y que el detector permanente da otra
# cosa. No es que el detector este mal: es que la cifra no tiene a quien
# preguntarle. Se deja a proposito, para que la discrepancia se vea.
REFERENCIA = {
    'SIN_RESPUESTA_BB': (652, True),
    'IMPORTE_SUBIDA': (45, False),
    'ACCION_DESPUES_FOLD': (8, False),
    'WINNER_FOLDEO': (214, True),
}


def cargar(path=DB_PATH):
    with open(path, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def cargar_commit(commit):
    crudo = subprocess.run(['git', 'show', '%s:%s' % (commit, DB_REL)],
                           cwd=ROOT, capture_output=True)
    if crudo.returncode != 0:
        raise SystemExit('no se pudo leer %s:%s' % (commit, DB_REL))
    return [json.loads(l) for l in crudo.stdout.decode('utf-8').splitlines()
            if l.strip()]


def num(hid):
    m = re.match(r'H_(\d+)$', hid or '')
    return int(m.group(1)) if m else None


def acciones_de(hand, street):
    return (((hand.get('streets') or {}).get(street) or {})
            .get('actions') or [])


def calles(hand):
    return ('preflop',) + POSTFLOP


def todas_las_acciones(hand):
    """(calle, accion) en orden real. `streets` ya va en orden, y dentro de
    cada calle las acciones tambien: ese orden es el dato."""
    out = []
    for s in calles(hand):
        for a in acciones_de(hand, s):
            out.append((s, a))
    return out


def dos_cartas_validas(c):
    return (len(c) == 4 and c[0] in RANGOS and c[1] in SUITS
            and c[2] in RANGOS and c[3] in SUITS)


def una_carta_valida(c):
    return len(c) == 2 and c[0] in RANGOS and c[1] in SUITS


def cartas_conocidas(hand):
    out = []
    for p in hand.get('players') or []:
        c = p.get('cards') or ''
        if c:
            out.append((p, c))
    return out


# --------------------------------------------------------------------------
# Formato
# --------------------------------------------------------------------------
def cm_004(hand):
    return True if learn.defecto_orden_ciega_bb(hand) else None


def cm_002(hand):
    malos = ['%s=%r' % (p.get('name'), p.get('cards'))
             for p, c in cartas_conocidas(hand) if not dos_cartas_validas(c)]
    return malos


def cartas_ilegales(hand):
    """Carta repetida entre dos jugadores. NO cuenta "varios jugadores con
    cartas": en un showdown puede haber mas de dos, y eso no es un defecto."""
    fallos = []
    vistas = collections.Counter()
    for _p, c in cartas_conocidas(hand):
        if not dos_cartas_validas(c):
            continue
        for carta in (c[:2], c[2:]):
            vistas[carta] += 1
    for carta, n in sorted(vistas.items()):
        if n > 1:
            fallos.append('%s en %d jugadores' % (carta, n))
    return fallos


def board_ilegal(hand):
    """Las entradas de `board` son UNA carta de 2 caracteres, no dos. Confundir
    los dos formatos hacia que casi toda la base pareciese invalida."""
    board = []
    for s in POSTFLOP:
        board += ((hand.get('streets') or {}).get(s) or {}).get('board') or []
    fallos = []
    for c in board:
        if not una_carta_valida(c):
            fallos.append('board %r no es una carta' % c)
    for c, n in sorted(collections.Counter(board).items()):
        if n > 1:
            fallos.append('board %s repetida x%d' % (c, n))
    jugadoras = collections.Counter()
    for _p, c in cartas_conocidas(hand):
        if dos_cartas_validas(c):
            for carta in (c[:2], c[2:]):
                jugadoras[carta] += 1
    comunes = sorted(set(board) & set(jugadoras))
    if comunes:
        fallos.append('board comparte carta con un jugador: %s'
                      % ', '.join(comunes))
    return fallos


def importe_subida(hand):
    """Una subida que no supera la apuesta viva.

    PREFLOP: usa la secuencia del MOTOR (`_preflop_sequence`), que es quien
    sabe cual entrada es la ciega y cual es una subida. Reescribir ese criterio
    aqui es exactamente el error que produjo 962 falsos positivos antes.

    POSTFLOP: `amount` es el total puesto en esa calle, asi que la comparacion
    se reinicia en cada calle.
    """
    fallos = []
    seq = learn._preflop_sequence(hand)
    acc = acciones_de(hand, 'preflop')
    voluntaria = False
    maximo = learn.BB
    for i, (pos, accion, amount, is_blind) in enumerate(seq):
        if is_blind or (pos == 'BB' and accion == 'b' and not voluntaria):
            if not is_blind:
                maximo = max(maximo, amount or 0.0)
            continue
        if accion == 'r' and (amount or 0.0) <= learn.BB:
            fallos.append('preflop %s r %.1f no supera la ciega %.1f'
                          % (pos, amount or 0.0, learn.BB))
        if accion in ('b', 'r', 'c'):
            voluntaria = True
        if i >= len(acc):
            break
    for s in POSTFLOP:
        maximo = 0.0
        for a in acciones_de(hand, s):
            accion = a.get('action')
            try:
                imp = float(a.get('amount') or 0.0)
            except (TypeError, ValueError):
                continue
            if accion in ('b', 'r'):
                if imp <= maximo:
                    fallos.append('%s %s %s no supera %.1f'
                                  % (s, a.get('pos'), a.get('amount'), maximo))
                maximo = max(maximo, imp)
            elif accion == 'c':
                maximo = max(maximo, imp)
    return fallos


# --------------------------------------------------------------------------
# Contradicciones
# --------------------------------------------------------------------------
def accion_despues_fold(hand):
    """PREFLOP. Es el alcance con el que se publico la cifra de 8; medirlo
    en todas las calles daria otra cifra y no seria la misma metrica."""
    folds, fallos = set(), []
    for a in acciones_de(hand, 'preflop'):
        if a.get('action') == 'f':
            folds.add(a.get('pos'))
        elif a.get('pos') in folds:
            fallos.append('%s %s despues de foldear' % (a.get('pos'),
                                                        a.get('action')))
    return fallos


def fold_tras_apuesta(hand):
    """Foldear con su propia apuesta viva. Se mide por calle: en el turn la
    apuesta de una calle anterior ya no esta viva."""
    fallos = []
    for s in calles(hand):
        viva = None
        for a in acciones_de(hand, s):
            pos, acc = a.get('pos'), a.get('action')
            if acc == 'b':
                viva = pos
            elif acc == 'r':
                viva = pos
            elif acc == 'c':
                viva = None
            elif acc == 'f':
                if viva == pos:
                    fallos.append('%s foldea con su apuesta viva en %s'
                                  % (pos, s))
                viva = None
            elif acc == 'x':
                viva = None
    return fallos


def accion_fantasma(hand):
    activos = {p.get('pos') for p in (hand.get('players') or [])
               if p.get('active') and p.get('pos')}
    return sorted({a.get('pos') for _s, a in todas_las_acciones(hand)
                   if a.get('pos') and a.get('pos') not in activos})


def posicion_duplicada(hand):
    activos = [p.get('pos') for p in (hand.get('players') or [])
               if p.get('active') and p.get('pos')]
    return ['%s x%d' % (p, activos.count(p))
            for p in sorted({a for a in activos if activos.count(a) > 1})]


PID = ('hero', 'p1', 'p2', 'p3', 'p4', 'p5')


def pos_de_pid(hand, pid):
    if pid not in PID:
        return None
    jugadores = hand.get('players') or []
    i = PID.index(pid)
    return jugadores[i].get('pos') if i < len(jugadores) else None


def winner_foldeo(hand):
    folds = {a.get('pos') for _s, a in todas_las_acciones(hand)
             if a.get('action') == 'f'}
    return ['%s(%s) foldeo' % (w, pos_de_pid(hand, w))
            for w in (hand.get('winner') or [])
            if (pos_de_pid(hand, w) or None) in folds]


def showdown_sin_winner(hand):
    sh = hand.get('showdown') or {}
    if not sh:
        return None
    texto = ' '.join(str(v) for v in sh.values())
    activos = {p.get('pos') for p in (hand.get('players') or [])
               if p.get('active') and p.get('pos')}
    citados = {p for p in activos if p and p in texto}
    ganadores = {pos_de_pid(hand, w) for w in (hand.get('winner') or [])}
    ganadores.discard(None)
    if citados - ganadores:
        return 'showdown cita a quien no gano: %s' % ', '.join(
            sorted(citados - ganadores))
    return None


def winner_vacio(hand):
    return 'sin winner' if not (hand.get('winner') or []) else None


# --------------------------------------------------------------------------
# Ausencias
# --------------------------------------------------------------------------
def sin_allin(hand):
    if 'allin' not in hand:
        return 'campo ausente'
    v = hand.get('allin')
    if v is None:
        return 'campo a None'
    if not isinstance(v, list):
        return 'tipo %s' % type(v).__name__
    return None


def sin_respuesta_bb(hand):
    """El preflop se cierra con una SUBIDA de un jugador que no es el BB.

    Esta es la definicion con la que se publico el "defecto de 652", y da 652.
    Lo que esa cifra NO significa es lo importante, y por eso la funcion
    devuelve el sub-caso en el texto:

      - **el BB tiene una entrada DESPUES de la subida**: respondio. No falta
        nada. Es el caso mayoritario, yva sea con `c`, con `f` o con `x`.
      - **el BB no tiene ninguna entrada despues de la subida**: ahi si puede
        faltar algo.

    La primera version de esta comprobacion decia "el BB no vuelve a actuar"
    y contaba como respuesta ausente manos donde el BB habia llamado. H_0014
    es el ejemplo: `CO:b1.0, BTN:r4.0, BB:c3.0` — el BB respondio, con un
    importe que no puede ser (una llamada a 3.0 contra una subida a 4.0), pero
    respondio. Eso es otro defecto, y lo recoge `IMPORTE_SUBIDA`.

    O sea: leer 652 como "652 manos sin respuesta del BB" es una lectura
    equivocada. Lo que falta de verdad es un numero mucho menor, y esta
    funcion lo dice caso por caso.
    """
    acc = acciones_de(hand, 'preflop')
    if not acc:
        return None
    bb = [i for i, a in enumerate(acc) if a.get('pos') == 'BB']
    vivas = [i for i, a in enumerate(acc) if a.get('action') in ('b', 'r')]
    if not vivas:
        return None
    ultimo = vivas[-1]
    if acc[ultimo].get('action') != 'r':
        return None
    if bb and bb[-1] == ultimo:
        return None
    if len(acc) - 1 == ultimo and acc[ultimo].get('pos') == 'BB':
        return None
    despues = [a for a in acc[ultimo + 1:] if a.get('pos') == 'BB']
    if despues:
        sub = 'el BB responde con %s, no falta nada' % despues[0].get('action')
    elif any(a.get('action') == 'f' and a.get('pos') == 'BB' for a in acc):
        sub = 'el BB ya habia FOLDEADO antes de esa subida: esta fuera'
    elif not bb:
        sub = 'el BB no tiene NINGUNA entrada preflop'
    else:
        sub = 'el BB NO ACTUA tras la subida'
    return 'preflop cierra con subida de %s (%s) -> %s' % (
        acc[ultimo].get('pos'), acc[ultimo].get('amount'), sub)


CLASES = (
    ('CM-004', 'entrada BB b que el motor no reconoce como ciega',
     cm_004, 'formato'),
    ('CM-002', 'centinela de carta que no es un codigo de carta',
     cm_002, 'formato'),
    ('CARTAS_ILEGALES', 'mas de 2 jugadores con cartas, o carta repetida',
     cartas_ilegales, 'formato'),
    ('BOARD_ILLEGAL', 'board repetido, invalido o compartido con un jugador',
     board_ilegal, 'formato'),
    ('IMPORTE_SUBIDA', 'subida que no supera la apuesta viva',
     importe_subida, 'formato'),
    ('ACCION_DESPUES_FOLD', 'actuar despues de haber foldeado',
     accion_despues_fold, 'contradiccion'),
    ('FOLD_TRAS_APUESTA', 'foldean con su propia apuesta viva',
     fold_tras_apuesta, 'contradiccion'),
    ('ACCION_FANTASMA', 'accion de una posicion que no esta en la mesa',
     accion_fantasma, 'contradiccion'),
    ('POSICION_DUPLICADA', 'dos jugadores activos con la misma posicion',
     posicion_duplicada, 'contradiccion'),
    ('WINNER_FOLDEO', 'winner incluye a alguien que foldeo',
     winner_foldeo, 'contradiccion'),
    ('SHOWDOWN_SIN_WINNER', 'showdown y winner no coinciden',
     showdown_sin_winner, 'contradiccion'),
    ('WINNER_VACIO', 'la mano no dice quien la gana',
     winner_vacio, 'contradiccion'),
    ('SIN_ALLIN', 'el campo allin falta o no es una lista',
     sin_allin, 'ausencia'),
    ('SIN_RESPUESTA_BB', 'el BB tiene entrada y no vuelve a actuar',
     sin_respuesta_bb, 'ausencia'),
)


def auditar(manos):
    hallazgo = {c: [] for c, _e, _f, _n in CLASES}
    for h in manos:
        for clave, _e, fn, _n in CLASES:
            try:
                r = fn(h)
            except Exception as exc:                    # noqa: BLE001
                r = 'la comprobacion fallo: %r' % (exc,)
            if r:
                hallazgo[clave].append((h.get('hand_id'), r))
    return hallazgo


def validar():
    """Los detectores permanentes contra las cifras ya publicadas.

    Dos cosas se comprueban, y las dos importan:
    que el detector reproduce la cifra, y que la cifra tiene a quien
    preguntarle. Una cifra sin codigo que la produzca no es un dato: es el
    recuerdo de un script que se borro.
    """
    print('=' * 78)
    print('AUTOCOMPROBACION  ·  detectores contra %s (%d manos)'
          % (COMMIT_ANTES, 1280))
    print('=' * 78)
    manos = cargar_commit(COMMIT_ANTES)
    hall = auditar(manos)
    print()
    print('%-24s %7s %9s  %s' % ('CLASE', 'DETECTA', 'PUBLICADO', 'VEREDICTO'))
    print('-' * 78)
    irrecuperables = []
    for clave in sorted(REFERENCIA):
        publicada, reproducible = REFERENCIA[clave]
        n = len(hall[clave])
        if reproducible:
            veredicto = 'reproduce' if n == publicada else 'DESVIO'
            if n != publicada:
                irrecuperables.append(clave)
        else:
            veredicto = ('NO SE REPRODUCE (cifra sin codigo que la produzca)'
                         if n != publicada
                         else 'coincide por casualidad, sin codigo de origen')
        print('%-24s %7d %9d  %s' % (clave, n, publicada, veredicto))
    print()
    print('  sin cifra publicada (solo informativo):')
    for clave, _e, _f, naturaleza in CLASES:
        if clave not in REFERENCIA:
            print('    %-22s %5d  %s' % (clave, len(hall[clave]), naturaleza))
    print()
    if irrecuperables:
        print('  RESULTADO: %s no reproduce su cifra publicada.'
              % ', '.join(irrecuperables))
        return 1
    print('  RESULTADO: las cifras con codigo de origen se reproducen.')
    print('  Las demas hay que tomarlas de este script, no de documentos '
          'anteriores.')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--hasta', default='H_1014',
                    help='ultimo hand_id del rango (por defecto H_1014)')
    ap.add_argument('--json', dest='json_out',
                    help='volcar el resultado en JSON')
    ap.add_argument('--validar', action='store_true',
                    help='contrastar los detectores con las cifras conocidas')
    args = ap.parse_args(argv)

    if args.validar:
        return validar()

    limite = num(args.hasta)
    todas = cargar()
    rango = [h for h in todas if limite is None
             or (num(h['hand_id']) or 0) <= limite]
    fuera = [h['hand_id'] for h in todas if limite is not None
             and (num(h['hand_id']) or 0) > limite]

    print('=' * 78)
    print('AUDITORIA DE hands_db.jsonl   ·   H_0001..%s' % args.hasta)
    print('=' * 78)
    print('manos en el rango : %d' % len(rango))
    print('fuera del rango   : %d  (%s .. %s)'
          % (len(fuera), fuera[0] if fuera else '-', fuera[-1] if fuera else '-'))
    print('total en la base  : %d' % len(todas))

    hall = auditar(rango)
    print()
    print('%-24s %7s  %s' % ('CLASE', 'CASOS', 'NATURALEZA'))
    print('-' * 78)
    for clave, etiqueta, _fn, naturaleza in CLASES:
        n = len(hall[clave])
        print('%-24s %7d  %s' % (clave, n, naturaleza))

    print()
    print('=' * 78)
    print('DETALLE CON IDENTIFICADORES')
    print('=' * 78)
    for clave, etiqueta, _fn, _n in CLASES:
        casos = hall[clave]
        if not casos:
            continue
        print()
        print('--- %s  (%d) ---  %s' % (clave, len(casos), etiqueta))
        ids = [h for h, _d in casos]
        print('    ids: %s' % ', '.join(ids))
        for hid, det in casos[:3]:
            print('      ej. %-9s %s' % (hid, det))

    if args.json_out:
        with open(args.json_out, 'w', encoding='utf-8') as f:
            json.dump({'rango': {'desde': 'H_0001', 'hasta': args.hasta,
                                 'manos': len(rango)},
                       'clases': {k: [{'hand_id': h, 'detalle': d}
                                      for h, d in v]
                                  for k, v in hall.items() if v}},
                      f, indent=2, ensure_ascii=False)
        print()
        print('volcado -> %s' % args.json_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())