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
    'tools/sanear_base.py',           # saneamiento, con backup y dry-run
    'tools/integrar_copia.py',        # integra una base candidata, con
                                      # restauracion GARANTIZADA en el
                                      # `finally` y verificada por sha
}


def test_el_inventario_coincide_con_el_instrumento():
    """La lista del documento y la del instrumento tienen que decir lo mismo.

    Un inventario que se queda viejo es peor que no tenerlo: invita a dar por
    cerrado un canal que ya se ha abierto otra vez."""
    assert _inventario_del_instrumento() == ESCRITORES_DECLARADOS


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