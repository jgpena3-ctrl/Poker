# -*- coding: utf-8 -*-
"""Verifica de solo lectura la adopcion de la base de 1344 manos.

Comprueba, sin escribir ni corregir archivos:

- SHA-256, tamano y numero de lineas de `data/hands_db.jsonl`;
- correspondencia con `HANDS_DB_COMMIT`, `HANDS_DB_SHA256` y
  `HANDS_DB_LINEAS` de `motor.learn`;
- que el blob del commit canonico coincide con el fichero en disco;
- los hashes registrados de los siete derivados canonicos;
- integridad de `data/calibration_window.json` y de la ventana de 877 manos;
- que la calibracion sigue en estado provisional;
- los metadatos que identifican los derivados como legado de 51a6fb9/1253;
- que `MULTIWAY_SOPORTADO` sigue siendo `False`.

Uso:
    python tools/verificar_adopcion_1344.py

Codigo de salida: 0 si todas las garantias se cumplen, 1 si falla cualquiera.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / 'tools'
for _path in (str(ROOT), str(TOOLS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from motor import learn  # noqa: E402
import motor.rules  # noqa: E402
import verificar_ventana_calibracion as ventana  # noqa: E402


DB = ROOT / 'data' / 'hands_db.jsonl'
SNAPSHOT = ROOT / 'data' / 'calibration_window.json'
INVENTORY = ROOT / 'DOCS' / 'B1_EXCEPCION_INVENTARIO.json'
PREFLOP_MATRICES = ROOT / 'data' / 'preflop_matrices.json'

BASE_COMMIT = '8594ed5'
BASE_SHA256 = '3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e'
BASE_BYTES = 2070355
BASE_LINES = 1344

SNAPSHOT_SHA256 = '7f2453f4ac9ee75907d0600fe0faa5acf23c62718051636739ed3c4f4661d6f1'
SELECTED_LINES_SHA256 = 'ea99bae67b61e213200b2ad2c0e0706121e7a7e7ef2a065941702a014f36e8ed'
SELECTED_COUNT = 877
EXCLUDED_COUNT = 23
RELIABLE_LIMIT = 900

PREFLOP_MATRICES_SHA256 = '075bae3aa9de8f6141c5db016a397a9b34d727ffbed4b6a5512d108c27f0e5c1'

DERIVATIVES = (
    'preflop_stats.json',
    'player_stats.json',
    'profiles.json',
    'profile_ranges.json',
    'postflop_ranges.json',
    'observations.json',
    'behavior.json',
)

LEGACY_BASE_COMMIT = '51a6fb9'
LEGACY_BASE_LINES = 1253
LEGACY_WINDOW = 877
LEGACY_OBSERVATIONS = 8742
LEGACY_HANDS_USED = 866


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    return _sha256_bytes(Path(path).read_bytes())


def _read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _git(*args):
    out = subprocess.run(
        ['git'] + list(args),
        cwd=str(ROOT),
        check=True,
        capture_output=True,
    )
    return out.stdout.decode('utf-8', errors='replace').strip()


def _git_blob_sha(data):
    header = b'blob ' + str(len(data)).encode('ascii') + b'\x00'
    return hashlib.sha1(header + data).hexdigest()


def _fail(message):
    raise AssertionError(message)


def check_base_sha256():
    got = _sha256_file(DB)
    if got != BASE_SHA256:
        _fail('esperado %s, obtenido %s' % (BASE_SHA256, got))
    return got


def check_base_bytes():
    got = DB.stat().st_size
    if got != BASE_BYTES:
        _fail('esperado %d, obtenido %d' % (BASE_BYTES, got))
    return '%d bytes' % got


def check_base_lines():
    raw = DB.read_bytes()
    physical = len(raw.splitlines())
    nonempty = sum(1 for line in raw.splitlines() if line.strip())
    if physical != BASE_LINES:
        _fail('lineas fisicas: esperado %d, obtenido %d' % (BASE_LINES, physical))
    if nonempty != BASE_LINES:
        _fail('lineas no vacias: esperado %d, obtenido %d' % (BASE_LINES, nonempty))
    return '%d lineas fisicas, %d no vacias' % (physical, nonempty)


def check_manifest():
    if learn.HANDS_DB_COMMIT != BASE_COMMIT:
        _fail('HANDS_DB_COMMIT: esperado %r, obtenido %r'
              % (BASE_COMMIT, learn.HANDS_DB_COMMIT))
    if learn.HANDS_DB_SHA256 != BASE_SHA256:
        _fail('HANDS_DB_SHA256: esperado %r, obtenido %r'
              % (BASE_SHA256, learn.HANDS_DB_SHA256))
    if learn.HANDS_DB_LINEAS != BASE_LINES:
        _fail('HANDS_DB_LINEAS: esperado %r, obtenido %r'
              % (BASE_LINES, learn.HANDS_DB_LINEAS))
    return 'commit %s, sha256 %s, lineas %d' % (
        learn.HANDS_DB_COMMIT, learn.HANDS_DB_SHA256, learn.HANDS_DB_LINEAS)


def check_commit_blob():
    kind = _git('cat-file', '-t', BASE_COMMIT)
    if kind != 'commit':
        _fail('%s no es un commit (git dice %r)' % (BASE_COMMIT, kind))
    disk = DB.read_bytes()
    blob = _git('rev-parse', '%s:data/hands_db.jsonl' % BASE_COMMIT)
    expected_blob = _git_blob_sha(disk)
    if blob != expected_blob:
        _fail('blob del commit %s = %s, blob del disco = %s'
              % (BASE_COMMIT, blob, expected_blob))
    last = _git('log', '-1', '--format=%H', '--', 'data/hands_db.jsonl')
    if not last.startswith(BASE_COMMIT):
        _fail('ultimo commit de la base = %s, esperado %s' % (last, BASE_COMMIT))
    return 'blob %s = disco; ultimo commit %s' % (blob[:12], last[:12])


def check_derivatives():
    expected = _read_json(SNAPSHOT)['derivatives']['canonical_sha256']
    if set(expected) != set(DERIVATIVES):
        _fail('el snapshot registra %r, se esperaban %r'
              % (sorted(expected), sorted(DERIVATIVES)))
    problems = []
    for name in DERIVATIVES:
        path = ROOT / 'data' / name
        if not path.exists():
            problems.append('%s: no existe' % name)
            continue
        got = _sha256_file(path)
        if got != expected[name]:
            problems.append('%s: esperado %s, obtenido %s'
                            % (name, expected[name], got))
    if problems:
        _fail('; '.join(problems))
    return '7/7 hashes coinciden con el snapshot'


def check_snapshot_file():
    got = _sha256_file(SNAPSHOT)
    if got != SNAPSHOT_SHA256:
        _fail('esperado %s, obtenido %s' % (SNAPSHOT_SHA256, got))
    return got


def check_calibration_window():
    snapshot, got, problems = ventana.verify(SNAPSHOT, DB)
    if problems:
        _fail('; '.join(problems))
    if got['selected_count'] != SELECTED_COUNT:
        _fail('ventana seleccionada: esperado %d, obtenido %d'
              % (SELECTED_COUNT, got['selected_count']))
    if len(got['excluded']) != EXCLUDED_COUNT:
        _fail('exclusiones CM-004: esperadas %d, obtenidas %d'
              % (EXCLUDED_COUNT, len(got['excluded'])))
    if got['selected_lines_sha256'] != SELECTED_LINES_SHA256:
        _fail('hash de lineas seleccionadas: esperado %s, obtenido %s'
              % (SELECTED_LINES_SHA256, got['selected_lines_sha256']))
    window = snapshot['window']
    if window.get('reliable_hands_limit') != RELIABLE_LIMIT:
        _fail('reliable_hands_limit: esperado %d, obtenido %r'
              % (RELIABLE_LIMIT, window.get('reliable_hands_limit')))
    return ('base %s, ventana %d, excluidas %d, hash %s'
            % (got['base_sha256'][:12], got['selected_count'],
               len(got['excluded']), got['selected_lines_sha256'][:12]))


def check_calibration_provisional():
    snapshot = _read_json(SNAPSHOT)
    if snapshot.get('status') != 'provisional':
        _fail('status: esperado provisional, obtenido %r' % snapshot.get('status'))
    provenance = snapshot.get('provenance_status', '')
    if not provenance.startswith('unverified'):
        _fail('provenance_status no empieza por unverified: %r' % provenance)
    derivatives_status = snapshot.get('derivatives', {}).get('status', '')
    if 'stale relative to current base' not in derivatives_status:
        _fail('derivatives.status no declara stale: %r' % derivatives_status)
    if 'not adopted' not in derivatives_status:
        _fail('derivatives.status no declara not adopted: %r' % derivatives_status)
    return 'status provisional; derivados stale/not adopted'


def check_derivative_legacy_metadata():
    preflop = _read_json(ROOT / 'data' / 'preflop_stats.json')
    behavior = _read_json(ROOT / 'data' / 'behavior.json')
    observations = _read_json(ROOT / 'data' / 'observations.json')
    profile_ranges = _read_json(ROOT / 'data' / 'profile_ranges.json')
    postflop_ranges = _read_json(ROOT / 'data' / 'postflop_ranges.json')

    checks = []
    checks.append(('preflop_stats.hands', preflop.get('hands'), LEGACY_WINDOW))
    checks.append(('behavior.hands', behavior.get('hands'), LEGACY_WINDOW))
    checks.append(('behavior.observaciones',
                   behavior.get('observaciones'), LEGACY_OBSERVATIONS))
    checks.append(('observations.len', len(observations), LEGACY_OBSERVATIONS))
    for label, obj in (('profile_ranges', profile_ranges),
                       ('postflop_ranges', postflop_ranges)):
        meta = obj.get('meta', {})
        checks.append(('%s.meta.hands_input' % label,
                       meta.get('hands_input'), LEGACY_WINDOW))
        checks.append(('%s.meta.hands_used' % label,
                       meta.get('hands_used'), LEGACY_HANDS_USED))
        checks.append(('%s.meta.code_commit' % label,
                       meta.get('code_commit'), '0fcceed'))
    for name, got, expected in checks:
        if got != expected:
            _fail('%s: esperado %r, obtenido %r' % (name, expected, got))

    inventory = _read_json(INVENTORY)
    source = inventory.get('adoption_1344', {}).get('derivatives_source', {})
    expected_source = {
        'base_commit': LEGACY_BASE_COMMIT,
        'base_lines': LEGACY_BASE_LINES,
        'window': LEGACY_WINDOW,
        'status': 'legacy_not_reanchored',
    }
    if source != expected_source:
        _fail('inventario adoption_1344.derivatives_source: esperado %r, obtenido %r'
              % (expected_source, source))

    snapshot = _read_json(SNAPSHOT)
    historical = snapshot.get('f72_metrics', {}).get('historical', {}).get('base')
    expected_historical = '%s / %d lines' % (LEGACY_BASE_COMMIT, LEGACY_BASE_LINES)
    if historical != expected_historical:
        _fail('f72_metrics.historical.base: esperado %r, obtenido %r'
              % (expected_historical, historical))
    return 'legado %s/%d, ventana %d; observaciones %d; hands_used %d' % (
        LEGACY_BASE_COMMIT, LEGACY_BASE_LINES, LEGACY_WINDOW,
        LEGACY_OBSERVATIONS, LEGACY_HANDS_USED)


def check_preflop_matrices():
    got = _sha256_file(PREFLOP_MATRICES)
    if got != PREFLOP_MATRICES_SHA256:
        _fail('esperado %s, obtenido %s' % (PREFLOP_MATRICES_SHA256, got))
    return got


def check_multiway():
    if motor.rules.MULTIWAY_SOPORTADO is not False:
        _fail('MULTIWAY_SOPORTADO debe ser False; es %r'
              % (motor.rules.MULTIWAY_SOPORTADO,))
    return 'MULTIWAY_SOPORTADO=False'


CHECKS = (
    ('base.sha256', check_base_sha256),
    ('base.bytes', check_base_bytes),
    ('base.lines', check_base_lines),
    ('manifest.learn', check_manifest),
    ('manifest.commit_blob', check_commit_blob),
    ('derivatives.hashes', check_derivatives),
    ('calibration.snapshot_sha256', check_snapshot_file),
    ('calibration.window', check_calibration_window),
    ('calibration.provisional', check_calibration_provisional),
    ('derivatives.legacy_metadata', check_derivative_legacy_metadata),
    ('preflop_matrices.sha256', check_preflop_matrices),
    ('rules.multiway', check_multiway),
)


def main():
    failures = 0
    print('VERIFICACION DE ADOPCION 1344')
    print('  base esperada: %s / %d lineas / %d bytes'
          % (BASE_SHA256, BASE_LINES, BASE_BYTES))
    print('')
    for name, check in CHECKS:
        try:
            detail = check()
        except Exception as exc:  # noqa: BLE001 - el verificador debe informar
            failures += 1
            print('FALLO  %-28s %s' % (name, exc))
        else:
            print('OK     %-28s %s' % (name, detail))
    print('')
    if failures:
        print('RESULTADO: FALLO (%d garantia(s) incumplida(s))' % failures)
        return 1
    print('RESULTADO: OK (todas las garantias de adopcion se cumplen)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
