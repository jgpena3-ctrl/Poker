# -*- coding: utf-8 -*-
"""Corrige los resultados incoherentes de la seccion del 4/11.

La revision de la base detecto seis manos del 4/11 con el resultado mal
cerrado y una con una posicion que nunca hablo:

- H_1330: MP foldeo preflop (el frame final lo muestra inactivo) pero el fold
  no quedo registrado; se inserta en orden, entre UTG y CO, con `inferred`.
- H_1337: la mano llego al showdown (se retiraron los folds del river y el
  ganador es un reparto BTN/BB), pero seguia marcada `fold_win: true` y sin
  casilla `showdown`. Ademas el SB quedo como `r 1.0` cuando igualaba la
  apuesta viva de 1.0: es un call.
- H_1342: showdown con ganador BB; la casilla `showdown` estaba vacia y los
  aportes del audit eran los de antes de la ultima edicion (gross 5.0 y
  uncalled 1.0; las acciones suman 4.0 y 0.0).
- H_1344, H_1355, H_1361: showdowns con un unico ganador y la casilla
  `showdown` vacia.
- H_1336, H_1343, H_1345, H_1348, H_1351, H_1354, H_1356, H_1366: las
  acciones muestran dos jugadores que nunca foldean (showdown), pero el audit
  seguia marcando `fold_win: true`, sin casilla `showdown` y con aportes de
  antes de la ultima edicion. Se reclasifican y se recalculan aportes, rake,
  bote y notas desde las acciones.

Los valores de `showdown` de las seis primeras manos se escriben literalmente
(el pid del ganador no se puede resolver contra `players` porque la base no
guarda `_id`; la correspondencia sale del indice de capturas). Para las ocho
reclasificadas se resuelve el pid con `motor.multiway.posicion_de_id` y se
toma el nombre del jugador de esa posicion, que es unico en la mesa.

Uso:
    python tools/corregir_resultados_20261104.py            # dry-run
    python tools/corregir_resultados_20261104.py --apply    # escribe con backup
    python tools/corregir_resultados_20261104.py --restore  # vuelve al backup
"""
import argparse
import copy
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, 'data', 'hands_db.jsonl')
BACKUP_DIR = os.path.join(ROOT, 'data', '_backup_corregir_resultados_20261104')
BACKUP_PATH = os.path.join(BACKUP_DIR, 'hands_db.jsonl')
STREETS = ('preflop', 'flop', 'turn', 'river')

sys.path.insert(0, ROOT)
from motor.multiway import posicion_de_id  # noqa: E402

# Manos con dos jugadores vivos al final: son showdowns, no victorias por fold.
SHOWDOWN_20261104 = (
    'H_1336', 'H_1343', 'H_1345', 'H_1348',
    'H_1351', 'H_1354', 'H_1356', 'H_1366',
)

# pid ganador -> texto de la casilla showdown. La base no guarda `_id` en
# `players`, asi que la correspondencia se toma del indice de capturas.
SHOWDOWN = {
    'H_1337': 'BTN (Nicorobacash)',   # p2, reparto con p4 (BB)
    'H_1342': 'BB (Jarduan)',         # hero, reparto con p5 (SB)
    'H_1344': 'BTN (Elperron)',       # p2
    'H_1355': 'CO (25289472)',        # p1
    'H_1361': 'BTN (Gutynho)',        # p5
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def leer_lineas(path):
    with io.open(path, encoding='utf-8') as f:
        return f.readlines()


def redondear2(value):
    return float(Decimal(str(float(value))).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP))


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


def redondear_bote(value):
    return float(Decimal(str(max(0.0, float(value)))).quantize(
        Decimal('0.1'), rounding=ROUND_HALF_UP))


def numero_mano(hand):
    try:
        return int(str(hand.get('hand_id') or '').split('_')[1])
    except (IndexError, ValueError):
        return None


def rake_params(hand):
    """Misma regla que tools/corregir_folds_showdown.py."""
    if (str(hand.get('date') or '').startswith('2026-11-04')
            and numero_mano(hand) is not None
            and 1328 <= numero_mano(hand) <= 1341):
        return 0.05, 2.5
    return 0.03, 0.3


def calcular_bote(hand, fold_win):
    """Recalcula aportes, rake y bote desde las acciones (regla del recorder)."""
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


def live_positions(hand):
    """Posiciones con acciones que no foldean; las que no actuaron no cuentan."""
    acts = defaultdict(list)
    for street in STREETS:
        for action in ((hand.get('streets') or {}).get(street) or {}).get(
                'actions') or []:
            if action.get('pos'):
                acts[action['pos']].append(action)
    folded = {pos for pos, acciones in acts.items()
              if any(a.get('action') == 'f' for a in acciones)}
    live = [pos for pos, acciones in acts.items()
            if pos not in folded
            and any(a.get('action') in ('p', 'b', 'c', 'r', 'x')
                    for a in acciones)]
    return sorted(live), folded


def showdown_text(hand):
    """`POS (Nombre)` del unico ganador, o None si no se puede resolver."""
    winner = hand.get('winner') or []
    if len(winner) != 1:
        return None
    pos = posicion_de_id(hand, winner[0])
    if not pos:
        return None
    nombres = sorted({p.get('name') for p in (hand.get('players') or [])
                      if p.get('pos') == pos and p.get('name')})
    if len(nombres) != 1:
        return None
    return '%s (%s)' % (pos, nombres[0])


def _accion_actual(hand, street, pos):
    for action in ((hand.get('streets') or {}).get(street) or {}).get(
            'actions') or []:
        if action.get('pos') == pos and action.get('action') in (
                'p', 'b', 'c', 'r', 'x', 'f'):
            return action
    return None


def limpiar_notas(hand, breakdown):
    """Actualiza o retira notas de bote/apuesta que quedaron obsoletas."""
    audit = hand.get('recorder_audit') or {}
    tol = float(audit.get('ambiguity_tolerance') or 0.2)
    if audit.get('pot_resolution') == 'read_incomplete_before_close':
        # Anotacion manual: la lectura se tomo antes de cerrar las apuestas.
        # No es una discrepancia ambigua y no debe revertirse al recalcular.
        return audit['pot_resolution']
    pot_read = audit.get('pot_read')
    calc = breakdown['pot_calculated']
    noninfl = breakdown['pot_calculated_noninflated']
    fold_win = bool(audit.get('fold_win'))
    if not isinstance(pot_read, (int, float)):
        resolucion = 'calculated'
    elif (fold_win and abs(float(pot_read) - noninfl) <= tol
          and abs(float(pot_read) - calc) > 0.005):
        resolucion = 'read_noninflated_to_inflated'
    elif abs(float(pot_read) - calc) <= tol:
        resolucion = 'read_confirms_calculated'
    else:
        resolucion = 'ambiguous_read_mismatch'
    audit['pot_resolution'] = resolucion

    nuevas = []
    for item in audit.get('ambiguities') or []:
        if not isinstance(item, dict):
            nuevas.append(item)
            continue
        code = item.get('code')
        if code in ('pot_read_vs_calculated',
                    'pot_read_vs_contributions'):
            if resolucion in ('read_confirms_calculated',
                              'read_noninflated_to_inflated'):
                continue
            if isinstance(pot_read, (int, float)):
                item['pot_read'] = round(float(pot_read), 1)
                item['difference'] = redondear2(abs(float(pot_read) - calc))
            if code == 'pot_read_vs_calculated':
                item['pot_calculated'] = calc
                item['pot_calculated_noninflated'] = noninfl
                item['fold_win'] = False
            else:
                item['contributions'] = breakdown['gross_contributions']
                item['completed_street_rake'] = breakdown['rake']
                item['pot_expected'] = calc
            nuevas.append(item)
            continue
        if code == 'bet_read_vs_recorded':
            action = _accion_actual(hand, item.get('street'), item.get('pos'))
            if action is None or action.get('action') not in ('b', 'r'):
                continue
            try:
                amount = float(action.get('amount') or 0.0)
                bet_read = float(item.get('bet_read') or 0.0)
            except (TypeError, ValueError):
                nuevas.append(item)
                continue
            if abs(amount - bet_read) <= tol:
                continue
            item['amount_recorded'] = redondear2(amount)
            item['difference'] = redondear2(abs(bet_read - amount))
            nuevas.append(item)
            continue
        nuevas.append(item)
    audit['ambiguities'] = nuevas
    audit['ambiguous'] = bool(nuevas or audit.get('ambiguous_actions'))
    return resolucion


def reclasificar_showdown(hand):
    """Convierte una victoria por fold mal marcada en el showdown que muestran
    las acciones, y recalcula el audit. No toca `final_pot`."""
    hid = hand.get('hand_id')
    if hid not in SHOWDOWN_20261104:
        return []
    live, _folded = live_positions(hand)
    if len(live) < 2:
        raise ValueError('%s: no hay dos jugadores vivos (%s)' % (hid, live))
    audit = hand.get('recorder_audit') or {}
    cambios = []
    if audit.get('fold_win') is not False:
        audit['fold_win'] = False
        cambios.append('fold_win -> false')
    if not hand.get('showdown'):
        texto = showdown_text(hand)
        if texto is None:
            raise ValueError('%s: no puedo resolver el ganador' % hid)
        hand['showdown'] = {'winner1': texto}
        cambios.append('showdown %s' % texto)
    breakdown = calcular_bote(hand, fold_win=False)
    antes = {k: audit.get(k) for k in breakdown}
    for campo, valor in breakdown.items():
        audit[campo] = valor
    if any(abs(float(antes.get(k) or 0.0) - float(v or 0.0)) > 0.001
           for k, v in breakdown.items()):
        cambios.append('audit')
    notas_antes = copy.deepcopy(audit.get('ambiguities'))
    resolucion_antes = audit.get('pot_resolution')
    limpiar_notas(hand, breakdown)
    if audit.get('ambiguities') != notas_antes:
        cambios.append('notas')
    if audit.get('pot_resolution') != resolucion_antes:
        cambios.append('resolucion')
    return cambios


def corregir_h1330(hand):
    """Inserta el fold de MP preflop si no esta registrado."""
    acts = ((hand.get('streets') or {}).get('preflop') or {}).get(
        'actions') or []
    if any(a.get('pos') == 'MP' for a in acts):
        return []
    idx = None
    for i, a in enumerate(acts):
        if a.get('pos') == 'UTG' and a.get('action') in ('c', 'r', 'b'):
            idx = i + 1
            break
    if idx is None:
        raise ValueError('H_1330: no encuentro la accion de UTG')
    acts.insert(idx, {
        'pos': 'MP', 'action': 'f', 'amount': 0.0,
        'amount_type': 'observed', 'inferred': True})
    return ['MP fold preflop']


def corregir_h1337(hand):
    cambios = []
    pre = ((hand.get('streets') or {}).get('preflop') or {}).get(
        'actions') or []
    for action in pre:
        if (action.get('pos') == 'SB' and action.get('action') == 'r'
                and float(action.get('amount') or 0.0) <= 1.0 + 1e-9):
            action['action'] = 'c'
            cambios.append('SB r 1.0 -> c 1.0')
    audit = hand.get('recorder_audit') or {}
    if audit.get('fold_win') is not False:
        audit['fold_win'] = False
        cambios.append('fold_win -> false')
    if not hand.get('showdown'):
        hand['showdown'] = {'winner1': SHOWDOWN['H_1337']}
        cambios.append('showdown')
    if audit.get('pot_resolution') != 'read_confirms_calculated':
        audit['pot_resolution'] = 'read_confirms_calculated'
        cambios.append('pot_resolution')
    return cambios


def corregir_h1342(hand):
    cambios = []
    if not hand.get('showdown'):
        hand['showdown'] = {'winner1': SHOWDOWN['H_1342']}
        cambios.append('showdown')
    audit = hand.get('recorder_audit') or {}
    matched = uncalled = gross = 0.0
    for street in STREETS:
        m, u, g = matched_y_uncalled(aportes_calle(hand, street))
        matched += m
        uncalled += u
        gross += g
    matched, uncalled, gross = (redondear2(matched), redondear2(uncalled),
                                redondear2(gross))
    if abs(float(audit.get('gross_contributions') or 0.0) - gross) > 0.001:
        audit['gross_contributions'] = gross
        cambios.append('gross')
    if abs(float(audit.get('matched_contributions') or 0.0) - matched) > 0.001:
        audit['matched_contributions'] = matched
        cambios.append('matched')
    if abs(float(audit.get('uncalled') or 0.0) - uncalled) > 0.001:
        audit['uncalled'] = uncalled
        cambios.append('uncalled')
    return cambios


def corregir_showdown(hand):
    hid = hand.get('hand_id')
    if hand.get('showdown'):
        return []
    hand['showdown'] = {'winner1': SHOWDOWN[hid]}
    return ['showdown']


CORRECTORES = {
    'H_1330': corregir_h1330,
    'H_1336': reclasificar_showdown,
    'H_1337': corregir_h1337,
    'H_1342': corregir_h1342,
    'H_1343': reclasificar_showdown,
    'H_1344': corregir_showdown,
    'H_1345': reclasificar_showdown,
    'H_1348': reclasificar_showdown,
    'H_1351': reclasificar_showdown,
    'H_1354': reclasificar_showdown,
    'H_1355': corregir_showdown,
    'H_1356': reclasificar_showdown,
    'H_1361': corregir_showdown,
    'H_1366': reclasificar_showdown,
}


def corregir_mano(hand):
    fn = CORRECTORES.get(hand.get('hand_id'))
    if fn is None:
        return None
    original = copy.deepcopy(hand)
    cambios = fn(hand)
    if hand == original:
        return None
    return {'hand_id': hand.get('hand_id'), 'cambios': cambios}


def construir_plan(db_path=DB_PATH):
    lineas = leer_lineas(db_path)
    nuevas = [None] * len(lineas)
    cambios = []
    for i, linea in enumerate(lineas):
        if not linea.strip():
            continue
        hand = json.loads(linea)
        detalle = corregir_mano(hand)
        if detalle is not None:
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
    print('=' * 78)
    print('RESULTADOS DE LA SECCION 2026-11-04')
    print('=' * 78)
    print('manos que cambian: %d' % len(cambios))
    print()
    for d in cambios:
        print('  %-7s %s' % (d['hand_id'], ', '.join(d['cambios'])))
    print()
    if not cambios:
        print('nada que cambiar: las manos del 4/11 ya estan corregidas.')
        return 0
    if not args.apply:
        print('dry-run: no se ha escrito nada. Usa --apply para aplicar.')
        return 0
    return 0 if aplicar(lineas, nuevas) else 1


if __name__ == '__main__':
    raise SystemExit(main())
