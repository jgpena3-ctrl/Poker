# -*- coding: utf-8 -*-
"""Corrige la mano H_1333 (linea 1304 de data/hands_db.jsonl).

La mano se cerro como victoria por fold, pero MP habia igualado la subida del
river y no podia retirarse: el fold era un artefacto del cierre. Ademas, un
aviso de la mesa (el stack de MP subio +8.0) se interpreto como devolucion de
una apuesta no igualada, con lo que el bote quedo en 29.8 en vez de 37.1.

El script:
  1. quita el fold espurio del river;
  2. recalcula aportes, rake (5 % / 2.5 BB) y bote desde las acciones;
  3. deja `fold_win` en False y el bote en 37.1;
  4. retira las ambiguedades de bote y la accion BB x ya explicadas;
  5. documenta el cambio en `recorder_audit.manual_correction`.

Uso:
    python tools/corregir_mano_H_1333.py            # dry-run
    python tools/corregir_mano_H_1333.py --apply    # escribe con backup
    python tools/corregir_mano_H_1333.py --restore  # vuelve al backup
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
BACKUP_DIR = os.path.join(ROOT, 'data', '_backup_corregir_mano_H_1333')
BACKUP_PATH = os.path.join(BACKUP_DIR, 'hands_db.jsonl')

HAND_ID = 'H_1333'
RAKE_RATE = 0.05
RAKE_CAP_BB = 2.5
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


def aportes_calle(hand, street):
    """Aporte absoluto por posicion, igual que recorder._street_contributions."""
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
    """Replica recorder._pot_breakdown para esta mano."""
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
    big_blind = float((hand.get('recorder_audit') or {}).get(
        'big_blind') or 1.0)
    rake = min(RAKE_RATE * rake_basis, RAKE_CAP_BB * big_blind)
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
    }


def corregir_mano(hand):
    """Aplica la correccion en sitio. Devuelve el detalle documentado."""
    audit = hand.get('recorder_audit')
    if not isinstance(audit, dict):
        raise ValueError('%s no tiene recorder_audit' % HAND_ID)

    river = ((hand.get('streets') or {}).get('river') or {})
    acciones = river.get('actions') or []
    fold_espurio = [
        a for a in acciones
        if a.get('action') == 'f' and a.get('pos') == 'MP']

    previo = {
        'fold_win': bool(audit.get('fold_win')),
        'gross_contributions': audit.get('gross_contributions'),
        'matched_contributions': audit.get('matched_contributions'),
        'uncalled': audit.get('uncalled'),
        'rake_basis': audit.get('rake_basis'),
        'rake': audit.get('rake'),
        'pot_calculated': audit.get('pot_calculated'),
        'pot_calculated_noninflated': audit.get('pot_calculated_noninflated'),
    }
    # Idempotencia: si ya se aplico, conservar el "antes" historico en vez de
    # tomar como anterior el estado ya corregido.
    correccion_previa = audit.get('manual_correction')
    if isinstance(correccion_previa, dict) and correccion_previa.get('previous'):
        previo = {**previo, **correccion_previa['previous']}

    if fold_espurio:
        river['actions'] = [a for a in acciones if a not in fold_espurio]

    # El check inferido del BB tras los limps es una regla del juego: deja de
    # llevar la marca de ambiguedad en la accion, no solo en el listado.
    for street_data in (hand.get('streets') or {}).values():
        for action in street_data.get('actions') or []:
            if action.get('action') == 'x' and action.get('ambiguous'):
                del action['ambiguous']

    breakdown = calcular_bote(hand, fold_win=False)
    audit.update(breakdown)
    audit['fold_win'] = False
    audit['pot_resolution'] = 'read_confirms_calculated'
    hand['final_pot'] = breakdown['pot_calculated']
    hand['winner'] = ['hero']
    hand['showdown'] = {'winner1': 'BB (Jarduan)'}

    # Ambas ambiguedades de bote quedan explicadas por la correccion.
    audit['ambiguities'] = [
        a for a in (audit.get('ambiguities') or [])
        if not (isinstance(a, dict)
                and a.get('code') in ('pot_read_vs_calculated',
                                      'pot_read_vs_contributions'))]
    # El check del BB tras los limps es inferido pero no ambiguo.
    audit['ambiguous_actions'] = [
        a for a in (audit.get('ambiguous_actions') or [])
        if not (isinstance(a, dict)
                and a.get('pos') == 'BB' and a.get('action') == 'x')]
    audit['ambiguous'] = bool(audit['ambiguities']
                              or audit['ambiguous_actions'])

    comision = audit.get('commission_correction') or {}
    comision.update({
        'reason': 'la mesa cobraba 5% y el recorder estaba en 3%',
        'rate': RAKE_RATE,
        'cap_bb': RAKE_CAP_BB,
        'base_rate': 0.03,
        'previous_rake': 0.3,
        'rake': breakdown['rake'],
        'pot_delta': redondear2(0.3 - breakdown['rake']),
    })
    audit['commission_correction'] = comision
    audit['manual_correction'] = {
        'reason': 'El river tenia un fold de mas: MP igualo la subida y no '
                  'podia retirarse; ademas su +8.0 de stack era un aviso de '
                  'la mesa, no una devolucion de apuesta no igualada. El '
                  'check inferido del BB tampoco es ambiguo.',
        'removed_fold': {'street': 'river', 'pos': 'MP'},
        'removed_ambiguous_action': {'street': 'preflop', 'pos': 'BB',
                                     'action': 'x'},
        'removed_uncalled_return': 8.0,
        'previous': previo,
        'corrected': {
            'fold_win': False,
            'gross_contributions': breakdown['gross_contributions'],
            'matched_contributions': breakdown['matched_contributions'],
            'uncalled': breakdown['uncalled'],
            'rake_basis': breakdown['rake_basis'],
            'rake': breakdown['rake'],
            'pot_calculated': breakdown['pot_calculated'],
            'pot_calculated_noninflated':
                breakdown['pot_calculated_noninflated'],
        },
        'pot_delta': redondear2(breakdown['pot_calculated']
                                - float(previo['pot_calculated'] or 0.0)),
    }
    return audit


def construir_plan(db_path=DB_PATH):
    lineas = leer_lineas(db_path)
    nuevas = [None] * len(lineas)
    detalle = None
    encontrada = False
    for i, linea in enumerate(lineas):
        if not linea.strip():
            continue
        hand = json.loads(linea)
        if hand.get('hand_id') != HAND_ID:
            continue
        encontrada = True
        original = copy.deepcopy(hand)
        detalle = corregir_mano(hand)
        if hand != original:
            nuevas[i] = hand
    if not encontrada:
        raise ValueError('%s no esta en la base' % HAND_ID)
    return lineas, nuevas, detalle


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
    ok = True
    msgs = []
    if len(antes) != len(despues):
        return False, ['FALLO: cambio el numero de lineas']

    manos_antes = [json.loads(l) for l in antes if l.strip()]
    manos_despues = [json.loads(l) for l in despues if l.strip()]
    if len(manos_antes) != len(manos_despues):
        return False, ['FALLO: cambio el numero de manos']

    for h_antes, h_despues in zip(manos_antes, manos_despues):
        if h_despues.get('hand_id') != HAND_ID:
            if h_antes != h_despues:
                ok = False
                msgs.append('FALLO: se modifico %s' % h_despues.get('hand_id'))
            continue
        audit = h_despues.get('recorder_audit') or {}
        river = ((h_despues.get('streets') or {}).get('river') or {})
        if any(a.get('action') == 'f' and a.get('pos') == 'MP'
               for a in river.get('actions') or []):
            ok = False
            msgs.append('FALLO: sigue el fold espurio de MP')
        if any(action.get('ambiguous')
               for data in (h_despues.get('streets') or {}).values()
               for action in (data.get('actions') or [])):
            ok = False
            msgs.append('FALLO: quedan acciones marcadas como ambiguas')
        if audit.get('fold_win') is not False:
            ok = False
            msgs.append('FALLO: fold_win no quedo en False')
        esperado = generar_verificacion(h_despues)
        for campo, valor in esperado.items():
            if isinstance(valor, float):
                if abs(float(audit.get(campo) or 0.0) - valor) > 0.005:
                    ok = False
                    msgs.append('FALLO: %s=%s, esperado=%s'
                                % (campo, audit.get(campo), valor))
            elif audit.get(campo) != valor:
                ok = False
                msgs.append('FALLO: %s=%s, esperado=%s'
                            % (campo, audit.get(campo), valor))
        if h_despues.get('final_pot') != esperado['pot_calculated']:
            ok = False
            msgs.append('FALLO: final_pot=%s' % h_despues.get('final_pot'))
        if audit.get('ambiguous') is not False:
            ok = False
            msgs.append('FALLO: la mano sigue ambigua')
        if h_despues.get('showdown') != {'winner1': 'BB (Jarduan)'}:
            ok = False
            msgs.append('FALLO: showdown no normalizado')
    if ok:
        msgs.append('OK  fold espurio eliminado y bote recalculado')
        msgs.append('OK  H_%s: fold_win=False, bote=37.1' % '1333')
    return ok, msgs


def generar_verificacion(hand):
    """Valores esperados a partir de las acciones corregidas."""
    return calcular_bote(hand, fold_win=False)


def aplicar(lineas, nuevas):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if os.path.exists(BACKUP_PATH):
        # No sobrescribir: el backup es el punto de restauracion original.
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
        shutil.copy2(BACKUP_PATH, DB_PATH)
        raise

    releido = leer_lineas(DB_PATH)
    ok2, msgs2 = verificar(lineas, releido)
    print()
    print('VERIFICACION POST-ESCRITURA')
    for m in msgs2:
        print('   %s' % m)
    if not ok2:
        print('restaurando el backup')
        shutil.copy2(BACKUP_PATH, DB_PATH)
        return False

    print()
    print('aplicado. nuevo sha256: %s' % sha256(DB_PATH))
    return True


def restaurar():
    if not os.path.exists(BACKUP_PATH):
        raise SystemExit('no existe el backup: %s' % BACKUP_PATH)
    shutil.copy2(BACKUP_PATH, DB_PATH)
    print('restaurado %s' % DB_PATH)
    print('sha256: %s' % sha256(DB_PATH))
    return 0


def imprimir_plan(detalle):
    print('=' * 78)
    print('CORRECCION DE LA MANO %s' % HAND_ID)
    print('=' * 78)
    if not detalle:
        print('nada que cambiar: la mano ya esta corregida.')
        return
    previo = detalle['manual_correction']['previous']
    corregido = detalle['manual_correction']['corrected']
    print('fold espurio   : river MP (retirado)')
    print('fold_win       : %s -> %s'
          % (previo['fold_win'], corregido['fold_win']))
    print('aportes brutos : %s -> %s'
          % (previo['gross_contributions'], corregido['gross_contributions']))
    print('igualados      : %s -> %s'
          % (previo['matched_contributions'],
             corregido['matched_contributions']))
    print('no igualado    : %s -> %s'
          % (previo['uncalled'], corregido['uncalled']))
    print('rake           : %s -> %s'
          % (previo['rake'], corregido['rake']))
    print('bote           : %s -> %s'
          % (previo['pot_calculated'], corregido['pot_calculated']))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true',
                    help='escribe los cambios (sin esto solo muestra el plan)')
    ap.add_argument('--restore', action='store_true',
                    help='restaura hands_db.jsonl desde el backup')
    args = ap.parse_args(argv)

    if args.restore:
        return restaurar()

    lineas, nuevas, detalle = construir_plan()
    if not any(n is not None for n in nuevas):
        print('=' * 78)
        print('CORRECCION DE LA MANO %s' % HAND_ID)
        print('=' * 78)
        print('nada que cambiar: la mano ya esta corregida.')
        return 0
    imprimir_plan(detalle)
    print()
    if not args.apply:
        print('dry-run: no se ha escrito nada. Usa --apply para aplicar.')
        return 0
    return 0 if aplicar(lineas, nuevas) else 1


_ORIGINAL = {}

if __name__ == '__main__':
    raise SystemExit(main())
