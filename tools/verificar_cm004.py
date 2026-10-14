# -*- coding: utf-8 -*-
"""Manifiesto y verificacion de las correcciones A MANO de hands_db.jsonl.

    python tools/verificar_cm004.py

Que problema resuelve
--------------------
`data/hands_db.jsonl` se ha corregido a mano. Eso tiene un coste: una base
editada a mano no tiene quien la vuelva a hacer ni quien detecte que alguien
la vuelve a estropear. Este script es esa pieza. NO ESCRIBE NADA.

La regla vive en el motor, no aqui
----------------------------------
El defecto ES la discrepancia con el motor: `_es_ciega_bb` exige que no haya
accion voluntaria previa, y si una `BB b` no lo cumple, el motor la lee como
una subida. Una cuenta hecha aqui podria discrepar de `_es_ciega_bb` y
publicar un numero que el motor no sostiene. Por eso las funciones viven en
`motor/learn.py` y este script las importa.

Las tres secciones
------------------
  1. INVARIANTE. ¿Queda alguna mano en las 1280 en la que una `BB b` no pueda
     ser la ciega? Se espera 0.
  2. CLASIFICACION. Para cada mano editada respecto a la version COMPROMETIDA,
     que clase de cambio es: reetiquetado (una sola etiqueta `b` pasa a `r`) o
     reconstruccion (ademas se anade, borra o reordena alguna accion, o se
     cambia lo que hizo otro jugador). El script no juzga si una
     reconstruccion es correcta: la DECLARA y exige que este declarada.
  3. DECLARADAS. Las reconstrucciones y los cambios ajenos a CM-004, cada uno
     con su motivo y, si sigue pendiente, el valor recomendado.

Por que declarar es obligatoria
-------------------------------
Porque un instrumento que dice "todo correcto" delante de un cambio sin
explicar es PEOR que uno que dice "no lo se". Si alguien edita a mano una
septima reconstruccion y no la anade a este fichero, el script falla en vez de
dar luz verde.
"""
import hashlib
import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor import learn  # noqa: E402

DB_REL = 'data/hands_db.jsonl'
DB_PATH = os.path.join(ROOT, *DB_REL.split('/'))

# --------------------------------------------------------------------------
# Correcciones que NO son un simple reetiquetado.
#
# Las RECONSTRUCCIONES cambian el preflop mas alla de la etiqueta del BB: anaden
# o borran acciones, las reordenan, o cambian lo que hizo OTRO jugador. Eso es
# reconstruir el orden, que es justamente lo que CM-004 declaraba no
# inventable. Se declaran una por una porque cada una es una decision
# distinta y no hay una regla comun que las cubra.
#
# El guion corto es el sintoma: las seis tienen la misma firma, una `BB b` mal
# ordenada mas ALGO MAS. De ahi que no valga la regla de reetiquetado.
# --------------------------------------------------------------------------
RECONSTRUCCIONES = {
    'H_0039': {
        'que': "BB 'b' 6.0 -> 'r' 6.0, y se ANADE 'BB f' 0.0 al final",
        'motivo': "El fold anadido es la MISMA inferencia que aplico CM-003 "
                  "(preflop cerrado y el BB sin accion propia, luego folteo), "
                  "pero en una mano que CM-003 no cubria porque el BB si "
                  "tenia entrada. Es ADITIVA y sigue una regla que ya existe, "
                  "que es lo que la hace mas defendible que H_0067, pero sigue "
                  "sin original: nadie vio ocurrir ese fold.",
        'estado': 'APLICADO - requiere revisar la grabacion',
        'recomendado': None,
    },
    'H_0051': {
        'que': "SB 'r' 0.5 -> 'c' 1.0, BB 'b' 5.0 -> 'r' 5.0, y se ANADE "
               "'SB f' 0.0",
        'motivo': "El 'SB r 0.5' era una SUBIDA POR DEBAJO DE LA CIEGA, "
                  "imposible, y del mismo genero que CM-001 (un importe leido "
                  "mal): 0.5 no puede ser una subida cuando la ciega es 1.0. "
                  "Leerlo como llamada a 1.0 es la unica lectura coherente. "
                  "Pero eso cambia lo que hizo el SB, no solo la etiqueta del "
                  "BB, y anade un fold.",
        'estado': 'APLICADO - requiere revisar la grabacion',
        'recomendado': None,
    },
    'H_0067': {
        'que': "una unica llamada 'SB c 1.5' se parte en DOS: 'SB c 1.0' "
               "antes del BB y 'SB c 1.5' despues; ademas 'BB b' 2.5 -> 'r'",
        'motivo': "La mano tiene una sola llamada registrada del SB, a 1.5, y "
                  "la reconstruccion la convierte en dos, una a 1.0 que NO "
                  "estaba grabada. Inventa una accion y duplica un importe. Es "
                  "el mas fragil de los seis: el unico defecto real era el 'b' "
                  "del BB, y el resto es relleno.",
        'estado': 'APLICADO - requiere revisar la grabacion',
        'recomendado': None,
    },
    'H_0109': {
        'que': "SB 'r' 0.5 -> 'c' 0.5, BB 'b' 3.0 -> 'r' 3.0",
        'motivo': "Misma familia que H_0051: el 'SB r 0.5' era una subida "
                  "imposible por debajo de la ciega y se relee como llamada. "
                  "Aqui no se anade ninguna accion, que es lo que lo hace mas "
                  "defendible que H_0051.",
        'estado': 'APLICADO - requiere revisar la grabacion',
        'recomendado': None,
    },
    'H_0143': {
        'que': "CO 'r' 1.0 -> 'c' 1.0, BB 'b' 3.0 -> 'r' 3.0",
        'motivo': "La misma regla, con el limite mas fino: una subida a "
                  "EXACTAMENTE 1.0, la ciega nominal, sin que nadie haya "
                  "subido antes. No es imposible por regla, pero tampoco es una "
                  "apertura: se relee como limp.",
        'estado': 'APLICADO - requiere revisar la grabacion',
        'recomendado': None,
    },
    'H_0263': {
        'que': "se BORRA 'MP x' 0.0, se reordena el preflop, y 'BB b' 2.5 -> "
               "'r' 2.5",
        'motivo': "El 'MP x' estaba grabado despues de que el MP ya habia "
                  "foldeado en el indice 1: un check de un jugador que ya no "
                  "esta en la mano es una contradiccion real, y borrarlo esta "
                  "justificado. Reordenar el resto del preflop NO lo esta: eso "
                  "es reconstruir la secuencia.",
        'estado': 'APLICADO - requiere revisar la grabacion',
        'recomendado': None,
    },
}

# Manos cambiadas que NO son de CM-004.
CAMBIOS_QUE_NO_SON_CM004 = {
    'H_0350': {
        'que': "dos players con cards='-' en vez de ''",
        'motivo': "CM-002. El guion no es un codigo de carta: son las 2 unicas "
                  "apariciones de ese centinela en las 1280 manos, frente a "
                  "6085 usos de la cadena vacia. Normalizar el centinela NO es "
                  "reconstruir las cartas, que es lo que CM-002 prohibe.",
        'estado': 'APLICADO',
        'recomendado': None,
    },
    'H_0969': {
        'que': "se borra el 'BB f' final del turn; winner ['hero','p4'] pasa a "
               "['hero']",
        'motivo': "El 'BB f' va detras de su propia apuesta sin respuesta: es "
                  "imposible. Con la apuesta del turn sin llamada el BB se "
                  "lleva el bote, y el SB (p4) no puede figurar como ganador.",
        'estado': 'APLICADO',
        'recomendado': None,
    },
    'H_0970': {
        'que': "winner ['hero','p1','p4'] pasa a ['hero']",
        'motivo': "Preflop: el BB postea, el BTN foldea, el SB foldea. Todos "
                  "foldean hasta las ciegas. El defecto real es que p4 (BTN) "
                  "FOLDEA y figura como ganador. Pero el recorte aplicado quita "
                  "ADEMAS p1 (BB), que comparte el bote: cambia un error por "
                  "otro. De las 77 manos del mismo patron, H_0345 graba SB+BB y "
                  "H_1050 graba BB+SB.",
        'estado': 'PENDIENTE - no aplicar sin revisar la grabacion',
        'recomendado': ['hero', 'p1'],
    },
}

DECLARADAS = dict(RECONSTRUCCIONES)
DECLARADAS.update(CAMBIOS_QUE_NO_SON_CM004)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def leer_texto(texto):
    return [json.loads(l) for l in texto.splitlines() if l.strip()]


def de_committed():
    """La version COMPROMETIDA. La regla se deriva contra ella: derivarla
    contra la copia de trabajo daria 0 y no comprobaria nada."""
    crudo = subprocess.run(['git', 'show', 'HEAD:%s' % DB_REL],
                           cwd=ROOT, capture_output=True)
    if crudo.returncode != 0:
        return None
    return leer_texto(crudo.stdout.decode('utf-8'))


def indices_cm004(manos):
    """hand_id -> [(indice, importe)] de las `BB b` mal ordenadas."""
    sel = {}
    for h in manos:
        for i, importe, causa in learn.entradas_bb_rechazadas(h):
            if causa == learn.CAUSA_ORDEN:
                sel.setdefault(h.get('hand_id'), []).append((i, importe))
    return sel


def solo_reetiquetado(antes, ahora, indices):
    """True si lo unico que cambio fueron las etiquetas `b` a `r` indicadas."""
    ac = ((antes.get('streets') or {}).get('preflop') or {}).get('actions') or []
    aa = ((ahora.get('streets') or {}).get('preflop') or {}).get('actions') or []
    if len(ac) != len(aa):
        return False
    cambiados = {i for i, (x, y) in enumerate(zip(ac, aa))
                 if canon(x) != canon(y)}
    esperados = {i for i, _imp in indices}
    if cambiados != esperados:
        return False
    return all(ac[i].get('action') == 'b' and aa[i].get('action') == 'r'
               and canon(dict(ac[i], action='r')) == canon(aa[i])
               for i in esperados)


def seccion(t):
    print()
    print('=' * 76)
    print(t)
    print('=' * 76)


def envolver(texto, ancho=68):
    palabras, linea, out = texto.split(), '', []
    for p in palabras:
        if len(linea) + len(p) + 1 > ancho:
            out.append(linea)
            linea = p
        else:
            linea = (linea + ' ' + p).strip()
    if linea:
        out.append(linea)
    return out


def main():
    sha_antes = sha256(DB_PATH)
    fallo = []

    trabajo = leer_texto(io.open(DB_PATH, encoding='utf-8').read())
    comprometida = de_committed()
    if comprometida is None:
        print('no se pudo leer la version comprometida de %s' % DB_REL)
        return 2
    T = {h['hand_id']: h for h in trabajo}
    C = {h['hand_id']: h for h in comprometida}

    # ------------------------------------------------------------------ 1
    seccion('1. INVARIANTE -- ninguna `BB b` que no pueda ser la ciega')
    malas = learn.manos_con_orden_ciega_malo(trabajo)
    if malas:
        print('  FALLO: %d mano(s) lo violan: %s' % (len(malas), ', '.join(malas)))
        fallo.append('invariante CM-004 violado por %s' % malas)
    else:
        print('  OK  0 de %d manos.' % len(trabajo))

    # ------------------------------------------------------------------ 2
    seccion('2. CLASIFICACION -- que clase de cambio tiene cada mano editada')
    derivadas = indices_cm004(comprometida)
    descuadres = []
    for h in comprometida:
        acc = ((h.get('streets') or {}).get('preflop') or {}).get('actions') or []
        for i, importe, causa in learn.entradas_bb_rechazadas(h):
            if causa != learn.CAUSA_ORDEN:
                continue
            a = acc[i] if i < len(acc) else None
            if not a or a.get('pos') != 'BB' or a.get('action') != 'b' \
                    or a.get('amount') != importe:
                descuadres.append((h.get('hand_id'), i))
    if descuadres:
        print('  FALLO: el indice del motor no apunta a su accion cruda en %s'
              % descuadres)
        fallo.append('indices del motor descuadrados')
    else:
        print('  la regla del motor selecciona %d mano(s) sobre las %d de la '
              'version comprometida.' % (len(derivadas), len(comprometida)))
        print('  OK  sus %d indices apuntan a su accion cruda.'
              % sum(len(v) for v in derivadas.values()))

    reetiquetadas, reconstruidas, ajenas = [], [], []
    for hid in sorted(set(T) | set(C)):
        if canon(C.get(hid)) == canon(T.get(hid)):
            continue
        if hid in derivadas and solo_reetiquetado(C[hid], T[hid],
                                                  derivadas[hid]):
            reetiquetadas.append(hid)
        elif hid in derivadas:
            reconstruidas.append(hid)
        else:
            ajenas.append(hid)

    print()
    print('  REETIQUETADO  (una sola etiqueta b -> r)      : %d  %s'
          % (len(reetiquetadas), ' '.join(reetiquetadas)))
    print('  RECONSTRUIDO (anade, borra o reordena)       : %d  %s'
          % (len(reconstruidas), ' '.join(reconstruidas) or '-'))
    print('  AJENO A CM-004                               : %d  %s'
          % (len(ajenas), ' '.join(ajenas) or '-'))
    print('  total de manos editadas a mano               : %d'
          % (len(reetiquetadas) + len(reconstruidas) + len(ajenas)))

    esperadas = set(derivadas)
    corregidas = set(reetiquetadas) | set(reconstruidas)
    faltan = sorted(esperadas - corregidas)
    sobran = sorted(corregidas - esperadas)
    if faltan:
        print('  FALLO: la regla senala %d mano(s) sin corregir: %s'
              % (len(faltan), ', '.join(faltan)))
        fallo.append('%d manos del conjunto CM-004 sin corregir' % len(faltan))
    if sobran:
        print('  FALLO: se han corregido %d mano(s) que la regla no senala: %s'
              % (len(sobran), ', '.join(sobran)))
        fallo.append('%d correcciones fuera del conjunto CM-004' % len(sobran))
    if not faltan and not sobran:
        print('  OK  las %d manos de la regla son exactamente las %d '
              'corregidas: ni una de mas ni una de menos.'
              % (len(esperadas), len(corregidas)))

    # ------------------------------------------------------------------ 3
    seccion('3. DECLARADAS -- todo lo que no es un reetiquetado trivial')
    sin_declarar = [h for h in reconstruidas + ajenas if h not in DECLARADAS]
    if sin_declarar:
        print('  FALLO: editadas y NO declaradas en este fichero: %s'
              % ', '.join(sin_declarar))
        print('         O falta declararlas, o son un cambio sin explicar. '
              'Sin esa distincion no hay manifiesto.')
        fallo.append('%d cambios sin declarar' % len(sin_declarar))
    else:
        print('  OK  las %d reconstrucciones y los %d cambios ajenos a CM-004 '
              'estan declaradas, con motivo.'
              % (len(reconstruidas), len(ajenas)))

    print()
    for hid in reconstruidas + ajenas:
        d = DECLARADAS.get(hid)
        if not d:
            continue
        print('  %s  [%s]' % (hid, d['estado']))
        print('      que : %s' % d['que'])
        for l in envolver(d['motivo']):
            print('      %s' % l)
        if d['recomendado'] is not None:
            print('      recomendado : %s' % (d['recomendado'],))
            print('      ahora       : %s' % (T.get(hid, {}).get('winner'),))
            print('      ^ NO coincide. Es una de las tareas pendientes.')

    declaradas_sin_cambio = sorted(set(DECLARADAS) - set(reconstruidas)
                                   - set(ajenas))
    if declaradas_sin_cambio:
        print()
        print('  AVISO: declaradas aqui pero sin cambio en la copia de '
              'trabajo: %s' % ', '.join(declaradas_sin_cambio))

    # ------------------------------------------------------------------ 4
    seccion('4. LA BASE NO SE HA TOCADO')
    if sha256(DB_PATH) == sha_antes:
        print('  OK  sha256 sin cambios durante la verificacion: %s' % sha_antes)
    else:
        print('  FALLO: la base cambio durante la verificacion')
        fallo.append('la base se escribio durante la verificacion')

    seccion('RESULTADO')
    if fallo:
        for f in fallo:
            print('  - %s' % f)
        return 1
    print('  Sin fallos, y sin escrituras.')
    pend = [h for h, d in DECLARADAS.items()
            if d['estado'].startswith('PENDIENTE')]
    rev = [h for h, d in DECLARADAS.items()
           if d['estado'].startswith('APLICADO') and 'revisar' in d['estado']]
    if pend:
        print('  PENDIENTE de aplicar    : %s' % ', '.join(pend))
    if rev:
        print('  APLICADO, sin revisar   : %s' % ', '.join(rev))
    return 0


if __name__ == '__main__':
    sys.exit(main())