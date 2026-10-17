# -*- coding: utf-8 -*-
"""La lista de los cinco bloqueos tiene que existir, estar completa, y no
resolver ninguno.

POR QUE ESTA EN UN FICHERO Y NO EN UN MENSAJE

R2 lo dice: «lo que hace que un proyecto se pueda retomar: no "queda esto",
sino "queda esto y es de este"». Y la lista vivia en los mensajes de commit y
en el informe de cada bloque, que es donde deja de estar en cuanto el commit
se deja de leer.

Y hay un riesgo concreto en tenerla escrita: **una lista de bloqueos escrita
es una lista que se puede ir cerrando**. Si el documento dijera «cerrado» en
alguno, estariamos declarando una resolucion que no existe. Asi que se
comprueba que los cinco siguen ABIERTOS, y que `DEFAULT_ALPHA` sigue en 2,0.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DOCS = os.path.join(ROOT, 'DOCS')
LISTA = os.path.join(DOCS, 'BLOQUEOS_Y_DUENOS.md')

# Los cinco, con lo que hace que cada uno sea EL que es, y no el otro.
LOS_CINCO = (
    ('INC-004', 'H_1196', 'la `BB b` mal ordenada'),
    ('matrix', 'intención del generador', 'qué significa'),
    ('board divergente', '2.3', 'las 5 manos'),
    ('preflop del motor', 'CONTRATO', 'la vía'),
    ('ponder', 'rival', 'por rival'),
)


def _leer():
    with io.open(LISTA, encoding='utf-8') as f:
        return f.read()


def test_la_lista_existe_y_tiene_los_cinco():
    """Y el fallo dice CUAL falta, que es lo que hace falta para arreglarlo."""
    doc = _leer()
    faltan = []
    for clave, ancla, que in LOS_CINCO:
        if clave.lower() not in doc.lower():
            faltan.append(que)
        if ancla not in doc:
            faltan.append('%s (falta el ancla %r)' % (que, ancla))
    assert not faltan, (
        'la lista de bloqueos esta incompleta:\n   '
        + '\n   '.join(faltan))


def test_cada_bloqueo_dice_de_quien_es():
    """Que no es decorativo: un bloqueo sin dueño es deuda. Y la columna de
    la tabla tiene que estar llena en los cinco."""
    doc = _leer()
    lineas = doc.split('\n')
    # La pregunta es «¿esta fila dice de quien es?», y la respuesta esta en la
    # CUARTA celda, no en una combinacion de palabras. Una version anterior
    # buscaba `de (quien|del|la)` y no encontraba «del dueño de data/»: tres
    # palabras donde la expresion pedia dos.
    DUENO = ('dueño', 'dueña', 'de quien', 'de quién', 'de la', 'del ',
             'de este', 'de quien decida')
    filas = [l for l in lineas if l.startswith('| ') and l.count('|') >= 5]
    con_dueno = [l for l in filas
                 if any(w in l.split('|')[4].lower() for w in DUENO)]
    assert len(con_dueno) >= 5, (
        'solo %d filas de la tabla dicen de quien es: %r. La tabla de '
        'bloqueos tiene que llenarla, o no es una lista de bloqueos sino '
        'una lista de problemas'
        % (len(con_dueno),
           [l.split('|')[4].strip() for l in filas]))


def test_ninguno_esta_cerrado():
    """Lo mas importante. Una lista escrita de bloqueos es una lista que se
    puede ir cerrando, y si este documento dijera «cerrado» en alguno estaria
    declarando una resolucion que no existe."""
    doc = _leer().lower()
    for palabra in ('cerrado', 'resuelto', 'solucionado', 'arreglado ya'):
        for i, linea in enumerate(doc.split('\n'), 1):
            if palabra in linea:
                # se admite en la frase que dice que NO lo esta
                if not any(n in linea for n in ('no ', 'sin ', 'que no',
                                                'declara', 'declaracion',
                                                'todavia', 'ninguno')):
                    raise AssertionError(
                        'linea %d dice %r sin negar: %s'
                        % (i, palabra, linea.strip()[:70]))


def test_default_alpha_sigue_en_dos_y_esta_dicho_ahi():
    """Que no es un bloqueo. Y que esta escrito, porque «no es un bloqueo» es
    una afirmacion que se puede equivocar."""
    doc = _leer()
    assert '2,0' in doc or '2.0' in doc, 'DEFAULT_ALPHA en la lista'
    assert 'no es un bloqueo' in doc.lower(), 'y que se dice que no lo es'
    # y que en el codigo siga en 2,0
    from motor import player_ranges
    assert abs(player_ranges.DEFAULT_ALPHA - 2.0) < 1e-12, (
        'DEFAULT_ALPHA ha cambiado: %r' % player_ranges.DEFAULT_ALPHA)


def test_inc004_esta_en_la_lista_y_sigue_abierto():
    """El criterio de la tarea 6 de R1, literalmente: que este en la lista, y
    que siga abierto."""
    doc = _leer()
    assert 'INC-004' in doc, 'INC-004 en la lista'
    assert 'H_1196' in doc, 'y con el identificador de la mano'
    doc_inc = io.open(os.path.join(DOCS, 'INC-004_H_1196.md'),
                      encoding='utf-8').read()
    assert 'ESTADO: ABIERTO' in doc_inc, (
        'el documento de INC-004 ya no dice ABIERTO: eso es un cambio de '
        'estado que no se ha decidido aqui')
    # Y que NO se le ATRIBUYA xfail. Que la palabra aparezca es correcto —la
    # lista dice «Ni xfail, ni skip»—, porque eso es declarar que el fallo esta
    # VISIBLE. Lo que no puede es aparecer sin negarse, que es lo que seria
    # declararlo escondido.
    #
    # Y esta distincion —«no aparece» contra «no se afirma»— es la misma que
    # el escaner de retracciones lleva cuatro rondas corrigiendo. Aqui, en el
    # test que comprueba la lista. Que es donde menos se le hubiera buscado.
    for i, linea in enumerate(doc.split('\n'), 1):
        if 'xfail' not in linea.lower():
            continue
        if not re.search(r'\bni\b|\bno\b|\bsin\b', linea, re.IGNORECASE):
            raise AssertionError(
                'linea %d menciona xfail sin negar: %s'
                % (i, linea.strip()[:70]))


def test_el_documento_no_resuelve_nada_nuevo():
    """Que la lista no aplique. Y la forma de comprobarlo es que no modifique
    nada: los cinco detalles van a enlaces, no a recetas."""
    doc = _leer()
    assert 'No se corrigen aquí' in doc or 'No se corrigen' in doc, (
        'la lista dice que algo se corrige. Esta es una lista, no un bloque')
    # Los TRES bloqueos que tienen documento propio tienen que APUNTAR a ese
    # documento, por nombre.
    #
    # Y no «hay N enlaces»: eso no dice nada, porque N puede ser el mismo
    # documento citado dos veces. Lo que puede fallar de verdad es que alguien
    # reescriba el documento de INC-004 y deje el enlace apuntando a otro, y
    # un recuento sigue dando verde.
    for nombre in ('INC-004_H_1196.md', 'QUE_ES_MATRIX.md',
                   'QUE_REPRESENTA_LA_PREDICCION.md'):
        assert '](%s)' % nombre in doc, (
            'la lista no enlaza a %s, que es donde se explica uno de los '
            'cinco' % nombre)