"""
record_hand.py — Live poker hand recorder v2.1

Captures screenshots, reads table state, detects actions via bet/stack changes,
and writes JSONL to hands_db.jsonl.

Action detection approach:
  - PRIMARY: bet text changes on felt (appears, increases, disappears)
  - FOLD: stack becomes invisible (None) while others act
  - STREET: all bets disappear simultaneously → pot collected
  - CHECKS: inferred from turn order (when no action detected between active players)

Usage: python record_hand.py
Configuration: set PLAYER_NAMES below.
"""
import json, os, time, datetime
import sys
import numpy as np
from PIL import ImageGrab

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from lector_estado import StateReader
from lector_unificado import CardReader

# ============================================================
# CONFIGURATION
# ============================================================
PLAYER_NAMES = {
    'hero': 'Hero',
    'p1': 'Player1',
    'p2': 'Player2',
    'p3': 'Player3',
    'p4': 'Player4',
    'p5': 'Player5',
}

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'hands_db.jsonl')
POLL_INTERVAL = 0.5

# ============================================================
# POSITION DERIVATION
# ============================================================
SCREEN_SEATS = ['hero', 'p5', 'p4', 'p3', 'p2', 'p1']
SEAT_ORDER = ['BTN', 'SB', 'BB', 'UTG', 'MP', 'CO']
PLAYER_IDS = ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']

def get_position(player_id, btn_player):
    if btn_player is None or player_id not in SCREEN_SEATS:
        return None
    btn_idx = SCREEN_SEATS.index(btn_player)
    player_idx = SCREEN_SEATS.index(player_id)
    pos_idx = (player_idx - btn_idx) % len(SEAT_ORDER)
    return SEAT_ORDER[pos_idx]

# ============================================================
# HAND RECORDER
# ============================================================
class HandRecorder:
    def __init__(self):
        self.reader = StateReader()
        self.card_reader = CardReader()
        self.output_path = OUTPUT_PATH
        self.hand_id = 0
        self.hand = None
        self.last_state = None
        self.last_img = None
        self.street_bet = {}
        self.street_has_bet = False

    def capture(self):
        pil = ImageGrab.grab()
        img_arr = np.array(pil.convert('RGB'))
        state = self.reader.read_all(pil)
        cards = self.card_reader.read_all(img_arr)
        state['hero_cards'] = cards['hero']
        state['community'] = cards['community']
        return state, img_arr

    # ---------- helpers ----------

    def _any_bet(self, state):
        for p in PLAYER_IDS:
            b = state.get(f'{p}_bet')
            if b is not None and b > 0:
                return True
        return False

    def _bet_sum(self, state):
        total = 0.0
        for p in PLAYER_IDS:
            b = state.get(f'{p}_bet')
            if b is not None and b > 0:
                total += b
        return total

    def _visible_stacks(self, state):
        return sum(1 for p in PLAYER_IDS if state.get(f'{p}_stake') is not None)

    def _hero_cards_str(self, state):
        hc = state.get('hero_cards', [None, None])
        return f'{hc[0] or ""}{hc[1] or ""}'

    def _get_com_list(self, state):
        cards = state.get('community', [])
        result = []
        for c in cards[:5]:
            if c['rank'] and c['suit']:
                result.append(f'{c["rank"]}{c["suit"]}')
            else:
                result.append('')
        return result

    def _street_ended(self, state):
        """True if all bets disappeared compared to last_state"""
        if self.last_state is None:
            return False
        had = any(self.last_state.get(f'{p}_bet') not in (None, 0, 0.0) for p in PLAYER_IDS)
        has = any(state.get(f'{p}_bet') not in (None, 0, 0.0) for p in PLAYER_IDS)
        return had and not has

    # ---------- lifecycle ----------

    def hand_started(self, state):
        btn = state.get('btn')
        if btn is None:
            return False
        # If already tracking a hand, only start a new one if the button moved
        if self.hand is not None:
            old_btn = self.hand.get('btn_player')
            if old_btn and btn != old_btn:
                return True
            return False
        # First hand: need bets visible and a small pot
        if not self._any_bet(state):
            return False
        pot = state.get('pot') or state.get('pot_wide') or 0
        if pot is not None and pot > 10:
            return False
        return True

    def hand_ended(self, state, last_state):
        if self.hand is None:
            return False
        # Button moved to a different player → new hand dealt
        btn = state.get('btn')
        if btn and self.hand.get('btn_player') and btn != self.hand['btn_player']:
            return True
        # Gradual stack disappearance → players folding
        vis_now = self._visible_stacks(state)
        vis_before = self._visible_stacks(last_state)
        if vis_now <= 1 and vis_before > 1 and vis_before - vis_now <= 2:
            return True
        return False

    def start_hand(self, state):
        self.hand_id += 1
        btn_player = state.get('btn')
        btn_idx = SCREEN_SEATS.index(btn_player) if btn_player else None

        hand = {
            'hand_id': f'H_{self.hand_id:04d}',
            'date': datetime.datetime.now().isoformat(),
            'btn_idx': btn_idx,
            'btn_player': btn_player,
            'players': [],
            'comunitarias': {'flop': [], 'turn': [], 'river': []},
            'streets': {
                'preflop': {'actions': [], 'board': []},
                'flop': {'actions': [], 'board': []},
                'turn': {'actions': [], 'board': []},
                'river': {'actions': [], 'board': []},
            },
            'current_street': 'preflop',
            'max_pot': 0.0,
            'final_pot': 0,
            'showdown': {},
        }

        for pid in PLAYER_IDS:
            pos = get_position(pid, btn_player)
            stack = state.get(f'{pid}_stake')
            active = stack is not None
            cards = self._hero_cards_str(state) if pid == 'hero' else ''
            hand['players'].append({
                'active': active,
                'name': PLAYER_NAMES.get(pid, pid),
                'pos': pos,
                'stack': stack,
                'cards': cards,
                '_id': pid,
            })

        self.hand = hand
        self.last_state = state

        # Capture initial bets as preflop actions (sorted by position order)
        pos_order = {'SB': 0, 'BB': 1, 'UTG': 2, 'MP': 3, 'CO': 4, 'BTN': 5}
        initial_bets = []
        for pid in PLAYER_IDS:
            bet = state.get(f'{pid}_bet')
            pos = get_position(pid, btn_player)
            if bet is not None and bet > 0 and pos:
                initial_bets.append((pos_order.get(pos, 99), pid, pos, bet))
        initial_bets.sort()
        self.street_has_bet = False
        for _, pid, pos, bet in initial_bets:
            atype = 'b' if not self.street_has_bet else 'c'
            self.street_has_bet = True
            self.hand['streets']['preflop']['actions'].append({'pos': pos, 'action': atype, 'amount': bet})

        self.street_bet = {p: state.get(f'{p}_bet') for p in PLAYER_IDS}

    STATE_ACTIONS = {
        'retirarse': 'f',
        'igualar': 'c',
        'subir': 'r',
        'apostar': 'b',
        'pasar': 'c',
    }

    def detect_actions(self, state):
        if self.last_state is None:
            return []
        actions = []
        detected_players = set()

        # Suppress fold detection on frames where all bets disappear (street end)
        suppress_folds = self._street_ended(state)

        for pid in PLAYER_IDS:
            old_bet = self.last_state.get(f'{pid}_bet')
            new_bet = state.get(f'{pid}_bet')
            old_stack = self.last_state.get(f'{pid}_stake')
            new_stack = state.get(f'{pid}_stake')
            pos = get_position(pid, self.hand['btn_player'])

            # FOLD: stack disappears (not on street-end frames)
            if not suppress_folds and old_stack is not None and new_stack is None:
                actions.append({'pos': pos, 'action': 'f', 'amount': 0.0})
                detected_players.add(pid)
                continue

            # BET change
            if new_bet != old_bet:
                if old_bet is None and new_bet is not None:
                    atype = 'b' if not self.street_has_bet else 'c'
                    self.street_has_bet = True
                    actions.append({'pos': pos, 'action': atype, 'amount': new_bet})
                    detected_players.add(pid)
                elif old_bet is not None and new_bet is not None and new_bet > old_bet and old_bet > 0:
                    actions.append({'pos': pos, 'action': 'r', 'amount': new_bet})
                    self.street_has_bet = True
                    detected_players.add(pid)

        # STATE-BASED detection: green text changes (fallback for players not caught above)
        for pid in PLAYER_IDS:
            if pid in detected_players:
                continue
            old_state = self.last_state.get(f'{pid}_state')
            new_state = state.get(f'{pid}_state')
            pos = get_position(pid, self.hand['btn_player'])
            if pos is None:
                continue
            # State appeared: None → meaningful action
            if old_state is None and new_state and new_state.lower() in self.STATE_ACTIONS:
                atype = self.STATE_ACTIONS[new_state.lower()]
                if atype == 'f':
                    actions.append({'pos': pos, 'action': 'f', 'amount': 0.0})
                    detected_players.add(pid)
                elif atype == 'b':
                    self.street_has_bet = True
                    bet = state.get(f'{pid}_bet') or 0
                    actions.append({'pos': pos, 'action': 'b', 'amount': bet})
                    detected_players.add(pid)
                elif atype == 'r':
                    self.street_has_bet = True
                    bet = state.get(f'{pid}_bet') or 0
                    actions.append({'pos': pos, 'action': 'r', 'amount': bet})
                    detected_players.add(pid)
                elif atype == 'c':
                    bet = state.get(f'{pid}_bet') or 0
                    if bet > 0:
                        self.street_has_bet = True
                    actions.append({'pos': pos, 'action': 'c', 'amount': bet})
                    detected_players.add(pid)

        return actions

    def detect_street_change(self, state):
        if self.hand is None:
            return None
        cards = self._get_com_list(state)
        visible = [c for c in cards if c]
        cur = self.hand['current_street']
        if cur == 'preflop' and len(visible) >= 3:
            return 'flop'
        if cur == 'flop' and len(visible) >= 4:
            return 'turn'
        if cur == 'turn' and len(visible) >= 5:
            return 'river'
        return None

    def change_street(self, new_street, state):
        cards = self._get_com_list(state)
        visible = [c for c in cards if c]
        if new_street == 'flop':
            self.hand['comunitarias']['flop'] = visible[:3]
            self.hand['streets']['flop']['board'] = visible[:3]
        elif new_street == 'turn':
            self.hand['comunitarias']['turn'] = [visible[3]] if len(visible) > 3 else ['']
            self.hand['streets']['turn']['board'] = [visible[3]] if len(visible) > 3 else []
        elif new_street == 'river':
            self.hand['comunitarias']['river'] = [visible[4]] if len(visible) > 4 else ['']
            self.hand['streets']['river']['board'] = [visible[4]] if len(visible) > 4 else []
        self.hand['current_street'] = new_street
        self.street_bet = {p: None for p in PLAYER_IDS}
        self.street_has_bet = False

    def finalize_hand(self, state):
        pot = state.get('pot') or state.get('pot_wide')
        if pot is not None:
            self.hand['final_pot'] = max(self.hand.get('max_pot', 0), pot)
        else:
            self.hand['final_pot'] = self.hand.get('max_pot', 0)

        non_folded = [p for p in self.hand['players'] if p['active'] and
                      state.get(f'{p["_id"]}_stake') is not None and
                      state.get(f'{p["_id"]}_state') not in (None, 'retirarse')]
        if len(non_folded) == 1:
            self.hand['showdown'] = {'winner1': f'{non_folded[0]["pos"]} ({non_folded[0]["name"]})'}

        out = {k: v for k, v in self.hand.items() if k not in ('btn_player', 'current_street', 'max_pot')}
        for p in out['players']:
            del p['_id']

        with open(self.output_path, 'a') as f:
            f.write(json.dumps(out) + '\n')
        log = getattr(self, '_last_log', print)
        log(f'  -> Saved H_{self.hand_id:04d}')

        self.hand = None
        self.street_bet = {}
        self.street_has_bet = False

    # ---------- main loop ----------

    def run(self, stop_event=None, log_func=print):
        log = log_func or (lambda *a, **kw: None)
        self._last_log = log
        log('HandRecorder started — waiting for hand...')

        while True:
            if stop_event and stop_event.is_set():
                if self.hand is not None:
                    log('Saving current hand on stop...')
                    self.finalize_hand(self.last_state)
                log('Stopped.')
                break

            try:
                state, img_arr = self.capture()

                # Track max pot
                pot = state.get('pot') or state.get('pot_wide')
                if pot is not None and self.hand is not None:
                    self.hand['max_pot'] = max(self.hand.get('max_pot', 0), pot)

                if self.hand_started(state):
                    if self.hand is not None:
                        log(f'Hand {self.hand_id}: replaced by new hand')
                        self.finalize_hand(state)
                    self.start_hand(state)
                    log(f'H_{self.hand_id:04d}: started')

                elif self.hand is not None:
                    actions = self.detect_actions(state)
                    for a in actions:
                        self.hand['streets'][self.hand['current_street']]['actions'].append(a)
                        log(f'  {self.hand["current_street"]}: {a["pos"]} {a["action"]} {a["amount"]}')

                    ns = self.detect_street_change(state)
                    if ns:
                        log(f'  >> {ns}')
                        self.change_street(ns, state)

                    if self.hand_ended(state, self.last_state):
                        log(f'H_{self.hand_id:04d}: ended')
                        self.finalize_hand(state)

                self.last_state = state
                self.last_img = img_arr
                time.sleep(POLL_INTERVAL)

            except KeyboardInterrupt:
                if self.hand is not None:
                    log('Saving current hand on exit...')
                    self.finalize_hand(self.last_state)
                log('Stopped.')
                break

# ============================================================
if __name__ == '__main__':
    hr = HandRecorder()
    hr.run()
