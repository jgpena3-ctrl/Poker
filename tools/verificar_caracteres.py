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
# sin comprobar nada, y decia corregir una "e" cirilica — U+0435 —
# cuando en realidad
#aba algo ASCII. `revision_2` A.
#
# Un caso conocido se corrige por la SECUENCIA EXACTA que lo identifica. Y si
# hay mas de una coincidencia, se reportan todas y NO se escribe nada: dos
# coincidencias ya no son "el caso conocido", son dos casos.
# El defecto documentado es `se` + el U+0435 + `Normalized`. El U+0435 es
# el "ie" cirilico, y escribirlo aqui en crudo contaminaria este
# fichero, que es justo lo que el script existe para senalar. El `{0}` dice
# DONDE va el caracter raro, y se rellena con `chr(0x435)`, el U+0435
# exacto. Escribir el U+0435 aqui en crudo contaminaria este fichero, que es
# justo lo que el script existe para senalar.
#
# Por que el `{0}` y no el nombre entero: antes se derivaba con
# `antes.replace(antes[-1], caracter)`, y `antes[-1]` de `seNormalized` es
# la `d` FINAL. La secuencia que salia era `seNormalize<cirilico>d`: el
# caracter raro en el sitio equivocado, y la correccion NUNCA disparaba
# sobre el caso documentado. `revision_2` §3.
#
# clave            -> (patron con {0}, reemplazo, caracter que debe ser {0})
CORRECCIONES = {
    'se-cirilico-Normalized': ('se{0}Normalized', 'se normalizado',
                               chr(0x435)),
}


def correcciones_de(s):
    """(texto_nuevo, aplicadas, pendientes) para el contenido `s`.

    NO ESCRIBE NADA. Todo el calculo ocurre aqui, sobre la cadena, y el
    llamante escribe UNA vez por fichero si y solo si el texto cambio y no
    hay pendientes. Que la decision se tome antes de abrir el fichero es lo
    que hace que "no escribir" sea de verdad una opcion y no una promesa.
    """
    nuevo, aplicadas, pendientes = s, [], []
    for clave, (patron, reemplazo, caracter) in sorted(CORRECCIONES.items()):
        # La coincidencia TIENE que llevar el caracter raro. Si no lo lleva,
        # es texto legitimo —un `seNormalized` ASCII de verdad— y no se toca.
        bueno = patron.replace('{0}', caracter)
        n = nuevo.count(bueno)
        if n == 0:
            continue
        if n > 1:
            # dos ya no son "el caso conocido", son dos casos
            pendientes.append((clave, bueno, n))
            continue
        nuevo = nuevo.replace(bueno, reemplazo)
        aplicadas.append((clave, bueno, reemplazo))
    return nuevo, aplicadas, pendientes

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


def parsear_hunks(texto):
    """[(linea_nueva, contenido)] de un `git diff -U0`.

    Se separa de `lineas_nuevas()` para poder PROBARLA con un diff
    sintetico de numeros conocidos, que es la unica forma de responder a
    `revision_2` §2 sin discutir: o el numero coincide con el real, o no.

    El numero sale del encabezado `@@ -a,b +c,d @@`, y `c` es la PRIMERA
    linea del lado nuevo de ese bloque. Cada linea anadida consume una.
    Con `-U0` no hay lineas de contexto, que es justo por lo que el
    argumento de `revision_2` ("n puede no corresponder a la linea real del
    siguiente bloque") tiene que medirse: depende de si la rama de contexto
    llega a dispararse alguna vez.
    """
    nuevas = []
    n = None
    for linea in texto.split('\n'):
        if linea.startswith('@@'):
            try:
                n = int(linea.split('+')[1].split(',')[0].split()[0])
            except (IndexError, ValueError):       # pragma: no cover
                n = None
        elif n is not None and linea.startswith('+') \
                and not linea.startswith('+++'):
            nuevas.append((n, linea[1:]))
            n += 1
        elif n is not None and linea.startswith('-') \
                and not linea.startswith('---'):
            continue                     # una linea borrada no avanza el numero
        elif n is not None and linea.startswith(' '):
            n += 1                      # solo con -U (no con -U0)
    return nuevas


def lineas_nuevas(path):
    """Las lineas que el CAMBIO anade, con su numero de linea.

    `revision_2` A: preguntar "¿este caracter estaba en HEAD?" no basta. Si
    ya estaba en otro parrafo del fichero, una aparicion NUEVA en el codigo
    sale clasificada como PREEXISTENTE y se pierde justo lo que se busca.

    La pregunta correcta es ¿este hallazgo pertenece al cambio? Y se
    responde con las lineas que `git diff` anade.
    """
    rel = os.path.relpath(path, ROOT).replace(os.sep, '/')

    # ---- caso 1: fichero SIN SEGUIMIENTO. `git diff` no lo ve, y sin esto
    # un fichero creado en este bloque salia PREEXISTENTE.
    estado = _porcelain(rel)
    if estado is None:
        return None
    if '??' in estado:
        try:
            contenido = io.open(path, encoding='utf-8').read()
        except (OSError, UnicodeDecodeError):        # pragma: no cover
            return None
        return list(enumerate(contenido.split('\n'), 1))

    nuevas = []
    # ---- caso 2: zona de TRABAJO. `git diff` la ve.
    for argv in (['git', 'diff', '-U0', '--', rel],
                 # y la zona INDICE, que `git diff` no mira: un fichero
                 # staged sale como sin cambios
                 ['git', 'diff', '--cached', '-U0', '--', rel]):
        try:
            out = subprocess.run(argv, cwd=ROOT,
                                 capture_output=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return None
        if out.returncode != 0:
            return None
        try:
            texto = out.stdout.decode('utf-8')
        except UnicodeDecodeError:                   # pragma: no cover
            return None
        nuevas.extend(parsear_hunks(texto))

    # el mismo numero puede aparecer en las dos zonas: se ordena y se quita
    # repetidos, y la clasificacion no cambia por eso
    vistas = set()
    return [x for x in sorted(nuevas) if not (x in vistas or vistas.add(x))]


def _porcelain(rel):
    """La linea de `git status --porcelain` de este fichero, o None."""
    try:
        out = subprocess.run(['git', 'status', '--porcelain', '--', rel],
                             cwd=ROOT, capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    try:
        return out.stdout.decode('utf-8', 'replace').strip()
    except Exception:                                # pragma: no cover
        return None


def en_cambio(path, c):
    """(estado, [lineas]) — ¿esta aparicion la ha anadido el cambio?

    Se devuelven TODAS las lineas anadidas que contienen `c`, no la
    primera. La clasificacion no cambia por eso, pero el informe tiene que
    poder senalar las dos: si un bloque anade el mismo caracter en tres
    sitios, decir "linea 4" deja a los otros dos sin senalar.
    """
    nuevas = lineas_nuevas(path)
    if nuevas is None:
        return None, []
    lineas = [n for n, texto in nuevas if c in texto]
    return (True, lineas) if lineas else (False, [])


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
        en_el_cambio, lineas = en_cambio(p, c)
        if en_el_cambio is True:
            estado = '>>> DEL CAMBIO <<<'
            nuevos += 1
            donde = 'lineas %s' % ', '.join(str(n) for n in lineas)
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
                # TODO se decide ANTES de abrir el fichero para escribir: la
                # funcion no toca el disco, y el llamante escribe una vez.
                nuevo, apl, pend = correcciones_de(s)
                pendientes.extend((p,) + x for x in pend)
                if nuevo == s:
                    continue
                if pend:
                    # una secuencia con mas de una coincidencia bloquea el
                    # fichero ENTERO: revisar a medias deja el resto sin
                    # validar. `revision_2` §3.
                    print('      NO se escribe: %s  (%d secuencia(s) con mas '
                          'de una coincidencia)'
                          % (os.path.relpath(p, ROOT), len(pend)))
                    continue
                io.open(p, 'w', encoding='utf-8', newline='').write(nuevo)
                aplicadas += len(apl)
                for _clave, bueno, reemplaza in apl:
                    print('      corregido: %s  (%r -> %r)'
                          % (os.path.relpath(p, ROOT), bueno, reemplaza))
        if pendientes:
            print()
            print('   %d coincidencia(s) de mas, NO se corrigen: dos o mas ya'
                  % len(pendientes))
            print('   no son "el caso conocido". A revision:')
            for p, clave, txt, n in pendientes:
                print('      %-36s %-22s %r  x%d'
                      % (os.path.relpath(p, ROOT), clave, txt, n))
        print('   Aplicadas: %d. Y nada mas: lo que no este en CORRECCIONES'
              % aplicadas)
        print('   se SENALA.')
    return 0


if __name__ == '__main__':
    sys.exit(main())