# -*- coding: utf-8 -*-
"""Lista de trabajo del saneamiento: que mano mirar, por que, y que decidir.

    python tools/lista_saneamiento.py                     # toda la base
    python tools/lista_saneamiento.py --lote LOTE_MECANICO
    python tools/lista_saneamiento.py --json salida.json
    python tools/lista_saneamiento.py --validar           # autocomprobacion

Que es, y por que no es `auditar_rango.py`
-------------------------------------------
`auditar_rango.py` responde **que hay**. Este responde **en que orden se
arregla y por que**. Son preguntas distintas y mezclarlas produce el modo de
fallar que ya se ha dado dos veces en este repositorio: una lista de 73
defectos que se lee como 73 decisiones y son una, y una cifra total que se
lee como "hay 73 problemas" sin decir cuantos son de verdad.

Tres reglas que este script impone, y que por eso estan escritas aqui y no
en un documento:

1. **Solo lee.** No abre `hands_db.jsonl` en modo escritura en ninguna
   rama, ni aqui ni por accidente. El saneamiento lo hace el mantenedor a
   mano, en `hand_editor.py`. Un script que propone correcciones y otro que
   las aplica son dos herramientas, y la segunda no existe todavia. Si
   existiera, este no seria el sitio para decidir cuales.

2. **Agrupa por decision, no por clase.** Una clase de 73 casos puede ser
   una sola decision (un campo que el recorder dejo de escribir en un tramo)
   o 73 (cada mano con su propia lectura). El numero de la clase no lo dice;
   el contenido si. Por eso los LOTES se declaran a mano con su
   justificacion, y `--validar` comprueba que las cifras del lote siguen
   cuadrando con las de `auditar_rango.py` — si el lote y el detector
   discrepan, el lote esta mal y hay que rehacerlo.

3. **Un lote sin manos NO se borra, se declara.** Si un lote se queda
   vacio porque su defecto se corrigio, sigue en la tabla con 0. Sacarlo
   borraria la evidencia de que se corrigio, y volveria a salir la proxima
   vez que se contara.

Los tres lotes
--------------
MECANICO  El valor correcto lo determina el dato. No hay lectura: hay una
          sola forma de escribirlo y se comprueba. Ejemplo: una accion de
          una posicion que no esta en la mesa — o no estaba, o el nombre
          esta mal.

LECTURA_DOBLE  El dato admite dos lecturas defendibles y elegirlas es
          criterio humano. Ejemplo: `WINNER_FOLDEO` puede ser un `winner`
          mal escrito o un fold mal escrito, y el dato no dice cual. Aqui
          este script solo presenta las dos.

LOTE  Una sola decision para muchas manos. Ejemplo: `SIN_ALLIN` son 73
          manos CONTIGUAS, `H_0001`..`H_0073`, sin el campo. No son 73
          problemas, es un tramo del que el recorder dejo de escribir una
          clave, y se arregla con una decision y una pasada.

El alcance por defecto es toda la base, y no `H_1014` como
`auditar_rango.py`. La revision manual llego a `H_1282` y el rango auditado
se quedo en `H_1014`: 267 manos se corrigieron sin que ningun detector las
mirase. Medido, no supuesto: `H_1203` trae una `ACCION_FANTASMA`, `H_1063`
y `H_1241` un `AUSENCIA_RESPUESTA_BB` y `H_1196` la unica violacion de
CM-004. Las cuatro son de las 267.
"""
import argparse
import collections
import hashlib
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from motor import learn  # noqa: E402
import auditar_rango as AR  # noqa: E402

DB_REL = 'data/hands_db.jsonl'
DB_PATH = os.path.join(ROOT, *DB_REL.split('/'))

# ---------------------------------------------------------------------------
# LOTES
# ---------------------------------------------------------------------------
# Cada lote declara: las clases que agrupa, de que tipo es, por que, y que
# hay que mirar en la mano para decidirlo. `clases` es lo que se contrasta
# con `auditar_rango.py` en `--validar`; si una clase aparece en dos lotes, la
# lista se solapa y el recuento por clase sale mal. Eso tambien se comprueba.

MECANICO = 'MECANICO'
LECTURA_DOBLE = 'LECTURA_DOBLE'
LOTE = 'LOTE'
LIMPIO = 'LIMPIO'


class Lote(object):
    def __init__(self, clave, tipo, clases, titulo, decision, mirar):
        self.clave = clave
        self.tipo = tipo
        self.clases = tuple(clases)
        self.titulo = titulo
        self.decision = decision
        self.mirar = mirar


LOTES = (
    Lote(
        'FANTASMA',
        MECANICO,
        ['ACCION_FANTASMA'],
        'accion de una posicion que no esta en la mesa',
        'La accion no puede estar: esa posicion no existe en esta mano. O el '
        'nombre de la posicion esta mal, o la accion es de otro jugador, o '
        'la accion sobra. SE DECIDE MIRANDO QUIEN HAY EN LA MESA.',
        ['players[].pos de todos, con name y active',
         'la accion fantasma: que calle, que indice, que pos, que importe'],
    ),
    Lote(
        'SIN_RESPUESTA_BB',
        MECANICO,
        ['AUSENCIA_RESPUESTA_BB'],
        'el BB esta en la mesa y no responde a una subida viva',
        'El BB tiene entrada, no vuelve a actuar, y el preflop se cierra con '
        'una subida viva de otro. O falta su entrada, o falta su respuesta, o '
        'el preflop se cerro antes de tiempo. SE DECIDE MIRANDO LA ULTIMA '
        'ACCION DEL PREFLOP.',
        ['la entrada del BB: que tiene y que le falta',
         'la subida viva que se queda sin respuesta, y de quien es',
         'que hace el BB en el resto de calles, si hace algo'],
    ),
    Lote(
        'IMPORTE_SUBIDA',
        LOTE,
        ['IMPORTE_SUBIDA'],
        'aperturas grabadas como subida que no superan la ciega',
        'Una sola forma, repetida: el preflop arranca con `r` por un importe '
        'que NO supera la ciega grande. MEDIDO: el suelo de 1.0 es correcto, '
        'porque la ciega grabada en la base es 1.0 en 915 manos, 0.5 en 6 y '
        '2.0 en 1 —y ninguna de las 30 de este lote tiene ciega grabada—. '
        'O sea que no es el detector el que se equivoca: `r 1.0` de salida es '
        'un limpeo con el codigo de una subida.\n'
        'LA DECISION ES SI `r` PASA A `c`, Y TIENE CONSECUENCIA: cambia lo que '
        'el preflop lee como apertura, y con ella las frecuencias de `open`, '
        '`3bet` y `squeeze` que salen de ahi.',
        ['la accion marcada: que calle, que posicion, que importe',
         'que hay antes (solo folds, o ya habia subida)',
         'la primera accion real de la mano, para ver si es la apertura'],
    ),
    Lote(
        'ALLIN_AUSENTE',
        LOTE,
        ['SIN_ALLIN'],
        'el campo `allin` falta en un tramo contiguo',
        'MEDIDO: las 73 son `H_0001`..`H_0073`, contiguas, y ninguna mas. No '
        'son 73 problemas, es un tramo en el que el recorder no escribio la '
        'clave. El campo es una lista de ids de jugador (`p1`..`p5`, `hero`); '
        'en las 1185 manos que si lo tienen, 984 valen `[]`.\n'
        'UNA decision, no 73: poner `allin: []` en el tramo SI nadie se fue '
        'all-in, y ponerlo con contenido si alguno lo estaba. Y para saberlo '
        'hace falta MIRAR la mano, porque del dato no sale: hay que buscar un '
        'stack a 0 o una subida al maximo.',
        ['stack de cada jugador: si alguno esta a 0, hubo all-in',
         'la ultima accion de cada calle: si alguien_raiseo al maximo',
         'final_pot, para contrastar'],
    ),
    Lote(
        'GANADOR_Y_FOLDEO',
        LECTURA_DOBLE,
        ['WINNER_FOLDEO'],
        '`winner` incluye a alguien que foldeo',
        'El dato se contradice y no dice cual de las dos mitades es la mala. '
        'LECTURA A: el `winner` esta mal y el fold esta bien — el nombre se '
        'piso. LECTURA B: el fold esta mal y el `winner` esta bien — quien '
        'figura.foldeo en realidad no se fue.\n'
        'La diferencia no es academica: A cambia el resultado de la mano y B '
        'cambia el PreflopStats. Se mira la mano entera.',
        ['quien figura en winner, y su pos',
         'la accion de ese jugador en cada calle: cuando y como folteo',
         'quien quedo activo al final'],
    ),
    Lote(
        'SHOWDOWN',
        LECTURA_DOBLE,
        ['SHOWDOWN_SIN_WINNER'],
        'el showdown cita a quien no gano',
        'El campo `showdown` nombra a alguien que no esta en `winner`. '
        'LECTURA A: el showdown cita a mas gente de la que gano — es un '
        'desglose de lo que se vio, no una declaracion del ganador, y es '
        'legitimo. LECTURA B: el `winner` esta incompleto y falta un ganador.\n'
        'Se resuelve mirando si el showdown esta describiendo la mesa entera '
        'o pretendiendo cerrar el reparto.',
        ['`winner` completo',
         '`showdown` completo, y quienes nombra',
         'la comparacion: quienes aparecen en showdown y no en winner'],
    ),
    Lote(
        'ORDEN_CIEGA_BB',
        LECTURA_DOBLE,
        ['CM-004'],
        'una `BB b` que el motor no reconoce como ciega',
        'La unica de este tipo que queda es `H_1196`, y tiene DOS lecturas '
        'defendibles.\n'
        'LECTURA A — EL DATO ESTA MAL: la subida del BB se grabo como `b` y '
        'deberia ser `r`. `_es_ciega_bb` ya avisa: la regla exige `act == '
        "'b'\", asi que una subida bien grabada NUNCA se lee como ciega. Si la "
        'GUI escribe las subidas del BB como `b`, esa es la forma de CM-004.\n'
        "LECTURA B — EL GUARD ES MAS ANCHO QUE EL DEFECTO: la regla de CM-004 "
        "era «una `BB b` tardía SIN POSTING PREVIO», y aqui el BB ya posteo en "
        'el indice 0.\n'
        'Lo que NO es opcion: relajar el invariante para que el test pase. '
        'Eso es lo que este canal manual existe para evitar.',
        ['la secuencia completa del preflop, con indices',
         'el posting del BB: indice y importe',
         'la accion marcada: por que la considera tardia'],
    ),
    # (1) Las que hoy dan 0. Se declaran con 0 y se quedan declaradas.
    Lote(
        'LIMPIO',
        LIMPIO,
        ['ACCION_DESPUES_FOLD', 'FOLD_TRAS_APUESTA', 'POSICION_DUPLICADA',
         'CARTAS_ILEGALES', 'BOARD_ILLEGAL', 'CM-002', 'WINNER_VACIO',
         'INACTIVO_QUE_ACTUA'],
        'clases que hoy dan cero, declaradas para que se vean',
        'Estas clases dan 0 casos en las 1258 manos. Se declaran igualmente, '
        'y el motivo es concreto: un lote que se queda vacio porque su '
        'defecto se corrigio se queda DECLARADO, y borrar la fila borraria '
        'la evidencia de que se corrigio — y la proxima vez que se cuente, '
        'volveria a salir como si fuera nuevo.\n'
        'Que esten a 0 es una MEDICION de hoy, no una garantia. La razon por '
        'la que 30 `IMPORTE_SUBIDA` escondian un unico patron es la misma '
        'que hace que un 0 pueda esconder otra cosa: por eso estan en la '
        'tabla y no en un documento que nadie relee.\n'
        'Y `INACTIVO_QUE_ACTUA` merece su propia linea porque SE HA VISTO. Daba '
        '1 —`H_1203`— y no lolooked porque el detector que la rozaba, '
        '`accion_fantasma`, lo hacia por el motivo equivocado. Al arreglar '
        'ese, el defecto desaparecio del informe sin haberse corregido: un '
        'agujero que se esconde no como error sino como silencio.',
        [],
    ),
)

# Informativo: no son defecto, pero se miraron y quedan asi. Se listan para
# que "14" sea un numero que alguien possa revisar, y no una cifra sin nombre.
GANADOR_MULTIPLE = 'GANADOR_MULTIPLE'


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

def cargar():
    return {h['hand_id']: h for h in AR.cargar()}


# Lo que este fichero tiene PROHIBIDO hacer, tal cual. Se lee en voz alta en
# `validar` porque la regla es de las que se respetan por estar escritas.
#
# Y la lista es CORTA a proposito: solo operaciones que sustituyen un fichero
# entero. No esta `write` ni `truncate` porque este fichero escribe —tiene que
# escribir, para el volcado `--json`— y buscar la palabra suelta daria un
# aviso sobre lo que no importa. Un guard que avisa de cosas legitimas
# entrena a ignorar avisos, y ese es el peor modo de fallo de un guard.
ESCRITURAS_PROHIBIDAS = (
    ('os.' + 'replace', 'escritura atomica: es de `hand_editor.py`'),
    ('os.' + 'rename', 'renombrar ficheros'),
    ('shutil.' + 'move', 'mover ficheros'),
    ('shutil.' + 'copyfile', 'copiar ficheros'),
    ('Path(' + ').write_', 'escritura de pathlib'),
)


def violaciones_de_escritura(propio):
    """Que escrituras prohibidas tiene este codigo. Devuelve una lista.

    Va aparte de `validar` y recibe el TEXTO como parametro, por una razon
    concreta: para poder meter una violation a proposito y comprobar que se
    detecta. Un chequeo que solo se puede ejecutar contra el fichero real solo
    se puede ver pasar, y un chequeo que solo se ve pasar no se sabe si
    funciona o si esta muerto.

    Lo que se busca NO es la palabra `write` en cualquier sitio: este fichero
    escribe en disco, y tiene que, para el volcado `--json`. Lo que no puede
    es escribir en la BASE. Por eso el criterio es la RUTA, no el modo: se
    busca un `open` cuya ruta sea la base, y una sustitucion de fichero
    entero.

    Y las needles van montadas por trozos porque el chequeo no puede
    dispararse a si mismo: escritas enteras, se encontrarian en su propia
    linea y fallarian siempre. Un guard que solo puede fallar es ruido.
    """
    fallos = []

    # (a) un `open` cuya ruta sea la base, en cualquier modo
    if re.search(r"open\s*\(\s*[^)\n]*\b(DB_PATH|DB_REL)\b", propio):
        fallos.append('abre la base con `open`. Para leerla esta '
                      '`auditar_rango.cargar()`, que la abre en lectura.')
    if re.search(r"open\s*\(\s*['\"][^'\"]*hands_db", propio):
        fallos.append('abre hands_db.jsonl por su nombre literal.')

    # (b) sustituir el fichero entero.
    for _op, _por_que in ESCRITURAS_PROHIBIDAS:
        if _op in propio:
            fallos.append('usa `%s`: %s.' % (_op, _por_que))
    return fallos


def sha_de(path=DB_PATH):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def ganador_multiple(hand):
    """Los ids que ganan, si son mas de uno. Devuelve None si no."""
    w = hand.get('winner') or []
    return [str(x) for x in w] if len(w) > 1 else None


def construir(manos, hasta=None):
    """La lista de trabajo. Devuelve (lotes, multiples, resumen).

    `lotes` es una lista de dicts, uno por lote, con las manos que le
    tocaron. `multiples` son las manos con 2+ ganadores, para revisarlas sin
    que el script opine si estan bien o mal.
    """
    if hasta is not None:
        limite = AR.num(hasta)
        seleccion = {k: v for k, v in manos.items()
                     if limite is None or (AR.num(k) or 0) <= limite}
    else:
        seleccion = manos

    hall, _mets = AR.auditar(list(seleccion.values()))

    por_clase = {}
    for clave, casos in hall.items():
        por_clase[clave] = casos

    salida = []
    for lote in LOTES:
        casos = []
        for clave in lote.clases:
            for hid, detalle in por_clase.get(clave, ()):
                casos.append({'hand_id': hid, 'clase': clave,
                              'detalle': detalle,
                              'mano': _ficha(seleccion[hid])})
        casos.sort(key=lambda c: AR.num(c['hand_id']) or 0)
        salida.append({
            'clave': lote.clave,
            'tipo': lote.tipo,
            'titulo': lote.titulo,
            'decision': lote.decision,
            'mirar': lote.mirar,
            'manos': casos,
            'n': len(casos),
        })

    multiples = []
    for hid in sorted(seleccion, key=lambda k: AR.num(k) or 0):
        g = ganador_multiple(seleccion[hid])
        if g:
            multiples.append({'hand_id': hid, 'winner': g,
                              'mano': _ficha(seleccion[hid])})

    resumen = {
        'db_commit': learn.HANDS_DB_COMMIT,
        'db_sha256': sha_de(),
        'manos': len(seleccion),
        'hasta': hasta or 'todas',
        'por_clase': {k: len(v) for k, v in sorted(por_clase.items()) if v},
        'lotes': {l.clave: l.tipo for l in LOTES},
        'ganadores_multiples': len(multiples),
    }
    return salida, multiples, resumen


def _ficha(hand):
    """Lo minimo para mirar la mano en el editor, sin volcar las 1258 lineas."""
    st = hand.get('streets') or {}
    return {
        'fecha': (hand.get('date') or '')[:19],
        'boton': hand.get('btn_player'),
        'jugadores': ['%s/%s%s' % (p.get('pos'), p.get('name'),
                                  '' if p.get('active') else ' (fold)')
                      for p in (hand.get('players') or [])],
        'preflop': _acciones(st.get('preflop')),
        'flop': _acciones(st.get('flop')),
        'turn': _acciones(st.get('turn')),
        'river': _acciones(st.get('river')),
        'winner': hand.get('winner'),
        'showdown': hand.get('showdown'),
        'allin': hand.get('allin', '<AUSENTE>'),
    }


def _acciones(calle):
    if not calle:
        return []
    return ['%d:%s %s %s' % (i, a.get('pos'), a.get('action'), a.get('amount'))
            for i, a in enumerate(calle.get('actions') or [])]


# ---------------------------------------------------------------------------
# Autocomprobacion
# ---------------------------------------------------------------------------

def validar():
    """Que los lotes cuadren con los detectores, y que el script no escriba.

    Tres cosas, y las tres por el mismo motivo: un instrumento de saneamiento
    que no se contrasta puede quedarse en silencio. En silencio significa
    «no hay nada que arreglar», que es la peor respuesta posible.

    1. Cada clase aparece en EXACTAMENTE un lote. Si aparece en dos, el
       recuento de la clase sale mal y el trabajo se duplica.
    2. Cada lote reproduce la cifra de `auditar_rango.py` para sus clases.
    3. Este fichero no abre la base en modo escritura. Se comprueba leyendo
       su propio codigo, porque un `open(..., 'w')` en una rama que no se ha
       ejecutado es justo el que no se nota.
    """
    fallos = []

    # (1) cada clase en un solo lote
    visto = collections.Counter()
    for lote in LOTES:
        for c in lote.clases:
            visto[c] += 1
    for c, n in sorted(visto.items()):
        if n != 1:
            fallos.append('la clase %s esta en %d lotes, deberia estar en 1'
                          % (c, n))
    clases_auditadas = {c for c, _e, _f, _n in AR.CLASES}
    sin_lote = clases_auditadas - set(visto)
    if sin_lote:
        fallos.append(
            'estas clases de `auditar_rango.py` no estan en ningun lote: %s\n'
            'Si dan 0 casos, ponelas en un lote con 0 antes que dejarlas '
            'fuera: un lote vacio se ve, una clase sin lote no.'
            % ', '.join(sorted(sin_lote)))

    # (2) las cifras del lote son las del detector
    manos = cargar()
    hall, _m = AR.auditar(list(manos.values()))
    for lote in LOTES:
        esperado = sum(len(hall.get(c, ())) for c in lote.clases)
        if esperado != len(hall.get(lote.clases[0], ())) and len(lote.clases) == 1:
            fallos.append('el lote %s no cuadra' % lote.clave)
    total_lotes = sum(len(hall.get(c, ())) for lote in LOTES
                      for c in lote.clases)
    total_clases = sum(len(v) for v in hall.values())
    if total_lotes != total_clases:
        fallos.append(
            'los lotes suman %d casos y los detectores %d. Cada caso tiene '
            'que estar en un lote y solo en uno.' % (total_lotes, total_clases))

    # (3) este fichero no escribe LA BASE
    propio = io.open(os.path.abspath(__file__), encoding='utf-8').read()
    fallos.extend(violaciones_de_escritura(propio))

    print('=' * 74)
    print('AUTOCOMPROBACION DE lista_saneamiento.py')
    print('=' * 74)
    print('  base            : %d manos' % len(manos))
    print('  clases con caso : %d' % len([k for k, v in hall.items() if v]))
    print('  lotes           : %d' % len(LOTES))
    print()
    if fallos:
        print('FALLOS')
        for f in fallos:
            print('  - %s' % f)
        print()
        print('NO ES FIABLE. No se usa para decidir.')
        return 1
    print('OK. Los lotes cubren cada clase una vez, las cifras coinciden con')
    print('`auditar_rango.py`, y este fichero no escribe.')
    return 0


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------

TIPOS_ORDEN = (MECANICO, LOTE, LECTURA_DOBLE)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--hasta', default=None,
                    help='ultimo hand_id (por defecto: toda la base)')
    ap.add_argument('--lote', dest='solo_lote',
                    help='mostrar solo un lote')
    ap.add_argument('--json', dest='json_out',
                    help='volcar el resultado en JSON')
    ap.add_argument('--validar', action='store_true',
                    help='contrastar lotes, cifras y no-escritura')
    ap.add_argument('--detalle', type=int, default=0,
                    help='fichas completas de las primeras N manos del lote')
    args = ap.parse_args(argv)

    if args.validar:
        return validar()

    manos = cargar()
    lotes, multiples, resumen = construir(manos, args.hasta)

    print('=' * 78)
    print('LISTA DE TRABAJO DEL SANEAMIENTO   ·   hands_db.jsonl')
    print('=' * 78)
    print('manos en el alcance : %d   (%s)' % (resumen['manos'], resumen['hasta']))
    print('commit declarado    : %s' % resumen['db_commit'])
    print('sha256 en disco     : %s' % resumen['db_sha256'][:16])
    if learn.HANDS_DB_SHA256 != resumen['db_sha256']:
        print()
        print('  ! el sha del disco NO es el declarado. Hay cambios sin '
              'commitear, o el manifiesto esta desfasado.')

    print()
    print('=' * 78)
    print('LOTES, por lo que cuesta decidir cada uno')
    print('=' * 78)
    print('%-18s %-14s %6s  %s' % ('LOTE', 'TIPO', 'MANOS', 'QUE ES'))
    print('-' * 78)
    ordenados = sorted(lotes, key=lambda l: (TIPOS_ORDEN.index(l['tipo'])
                                              if l['tipo'] in TIPOS_ORDEN else 9,
                                              -l['n'], l['clave']))
    for l in ordenados:
        print('%-18s %-14s %6d  %s' % (l['clave'], l['tipo'], l['n'],
                                       l['titulo']))
    print()
    print('  MECANICO     el dato determina el valor. No hay lectura.')
    print('  LOTE         una decision para muchas manos.')
    print('  LECTURA_DOBLE  dos lecturas defendibles; elige una persona.')

    for l in ordenados:
        if args.solo_lote and l['clave'] != args.solo_lote:
            continue
        print()
        print('=' * 78)
        print('%s   (%s)   %d manos' % (l['clave'], l['tipo'], l['n']))
        print('=' * 78)
        print(l['titulo'])
        print()
        for linea in l['decision'].split('\n'):
            print('  ' + linea)
        print()
        print('  QUE MIRAR EN LA MANO:')
        for q in l['mirar']:
            print('    - %s' % q)
        if not l['manos']:
            print()
            print('  Sin manos. El lote se queda declarado y vacio a proposito:')
            print('  borrar la fila borraria la evidencia de que se corrigio.')
            continue
        print()
        ids = [c['hand_id'] for c in l['manos']]
        print('  ids: %s' % ', '.join(ids[:40]))
        if len(ids) > 40:
            print('       ... y %d mas' % (len(ids) - 40))
        for c in l['manos'][:args.detalle]:
            print()
            print('  --- %s  [%s]' % (c['hand_id'], c['clase']))
            print('      %s' % c['detalle'])
            _imprimir_mano(c['mano'])

    print()
    print('=' * 78)
    print('GANADOR MULTIPLE   %d manos' % len(multiples))
    print('=' * 78)
    print('No es una clase de defecto: la revision bajo las de 2+ ganadores de')
    print('179 a 14 y estas son las que quedan. Se listan para que el numero sea')
    print('revisable, no para que este script opine si estan bien.')
    print()
    print('  ids: %s' % ', '.join(m['hand_id'] for m in multiples))

    if args.json_out:
        with open(args.json_out, 'w', encoding='utf-8') as f:
            json.dump({'resumen': resumen, 'lotes': lotes,
                       'ganadores_multiples': multiples},
                      f, indent=2, ensure_ascii=False)
        print()
        print('volcado -> %s' % args.json_out)
    return 0


def _imprimir_mano(ficha):
    print('      fecha      %s' % ficha['fecha'])
    print('      boton      %s' % ficha['boton'])
    print('      jugadores  %s' % ' | '.join(ficha['jugadores']))
    for calle in ('preflop', 'flop', 'turn', 'river'):
        if ficha[calle]:
            print('      %-10s %s' % (calle, '  '.join(ficha[calle])))
    print('      winner     %s' % (ficha['winner'],))
    print('      showdown   %s' % (ficha['showdown'],))
    print('      allin      %s' % (ficha['allin'],))


if __name__ == '__main__':
    sys.exit(main())
