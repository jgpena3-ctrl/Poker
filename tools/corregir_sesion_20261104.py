# -*- coding: utf-8 -*-
"""Corrige la sesion del 2026-11-04 en data/hands_db.jsonl.

Dos cambios, ambos acotados y reversibles:

1. Comision real del 5 % en H_1328..H_1341.
   La mesa cobraba 5 % con tope de 2.5 BB, pero el recorder tenia activada
   la palomita de 3 % / 0.3 BB. Se recalcula la comision sobre el mismo
   `rake_basis` que ya estaba registrado y se ajustan los importes de bote
   que dependian de ella. H_1342 en adelante ya estaba al 3 % y no se toca.

2. Los folds inferidos dejan de ser ambiguedades.
   Un fold que la mesa ya aplico no necesita revision. Se elimina la marca
   `ambiguous` de la accion, se conserva `inferred` como procedencia y se
   retira la anotacion `fold_missing_at_close`. Tambien se recalcula
   `recorder_audit.ambiguous_actions` a partir de las acciones reales.

3. Los checks inferidos del BB tras los limps dejan de ser ambiguedades.
   Son una regla del juego, no una duda: se conserva `inferred` pero se
   retira `ambiguous` de la accion.

Uso:
    python tools/corregir_sesion_20261104.py            # dry-run
    python tools/corregir_sesion_20261104.py --apply    # escribe con backup
"""
import argparse
import copy
import hashlib
import io
import json
import os
import shutil
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, 'data', 'hands_db.jsonl')
BACKUP_DIR = os.path.join(ROOT, 'data', '_backup_corregir_sesion_20261104')

FECHA = '2026-11-04'
H_MIN, H_MAX = 1328, 1341
RAKE_RATE_5 = 0.05
RAKE_CAP_BB_5 = 2.5
RAKE_RATE_3 = 0.03
RAKE_CAP_BB_3 = 0.3


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def leer_lineas(path):
    with io.open(path, encoding='utf-8') as f:
        return f.readlines()


def numero_mano(hand):
    hid = str(hand.get('hand_id') or '')
    try:
        return int(hid.split('_')[1])
    except (IndexError, ValueError):
        return None


def es_sesion_5pct(hand):
    return (str(hand.get('date') or '').startswith(FECHA)
            and numero_mano(hand) is not None
            and H_MIN <= numero_mano(hand) <= H_MAX)


def _round1(value):
    return round(max(0.0, float(value)), 1)


def _round2(value):
    return round(float(value), 2)


def limpiar_folds(hand):
    """Quita la ambiguedad de los folds inferidos. Devuelve cuantos toco."""
    audit = hand.get('recorder_audit')
    if not isinstance(audit, dict):
        return 0
    tocados = 0
    for data in (hand.get('streets') or {}).values():
        for action in (data or {}).get('actions') or []:
            if action.get('action') == 'f' and action.get('ambiguous') is True:
                del action['ambiguous']
                tocados += 1

    ambiguities = audit.get('ambiguities')
    if isinstance(ambiguities, list):
        antes = len(ambiguities)
        audit['ambiguities'] = [
            a for a in ambiguities
            if not (isinstance(a, dict)
                    and a.get('code') == 'fold_missing_at_close')]
        tocados += antes - len(audit['ambiguities'])

    # Reconstruir la lista desde las acciones evita dejar entradas de folds
    # que ya no llevan la marca o que se editaron despues del cierre.
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
    return tocados


def limpiar_checks(hand):
    """Quita la ambiguedad de los checks inferidos. Devuelve cuantos toco.

    El check del BB tras los limps es una regla del juego, no una duda; se
    conserva `inferred` como procedencia.
    """
    audit = hand.get('recorder_audit')
    if not isinstance(audit, dict):
        return 0
    tocados = 0
    for data in (hand.get('streets') or {}).values():
        for action in (data or {}).get('actions') or []:
            if action.get('action') == 'x' and action.get('ambiguous') is True:
                del action['ambiguous']
                tocados += 1
    if tocados:
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
        audit['ambiguous'] = bool(audit.get('ambiguities')
                                  or ambiguous_actions)
    return tocados


def corregir_comision(hand):
    """Pasa la comision registrada del 3 % al 5 % real. Devuelve el detalle."""
    audit = hand.get('recorder_audit')
    if not isinstance(audit, dict):
        raise ValueError('%s no tiene recorder_audit' % hand.get('hand_id'))
    for campo in ('rake_basis', 'rake', 'fold_win',
                  'gross_contributions', 'matched_contributions'):
        if campo not in audit:
            raise ValueError('%s no tiene recorder_audit.%s'
                             % (hand.get('hand_id'), campo))

    basis = float(audit.get('rake_basis') or 0.0)
    bb = float(audit.get('big_blind') or 1.0)
    old_rake = _round2(audit.get('rake') or 0.0)
    new_rake = _round2(min(RAKE_RATE_5 * basis, RAKE_CAP_BB_5 * bb))

    # Idempotencia: si ya esta al 5 %, no se vuelve a aplicar.
    correction = audit.get('commission_correction')
    if audit.get('rake_cap') == _round2(RAKE_CAP_BB_5 * bb) \
            and abs(old_rake - new_rake) < 0.005:
        return {'ya_aplicada': True, 'old': old_rake, 'new': new_rake,
                'delta': 0.0, 'basis': basis}

    # Precondicion: el estado de partida debe ser el esquema del 3 %.
    esperado_3 = _round2(min(RAKE_RATE_3 * basis, RAKE_CAP_BB_3 * bb))
    if abs(old_rake - esperado_3) > 0.005 or audit.get('rake_cap') != _round2(
            RAKE_CAP_BB_3 * bb):
        raise ValueError(
            '%s no esta en el esquema del 3 %% esperado (rake=%s, cap=%s, '
            'esperado=%s/%s)'
            % (hand.get('hand_id'), old_rake, audit.get('rake_cap'),
               esperado_3, _round2(RAKE_CAP_BB_3 * bb)))

    delta = _round2(new_rake - old_rake)
    if delta < 0:
        raise ValueError('%s: la comision nueva es menor que la vieja'
                         % hand.get('hand_id'))

    audit['rake'] = new_rake
    audit['rake_cap'] = _round2(RAKE_CAP_BB_5 * bb)
    for campo in ('pot_calculated', 'pot_calculated_noninflated',
                  'pot_live_calculated'):
        if isinstance(audit.get(campo), (int, float)):
            audit[campo] = _round1(audit[campo] - delta)

    if isinstance(hand.get('final_pot'), (int, float)):
        hand['final_pot'] = _round1(hand['final_pot'] - delta)

    # El aviso de bote calculado se recalcula: si el unico motivo era la
    # comision, deja de ser una ambiguedad pendiente.
    pot_read = audit.get('pot_read')
    if isinstance(pot_read, (int, float)):
        tol = float(audit.get('ambiguity_tolerance') or 0.2)
        calc = audit.get('pot_calculated')
        noninfl = audit.get('pot_calculated_noninflated')
        fold_win = bool(audit.get('fold_win'))
        resolution = 'calculated'
        if (fold_win and abs(pot_read - noninfl) <= tol
                and abs(pot_read - calc) > 0.005):
            resolution = 'read_noninflated_to_inflated'
        elif abs(pot_read - calc) <= tol:
            resolution = 'read_confirms_calculated'
        else:
            resolution = 'ambiguous_read_mismatch'
        audit['pot_resolution'] = resolution
        ambiguities = audit.get('ambiguities')
        if isinstance(ambiguities, list):
            if resolution == 'ambiguous_read_mismatch':
                for item in ambiguities:
                    if isinstance(item, dict) \
                            and item.get('code') == 'pot_read_vs_calculated':
                        item['pot_calculated'] = calc
                        item['pot_calculated_noninflated'] = noninfl
                        item['difference'] = _round2(
                            abs(float(pot_read) - float(calc)))
            else:
                audit['ambiguities'] = [
                    a for a in ambiguities
                    if not (isinstance(a, dict)
                            and a.get('code') == 'pot_read_vs_calculated')]

    audit.setdefault('commission_correction', {})
    audit['commission_correction'] = {
        'reason': 'la mesa cobraba 5% y el recorder estaba en 3%',
        'rate': RAKE_RATE_5,
        'cap_bb': RAKE_CAP_BB_5,
        'base_rate': RAKE_RATE_3,
        'previous_rake': old_rake,
        'rake': new_rake,
        'pot_delta': _round2(-delta),
    }
    return {'ya_aplicada': False, 'old': old_rake, 'new': new_rake,
            'delta': delta, 'basis': basis}


def construir_plan(db_path=DB_PATH):
    lineas = leer_lineas(db_path)
    nuevas = [None] * len(lineas)
    cambios = []
    tocadas = 0
    for i, linea in enumerate(lineas):
        if not linea.strip():
            continue
        hand = json.loads(linea)
        original = copy.deepcopy(hand)
        detalle = {}
        if es_sesion_5pct(hand):
            detalle['comision'] = corregir_comision(hand)
        detalle['folds'] = limpiar_folds(hand)
        detalle['checks'] = limpiar_checks(hand)
        if hand != original:
            nuevas[i] = hand
            tocadas += 1
            cambios.append((hand.get('hand_id'), detalle))
    return lineas, nuevas, cambios, tocadas


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


def verificar(antes, despues):
    msgs = []
    ok = True
    if len(antes) != len(despues):
        return False, ['FALLO: cambio el numero de lineas (%d -> %d)'
                       % (len(antes), len(despues))]

    manos_antes = [json.loads(l) for l in antes if l.strip()]
    manos_despues = [json.loads(l) for l in despues if l.strip()]
    if len(manos_antes) != len(manos_despues):
        return False, ['FALLO: cambio el numero de manos']

    for h in manos_despues:
        audit = h.get('recorder_audit') or {}
        for data in (h.get('streets') or {}).values():
            for a in (data or {}).get('actions') or []:
                if a.get('action') == 'f' and a.get('ambiguous') is True:
                    ok = False
                    msgs.append('FALLO: %s conserva fold ambiguo'
                                % h.get('hand_id'))
                if a.get('action') == 'x' and a.get('ambiguous') is True:
                    ok = False
                    msgs.append('FALLO: %s conserva check ambiguo'
                                % h.get('hand_id'))
                if any(x.get('action') == 'f'
                       for x in (audit.get('ambiguous_actions') or [])):
                    ok = False
                    msgs.append('FALLO: %s lista un fold en ambiguous_actions'
                                % h.get('hand_id'))
        if any(a.get('code') == 'fold_missing_at_close'
               for a in (audit.get('ambiguities') or [])):
            ok = False
            msgs.append('FALLO: %s conserva fold_missing_at_close'
                        % h.get('hand_id'))
        if es_sesion_5pct(h):
            basis = float(audit.get('rake_basis') or 0.0)
            bb = float(audit.get('big_blind') or 1.0)
            esperado = _round2(min(RAKE_RATE_5 * basis,
                                   RAKE_CAP_BB_5 * bb))
            if abs(float(audit.get('rake') or 0.0) - esperado) > 0.005:
                ok = False
                msgs.append('FALLO: %s rake=%s, esperado=%s'
                            % (h.get('hand_id'), audit.get('rake'), esperado))
            if audit.get('rake_cap') != _round2(RAKE_CAP_BB_5 * bb):
                ok = False
                msgs.append('FALLO: %s rake_cap=%s, esperado=%s'
                            % (h.get('hand_id'), audit.get('rake_cap'),
                               _round2(RAKE_CAP_BB_5 * bb)))
    if ok:
        msgs.append('OK  folds y checks inferidos sin marca de ambiguedad')
        msgs.append('OK  comision al 5 %% en H_%d..H_%d' % (H_MIN, H_MAX))
    return ok, msgs


def imprimir_plan(cambios, tocadas):
    print('=' * 78)
    print('CORRECCION DE LA SESION %s' % FECHA)
    print('=' * 78)
    print('manos que cambian: %d' % tocadas)
    print()
    for hid, detalle in cambios:
        com = detalle.get('comision')
        folds = detalle.get('folds', 0)
        checks = detalle.get('checks', 0)
        partes = []
        if com:
            if com.get('ya_aplicada'):
                partes.append('comision ya al 5%% (rake=%s)' % com['new'])
            else:
                partes.append('rake %s -> %s (delta %+.2f, base %s)'
                              % (com['old'], com['new'], com['delta'],
                                 com['basis']))
        if folds:
            partes.append('%d marca(s) de fold retirada(s)' % folds)
        if checks:
            partes.append('%d check(s) inferido(s) sin ambiguedad' % checks)
        print('  %-7s %s' % (hid, '; '.join(partes)))


def aplicar(lineas, nuevas, cambios, tocadas):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup = os.path.join(BACKUP_DIR, 'hands_db.jsonl')
    if os.path.exists(backup):
        # Conservar el punto de restauracion original de la sesion.
        print('backup    : %s (existente, se conserva)'
              % os.path.relpath(backup, ROOT))
        print('sha256    : %s' % sha256(backup))
    else:
        shutil.copy2(DB_PATH, backup)
        h_orig, h_back = sha256(DB_PATH), sha256(backup)
        print('backup    : %s' % os.path.relpath(backup, ROOT))
        print('sha256    : %s' % h_orig)
        print('verificado: %s' % ('OK, coinciden' if h_orig == h_back
                                 else 'FALLO, NO coinciden'))
        if h_orig != h_back:
            raise RuntimeError('el backup no coincide con el original; '
                               'abortando')

    salida = []
    for i, linea in enumerate(lineas):
        salida.append(linea if nuevas[i] is None
                      else json.dumps(nuevas[i], ensure_ascii=False) + '\n')

    ok, msgs = verificar(lineas, salida)
    if not ok:
        print('la verificacion en memoria falla; NO se escribe nada:')
        for m in msgs:
            print('   %s' % m)
        return False

    tmp = escribir_atomico(salida, DB_PATH)
    try:
        os.replace(tmp, DB_PATH)
    except Exception:
        os.remove(tmp)
        shutil.copy2(backup, DB_PATH)
        raise

    releido = leer_lineas(DB_PATH)
    ok2, msgs2 = verificar(lineas, releido)
    print()
    print('VERIFICACION POST-ESCRITURA')
    for m in msgs2:
        print('   %s' % m)
    if not ok2:
        print('restaurando el backup')
        shutil.copy2(backup, DB_PATH)
        return False

    print()
    print('aplicado. nuevo sha256: %s' % sha256(DB_PATH))
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true',
                    help='escribe los cambios (sin esto solo muestra el plan)')
    args = ap.parse_args(argv)

    lineas, nuevas, cambios, tocadas = construir_plan()
    imprimir_plan(cambios, tocadas)
    print()
    if not tocadas:
        print('nada que cambiar: la base ya esta corregida.')
        return 0
    if not args.apply:
        print('dry-run: no se ha escrito nada. Usa --apply para aplicar.')
        return 0
    return 0 if aplicar(lineas, nuevas, cambios, tocadas) else 1


if __name__ == '__main__':
    raise SystemExit(main())
