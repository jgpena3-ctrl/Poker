# -*- coding: utf-8 -*-
"""LOS TESTS DEL CONTRATO DE LA `p` NO SON VACIOS: se muta el motor.

Y lo que este script hace es **romper el motor a proposito** y mirar si los
tests lo notan ✓. Y el motivo de que haga falta: **un test que pasa no dice
nada sobre lo que vigila**, y solo un test que se ha visto fallar dice algo.

Y las tres mutaciones, y cada una rompe UN contrato:

  M1  se quita el salto de las posts en `preflop_events`, de modo que una
      `p` se cuenta como decision;
  M2  `_es_ciega_bb` deja de reconocer la `p` como ciega;
  M3  `entradas_bb_rechazadas` deja de marcar «el BB ya posteo».

## Y LA PUERTA, QUE ES DE SEGURIDAD

Y este script ESCRIBE en `motor/learn.py`, y por eso tiene tres CONDITIONS:

  · **el arbol tiene que estar limpio**, para que la restauracion sea
    verificable y no pise nada de nadie;
  · el original se guarda **en memoria** y se restaura SIEMPRE, en un
    `finally`;
  · y al final se comprueba el **sha** del fichero, y si no coincide, el
    script lo dice y sale con codigo 1.

Y por eso es un instrumento y no un test: muta el motor, y un test que muta
el motor mientras corre la suite es un test que puede dejar el motor roto si
la suite se interrumpe ✓.

```
python tools/mutar_contrato_p.py
```
"""
import hashlib
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEARN = os.path.join(ROOT, 'motor', 'learn.py')

MUTACIONES = [
    ('M1', 'el salto de las posts en `preflop_events`',
     "        if act == 'p':\n",
     "        if act == 'q':\n"),
    ('M2', '`_es_ciega_bb` deja de reconocer la `p` como ciega',
     "if pos == 'BB' and act in ('b', 'p') and not voluntary_before:",
     "if pos == 'BB' and act == 'b' and not voluntary_before:"),
    ('M3', '`entradas_bb_rechazadas` deja de marcar «el BB ya posteo»',
     "            if pos == 'BB' and act == 'p':",
     "            if pos == 'BB' and act == 'q':"),
]

# Y los tests que tienen que notar las tres.
TESTS = ['motor/test_accion_p.py', 'motor/test_cm004.py',
         'motor/test_orden_preflop.py', 'motor/test_ciega_bb.py']


def _git(*args):
    return subprocess.run(['git'] + list(args), cwd=ROOT,
                          capture_output=True, text=True)


def _arbol_limpio():
    r = _git('status', '--porcelain')
    return r.returncode == 0 and not r.stdout.strip()


def _correr():
    return subprocess.run([sys.executable, '-m', 'pytest'] + TESTS + ['-q'],
                          cwd=ROOT, capture_output=True, text=True)


def main():
    if not _arbol_limpio():
        print('EL ARBOL TIENE CAMBIOS, y este script ESCRIBE en motor/learn.py.')
        print()
        print('   Y el motivo de la condicion: la restauracion se verifica con')
        print('   un sha, y con cambios en el arbol ese sha no demuestra nada.')
        print()
        print('   Commitea o guarda lo que tengas y vuelve a lanzarlo.')
        return 2

    original = io.open(LEARN, 'rb').read()
    sha = hashlib.sha256(original).hexdigest()
    resultados = []
    print('1. LA MUTACION: se rompe el motor y se mira si los tests lo notan')
    print()
    try:
        for etiqueta, que, viejo, nuevo in MUTACIONES:
            texto = original.decode('utf-8')
            if texto.count(viejo) != 1:
                print('   MEDIDO, %s: el patron aparece %d veces, y se esperaba 1.'
                      % (etiqueta, texto.count(viejo)))
                print('      O el motor ha cambiado, o la mutacion ya no aplica.')
                resultados.append((etiqueta, None))
                continue
            mutado = texto.replace(viejo, nuevo, 1)
            with io.open(LEARN, 'w', encoding='utf-8', newline='') as f:
                f.write(mutado)
            r = _correr()
            notado = r.returncode != 0
            print('   MEDIDO, %s (%s): %s' % (
                etiqueta, que,
                'LOS TESTS LO NOTAN' if notado
                else '*** LOS TESTS NO LO NOTAN ***'))
            if not notado:
                print('      Y eso es un HUECO: ese contrato no esta vigilado.')
            resultados.append((etiqueta, notado))
            with io.open(LEARN, 'wb') as f:
                f.write(original)
    finally:
        with io.open(LEARN, 'wb') as f:
            f.write(original)

    sha_tras = hashlib.sha256(io.open(LEARN, 'rb').read()).hexdigest()
    igual = sha_tras == sha
    print()
    print('   MEDIDO, el motor restaurado: %s' % ('IGUAL' if igual else
                                                 '*** DISTINTO ***'))
    if not igual:
        print('   Y HAY QUE RESTAURARLO A MANO: git checkout motor/learn.py')
        return 1
    fallos = [e for e, ok in resultados if ok is False]
    if fallos:
        print()
        print('   Y hay %d mutacion(es) que los tests NO notan: %r' % (
            len(fallos), fallos))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
