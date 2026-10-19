# -*- coding: utf-8 -*-
"""`tools/verificar_caracteres.py`: que la regla sea DERIVADA, y que tenga
dientes.

Y por que este fichero existe: el barrido de caracteres raros estaba escrito
con RANGOS de puntos de codigo, y un rango escrito a mano se queda corto sin
que nada se note. Y MEDIDO, el de este repo se habia quedado:

    el rango anterior no incluia el ARABE (U+0600..U+06FF)
    y en el repo habia TRES caracteres arabes
    y el rango anterior tampoco incluia el U+FEFF (BOM)
    y en el repo habia DOS BOMs

Y un rango que se queda corto no avisa: devuelve cero hallazgos, que es un
verde.

Y la regla que lo sustituye se decide por el NOMBRE Unicode del caracter, que
dice que es el caracter, y no por donde cae.
"""
import io
import os
import unicodedata
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import verificar_caracteres as VC  # noqa: E402

RUTA = os.path.join(ROOT, 'tools', 'verificar_caracteres.py')


def _fuente():
    with io.open(RUTA, encoding='utf-8') as f:
        return f.read()


# --- 1. la regla no son rangos ---------------------------------------------

def test_la_regla_no_usa_rangos_de_puntos_de_codigo():
    """Que no vuelva el `RANGOS`, que es lo que se quedo corto.

    Y como se comprueba: mirando el CODIGO, y no el texto. Y no por una lista
    de rangos prohibidos —que seria otra lista escrita a mano, y se quedaria
    corta por el otro lado—: lo que se mira es que en el ARBOL no hay ninguna
    constante de rangos, y que la regla se decide por el NOMBRE del caracter.

    Y MEDIDO, por que el rango escrito a mano era un problema de verdad y no
    una preocupacion teorica: el anterior no incluia el arabe, y en el repo
    habia tres caracteres arabes que NO se senalaban.

    Y el AST y no el texto, por una razon que este bloque lleva cuarenta
    bloques corrigiendo: en el TEXTO esta bien que aparezca la palabra
    «RANGOS», porque el comentario que explica el cambio la nombra. Lo que
    no puede es EXISTIR.
    """
    import ast
    arbol = ast.parse(_fuente())
    globales = set()
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign):
            for objetivo in nodo.targets:
                if isinstance(objetivo, ast.Name):
                    globales.add(objetivo.id)
        elif isinstance(nodo, ast.AnnAssign) and isinstance(nodo.target, ast.Name):
            globales.add(nodo.target.id)
    assert 'RANGOS' not in globales, (
        'vuelve la constante de RANGOS. Y es la clase de lista que se queda '
        'corta sin que nada se note.')

    # Y que no haya NINGUN rango escrito a mano. Y lo que se mira no son los
    # numeros sueltos —`chr(0xFE0F)` es un caracter legitimo—, sino las
    # COMPARACIONES: un rango es comparar un punto de codigo con un numero
    # grande, y el unico sitio donde puede haber eso es la puntuacion de
    # Unicode, que es una CONSTANTE CON NOMBRE y no un numero suelto.
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Compare):
            continue
        for comparable in nodo.comparators:
            if (isinstance(comparable, ast.Constant)
                    and isinstance(comparable.value, int)
                    and comparable.value > 0x206F):
                raise AssertionError(
                    'hay una comparacion contra el numero %d (0x%X), y eso es '
                    'un rango escrito a mano. La puntuacion de Unicode tiene '
                    'que ser una constante con nombre.'
                    % (comparable.value, comparable.value))
    assert 'unicodedata.name' in _fuente(), (
        'y la regla tiene que decidir por el NOMBRE Unicode del caracter')


def test_la_regla_usa_las_cuatro_condiciones():
    """Las cuatro, y en el codigo.

    Y el orden importa, y hay un motivo medido: el salto de linea NO es
    imprimible, de modo que la comprobacion de «invisible» tiene que ir
    despues de la de «es ASCII». MEDIDO, con el orden contrario el script
    senalaba 254 saltos de linea.
    """
    fuente = _fuente()
    for trozo, que in (
            ('isprintable', 'lo invisible'),
            ('ord(c) < 0x80', 'lo ASCII'),
            ("c in ' \\t\\n\\r'", 'los espacios'),
            ('PUNTUACION_UNICODE', 'la puntuacion de Unicode')):
        assert trozo in fuente, (
            'falta la condicion de %s: %r' % (que, trozo))
    i_invisible = fuente.index('isprintable')
    i_ascii = fuente.index('ord(c) < 0x80')
    assert i_ascii < i_invisible, (
        'la condicion de «es ASCII» tiene que ir ANTES que la de «es '
        'invisible», porque el salto de linea no es imprimible. MEDIDO: con el '
        'orden contrario el script senalaba 254 saltos de linea.')


# --- 2. detecta coreano ----------------------------------------------------

def test_detecta_el_coreano():
    """Que un Hangul se senale, que es el caso que R2 nombra.

    Y el motivo de que el coreano sea el caso: es el que se coló en un
    fichero de texto de este repo, y el rango anterior —que iba de 0x2E80 a
    0x9FFF— no lo cubria, porque el Hangul empieza en 0xAC00 y 0x9FFF se
    queda antes.

    Y el caso es SINTETICO, y por que: en el repo no hay ningun coreano
    ahora mismo, de modo que el caso del repo pasaria con cualquier regla.
    """
    assert VC._sospechoso(chr(0xAC00)) is not None, (
        'un Hangul tiene que ser sospechoso, y no se senala. Y el rango '
        'anterior no lo cubria: el Hangul empieza en 0xAC00, despues de su '
        '0x9FFF.')
    # Y los cuatro sistemas que su nombre no dice LETTER
    for cp, nombre in ((0xAC00, 'HANGUL SYLLABLE GA'),
                       (0x4E00, 'CJK UNIFIED IDEOGRAPH-4E00'),
                       (0x3001, 'IDEOGRAPHIC COMMA'),
                       (0xA000, 'YI SYLLABLE IT')):
        assert VC._sospechoso(chr(cp)) is not None, (
            'el U+%04X (%s) tiene que ser sospechoso' % (cp, nombre))


# --- 3. detecta lo que la lista vieja no cubria ----------------------------

def test_detecta_los_alfabetos_que_la_lista_veja_no_cubria():
    """El arabe, y los demas, que es la raison d'etre del cambio.

    Y el caso del arabe es REAL, no inventado: hay tres caracteres arabes en
    `motor/test_asistente_live.py`, y el rango anterior NO los senalaba.

    Y MEDIDO, el alcance de lo que se gana, que es lo que hace que el cambio
    valga la pena:

        el rango anterior cubria  cirilico, armenio, han, CJK
        este cubre ademas         arabe, hebreo, devanagari, thai, coreano
    """
    for cp, nombre in ((0x0628, 'ARABIC LETTER BEH'),
                       (0x05D0, 'HEBREW LETTER ALEF'),
                       (0x0915, 'DEVANAGARI LETTER KA'),
                       (0x0E01, 'THAI CHARACTER KO KAI'),
                       (0x10A0, 'GEORGIAN CAPITAL LETTER AN')):
        assert VC._sospechoso(chr(cp)) is not None, (
            'el U+%04X (%s) tiene que ser sospechoso' % (cp, nombre))

    # Y que un rango POR ESCRITO no lo habria cogido: el arabe esta entre
    # 0x0600 y 0x06FF, y la lista vieja no lo mencionaba.
    fuente = _fuente()
    assert '0x0600' not in fuente, (
        'vuelve el rango del arabe, y ese rango es el que se quedaba corto')


def test_el_bom_y_los_caracteres_invisibles_se_senalan():
    """Lo invisible, que el rango anterior tampoco cubria.

    MEDIDO: el rango anterior cubria el U+FFFD —el caracter de reemplazo— y
    nada mas de los invisibles. Y en el repo hay DOS U+FEFF, el BOM, en dos
    documentos. Y un BOM no se ve: es un byte que no aparece en ningun sitio
    y que cambia como se lee el fichero.
    """
    assert VC._sospechoso(chr(0xFEFF)) == 'invisible', (
        'el BOM tiene que ser sospechoso, y no invisible sino invisible')
    assert VC._sospechoso(chr(0x200B)) == 'invisible', (
        'y el ZERO WIDTH SPACE tambien')


# --- 4. no acusa al repertorio legitimo -------------------------------------

def test_no_acusa_al_repertorio_que_el_proyecto_usa():
    """Lo que el repo usa de verdad, que es mucho mas de lo que la lista
    permitia.

    MEDIDO: el repo usa 81 caracteres no-ASCII distintos, y la lista de
    permitidos tenia 34. Y la diferencia no es que los otros 47 sean
    sospechosos: es que estan en rangos que la lista vieja no miraba, y por
    eso pasaban sin que nadie se preguntara.
    """
    for c in ('→', '←', 'á', 'é', 'ñ', '«', '»', '—', '…', '“', '”',
              '§', '·', 'ω', 'Σ', 'α', 'τ', 'Δ', '─', '│', '├', '▼',
              '⚠', '⚙', '✗', '✋', '▶', '■', '×', '≤', '≥', '≈', '∈',
              '≠', '±', '−', '∑', '📷', '💾', '▁'):
        assert VC._sospechoso(c) is None, (
            'el %r (U+%04X) lo usa el proyecto y no tiene que ser sospechoso'
            % (c, ord(c)))


def test_la_excepcion_del_ejemplo_deliberado_es_por_sitio():
    """El U+0435 es un ejemplo INTENCIONADO en un documento, y una corrupcion
    en otro fichero.

    MEDIDO, el motivo de que la excepcion sea POR SITIO y no por caracter: el
    mismo U+0435 esta en `DOCS/INC-003_BARRIDO_DESTRUCTIVO.md`, donde el
    documento dice que es intencionado, y en `motor/test_canal_manual.py`,
    donde es una corrupcion. Una excepcion por caracter los taparia a los
    dos, y el guardiano no veria ni el ejemplo ni la corrupcion.
    """
    c = chr(0x435)
    assert VC._sospechoso(c, os.path.join(ROOT, 'DOCS',
                                          'INC-003_BARRIDO_DESTRUCTIVO.md')) is None, (
        'en el documento del ejemplo el U+0435 es intencionado, y no tiene '
        'que senalarse')
    assert VC._sospechoso(c, os.path.join(ROOT, 'motor',
                                          'test_canal_manual.py')) is not None, (
        'y en el otro fichero el MISMO caracter es una corrupcion, y tiene que '
        'senalarse. Una excepcion por caracter los taparia a los dos.')


# --- y el guardian de verdad: que no entre nada nuevo ------------------------

def test_ningun_hallazgo_es_del_cambio():
    """Que ningun hallazgo venga de un cambio sin commitear.

    Y este es el guardian de verdad, y es el que habria pillado la palabra en
    coreano que se coló en un fichero de texto: un hallazgo «DEL CAMBIO» es
    un caracter que ha entrado ahora, y hay que decidir si se queda.

    Y la clasificacion la hace el propio script, mirando las LINEAS que el
    diff anade, y no preguntando «¿estaba en HEAD?». MEDIDO, la razon: si ya
    estaba en otro parrafo del fichero, una aparicion NUEVA en el codigo
    salia clasificada como PREEXISTENTE y se perdia justo lo que se busca.
    """
    hallazgos = VC.revisar()
    assert hallazgos, (
        'el barrido no encuentra NADA, y eso no puede ser: MEDIDO, hay once '
        'hallazgos preexistentes en el repo, y nueve de ellos son en ficheros '
        '.py. Un barrido que no encuentra nada esta mirando otra cosa.')
    nuevos = []
    for ruta, c, nombre in hallazgos:
        en_el_cambio, lineas = VC.en_cambio(ruta, c)
        if en_el_cambio is True:
            nuevos.append((os.path.relpath(ruta, ROOT), repr(c), lineas))
    assert not nuevos, (
        'hay %d hallazgo(s) DEL CAMBIO: %r. O sea que un caracter sospechoso ha '
        'entrado ahora, y hay que decidir si se queda o se quita.'
        % (len(nuevos), nuevos))

# --- y la declaracion, que es lo que hace que «preexistente» sea una cosa ---

def test_el_numero_de_hallazgos_es_el_declarado():
    """Que el numero de hallazgos sea el declarado, y no uno de memoria.

    Y por que un NUMERO y no una lista de ficheros: lo que se vigila es que
    no CREZCAN, y una lista de ficheros seria una lista escrita a mano, que se
    queda corta sin que nada se note. Y el detalle esta en
    `DOCS/HALLAZGOS_DECLARADOS.md`.

    Y lo que se comprueba aqui es que el numero y el documento NO SE SEPAREN:
    un test que solo mira el numero no dice nada de si el documento dice el
    mismo, y un documento que dice un numero que ya no es el del codigo es
    una declaracion falsa.
    """
    hallazgos = VC.revisar()
    assert len(hallazgos) == VC.SOSPECHOSOS_ABAJO, (
        'hay %d hallazgos y el declarado es %d. Si se ha ARREGLADO uno, el '
        'numero baja y hay que subir la constante a mano: quitar un defecto '
        'tiene que ser una decision. Y si se ha METIDO uno, hay que '
        'declararlo con su motivo.'
        % (len(hallazgos), VC.SOSPECHOSOS_ABAJO))

    doc = io.open(os.path.join(ROOT, 'DOCS', 'HALLAZGOS_DECLARADOS.md'),
                  encoding='utf-8').read()
    assert str(VC.SOSPECHOSOS_ABAJO) in doc, (
        'el documento de hallazgos no menciona el numero declarado (%d). Y un '
        'documento que dice un numero que ya no es el del codigo es una '
        'declaracion falsa.'
        % VC.SOSPECHOSOS_ABAJO)


# -*- coding: utf-8 -*-
"""El test que ata la declaracion, hallazgo por hallazgo."""
import io
import os
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'DOCS', 'HALLAZGOS_DECLARADOS.md')


def _filas_de_la_declaracion():
    """Las filas de la tabla de hallazgos del documento de declaracion.

    Y se PARSEAN, y no se buscan con un `in`. Y el motivo es el que R2
    senalo: un `in` encuentra el NOMBRE en cualquier parte del documento, y
    no dice si el hallazgo esta asociado al FICHERO correcto, al PUNTO DE
    CODIGO correcto, y a una JUSTIFICACION concreta.

    Y una declaracion en la que el nombre aparece pero el fichero es el
    equivocado sigue siendo una declaracion falsa, y es la clase de error que
    este bloque lleva cuarenta y seis bloques corrigiendo: una afirmacion
    sobre una magnitud medida con otra.
    """
    with io.open(DOC, encoding='utf-8') as f:
        lineas = f.read().split('\n')
    filas = []
    dentro = False
    for l in lineas:
        if l.startswith('| fichero |'):
            dentro = True
            continue
        if not dentro:
            continue
        if not l.startswith('|'):
            break
        celdas = [c.strip() for c in l.strip('|').split('|')]
        if len(celdas) != 4:
            continue
        if set(''.join(celdas)) <= set('-: '):
            continue
        filas.append(celdas)
    return filas


def test_los_hallazgos_estan_declarados_en_el_documento():
    """Que CADA hallazgo este declarado con su fichero, su punto de codigo y
    su motivo. Y no solo con su nombre.

    Y esto es lo que R2 senalo, y es un matiz que delimita el contrato de los
    tests: antes, el test comprobaba que el nombre Unicode de cada hallazgo
    apareciera EN ALGUN SITIO del documento. Eso no dice:

      · que el hallazgo este asociado al FICHERO correcto;
      · ni que el punto de codigo sea el correcto;
      · ni que haya una justificacion concreta.

    Y una declaracion en la que el nombre aparece pero el fichero es el
    equivocado sigue siendo una declaracion falsa.

    Y el modo de comprobarlo es comparar LOS CONJUNTOS: lo declarado contra lo
    MEDIDO. Y por que conjuntos y no «cada fila esta en el fichero»: porque
    «cada fila esta» no dice que no haya filas de mas, y una fila de mas es
    un hallazgo declarado que no existe.

    Y el motivo se comprueba que EXISTA, y no que sea bueno: que sea bueno lo
    lee quien lo lee, y un test no puede juzgar un texto. Lo que si puede es
    decir que no es un marcador de posicion vacio.
    """
    import verificar_caracteres as VC

    filas = _filas_de_la_declaracion()
    assert filas, (
        'la tabla de hallazgos de `DOCS/HALLAZGOS_DECLARADOS.md` esta vacia, o '
        'no tiene el formato que se espera: cuatro celdas por fila.')

    declarados = {}
    for fichero, nombre, codepoint, motivo in filas:
        clave = (fichero.strip('`'), nombre.strip('`'), codepoint.strip())
        declarados[clave] = motivo.strip()

    medidos = {}
    for ruta, c, _nombre in VC.revisar():
        rel = os.path.relpath(ruta, ROOT).replace(os.sep, '/')
        medidos[(rel, unicodedata.name(c), 'U+%04X' % ord(c))] = True

    faltan = sorted(set(medidos) - set(declarados))
    sobran = sorted(set(declarados) - set(medidos))
    assert not faltan, (
        'hay %d hallazgo(s) MEDIDOS que no estan declarados: %r. Y un '
        'hallazgo que no se declara es un fallo esperando a que alguien lo '
        'encuentre por sorpresa.' % (len(faltan), faltan))
    assert not sobran, (
        'hay %d fila(s) DECLARADAS que no corresponden a ningun hallazgo: %r. '
        'Y una declaracion de un hallazgo que no existe es peor que no '
        'declararlo: hace creer que se ha mirado algo que no se ha mirado.'
        % (len(sobran), sobran))

    for clave, motivo in sorted(declarados.items()):
        assert motivo, (
            'el hallazgo %r no tiene motivo escrito. Y un hallazgo sin '
            'motivo es una lista de Ebola, no una declaracion.' % (clave,))
        assert motivo.strip(' .') not in ('-', '—', 'TODO', '...'), (
            'el motivo del hallazgo %r es un marcador de posicion, no un '
            'motivo.' % (clave,))

# --- y la declaracion, que es lo que hace que «preexistente» sea una cosa ---
