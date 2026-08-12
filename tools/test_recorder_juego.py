"""
test_recorder_juego.py — Reproduce las capturas de juego en
capturas/juego/ a través de la lógica de LiveRecorder y valida
el resultado contra la primera entrada de hands_db.jsonl.

Uso:  python test_recorder_juego.py
"""
import json, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from capture_live import init_reader, get_readers
from lector_estado import CAPTURAS_DIR
from recorder.recorder_live import LiveRecorder, PLAYER_NAMES, OUTPUT_PATH

JUEGO_DIR = os.path.join(CAPTURAS_DIR, 'juego')
EXPECTED_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'hands_db.jsonl')

PLAYER_NAMES.update({
    'hero': 'Juanmabm',
    'p1': 'Jarduan',
    'p2': 'NESANVAR',
    'p3': 'Pipaaf182',
    'p4': 'mur420',
    'p5': 'Hachirama',
})


def load_frame(num):
    """Carga una captura de juego desde archivo, ejecuta lectores, devuelve state."""
    path = os.path.join(JUEGO_DIR, f'mano1 ({num}).png')
    if not os.path.exists(path):
        return None
    pil = Image.open(path)
    img_arr = np.array(pil.convert('RGB'))
    state = STATE_READER.read_all(pil)
    cards = CARD_READER.read_all(img_arr)
    state['p1_cards'] = cards['hero']
    state['community'] = cards['community']
    return state, img_arr, pil


def print_state(state, label=''):
    print(f'\n--- {label} ---')
    pot = state.get('pot')
    btn = state.get('btn')
    print(f'  pot={pot} btn={btn} hero={state.get("hero_cards")}')
    com = state.get('community', [])
    com_str = ' '.join(
        f'{c["rank"]}{c["suit"]}' if c and c.get('rank') else '?'
        for c in com
    )
    print(f'  community: {com_str}')
    print(f'  {"player":>8} {"stake":>7} {"bet":>7} {"state":>15}')
    print(f'  {"-" * 42}')
    for p in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
        sk = state.get(f'{p}_stake')
        bt = state.get(f'{p}_bet')
        st = state.get(f'{p}_state', '—') or '—'
        sk_s = f'{sk:.1f}' if sk is not None else '-'
        bt_s = f'{bt:.1f}' if bt is not None else '-'
        print(f'  {p:>8} {sk_s:>7} {bt_s:>7} {st:>15}')


def print_hand(hand, label=''):
    if hand is None:
        print(f'\n{label}: (no hand)')
        return
    print(f'\n{label}: {hand["hand_id"]}')
    for p in hand['players']:
        print(f'  {p["name"]:>12} pos={p["pos"]:>3} stack={p["stack"]} cards={p["cards"]}')
    for sname in ['preflop', 'flop', 'turn', 'river']:
        s = hand['streets'].get(sname)
        if s and s['actions']:
            board = ' '.join(s['board']) if s['board'] else ''
            print(f'  {sname:>8} [{board}]')
            for a in s['actions']:
                amt_s = f'{a["amount"]:.1f}' if isinstance(a['amount'], float) else str(a['amount'])
                print(f'           {a["pos"]:>3} {a["action"]} {amt_s}')
    com = hand.get('comunitarias', {})
    for st in ['flop', 'turn', 'river']:
        if com.get(st):
            print(f'  {st:>8} cards: {" ".join(com[st])}')
    fp = hand.get('final_pot')
    sw = hand.get('showdown', {})
    print(f'  final_pot={fp}  showdown={sw}')


# ============================================================
if __name__ == '__main__':
    print('=== Inicializando lectores...')
    init_reader()
    STATE_READER, CARD_READER = get_readers()
    print('  OK')

    recorder = LiveRecorder()
    recorder.output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'test_output.jsonl')

    # Limpiar salida previa
    if os.path.exists(recorder.output_path):
        os.remove(recorder.output_path)

    print('\n=== Reproduciendo frames ===')

    for frame_num in range(6):
        result = load_frame(frame_num)
        if result is None:
            print(f'Frame {frame_num}: archivo no encontrado, terminando.')
            break

        state, img_arr, pil = result

        print(f'--- Frame {frame_num} ---')
        btn = state.get('btn')
        coms = recorder._visible_coms(state)
        com_list = recorder._get_com_list(state)
        print(f'btn={btn} coms={coms} community={" ".join(com_list)}')
        for p in ['hero','p1','p2','p3','p4','p5']:
            sk = state.get(f'{p}_stake')
            bt = state.get(f'{p}_bet')
            st = state.get(f'{p}_state')
            sk_s = f'{sk:.1f}' if sk is not None else '-'
            bt_s = f'{bt:.1f}' if bt is not None else '-'
            st_s = st or '-'
            print(f'  {p:>6} stake={sk_s:>6} bet={bt_s:>6} state={st_s}')

        pot = state.get('pot')
        if recorder.hand is not None and pot is not None:
            recorder.hand['max_pot'] = max(recorder.hand.get('max_pot', 0), pot)

        if recorder._is_new_hand(state):
            if recorder.hand is not None:
                print(f'  >> Mano anterior reemplazada')
                recorder.finalize_hand(recorder.last_state)
            recorder.start_hand(state)
            print(f'  >> NUEVA MANO: {recorder.hand["hand_id"]}')
            for a in recorder.hand['streets']['preflop']['actions']:
                print(f'     preflop: {a["pos"]} {a["action"]} {a["amount"]}')

        elif recorder.hand is not None:
            cur = recorder.hand['current_street']

            # 1. Detectar folds/lag en CADA frame (comparando last_state vs state)
            actions = recorder.detect_actions(state)
            for a in actions:
                s, pos, act, amt = a
                print(f'     {s}: {pos} {act} {amt}')

            # 2. Detectar cambio de calle
            ns = recorder.detect_street_change(state)
            if ns:
                print(f'  >> {ns.upper()}')
                recorder.change_street(ns, state)
                # 3. Procesar labels para la NUEVA calle
                recorder.process_street_labels(state, ns)
                for a in recorder.hand['streets'][ns]['actions']:
                    print(f'     {ns}: {a["pos"]} {a["action"]} {a["amount"]}')
            else:
                # 4. Sin cambio: procesar labels para la calle actual
                before = len(recorder.hand['streets'][cur]['actions'])
                recorder.process_street_labels(state, cur)
                for a in recorder.hand['streets'][cur]['actions'][before:]:
                    print(f'     {cur}: {a["pos"]} {a["action"]} {a["amount"]}')

            if recorder._is_hand_over(state):
                print(f'  >> MANO TERMINADA')
                recorder.finalize_hand(recorder.last_state)

        recorder.last_state = state
        recorder.last_img = img_arr

    # Si la mano no se cerró, forzar cierre
    if recorder.hand is not None:
        print(f'  >> Forzando cierre de mano')
        recorder.finalize_hand(recorder.last_state)

    # Mostrar resultado
    print('\n' + '=' * 60)
    print('RESULTADO DEL RECORDER')
    print('=' * 60)
    if os.path.exists(recorder.output_path):
        with open(recorder.output_path) as f:
            result_hand = json.loads(f.readline())
            print_hand(result_hand, 'RECORDER')

    # Comparar con expected
    print('\n' + '=' * 60)
    print('COMPARACIÓN CON EXPECTED')
    print('=' * 60)
    if os.path.exists(EXPECTED_PATH):
        with open(EXPECTED_PATH) as f:
            expected = json.loads(f.readline())
        print_hand(expected, 'EXPECTED')

        # Comparar acciones
        if os.path.exists(recorder.output_path):
            with open(recorder.output_path) as f:
                actual = json.loads(f.readline())

            mismatches = []
            for street in ['preflop', 'flop', 'turn', 'river']:
                ea = expected['streets'].get(street, {}).get('actions', [])
                aa = actual['streets'].get(street, {}).get('actions', [])
                if ea != aa:
                    mismatches.append((street, ea, aa))

            if mismatches:
                print('\nDIFERENCIAS:')
                for street, exp, act in mismatches:
                    print(f'  {street}:')
                    print(f'    expected: {exp}')
                    print(f'    actual:   {act}')
            else:
                print('\n  OK - Todas las calles coinciden')

            # Comparar comunitarias
            ec = expected.get('comunitarias', {})
            ac = actual.get('comunitarias', {})
            if ec != ac:
                print(f'\n  Comunitarias differ: expected={ec} actual={ac}')
            else:
                print(f'  OK - Comunitarias coinciden')
