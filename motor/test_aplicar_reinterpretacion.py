# -*- coding: utf-8 -*-
"""`aplicar_reinterpretacion.py`: sus caminos de salida y de escritura.

revision_2 §1 encontró dos caminos que devolvían éxito sin comprobar el
alcance:

  a) el fichero ya coincidía (idempotencia) y el alcance no cuadraba
  b) dry-run con el alcance sin cuadrar

Y este bloque construyó el caso (c) al equivocarse: `--apply` sobrescribió
928 líneas que alguien había escrito a mano, porque el script solo comparaba
con su PROPIA salida y no con la de nadie más. Un fichero ajeno no es un
fichero que este script pueda reemplazar, por muy bien que cuadre su alcance.
"""
import io
import json
import os
import shutil

import pytest

from motor import learn
from tools import aplicar_reinterpretacion as AR
from tools.aplicar_reinterpretacion import (COMMIT_ANTES, SHA_ANTES, SHA_SALIDA,
                                            main, set_tocado)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _previa():
    return AR.version_previa()


def _esperado():
    lineas, _cambios = AR.aplicar_a_mano(_previa())
    return lineas


def _escribir(lineas, destino):
    with io.open(destino, 'w', encoding='utf-8', newline='\n') as f:
        for l in lineas:
            f.write(l + '\n')


# --- (a) y (b): el alcance bloquea los dos caminos de exito ---------------

def _sin_una_mano(monkeypatch, hid):
    """Quita `hid` del conjunto declarado, sin recursion.

    `AR.learn` ES el modulo `learn`, asi que la lambda no puede llamar a
    `learn.manos_excluidas()`: estaria llamandose a si misma. Se captura el
    valor antes de parchearlo.
    """
    original = frozenset(learn.manos_excluidas())
    valor = original - {hid}
    monkeypatch.setattr(AR.learn, 'manos_excluidas', lambda: valor)
    return valor


def _sin_revision(monkeypatch):
    """Quita el bloqueo por revision manual para probar el resto.

    Los tres bloqueos se prueban por separado: alcance (2), fichero ajeno (3)
    y revision en curso (4). Un test que los mezclara no sabria cual fallo.
    """
    monkeypatch.setattr(AR.learn, 'REVISION_EN_CURSO', False)


# --- la revision en curso, que va antes que los otros dos -------------------

def test_la_revision_en_curso_impide_que_un_script_escriba(monkeypatch, tmp_path,
                                                           capsys):
    """Mientras el mantenedor revisa, `--apply` se niega.

    Y `--descartar-cambios` NO lo salta: saltarlo significaria terminar la
    revision, no escribir mas rapido.

    Lo que se protege es UNA cosa: que un SCRIPT escriba. Lo que el mantenedor
    haga a mano es la revision, y para eso esta `HANDS_DB_SHA256`. Antes este
    guard decia tambien "la base esta congelada", que era contradictorio —
    revisar una mano ES cambiarla— y por eso 9b5905a dejo el repo en rojo. Ver
    `learn.REVISION_EN_CURSO`.
    """
    destino = tmp_path / 'hands_db.jsonl'
    _escribir(_previa(), destino)
    monkeypatch.setattr(AR, 'DB_PATH', str(destino))
    assert AR.learn.REVISION_EN_CURSO is True, (
        'la revision manual deberia seguir en curso')
    rc = main(['--apply'])
    out = capsys.readouterr().out
    assert rc == 4, out
    assert 'REVISION EN CURSO' in out, out
    assert 'NO es un congelamiento' in out, out
    rc2 = main(['--apply', '--descartar-cambios'])
    out2 = capsys.readouterr().out
    assert rc2 == 4, out2
    assert 'REVISION EN CURSO' in out2, out2


def test_el_dry_run_informa_de_la_revision_pero_no_falla(monkeypatch,
                                                         tmp_path, capsys):
    """Un dry-run no escribe nada, asi que informa y sigue.

    Un informe que no se puede ver no sirve para decidir.
    """
    destino = tmp_path / 'hands_db.jsonl'
    _escribir(_previa(), destino)
    monkeypatch.setattr(AR, 'DB_PATH', str(destino))
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert 'revision manual en curso' in out, out


def test_el_alcance_bloquea_el_camino_idempotente(monkeypatch, tmp_path, capsys):
    """revision_2 §1 (a).

    El fichero actual coincide con la salida del script, asi que la
    comprobacion de idempotencia se dispara. Pero si el ALCANCE no cuadra, el
    script esta produciendo otra cosa, y da igual que esa otra cosa este
    escrita: tiene que devolver error.
    """
    destino = tmp_path / 'hands_db.jsonl'
    _escribir(_esperado(), destino)
    monkeypatch.setattr(AR, 'DB_PATH', str(destino))
    _sin_revision(monkeypatch)
    _sin_una_mano(monkeypatch, 'H_0722')
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 2, out
    assert 'ALCANCE' in out, out


def test_el_alcance_bloquea_el_dry_run(monkeypatch, tmp_path, capsys):
    """revision_2 §1 (b). El dry-run tambien falla si el alcance no cuadra."""
    destino = tmp_path / 'hands_db.jsonl'
    _escribir(_previa(), destino)
    monkeypatch.setattr(AR, 'DB_PATH', str(destino))
    _sin_revision(monkeypatch)
    _sin_una_mano(monkeypatch, 'H_0722')
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 2, out
    assert 'ALCANCE' in out, out


def test_alcance_correcto_en_dry_run_da_cero(monkeypatch, tmp_path, capsys):
    """El camino de exito normal sigue funcionando."""
    destino = tmp_path / 'hands_db.jsonl'
    _escribir(_previa(), destino)
    monkeypatch.setattr(AR, 'DB_PATH', str(destino))
    _sin_revision(monkeypatch)
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert 'alcance:' in out and 'exactamente las declaradas' in out, out


# --- (c): el fichero ajeno no se sobrescribe -----------------------------

def test_no_sobrescribe_un_fichero_ajeno(monkeypatch, tmp_path, capsys):
    """revision_2, y el caso que este bloque construyó equivocándose.

    Un fichero que no es ni la referencia ni la salida de este script ha sido
    editado por alguien. `--apply` tiene que negarse.
    """
    destino = tmp_path / 'hands_db.jsonl'
    lineas = _previa().splitlines()
    una = json.loads(lineas[5])
    una['final_pot'] = 999.0
    lines = list(lineas)
    lines[5] = json.dumps(una, ensure_ascii=False)
    _escribir(lines, destino)
    # Solo se parchea `DB_PATH`. `ROOT` NO: `version_previa()` lo usa como
    # `cwd` de `git show`, y parchearlo rompe la lectura de la referencia.
    # El backup va al directorio real, que esta en `.gitignore`.
    monkeypatch.setattr(AR, 'DB_PATH', str(destino))
    _sin_revision(monkeypatch)

    rc = main(['--apply'])
    out = capsys.readouterr().out
    assert rc == 3, out
    assert 'ajeno' in out and 'SOBRESCRIBE' in out, out
    # y lo importante: el fichero ajeno sigue intacto
    assert json.loads(io.open(str(destino), encoding='utf-8').read()
                      .splitlines()[5])['final_pot'] == 999.0


def test_descartar_cambios_requiere_los_dos_flags(monkeypatch, tmp_path, capsys):
    """`--descartar-cambios` sin `--apply` no escribe: sigue siendo dry-run."""
    destino = tmp_path / 'hands_db.jsonl'
    lines = _previa().splitlines()
    una = json.loads(lines[5])
    una['final_pot'] = 999.0
    lines[5] = json.dumps(una, ensure_ascii=False)
    _escribir(lines, destino)
    monkeypatch.setattr(AR, 'DB_PATH', str(destino))
    _sin_revision(monkeypatch)
    antes = io.open(str(destino), encoding='utf-8').read()
    rc = main(['--descartar-cambios'])
    assert rc == 0, capsys.readouterr().out
    assert io.open(str(destino), encoding='utf-8').read() == antes


# --- (d) la verificacion post compara con el resultado esperado -----------

def test_la_verificacion_post_compara_con_el_esperado(monkeypatch, tmp_path,
                                                     capsys):
    """revision_2 §1: la garantia declarada era mas fuerte que la hecha.

    Antes solo se comprobaban el numero de manos y el invariante CM-004, y las
    dos pueden cumplirse con un fichero equivocado. Ahora se compara el
    fichero releido con lo que el script dice que produce.
    """
    codigo = io.open(os.path.join(ROOT, 'tools',
                                  'aplicar_reinterpretacion.py'),
                     encoding='utf-8').read()
    assert 'el fichero releido es IDENTICO al resultado esperado' in codigo
    assert 'NO es el resultado esperado' in codigo
    # y no basta con el invariante
    assert 'invariante CM-004 violado' in codigo


# --- revision_2 §3: los resultados de la regla, anclados ------------------

def test_los_resultados_de_la_regla_estan_fijados():
    """El numero y la identidad de las manos que la regla deriva.

    El verificador depende de que el codigo ACTUAL de `learn` siga
    reproduciendo la regla historica. Si la cambia, cambia el conjunto
    derivado, y sin este test no habria nada que lo notase.
    """
    anteriores = [json.loads(l) for l in _previa().splitlines() if l.strip()]
    derivadas = set()
    for h in anteriores:
        for _i, _amt, causa in learn.entradas_bb_rechazadas(h):
            if causa == learn.CAUSA_ORDEN:
                derivadas.add(h['hand_id'])
    assert len(anteriores) == 1280
    assert len(derivadas) == 23
    assert derivadas == set(learn.manos_excluidas()), (
        sorted(derivadas ^ set(learn.manos_excluidas())))


def test_el_conjunto_de_manos_tocadas_esta_fijado():
    """23 de CM-004 + H_0350. Ni una mas, ni una menos."""
    tocadas = set_tocado(_previa(), '\n'.join(_esperado()))
    declaradas = {'H_0350'} | set(learn.manos_excluidas())
    assert tocadas == declaradas, sorted(tocadas ^ declaradas)
    assert len(tocadas) == 24


def test_los_sha_estan_fijados():
    """La referencia por commit Y por contenido, y la salida por contenido.

    Direccionar por commit no basta: el commit no garantiza que siga siendo
    la version que creimos. Y la salida tiene que tener hash propio, que es
    lo que permite reconocer un fichero ajeno.
    """
    import hashlib
    crudo = AR.subprocess.run(
        ['git', 'show', '%s:data/hands_db.jsonl' % COMMIT_ANTES],
        cwd=ROOT, capture_output=True).stdout
    assert hashlib.sha256(crudo).hexdigest() == SHA_ANTES
    lineas = _esperado()
    con_nl = ''.join(l + '\n' for l in lineas).encode('utf-8')
    assert hashlib.sha256(con_nl).hexdigest() == SHA_SALIDA, (
        'la salida de este script ya no es la que esta fijada en '
        'SHA_SALIDA: si es a proposito, actualiza el valor y explica por que')