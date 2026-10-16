# -*- coding: utf-8 -*-
"""El chequeo que sustituye al barrido: SOLO INFORMA.

`INC-003_BARRIDO_DESTRUCTIVO.md`. El barrido anterior recorria 44 ficheros y
BORRABA `§`, `·` y `«»` porque su rango empezaba en U+00A0 y U+00A7 es el
signo de seccion.

Este no escribe nada. Escribe un informe y sale.

La diferencia no es de codigo: es que este pide `--corregir` explicitamente,
y aun asi corrige solo la cadena CONOCIDA, porque un caso conocido se
corrige por nombre y lo desconocido se SENALA.
"""
import argparse
import glob
import io
import os
import subprocess
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Lo que el proyecto USA de verdad. No es contaminacion.
PERMITIDOS = set('·§«»¿¡…—–áéíóúñÁÉÍÓÚÑüÜçÇãõâêô«»«“”„‟')

RANGOS = (
    (0x3000, 0x9FFF, 'CJK'),
    (0x0400, 0x04FF, 'cirilico'),
    (0x0530, 0x058F, 'armenio'),
    (0x4E00, 0x9FFF, 'han'),
    (0xFFFD, 0xFFFD, 'replacement'),
)

# La UNICA correccion automatica. Un caso conocido, por nombre.
CORRECCIONES = {
    'Normalized': 'normalizado',   # una "e" cirilica dentro
}

PATRONES = ('tools/*.py', 'motor/*.py', 'recorder/*.py', 'DOCS/*.md',
            'tests/*.py')


def revisar(patrones=PATRONES):
    """(fichero, caracter, nombre) para cada sospechoso. NO ESCRIBE NADA."""
    hallazgos = []
    for pat in patrones:
        for p in sorted(glob.glob(os.path.join(ROOT, pat))):
            try:
                s = io.open(p, encoding='utf-8').read()
            except (OSError, UnicodeDecodeError):
                continue
            for c in sorted(set(s)):
                if c in PERMITIDOS:
                    continue
                for lo, hi, nombre in RANGOS:
                    if lo <= ord(c) <= hi:
                        hallazgos.append((p, c, nombre))
                        break
    return hallazgos


def en_head(path, c):
    """¿Este carácter ya estaba en la ultima version de git?

    `INC-003`: lo que hay que distinguir no es "raro" de "normal", sino
    "llevaba años aqui" de "se ha colado". Un barrido absoluto borro `§`,
    `·` y `«»` de 44 ficheros, y no puede haber forma de recuperarlos de
    ahi salvo con `git checkout`.
    """
    rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
    try:
        out = subprocess.run(['git', 'show', 'HEAD:' + rel],
                             cwd=ROOT, capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None                      # no se puede saber
    if out.returncode != 0:
        return False                     # el fichero no esta en HEAD
    try:
        antes = out.stdout.decode('utf-8')
    except UnicodeDecodeError:           # pragma: no cover
        return None
    return c in antes


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='verificar_caracteres.py',
        description='Busca caracteres sospechosos. SOLO INFORMA salvo que se '
                    'pida --corregir, y aun asi corrige una unica cadena '
                    'conocida.')
    ap.add_argument('--corregir', action='store_true',
                    help='aplicar las correcciones CONOCIDAS. Lo demas se '
                         'reporta, no se toca.')
    args = ap.parse_args(argv)

    print('=' * 74)
    print('VERIFICACION DE CARACTERES   (solo lectura por defecto)')
    print('=' * 74)
    print()
    print('   INC-003: un barrido anterior borro 44 ficheros porque su rango')
    print('   empezaba en U+00A0 y U+00A7 es el signo de seccion. Este script')
    print('   NO borra nada: enumera lo que el proyecto usa de verdad y solo')
    print('  SENALA lo que se sale de ahi.')
    print()

    permitidos = ''.join(sorted(PERMITIDOS))
    print('   Caracteres permitidos (%d): %s' % (len(PERMITIDOS), permitidos))
    print()

    h = revisar()
    if not h:
        print('   Ningun caracter sospechoso. Correcto.')
        print()
        return 0

    print('   %d hallazgo(s):' % len(h))
    print()
    nuevos = 0
    for p, c, nombre in h:
        rel = os.path.relpath(p, ROOT)
        try:
            nm = unicodedata.name(c)
        except ValueError:                              # pragma: no cover
            nm = 'sin nombre'
        previo = en_head(p, c)
        if previo is True:
            estado = 'PREEXISTENTE'
        elif previo is False:
            estado = '>>> NUEVO <<<'
            nuevos += 1
        else:
            estado = 'sin verificar'
        print('      %-38s %r  U+%04X  %-10s %-13s %s'
              % (rel, c, ord(c), nombre, estado, nm))
    print()
    print('   NUEVOS: %d. Los preexistentes no se tocan: son de antes y no' % nuevos)
    print('   son de este bloque.')
    print()
    print('   Cada uno dice si estaba ya en HEAD o es nuevo. Para eso:')
    print()
    print('       git diff --stat')
    print('       git diff -U0 | grep -n "<caracter>"')
    print()
    print('   Un caracter que NO aparece en el diff es preexistente y NO se')
    print('   toca. Ese es el paso que faltó en INC-003.')

    if args.corregir:
        print()
        print('   Aplicando las correcciones CONOCIDAS (%d): %s'
              % (len(CORRECCIONES), ', '.join(sorted(CORRECCIONES))))
        for pat in PATRONES:
            for p in sorted(glob.glob(os.path.join(ROOT, pat))):
                s = io.open(p, encoding='utf-8').read()
                nuevo = s
                for antes, despues in CORRECCIONES.items():
                    nuevo = nuevo.replace(antes, despues)
                if nuevo != s:
                    io.open(p, 'w', encoding='utf-8', newline='').write(nuevo)
                    print('      corregido: %s' % os.path.relpath(p, ROOT))
        print('   Y nada mas. Lo que no este en CORRECCIONES se SENALA.')
    return 0


if __name__ == '__main__':
    sys.exit(main())