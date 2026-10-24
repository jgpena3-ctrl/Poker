# -*- coding: utf-8 -*-
"""Audita `hands_db.jsonl` por clases de defecto, sobre un rango de manos.

    python tools/auditar_rango.py                       # hasta H_1014
    python tools/auditar_rango.py --hasta H_0500
    python tools/auditar_rango.py --db <otra.jsonl>      # otra base o copia
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
      INACTIVO_QUE_ACTUA   jugador inactivo que tiene acciones

    Formato
      ACTIVO_SIN_POSICION  jugador activo sin posicion asignada

    Ausencia
      ACTIVO_SIN_ACCION    activo que no actua nunca, ni foldea ni va all-in
      ACTIVO_SIN_ACCION_CALLE  activo que desaparece en una calle con acciones
      SIN_ALLIN            el campo `allin` falta o no es una lista
      SIN_RESPUESTA_BB     el BB tiene entrada, no vuelve a actuar, y el
                           preflop se cierra con una subida viva de otro

    Forma (no defecto)
      INACTIVO_CON_POSICION  inactivo que conserva posicion: solo es defecto
                             cuando ademas actua (`INACTIVO_QUE_ACTUA`)
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
    # Las dos metricas del BB, con nombres que no se pueden confundir. review
    # revision_2 §2: el patron historico (652) NO es el recuento de ausencias
    # (23), y publicarlos bajo un solo nombre es lo que produjo el error de
    # lectura de los tres bloques anteriores.
    'PATRON_BB_SIN_RESPUESTA': (652, True),
    'AUSENCIA_RESPUESTA_BB': (23, True),
    # Estas dos NO reproducen, y la razon es que se publicaron desde scripts
    # de un solo uso que no se han versionado. No es que el detector este mal:
    # es que la cifra no tiene a quien preguntarle.
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
    """Una subida que no supera la apuesta viva anterior.

    review revision_2 §3: la version anterior comparaba cada `r` contra
    `learn.BB`, que es la CIEGA NOMINAL, no contra lo que estaba vivo en ese
    momento. Con eso, una subida que supera la ciega pero no la apuesta
    anterior pasaba desapercibida, y el recuento no era exhaustivo.

    Ahora se lleva el maximo de lo apostado. PREFLOP usa la secuencia del
    MOTOR (`_preflop_sequence`), que es quien sabe cual entrada es la ciega;
    reimplementar ese criterio aqui es el error que produjo 962 falsos
    positivos. POSTFLOP se mide por calle, porque `amount` es el total puesto
    en esa calle y el bote no arrastra.
    """
    fallos = []
    for s in calles(hand):
        # El suelo de una calle es lo que hay que superar para subir. En
        # PREFLOP es la ciega grande SIEMPRE, este o no este grabada: y esa
        # distincion importa, porque una mano sin la ciega del BB registrada
        # —que es justo la firma de CM-004— si no tendria suelo y cualquier
        # subida pasaria el filtro.
        maximo = learn.BB if s == 'preflop' else 0.0
        for a in acciones_de(hand, s):
            accion = a.get('action')
            try:
                imp = float(a.get('amount') or 0.0)
            except (TypeError, ValueError):
                continue
            if accion == 'r':
                if imp <= maximo:
                    fallos.append('%s %s %s no supera la apuesta viva (%.1f)'
                                  % (s, a.get('pos'), a.get('amount'), maximo))
                maximo = max(maximo, imp)
            elif accion in ('b', 'c'):
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


def inactivo_que_actua(hand):
    """Jugadores marcados `active: false` que tienen acciones.

    MEDIDO, y el motivo de que exista: el defecto real de `H_1203` era este,
    y ningun detector lo miraba. `accion_fantasma` lo rozaba —decia que el BB
    de esa mano no estaba en la mesa— pero por el motivo equivocado, porque
    confundia `active` con «está en la mesa». Al arreglar ese detector, el
    defecto de `H_1203` desaparecio del informe sin haberse corregido, que es
    la forma mas uncomfortable de que un agujero se esconda: no como error,
    sino como silencio.

    Que `active: false` se pueda interpretar, y cuando: en la base hay 21
    jugadores con `pos` puesta y `active: false`, y 20 de ellos no tienen
    ninguna accion. Son los que se sentaron y noMigration jugado, que es
    justo lo que la bandera significa. Uno, en cambio, postea y llama tres
    calles, y ese es un dato roto.
    """
    actions = {a.get('pos') for _s, a in todas_las_acciones(hand) if a.get('pos')}
    return sorted(
        '%s(%s)' % (p.get('pos'), p.get('name'))
        for p in (hand.get('players') or [])
        if p.get('pos') and not p.get('active') and p.get('pos') in actions)


def activo_sin_posicion(hand):
    """Jugadores `active: true` sin una `pos` utilizable.

    `active` no significa «sigue en la mano» (eso lo dice la accion), pero si
    significa «se sento a jugar». Un jugador sentado sin posicion no se puede
    situar en la mesa ni en el orden de accion: es un dato que falta.
    """
    fallos = []
    for p in (hand.get('players') or []):
        if not p.get('active'):
            continue
        if not (p.get('pos') or '').strip():
            fallos.append('%s sin pos' % (p.get('name') or '?'))
    return fallos


def activo_sin_accion(hand):
    """Activos que no actuaron en NINGUNA calle, y no foldearon ni fueron
    all-in. Un jugador asi nunca tomo una decision: o el registro perdio sus
    acciones, o la bandera `active` esta mal puesta.

    No se cuentan los que foldearon (tuvieron su accion `f`) ni los all-in
    (pueden no volver a actuar). La lista `allin` guarda pids (`p3`), no
    posiciones, y se traduce con `pos_de_pid`.
    """
    acciones = {a.get('pos') for _s, a in todas_las_acciones(hand)
                if a.get('pos')}
    folds = {a.get('pos') for _s, a in todas_las_acciones(hand)
             if a.get('action') == 'f' and a.get('pos')}
    allin = {pos_de_pid(hand, pid) for pid in (hand.get('allin') or [])}
    allin.discard(None)
    fallos = []
    for p in (hand.get('players') or []):
        if not p.get('active') or not p.get('pos'):
            continue
        pos = p.get('pos')
        if pos in acciones or pos in folds or pos in allin:
            continue
        fallos.append('%s sin accion ni fold ni all-in' % pos)
    return fallos


def activo_sin_accion_calle(hand):
    """Por calle: activos que no actuaron en una calle CON acciones, sin estar
    foldeados ni all-in al empezar esa calle.

    Es mas fino que `activo_sin_accion`: detecta al que actuo en preflop y
    desaparece en el flop. Las calles sin acciones (check-check no grabado o
    mano terminada) no se cuentan: ahi no falta una accion, falta el registro.
    """
    allin = {pos_de_pid(hand, pid) for pid in (hand.get('allin') or [])}
    allin.discard(None)
    folds = set()
    fallos = []
    for s in calles(hand):
        acts = acciones_de(hand, s)
        if not acts:
            continue
        actuaron = {a.get('pos') for a in acts if a.get('pos')}
        for p in (hand.get('players') or []):
            pos = p.get('pos')
            if not p.get('active') or not pos:
                continue
            if pos in folds or pos in allin:
                continue
            if pos not in actuaron:
                fallos.append('%s sin accion en %s' % (pos, s))
        folds |= {a.get('pos') for a in acts
                  if a.get('action') == 'f' and a.get('pos')}
    return fallos


def inactivo_con_posicion(hand):
    """Jugadores `active: false` que conservan una `pos`.

    Es una FORMA, no un defecto por si sola: en la base son jugadores que se
    sentaron y no jugaron. Se publica como metrica porque el subconjunto que
    ademas actua —`INACTIVO_QUE_ACTUA`— si es una contradiccion.
    """
    return sorted('%s(%s)' % (p.get('pos'), p.get('name') or '?')
                  for p in (hand.get('players') or [])
                  if not p.get('active') and (p.get('pos') or '').strip())


def accion_fantasma(hand):
    """Posiciones que actuaron y no estan en la mesa. Una posicion esta en la
    mesa si ALGUN jugador la tiene puesta, este activo o no.

    MEDIDO, y por que importa: antes miraba solo los jugadores `active`, y eso
    daba UN falso positivo, `H_1203`. En esa mano el BB (Jarduan) postea y
    llama tres calles con `active: false`, y el detector lo decia ausente de la
    mesa.

    Por que el filtro de `active` no vale aqui: `active` NO significa «sigue
    en la mano». Medido sobre las 1258: hay **4991** jugadores con
    `active: true` que.foldan. Es decir, la bandera dice «se sento a jugar»,
    no «esta en el bote». Un detector que la lea como «esta en la mesa» no
    mide lo que dice medir, y un detector que no mide lo que dice medir no se
    puede usar para decidir.

    Lo que si distingue a los sentados de verdad es que NO tienen acciones, y
    eso lo mide otro sitio: de los 21 jugadores con `pos` y `active: false` en
    toda la base, solo uno tiene acciones, y es el BB de `H_1203`.
    """
    en_la_mesa = {p.get('pos') for p in (hand.get('players') or [])
                  if p.get('pos')}
    return sorted({a.get('pos') for _s, a in todas_las_acciones(hand)
                   if a.get('pos') and a.get('pos') not in en_la_mesa})


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
    citados = {p for p in activos
               if p and re.search(r'\b%s\b' % re.escape(p), texto)}
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


def patron_bb_sin_respuesta(hand):
    """La REGLA ESTRUCTURAL historica: el preflop se cierra con una subida de
    alguien que no es el BB. Devuelve 652 sobre la base completa.

    Se llama asi, y no `sin_respuesta_bb`, porque NO mide ausencias: mide una
    forma. Que el BB respondiera o no es otra pregunta, y la contesta
    `ausencia_respuesta_bb`.

    Mantenida aparte porque es la cifra que el proyecto publico, y porque
    revisar el historico exige poder reproducir el numero que se publico.
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
        sub = 'el BB responde con %s' % despues[0].get('action')
    elif any(a.get('action') == 'f' and a.get('pos') == 'BB' for a in acc):
        sub = 'el BB ya habia FOLDEADO antes de esa subida'
    elif not bb:
        sub = 'el BB no tiene NINGUNA entrada preflop'
    else:
        sub = 'el BB NO ACTUA tras la subida'
    return 'preflop cierra con subida de %s (%s) -> %s' % (
        acc[ultimo].get('pos'), acc[ultimo].get('amount'), sub)


def ausencia_respuesta_bb(hand):
    """AUSENCIA REAL: el BB estaba en la mesa y no hizo nada tras la subida.

    Devuelve `None` cuando NO hay ausencia. Es la distincion que review
    revision_2 §2 pide y que la primera version no hacia: la funcion
    devolvia un texto no vacio tambien cuando el BB habia respondido, y
    `auditar()` registra cualquier retorno verdadero. O sea: registraba como
    hallazgo casos en los que su propio mensaje decia "no falta nada". Que
    `--validar` reprodujera 652 confirmaba que reproducia un contador, no que
    identificara ausencias.

    Sobre la base completa: 23 ausencias de 1280. Las 652 son el patron.
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
    # el BB no es el que subio
    if acc[ultimo].get('pos') == 'BB':
        return None
    # respondio despues
    if any(a.get('pos') == 'BB' for a in acc[ultimo + 1:]):
        return None
    # ya estaba fuera de la mano
    if any(a.get('action') == 'f' and a.get('pos') == 'BB' for a in acc):
        return None
    if not bb:
        return 'el BB no tiene NINGUNA entrada preflop'
    return 'el BB NO ACTUA tras la subida de %s (%s)' % (
        acc[ultimo].get('pos'), acc[ultimo].get('amount'))


# Compatibilidad: el nombre que se usaba antes. Se mantiene para que las
# referencias viejas no se rompan, y avisa de que la metrica que promises es
# la otra.
sin_respuesta_bb = patron_bb_sin_respuesta


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
    ('INACTIVO_QUE_ACTUA', 'jugador marcado ausente que tiene acciones',
     inactivo_que_actua, 'contradiccion'),
    ('ACTIVO_SIN_POSICION', 'jugador activo sin posicion asignada',
     activo_sin_posicion, 'formato'),
    ('ACTIVO_SIN_ACCION', 'activo que no actua en ninguna calle ni foldea ni '
     'va all-in', activo_sin_accion, 'ausencia'),
    ('ACTIVO_SIN_ACCION_CALLE', 'activo que desaparece en una calle con '
     'acciones', activo_sin_accion_calle, 'ausencia'),
    ('SIN_ALLIN', 'el campo allin falta o no es una lista',
     sin_allin, 'ausencia'),
    ('AUSENCIA_RESPUESTA_BB', 'el BB esta en la mesa y no responde',
     ausencia_respuesta_bb, 'ausencia'),
)

# Las metricas que NO son clases, porque miden una forma y no un defecto. Se
# calculan aparte y se publican con su propio nombre, para que el numero
# historico que se publico 652 veces no se confunda con el de ausencias.
METRICAS_NO_FALLA = (
    ('PATRON_BB_SIN_RESPUESTA',
     'el preflop cierra con una subida de un no-BB (forma, no defecto)',
     patron_bb_sin_respuesta),
    ('INACTIVO_CON_POSICION',
     'jugador inactivo que conserva posicion (forma; solo es defecto si actua)',
     inactivo_con_posicion),
)

SOLO_PATRON = 'PATRON_BB_SIN_RESPUESTA'


def auditar(manos):
    """Clases (defectos) y metricas de forma, en dos diccionarios separados.

    No se mezclan, y no por limpieza: review revision_2 §2. La version
    anterior tenia el patron del BB como una clase mas, de modo que el
    informe decia "486 casos" cuando 481 de esos no eran defectos. Un
    instrumento que reporta como hallazgo algo que su propio texto describe
    como "no falta nada" no se puede usar para decidir nada.
    """
    hallazgo = {c: [] for c, _e, _f, _n in CLASES}
    metricas = {c: [] for c, _e, _f in METRICAS_NO_FALLA}
    for h in manos:
        for clave, _e, fn, _n in CLASES:
            try:
                r = fn(h)
            except Exception as exc:                    # noqa: BLE001
                r = 'la comprobacion fallo: %r' % (exc,)
            if r:
                hallazgo[clave].append((h.get('hand_id'), r))
        for clave, _e, fn in METRICAS_NO_FALLA:
            if fn(h):
                metricas[clave].append(h.get('hand_id'))
    return hallazgo, metricas


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
    hall, mets = auditar(manos)
    print()
    print('%-26s %7s %9s  %s' % ('METRICA', 'DETECTA', 'PUBLICADO', 'VEREDICTO'))
    print('-' * 78)
    irrecuperables = []
    todo = dict((c, len(hall[c])) for c in hall)
    todo.update((c, len(mets[c])) for c in mets)
    for clave in sorted(REFERENCIA):
        publicada, reproducible = REFERENCIA[clave]
        n = todo.get(clave, 0)
        if reproducible:
            veredicto = 'reproduce' if n == publicada else 'DESVIO'
            if n != publicada:
                irrecuperables.append(clave)
        else:
            veredicto = ('NO SE REPRODUCE (cifra sin codigo que la produzca)'
                         if n != publicada
                         else 'coincide por casualidad, sin codigo de origen')
        print('%-26s %7d %9d  %s' % (clave, n, publicada, veredicto))
    print()
    print('  el patron y la AUSENCIA son dos metricas distintas:')
    print('    %-22s %d  (forma: el preflop cierra con una subida de un no-BB)'
          % ('PATRON_BB_SIN_RESPUESTA', len(mets['PATRON_BB_SIN_RESPUESTA'])))
    print('    %-22s %d  (defecto: el BB esta y no hace nada)'
          % ('AUSENCIA_RESPUESTA_BB',
             len(hall['AUSENCIA_RESPUESTA_BB'])))
    print()
    print('  sin cifra publicada (solo informativo):')
    for clave, _e, _f, naturaleza in CLASES:
        if clave not in REFERENCIA:
            print('    %-24s %5d  %s' % (clave, len(hall[clave]), naturaleza))
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
    ap.add_argument('--db', default=DB_PATH,
                    help='base a auditar (por defecto data/hands_db.jsonl)')
    ap.add_argument('--json', dest='json_out',
                    help='volcar el resultado en JSON')
    ap.add_argument('--validar', action='store_true',
                    help='contrastar los detectores con las cifras conocidas')
    args = ap.parse_args(argv)

    if args.validar:
        return validar()

    limite = num(args.hasta)
    todas = cargar(args.db)
    rango = [h for h in todas if limite is None
             or (num(h['hand_id']) or 0) <= limite]
    fuera = [h['hand_id'] for h in todas if limite is not None
             and (num(h['hand_id']) or 0) > limite]

    print('=' * 78)
    print('AUDITORIA DE %s   ·   H_0001..%s' % (args.db, args.hasta))
    print('=' * 78)
    print('manos en el rango : %d' % len(rango))
    print('fuera del rango   : %d  (%s .. %s)'
          % (len(fuera), fuera[0] if fuera else '-', fuera[-1] if fuera else '-'))
    print('total en la base  : %d' % len(todas))

    hall, mets = auditar(rango)
    print()
    print('CLASES (defectos).  Cada caso necesita una decision.')
    print()
    print('%-24s %7s  %s' % ('CLASE', 'CASOS', 'NATURALEZA'))
    print('-' * 78)
    for clave, etiqueta, _fn, naturaleza in CLASES:
        n = len(hall[clave])
        print('%-24s %7d  %s' % (clave, n, naturaleza))

    print()
    print('METRICAS (formas).  No son defectos: no requieren decision.')
    print()
    print('%-24s %7s  %s' % ('METRICA', 'CASOS', 'QUE MIDE'))
    print('-' * 78)
    for clave, etiqueta, _fn in METRICAS_NO_FALLA:
        print('%-24s %7d  %s' % (clave, len(mets[clave]), etiqueta))
    print()
    print('  Ojo: PATRON_BB_SIN_RESPUESTA y AUSENCIA_RESPUESTA_BB no son la')
    print('  misma cifra. La primera es una forma del preflop; la segunda, un')
    print('  defecto. Confundirlas fue lo que hizo leer 652 como si fueran 652')
    print('  manos sin respuesta del BB. Ver DOCS/DEFECTO_652.md.')

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
    for clave, etiqueta, _fn in METRICAS_NO_FALLA:
        if not mets[clave]:
            continue
        print()
        print('--- %s  (%d) ---  %s' % (clave, len(mets[clave]), etiqueta))
        print('    ids: %s' % ', '.join(mets[clave][:60]))
        if len(mets[clave]) > 60:
            print('    ... y %d mas' % (len(mets[clave]) - 60))

    if args.json_out:
        with open(args.json_out, 'w', encoding='utf-8') as f:
            json.dump({'rango': {'desde': 'H_0001', 'hasta': args.hasta,
                                 'manos': len(rango)},
                       'clases': {k: [{'hand_id': h, 'detalle': d}
                                      for h, d in v]
                                  for k, v in hall.items() if v},
                       'metricas_no_falla': {k: v for k, v in mets.items()
                                             if v}},
                      f, indent=2, ensure_ascii=False)
        print()
        print('volcado -> %s' % args.json_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())