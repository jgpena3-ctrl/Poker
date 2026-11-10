# -*- coding: utf-8 -*-
"""Repone el bote inflado en victorias por fold.

El recorder restaba la devolucion de la apuesta no igualada tambien del bote
final, dejando el bote en su version no inflada. En el formato historico una
victoria por fold conserva el excedente no igualado, de modo que la ultima
apuesta del ganador debe seguir dentro del bote.

Este script solo toca las manos donde `final_pot` coincide con el bote no
inflado (`matched - rake`) y ademas existe un excedente no igualado. Las manos
corregidas a mano que usan otra referencia (p. ej. el bote leido en pantalla)
se dejan intactas.

Uso:
    python tools/corregir_bote_inflado_fold.py            # dry-run
    python tools/corregir_bote_inflado_fold.py --apply    # escribe con backup
    python tools/corregir_bote_inflado_fold.py --restore  # vuelve al backup
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
BACKUP_DIR = os.path.join(ROOT, 'data', '_backup_corregir_bote_inflado_fold')
BACKUP_PATH = os.path.join(BACKUP_DIR, 'hands_db.jsonl')
STREETS = ('preflop', 'flop', 'turn', 'river')
TOL = 0.051


def _round1(value):
    return float(Decimal(str(value)).quantize(Decimal('0.1'),
                                              rounding=ROUND_HALF_UP))


def _round2(value):
    return float(Decimal(str(value)).quantize(Decimal('0.01'),
                                              rounding=ROUND_HALF_UP))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def leer_lineas(path):
    with io.open(path, encoding='utf-8') as f:
        return f.readlines()


def _street_contributions(actions):
    contributions = {}
    for action in actions or []:
        if action.get('action') not in ('p', 'b', 'c', 'r'):
            continue
        pos = action.get('pos')
        if not pos:
            continue
        try:
            amount = max(0.0, float(action.get('amount') or 0.0))
        except (TypeError, ValueError):
            continue
        contributions[pos] = max(contributions.get(pos, 0.0), amount)
    return contributions


def _matched_and_uncalled(contributions):
    values = sorted(contributions.values(), reverse=True)
    gross = sum(values)
    uncalled = (max(0.0, values[0] - (values[1] if len(values) > 1 else 0.0))
                if values else 0.0)
    return gross - uncalled, uncalled, gross


def _totales(hand):
    matched_total = gross_total = 0.0
    for street in STREETS:
        actions = (((hand.get('streets') or {}).get(street) or {})
                   .get('actions') or [])
        matched, _uncalled, gross = _matched_and_uncalled(
            _street_contributions(actions))
        matched_total += matched
        gross_total += gross
    return matched_total, gross_total


def _resolucion(pot_read, calculado, no_inflado, fold_win, tol):
    if pot_read is None:
        return 'calculated'
    if (fold_win and abs(pot_read - no_inflado) <= tol
            and abs(pot_read - calculado) > 0.005):
        return 'read_noninflated_to_inflated'
    if abs(pot_read - calculado) <= tol:
        return 'read_confirms_calculated'
    return 'ambiguous_read_mismatch'


def corregir_hand(hand):
    """Devuelve el detalle del cambio o None si la mano no aplica."""
    audit = hand.get('recorder_audit')
    if not isinstance(audit, dict) or not audit.get('fold_win'):
        return None
    if 'gross_contributions' not in audit or 'matched_contributions' not in audit:
        return None
    final_pot = hand.get('final_pot')
    if not isinstance(final_pot, (int, float)):
        return None

    matched, gross = _totales(hand)
    rake = float(audit.get('rake') or 0.0)
    calculado = _round1(gross - rake)
    no_inflado = _round1(matched - rake)
    if abs(final_pot - no_inflado) > TOL:
        return None
    if abs(calculado - no_inflado) <= TOL:
        return None

    pot_read = audit.get('pot_read')
    if isinstance(pot_read, (int, float)):
        pot_read = _round1(pot_read)
    tol = float(audit.get('ambiguity_tolerance') or 0.2)
    resolucion = _resolucion(pot_read, calculado, no_inflado, True, tol)
    if resolucion == 'ambiguous_read_mismatch':
        # No se fuerza una mano cuyo bote leido no encaja: requiere revision.
        return {'revisar': True, 'hand_id': hand.get('hand_id'),
                'final_pot': final_pot, 'calculado': calculado,
                'no_inflado': no_inflado, 'pot_read': pot_read}

    anterior = final_pot
    audit['gross_contributions'] = _round2(gross)
    audit['matched_contributions'] = _round2(matched)
    audit['uncalled'] = _round2(max(0.0, gross - matched))
    audit['pot_calculated'] = calculado
    audit['pot_calculated_noninflated'] = no_inflado
    audit['pot_resolution'] = resolucion
    hand['final_pot'] = calculado
    audit['pot_inflation_correction'] = {
        'reason': 'la devolucion de la apuesta no igualada vaciaba el bote '
                  'final; en victoria por fold se conserva el excedente',
        'previous_final_pot': anterior,
        'final_pot': calculado,
        'uncalled_restored': _round2(max(0.0, gross - matched)),
    }
    return {'hand_id': hand.get('hand_id'), 'antes': anterior,
            'despues': calculado, 'uncalled': _round2(gross - matched),
            'resolucion': resolucion}


def construir_plan(db_path=DB_PATH):
    lineas = leer_lineas(db_path)
    nuevas = [None] * len(lineas)
    cambios = []
    revisar = []
    for i, linea in enumerate(lineas):
        if not linea.strip():
            continue
        hand = json.loads(linea)
        original = copy.deepcopy(hand)
        detalle = corregir_hand(hand)
        if not detalle:
            continue
        if detalle.get('revisar'):
            revisar.append(detalle)
            continue
        if hand != original:
            nuevas[i] = hand
            cambios.append(detalle)
    return lineas, nuevas, cambios, revisar


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

    lineas, nuevas, cambios, revisar = construir_plan()
    print('=' * 78)
    print('REPOSICION DEL BOTE INFLADO EN VICTORIAS POR FOLD')
    print('=' * 78)
    print('manos que cambian: %d' % len(cambios))
    for c in cambios:
        print('  %-8s %6.1f -> %6.1f  (+%.1f no igualado, %s)'
              % (c['hand_id'], c['antes'], c['despues'], c['uncalled'],
                 c['resolucion']))
    if revisar:
        print()
        print('manos que requieren revision manual: %d' % len(revisar))
        for c in revisar:
            print('  %-8s final=%s calc=%s no_inflado=%s leido=%s'
                  % (c['hand_id'], c['final_pot'], c['calculado'],
                     c['no_inflado'], c['pot_read']))
    print()
    if not cambios:
        print('nada que cambiar: los botes ya estan inflados.')
        return 0
    if not args.apply:
        print('dry-run: no se ha escrito nada. Usa --apply para aplicar.')
        return 0
    return 0 if aplicar(lineas, nuevas) else 1


if __name__ == '__main__':
    raise SystemExit(main())
