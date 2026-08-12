"""
Test: reproduce mano6 capture through LiveRecorder.
"""
import json, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from capture_live import init_reader, get_readers
from lector_estado import CAPTURAS_DIR
from recorder.recorder_live import LiveRecorder, PLAYER_NAMES

PLAYER_NAMES.update({
    'hero': 'Juanmabm', 'p1': 'Jarduan', 'p2': 'NESANVAR',
    'p3': 'Pipaaf182', 'p4': 'mur420', 'p5': 'Hachirama',
})

print('=== Inicializando lectores...')
init_reader()
sr, cr = get_readers()
print('  OK')

rec = LiveRecorder()
rec.output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'test_mano6.jsonl')
if os.path.exists(rec.output_path):
    os.remove(rec.output_path)

path = os.path.join(CAPTURAS_DIR, 'juego', 'mano6.png')
pil = Image.open(path)
img = np.array(pil.convert('RGB'))
state = sr.read_all(pil)
cards = cr.read_all(img)
for k in ['hero','p1','p2','p3','p4','p5']:
    if k in cards and cards[k]:
        state[f'{k}_cards'] = cards[k]
state['community'] = cards.get('community', [])

print()
print('=== State ===')
print(f'pot={state.get("pot")} btn={state.get("btn")}')
for p in ['hero','p1','p2','p3','p4','p5']:
    sk = state.get(f'{p}_stake')
    bt = state.get(f'{p}_bet')
    st = state.get(f'{p}_state')
    print(f'  {p}: stake={sk} bet={bt} state={st}')
print(f'community: {state.get("community")}')
print(f'cards:')
for p in ['hero','p1','p2','p3','p4','p5']:
    c = state.get(f'{p}_cards')
    if c:
        print(f'  {p}: {c}')

logs = []
rec.process_frame(state, img, log=lambda m: logs.append(m))
print()
for m in logs:
    print(m)

if rec.hand:
    print()
    print('=== Hand ===')
    print(json.dumps(rec.hand, indent=2, default=str))
else:
    print('no hand')
