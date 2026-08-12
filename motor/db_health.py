"""db_health.py — salud y evolución de hands_db.jsonl (pegar7 §14.4).

Reporte único de ingesta y cobertura para medir el progreso mientras crece
la base: manos, jugadores, decisiones conocidas por calle, issues detectados
(boards rotos, duplicados), celdas preflop/postflop con muestra utilizable
(n ≥ umbral) y delta de manos nuevas desde el último snapshot.

```
python -m motor.db_health            # reporte completo (no persiste)
python -m motor.db_health --json     # + actualiza data/db_health.json
python -m motor.db_health --posts 5  # umbral de n para celdas postflop
```

La ingesta SÓLO reporta (nunca borra): los modelos ya descartan aguas abajo
lo que no sirve (regla TECNICO §6: "se marcan, no se borran").
"""
import json
import os
import time
from typing import Dict, List, Tuple

from .learn import HERO_NAMES, load_hands
from .observations import STREETS, extract_hands

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_DIR, 'data', 'hands_db.jsonl')
SNAPSHOT_PATH = os.path.join(REPO_DIR, 'data', 'db_health.json')

DEFAULT_MIN_N = 10


# ---------------------------------------------------------------------------
# Ingesta: issues
# ---------------------------------------------------------------------------

def _board_codes(hand: dict) -> List[List[str]]:
    out = []
    for st in STREETS:
        if st == 'preflop':
            continue
        b = (hand.get('streets', {}).get(st, {}) or {}).get('board') or []
        if b:
            out.append(list(b))
    return out


def validate_hands(hands) -> Dict[str, object]:
    """Detecta problemas de ingesta sin descartar nada.

    Retorna: {'n_hands': ..., 'issues': {tipo: n}, 'examples': {tipo: [...]},
    'positions': {pos: n}} — cada mano entra en la primera issue que la
    marca (para no contar doble).
    """
    issues = {'dup_board': 0, 'flop_corto': 0, 'hand_id_dup': 0,
              'amount_invalido': 0, 'pos_desconocida': 0,
              'carta_repetida': 0}
    examples: Dict[str, List] = {}
    seen_ids: Dict[str, int] = {}
    n_with_board = 0

    for h in hands:
        tag = None
        hid = h.get('hand_id') or '?'
        if hid != '?':
            if hid in seen_ids:
                tag = 'hand_id_dup'
            seen_ids[hid] = seen_ids.get(hid, 0) + 1
        if tag is None:
            boards = _board_codes(h)
            if boards:
                n_with_board += 1
            for b in boards:
                if len(set(b)) != len(b):
                    tag = 'dup_board'
                    break
        if tag is None:
            # carta de turn/river que ya estaba en el flop (board roto)
            acum = []
            for st in STREETS:
                if st == 'preflop':
                    continue
                b = (h.get('streets', {}).get(st, {}) or {}).get('board') or []
                if len(b) == 1 and any(c in acum for c in b):
                    tag = 'carta_repetida'
                    break
                if b:
                    acum = list(b)
        if tag is None:
            fb = (h.get('streets', {}).get('flop', {}) or {}).get('board') or []
            acts = h.get('streets', {}).get('flop', {}).get('actions') or []
            if fb and len(fb) < 3 and acts:
                tag = 'flop_corto'
        if tag is None:
            poss = {p.get('pos') for p in h.get('players', [])}
            for p in h.get('players', []):
                for k in ('stack',):
                    try:
                        float(p.get(k) if p.get(k) is not None else 0)
                    except (TypeError, ValueError):
                        tag = 'amount_invalido'
                        break
            for st in STREETS:
                if tag:
                    break
                for a in h.get('streets', {}).get(st, {}).get('actions', []):
                    if a.get('pos') not in poss:
                        tag = 'pos_desconocida'
                        break
        if tag:
            issues[tag] += 1
            examples.setdefault(tag, [])
            if len(examples[tag]) < 3:
                examples[tag].append(
                    {'hand_id': hid, **({'board': str(h.get('streets', {}).get(
                        'flop', {}).get('board'))} if tag in (
                            'dup_board', 'flop_corto') else {})})

    return {'n_hands': len(hands), 'n_hands_con_board': n_with_board,
            'issues': issues, 'examples': examples}


# ---------------------------------------------------------------------------
# Cobertura
# ---------------------------------------------------------------------------

def coverage(hands, min_n: int = DEFAULT_MIN_N) -> Dict[str, object]:
    """Cobertura de la DB para los dos modelos de rango."""
    obs = extract_hands(hands)
    out = {'hands': len(hands),
           'players': len({o.player for o in obs}),
           'cedulas': len(obs),
           'conocidas': sum(1 for o in obs if o.hand_known and o.cards)}
    by_street = {}
    for o in obs:
        d = by_street.setdefault(o.street, {'obs': 0, 'conocidas': 0})
        d['obs'] += 1
        if o.hand_known and o.cards:
            d['conocidas'] += 1
    out['by_street'] = by_street

    # --- preflop: celdas (perfil, spot) con muestra utilizable
    from .profile import Profiles
    from .learn import PreflopStats

    profs = Profiles.from_hands(hands)
    labels = {name: p.label for name, p in profs.profiles.items()}
    pstats = PreflopStats.from_hands(hands)
    denom: Dict[Tuple[str, str], int] = {}
    for pname, denoms in pstats.denoms.items():
        per = labels.get(pname)
        if not per:
            continue
        for spot, n in dict(denoms).items():
            if not spot:
                continue
            key = (per, spot)
            denom[key] = denom.get(key, 0) + n
    preflop = {}
    for (per, spot), n in sorted(denom.items(), key=lambda kv: -kv[1]):
        if n >= min_n:
            preflop[f'{per}|{spot}'] = n
    out['preflop_celdas_n' + str(min_n)] = preflop

    # --- postflop: celdas (street, facing, bucket) con n >= min_n
    from .postflop_ranges import PostflopRangeModel

    pm = PostflopRangeModel.from_hands(hands, labels=labels)
    cells = {}
    for (per, st, fac, b), n in pm.opp.items():
        if n >= min_n:
            cells[f'{per}|{st}|{fac}|b{b}'] = n
    out['postflop_celdas_n' + str(min_n)] = cells
    out['postflop_celdas_total'] = len(pm.opp)
    return out


# ---------------------------------------------------------------------------
# Snapshot / delta
# ---------------------------------------------------------------------------

def snapshot_delta(hands) -> Dict[str, object]:
    """Manos nuevas (y perdidas) frente al último snapshot guardado."""
    current = {h.get('hand_id') for h in hands if h.get('hand_id')}
    out = {'nuevas': 0, 'nuevo_por_jugador': {}, 'ts': time.strftime(
        '%Y-%m-%d %H:%M')}
    if not os.path.exists(SNAPSHOT_PATH):
        out['sin_snapshot'] = True
        return out
    try:
        with open(SNAPSHOT_PATH, encoding='utf-8') as f:
            prev = json.load(f)
    except (json.JSONDecodeError, OSError):
        out['sin_snapshot'] = True
        return out
    prev_ids = set(prev.get('hand_ids', []))
    nueva = current - prev_ids
    out['nuevas'] = len(nueva)
    per_player: Dict[str, int] = {}
    for h in hands:
        if h.get('hand_id') in nueva:
            for p in h.get('players', []):
                n = p.get('name')
                if n:
                    per_player[n] = per_player.get(n, 0) + 1
    out['nuevo_por_jugador'] = dict(sorted(
        per_player.items(), key=lambda kv: -kv[1])[:15])
    return out


def save_snapshot(hands):
    with open(SNAPSHOT_PATH, 'w', encoding='utf-8') as f:
        json.dump({'ts': time.strftime('%Y-%m-%d %H:%M'),
                   'hand_ids': sorted({h.get('hand_id') for h in hands
                                       if h.get('hand_id')})},
                  f, indent=1, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _fmt_pct(a, b):
    return f'{100 * a / b:.0f}%' if b else '—'


def main(argv=None):
    import sys

    args = list(argv if argv is not None else sys.argv[1:])
    write_json = '--json' in args
    min_n = DEFAULT_MIN_N
    if '--posts' in args:
        try:
            min_n = int(args[args.index('--posts') + 1])
        except (ValueError, IndexError):
            pass

    hands = load_hands()
    valid = validate_hands(hands)
    cov = coverage(hands, min_n=min_n)
    delta = snapshot_delta(hands)

    print(f'Manos: {valid["n_hands"]}  (con board: '
          f'{valid["n_hands_con_board"]}) · jugadores: {cov["players"]}')
    print(f'Decisiones: {cov["cedulas"]} · con mano conocida: '
          f'{cov["conocidas"]} ({_fmt_pct(cov["conocidas"], cov["cedulas"])})')

    print('\n-- Ingesta (issues; se marcan, no se borran) --')
    issues = valid['issues']
    if not any(issues.values()):
        print('  sin issues detectados')
    for k, v in issues.items():
        if v:
            print(f'  {k}: {v}')
            for ex in valid['examples'].get(k, [])[:2]:
                print(f'      ej. {ex.get("hand_id")} {ex.get("board", "")}')

    print('\n-- Evolución vs snapshot --')
    if delta.get('sin_snapshot'):
        print('  (sin snapshot previo; --json lo crea)')
    else:
        print(f'  manos nuevas: {delta["nuevas"]}')
        for nom, n in delta['nuevo_por_jugador'].items():
            print(f'      {nom}: {n}')

    print(f'\n-- Cobertura preflop (perfil|spot, n>={min_n}) --')
    pf = cov['preflop_celdas_n' + str(min_n)]
    if not pf:
        print('  (ninguna celda con muestra suficiente)')
    for k, n in pf.items():
        print(f'  {k:38} n={n}')

    print(f'\n-- Cobertura postflop (perfil|street|facing|bucket, n>={min_n}) --')
    pp = cov['postflop_celdas_n' + str(min_n)]
    print(f'  celdas con muestra: {len(pp)} de '
          f'{cov["postflop_celdas_total"]} totales')
    for k, n in pp.items():
        print(f'  {k:44} n={n}')

    if write_json:
        save_snapshot(hands)
        payload = {'ts': delta['ts'], 'min_n': min_n, 'valid': valid,
                   'coverage': cov, 'delta': delta,
                   'hand_ids': sorted({h.get('hand_id') for h in hands
                                       if h.get('hand_id')})}
        path = args[args.index('--out') + 1] if '--out' in args \
            else SNAPSHOT_PATH
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=1, ensure_ascii=False)
        print(f'\n-> {path}')


if __name__ == '__main__':
    main()