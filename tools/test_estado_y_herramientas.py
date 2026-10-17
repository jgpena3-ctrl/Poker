# -*- coding: utf-8 -*-
"""R1 tareas 1, 2 y 3: verificar, no suponer.

  Tarea 1  Los CINCO documentos dicen lo mismo sobre el estado de Fase D.
  Tarea 2  La tabla de casos del detector esta en el CODIGO, con assert, y
           con un test que la ejecuta.
  Tarea 3  `revisar(patrones=None)` usa la constante cambiada.

Un test de coherencia entre documentos es raro, y aqui tiene sentido: el
motivo por el que se escribe es que los .md se corrigen a mano y se quedan
diciendo cosas distintas. Un documento que dice una cosa y el codigo hace
otra es el patron de este bloque; entre documentos es lo mismo, y es
justo lo que R1 pide verificar.

Los estados que tienen que coincidir:
    bloque 0  cerrado
    bloque 1  desbloqueado para implementar; su METRICA no es calculable
    bloque 2  cerrado como eleccion
    bloque 3  reabierto
    DEFAULT_ALPHA  2,0, por el argumento (3)
"""
import importlib.util
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'DOCS')

# Los cinco que declaran el estado. Los cinco tienen que estar.
LOS_CINCO = ('FASE_D_BLOQUEADA.md', 'REPRESENTATIVIDAD_23.md',
             'LIMITACION_PREFLOP_AUC.md', 'INC-004_H_1196.md',
             'QUE_ES_MATRIX.md')


def _leer(nombre):
    with io.open(os.path.join(DOCS, nombre), encoding='utf-8') as f:
        return f.read()


def _mod(nombre, donde):
    ruta = os.path.join(ROOT, donde, nombre)
    spec = importlib.util.spec_from_file_location(nombre[:-3].replace('.', '_'),
                                                  ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ==================================================== TAREA 1: coherencia
def test_los_cinco_documentos_existen():
    for n in LOS_CINCO:
        assert os.path.exists(os.path.join(DOCS, n)), 'falta %s' % n


def test_no_hay_auc_preflop_md():
    """R1 lo dice tres veces: no hay AUC, y por tanto no hay documento del
    AUC. Un fichero cuyo nombre promete un numero que no existe es peor que
    no tener fichero."""
    assert not os.path.exists(os.path.join(DOCS, 'AUC_PREFLOP.md'))


def test_default_alpha_sigue_en_dos():
    """Y no en un documento: en el CODIGO. Que el valor correcto este en el
    .md y equivocado en el codigo es el patron de siempre al reves."""
    from motor import player_ranges
    assert player_ranges.DEFAULT_ALPHA == 2.0


def test_todos_dicen_el_mismo_default_alpha():
    """Y que los documentos no affirmen otra cosa. Se busca cualquier
    `DEFAULT_ALPHA = <distinto de 2,0>` en los cinco."""
    for n in LOS_CINCO:
        s = _leer(n)
        for m in re.finditer(r'DEFAULT_ALPHA`?\s*(?:=|es|sigue en)\s*'
                             r'\*{0,2}([0-9]+(?:,[0-9]+)?)', s):
            v = m.group(1).replace(',', '.')
            assert v in ('2.0', '2'), (
                '%s dice que DEFAULT_ALPHA es %s' % (n, m.group(1)))


def test_el_bloque_1_esta_desbloqueado_pero_su_metrica_no():
    """Las dos mitades. Es facil que una se quede y la otra se vaya, y
    entonces el documento promete una metrica que no existe."""
    for n in ('FASE_D_BLOQUEADA.md', 'LIMITACION_PREFLOP_AUC.md',
              'REPRESENTATIVIDAD_23.md'):
        s = _leer(n)
        baja = s.lower()
        assert 'desbloquead' in baja, (
            '%s no dice que el bloque 1 esta desbloqueado' % n)
        assert ('no es calculable' in baja or 'no se puede calcular' in baja
                or 'no se calcula' in baja), (
            '%s no dice que su metrica no es calculable' % n)


def test_el_bloque_3_dice_lo_mismo_en_los_dos_documentos():
    """`FASE_D_BLOQUEADA.md` dice 'REABIERTO'. `QUE_ES_MATRIX.md` dice
    'no se sabe que clase de cosa es'. Es lo mismo con otras palabras.

    Un test que exige el mismo vocabulario no comprueba coherencia: comprueba
    ortografia. Lo que se comprueba es que los dos affirmen lo mismo.
    """
    fase = _leer('FASE_D_BLOQUEADA.md')
    matrix = _leer('QUE_ES_MATRIX.md').lower()
    assert re.search(r'[Rr][Ee][Aa][Bb][Ii][Ee][Rr][Tt][Oo]', fase), (
        'FASE_D_BLOQUEADA.md no declara el bloque 3 reabierto')
    assert 'no se sabe' in matrix, (
        'QUE_ES_MATRIX.md no dice que no se sabe que clase de cosa es')
    assert 'no se puede saber con datos' in matrix, (
        'y tiene que decir que no se deduce de los datos, que es el motivo '
        'del reapertura')


def test_que_es_matrix_no_declara_el_bloque_3_cerrado():
    """Si los dos se contradijeran, el test de arriba pasaria igual: los dos
    tendrian su palabra. Se comprueba que QUE_ES_MATRIX.md no diga en ningun
    sitio que el bloque este cerrado."""
    matrix = _leer('QUE_ES_MATRIX.md').lower()
    for frase in ('bloque 3 cerrado', 'el bloque 3 esta cerrado',
                  'queda cerrado el bloque 3'):
        assert frase not in matrix, (
            'QUE_ES_MATRIX.md dice que el bloque 3 esta cerrado, y '
            'FASE_D_BLOQUEADA.md que esta reabierto')


def test_ningun_documento_dice_que_el_auc_preflop_se_calculo():
    """La conclusion que hubo que defender tres bloques."""
    for n in LOS_CINCO:
        s = _leer(n).lower()
        for frase in ('auc preflop de 0,', 'auc preflop de 0.',
                      'se ha calculado el auc'):
            assert frase not in s, (
                '%s dice que el AUC preflop si se ha calculado' % n)


def test_el_bloque_2_esta_cerrado_como_eleccion():
    s = _leer('FASE_D_BLOQUEADA.md').lower()
    assert 'cerrado como' in s and 'elecci' in s


# ==================================================== TAREA 2: la tabla
def test_la_tabla_de_casos_esta_en_el_codigo_no_en_un_script_de_temporal():
    ar = _mod('auditar_representatividad.py', 'tools')
    fuente = io.open(ar.__file__, encoding='utf-8').read()
    i = fuente.index('def sanity_de_cartas')
    cuerpo = fuente[i:i + 2200]
    assert 'KhJs' in cuerpo, (
        'el caso que rompia el detector tiene que estar en el REPO: si vive '
        'en un script de %TEMP%, el detector puede romperse y la suite sigue '
        'verde')
    assert 'KhJh' in cuerpo, 'y el suited del mismo par'


def test_la_tabla_aborta_si_el_detector_falla():
    """Con un detector roto, los numeros de C3 no se publican."""
    ar = _mod('auditar_representatividad.py', 'tools')
    fuente = io.open(ar.__file__, encoding='utf-8').read()
    i = fuente.index('fallos, lineas, n_casos = sanity_de_cartas()')
    cuerpo = fuente[i:i + 600]
    assert 'assert fallos == 0' in cuerpo, (
        'y el mensaje tiene que decir que C3 no se publica con el detector '
        'roto, que es la razon por la que el assert existe')
    assert 'detector de cartas falla' in cuerpo


def test_la_tabla_declara_ocho_casos_y_son_ocho():
    ar = _mod('auditar_representatividad.py', 'tools')
    fallos, lineas, n = ar.sanity_de_cartas()
    assert fallos == 0, 'la tabla falla: %r' % [l for l in lineas
                                                if 'MAL' in l]
    assert n == 8, 'son %d casos' % n
    assert len(lineas) == 8


def test_el_total_de_la_tabla_no_esta_escrito_a_mano():
    """El fallo de este bloque: un 'de 7' fijo que pasa a mentir cuando se
    anade un caso. El total tiene que salir de la lista."""
    fuente = io.open(_mod('auditar_representatividad.py', 'tools').__file__,
                     encoding='utf-8').read()
    assert "print('   fallos: %d de %d'" in fuente
    # el comentario que explica el arreglo menciona "de 7" a proposito; lo
    # que no puede haber es un total FIJO dentro de una cadena de formato
    assert 'de 7 casos' not in fuente, 'el mensaje del assert lo lleva a mano'
    assert 'fallos: %d de 7' not in fuente
    assert re.search(r'de 7\b(?![^\n]*fijo)', fuente.split('SANIDAD')[-1]
                     .split('fallos:')[0]) is None, (
        'y no hay ningun total escrito a mano en la seccion del detector')


def test_la_tabla_detecta_un_detector_roto():
    """La prueba de que la tabla PUEDE fallar. Una tabla que nunca falla no
    protege nada: eso es lo que pasaba con el detector anterior."""
    ar = _mod('auditar_representatividad.py', 'tools')
    original = ar.cartas
    try:
        # el modo en el que el detector era el de antes: alfabetico
        def cartas_roto(c2):
            c2 = (c2 or '').strip()
            if len(c2) != 4:
                return ''
            for i in (0, 2):
                if c2[i] not in ar.RANGOS or c2[i + 1] not in ar.PALOS:
                    return ''
            return ''.join(sorted((c2[0], c2[2]))), c2[1] + c2[3]
        ar.cartas = cartas_roto
        fallos, lineas, _n = ar.sanity_de_cartas()
        assert fallos > 0, (
            'con el detector alfabetico la tabla tiene que FALLAR. Si no '
            'falla, la tabla no mira lo que dice mirar')
        # fallan LOS DOS casos del par KJ, suited y sin palo. Es un fallo
        # solo porque las dos cartas son el mismo par, no dos.
        malos = sorted(l.split()[0] for l in lineas if 'MAL' in l)
        assert malos == ['KhJh', 'KhJs'], (
            'y tienen que ser los dos del par KJ, y no otros: %r' % malos)
    finally:
        ar.cartas = original


# ================================================== TAREA 3: revisar()
def test_revisar_usa_la_constante_cambiada():
    """El bug: `def revisar(patrones=PATRONES)` se evalua AL IMPORTAR, asi
    que cambiar la constante no cambiaba lo que se escanea."""
    vc = _mod('verificar_caracteres.py', 'tools')
    import tempfile
    d = tempfile.mkdtemp(prefix='opencode_rev_')
    os.makedirs(os.path.join(d, 'sub'))
    with io.open(os.path.join(d, 'sub', 'a.py'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write('x = "%s"\n' % chr(0x3001))
    with io.open(os.path.join(d, 'sub', 'b.txt'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write('y = "%s"\n' % chr(0x3001))
    try:
        ROOT_ANTES, PATRONES_ANTES = vc.ROOT, vc.PATRONES
        vc.ROOT = d
        try:
            # por defecto: lo que dice la constante AHORA. Por eso se
            # cambia antes de llamar: la pregunta es si la manda, y con el
            # PATRONES de verdad (tools/*.py) un temporal no encuentra nada
            vc.PATRONES = ('sub/*',)
            h = vc.revisar()
            assert len(h) == 2, (
                'los dos ficheros tienen el mismo caracter, y la constante '
                'tiene que mandar: %d' % len(h))
            # y ahora la constante cambia
            vc.PATRONES = ('sub/*.py',)
            h2 = vc.revisar()
            assert len(h2) == 1, (
                'cambiar PATRONES tiene que cambiar lo que se escanea: %d'
                % len(h2))
            assert 'a.py' in h2[0][0]
            # y el argumento explicito manda sobre la constante
            h3 = vc.revisar(('sub/*.txt',))
            assert len(h3) == 1 and 'b.txt' in h3[0][0]
        finally:
            vc.ROOT, vc.PATRONES = ROOT_ANTES, PATRONES_ANTES
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def test_revisar_no_tiene_argumento_por_defecto_congelado():
    """La forma del fallo, para que no vuelva por la misma puerta."""
    import inspect
    fuente = inspect.getsource(_mod('verificar_caracteres.py', 'tools').revisar)
    i = fuente.index('def revisar(')
    firma = fuente[i:fuente.index(':', i)]
    assert 'patrones=PATRONES' not in firma, (
        'el valor por defecto se evalua al importar: cambiar la constante no '
        'cambia lo que se escanea')
    assert 'patrones=None' in firma