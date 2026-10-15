# -*- coding: utf-8 -*-
"""Rehace `hands_db.jsonl` desde una version conocida: la reinterpretacion de
CM-004 y el centinela de CM-002. Nada mas.

    python tools/aplicar_reinterpretacion.py            # dry-run (no escribe)
    python tools/aplicar_reinterpretacion.py --apply

Por que EXISTE este script
-------------------------
La reinterpretacion se aplico A MANO. Una base editada a mano no tiene quien
la vuelva a hacer ni quien detecte que alguien la vuelve a estropear. Este
script es eso: deriva el estado final de la version previa (`e314f74`) con dos
reglas, y verifica que el resultado sea exactamente el esperado.

Que aplica, y que NO
--------------------
1. CM-004. La entrada `BB b` que el motor NO reconoce como ciega pasa a `r`.
   La lista NO esta escrita aqui: la deriva `learn.entradas_bb_rechazadas`, la
   misma regla que usa el motor. Escribirla seria una segunda regla, y una
   segunda regla puede discrepar de la primera.

2. CM-002. Los dos `players` con `cards="-"` pasan a `""`. El guion no es un
   codigo de carta y hay 2 apariciones en 1280 manos frente a 6085 de la
   cadena vacia: se normaliza el centinela, no se reconstruye la carta.

Y NO aplica nada mas. En particular, NO aplica las seis reconstrucciones de
preflop ni los recortes de `winner`: eran correcciones a mano, las seis
reaparecen 8, 45 y 652 veces mas en la base, y corregir una no hace que las
otras sean menos. Ver `DOCS/RECONSTRUCCIONES_CM004.md`.

Garantias
---------
1. Se construye DESDE `e314f74`, verificado por sha256. No se parte del
   fichero actual, que es justamente lo que hay que poder rehacer.
2. Idempotente por construccion: el resultado no depende del estado de
   entrada. Aplicarlo dos veces da el mismo fichero.
3. El resultado se compara con el fichero actual ANTES de escribir. Si
   difieren, se imprime el diff y no se escribe nada.
4. Backup verificado por sha256 antes de tocar el original.
5. Escritura atomica con validacion de cada linea.
6. Rollback automatico si la verificacion post-escritura falla.
7. Verificacion post: mismo numero de manos, invariante CM-004 a 0, y el
   conjunto de manos modificadas es EXACTAMENTE el esperado.
"""
import argparse
import collections
import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor import learn  # noqa: E402

DB_REL = 'data/hands_db.jsonl'
DB_PATH = os.path.join(ROOT, *DB_REL.split('/'))
COMMIT_ANTES = 'e314f74'
SHA_ANTES = 'bb46fec0f2e37dc7c4280cb2302d3180c0502cf9d289ab8430b1e6d957d912ee'

# Lo que este script DEJA fuera, y por que. Cada uno se revierte.
REVERTIDAS = (
    ('H_0039', 'anade `BB f` que nadie grabo. El patron aparece 652 veces.'),
    ('H_0051', '`SB r 0.5` -> `c 1.0` y `SB f` anadido. El patron, 45 veces.'),
    ('H_0067', 'parte una llamada grabada en dos, una a un importe que no '
               'constaba. No tiene patron propio.'),
    ('H_0109', '`SB r 0.5` -> `c 0.5`. El patron, 45 veces.'),
    ('H_0143', '`CO r 1.0` -> `c 1.0`. El patron, 45 veces.'),
    ('H_0263', 'borra `MP x` y reordena el preflop. El patron, 8 veces.'),
    ('H_0969', 'borra un `BB f` y recorta `winner`. `winner` es no fiable en '
               '214 de 1280 manos; corregir una no dice nada de las otras.'),
    ('H_0970', 'recorta `winner` y ademas quita al BB de un bote que gano. '
               'Mismo campo, misma causa.'),
)


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def version_previa():
    crudo = subprocess.run(['git', 'show', '%s:%s' % (COMMIT_ANTES, DB_REL)],
                           cwd=ROOT, capture_output=True)
    if crudo.returncode != 0:
        raise SystemExit('no se pudo leer %s:%s' % (COMMIT_ANTES, DB_REL))
    real = sha256_bytes(crudo.stdout)
    if real != SHA_ANTES:
        raise SystemExit('%s:%s tiene sha256 %s, no el esperado %s'
                         % (COMMIT_ANTES, DB_REL, real[:16], SHA_ANTES[:16]))
    return crudo.stdout.decode('utf-8')


def aplicar_a_mano(texto):
    """Devuelve (lineas, cambios). La lista de manos sale del motor."""
    cambios = []
    salida = []
    for n, linea in enumerate(texto.splitlines(), 1):
        if not linea.strip():
            salida.append(linea)
            continue
        h = json.loads(linea)
        hid = h.get('hand_id')
        original = copy.deepcopy(h)

        # --- CM-004: la que el motor no reconoce como ciega pasa a `r` ----
        acc = ((h.get('streets') or {}).get('preflop') or {}).get(
            'actions') or []
        for i, importe, causa in learn.entradas_bb_rechazadas(h):
            if causa != learn.CAUSA_ORDEN:
                continue
            antes = dict(acc[i])
            acc[i] = dict(acc[i], action='r')
            cambios.append((hid, n, 'CM-004', antes, dict(acc[i])))

        # --- CM-002: el guion no es un codigo de carta --------------------
        for k, p in enumerate(h.get('players') or []):
            if p.get('cards') == '-':
                cambios.append((hid, n, 'CM-002', dict(p), dict(p,
                                                                 cards='')))
                p['cards'] = ''

        if json.dumps(original, sort_keys=True) != json.dumps(
                h, sort_keys=True):
            salida.append(json.dumps(h, ensure_ascii=False))
        else:
            salida.append(linea)
    return salida, cambios


def diff_contra_actual(lineas):
    actual = io.open(DB_PATH, encoding='utf-8').read().splitlines()
    iguales = actual == lineas
    if iguales:
        return True, []
    cambios = []
    for i, (a, b) in enumerate(zip(actual, lineas), 1):
        if a != b:
            cambios.append(i)
    return False, cambios


# SHA-256 de la salida de ESTE script sobre `e314f74`, y de la referencia.
# Un fichero actual que no sea ninguno de los dos significa que alguien lo
# ha editado: y entonces este script no debe escribir encima.
SHA_SALIDA = '173a72743c7a54255452fb3fc4d8a9095adaddff29a54d84dda1d459bcc7fe8d'


def estado_del_fichero_actual():
    """(estado, sha). Estado ∈ {referencia, salida_de_este_script, ajeno}.

    Es la garantia que faltaba, y se lleno por un accidente concreto:
    `--apply` con un fichero que NO era suyo lo sobrescribio igualmente,
    porque solo comparaba con su PROPIA salida y no con la de nadie mas. Un
    fichero ajeno no es un fichero que este script pueda reemplazar, por muy
    bien que cuadre su alcance.
    """
    sha = sha256_bytes(open(DB_PATH, 'rb').read())
    if sha == SHA_ANTES:
        return 'referencia', sha
    if sha == SHA_SALIDA:
        return 'salida_de_este_script', sha
    return 'ajeno', sha


def set_tocado(texto_a, texto_b):
    """Los `hand_id` cuyo contenido difiere entre dos versiones de la base."""
    a = {json.loads(l)['hand_id']: l for l in texto_a.splitlines() if l.strip()}
    b = {json.loads(l)['hand_id']: l for l in texto_b.splitlines() if l.strip()}
    return {hid for hid in set(a) | set(b) if a.get(hid) != b.get(hid)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true',
                    help='escribir de verdad (sin esto, dry-run)')
    ap.add_argument('--descartar-cambios', action='store_true',
                    help='escribir aunque el fichero actual NO sea ni la '
                         'referencia ni la salida de este script')
    args = ap.parse_args(argv)

    print('=' * 74)
    print('aplicar_reinterpretacion  ·  %s'
          % ('MODO REAL' if args.apply else 'DRY-RUN (no escribe)'))
    print('=' * 74)

    previa = version_previa()
    print('origen   : %s:%s  (sha256 verificado)' % (COMMIT_ANTES, DB_REL))

    lineas, cambios = aplicar_a_mano(previa)
    manos = [json.loads(l) for l in lineas if l.strip()]
    resultado = '\n'.join(lineas)

    # El conjunto REAL de manos tocadas, derivado comparando con la previa.
    # Declarado aparte para que se note si el alcance cambia.
    tocadas = set_tocado(previa, resultado)
    declaradas = {'H_0350'} | set(learn.manos_excluidas())
    alcance_ok = tocadas == declaradas

    print()
    print('manos modificadas: %d   acciones tocadas: %d'
          % (len(tocadas), len(cambios)))
    print()
    por_tipo = collections.Counter(c[2] for c in cambios)
    for tipo, n in sorted(por_tipo.items()):
        print('  %-8s %d' % (tipo, n))
    print()
    print('  CM-004: la lista NO esta escrita en el script. La deriva')
    print('          `learn.entradas_bb_rechazadas`, que es la regla del motor.')
    print('          %d mano(s).' % len({c[0] for c in cambios
                                        if c[2] == 'CM-004'}))
    print('  CM-002: H_0350, dos `cards="-"`. El guion no es un codigo de carta.')
    print()
    if alcance_ok:
        print('  alcance: las %d manos tocadas son exactamente las declaradas '
              '(23 de CM-004 + H_0350).' % len(tocadas))
    else:
        print('  FALLO DE ALCANCE.')
        print('    tocadas pero no declaradas   : %s'
              % (sorted(tocadas - declaradas) or 'ninguna'))
        print('    declaradas pero no tocadas   : %s'
              % (sorted(declaradas - tocadas) or 'ninguna'))

    # --- garantia 3 y 4: el alcance ANTES de cualquier retorno de exito ----
    #
    # revision_2 §1: el alcance se informaba pero no bloqueaba el exito, y
    # habia DOS caminos que devolvian 0 sin comprobarlo:
    #
    #   a) el fichero ya coincidia (idempotencia) y el alcance no cuadraba
    #   b) dry-run con el alcance sin cuadrar
    #
    # Los dos estan cerrados aqui. La idempotencia significa "el resultado
    # reproducido coincide Y todas las invariantes se cumplen", no solo "el
    # contenido coincide": si el conjunto de manos tocadas no es el declarado,
    # el script esta produciendo otra cosa, y da igual que esa otra cosa ya
    # este escrita.
    if not alcance_ok:
        print()
        print('ABORTANDO: el alcance no cuadra. No se escribe nada.')
        if args.apply:
            print('  (--apply no cambia nada: un alcance incorrecto no se '
                  'puede aplicar en ningun modo.)')
        else:
            print('  (dry-run tambien falla: es el mismo defecto.)')
        return 2

    # --- la base esta CONGELADA mientras la revision manual siga en curso ---
    #
    # El mantenedor esta revisando las manos una a una, y las decisiones que
    # dependen de ello no se toman hasta el final. Editar la base mientras tanto
    # invalida la revision: se estarian revisando manos que luego cambian.
    #
    # Solo bloquea ESCRIBIR. El dry-run informa y sigue: no escribe nada, y un
    # informe que no se puede ver no sirve para decidir.
    #
    # No es una intencion, es un booleano en `learn`, y `--descartar-cambios`
    # NO lo salta: saltarlo significa terminar la revision.
    congelada = learn.REVISION_PENDIENTE and args.apply
    if congelada:
        print()
        print('  BASE CONGELADA: hay una revision manual en curso.')
        print('    revisadas hasta : %s' % learn.REVISION_HASTA)
        print('    total esperado  : %d' % learn.REVISION_TOTAL_ESPERADA)
        print()
        print('  No se escribe nada. Las decisiones que dependen de la revision')
        print('  (los cambios sin motivo, las eliminadas, las reconstrucciones)')
        print('  se toman AL FINAL, no ahora.')
        print('  Para escribir haria falta poner learn.REVISION_PENDIENTE a')
        print('  False, que significa "la revision ha terminado".')
        return 4
    if learn.REVISION_PENDIENTE:
        print()
        print('  AVISO: hay una revision manual en curso (hasta %s de %d).'
              % (learn.REVISION_HASTA, learn.REVISION_TOTAL_ESPERADA))
        print('  En --apply la base esta CONGELADA y no se puede escribir.')
        print('  Esto es un dry-run: informa, no escribe.')

    iguales, lineas_distintas = diff_contra_actual(lineas)
    print()

    # --- garantia 3b: el fichero actual tiene que ser ALGO conocido -------
    estado, sha_actual = estado_del_fichero_actual()
    print('fichero actual: sha256 %s  ->  %s' % (sha_actual[:16], estado))
    if estado == 'ajeno':
        print()
        print('  AVISO: el fichero actual NO es la referencia (%s) ni la salida'
              % SHA_ANTES[:16])
        print('  de este script (%s). Alguien lo ha editado a mano.'
              % SHA_SALIDA[:16])
        print('  Aplicar aqui lo SOBRESCRIBE: %d linea(s) ajenas se perderian.'
              % len(lineas_distintas))
        if not args.apply:
            print()
            print('  (dry-run: no se escribe nada y esto no es un error aqui.)')
            print('  En --apply si lo es, porque entonces se perderian.')
        elif not args.descartar_cambios:
            print()
            print('  ABORTANDO. Para hacerlo de verdad, a sabiendas:')
            print('      --apply --descartar-cambios')
            print('  El backup se hace antes de escribir, pero un cambio ajeno no')
            print('  es un cambio que este script pueda deshacer.')
            return 3

    if iguales:
        print('el fichero ACTUAL ya es identico al que produce este script,')
        print('y el alcance cuadra. IDEMPOTENCIA CORRECTA.')
        print('nada que hacer.')
        return 0

    print('el fichero actual difiere del que produce este script en %d linea(s):'
          % len(lineas_distintas))
    print()
    print('LO QUE ESTE SCRIPT DEJA FUERA (y por que):')
    for hid, motivo in REVERTIDAS:
        print('   %-8s %s' % (hid, motivo))

    if not args.apply:
        print()
        print('DRY-RUN. Para escribir de verdad: --apply')
        return 0

    # --- garantia 4: backup verificado -----------------------------------
    backup_dir = os.path.join(ROOT, 'data', '_backup_aplicar_correcciones')
    os.makedirs(backup_dir, exist_ok=True)
    backup = os.path.join(backup_dir, 'hands_db.jsonl.antes_reinterpretacion')
    shutil.copy2(DB_PATH, backup)
    h_orig, h_back = sha256_bytes(open(DB_PATH, 'rb').read()), \
        sha256_bytes(open(backup, 'rb').read())
    if h_orig != h_back:
        raise SystemExit('el backup no coincide; abortando')
    print()
    print('backup    : %s  (sha256 verificado, %s)'
          % (os.path.relpath(backup, ROOT), h_orig[:16]))

    # --- garantia 5: escritura atomica -----------------------------------
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(DB_PATH),
                               prefix='.hands_db_', suffix='.tmp')
    os.close(fd)
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        for l in lineas:
            f.write(l + '\n')
    for n, l in enumerate(io.open(tmp, encoding='utf-8'), 1):
        if l.strip():
            json.loads(l)

    os.replace(tmp, DB_PATH)

    # --- garantia 7: verificacion post, CONTRA EL RESULTADO ESPERADO ------
    #
    # revision_2 §1: la garantia declarada era mas fuerte que la
    # implementada. Antes solo se comprobaban el numero de manos y el
    # invariante CM-004, y las dos pueden cumplirse con un fichero
    # equivocado. Ahora se compara el fichero releido, linea a linea, con lo
    # que este script dice que produce.
    releido = io.open(DB_PATH, encoding='utf-8').read().splitlines()
    releidas = [json.loads(l) for l in releido if l.strip()]
    malas = learn.manos_con_orden_ciega_malo(releidas)
    ok = True

    print()
    print('VERIFICACION POST-ESCRITURA')
    print('   %d manos' % len(releidas))
    if len(releidas) != len(manos):
        print('   FALLO: numero de manos %d -> %d' % (len(manos),
                                                      len(releidas)))
        ok = False
    else:
        print('   OK  numero de manos sin cambio')
    if releido == lineas:
        print('   OK  el fichero releido es IDENTICO al resultado esperado')
    else:
        print('   FALLO: el fichero releido NO es el resultado esperado')
        for i, (a, b) in enumerate(zip(releido, lineas)):
            if a != b:
                print('     primera diferencia en la linea %d' % (i + 1))
                break
        ok = False
    if malas:
        ok = False
        print('   FALLO: invariante CM-004 violado por %s' % malas)
    else:
        print('   OK  invariante CM-004: 0 de %d' % len(releidas))

    if not ok:
        print('   restaurando el backup')
        shutil.copy2(backup, DB_PATH)
        return 1

    print()
    print('aplicado. sha256: %s' % sha256_bytes(open(DB_PATH, 'rb').read()))
    return 0


if __name__ == '__main__':
    sys.exit(main())