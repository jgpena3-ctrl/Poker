# -*- coding: utf-8 -*-
"""Manifiesto de snapshots y verificacion de identidad.

Fase 1 de la politica de mantenimiento: descriptores y fixture inmutable.
No mide los 22 pines historicos ni convierte el snapshot en la base actual.

Reglas que se comprueban:

- el manifiesto declara identidad suficiente (path, commit, sha256, lineas);
- el fixture existe y coincide con su SHA-256 y su numero de lineas;
- cada snapshot es una poblacion historica separada, no un corte de las
  primeras N lineas de la base dinamica;
- el manifiesto `HANDS_DB_*` sigue coincidiendo con el disco antes de medir.
"""
import hashlib
import json
import os
import re
import sys

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from motor import learn  # noqa: E402


MANIFEST = ROOT / 'tests' / 'data' / 'snapshots.json'
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
COMMIT_RE = re.compile(r'^[0-9a-f]{7,40}$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

CAMPOS_OBLIGATORIOS = (
    'id',
    'path',
    'source_path',
    'commit',
    'sha256',
    'lineas',
    'purpose',
    'created',
    'owner',
    'metrics_version',
)


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _lineas(data):
    return data.splitlines()


def _jsonl(data):
    return [json.loads(line.decode('utf-8')) for line in _lineas(data) if line.strip()]


@pytest.fixture(scope='session')
def manifiesto():
    assert MANIFEST.exists(), 'falta el manifiesto %s' % MANIFEST
    with MANIFEST.open('r', encoding='utf-8') as f:
        datos = json.load(f)
    assert isinstance(datos, dict), 'el manifiesto debe ser un objeto JSON'
    assert 'snapshots' in datos, 'el manifiesto debe declarar "snapshots"'
    snapshots = datos['snapshots']
    assert isinstance(snapshots, list) and snapshots, '"snapshots" debe ser una lista no vacia'
    return snapshots


@pytest.fixture(scope='session')
def snapshot_1253(manifiesto):
    entradas = [s for s in manifiesto if s['id'] == 's1253-51a6fb9']
    assert len(entradas) == 1, 'debe existir exactamente un snapshot s1253-51a6fb9'
    entrada = entradas[0]
    path = ROOT / entrada['path']
    assert path.is_file(), 'falta el fixture %s' % path
    data = path.read_bytes()
    assert _sha256(data) == entrada['sha256'], (
        'el fixture %s no coincide con el sha256 declarado' % entrada['path'])
    lineas = _lineas(data)
    assert len(lineas) == entrada['lineas'], (
        'el fixture %s tiene %d lineas; el manifiesto declara %d'
        % (entrada['path'], len(lineas), entrada['lineas']))
    return {
        'entrada': entrada,
        'bytes': data,
        'lineas': lineas,
        'manos': _jsonl(data),
    }


def test_el_manifiesto_tiene_el_esquema_minimo(manifiesto):
    ids = []
    for entrada in manifiesto:
        faltan = [campo for campo in CAMPOS_OBLIGATORIOS if campo not in entrada]
        assert not faltan, 'snapshot %r sin campos: %r' % (entrada.get('id'), faltan)

        assert isinstance(entrada['id'], str) and entrada['id'], 'id vacio'
        assert isinstance(entrada['path'], str) and entrada['path'], 'path vacio'
        assert isinstance(entrada['source_path'], str) and entrada['source_path'], (
            'source_path vacio para %s' % entrada['id'])
        assert not os.path.isabs(entrada['path']), 'path debe ser relativo: %s' % entrada['path']
        assert '..' not in Path(entrada['path']).parts, 'path no debe salir del repo: %s' % entrada['path']
        assert (ROOT / entrada['source_path']).is_file(), (
            'source_path no existe: %s' % entrada['source_path'])
        assert COMMIT_RE.match(entrada['commit']), 'commit invalido: %r' % entrada['commit']
        assert SHA256_RE.match(entrada['sha256']), 'sha256 invalido: %r' % entrada['sha256']
        assert isinstance(entrada['lineas'], int) and not isinstance(entrada['lineas'], bool)
        assert entrada['lineas'] > 0, 'lineas debe ser positivo'
        for campo in ('purpose', 'owner', 'metrics_version'):
            assert isinstance(entrada[campo], str) and entrada[campo].strip(), (
                '%s vacio para %s' % (campo, entrada['id']))
        assert DATE_RE.match(entrada['created']), 'created invalido: %r' % entrada['created']
        ids.append(entrada['id'])

    assert len(ids) == len(set(ids)), 'hay ids de snapshot duplicados'


def test_cada_fixture_coincide_con_su_hash_y_sus_lineas(manifiesto):
    for entrada in manifiesto:
        path = ROOT / entrada['path']
        assert path.is_file(), 'falta el fixture %s' % entrada['path']
        data = path.read_bytes()
        assert _sha256(data) == entrada['sha256'], (
            '%s: sha256 del fixture distinto del declarado' % entrada['id'])
        lineas = _lineas(data)
        assert len(lineas) == entrada['lineas'], (
            '%s: %d lineas fisicas, esperadas %d'
            % (entrada['id'], len(lineas), entrada['lineas']))
        assert sum(1 for line in lineas if line.strip()) == entrada['lineas'], (
            '%s: hay lineas vacias en el fixture' % entrada['id'])
        manos = _jsonl(data)
        assert len(manos) == entrada['lineas'], (
            '%s: no todas las lineas son JSON validas' % entrada['id'])
        hand_ids = [m.get('hand_id') for m in manos]
        assert all(isinstance(h, str) and h for h in hand_ids), (
            '%s: hay manos sin hand_id' % entrada['id'])
        assert len(hand_ids) == len(set(hand_ids)), (
            '%s: hay hand_id duplicados' % entrada['id'])


def test_ningun_snapshot_es_un_corte_de_lineas_de_la_fuente(manifiesto):
    for entrada in manifiesto:
        snapshot = _jsonl((ROOT / entrada['path']).read_bytes())
        fuente = _jsonl((ROOT / entrada['source_path']).read_bytes())
        assert len(fuente) >= entrada['lineas'], (
            '%s: la fuente tiene menos lineas que el snapshot' % entrada['id'])
        primeras = fuente[:entrada['lineas']]
        assert snapshot != primeras, (
            '%s: el snapshot coincide con las primeras %d lineas de la fuente; '
            'es un corte, no una poblacion historica separada'
            % (entrada['id'], entrada['lineas']))


def test_el_manifiesto_de_la_base_actual_coincide_con_el_disco():
    data = Path(learn.DB_PATH).read_bytes()
    assert _sha256(data) == learn.HANDS_DB_SHA256, (
        'el disco no coincide con HANDS_DB_SHA256; no se debe medir sobre una '
        'base distinta de la declarada')
    assert len(_lineas(data)) == learn.HANDS_DB_LINEAS, (
        'el disco tiene %d lineas; HANDS_DB_LINEAS declara %d'
        % (len(_lineas(data)), learn.HANDS_DB_LINEAS))
    assert COMMIT_RE.match(learn.HANDS_DB_COMMIT), (
        'HANDS_DB_COMMIT invalido: %r' % learn.HANDS_DB_COMMIT)


def test_el_snapshot_no_sustituye_a_la_base_actual(snapshot_1253):
    actual = Path(learn.DB_PATH).read_bytes()
    assert snapshot_1253['bytes'] != actual, (
        'el snapshot 1253 no puede ser el fichero actual')
    assert len(snapshot_1253['manos']) == snapshot_1253['entrada']['lineas']
