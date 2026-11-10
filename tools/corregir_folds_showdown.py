# -*- coding: utf-8 -*-
"""Elimina folds inferidos que se marcaron en showdowns.

Regla (la que el usuario pidio): se retira un fold inferido solo si el jugador
ya habia igualado la apuesta de esa calle, es decir, no tenia ninguna apuesta
por completar. Si su aporte era menor que el maximo de la calle, el fold es
real y se conserva.

Se recalcula `fold_win`, aportes, rake y bote desde las acciones restantes, y
se actualiza `winner`/`showdown` cuando la mano deja de ser victoria por fold.

Uso:
    python tools/corregir_folds_showdown.py            # dry-run
    python tools/corregir_folds_showdown.py --apply    # escribe con backup
    python tools/corregir_folds_showdown.py --restore  # vuelve al backup
"""
import argparse
import copy
import hashlib
import io
import json
import os
import shutil
import tempfile
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, 'data', 'hands_db.jsonl')
BACKUP_DIR = os.path.join(ROOT, 'data', '_backup_corregir_folds_showdown')
BACKUP_PATH = os.path.join(BACKUP_DIR, 'hands_db.jsonl')
STREETS = ('preflop', 'flop', 'turn', 'river')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def leer_lineas(path):
    with io.open(path, encoding='utf-8') as f:
        return f.readlines()


def redondear_bote(value):
    return float(Decimal(str(max(0.0, float(value)))).quantize(
        Decimal('0.1'), rounding=ROUND_HALF_UP))


def redondear2(value):
    return float(Decimal(str(float(value))).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP))


def numero_mano(hand):
    hid = str(hand.get('hand_id') or '')
    try:
        return int(hid.split('_')[1])
    except (IndexError, ValueError):
        return None


def rake_params(hand):
    audit = hand.get('recorder_audit') or {}
    if (str(hand.get('date') or '').startswith('2026-11-04')
            and numero_mano(hand) is not None
            and 1328 <= numero_mano(hand) <= 1341):
        return 0.05, 2.5
    return 0.03, 0.3


def aportes_calle(hand, street):
    aportes = {}
    for action in ((hand.get('streets') or {}).get(street) or {}).get(
            'actions') or []:
        pos = action.get('pos')
        if not pos or action.get('action') not in ('p', 'b', 'c', 'r'):
            continue
        try:
            amount = max(0.0, float(action.get('amount') or 0.0))
        except (TypeError, ValueError):
            continue
        aportes[pos] = max(aportes.get(pos, 0.0), amount)
    return aportes


def matched_y_uncalled(aportes):
    values = sorted(aportes.values(), reverse=True)
    gross = sum(values)
    uncalled = (max(0.0, values[0] - (values[1] if len(values) > 1 else 0.0))
                if values else 0.0)
    return gross - uncalled, uncalled, gross


def calcular_bote(hand, fold_win):
    board = hand.get('comunitarias') or {}
    has_postflop = any(board.get(s) for s in ('flop', 'turn', 'river'))
    gross_total = matched_total = rake_basis = 0.0
    for street in STREETS:
        matched, _uncalled, gross = matched_y_uncalled(
            aportes_calle(hand, street))
        matched_total += matched
        gross_total += gross
        completada = False
        if street == 'preflop':
            completada = has_postflop
        elif street == 'flop':
            completada = bool(board.get('turn') or board.get('river'))
        elif street == 'turn':
            completada = bool(board.get('river'))
        elif street == 'river':
            completada = True
        if completada and (street != 'preflop' or has_postflop):
            rake_basis += matched
    audit = hand.get('recorder_audit') or {}
    big_blind = float(audit.get('big_blind') or 1.0)
    rate, cap_bb = rake_params(hand)
    rake = min(rate * rake_basis, cap_bb * big_blind)
    pot_inflated = (gross_total if fold_win else matched_total) - rake
    pot_no_inflado = matched_total - rake
    return {
        'gross_contributions': redondear2(gross_total),
        'matched_contributions': redondear2(matched_total),
        'uncalled': redondear2(max(0.0, gross_total - matched_total)),
        'rake_basis': redondear2(rake_basis),
        'rake': redondear2(rake),
        'pot_calculated': redondear_bote(pot_inflated),
        'pot_calculated_noninflated': redondear_bote(pot_no_inflado),
        'pot_live_calculated': redondear_bote(gross_total - rake),
        'rake_cap': redondear2(cap_bb * big_blind),
    }


def folds_removibles(hand):
    """Devuelve la lista de (street, pos) de folds inferidos removibles."""
    out = []
    for street in STREETS:
        aportes = aportes_calle(hand, street)
        maximo = max(aportes.values()) if aportes else 0.0
        for action in ((hand.get('streets') or {}).get(street) or {}).get(
                'actions') or []:
            if (action.get('action') == 'f'
                    and action.get('inferred') is True
                    and action.get('pos')):
                pos = action.get('pos')
                aporte = aportes.get(pos, 0.0)
                # Removible solo si el jugador ya habia igualado la apuesta
                # (no tenia ninguna apuesta por completar).
                if maximo > 0.05 and aporte + 0.05 >= maximo:
                    out.append((street, pos))
    return out


def corregir_mano(hand):
    audit = hand.get('recorder_audit')
    if not isinstance(audit, dict):
        return None
    if not audit.get('fold_win'):
        return None

    removibles = folds_removibles(hand)
    if not removibles:
        return None

    original = copy.deepcopy(hand)
    # Quitar los folds removibles.
    conjunto = set(removibles)
    for street, _ in removibles:
        data = (hand.get('streets') or {}).get(street) or {}
        data['actions'] = [
            a for a in (data.get('actions') or [])
            if not (a.get('action') == 'f' and a.get('inferred') is True
                    and (street, a.get('pos')) in conjunto)]
        (hand.get('streets') or {})[street] = data

    # Recalcular fold_win: si quedan >=2 jugadores sin fold, es showdown.
    folded = set()
    for s in (hand.get('streets') or {}).values():
        for a in (s.get('actions') or []):
            if a.get('action') == 'f' and a.get('pos'):
                folded.add(a.get('pos'))
    players = hand.get('players') or []
    non_folded = [p for p in players
                  if p.get('active') and p.get('pos')
                  and p.get('pos') not in folded
                  and p.get('_id') not in (hand.get('allin') or [])]
    allin_in = [p for p in players
                if p.get('active') and p.get('pos')
                and p.get('_id') in (hand.get('allin') or [])
                and p.get('pos') not in folded]
    fold_win = (len(non_folded) + len(allin_in)) <= 1

    breakdown = calcular_bote(hand, fold_win=fold_win)
    audit.update(breakdown)
    audit['fold_win'] = fold_win
    rate, cap_bb = rake_params(hand)
    audit['rake_cap'] = redondear2(cap_bb * float(audit.get('big_blind') or 1.0))

    pot_read = audit.get('pot_read')
    if isinstance(pot_read, (int, float)):
        tol = float(audit.get('ambiguity_tolerance') or 0.2)
        calc = breakdown['pot_calculated']
        noninfl = breakdown['pot_calculated_noninflated']
        if fold_win and abs(pot_read - noninfl) <= tol \
                and abs(pot_read - calc) > 0.005:
            audit['pot_resolution'] = 'read_noninflated_to_inflated'
        elif abs(pot_read - calc) <= tol:
            audit['pot_resolution'] = 'read_confirms_calculated'
            audit['ambiguities'] = [
                a for a in (audit.get('ambiguities') or [])
                if not (isinstance(a, dict)
                        and a.get('code') in ('pot_read_vs_calculated',
                                              'pot_read_vs_contributions'))]
        else:
            audit['pot_resolution'] = 'ambiguous_read_mismatch'
    hand['final_pot'] = breakdown['pot_calculated']

    if fold_win and (len(non_folded) + len(allin_in)) == 1:
        survivor = (non_folded + allin_in)[0]
        hand['winner'] = [survivor.get('_id')]
        hand['showdown'] = {}
    else:
        # Showdown: conservar ganador manual si lo habia.
        if not isinstance(hand.get('winner'), list):
            hand['winner'] = []
        if isinstance(hand.get('winner'), list) and len(hand['winner']) == 1:
            pid = hand['winner'][0]
            pobj = next((p for p in players if p.get('_id') == pid), None)
            if pobj:
                hand['showdown'] = {
                    'winner1': '%s (%s)' % (pobj.get('pos'),
                                             pobj.get('name'))}

    # Rebuild ambiguous_actions from remaining flagged actions.
    ambiguous_actions = [
        {'street': street,
         'pos': action.get('pos'),
         'action': action.get('action'),
         'amount': action.get('amount'),
         'inferred': bool(action.get('inferred'))}
        for street, data in (hand.get('streets') or {}).items()
        for action in (data or {}).get('actions') or []
        if action.get('ambiguous') and action.get('action') != 'f']
    audit['ambiguous_actions'] = ambiguous_actions
    audit['ambiguous'] = bool(audit.get('ambiguities') or ambiguous_actions)

    detalle = {
        'hand_id': hand.get('hand_id'),
        'removidos': removibles,
        'fold_win': (True, fold_win),
        'pot': (audit.get('pot_calculated'), breakdown['pot_calculated']),
        'award_display_ignored': bool(audit.get('award_display_ignored')),
    }
    if hand != original:
        return detalle
    return None


def construir_plan(db_path=DB_PATH):
    lineas = leer_lineas(db_path)
    nuevas = [None] * len(lineas)
    cambios = []
    for i, linea in enumerate(lineas):
        if not linea.strip():
            continue
        hand = json.loads(linea)
        if not isinstance(hand.get('recorder_audit'), dict):
            continue
        original = copy.deepcopy(hand)
        detalle = corregir_mano(hand)
        if detalle is not None and hand != original:
            nuevas[i] = hand
            cambios.append(detalle)
    return lineas, nuevas, cambios


def escribir_atomico(lineas, destino):
    d = os.path.dirname(destino)
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.hands_db_', suffix='.tmp')
    os.close(fd)
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        for linea in lineas:
            f.write(linea if linea.endswith('\n') else linea + '\n')
    with io.open(tmp, encoding='utf-8') as f:
        for n, linea in enumerate(f, 1):
            if linea.strip():
                try:
                    json.loads(linea)
                except ValueError as exc:
                    os.remove(tmp)
                    raise ValueError('temporal invalido en linea %d: %s'
                                     % (n, exc))
    return tmp


def aplicar(lineas, nuevas):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if os.path.exists(BACKUP_PATH):
        print('backup    : %s (existente, se conserva)'
              % os.path.relpath(BACKUP_PATH, ROOT))
        print('sha256    : %s' % sha256(BACKUP_PATH))
    else:
        shutil.copy2(DB_PATH, BACKUP_PATH)
        h_orig, h_back = sha256(DB_PATH), sha256(BACKUP_PATH)
        print('backup    : %s' % os.path.relpath(BACKUP_PATH, ROOT))
        print('sha256    : %s' % h_orig)
        print('verificado: %s' % ('OK, coinciden' if h_orig == h_back
                                 else 'FALLO, NO coinciden'))
        if h_orig != h_back:
            raise RuntimeError('el backup no coincide con el original; '
                               'abortando')

    salida = [linea if nuevas[i] is None
              else json.dumps(nuevas[i], ensure_ascii=False) + '\n'
              for i, linea in enumerate(lineas)]

    tmp = escribir_atomico(salida, DB_PATH)
    try:
        os.replace(tmp, DB_PATH)
    except Exception:
        os.remove(tmp)
        shutil.copy2(BACKUP_PATH, DB_PATH)
        raise
    print()
    print('aplicado. nuevo sha256: %s' % sha256(DB_PATH))
    return True


def imprimir_plan(cambios):
    print('=' * 78)
    print('FOLDS INFERIDOS EN SHOWDOWNS')
    print('=' * 78)
    print('manos que cambian: %d' % len(cambios))
    print()
    for d in cambios:
        warn = '  [tiene award_display_ignored: revisar]' \
            if d['award_display_ignored'] else ''
        print('  %-7s removidos=%s  fold_win %s -> %s  bote %s -> %s%s'
              % (d['hand_id'], d['removidos'], d['fold_win'][0],
                 d['fold_win'][1], d['pot'][0], d['pot'][1], warn))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true',
                    help='escribe los cambios (sin esto solo muestra el plan)')
    ap.add_argument('--restore', action='store_true',
                    help='restaura hands_db.jsonl desde el backup')
    args = ap.parse_args(argv)

    if args.restore:
        if not os.path.exists(BACKUP_PATH):
            raise SystemExit('no existe el backup: %s' % BACKUP_PATH)
        shutil.copy2(BACKUP_PATH, DB_PATH)
        print('restaurado %s' % DB_PATH)
        print('sha256: %s' % sha256(DB_PATH))
        return 0

    lineas, nuevas, cambios = construir_plan()
    imprimir_plan(cambios)
    print()
    if not cambios:
        print('nada que cambiar: no hay folds inferidos sin apuesta por '
              'completar.')
        return 0
    if not args.apply:
        print('dry-run: no se ha escrito nada. Usa --apply para aplicar.')
        return 0
    return 0 if aplicar(lineas, nuevas) else 1


if __name__ == '__main__':
    raise SystemExit(main())
