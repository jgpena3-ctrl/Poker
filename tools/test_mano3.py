"""
Test: reproduce mano3 frames through LiveRecorder and show all state.
"""
import json, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from capture_live import init_reader, get_readers
from lector_estado import CAPTURAS_DIR
from recorder.recorder_live import LiveRecorder, PLAYER_NAMES, OUTPUT_PATH

PLAYER_NAMES.update({
    'hero': 'Juanmabm', 'p1': 'Jarduan', 'p2': 'NESANVAR',
    'p3': 'Pipaaf182', 'p4': 'mur420', 'p5': 'Hachirama',
})

JUEGO_DIR = os.path.join(CAPTURAS_DIR, 'juego')

def load_frame(num):
    path = os.path.join(JUEGO_DIR, f'mano3 ({num}).png')
    if not os.path.exists(path):
        return None
    pil = Image.open(path)
    img_arr = np.array(pil.convert('RGB'))
    state = STATE_READER.read_all(pil)
    cards = CARD_READER.read_all(img_arr)
    state['p1_cards'] = cards['hero']
    state['community'] = cards['community']
    return state, img_arr, pil

print('=== Inicializando lectores...')
init_reader()
STATE_READER, CARD_READER = get_readers()
print('  OK')

recorder = LiveRecorder()
recorder.output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'test_output_mano3.jsonl')
if os.path.exists(recorder.output_path):
    os.remove(recorder.output_path)

for frame_num in range(1, 13):
    result = load_frame(frame_num)
    if result is None:
        print(f'Frame {frame_num}: no file, stopping.')
        break
    state, img_arr, pil = result

    print(f'\n=== Frame {frame_num} ===')
    pot = state.get('pot')
    btn = state.get('btn')
    coms = recorder._visible_coms(state)
    print(f'pot={pot} btn={btn} coms={coms}')
    for p in ['hero','p1','p2','p3','p4','p5']:
        sk = state.get(f'{p}_stake')
        bt = state.get(f'{p}_bet')
        st = state.get(f'{p}_state')
        sk_s = f'{sk:.1f}' if sk is not None else '-'
        bt_s = f'{bt:.1f}' if bt is not None else '-'
        st_s = st or '-'
        print(f'  {p:>6} stake={sk_s:>6} bet={bt_s:>6} state={st_s}')

    rec_log = []
    recorder.process_frame(state, img_arr, log=lambda msg: rec_log.append(msg))

    if recorder.hand:
        cur = recorder.hand['current_street']
        print(f'  current_street={cur}')
        print(f'  inactive={recorder._inactive_players}')
        for sn in ['preflop', 'flop', 'turn', 'river']:
            acts = recorder.hand['streets'][sn]['actions']
            if acts:
                print(f'    {sn}: {acts}')
    else:
        print('  (no hand)')

    if rec_log:
        print(f'  logs:')
        for msg in rec_log:
            print(f'    {msg}')

if recorder.hand:
    print('\n>> Forzando cierre')
    recorder.finalize_hand(recorder.last_state)

print('\n=== Resultado final ===')
if os.path.exists(recorder.output_path):
    with open(recorder.output_path) as f:
        print(f.read())
