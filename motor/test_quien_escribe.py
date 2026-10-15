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
ESCRITORES_DECLARADOS = {
    'hand_editor.py',                 # REESCRIBE la base entera
    'recorder/record_hand.py',        # AÑADE una mano
    'recorder/recorder_live.py',      # AÑADE manos
    'tools/aplicar_correcciones.py',  # migraciones, con backup
    'tools/aplicar_reinterpretacion.py',
}


def test_el_inventario_coincide_con_el_instrumento():
    """La lista del documento y la del instrumento tienen que decir lo mismo.

    Un inventario que se queda viejo es peor que no tenerlo: invita a dar por
    cerrado un canal que ya se ha abierto otra vez."""
    assert _inventario_del_instrumento() == ESCRITORES_DECLARADOS


def test_el_instrumento_declara_sus_propios_casos():
    """`tools/quien_escribe.py` tiene que seguir autocomprobándose.

    Un instrumento que no demuestra que ve lo que dice ver no puede usarse
    para decir que no hay nada. Es el mismo argumento que
    `RESUMEN_SECCION.md` §8, aplicado a este fichero."""
    if not os.path.exists(INSTRUMENTO):
        pytest.skip('aun no esta en el repo')
    texto = io.open(INSTRUMENTO, encoding='utf-8').read()
    for caso in ('cadena', 'indirecta', 'atributo', 'solo lectura',
                 'a otro fichero', 'copia mutada en tmp'):
        assert caso in texto, (
            'falta el caso de autocomprobacion %r: el instrumento se ha '
            'quedado sin el caso que lo hacia fiable' % caso)
    assert 'raise SystemExit(1)' in texto, (
        'el instrumento no se detiene cuando su autocomprobacion falla; eso '
        'dejaria pasar un instrumento roto dando autoridad')


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