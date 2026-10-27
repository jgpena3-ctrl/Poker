"""Abre una sesión aislada de prueba manual para el LiveRecorder.

No escribe ni lee como salida la base canónica. El manifiesto que genera deja
constancia de los IDs bajo prueba y del hash de la base al comenzar.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_ROOT = os.path.join(ROOT, 'pruebas', 'recorder')
CANONICAL = os.path.join(ROOT, 'data', 'hands_db.jsonl')


def _load_targets(path):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    targets = data.get('targets', [])
    if not isinstance(targets, list) or not all(isinstance(x, str) for x in targets):
        raise ValueError('"targets" debe ser una lista de IDs de texto')
    return targets


def _canonical_hands():
    out = {}
    with open(CANONICAL, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                h = json.loads(line)
            except json.JSONDecodeError:
                continue
            out[h.get('hand_id')] = h
    return out


def _detalle_target(hid, hands):
    h = hands.get(hid)
    if not h:
        return {'hand_id': hid, 'date': None, 'players': [], 'jarduan': False,
                'jarduan_cards': ''}
    players = [p.get('name') for p in (h.get('players') or [])]
    jarduan_cards = ''
    for p in (h.get('players') or []):
        if (p.get('name') or '').lower() == 'jarduan':
            jarduan_cards = p.get('cards') or ''
    return {
        'hand_id': hid,
        'date': h.get('date'),
        'players': players,
        'jarduan': any((p or '').lower() == 'jarduan'
                       for p in players),
        'jarduan_cards': jarduan_cards,
    }


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id', dest='ids', action='append', default=[],
                        help='ID histórico objetivo; se puede repetir')
    parser.add_argument('--no-launch', action='store_true',
                        help='solo crea y muestra la sesión')
    args = parser.parse_args()

    targets = args.ids or _load_targets(os.path.join(TEST_ROOT, 'objetivos.json'))
    if not targets:
        parser.error('indica al menos un --id o rellena pruebas/recorder/objetivos.json')

    targets = sorted(set(targets))

    hands = _canonical_hands()
    detalles = [_detalle_target(t, hands) for t in targets]
    print('Objetivos (%d):' % len(targets))
    for d in detalles:
        marca = '  <-- Jarduan' if d['jarduan'] else ''
        cartas = ('  cartas Jarduan: ' + d['jarduan_cards']) if d['jarduan_cards'] else ''
        print('  %-8s  %s  %s%s%s' % (d['hand_id'],
              (d['date'] or '')[:19],
              ', '.join(d['players']), marca, cartas))

    stamp = dt.datetime.now().strftime('%Y%m%dT%H%M%S')
    session = os.path.join(TEST_ROOT, 'sesiones', 'manual_' + stamp)
    os.makedirs(os.path.join(session, 'resultados'))
    os.makedirs(os.path.join(session, 'capturas'))
    output = os.path.join(session, 'resultados', 'hands_db.jsonl')
    manifest = {
        'created_at': dt.datetime.now().isoformat(),
        'mode': 'manual-recorder-test',
        'targets': targets,
        'target_details': detalles,
        'canonical_db': os.path.relpath(CANONICAL, ROOT),
        'canonical_sha256': _sha256(CANONICAL),
        'output': os.path.relpath(output, session),
        'capture_dir': 'capturas',
    }
    with open(os.path.join(session, 'sesion.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print('Sesión de prueba:', session)
    if args.no_launch:
        return
    env = os.environ.copy()
    env.update({
        'POKER_TEST_SESSION': session,
        'POKER_TEST_OUTPUT': output,
        'POKER_TEST_CAPTURE_DIR': os.path.join(session, 'capturas'),
        'POKER_TEST_TARGETS': ','.join(targets),
    })
    subprocess.run([sys.executable, os.path.join(ROOT, 'recorder',
                    'poker_recorder_gui.py')], cwd=ROOT, env=env, check=True)


if __name__ == '__main__':
    main()
