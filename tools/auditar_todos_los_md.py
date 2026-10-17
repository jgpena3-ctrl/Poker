# -*- coding: utf-8 -*-
"""El barrido de TODOS los `.md` del repositorio.

POR QUE ESTA EN EL REPO Y NO EN UN SCRIPT DE TEMPORAL

La regla vive en `retraccion_scan` y la comprobaba sobre **cuatro**
documentos. Los otros **55** nunca se habian mirado.

Y eso es un agujero con forma: una cifra repetida aparece en todas partes, en
un plan, en un informe, en una nota al pie. Si la cuarta correccion llego a
los cuatro documentos que se Haber leido, no hay ninguna razon para que este
llegue a los demas.

La primera vez que se ejecuto, senalo UN documento mas —`FASE_D_PLAN.md`,
que dice `| TOTAL | 78 |`— y era un falso positivo: ese 78 es el total de
cuatro defectos de datos, no las positivas preflop. Se resolvio mirando el
encabezado de la tabla, que es donde esta el sujeto.

Un barrido que senala una linea correcta es peor que uno que no senala nada,
porque entrena a ignorar. Y eso ya habia pasado dos veces en este bloque con
las negaciones.

LO QUE NO HACE

  - no toca ficheros. Este script solo LEE. Escribir en un documento que
    revisa es lo que hizo INC-003, y no se repite.
  - no excluye los `.pytest_cache`: no hay ningun `README.md` de pytest que
   (versionado). Se listan pero no se auditan si no son del repo.

COMO SE USA

    python tools/auditar_todos_los_md.py

Sale 0 si ningun documento afirma una frase retirada.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from retraccion_scan import (                              # noqa: E402
    LOS_TRES, RETIRADAS, frases_retiradas_en)

# Los que ya tienen auditoria propia, y su regla esta probada sobre ellos.
CON_AUDITAR_PROPIA = LOS_TRES

# Un numero dentro de una fila de tabla no significa nada sin el encabezado,
# y hay numeros que coinciden y no son el mismo numero. Anadidos aqui con su
# sujeto, para que el filtro de sujeto los descarte.
#
# Y NO `48 con etiqueta`: esa es la cifra VIGENTE del postflop, la que
# publica el AUC. Meterla en las retiradas hace que el barrido senale el
# numero correcto, y eso solo se ve con un test que meta una CITA y
# compruebe que no la senala: un numero correcto citado tampoco es una
# violacion afirmada, es una violacion citada.
RETIRADAS_EXTRA = RETIRADAS + (
    ('tres pares', 'es dos pares y el tablero entero: el ranking cambio'),
)


def _md_del_repo(raiz=None):
    raiz = raiz or ROOT
    out = []
    for d, sub, archivos in os.walk(raiz):
        # fuera de `.git` y de cualquier cache
        if '.git' in sub or '.pytest_cache' in d or '__pycache__' in d:
            continue
        for n in sorted(archivos):
            if n.endswith('.md'):
                out.append(os.path.relpath(os.path.join(d, n), raiz))
    return sorted(out)


def _leer(rel, raiz=None):
    with io.open(os.path.join(raiz or ROOT, rel), encoding='utf-8') as f:
        return f.read()


def auditar_todos(frases=None, raiz=None):
    """[(fichero, [(linea, frase, texto_de_la_linea)])]

    `raiz` existe para que un test pueda meter un arbol con una violacion y
    comprobar que el barrido la ve. Un barrido que no se puede provocar no se
    sabe si vigila o si esta roto.
    """
    frases = frases or RETIRADAS_EXTRA
    salida = []
    for rel in _md_del_repo(raiz):
        try:
            texto = _leer(rel, raiz)
        except (IOError, OSError, UnicodeDecodeError) as e:
            print('   no se puede leer %s: %s' % (rel, e))
            continue
        malas, _citadas = frases_retiradas_en(texto, frases)
        if malas:
            salida.append((rel, malas))
    return salida


def main():
    todos = _md_del_repo()
    sin_auditar = [t for t in todos
                   if os.path.basename(t) not in CON_AUDITAR_PROPIA]
    print('=' * 78)
    print('TODOS LOS .md DEL REPOSITORIO')
    print('=' * 78)
    print('   %d documentos.  Con auditoria propia: %d.  Sin ella: %d'
          % (len(todos), len(todos) - len(sin_auditar), len(sin_auditar)))

    print()
    print('=' * 78)
    print('FRASES RETIRADAS AFIRMADAS')
    print('=' * 78)
    salida = auditar_todos()
    if not salida:
        print('   ninguna, en ninguno de los %d' % len(todos))
    for rel, malas in salida:
        print()
        print('   %s' % rel)
        for i, frase, linea in malas:
            ctx = dict(RETIRADAS_EXTRA).get(frase, '')
            print('      %4d  [%s]' % (i, frase))
            print('            %s' % linea)
            print('            por que se retira: %s' % ctx)
    print()
    print('   documentos con al menos una: %d' % len(salida))
    return 1 if salida else 0


if __name__ == '__main__':
    sys.exit(main())