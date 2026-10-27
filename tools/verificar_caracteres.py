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
import re
import subprocess
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Lo que el proyecto USA de verdad. No es contaminacion.
#
# Y el `U+FE0F` va aqui con `chr()`, y no escrito en crudo, por el mismo
# motivo que el U+0435 de mas abajo: un selector de variacion no es
# imprimible, de modo que la regla de «lo invisible es sospechoso» lo
# senalaria, y el fichero se contaminaria paraSENALAR una contaminacion.
PERMITIDOS = set('·§«»¿¡…—–áéíóúñÁÉÍÓÚÑüÜçÇãõâêô«»«“”„‟'
                  + chr(0xFE0F))

# ---------------------------------------------------------------------------
# LA REGLA, y por que no son RANGOS
# ---------------------------------------------------------------------------
#
# Antes esta regla eran RANGOS de puntos de codigo, escritos a mano. Y un
# rango escrito a mano se queda corto sin que nada se note. MEDIDO: el de
# este fichero NO incluia el ARABE (U+0600..U+06FF), y en el repo habia
# TRES caracteres arabes. Y un rango que se queda corto no avisa: devuelve
# cero hallazgos, que es un verde.
#
# Y la regla que lo sustituye se decide por el NOMBRE Unicode del caracter,
# que dice QUE ES el caracter. Y el nombre tiene una forma:
#
#     LATIN SMALL LETTER A WITH ACUTE   ->  LATIN, permitido
#     CYRILLIC SMALL LETTER O           ->  LETTER de otro alfabeto
#     ARABIC LETTER TEH                 ->  LETTER de otro alfabeto
#     THAI CHARACTER KO KAI             ->  CHARACTER de otro alfabeto
#     GREEK SMALL LETTER TAU            ->  GREEK, permitido
#     HANGUL SYLLABLE GA                ->  sin LETTER: hay que nombrarlo
#     CJK UNIFIED IDEOGRAPH-4E00        ->  sin LETTER: hay que nombrarlo
#     RIGHTWARDS ARROW                  ->  un simbolo, no un sistema
#
# De ahi sale todo, y sale SIN enumerar rangos.

# Los alfabetos que el proyecto USA. Y son dos, y sale de medir el repo
# entero, no de suponerlo: LATIN, y GREEK —que se usa como notacion
# matematica—. MEDIDO: no hay ni una letra de otro alfabeto que sea
# legitima en el repo.
ALFABETOS_USADOS = ('LATIN', 'GREEK')

# Y los sistemas cuyos caracteres NO se llaman LETTER, que hay que
# nombrarlos aparte. Y son cuatro: HANGUL (SYLLABLE), CJK (UNIFIED
# IDEOGRAPH), YI (SYLLABLE) e IDEOGRAPHIC (la puntuacion CJK).
SISTEMAS_SIN_LETRAS = ('CJK', 'HANGUL', 'YI', 'IDEOGRAPHIC')

# La puntuacion de Unicode, que SI puede aparecer y es legitima: son las
# rayas, las comillas angulares y los puntos suspensivos.
PUNTUACION_UNICODE = (0x2000, 0x206F)

# Y las excepciones POR SITIO, y no por caracter.
#
# MEDIDO, el motivo de que sean por sitio: el U+0435 cirilico del ejemplo de
# `DOCS/INC-003_BARRIDO_DESTRUCTIVO.md` es INTENCIONADO —lo dice el propio
# documento— y el MISMO caracter en `motor/test_canal_manual.py` es una
# corrupcion. Una excepcion por caracter los taparia a los dos.
EXCEPCIONES = (
    ('DOCS/INC-003_BARRIDO_DESTRUCTIVO.md', chr(0x435)),
)


# Los hallazgos que YA se sabian, y que se DECLARAN en vez de tocarse.
#
# Y el motivo de que esto sea un NUMERO y no una lista de ficheros: lo que se
# vigila es que no CREZCAN, y una lista de ficheros seria una lista escrita a
# mano, que se queda corta sin que nada se note. Y el detalle —que caracter,
# en que fichero, y por que no se toca— esta en
# `DOCS/HALLAZGOS_DECLARADOS.md`, que es donde esta la DECLARACION.
#
# Y el numero no es de este bloque: es el que hay. MEDIDO, y la regla es la
# de `DOCS/HALLAZGOS_DECLARADOS.md`: lo preexistente se declara y se
# reporta, y no se toca; lo del cambio se arregla.
#
# Y un hallazgo que se ARREGLA baja este numero, y el test falla, y hay que
# subir la constante a mano. Y eso es lo que se quiere: que quitar un
# defecto sea una decision, y no un efecto secundario.
#
# Y MEDIDO, y por que estuvo en 13 y ha vuelto a 11: al extender el alcance
# del barrido a la raiz del repo y a `trabajo/`, aparecieron DOS, en
# `APUESTAS_DIFICILES.md` —dos ideogramas chinos pegados a un numero, en un
# documento en espanol—. Y se han ARREGLADO, porque la columna de esa tabla es
# el numero, y el numero era un 0. De modo que los dos ideogramas no eran una
# marca: eran una errata.
#
# Y el motivo por el que se arreglan y no se declaran: **un hallazgo del
# barrido es un defecto, y una excepcion es un hueco**. Un `.md` con dos
# ideogramas chinos pegados a un numero no es una decision del autor: es una
# errata, y se quita.
SOSPECHOSOS_ABAJO = 12

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

# Y el alcance, y por que esta asi.
#
# MEDIDO, lo que hay FUERA de las tres carpetas del inventario:
#
#     los .py de la raiz y de `trabajo/` : 2, y los dos LIMPIOS
#     los .md de la raiz y de `trabajo/` : 7, y uno con dos caracteres chinos
#     los .jsonl de `trabajo/`            : 3, y los tres limpios
#
# Y la decision: **se extiende el alcance y se DECLARA lo que aparezca**, en
# vez de ampliar la lista de excepciones. Un fichero que nadie vigila es un
# fichero que nadie lee.
#
# Y los `.txt` de la raiz quedan FUERA, y el motivo es el de siempre: la
# politica de exclusion de los `.txt` es que pueden estar en UTF-16LE, y leidos
# como texto dan un caracter de control por cada letra. MEDIDO, los de ESTA
# raiz estan en UTF-8 y limpios, de modo que incluirlos no costaria nada: pero
# la politica es de los `.txt` en general, y se cambia para todos o para
# ninguno.
#
# Y el `.csv` tambien queda fuera, y el motivo es que no es codigo ni
# documentacion del motor: es una tabla de datos.
#
# Y los `.py`, los `.md` y los `.jsonl` que estan FUERA de las carpetas del
# inventario SI se vigilan, y se DECLARAN uno a uno en
# `tools/test_ejecutar_pytest.py`, que es donde esta la lista y el guardian.
PATRONES = ('tools/*.py', 'motor/*.py', 'recorder/*.py', 'DOCS/*.md',
            'tests/*.py',
            '*.py', 'trabajo/*.py', '*.md', 'trabajo/*.md',
            '*.jsonl', 'trabajo/*.jsonl')


def _coincide_con(patron, rel):
    """Si un fichero, con su ruta RELATIVA, casa con un patron de `PATRONES`.

    Y la semantica es la de `glob`: el asterisco NO cruza la barra. De modo
    que `*.py` casa con `hand_editor.py` y NO con `trabajo/x.py`, que es lo
    que hace `glob.glob` y lo que hace `fnmatch` NO.

    Y por que hace falta: para comprobar que un fichero DECLARADO esta de
    verdad bajo el barrido. Y un `fnmatch` de los ordinarios daria la
    respuesta equivocada, porque su asterisco cruza la barra.
    """
    rx = '^' + re.escape(patron).replace('\\*', '[^/]*') + '$'
    return re.match(rx, rel) is not None


def revisar(patrones=None):
    """(fichero, caracter, nombre) para cada sospechoso. NO ESCRIBE NADA.

    `patrones=None` significa "usa PATRONES, LEIDA AHORA". Antes era
    `patrones=PATRONES`, que se evalua al importar: cambiar la constante no
    cambiaba lo que se escanea, y como `main()` sale antes de `--corregir`
    cuando no hay hallazgos, la correccion quedaba colgando de un valor
    congelado y la herramienta no se podia probar.
    """
    if patrones is None:
        patrones = PATRONES
    hallazgos = []
    for pat in patrones:
        for p in sorted(glob.glob(os.path.join(ROOT, pat))):
            try:
                s = io.open(p, encoding='utf-8').read()
            except (OSError, UnicodeDecodeError):
                continue
            for c in sorted(set(s)):
                nombre = _sospechoso(c, p)
                if nombre is not None:
                    hallazgos.append((p, c, nombre))
    return hallazgos


def _sospechoso(c, ruta=None):
    """El nombre de POR QUE este caracter es sospechoso, o None si no lo es.

    Y la regla, que son CUATRO condiciones de exencion y una de senal:

        1. NO es imprimible            ->  es invisible: sospechoso
        2. es ASCII                    ->  permitido
        3. es un espacio o un salto    ->  permitido
        4. es puntuacion de Unicode   ->  permitido
        5. y no esta en `PERMITIDOS` ni en las EXCEPCIONES de su sitio

    Y de ahi, lo que decide, y no un rango:

        - si el nombre dice LETTER o CHARACTER, su alfabeto es la primera
          palabra, y es sospechoso si ese alfabeto no es uno de los que el
          proyecto usa;
        - si el nombre NO dice LETTER, es de uno de los cuatro sistemas que
          hay que nombrar aparte;
        - y si no es ninguna de las dos cosas, es un simbolo, y no es
          sospechoso.

    Y el texto de `PERMITIDOS` y de las EXCEPCIONES va aparte, porque son
    dos preguntas distintas: una es «que usa el proyecto» y la otra es «este
    sitio, este caracter». MEDIDO, el motivo de separarlas: el U+0435
    cirilico es un ejemplo INTENCIONADO en un documento y una corrupcion en
    otro fichero.
    """
    if c in PERMITIDOS:
        return None
    if ruta is not None:
        rel = os.path.relpath(ruta, ROOT).replace(os.sep, '/')
        for fichero, caracter in EXCEPCIONES:
            if rel == fichero and c == caracter:
                return None
    # Y el ORDEN importa, y no por gusto. MEDIDO, dos veces:
    #
    #   · el salto de linea NO es imprimible, de modo que la comprobacion de
    #     «invisible» tiene que ir DESPUES de la de «es ASCII» y la de «es un
    #     espacio». Con el orden contrario el script senalaba 254 saltos.
    #   · y el U+200B —ZERO WIDTH SPACE— NO es imprimible Y esta en la
    #     puntuacion de Unicode, de modo que «invisible» tiene que ir antes
    #     que «puntuacion de Unicode». Con el orden contrario el espacio de
    #     ancho cero pasaba.
    #
    # 2. lo ASCII
    if ord(c) < 0x80:
        return None
    # 3. los espacios
    if c in ' \t\n\r':
        return None
    # 4. lo invisible
    if not c.isprintable():
        return 'invisible'
    # 5. la puntuacion de Unicode
    if PUNTUACION_UNICODE[0] <= ord(c) <= PUNTUACION_UNICODE[1]:
        return None
    try:
        nombre = unicodedata.name(c)
    except ValueError:
        return None
    if not nombre:
        return None
    if nombre.startswith(ALFABETOS_USADOS):
        return None
    if ' LETTER ' in nombre or ' CHARACTER ' in nombre \
            or nombre.endswith(' LETTER') or nombre.endswith(' CHARACTER'):
        return nombre.split(' ')[0].lower()
    if nombre.split(' ')[0] in SISTEMAS_SIN_LETRAS:
        return nombre.split(' ')[0].lower()
    return None


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

    # ---- caso 2: UN SOLO diff, `git diff HEAD`.
    #
    # Antes eran dos: `git diff` (arbol vs indice) y `git diff --cached`
    # (indice vs HEAD). Cada uno va en coordenadas de SU version, y con
    # cambios en las dos zonas los numeros no coinciden con el fichero
    # actual. MEDIDO: staged abajo y unstaged arriba, 2 de 3 lineas con el
    # numero equivocado. `git diff HEAD` es arbol contra HEAD, su lado `+`
    # es el fichero ACTUAL, y da 0 de 3 erroneos.
    #
    # Y sale mas corto: al no haber dos zonas que combinar, no hace falta
    # quitar duplicados ni ordenar. Una cosa menos que puede quedar mal.
    #
    # Lo que NO cambia: la clasificacion. "Este hallazgo es del cambio" ya
    # era cierta con las dos vistas y lo sigue siendo con una.
    try:
        out = subprocess.run(['git', 'diff', 'HEAD', '-U0', '--', rel],
                             cwd=ROOT, capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    try:
        texto = out.stdout.decode('utf-8')
    except UnicodeDecodeError:                       # pragma: no cover
        return None
    return parsear_hunks(texto)


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
    print('   Alfabetos usados: %s' % ', '.join(ALFABETOS_USADOS))
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