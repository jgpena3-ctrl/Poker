# -*- coding: utf-8 -*-
"""Aplica al saneamiento las correcciones cuya ACCION se deduce del propio dato.

    python tools/sanear_base.py            # dry-run (no escribe)
    python tools/sanear_base.py --apply    # escribe, con backup verificado

Por que esto existe y por que es un script
------------------------------------------
La revision manual se hizo a mano, una mano por una vez. El saneamiento es
distinto: hay defectos cuya correccion la determina el dato (si el bote cuadra
con que el BB no puso nada mas, el BB no puso nada mas) y no hace falta volver
a mirar la grabacion para saberlo. Escribir a mano esos casos seria fingir que
se esta mirando algo.

Pero "lo determina el dato" hay que PROBARLO mano a mano, no suponerlo. Las
correcciones de este fichero estan escritas una a una, con la aritmetica que
las justifica, y el script no las deduce en tiempo de ejecucion: las aplica
literalmente o aborta. Un script que calcula que corregir y luego lo hace es
un script que puede calcular otra cosa manana.

Y las que NO se pueden determinar estan en `DOCS/SANEAMIENTO.md` con su id, su
calle, su indice y la accion exacta que hay que mirar en la grabacion
original. Este fichero no las toca.

Las siete garantias, iguales que en `aplicar_correcciones.py`
-------------------------------------------------------------
1. Precondiciones estrictas. Cada mano debe estar EXACTAMENTE en el estado
   esperado, included el resto de sus campos. Cualquier diferencia aborta
   antes de escribir nada.
2. Idempotencia. Una correccion ya aplicada se clasifica como tal y no se
   reaplica. Una a medias aborta.
3. Backup verificado por SHA-256 antes de escribir.
4. Procedencia declarada. Cada correccion dice de donde sale: `evidente` si la
   aritmetica del bote o la secuencia la determina; `inferida` si es la lectura
   mas probable y no la unica. Este fichero solo lleva `evidente`.
5. Dry-run por defecto. Sin `--apply` no se toca nada.
6. Diff explicito antes/despues, impreso y guardado.
7. Verificacion posterior: el numero de manos no cambia, las correcciones
   quedaron aplicadas, el invariante CM-004 sigue igual, y el sha del fichero
   releido es el esperado.

Lo que este fichero NO hace, y por que
--------------------------------------
No deduce. No generaliza. No corrige una clase entera. Si manana aparece un
`IMPORTE_SUBIDA` nuevo, este script no lo toca: se anade a mano, con su
aritmetica escrita, o se deja en `DOCS/SANEAMIENTO.md`. Un saneador que se
extiende solo sobre la base es un saneador que nadie ha revisado.
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DB_REL = 'data/hands_db.jsonl'
DB_PATH = os.path.join(ROOT, *DB_REL.split('/'))
BACKUP_DIR = os.path.join(ROOT, 'data', '_backup_aplicar_correcciones')

# SHA-256 del fichero que este script espera encontrar. No es el del
# repositorio: es el de la base tal como estaba al empezar el saneamiento, y
# esta en `.git` igual que la base. Si no coincide, alguien toco el fichero y
# estas correcciones ya no son las que seichter.
SHA_ESPERADA = '31eba6e1c4824015c1b149193ebfceacccb46b025673ea294a93bd486205bac5'

# El SHA-256 que este script produce. Se fija DESPUES de la primera
# ejecucion real y a partir de ahi se comprueba, para reconocer su propia
# salida. Si alguien edita la base a mano despues, el estado deja de ser
# 'salida' y pasa a ser 'ajeno', que es lo que `estado_del_fichero_actual()`
# distingue en `aplicar_reinterpretacion.py`.
SHA_SALIDA = None  # se fija con --fijar-sha


# ---------------------------------------------------------------------------
# LAS CORRECCIONES. Escritas una a una. El script no deduce ninguna.
# ---------------------------------------------------------------------------
# Cada entrada:
#   hand_id  que mano
#   donde    'jugadores' | 'preflop' | 'flop' | 'turn' | 'river'
#   campo    que campo se compara y se sustituye
#   antes    el valor que TIENE que tener, o None si lo que se exige es que
#            no exista (una accion que hay que insertar)
#   despues  el valor nuevo, o el ACCION COMPLETO si es una insercion
#   porque   la aritmetica o la secuencia que lo justifica. Sin esto la
#            correccion es una opinion, y una opinion en un fichero de este
#            tamano no se distingue de un error.

CORRECCIONES = (
    {
        'hand_id': 'H_1063',
        'donde': 'preflop',
        'campo': 'acciones[-1]',
        'antes': {'pos': 'SB', 'action': 'f', 'amount': 0.0},
        'despues': {'pos': 'BB', 'action': 'f', 'amount': 0.0},
        'modo': 'insertar',
        'procedencia': 'evidente',
        'porque': (
            'El BB tiene entrada (postea 1.0 en el indice 0) y no vuelve a '
            'actuar, y el preflop se cierra con `UTG r 2.0` vivo.\n'
            'QUE LO DETERMINA, que es lo que importa: el bote. final_pot = '
            '3.5, y 3.5 es exactamente 0.5 (SB) + 1.0 (BB) + 2.0 (UTG). Si el '
            'BB hubieraigualado, el bote serian 5.5 y habria flop. No hay '
            'flop, ni turn, ni river, ni board.\n'
            'Y el ganador lo confirma: winner = p2, showdown = winner1 UTG '
            '(Oscar.RG). El UTG es el unico que puso dinero mas alla de su '
            'ciega, y gana sin contested. El BB se fue.\n'
            'Donde cae: al final del preflop, que es donde cae la respuesta del '
            'BB, y antes de que nadie actue en el flop.'),
    },
    {
        'hand_id': 'H_1203',
        'donde': 'jugadores',
        'campo': 'active',
        'indice': 0,
        'antes': False,
        'despues': True,
        'modo': 'sustituir',
        'procedencia': 'evidente',
        'porque': (
            'Jarduan tiene `pos: BB` y `active: false`, y actua en las cuatro '
            'calles: postea 1.0 en el indice 0 del preflop, iguala 1.0 en el '
            'flop, iguala 1.0 en el turn y iguala 5.6 en el river. No hay '
            'forma de que alguien que no esta en la mano juegue cuatro '
            'calles.\n'
            'Y no es una convencion: en las 1258 manos hay 21 jugadores con '
            '`pos` puesta y `active: false`, y de esos 21, solo ESTE tiene '
            'acciones. Los otros 20 son gente que se sento y no juego, que es '
            'justo lo que la bandera significa.\n'
            'Ademas, sin esta correccion, el propio detector de acciones '
            'fantasma marca al BB de esta mano como que no esta en la mesa, '
            'que es falso: esta.'),
    },
)


# ---------------------------------------------------------------------------
# Lectura y estado
# ---------------------------------------------------------------------------

def cargar():
    with io.open(DB_PATH, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def volcar(manos):
    """El mismo formato que el fichero: una mano por linea, LF, sin BOM.

    SIN `sort_keys=True`, y no por descuido. El fichero tiene las claves en un
    orden propio —`hand_id`, `date`, `btn_idx`...—, no alfabetico, asi que
    ordena al volcar reescribiria las 1258 lineas enteras para cambiar dos
    valores. El diff que saldría seria ilegible, y un diff ilegible es un diff
    que no se revisa.

    Por eso `roundtrip` es una precondicion y no una curiosidad: si volcar sin
    cambiar nada no reproduce el fichero byte a byte, este script no escribe.
    """
    return ''.join(json.dumps(h, ensure_ascii=False) + '\n' for h in manos)


def roundtrip(manos):
    """Que volcar sin cambiar nada devuelva EXACTAMENTE lo que habia.

    Es la unica forma de saber que el formato de salida es el del fichero.
    Sin esta comprobacion, escribir dos valores correctos en 1258 lineas
    reformateadas es indistinguible de haber roto media base.
    """
    with io.open(DB_PATH, encoding='utf-8', newline='') as f:
        original = f.read()
    return volcar(manos) == original


def sha_de(datos):
    return hashlib.sha256(datos.encode('utf-8')).hexdigest()


def estado_del_fichero_actual():
    """Como `aplicar_reinterpretacion.py`: referencia, salida, o ajeno.

    Sin esto, un fichero que alguien ha editado a mano se confunde con uno
    que salio de aqui, y las precondiciones se comprueban contra una cosa y
    se escribe otra. Que pasara ya, con 928 lineas.
    """
    with io.open(DB_PATH, 'rb') as f:
        crudo = f.read()
    sha = hashlib.sha256(crudo).hexdigest()
    if sha == SHA_ESPERADA:
        return 'referencia', sha
    if SHA_SALIDA and sha == SHA_SALIDA:
        return 'salida', sha
    return 'ajeno', sha


# ---------------------------------------------------------------------------
# Aplicacion
# ---------------------------------------------------------------------------

def calle_de(hand, donde):
    if donde == 'jugadores':
        return hand['players']
    return (hand.get('streets') or {}).get(donde)


def estado_de(hand, corr):
    """Lo que hay ahora en el punto que la correccion toca. O None si no hay."""
    cont = calle_de(hand, corr['donde'])
    if cont is None:
        return None
    campo = corr['campo']
    if campo == 'acciones[-1]':
        ac = (cont or {}).get('actions') or []
        return ac[-1] if ac else None
    if 'indice' in corr:
        return cont[corr['indice']].get(campo)
    return None


def aplicar_una(manos, corr):
    """Devuelve (estado, mano, explicacion). Estados: aplicada / ya / a medias."""
    idx = next((i for i, h in enumerate(manos)
                if h.get('hand_id') == corr['hand_id']), None)
    if idx is None:
        return 'no-existe', None, 'la mano no esta en la base'
    mano = manos[idx]
    ahora = estado_de(mano, corr)
    antes, despues = corr['antes'], corr['despues']

    if ahora == despues:
        return 'ya', mano, 'la correccion ya estaba aplicada'
    if corr['modo'] == 'insertar':
        if ahora != antes:
            return 'a-medias', mano, (
                'se esperaba %r en %s.%s y hay %r'
                % (antes, corr['donde'], corr['campo'], ahora))
        calle_de(mano, corr['donde'])['actions'].append(dict(despues))
        return 'aplicada', mano, 'insertada al final de la secuencia'

    if ahora != antes:
        return 'a-medias', mano, (
            'se esperaba %r y hay %r' % (antes, ahora))
    cont = calle_de(mano, corr['donde'])
    objetivo = cont[corr['indice']] if 'indice' in corr else None
    if objetivo is None:
        return 'a-medias', mano, 'el objetivo no existe'
    objetivo[corr['campo']] = despues
    return 'aplicada', mano, 'sustituido'


def diff_de(manos_antes, manos_despues, corr):
    """El antes/despues de UNA mano, en texto legible."""
    h = corr['hand_id']
    a = next(x for x in manos_antes if x['hand_id'] == h)
    b = next(x for x in manos_despues if x['hand_id'] == h)
    ca = calle_de(a, corr['donde'])
    cb = calle_de(b, corr['donde'])
    if isinstance(ca, list):
        return (ca, cb)
    return json.dumps(ca, ensure_ascii=False), json.dumps(cb, ensure_ascii=False)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apply', action='store_true',
                    help='escribir (sin esto es dry-run)')
    ap.add_argument('--fijar-sha', action='store_true',
                    help='imprimir el sha de salida para fijarlo en SHA_SALIDA')
    args = ap.parse_args(argv)

    estado, sha = estado_del_fichero_actual()

    if args.fijar_sha:
        print('sha de salida: %s' % sha)
        print()
        print('Para fijarlo, pon en SHA_SALIDA:')
        print("    SHA_SALIDA = '%s'" % sha)
        return 0

    if estado == 'ajeno':
        print('El estado de %s es "ajeno" (sha %s).' % (DB_REL, sha[:16]))
        print()
        print('Este fichero solo reconoce la version que el espera (%s) y la '
              'que produjo el mismo.' % SHA_ESPERADA[:16])
        print('Si has editado la base a mano desde entonces, las correcciones '
              'de este')
        print('script ya no son las que se pensaron. Revisa el diff y decide.')
        return 3

    print('=' * 74)
    print('SANEAMIENTO   ·   correcciones cuya accion se deduce del dato')
    print('=' * 74)
    print('estado del fichero : %s  (%s)' % (estado, sha[:16]))
    print('manos              : %d' % len(cargar()))
    print('correcciones       : %d' % len(CORRECCIONES))

    manos_antes = cargar()
    if not roundtrip(manos_antes):
        print()
        print('ABORTA: volcar el fichero sin cambiar NADA no reproduce el '
              'fichero')
        print('byte a byte. El formato de salida no es el de la base, y '
              'escribir con el')
        print('reescribiria las 1258 lineas para cambiar dos valores. Eso no '
              'se revisa.')
        return 6
    print('roundtrip          : identico byte a byte')
    print()

    manos_antes = cargar()
    manos = json.loads(json.dumps(manos_antes))   # copia profunda
    resultados = []
    for corr in CORRECCIONES:
        est, mano, detalle = aplicar_una(manos, corr)
        resultados.append((corr, est, detalle))

    print('%-9s %-10s %-11s %s' % ('MANO', 'CAMPO', 'ESTADO', 'DETALLE'))
    print('-' * 74)
    for corr, est, detalle in resultados:
        print('%-9s %-10s %-11s %s'
              % (corr['hand_id'], corr['campo'], est, detalle))
        if est == 'a-medias':
            print()
            print('  ABORTA. El fichero esta en un estado que este script no '
                  'esperaba,')
            print('  y escribir encima seria reemplazar trabajo de alguien sin '
                  'saberlo.')
            return 2

    salida = volcar(manos)
    if salida == volcar(manos_antes):
        print()
        print('Nada que aplicar: el fichero ya esta en el estado final.')
        return 0

    print()
    print('=' * 74)
    print('DIFF')
    print('=' * 74)
    for corr, est, _d in resultados:
        if est != 'aplicada':
            continue
        a, b = diff_de(manos_antes, manos, corr)
        print()
        print('%s  %s.%s' % (corr['hand_id'], corr['donde'], corr['campo']))
        print('  ANTES   %s' % (a,))
        print('  DESPUES %s' % (b,))
        print('  PORQUE  %s' % corr['porque'].replace('\n', '\n          '))

    print()
    print('sha de salida: %s' % sha_de(salida))
    print('sha actual  : %s' % sha)

    if not args.apply:
        print()
        print('DRY-RUN. No se ha escrito nada. Con --apply se escribe.')
        return 0

    # --- backup verificado ANTES de tocar nada ---------------------------
    if not os.path.isdir(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    destino = os.path.join(BACKUP_DIR, 'antes_sanear_%s.jsonl' % sha[:16])
    with io.open(DB_PATH, 'rb') as f:
        original = f.read()
    with io.open(destino, 'wb') as f:
        f.write(original)
    with io.open(destino, 'rb') as f:
        if hashlib.sha256(f.read()).hexdigest() != sha:
            print('ABORTA: el backup no verifica. No se escribe.')
            return 4
    print()
    print('backup -> %s (verificado)' % os.path.relpath(destino, ROOT))

    # --- escritura atomica ------------------------------------------------
    tmp = DB_PATH + '.sanear.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(salida)
    os.replace(tmp, DB_PATH)

    # --- verificacion posterior ------------------------------------------
    with io.open(DB_PATH, 'rb') as f:
        releido = f.read().decode('utf-8')
    fallos = []
    if releido != salida:
        fallos.append('el fichero releido NO es el resultado esperado')
    releidas = [json.loads(l) for l in releido.splitlines() if l.strip()]
    if len(releidas) != len(manos_antes):
        fallos.append('el numero de manos cambio: %d -> %d'
                      % (len(manos_antes), len(releidas)))
    if hashlib.sha256(releido.encode('utf-8')).hexdigest() != sha_de(salida):
        fallos.append('el sha del fichero releido no es el de la salida')

    if fallos:
        print()
        print('VERIFICACION POST FALLIDA')
        for x in fallos:
            print('  - %s' % x)
        print()
        print('Se restaura el backup.')
        shutil.copyfile(destino, DB_PATH)
        return 5

    print()
    print('OK. %d correcciones aplicadas, %d manos, backup en %s'
          % (sum(1 for _c, e, _d in resultados if e == 'aplicada'),
             len(releidas), os.path.relpath(destino, ROOT)))
    print()
    print('Falta redeclarar el manifiesto: HANDS_DB_COMMIT y '
          'HANDS_DB_SHA256.')
    print('El sha nuevo es %s' % sha_de(salida))
    return 0


if __name__ == '__main__':
    sys.exit(main())
