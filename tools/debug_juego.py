"""
debug_juego.py — Process 6 screenshot frames of a poker hand and
compare with the expected hand record from hands_db.jsonl.
"""
import os, sys, json
from PIL import Image
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'tools'))

from lector_estado import StateReader
from lector_unificado import CardReader

JUEGO_DIR = os.path.join(REPO, 'capturas', 'juego')
DB_PATH   = os.path.join(REPO, 'data', 'hands_db.jsonl')

# ---------------------------------------------------------------------------
# Helper: format a single state dict into readable lines
# ---------------------------------------------------------------------------
PLAYER_KEYS = ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']

def fmt_state(state):
    lines = []
    lines.append(f"  pot       = {state.get('pot')!r}")
    lines.append(f"  pot       = {state.get('pot')!r}")
    lines.append(f"  btn       = {state.get('btn')!r}")
    lines.append(f"  hero_cards= {state.get('hero_cards')!r}")
    com = state.get('community', [])
    com_strs = []
    for c in com:
        if c and c.get('rank'):
            r = c['rank']
            s = c.get('suit', '')
            com_strs.append(f"{r}{s}" if s else r)
        else:
            com_strs.append('--')
    lines.append(f"  community = {com_strs}")
    lines.append(f"  players:")
    for pk in PLAYER_KEYS:
        stake = state.get(f'{pk}_stake')
        bet   = state.get(f'{pk}_bet')
        st    = state.get(f'{pk}_state')
        lines.append(f"    {pk:6s}: stake={stake!r:>8s}  bet={bet!r:>8s}  state={st!r}")
    return '\n'.join(lines)

# ---------------------------------------------------------------------------
# 1. Load readers
# ---------------------------------------------------------------------------
print("=" * 72)
print("DEBUG JUEGO — mano1 (0..5)")
print("=" * 72)

print("\n--- Loading readers ... ", end='', flush=True)
sr = StateReader()
cr = CardReader()
print("OK")

# ---------------------------------------------------------------------------
# 2. Process each frame
# ---------------------------------------------------------------------------
frames = []
for i in range(6):
    fname = f"mano1 ({i}).png"
    path  = os.path.join(JUEGO_DIR, fname)
    if not os.path.exists(path):
        print(f"\n  *** {fname}: FILE NOT FOUND ***")
        continue

    pil = Image.open(path)
    img_arr = np.array(pil.convert('RGB'))

    state = sr.read_all(pil)
    cards = cr.read_all(img_arr)
    state['hero_cards'] = cards['hero']
    state['community']  = cards['community']

    frames.append(state)

    print(f"\n{'-' * 72}")
    print(f"  FRAME {i} — {fname}")
    print(f"{'-' * 72}")
    print(fmt_state(state))

# ---------------------------------------------------------------------------
# 3. Compare with expected hand from DB
# ---------------------------------------------------------------------------
print(f"\n{'=' * 72}")
print("COMPARISON WITH hands_db.jsonl (first line)")
print('=' * 72)

with open(DB_PATH, encoding='utf-8') as f:
    expected = json.loads(f.readline())

print(f"\n  hand_id  : {expected['hand_id']}")
print(f"  btn_idx  : {expected['btn_idx']}")
print(f"  final_pot: {expected['final_pot']}")
print(f"  showdown : {expected['showdown']}")
print(f"\n  Expected community cards:")
for street in ['preflop', 'flop', 'turn', 'river']:
    board = expected['streets'][street]['board']
    print(f"    {street:>8s}: {board}")

print(f"\n  Expected players:")
for pl in expected['players']:
    print(f"    {pl['pos']:4s} {pl['name']:12s} stack={pl['stack']:>6.1f}  cards={pl['cards']!r}  active={pl['active']}")

# ---------------------------------------------------------------------------
# 4. Identify what each frame represents
# ---------------------------------------------------------------------------
print(f"\n{'-' * 72}")
print("FRAME IDENTIFICATION")
print('-' * 72)

for i, st in enumerate(frames):
    com = st.get('community', [])
    ranks = [c['rank'] for c in com if c and c.get('rank')]
    ncards = len(ranks)
    # Determine street based on number of community cards visible
    if ncards == 0:
        street = "PREFLOP"
    elif ncards <= 2:
        street = "PREFLOP or early FLOP"
    elif ncards == 3:
        street = "FLOP"
    elif ncards == 4:
        street = "TURN"
    elif ncards == 5:
        street = "RIVER"
    else:
        street = f"?? ({ncards} cards)"

    # Check for showdown indicators (hero cards visible and community complete)
    hero = st.get('hero_cards', [None, None])
    has_hero = bool(hero and hero[0] and hero[1])
    showdown_hint = ""
    if has_hero and ncards == 5:
        showdown_hint = "  <- SHOWDOWN (hero cards + full board)"
    elif has_hero and ncards < 5:
        showdown_hint = "  <- hero cards visible but board incomplete"

    print(f"  Frame {i}: {ncards} community cards -> {street}{showdown_hint}")
    if ranks:
        suits = [c.get('suit', '') or '' for c in com if c and c.get('rank')]
        cards_str = [f"{r}{s}" for r, s in zip(ranks, suits)]
        print(f"           cards: {cards_str}")

print(f"\n{'=' * 72}")
print("DONE")
