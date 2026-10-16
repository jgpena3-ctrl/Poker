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

# La UNICA correccion automatica, y por SECUENCIA DE CARACTERES.
#
# Antes era `{'Normalized': 'normalizado'}`: una sustitucion de texto ASCII
# que, ademas, hacia las DOS COSAS mal. Sustituia todas las apariciones
# sin comprobar nada, y decia corregir una `е` cirilica cuando en realidad
#aba algo ASCII. `revision_2` A.
#
# Un caso conocido se corrige por la SECUENCIA EXACTA que lo identifica. Y si
# hay mas de una coincidencia, se reportan todas y NO se escribe nada: dos
# coincidencias ya no son "el caso conocido", son dos casos.
CORRECCIONES = {
    'seNormalized': ('se normalizado',
                     # el caracter que tiene que ser el cirilico U+0435
                     chr(0x435)),
}

PREFIJOS = ('tools/', 'motor/', 'recorder/', 'DOCS/', 'tests/')

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


def lineas_nuevas(path):
    """Las lineas que el CAMBIO anade, con su numero de linea.

    `revision_2` A: preguntar "¿este caracter estaba en HEAD?" no basta. Si
    ya estaba en otro parrafo del fichero, una aparicion NUEVA en el codigo
    sale clasificada como PREEXISTENTE y se pierde justo lo que se busca.

    La pregunta correcta es ¿este hallazgo pertenece al cambio? Y se
    responde con las lineas que `git diff` anade.
    """
    rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
    try:
        out = subprocess.run(
            ['git', 'diff', '-U0', '--', rel],
            cwd=ROOT, capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    try:
        texto = out.stdout.decode('utf-8')
    except UnicodeDecodeError:           # pragma: no cover
        return None
    nuevas = []
    for linea in texto.split('\n'):
        if linea.startswith('@@'):
            # @@ -a,b +c,d @@   -> c es la primera linea nueva
            try:
                c = int(linea.split('+')[1].split(',')[0].split()[0])
            except (IndexError, ValueError):       # pragma: no cover
                continue
            n = 1
        elif linea.startswith('+') and not linea.startswith('+++'):
            nuevas.append((n, linea[1:]))
            n += 1
        elif linea.startswith(' '):
            n += 1
    return nuevas


def en_cambio(path, c):
    """(estado, linea) — ¿esta aparicion la ha anadido el cambio?"""
    nuevas = lineas_nuevas(path)
    if nuevas is None:
        return None, None
    for n, texto in nuevas:
        if c in texto:
            return True, n
    return False, None


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
        en_el_cambio, linea = en_cambio(p, c)
        if en_el_cambio is True:
            estado = '>>> DEL CAMBIO <<<'
            nuevos += 1
            donde = 'linea %d' % linea
        elif en_el_cambio is False:
            estado = 'PREEXISTENTE'
            donde = ''
        else:
            estado = 'sin verificar'
            donde = ''
        print('      %-38s %r  U+%04X  %-10s %-16s %s  %s'
              % (rel, c, ord(c), nombre, estado, nm, donde))
    print()
    print('   DEL CAMBIO: %d. Los preexistentes no se tocan: son de antes' % nuevos)
    print('   y no son de este bloque.')
    print()
    print('   La diferencia con la version anterior: preguntar "¿este caracter')
    print('   estaba en HEAD?" no basta, porque si ya estaba en otro parrafo')
    print('   una aparicion NUEVA en el codigo salia PREEXISTENTE. Aqui se')
    print('   miran las LINEAS que el diff anade.')
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
        aplicadas = 0
        pendientes = []
        for pat in PATRONES:
            for p in sorted(glob.glob(os.path.join(ROOT, pat))):
                s = io.open(p, encoding='utf-8').read()
                for antes, (despues, caracter) in CORRECCIONES.items():
                    # la coincidencia TIENE que llevar el caracter raro. Si no,
                    # es texto legitimo y no se toca.
                    bueno = antes.replace(antes[-1], caracter)
                    n = s.count(bueno)
                    if n == 0:
                        continue
                    if n > 1:
                        pendientes.append((p, bueno, n))
                        continue
                    s = s.replace(bueno, despues)
                    io.open(p, 'w', encoding='utf-8', newline='').write(s)
                    aplicadas += 1
                    print('      corregido: %s  (%r -> %r)'
                          % (os.path.relpath(p, ROOT), bueno, despues))
        if pendientes:
            print()
            print('   %d coincidencia(s) de mas, NO se corrigen: dos o mas ya'
                  % len(pendientes))
            print('   no son "el caso conocido". A revision:')
            for p, txt, n in pendientes:
                print('      %-36s %r  x%d'
                      % (os.path.relpath(p, ROOT), txt, n))
        print('   Aplicadas: %d. Y nada mas: lo que no este en CORRECCIONES'
              % aplicadas)
        print('   se SENALA.')
    return 0


if __name__ == '__main__':
    sys.exit(main())