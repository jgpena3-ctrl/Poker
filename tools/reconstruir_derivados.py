# -*- coding: utf-8 -*-
"""Reconstruccion de derivados con backup y comparacion (revision_2).

Procedimiento:
  1. Congelar  : comprueba que el arbol esta limpio y anota el commit.
  2. Backup    : copia data/ a data/_snapshot_pre_rebuild_<commit>/ con hashes.
  3. Baseline  : registra metricas de los derivados actuales.
  4. Regenerar : ejecuta los CLIs oficiales del proyecto.
  5. Comparar  : diff de metricas antes/despues.

Uso:
  python tools/reconstruir_derivados.py backup
  python tools/reconstruir_derivados.py regen
  python tools/reconstruir_derivados.py comparar
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
sys.path.insert(0, ROOT)

DERIVADOS = ['profile_ranges.json', 'postflop_ranges.json',
             'preflop_stats.json', 'player_stats.json', 'profiles.json',
             'behavior.json', 'observations.json']


def _sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()[:16]


def _head():
    return subprocess.check_output(
        ['git', 'rev-parse', '--short', 'HEAD'],
        cwd=ROOT).decode().strip()


def _status():
    out = subprocess.check_output(['git', 'status', '--porcelain'],
                                  cwd=ROOT).decode().strip()
    return out


# ---------------------------------------------------------------- 1 y 2
def cmd_backup():
    dirty = _status()
    print('commit  : %s' % _head())
    print('arbol   : %s' % ('LIMPIO' if not dirty else 'CON CAMBIOS'))
    if dirty:
        print('  ' + dirty.replace('\n', '\n  '))

    snap = os.path.join(DATA, '_snapshot_pre_rebuild_%s' % _head())
    os.makedirs(snap, exist_ok=True)
    hashes = {}
    for name in DERIVADOS:
        src = os.path.join(DATA, name)
        if not os.path.exists(src):
            print('  %-26s (no existe)' % name)
            continue
        dst = os.path.join(snap, name)
        with open(src, 'rb') as a, open(dst, 'wb') as b:
            b.write(a.read())
        hashes[name] = {'sha256_16': _sha(src),
                        'bytes': os.path.getsize(src)}
        print('  %-26s %10d bytes  sha=%s'
              % (name, hashes[name]['bytes'], hashes[name]['sha256_16']))
    with open(os.path.join(snap, '_hashes.json'), 'w', encoding='utf-8') as f:
        json.dump({'commit': _head(), 'dirty': bool(dirty),
                   'files': hashes}, f, indent=2)
    print('\nbackup -> %s' % snap)
    print('verifica antes de continuar: comparar los hashes con _hashes.json')
    return 0


# ---------------------------------------------------------------- 3
def _metricas():
    from motor.learn import load_hands, preflop_events
    import collections
    hands = load_hands(reliable_only=True)
    cats = collections.Counter()
    denoms = collections.Counter()
    jugadores = set()
    known = 0
    eventos = 0
    for h in hands:
        for ev in preflop_events(h):
            eventos += 1
            cats[ev.category] += 1
            denoms[ev.denom] += 1
            jugadores.add(ev.player)
            if ev.hand_known:
                known += 1

    def _json_stats(name):
        p = os.path.join(DATA, name)
        if not os.path.exists(p):
            return None
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        return d

    pr = _json_stats('profile_ranges.json')
    po = _json_stats('postflop_ranges.json')

    out = {
        'manos': len(hands),
        'eventos': eventos,
        'jugadores': len(jugadores),
        'eventos_con_cartas': known,
        'categorias': dict(sorted(cats.items())),
        'denominadores': dict(sorted(denoms.items())),
    }
    if pr:
        out['profile_ranges'] = {
            'opp_keys': len(pr.get('opp', {})),
            'cnt_keys': len(pr.get('cnt', {})),
            'jugadores': len(pr.get('perfil', {})),
            'omega_keys': len(pr.get('omega', {})),
            'bytes': os.path.getsize(os.path.join(DATA,
                                                  'profile_ranges.json')),
        }
    if po:
        out['postflop_ranges'] = {
            'opp_keys': len(po.get('opp', {})),
            'cnt_keys': len(po.get('cnt', {})),
            'bytes': os.path.getsize(os.path.join(DATA,
                                                  'postflop_ranges.json')),
        }
    return out


def cmd_baseline():
    m = _metricas()
    snap = os.path.join(DATA, '_snapshot_pre_rebuild_%s' % _head())
    out = os.path.join(snap, 'baseline_metricas.json')
    os.makedirs(snap, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(m, f, indent=2, ensure_ascii=False)
    print(json.dumps(m, indent=2, ensure_ascii=False))
    print('\n-> %s' % out)
    return 0


# ---------------------------------------------------------------- 4
def cmd_regen():
    pasos = [
        ('learn', [sys.executable, '-m', 'motor.learn', '--json']),
        ('stats', [sys.executable, '-m', 'motor.stats', '--json']),
        ('profile', [sys.executable, '-m', 'motor.profile', '--json']),
        ('player_ranges', [sys.executable, '-m', 'motor.player_ranges',
                           '--json']),
        ('postflop_ranges', [sys.executable, '-m', 'motor.postflop_ranges',
                             '--json']),
        ('observations', [sys.executable, '-m', 'motor.observations',
                          '--json']),
        ('behavior', [sys.executable, '-m', 'motor.behavior', '--json']),
    ]
    for nombre, cmd in pasos:
        print('--- %s ---' % nombre)
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        tail = (r.stdout or '').strip().split('\n')[-3:]
        for line in tail:
            print('   ' + line)
        if r.returncode != 0:
            print('   ERROR rc=%d' % r.returncode)
            print('   ' + (r.stderr or '')[-500:])
            return 1
    print('\nregeneracion completa')
    return 0


# ---------------------------------------------------------------- 5
def cmd_comparar():
    snap = os.path.join(DATA, '_snapshot_pre_rebuild_%s' % _head())
    with open(os.path.join(snap, 'baseline_metricas.json'),
              encoding='utf-8') as f:
        antes = json.load(f)
    despues = _metricas()

    print('=' * 72)
    print('COMPARACION DE DERIVADOS  (%s)' % _head())
    print('=' * 72)
    print('')
    print('%-28s %12s %12s %10s' % ('metrica', 'antes', 'despues', 'delta'))
    print('-' * 72)
    for k in ('manos', 'eventos', 'jugadores', 'eventos_con_cartas'):
        a, b = antes.get(k), despues.get(k)
        print('%-28s %12s %12s %10s' % (k, a, b, b - a))
    print('')

    for grupo in ('denominadores', 'categorias'):
        a = antes.get(grupo, {})
        b = despues.get(grupo, {})
        claves = sorted(set(a) | set(b))
        print('%s:' % grupo)
        for c in claves:
            x, y = a.get(c, 0), b.get(c, 0)
            marca = '' if x == y else '   <-- cambia'
            print('  %-18s %8s %8s %8s%s' % (c, x, y, y - x, marca))
        print('')

    for k in ('profile_ranges', 'postflop_ranges'):
        a = antes.get(k)
        b = despues.get(k)
        if not a or not b:
            continue
        print('%s:' % k)
        for sub in a:
            x, y = a.get(sub), b.get(sub)
            if isinstance(x, int) and isinstance(y, int):
                print('  %-18s %8s %8s %8s' % (sub, x, y, y - x))
        print('')

    with open(os.path.join(snap, 'metricas_post_rebuild.json'), 'w',
              encoding='utf-8') as f:
        json.dump(despues, f, indent=2, ensure_ascii=False)
    print('metricas post -> %s' % os.path.join(snap,
                                               'metricas_post_rebuild.json'))
    return 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    fn = {'backup': cmd_backup, 'baseline': cmd_baseline,
          'regen': cmd_regen, 'comparar': cmd_comparar}.get(cmd)
    if not fn:
        print(__doc__)
        return 1
    return fn()


if __name__ == '__main__':
    sys.exit(main())