# -*- coding: utf-8 -*-
"""Manifiesto y verificacion de `hands_db.jsonl`. NO ESCRIBE NADA.

    python tools/verificar_cm004.py

Que problema resuelve
--------------------
La base se ha editado a mano, y una base editada a mano no tiene quien la
vuelva a hacer ni quien detecte que alguien la vuelve a estropear. Este
script es la lista de lo que se toco y el porque.

Las tres secciones
------------------
  1. INVARIANTE. ¿Queda alguna mano en las 1280 en la que una `BB b` no pueda
     ser la ciega? Se espera 0.
  2. CLASIFICACION. Para cada mano editada respecto a la version PREVIA de la
     base (anclada al commit `e314f74`), que clase de cambio es. Se espera
     EXACTAMENTE: 23 reetiquetados y 1 centinela de carta.
  3. REVERTIDAS. Las ocho correcciones que se deshicieron, con el motivo. Se
     verifica que NO esten en el fichero: una revertida que reaparece es un
     fallo, y una corregida que nadie declaro tambien.

Por que anclar a un commit y no a HEAD
--------------------------------------
Porque en cuanto la reinterpretacion esta commiteada, HEAD contiene la base
ya corregida: la regla derivaria 0 manos y el script pasaria sin comprobar
nada. Ver `SHA_ANTES`.

La regla vive en el motor, no aqui
----------------------------------
El defecto ES la discrepancia con el motor: `_es_ciega_bb` exige que no haya
accion voluntaria previa. Una cuenta hecha aqui podria discrepar de
`_es_ciega_bb` y publicar un numero que el motor no sostiene. Las funciones
viven en `motor/learn.py` y este script las importa.
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

# Se direcciona por COMMIT, que es lo unico que git resuelve, y se VERIFICA
# por el sha256 del contenido, que es lo que detecta que ese commit dejase de
# ser el que creimos.
COMMIT_ANTES = 'e314f74'
SHA_ANTES = 'bb46fec0f2e37dc7c4280cb2302d3180c0502cf9d289ab8430b1e6d957d912ee'

# Las ocho correcciones a mano que se han DESHECHO.
#
# Todas compartian el mismo defecto de procedimiento, y no de poker: el
# defecto que las justificaba NO es raro, se repite cientos de veces en la
# base. Corregir una vez un defecto que aparece 652 veces deja la base unas
# veces bien y otras mal, sin que nadie diga por que. Un defecto uniforme y
# conocido es recuperable; uno parcheado sin script, no.
#
# La evidencia del recuento esta en `DOCS/RECONSTRUCCIONES_CM004.md`.
#
# Las seis primeras conservan el reetiquetado `b` -> `r` del BB, que es la
# parte con una regla exacta y derivada del motor. Se revierte TODO lo demas.
REVERTIDAS_PARCIALES = {
    'H_0039': 'anade un `BB f` que nadie grabo. El patron "el BB no vuelve a '
              'actuar tras la ultima subida" aparece en 652 de las 1280 manos.',
    'H_0051': '`SB r 0.5` -> `c 1.0` y anade un `SB f`. El patron "subida a '
              'un importe <= la ciega nominal" aparece en 45 manos.',
    'H_0067': 'parte una llamada grabada en DOS, una de ellas a un importe '
              'que no constaba. Inventa una accion, y no tiene patron propio '
              'que la respalde: es el peor de los ocho.',
    'H_0109': '`SB r 0.5` -> `c 0.5`. El patron, 45 manos.',
    'H_0143': '`CO r 1.0` -> `c 1.0`. El patron, 45 manos.',
    'H_0263': 'borra un `MP x` y reordena el preflop. El patron "accion de '
              'alguien que ya habia foldeado" aparece en 8 manos.',
}

# Estas dos no tienen ninguna parte que conservar: no son de CM-004 y se
# vuelven al valor grabado entero.
REVERTIDAS_TOTALES = {
    'H_0969': 'borra un `BB f` imposible y recorta `winner`. El campo '
              '`winner` es incoherente en 214 de las 1280 manos, y ademas '
              'este recorte no es el unico caso de su patron.',
    'H_0970': 'recorta `winner` y ADEMAS quita al BB de un bote que gano: '
              'cambia un error por otro. Mismo campo, misma causa que '
              'H_0969.',
}

REVERTIDAS = dict(REVERTIDAS_PARCIALES)
REVERTIDAS.update(REVERTIDAS_TOTALES)

# El unico cambio que se mantiene y no es de CM-004.
CAMBIOS_QUE_NO_SON_CM004 = {
    'H_0350': {
        'que': "dos players con cards='-' en vez de ''",
        'motivo': "CM-002. El guion no es un codigo de carta: son las 2 unicas "
                  "apariciones de ese centinela en las 1280 manos, frente a "
                  "6085 usos de la cadena vacia. Normalizar el centinela NO "
                  "es reconstruir las cartas, que es lo que CM-002 prohibe. "
                  "Aqui el patron se aplica a TODAS sus apariciones, que es "
                  "justo lo que se echa en falta a los otros ocho.",
        'estado': 'APLICADO',
    },
}

DECLARADAS = set(CAMBIOS_QUE_NO_SON_CM004)


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


def de_referencia():
    """La version de la base de la que se deriva la regla. Verificada."""
    crudo = subprocess.run(['git', 'show', '%s:%s' % (COMMIT_ANTES, DB_REL)],
                           cwd=ROOT, capture_output=True)
    if crudo.returncode != 0:
        return None, 'no se pudo leer %s:%s' % (COMMIT_ANTES, DB_REL)
    real = hashlib.sha256(crudo.stdout).hexdigest()
    if real != SHA_ANTES:
        return None, ('%s:%s tiene sha256 %s, no el %s esperado'
                      % (COMMIT_ANTES, DB_REL, real[:16], SHA_ANTES[:16]))
    return crudo.stdout.decode('utf-8'), None


def indices_cm004(manos):
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
    referencia, error = de_referencia()
    if referencia is None:
        print('  FALLO: %s' % error)
        print('         Sin la version previa no se deriva la regla, y sin la '
              'regla este script no comprueba nada.')
        return 2
    T = {h['hand_id']: h for h in trabajo}
    C = {h['hand_id']: h for h in leer_texto(referencia)}

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
    derivadas = indices_cm004(C and leer_texto(referencia))
    descuadres = []
    for h in leer_texto(referencia):
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
              'version previa (%s).'
              % (len(derivadas), len(C), COMMIT_ANTES))
        print('  OK  sus %d indices apuntan a su accion cruda.'
              % sum(len(v) for v in derivadas.values()))

    reetiquetadas, reconstruidas, ajenas, otras = [], [], [], []
    for hid in sorted(set(T) | set(C)):
        if canon(C.get(hid)) == canon(T.get(hid)):
            continue
        if hid in derivadas and solo_reetiquetado(C[hid], T[hid],
                                                  derivadas[hid]):
            reetiquetadas.append(hid)
        elif hid in derivadas:
            reconstruidas.append(hid)
        elif hid in DECLARADAS:
            ajenas.append(hid)
        else:
            otras.append(hid)

    print()
    print('  REETIQUETADO  (una sola etiqueta b -> r)      : %d  %s'
          % (len(reetiquetadas), ' '.join(reetiquetadas)))
    print('  RECONSTRUIDO (anade, borra o reordena)       : %d  %s'
          % (len(reconstruidas), ' '.join(reconstruidas) or '- (esperado)'))
    print('  OTRO, y declarado                             : %d  %s'
          % (len(ajenas), ' '.join(ajenas) or '-'))
    print('  OTRO, y SIN declarar                           : %d  %s'
          % (len(otras), ' '.join(otras) or '-'))
    print('  total de manos editadas                       : %d'
          % (len(reetiquetadas) + len(reconstruidas) + len(ajenas)
             + len(otras)))

    if reconstruidas:
        print('  FALLO: hay %d manos con cambios que NO son un reetiquetado. '
              'Solo se permite anadir, borrar o reordenar con una decision '
              'escrita.' % len(reconstruidas))
        fallo.append('%d reconstrucciones sin decision' % len(reconstruidas))
    if otras:
        print('  FALLO: manos editadas y no declaradas. O falta declararlas, '
              'o son un cambio sin explicar.')
        fallo.append('%d cambios sin declarar' % len(otras))

    faltando = sorted(set(derivadas) - set(reetiquetadas) - set(reconstruidas))
    if faltando:
        print('  FALLO: la regla senala %d mano(s) sin corregir: %s'
              % (len(faltando), ', '.join(faltando)))
        fallo.append('%d manos del conjunto CM-004 sin corregir' % len(faltando))

    # ------------------------------------------------------------------ 3
    seccion('3. REVERTIDAS -- las ocho que se deshicieron')
    reaparecidas = [h for h in REVERTIDAS_TOTALES
                    if canon(C.get(h)) != canon(T.get(h))]
    if reaparecidas:
        print('  FALLO: estas revertedidas enteras han vuelto a cambiar: %s'
              % ', '.join(sorted(reaparecidas)))
        fallo.append('%d revertedidas enteras reaparecidas' % len(reaparecidas))
    else:
        print('  OK  las %d revertidas ENTERAS son identicas a la version '
              'previa.' % len(REVERTIDAS_TOTALES))

    con_exceso = [h for h in REVERTIDAS_PARCIALES
                  if h in reconstruidas]
    if con_exceso:
        print('  FALLO: estas revertidas PARCIALES vuelven a anadir, borrar o '
              'reordenar: %s' % ', '.join(sorted(con_exceso)))
        fallo.append('%d revertidas parciales con cambios de mas'
                     % len(con_exceso))
    else:
        print('  OK  las %d revertidas PARCIALES solo conservan el '
              'reetiquetado `b` -> `r` del BB, que es la parte con regla '
              'exacta.' % len(REVERTIDAS_PARCIALES))

    print()
    print('  Han vuelto al valor grabado porque no hay original que permita '
          'sostener')
    print('  ninguna lectura. El defecto sigue documentado, no escondido:')
    print('  ver DOCS/RECONSTRUCCIONES_CM004.md.')
    print()
    for hid in sorted(REVERTIDAS):
        etiqueta = 'PARCIAL' if hid in REVERTIDAS_PARCIALES else 'ENTERA'
        print('  %-8s [%s]' % (hid, etiqueta))
        for l in envolver(REVERTIDAS[hid]):
            print('      %s' % l)

    for hid in DECLARADAS:
        d = CAMBIOS_QUE_NO_SON_CM004[hid]
        if hid not in ajenas:
            print()
            print('  AVISO: %s esta declarada pero no ha cambiado' % hid)
            continue
        print()
        print('  %s  [%s]' % (hid, d['estado']))
        print('      que : %s' % d['que'])
        for l in envolver(d['motivo']):
            print('      %s' % l)

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
    print('  %d manos editadas: %d reetiquetados de CM-004 + %d centinela. '
          'Nada mas.' % (len(reetiquetadas) + len(ajenas),
                         len(reetiquetadas), len(ajenas)))
    return 0


if __name__ == '__main__':
    sys.exit(main())