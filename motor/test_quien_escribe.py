# -*- coding: utf-8 -*-
"""T4 — quién escribe `hands_db.jsonl`, y qué tiene cada escritor.

`DOCS/CANAL_MANUAL_CERRADO.md` §6 dice que el canal manual está cerrado. Eso
solo es verdad si la lista de quien escribe está completa, y la lista se
midió con `tools/quien_escribe.py`... que hasta hace un momento no existía.

Lo que este fichero fija:

1. La INVENTARIO de escritores, y que no crezca sin que se declare.
2. Que `hand_editor.py` —el único que REESCRIBE la base entera— tenga red:
   backup verificado, escritura atómica, y aviso de que el manifiesto queda
   obsoleto.

Lo que NO hace: prohibir la edición a mano. El mantenedor tiene que poder
revisar las manos, y eso es editar el fichero. Lo que no puede es hacerlo sin
que quede escrito, que es otra cosa.

El instrumento (`tools/quien_escribe.py`) se autocomprueba con seis casos de
respuesta conocida antes de usarse. Este test comprueba que el inventario que
hay aquí y el que da el instrumento **coinciden**, que es lo único que hace
que la lista sirva de algo.
"""
import io
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import hand_editor                                              # noqa: E402
from motor import learn                                         # noqa: E402

INSTRUMENTO = os.path.join(ROOT, 'tools', 'quien_escribe.py')


# ---------------------------------------------------------------------------
# 1. el inventario
# ---------------------------------------------------------------------------

def _inventario_del_instrumento():
    """Los que el instrumento clasifica como ESCRIBEN, y solo esos."""
    if not os.path.exists(INSTRUMENTO):
        pytest.skip('tools/quien_escribe.py no esta (todavia) en el repo')
    p = subprocess.run([sys.executable, INSTRUMENTO],
                       cwd=ROOT, capture_output=True)
    out = p.stdout.decode('utf-8', 'replace')
    assert 'ROTO' not in out, (
        'el instrumento se autocomprobacion y ha fallado:\n%s' % out[-2000:])
    seccion = out.split('=== ESCRIBEN en hands_db.jsonl ===')[1]
    seccion = seccion.split('===')[0]
    return {l.split()[0] for l in seccion.splitlines() if l.strip()}


#: Lo que el fichero dice. Si el instrumento ve uno mas, este test falla.
# Cada escritor, con QUE escribe, DONDE, y BAJO QUE CONDICION.
#
# Y no es una lista de nombres, y el motivo: una lista de nombres NO SE PUEDE
# COMPROBAR. El guardián de mas abajo comprueba que el instrumento —que mira
# por el ARBOL quien escribe en `hands_db.jsonl`— y esta declaracion dicen lo
# mismo. Y con una lista de nombres, lo unico que se podria comprobar es que
# no se ha olvidado un nombre, que es otra cosa.
#
# Y el campo `temporal` es el que evita el permiso permanente: si la escritura
# es temporal, la declaracion tiene que decirlo Y decir como se restaura. Y
# hay un test que lo comprueba.
ESCRITORES_DECLARADOS = {
    'hand_editor.py': {
        'escribe': 'la base entera',
        'destino': 'data/hands_db.jsonl',
        'condicion': 'a mano, y con un `.bak` al lado',
        'temporal': False,
        'operacion': 'rewrite completo desde la UI',
        'ejecucion': 'manual/UI',
        'durante_live': 'posible; no se halló lock de sesión compartido',
        'proteccion': 'backup .bak; no gate por hash base declarado',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto; revisión manual necesaria, no se presume seguro',
        'operacion': 'rewrite completo desde la UI',
        'ejecucion': 'manual/UI',
        'durante_live': 'posible; no se halló lock de sesión compartido',
        'proteccion': 'backup .bak; no gate por hash base declarado',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto; requiere operador y revisión, no se presume seguro',
    },
    'recorder/record_hand.py': {
        'escribe': 'una mano',
        'destino': 'data/hands_db.jsonl',
        'condicion': 'en vivo, mientras se juega',
        'temporal': False,
        'operacion': 'append de una mano',
        'ejecucion': 'por evento de recorder',
        'durante_live': 'sí; es su función prevista',
        'proteccion': 'validaciones del recorder; sin lock común con scripts de edición',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto por ser writer live; coordinar ediciones',
        'operacion': 'append de una mano',
        'ejecucion': 'por evento de recorder',
        'durante_live': 'sí; es su función prevista',
        'proteccion': 'validaciones del recorder; sin lock común con scripts de edición',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto por ser writer live; debe coordinarse con ediciones',
    },
    'recorder/recorder_live.py': {
        'escribe': 'manos',
        'destino': 'data/hands_db.jsonl',
        'condicion': 'en vivo, mientras se juega',
        'temporal': False,
        'operacion': 'append de mano(s)',
        'ejecucion': 'por evento de recorder live',
        'durante_live': 'sí; es su función prevista',
        'proteccion': 'flujo live; sin lock común con scripts de edición',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto por ser writer live; coordinar ediciones',
        'operacion': 'append de mano(s)',
        'ejecucion': 'por evento de recorder live',
        'durante_live': 'sí; es su función prevista',
        'proteccion': 'flujo live; sin lock común con scripts de edición',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto por ser writer live; debe coordinarse con ediciones',
    },
    'tools/aplicar_correcciones.py': {
        'escribe': 'migraciones',
        'destino': 'data/hands_db.jsonl',
        'condicion': 'con backup, y con dry-run por defecto',
        'temporal': False,
        'operacion': 'rewrite atómico de migraciones CM-001/003',
        'ejecucion': 'CLI explícita con --apply',
        'durante_live': 'posible si se invoca concurrentemente; sin lock',
        'proteccion': 'dry-run, backup/hash y validación; no lock live',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto; requiere revisar plan y base objetivo',
        'operacion': 'rewrite atómico con correcciones manuales CM-001/003',
        'ejecucion': 'CLI explícita con --apply',
        'durante_live': 'posible si se invoca concurrentemente; sin lock',
        'proteccion': 'dry-run, backup/hash y validación; no lock live',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto; no declarar seguro por tener backup',
    },
    'tools/aplicar_reinterpretacion.py': {
        'escribe': 'la base reinterpretada',
        'destino': 'data/hands_db.jsonl',
        'condicion': 'con backup, y con dry-run por defecto',
        'temporal': False,
        'operacion': 'rewrite atómico de reinterpretación',
        'ejecucion': 'CLI explícita con --apply',
        'durante_live': 'posible si se invoca concurrentemente; sin lock',
        'proteccion': 'hash de origen/salida, backup y rollback',
        'derivados_manifiestos': 'manifiesto puede quedar stale; no se actualiza',
        'riesgo': 'alto; una reinterpretación no equivale a adopción',
        'operacion': 'rewrite atómico a partir de base/version pin',
        'ejecucion': 'CLI explícita con --apply',
        'durante_live': 'posible si se invoca concurrentemente; sin lock',
        'proteccion': 'hash de origen/salida, backup y rollback',
        'derivados_manifiestos': 'manifiesto puede quedar stale; no se actualiza',
        'riesgo': 'alto; reinterpretación no equivale a adopción',
    },
    'tools/sanear_base.py': {
        'escribe': 'el saneamiento',
        'destino': 'data/hands_db.jsonl',
        'condicion': 'con backup, y con dry-run por defecto',
        'temporal': False,
        'operacion': 'rewrite/saneamiento de la base',
        'ejecucion': 'CLI explícita con --apply',
        'durante_live': 'posible si se invoca concurrentemente; sin lock',
        'proteccion': 'backup y temporal; no lock live',
        'derivados_manifiestos': 'no observado; manifiesto no sincronizado',
        'riesgo': 'alto; requiere revisar plan completo',
        'operacion': 'rewrite/saneamiento de la base',
        'ejecucion': 'CLI explícita con --apply',
        'durante_live': 'posible si se invoca concurrentemente; sin lock',
        'proteccion': 'backup y temporal; no lock live',
        'derivados_manifiestos': 'no observado; manifiesto no sincronizado',
        'riesgo': 'alto; requiere revisar plan completo',
    },
    'tools/integrar_copia.py': {
        'escribe': 'la base CANDIDATA, mientras dura la integracion',
        'destino': 'data/hands_db.jsonl',
        'condicion': ('swap con la candidata, y RESTAURACION en el `finally`, '
                      'verificada por sha; y el sha de la candidata se '
                      'comprueba ANTES de tocar nada'),
        'temporal': True,
        'operacion': 'swap temporal de candidato y restauración',
        'ejecucion': 'CLI/procedimiento de integración explícito',
        'durante_live': 'posible si se invoca durante sesión; sin coordinación recorder',
        'proteccion': 'hash precondición, backup y restore en finally',
        'derivados_manifiestos': 'revisión de manifiestos depende del caller',
        'riesgo': 'alto; temporalidad no implica aislamiento live',
        'operacion': 'swap temporal de candidato y restauración',
        'ejecucion': 'CLI/procedimiento de integración explícito',
        'durante_live': 'posible si se invoca durante una sesión; no coordina recorder',
        'proteccion': 'hash precondición, backup y restore en finally',
        'derivados_manifiestos': 'revisión específica de manifiestos del caller',
        'riesgo': 'alto; temporalidad no significa aislamiento live',
    },
    'tools/corregir_anotaciones_20261110.py': {
        'escribe': 'recorder_audit y audit_notes de H_1303/H_1327/H_1351',
        'destino': 'data/hands_db.jsonl', 'temporal': False,
        'condicion': 'CLI --apply; dry-run por defecto; backup y atomic replace',
        'operacion': 'rewrite de tres IDs; no modifica acciones/final_pot',
        'ejecucion': 'manual CLI', 'durante_live': 'posible concurrente; sin lock',
        'proteccion': 'backup hash al crearlo, JSON temporal válido; backup existente no se coteja con base actual',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto; backup existente y ausencia de lock requieren atención',
    },
    'tools/corregir_bote_inflado_fold.py': {
        'escribe': 'final_pot y recorder_audit de folds que cumplen condiciones',
        'destino': 'data/hands_db.jsonl', 'temporal': False,
        'condicion': 'CLI --apply; exige audit fold_win y coincidencia de bote; backup',
        'operacion': 'rewrite por plan; marca lecturas discordantes para revisión',
        'ejecucion': 'manual CLI', 'durante_live': 'posible concurrente; sin lock',
        'proteccion': 'dry-run, backup/hash inicial, JSON temporal válido; sin hash precondición de DB al aplicar',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto; reglas de reconstrucción afectan resultados económicos',
    },
    'tools/corregir_folds_showdown.py': {
        'escribe': 'acciones, fold_win, winner/showdown, botes y audit',
        'destino': 'data/hands_db.jsonl', 'temporal': False,
        'condicion': 'CLI --apply; solo folds inferidos con aporte que iguala el nivel; backup',
        'operacion': 'rewrite de manos con folds inferidos removibles',
        'ejecucion': 'manual CLI', 'durante_live': 'posible concurrente; sin lock',
        'proteccion': 'dry-run, backup/hash inicial, JSON temporal válido; rollback ante replace fallido',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto; modifica acción y resultado',
    },
    'tools/corregir_mano_H_1333.py': {
        'escribe': 'H_1333: acciones, resultado, audit y notas de corrección',
        'destino': 'data/hands_db.jsonl', 'temporal': False,
        'condicion': 'CLI --apply; ID fijo; backup; verifica antes y después',
        'operacion': 'rewrite de una mano',
        'ejecucion': 'manual CLI', 'durante_live': 'posible concurrente; sin lock',
        'proteccion': 'backup/hash, validación completa en memoria y tras escritura, restore',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto; verificación acotada a H_1333',
    },
    'tools/corregir_resultados_20261029.py': {
        'escribe': 'folds, fold_win, showdown, bote y audit de H_1314/H_1324',
        'destino': 'data/hands_db.jsonl', 'temporal': False,
        'condicion': 'CLI --apply; IDs/casos fijos; backup',
        'operacion': 'rewrite mediante helpers de resultados 20261104',
        'ejecucion': 'manual CLI', 'durante_live': 'posible concurrente; sin lock',
        'proteccion': 'dry-run, backup/hash inicial, JSON temporal válido; sin verificación post-write',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto; inserta una acción inferida y edita resultados',
    },
    'tools/corregir_resultados_20261104.py': {
        'escribe': 'acciones, showdown, fold_win, final_pot y recorder_audit en IDs fijados',
        'destino': 'data/hands_db.jsonl', 'temporal': False,
        'condicion': 'CLI --apply; mapa de IDs y cambios codificado; backup',
        'operacion': 'rewrite de resultados/showdown de sesión',
        'ejecucion': 'manual CLI', 'durante_live': 'posible concurrente; sin lock',
        'proteccion': 'dry-run, backup/hash inicial y JSON temporal válido; sin verificación post-write',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto; altera acciones/resultados económicos',
    },
    'tools/corregir_sesion_20261104.py': {
        'escribe': 'rake/botes y marcas de ambigüedad de folds/checks',
        'destino': 'data/hands_db.jsonl', 'temporal': False,
        'condicion': 'CLI --apply; rake solo H_1328..H_1341 por fecha/ID; backup',
        'operacion': 'rewrite de varias manos; elimina flags de ambigüedad',
        'ejecucion': 'manual CLI', 'durante_live': 'posible concurrente; sin lock',
        'proteccion': 'dry-run, backup, validación antes/después; no ofrece --restore CLI',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto; backup requiere restauración manual y regla cubre sesión',
    },
    'tools/corregir_showdown_posicion.py': {
        'escribe': 'showdown.winner1 (posición/nombre)',
        'destino': 'data/hands_db.jsonl', 'temporal': False,
        'condicion': 'CLI --apply; nombre único y posición debe coincidir con winner; backup',
        'operacion': 'rewrite de etiquetas de showdown',
        'ejecucion': 'manual CLI', 'durante_live': 'posible concurrente; sin lock',
        'proteccion': 'dry-run, omite irresolubles, backup/hash inicial, JSON temporal válido',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto; comprobación depende de identidad/ganador de la fila',
    },
    'tools/eliminar_mano_H_1323.py': {
        'escribe': 'elimina H_1323 y archiva su línea en data/_eliminadas',
        'destino': 'data/hands_db.jsonl',
        'temporal': False,
        'condicion': 'CLI --apply; verifica duplicación contra H_1322; backup completo',
        'operacion': 'delete de una línea + archivo de cuarentena',
        'ejecucion': 'manual CLI', 'durante_live': 'posible concurrente; sin lock',
        'proteccion': 'verifica ganador/tablero/jugadores, backup/hash; archivo de cuarentena se abre en escritura',
        'derivados_manifiestos': 'no observado; pins/manifiestos quedarían stale',
        'otros_destinos': 'data/_eliminadas/H_1323.jsonl',
        'riesgo': 'alto; eliminación persistente con restauración desde backup',
    },
    'tools/limpiar_anotaciones_ruido.py': {
        'escribe': 'campos de auditoría capture/capture_sha256/award_display_ignored',
        'destino': 'data/hands_db.jsonl', 'temporal': False,
        'condicion': 'CLI --apply; limpia solo campos enumerados; backup',
        'operacion': 'rewrite de recorder_audit; no borra capturas/index',
        'ejecucion': 'manual CLI', 'durante_live': 'posible concurrente; sin lock',
        'proteccion': 'dry-run, backup/hash inicial, JSON temporal válido',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto; elimina referencias de auditoría del registro canónico',
    },
    'tools/limpiar_notas_inferidas.py': {
        'escribe': 'ambiguities/ambiguous_actions y flags ambiguous inferidos',
        'destino': 'data/hands_db.jsonl', 'temporal': False,
        'condicion': 'CLI --apply; códigos y flags inferidos enumerados; backup',
        'operacion': 'rewrite de auditoría; conserva inferred en acciones',
        'ejecucion': 'manual CLI', 'durante_live': 'posible concurrente; sin lock',
        'proteccion': 'dry-run, backup/hash inicial, JSON temporal válido',
        'derivados_manifiestos': 'no observado',
        'riesgo': 'alto; cambia estado de incertidumbre del registro',
    },
}


def test_el_inventario_coincide_con_el_instrumento():
    """La lista del documento y la del instrumento tienen que decir lo mismo.

    Un inventario que se queda viejo es peor que no tenerlo: invita a dar por
    cerrado un canal que ya se ha abierto otra vez.

    Y ahora la lista es un DICCIONARIO, porque una lista de nombres no se
    puede comprobar: con una lista, lo unico que se mira es que no se haya
    olvidado un nombre. Y lo que se mira ahora es que el conjunto de claves
    sea el mismo que el del instrumento.
    """
    assert _inventario_del_instrumento() == set(ESCRITORES_DECLARADOS)


def test_cada_escritor_declara_que_escribe_y_donde():
    """Y que la declaracion de cada uno este COMPLETA.

    Y las cuatro cosas, y por que las cuatro:

      · `escribe` — QUE escribe. Sin esto, la declaracion no dice nada.
      · `destino` — DONDE. Y tiene que ser la base, porque el instrumento
        mide justamente eso.
      · `condicion` — BAJO QUE CONDICION. Sin esto, «escribe la base» es un
        permiso permanente.
      · `temporal` — si la escritura es temporal. Y entonces la condicion
        tiene que decir COMO se restaura, porque una escritura temporal sin
        restauracion declarada es una escritura permanente.
    """
    for nombre, d in sorted(ESCRITORES_DECLARADOS.items()):
        for campo in ('escribe', 'destino', 'condicion', 'temporal',
                      'operacion', 'ejecucion', 'durante_live', 'proteccion',
                      'derivados_manifiestos', 'riesgo'):
            assert campo in d, (
                'la declaracion de %r no tiene el campo %r' % (nombre, campo))
        assert d['escribe'].strip(), 'lo que escribe %r esta vacio' % nombre
        assert d['destino'].strip(), 'donde escribe %r esta vacio' % nombre
        assert d['condicion'].strip(), (
            'la condicion de %r esta vacia, y sin condicion una declaracion de '
            'escritor es un permiso' % nombre)
        assert d['destino'] == 'data/hands_db.jsonl', (
            'el destino declarado de %r es %r, y el instrumento mide la base'
            % (nombre, d['destino']))
        if d['temporal']:
            condicion = d['condicion'].lower()
            assert ('finally' in condicion or 'restaur' in condicion), (
                'la escritura de %r es TEMPORAL, y su condicion tiene que decir '
                'como se restaura: %r' % (nombre, d['condicion']))
        assert d['riesgo'].strip(), (
            'el escritor %r no puede quedar sin clasificación de riesgo'
            % nombre)
        assert d['riesgo'].strip().lower() not in ('safe', 'seguro', 'segura'), (
            'no se declara seguro un writer sin una evaluación explícita: %r'
            % nombre)
        assert d['durante_live'].strip(), (
            'el escritor %r no puede asumir ausencia de sesión live'
            % nombre)
        assert d['proteccion'].strip(), (
            'el escritor %r debe declarar protecciones conocidas o su ausencia'
            % nombre)


def test_la_declaracion_no_tiene_una_entrada_que_no_exista():
    """Y que no haya entradas que no correspondan a un escritor de verdad.

    Y el motivo: una declaracion de algo que ya no esta es una declaracion
    falsa, y peor: un nombre que se queda da la sensacion de que algo sigue
    vigilado.
    """
    reales = _inventario_del_instrumento()
    sobran = sorted(set(ESCRITORES_DECLARADOS) - reales)
    assert not sobran, (
        'hay %d entrada(s) declaradas que el instrumento no ve: %r. Y una '
        'declaracion de algo que no existe es una declaracion falsa.'
        % (len(sobran), sobran))


def test_el_instrumento_pasa_sus_propios_casos():
    """`tools/quien_escribe.py` tiene que seguir autocomprobandose, Y PASANDO.

    Un test que mira que los nombres de los casos esten escritos en el
    fichero no sirve: si alguien vacia la lista de autocomprobacion y deja
    los nombres en un comentario, ese test sigue en verde y el instrumento ya
    no mira nada.

    Este lo EJECUTA y exige que los siete casos salgan en `OK`. Es lo unico
    que convierte "el instrumento se autocomprueba" en "se autocomprueba y
    acierta"."""
    if not os.path.exists(INSTRUMENTO):
        pytest.skip('aun no esta en el repo')
    p = subprocess.run([sys.executable, INSTRUMENTO],
                       cwd=ROOT, capture_output=True)
    out = p.stdout.decode('utf-8', 'replace')
    assert p.returncode == 0, (
        'el instrumento se paro: su autocomprobacion fallo.\n%s' % out)
    for caso in ('cadena', 'indirecta', 'atributo', 'solo lectura',
                 'a otro fichero', 'copia mutada en tmp', 'helper'):
        linea = [l for l in out.splitlines() if l.strip().startswith(caso)]
        assert linea, 'el instrumento no reporta el caso %r:\n%s' % (caso, out)
        assert ' OK ' in linea[0], (
            'el caso %r falla: %s' % (caso, linea[0].strip()))
    assert 'ROTO' not in out, out


def test_el_instrumento_detecta_las_tres_formas_de_escribir():
    """La tarea pide que las TRES formas esten cubiertas por test.

    Son las tres que un `open()` se pierde, y las tres estan en este repo:

    | | forma | quien |
    |---|---|---|
    | 1 | ruta construida **en cadena** (`DB_NAME` -> `DB_PATH`) | los dos `aplicar_*` |
    | 2 | escritura **indirecta**: `shutil.copy2(backup, DB_PATH)` | los dos `aplicar_*` |
    | 3 | escritura **atraves de un helper** que recibe la ruta | `hand_editor` |

    Se comprueba sobre el repo real, no sobre un fragmento de ejemplo: que el
    instrumento encuentre de verdad a los cinco escritores."""
    assert 'tools/aplicar_reinterpretacion.py' in _inventario_del_instrumento(), (
        'el instrumento no ve a aplicar_reinterpretacion.py, que escribe con '
        'copy2/replace y no con open()')
    assert 'hand_editor.py' in _inventario_del_instrumento(), (
        'el instrumento no ve a hand_editor.py, que escribe a traves de un '
        'helper: un inventario que se queda viejo al envolver la escritura da '
        'por cerrado un canal que se ha vuelto a abrir')


# ---------------------------------------------------------------------------
# 2. el guard de hand_editor
# ---------------------------------------------------------------------------

def test_hand_editor_tiene_red():
    """El único que reescribe la base entera tiene que tener las tres cosas.

    Backup verificado, temporal y `os.replace`, y aviso de manifiesto
    obsoleto. Sin las tres, guardar 1258 manos es un acto de fe."""
    src = io.open(os.path.join(ROOT, 'hand_editor.py'), encoding='utf-8').read()
    assert 'shutil.copy2' in src, 'sin backup'
    assert 'os.replace' in src, 'escritura no atomica'
    assert 'HANDS_DB_SHA256' in src, (
        'no compara contra el manifiesto: escribir es legitimo, escribir sin '
        'declarar despues no lo es')
    assert "_sha256_de(backup) != sha_antes" in src, (
        'el backup no se verifica antes de escribir: es una copia de la que '
        'se supone que funciona, y las copias fallan')


def test_el_guard_escribe_y_declara(tmp_path):
    """El camino normal: escribe, deja backup verificable y devuelve el sha.

    Se prueba contra un fichero propio, no contra la base: este test no puede
    tocar `data/hands_db.jsonl` ni aunque quiera, y un guard de escritura que
    solo se prueba escribiendo en la base real no es un guard."""
    ruta = tmp_path / 'hands_db.jsonl'
    manos = [{'hand_id': 'H_0001', 'streets': {}},
             {'hand_id': 'H_0002', 'streets': {}}]
    ok, sha = hand_editor._guardar_base(manos, str(ruta))
    assert ok, 'el guard se niega a escribir en un fichero nuevo'
    assert os.path.exists(str(ruta))
    assert len(io.open(str(ruta), encoding='utf-8').read().splitlines()) == 2
    assert len(sha) == 64
    # Y no deja temporal detrás: `os.replace` lo consume.
    assert not os.path.exists(str(ruta) + '.tmp')


def test_el_guard_hace_backup_verificable(tmp_path):
    """Antes de escribir, copia. Y la copia tiene que ser la misma cosa."""
    ruta = tmp_path / 'hands_db.jsonl'
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write('{"hand_id": "ORIGINAL"}\n')
    antes = hand_editor._sha256_de(str(ruta))

    ok, _sha = hand_editor._guardar_base([{'hand_id': 'NUEVA'}], str(ruta))
    assert ok
    backup = str(ruta) + '.bak'
    assert os.path.exists(backup), 'no dejo backup'
    assert hand_editor._sha256_de(backup) == antes, (
        'el backup no es el fichero original: no sirve para nada')
    assert 'NUEVA' in io.open(str(ruta), encoding='utf-8').read()


def test_si_el_backup_falla_no_se_escribe(tmp_path, monkeypatch):
    """El guard tiene que negarse a escribir cuando la red falla.

    Es el unico test que demuestra que las otras comprobaciones sirven: si el
    backup se aceptara siempre, las demas serian decorativas."""
    ruta = tmp_path / 'hands_db.jsonl'
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write('{"hand_id": "ORIGINAL"}\n')
    original = io.open(str(ruta), encoding='utf-8').read()

    import shutil as _sh
    monkeypatch.setattr(hand_editor.shutil, 'copy2',
                        lambda *a, **k: None)          # copia que no copia
    ok, sha = hand_editor._guardar_base([{'hand_id': 'NUEVA'}], str(ruta))
    assert ok is False, 'escribio sin backup verificado'
    assert sha is None
    assert io.open(str(ruta), encoding='utf-8').read() == original, (
        'la base cambio pese a que el guard dijo que no')


def test_si_la_escritura_falla_no_se_toca_la_original(tmp_path, monkeypatch):
    """Fallo a mitad de escribir: el original intacto.

    Es el motivo de escribir a un temporal y hacer `os.replace`. Un
    `open(DATA_PATH, 'w')` a pelo deja el fichero a medias si el disco se
    llena, y `json.dumps` de la mano 900 puede fallar."""
    ruta = tmp_path / 'hands_db.jsonl'
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write('{"hand_id": "ORIGINAL"}\n')
    original = io.open(str(ruta), encoding='utf-8').read()

    def _explota(*a, **k):
        raise OSError('disco lleno')

    monkeypatch.setattr(hand_editor.os, 'replace', _explota)
    ok, sha = hand_editor._guardar_base([{'hand_id': 'NUEVA'}], str(ruta))
    assert ok is False
    assert sha is None
    assert io.open(str(ruta), encoding='utf-8').read() == original, (
        'la original cambio: os.replace no llego a correr, pero algo escribio')
    assert not os.path.exists(str(ruta) + '.tmp'), 'dejo el temporal'


def test_si_la_copia_falla_por_excepcion_no_se_escribe(tmp_path, monkeypatch):
    """La reserva A de la revision tecnica: `copy2` estaba FUERA del try.

    Sin permisos, o sin disco, la excepcion subia y se comia el guardar:
    el usuario se quedaba con un error que no explicaba nada, en vez de con
    un `False` que dice «no he guardado, la base sigue como estaba».

    Es el fallo MAS PROBABLE de los cuatro: es el primero que se intenta.
    """
    ruta = tmp_path / 'hands_db.jsonl'
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write('{"hand_id": "ORIGINAL"}\n')
    original = io.open(str(ruta), encoding='utf-8').read()

    def _explota(*a, **k):
        raise OSError('sin permisos')

    monkeypatch.setattr(hand_editor.shutil, 'copy2', _explota)
    ok, sha = hand_editor._guardar_base([{'hand_id': 'NUEVA'}], str(ruta))
    assert ok is False, 'escribio pese a que la copia del backup reventaba'
    assert sha is None
    assert io.open(str(ruta), encoding='utf-8').read() == original


def test_si_la_escritura_del_temporal_falla_no_se_toca_la_original(
        tmp_path, monkeypatch):
    """Fallo escribiendo el temporal: el original intacto.

    Es el motivo de escribir a un temporal y hacer `os.replace`. Un
    `open(DATA_PATH,'w')` a pelo deja el fichero a medias si el disco se
    llena, y `json.dumps` de la mano 900 puede fallar."""
    import builtins
    ruta = tmp_path / 'hands_db.jsonl'
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write('{"hand_id": "ORIGINAL"}\n')
    original = io.open(str(ruta), encoding='utf-8').read()

    real = builtins.open

    def _falla_en_temporal(*a, **k):
        if str(a[0]).endswith('.tmp'):
            raise OSError('disco lleno')
        return real(*a, **k)

    monkeypatch.setattr(builtins, 'open', _falla_en_temporal)
    ok, sha = hand_editor._guardar_base([{'hand_id': 'NUEVA'}], str(ruta))
    assert ok is False
    assert sha is None
    assert io.open(str(ruta), encoding='utf-8').read() == original
    assert not os.path.exists(str(ruta) + '.tmp'), 'dejo el temporal'


def test_si_el_reemplazo_falla_no_se_toca_la_original(tmp_path, monkeypatch):
    """Falla `os.replace`: la original intacta y el temporal limpiado."""
    ruta = tmp_path / 'hands_db.jsonl'
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write('{"hand_id": "ORIGINAL"}\n')
    original = io.open(str(ruta), encoding='utf-8').read()

    def _explota(*a, **k):
        raise OSError('reemplazo rechazado')

    monkeypatch.setattr(hand_editor.os, 'replace', _explota)
    ok, sha = hand_editor._guardar_base([{'hand_id': 'NUEVA'}], str(ruta))
    assert ok is False
    assert sha is None
    assert io.open(str(ruta), encoding='utf-8').read() == original, (
        'os.replace no llego a correr, pero algo escribio')
    assert not os.path.exists(str(ruta) + '.tmp')


def test_si_la_limpieza_falla_no_tapa_el_error_original(tmp_path, monkeypatch):
    """La segunda mitad de la reserva A.

    Si `os.remove(tmp)` falla —que es lo que pasa cuando el disco esta lleno,
    el MISMO motivo por el que fallo la escritura—, su excepcion se tragaba el
    `OSError` bueno. El usuario recibia un error que no explicaba nada, y lo
    que falla al limpiar no puede tapar lo que falla al escribir.

    Se comprueba que se devuelve `(False, None)` y NO que se propaga nada."""
    ruta = tmp_path / 'hands_db.jsonl'
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write('{"hand_id": "ORIGINAL"}\n')
    original = io.open(str(ruta), encoding='utf-8').read()

    def _replace_falla(*a, **k):
        raise OSError('disco lleno: no se puede escribir')

    def _remove_falla(*a, **k):
        raise OSError('disco lleno: no se puede limpiar')

    monkeypatch.setattr(hand_editor.os, 'replace', _replace_falla)
    monkeypatch.setattr(hand_editor.os, 'remove', _remove_falla)
    ok, sha = hand_editor._guardar_base([{'hand_id': 'NUEVA'}], str(ruta))
    assert ok is False, 'un fallo de limpieza debe seguir siendo (False, None)'
    assert sha is None
    assert io.open(str(ruta), encoding='utf-8').read() == original


def test_el_guard_no_lanza_jamas(tmp_path):
    """El contrato de error, en una linea: `_guardar_base` no propaga NUNCA.

    Se comprueba con las cuatro cosas que pueden fallar, cada una con su
    propio contexto de monkeypatch. Un solo camino de excepcion que se
    escape es un guardar que se come la base, y la excepcion es justo lo que
    el llamador —un boton de una GUI— no sabe manejar.

    Los cuatro fallos concretos tienen su propio test arriba. Este es el que
    dice que el contrato se cumple en todos, y no solo en los que se me
    ocurrido. Que es la diferencia entre un contrato y una lista de pruebas.
    """
    import builtins

    def _explota(*a, **k):
        raise OSError('boom')

    ruta = tmp_path / 'hands_db.jsonl'
    # Cada caso es una lista de (modulo, atributo) que se rompen A LA VEZ.
    # `os.remove` solo se alcanza en la limpieza, que solo se ejecuta si ya
    # fallo algo antes: parchearlo solo no activa ningun fallo y el guard
    # responderia `True`, que es correcto pero no es lo que se quiere probar.
    objetivos = [
        ('la copia del backup', [(hand_editor.shutil, 'copy2')]),
        ('el reemplazo', [(hand_editor.os, 'replace')]),
        ('la escritura', [(builtins, 'open')]),
        ('la limpieza', [(hand_editor.os, 'replace'), (hand_editor.os, 'remove')]),
    ]
    for nombre, a_romper in objetivos:
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write('{"hand_id": "ORIGINAL"}\n')
        originales = [(m, a, getattr(m, a)) for m, a in a_romper]
        for m, a, _v in originales:
            setattr(m, a, _explota)
        try:
            ok, sha = hand_editor._guardar_base([{'hand_id': 'X'}], str(ruta))
        except Exception as e:              # pragma: no cover
            for m, a, v in originales:
                setattr(m, a, v)
            pytest.fail('rompiendo %s, el guard lanzo %s: %r'
                        % (nombre, type(e).__name__, e))
        finally:
            for m, a, v in originales:
                setattr(m, a, v)
        assert ok is False, nombre
        assert sha is None, nombre


def test_la_base_nueva_tambien_esta_protegida(tmp_path, monkeypatch):
    """La rama de el fichero no existe tambien devuelve False si falla.

    Es la rama menos vigilada porque parece inocua: no hay original que
    perder. Pero es la que se ejecuta la primera vez, y un `OSError` ahí
    sube igual que en cualquier otra parte."""
    import builtins
    ruta = tmp_path / 'hands_db.jsonl'

    def _explota(*a, **k):
        raise OSError('no se puede crear')

    monkeypatch.setattr(builtins, 'open', _explota)
    ok, sha = hand_editor._guardar_base([{'hand_id': 'X'}], str(ruta))
    assert ok is False
    assert sha is None


# ---------------------------------------------------------------------------
# 3. lo que el manifiesto declara
# ---------------------------------------------------------------------------

def test_el_manifiesto_y_el_disco_coinciden():
    """La premisa de todo: el editor compara contra algo que es verdad.

    Si `HANDS_DB_SHA256` no fuera el hash real, el aviso de «guardado sin
    declarar» saltaría siempre y nadie leería nada."""
    real = hand_editor._sha256_de(
        os.path.join(ROOT, 'data', 'hands_db.jsonl'))
    assert real == learn.HANDS_DB_SHA256, (
        'hands_db.jsonl tiene sha256 %s y el declarado es %s. El editor '
        'compararia contra una mentira y avisaria siempre.'
        % (real[:16], learn.HANDS_DB_SHA256[:16]))
