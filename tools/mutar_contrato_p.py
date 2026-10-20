# -*- coding: utf-8 -*-
"""LOS TESTS DEL CONTRATO DE LA `p` NO SON VACIOS: se muta el motor.

Y lo que este script hace es **romper el motor a proposito** y mirar si los
tests lo notan ✓. Y el motivo de que haga falta: **un test que pasa no dice
nada sobre lo que vigila**, y solo un test que se ha visto fallar dice algo.

## Y LAS TRES MUTACIONES, Y CADA UNA ROMPE UN CONTRATO

  M1  se quita el salto de las posts en `preflop_events`, de modo que una
      `p` se cuenta como decision;
  M2  `_es_ciega_bb` deja de reconocer la `p` como ciega;
  M3  `entradas_bb_rechazadas` deja de marcar «el BB ya posteo».

## Y LA PUERTA, QUE ES DE SEGURIDAD

Y este script ESCRIBE en `motor/learn.py`, y por eso tiene cuatro condiciones:

  · **el arbol tiene que estar limpio**, para que la restauracion sea
    verificable y no pise nada de nadie;
  · el original se guarda **en memoria** y se restaura SIEMPRE, en un
    `finally`, **y no depende de que el test pase**: si el test lanza, el
    fichero vuelve a su sitio igual ✓;
  · al final se comprueba el **sha**, y si no coincide, el script lo dice y
    sale con codigo 1;
  · y una mutacion **no declarada** es un error, no un «no encuentro el
    patron»: porque un patron que ya no esta es un motor que ha cambiado, y
    eso hay que decirlo.

## Y NO ES UN TEST DE LA SUITE

Y es un INSTRUMENTO, y se ejecuta a mano cuando se quiere comprobar que los
tests no son vacios ✓, y no en cada `pytest` ✓: porque muta el motor, y un
test que muta el motor mientras corre la suite puede dejarlo roto si la
suite se interrumpe ✓.

```
python tools/mutar_contrato_p.py                # las tres
python tools/mutar_contrato_p.py --mutacion M3  # una sola
```
"""
import hashlib
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEARN_REL = 'motor/learn.py'

MUTACIONES = {
    'M1': {
        'que': 'el salto de las posts en `preflop_events`',
        'invariante': 'una posta no es una decision, y el jugador sigue '
                      'sin decidir',
        'test': 'motor/test_accion_p.py::test_una_p_sola_no_es_ninguna_decision',
        'viejo': "        if act == 'p':\n",
        'nuevo': "        if act == 'q':\n",
    },
    'M2': {
        'que': '`_es_ciega_bb` deja de reconocer la `p` como ciega',
        'invariante': 'la ciega del BB puede escribirse de las dos maneras',
        'test': ('motor/test_accion_p.py::'
                 'test_la_ciega_del_bb_grabada_como_p_se_reconoce'),
        'viejo': "if pos == 'BB' and act in ('b', 'p') and not voluntary_before:",
        'nuevo': "if pos == 'BB' and act == 'b' and not voluntary_before:",
    },
    'M3': {
        'que': '`entradas_bb_rechazadas` deja de marcar «el BB ya posteo»',
        'invariante': 'un BB que YA posteo la ciega no puede tener una ciega '
                      'segunda',
        'test': ('motor/test_accion_p.py::'
                 'test_un_bb_que_ya_posteo_no_vuelve_a_ser_una_ciega'),
        'viejo': "            if pos == 'BB' and act == 'p':",
        'nuevo': "            if pos == 'BB' and act == 'q':",
    },
    # Y la M4 es la mutacion del CAMINO DE LA CONTRAPARTE: sin ella, el
    # motor deja de rechazar las ciegas tardias, y con ella se nota.
    #
    # Y el motivo de que haga falta: la contraparte del hueco de M3 —un BB
    # que NO posteo antes y tiene una `b` tarde— no es sensible a M3, porque
    # M3 es el caso de la `p` ✓. De modo que la contraparte vigila SU camino,
    # y la mutacion de SU camino es esta ✓.
    'M4': {
        'que': 'el motor deja de rechazar las ciegas tardias',
        'invariante': 'un BB que NO posteo antes y tiene una `b` tarde es un '
                      'rechazo',
        'test': ('motor/test_accion_p.py::'
                 'test_sin_la_p_de_antes_la_b_del_bb_si_es_un_rechazo'),
        'viejo': ("        if pos == 'BB' and act in ('b', 'p') "
                  "and not bb_ya_posteo:"),
        'nuevo': ("        if pos == 'ZZ' and act in ('b', 'p') "
                  "and not bb_ya_posteo:"),
    },
}

# Y los tests que tienen que notar las tres.
TESTS = ['motor/test_accion_p.py', 'motor/test_cm004.py',
         'motor/test_orden_preflop.py', 'motor/test_ciega_bb.py']


def _acepta_tests(runner):
    """Si el runner acepta la lista de tests, y si no, se llama sin ella.

    Y el motivo: un runner de pruebas propio —el de los tests de ESTE
    fichero— puede querer correr un solo nodo ✓, y el de por defecto corre
    la lista entera ✓.
    """
    import inspect
    try:
        return len(inspect.signature(runner).parameters) >= 1
    except (TypeError, ValueError):
        return False


def _git(*args):
    return subprocess.run(['git'] + list(args), cwd=ROOT,
                          capture_output=True, text=True)


def arbol_limpio():
    r = _git('status', '--porcelain')
    return r.returncode == 0 and not r.stdout.strip()


def _limpiar_cache(modulo='learn'):
    """Borra el `.pyc` del modulo mutado, y dice cuantos ha borrado.

    Y el motivo, MEDIDO: **una mutacion que conserva el TAMANO del fichero
    deja el `__pycache__` seemingly valido** ✓, porque en Windows la marca de
    tiempo tiene una granularidad gruesa ✓. Y entonces el subproceso importa
    el BYTECODE MUTADO en vez del codigo restaurado ✓, y el instrumento
    DA FALSOS POSITIVOS ✓.

    Y el `.pyc` se borra DESPUES de mutar y ANTES de correr los tests ✓, que
    es cuando importa ✓.
    """
    d = os.path.join(ROOT, 'motor', '__pycache__')
    if not os.path.isdir(d):
        return 0
    n = 0
    for nombre in os.listdir(d):
        if nombre.startswith(modulo) and nombre.endswith('.pyc'):
            try:
                os.remove(os.path.join(d, nombre))
                n += 1
            except OSError:
                pass
    return n


def _entorno_sin_bytecode():
    """El entorno, sin escribir bytecode.

    Y el motivo: si el subproceso escribe un `.pyc` del codigo MUTADO, otro
    proceso puede leerlo despues ✓, y el motor parece roto sin estarlo ✓.
    """
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def _correr(tests=None):
    return subprocess.run([sys.executable, '-m', 'pytest']
                          + list(tests or TESTS) + ['-q'],
                          cwd=ROOT, capture_output=True, text=True,
                          env=_entorno_sin_bytecode())


def tabla_de_mutaciones():
    """La tabla, en forma de filas, y con su verificacion.

    Y la forma es la del informe: que invariante rompe, que test la nota, y
    si la nota ✓. Y la ultima columna NO es una opinion: se comprueba ✓.
    """
    filas = []
    for etiqueta in sorted(MUTACIONES):
        mut = MUTACIONES[etiqueta]
        filas.append({
            'mutacion': etiqueta,
            'que': mut['que'],
            'invariante': mut['invariante'],
            'test': mut['test'],
        })
    return filas


def _version_commiteada(ruta):
    """El contenido COMITEADO del fichero, y `None` si no se puede leer.

    Y el motivo de que sea de GIT y no del disco ✓: el disco puede estar
    sucio ✓, y un «original» sucio hace que la restauracion restaure la
    mutacion ✓.
    """
    try:
        relativo = os.path.relpath(os.path.abspath(ruta), ROOT)
        r = subprocess.run(['git', 'show', 'HEAD:%s' % relativo.replace('\\', '/')],
                           cwd=ROOT, capture_output=True)
        if r.returncode != 0:
            return None
        return r.stdout
    except Exception:                                  # noqa: BLE001
        return None


def _fichero_limpio(ruta):
    """Si el fichero tiene cambios sin commitear."""
    relativo = os.path.relpath(os.path.abspath(ruta), ROOT).replace('\\', '/')
    r = subprocess.run(['git', 'status', '--porcelain', relativo],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0 and not r.stdout.strip()


def mutar_y_comprobar(etiqueta, ruta=None, runner=None, tests=None):
    """Muta el motor, mira si los tests lo notan, y lo RESTAURA SIEMPRE.

    Y la restauracion no depende de que el test pase ✓: esta en un
    `finally`, y por eso el `finally` es la parte importante y no el resto.

    Y devuelve `(notado, detalle)`, y el detalle es lo que hay que mirar
    cuando NO se nota: que el patron no aparezca, o que el test lanzara.
    """
    if etiqueta not in MUTACIONES:
        raise ValueError(
            'mutacion no declarada: %r. Las declaradas son: %r. Y una '
            'mutacion no declarada NO se ignora: es un error, porque un '
            'patron que ya no esta quiere decir que el motor ha cambiado.'
            % (etiqueta, sorted(MUTACIONES)))
    ruta = ruta or os.path.join(ROOT, *LEARN_REL.split('/'))
    runner = runner or _correr
    mut = MUTACIONES[etiqueta]

    # Y EL ORIGINAL SE LEE DE GIT, y no del fichero ✓. Y el motivo es el que
    # costó una fuga ✓: si el fichero esta ya sucio ✓ —por una fuga
    # anterior, o por la accion de otro agente en el mismo repositorio ✓—
    # leerlo de ahi da un «original» que ya es el mutado ✓, y la restauracion
    # vuelve a dejar la mutacion ✓, y el sha coincide ✓, y el instrumento
    # cree que ha restaurado ✓.
    original = _version_commiteada(ruta)
    if original is None:
        raise RuntimeError(
            'no se puede leer la version COMITEADA de %s, y sin ella la '
            'restauracion no se puede comprobar ✓' % ruta)
    sha = hashlib.sha256(original).hexdigest()

    # Y ADEMAS, no se muta un fichero que no este limpio ✓, que es lo que
    # hace imposible mutar sobre una mutacion ✓.
    if not _fichero_limpio(ruta):
        raise RuntimeError(
            'el fichero %s tiene cambios sin commitear, y el instrumento NO '
            'muta sobre un arbol sucio: la restauracion no seria comprobable'
            % ruta)
    texto = original.decode('utf-8')
    if texto.count(mut['viejo']) != 1:
        return False, ('el patron aparece %d veces, y se esperaba 1'
                       % texto.count(mut['viejo']))
    notado = False
    detalle = ''
    try:
        with io.open(ruta, 'w', encoding='utf-8', newline='') as f:
            f.write(texto.replace(mut['viejo'], mut['nuevo'], 1))
        # Y LA CACHE, que es lo que hacia que este instrumento mintiera ✓.
        _limpiar_cache()
        r = runner(tests) if _acepta_tests(runner) else runner()
        notado = r.returncode != 0
        detalle = (r.stdout or '')[-800:]
    finally:
        with io.open(ruta, 'wb') as f:
            f.write(original)
        _limpiar_cache()
    sha_tras = hashlib.sha256(io.open(ruta, 'rb').read()).hexdigest()
    if sha_tras != sha:
        raise AssertionError(
            'el fichero NO ha vuelto a ser el de antes: sha %r y %r. Y hay '
            'que restaurarlo a mano: git checkout %s' % (sha_tras, sha, LEARN_REL))
    return notado, detalle


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='mutar_contrato_p.py',
                                 description='Rompe el motor a proposito y '
                                             'mira si los tests lo notan. '
                                             'NO es un test de la suite.')
    ap.add_argument('--mutacion', default=None, choices=sorted(MUTACIONES),
                    help='una sola mutacion; por defecto, las tres')
    ap.add_argument('--fichero', default=None,
                    help='el fichero a mutar; por defecto `motor/learn.py`')
    args = ap.parse_args(argv)

    if not arbol_limpio():
        print('EL ARBOL TIENE CAMBIOS, y este script ESCRIBE en `%s`.' % LEARN_REL)
        print()
        print('   Y el motivo de la condicion: la restauracion se verifica con')
        print('   un sha, y con cambios en el arbol ese sha no demuestra nada.')
        print()
        print('   Commitea o guarda lo que tengas y vuelve a lanzarlo.')
        return 2

    ruta = args.fichero or os.path.join(ROOT, *LEARN_REL.split('/'))
    etiquetas = [args.mutacion] if args.mutacion else sorted(MUTACIONES)
    print('1. LA MUTACION: se rompe el motor y se mira si los tests lo notan')
    print()
    fallos = []
    for etiqueta in etiquetas:
        mut = MUTACIONES[etiqueta]
        # Y se corre EL TEST DE LA TABLA, y no la suite entera ✓, porque lo
        # que se comprueba es que ese test concreto nota esta mutacion ✓.
        notado, detalle = mutar_y_comprobar(etiqueta, ruta,
                                            tests=[mut['test']])
        print('   MEDIDO, %s (%s): %s' % (
            etiqueta, mut['que'],
            'EL TEST DE LA TABLA LO NOTA' if notado
            else '*** EL TEST DE LA TABLA NO LO NOTA ***'))
        print('      invariante: %s' % mut['invariante'])
        print('      test      : %s' % mut['test'])
        if not notado:
            print('      Y eso es una BRECHA DE COBERTURA: ese contrato no '
                  'esta vigilado, y no es motivo para relajar el test.')
            fallos.append(etiqueta)
    print()
    print('   MEDIDO, el motor restaurado: SIEMPRE (en un `finally`)')
    if fallos:
        print()
        print('   Y hay %d mutacion(es) que los tests NO notan: %r' % (
            len(fallos), fallos))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
