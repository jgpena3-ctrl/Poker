"""
recorder_live.py — Live poker hand recorder v3

Usa capture_live.capture() para obtener el estado de la mesa
(lectores inicializados una sola vez) y se encarga de la lógica
del juego: detección de manos nuevas, asignación de posiciones,
seguimiento de acciones con compensación de lag entre frames,
cambios de calle y guardado en JSONL.

Usage:  python recorder_live.py
        (o desde poker_recorder_gui.py)
"""
import json, os, time, datetime
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from capture_live import capture as _capture

PLAYER_NAMES = {
    'hero': 'Hero',
    'p1': 'Player1',
    'p2': 'Player2',
    'p3': 'Player3',
    'p4': 'Player4',
    'p5': 'Player5',
}

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'hands_db.jsonl')
POLL_INTERVAL = 0.0

SCREEN_SEATS = ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']
POSITION_ORDER = ['BTN', 'SB', 'BB', 'CO', 'MP', 'UTG']
PLAYER_IDS = ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']
NULL_STATES = {'retirarse', 'ausente', 'inactivo', 'sin jugador', 'fuera'}
MANUAL_CARDS = {}    # pid -> card_str override from GUI
MANUAL_WINNER = None  # None = auto-detect, or list of pids e.g. ['p2', 'p3']
MANUAL_INACTIVE = set()    # set of pids marked inactive from GUI
MANUAL_POSITIONS = {}      # pid -> position override from GUI (e.g. {'hero': 'BTN'})
STATE_ACTIONS = {'retirarse': 'f', 'igualar': 'c', 'subir': 'r', 'apostar': 'b', 'apostar todo': 'b', 'pasar': 'x', 'mostrar cartas': 'c'}


class LiveRecorder:
    def __init__(self):
        self.output_path = OUTPUT_PATH
        self.hand_id = None
        self.hand = None
        self.last_state = None
        self.last_img = None
        self.street_has_bet = False
        self._inactive_players = set()
        self._allin_players = set()
        self._stake_history = {}
        self._initial_stakes = {}
        self._hand_positions = None
        self._folded_positions = set()
        self.on_hand_saved = None

    def _last_hand_id(self, path):
        """Lee el último hand_id del archivo de salida para continuar la numeración."""
        if not os.path.exists(path):
            return 0
        try:
            with open(path) as f:
                last = None
                for line in f:
                    line = line.strip()
                    if line:
                        last = line
                if last:
                    import re
                    m = re.search(r'"hand_id"\s*:\s*"H_(\d+)"', last)
                    if m:
                        return int(m.group(1))
        except Exception:
            pass
        return 0

    def _ensure_hand_id(self):
        if self.hand_id is None:
            self.hand_id = self._last_hand_id(self.output_path)

    # ---------- capture (delegada a capture_live) ----------

    def capture(self):
        return _capture()

    # ---------- helpers ----------

    def _any_bet(self, state):
        return any(state.get(f'{p}_bet') not in (None, 0, 0.0) for p in PLAYER_IDS)

    def _get_active(self, state):
        return [p for p in PLAYER_IDS if state.get(f'{p}_state') not in NULL_STATES and p not in self._inactive_players]

    def _get_seated(self, state):
        """Jugadores con asiento (excluye sillas vacías)."""
        return [p for p in PLAYER_IDS if state.get(f'{p}_state') not in ('sin jugador', 'fuera', 'inactivo')]


    def _visible_stacks(self, state):
        """Jugadores con stack visible, bet>0 o all-in."""
        return sum(1 for p in PLAYER_IDS
                   if state.get(f'{p}_stake') is not None
                   or (state.get(f'{p}_bet') or 0) > 0
                   or p in self._allin_players)

    def _get_com_list(self, state):
        cards = state.get('community', [])
        return [(f'{c["rank"]}{c["suit"]}' if c and c.get('rank') and c.get('suit') else '')
                for c in cards[:5]]

    def _visible_coms(self, state):
        return sum(1 for c in self._get_com_list(state) if c)

    # ---------- posición (desde BTN en sentido horario, saltando inactivos) ----------

    def _assign_positions(self, state):
        btn = state.get('btn')
        if btn is None or btn not in SCREEN_SEATS:
            return {}
        seated = self._get_seated(state)
        # Skip manual inactives for position assignment (except BTN itself)
        active = [p for p in seated if p not in MANUAL_INACTIVE or p == btn]
        n = len(SCREEN_SEATS)
        positions = {}
        btn_idx = SCREEN_SEATS.index(btn)
        positions[btn] = 'BTN'

        # Sentido horario desde BTN: SB, BB (como hasta ahora)
        cur = (btn_idx + 1) % n
        for pos in ['SB', 'BB']:
            for _ in range(n):
                p = SCREEN_SEATS[cur]
                if p in active and p not in positions:
                    positions[p] = pos
                    cur = (cur + 1) % n
                    break
                cur = (cur + 1) % n

        # Sentido antihorario desde el más próximo a BTN: CO, MP, UTG
        # (el sobrante desaparece desde UTG si hay inactivos)
        cur = (btn_idx - 1) % n
        for pos in ['CO', 'MP', 'UTG']:
            for _ in range(n):
                p = SCREEN_SEATS[cur]
                if p in active and p not in positions:
                    positions[p] = pos
                    cur = (cur - 1) % n
                    break
                cur = (cur - 1) % n
        # Aplicar posiciones manuales del GUI
        for pid, pos in MANUAL_POSITIONS.items():
            if pos:
                positions[pid] = pos
        return positions

    # ---------- ciclo de vida de la mano ----------

    def _can_start_hand(self, state, log=print):
        btn = state.get('btn')
        if btn is None or btn not in SCREEN_SEATS:
            log(f'  [can_start] FAIL: btn={btn}')
            return False
        stakes = [state.get(f'{p}_stake') for p in PLAYER_IDS]
        vis = sum(1 for s in stakes if s is not None)
        if vis < 2:
            log(f'  [can_start] FAIL: only {vis} visible stacks')
            return False
        log(f'  [can_start] OK btn={btn} vis={vis}')
        return True

    def _is_new_hand(self, state):
        if self.hand is None:
            return self._can_start_hand(state)
        prev_btn = self.last_state.get('btn') if self.last_state else None
        curr_btn = state.get('btn')
        if prev_btn is None or curr_btn is None or prev_btn == curr_btn:
            return False
        if self._visible_coms(state) >= 2:
            return False
        states = [state.get(f'{p}_state') for p in PLAYER_IDS]
        if 'SB' not in states and 'BB' not in states:
            return False
        return True

    def _is_hand_over(self, state):
        if self.hand is None:
            return False
        btn = state.get('btn')
        if btn and self.hand.get('btn_player') and btn != self.hand['btn_player']:
            return True
        # Solo finalizar en automático cuando TODOS menos 1 han recibido un
        # fold real ('retirarse'/'ausente' o fold ya registrado). NO cuentan
        # 'inactivo'/'sin jugador'/'fuera' (sillas vacías o transición de
        # pantalla): un check/check o bet/call en curso mantiene la mano viva.
        # Los all-in cuentan como jugador en juego (nunca se descuentan).
        still_in = 0
        for p in self.hand['players']:
            pid = p['_id']
            if not p['active']:
                continue  # silla que nunca entró en la mano
            if pid in self._allin_players:
                still_in += 1
                continue
            if pid in self._inactive_players or p['pos'] in self._folded_positions:
                continue  # fold registrado (o inactivo manual del GUI)
            st = state.get(f'{pid}_state')
            if st in ('retirarse', 'ausente'):
                continue  # fold real visto en este frame
            still_in += 1
        return still_in <= 1

    def start_hand(self, state):
        self._ensure_hand_id()
        self.hand_id += 1
        btn_player = state.get('btn')
        btn_idx = SCREEN_SEATS.index(btn_player) if btn_player else -1
        positions = self._assign_positions(state)
        self._hand_positions = positions

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
            stake = state.get(f'{pid}_stake')
            bet = state.get(f'{pid}_bet')
            stack = (stake + bet) if (stake is not None and bet is not None) else stake
            cards = MANUAL_CARDS.get(pid) or self._cards_str(state, pid)
            hand['players'].append({
                'active': stake is not None,
                'name': PLAYER_NAMES.get(pid, pid),
                'pos': positions.get(pid, ''),
                'stack': stack,
                'cards': cards,
                '_id': pid,
            })

        self._inactive_players = set()
        self._allin_players = set()
        self._folded_positions = set()
        self._stake_history = {}
        self._initial_stakes = {}
        for pid in PLAYER_IDS:
            self._initial_stakes[pid] = state.get(f'{pid}_stake')

        self.hand = hand
        self.last_state = state
        self.street_has_bet = False

        self._reconstruct_preflop(state)

    def _assign_cards_by_name(self, state):
        """Reasigna state['hero_cards'] al pid cuyo nombre sea 'Jarduan'
           (o a 'hero' si no se encuentra). Borra la original si cambió de dueño."""
        cards = state.get('hero_cards')
        if not cards:
            return
        target_pid = 'hero'
        for pid in PLAYER_IDS:
            if PLAYER_NAMES.get(pid, '').lower() == 'jarduan':
                target_pid = pid
                break
        if target_pid != 'hero':
            del state['hero_cards']
        state[f'{target_pid}_cards'] = cards

    def _cards_str(self, state, pid):
        hc = state.get(f'{pid}_cards', None)
        if hc is not None:
            parts = []
            for c in hc:
                if c and isinstance(c, dict):
                    parts.append(f'{c.get("rank", "")}{c.get("suit", "")}')
                elif c:
                    parts.append(str(c))
            return ''.join(parts)
        return ''

    def _get_pos_map(self, state=None):
        """{position_name: pid, ...} — usa posiciones fijas si hay mano activa."""
        if self._hand_positions is not None:
            return {v: k for k, v in self._hand_positions.items()}
        if state is None:
            return {}
        by_pid = self._assign_positions(state)
        return {v: k for k, v in by_pid.items()}

    def _get_pid_map(self, state=None):
        """{pid: position_name, ...} — usa posiciones fijas si hay mano activa."""
        if self._hand_positions is not None:
            return self._hand_positions
        if state is None:
            return {}
        return self._assign_positions(state)

    def _reconstruct_preflop(self, state):
        """Reconstruye acciones preflop desde state labels (frame 0).
           Las ciegas (sin label, solo bet visible) no se registran como
           acciones separadas — se acumulan en _blinds_by_pos para agregar
           al primer movimiento voluntario de ese jugador."""
        PREFLOP_ORDER = ['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB']
        pos_map = self._get_pos_map(state)
        street_has_bet = False
        max_bet = 0.0
        self._blinds_by_pos = {}

        for pos_name in PREFLOP_ORDER:
            pid = pos_map.get(pos_name)
            if pid is None:
                continue
            label = state.get(f'{pid}_state')
            bet = state.get(f'{pid}_bet')

            if label == 'retirarse' or label == 'ausente':
                self._add_action('preflop', pos_name, 'f', 0.0)
            elif label in ('subir', 'apostar', 'apostar todo'):
                atype = 'b' if not street_has_bet else 'r'
                amt = bet or 0.0
                self._add_action('preflop', pos_name, atype, amt)
                street_has_bet = True
                max_bet = max(max_bet, amt)
                # Detectar all-in
                if label == 'apostar todo':
                    self._allin_players.add(pid)
                else:
                    init = self._initial_stakes.get(pid)
                    if init is not None and amt >= init - 0.01:
                        self._allin_players.add(pid)
            elif label == 'igualar':
                amt = bet or 0.0
                self._add_action('preflop', pos_name, 'c', amt)
                street_has_bet = True
            elif label == 'pasar':
                self._add_action('preflop', pos_name, 'x', 0.0)
            elif label is None and bet is not None and bet > 0:
                # Ciega (sin label): no se registra como acci&oacute;n,
                # se guarda para sumar al primer movimiento voluntario.
                self._blinds_by_pos[pos_name] = bet
                street_has_bet = True
                max_bet = max(max_bet, bet)
            elif label is None and bet is None:
                pass  # no action visible yet

        self.street_has_bet = street_has_bet
        self._preflop_current_bet = max_bet

    def _add_action(self, street, pos, action, amount):
        if self.hand is None:
            return
        # Si hay ciega pendiente para esta posici&oacute;n, sumarla al monto
        if pos in self._blinds_by_pos:
            amount += self._blinds_by_pos.pop(pos)
        self.hand['streets'][street]['actions'].append({
            'pos': pos, 'action': action, 'amount': round(amount, 2)
        })
        if action == 'f':
            self._folded_positions.add(pos)

    # ---------- detección de acciones ----------

    def _get_street_order(self, state, street_name):
        if street_name == 'preflop':
            return ['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB']
        return ['SB', 'BB', 'UTG', 'MP', 'CO', 'BTN']

    def _active_ids(self, state):
        return [p for p in PLAYER_IDS
                if state.get(f'{p}_stake') is not None
                and state.get(f'{p}_state') not in NULL_STATES
                and p not in self._inactive_players]

    def _mark_inactive(self, pid, pos_name):
        """Marca a pid como inactivo y purga sus acciones de todas las calles."""
        self._inactive_players.add(pid)
        if self.hand is not None:
            for street_data in self.hand['streets'].values():
                street_data['actions'] = [a for a in street_data['actions']
                                          if a.get('pos') != pos_name]

    def _detect_inactive(self, state):
        """Solo inactivos manuales del GUI — detección automática deshabilitada."""
        if self.hand is None:
            return
        pid_map = self._get_pid_map(state)
        for pid in MANUAL_INACTIVE:
            if pid not in self._inactive_players:
                pos_name = pid_map.get(pid)
                self._mark_inactive(pid, pos_name)

    def _process_folds_and_lag(self, state):
        """Detecta folds y lag (stake decrease) entre last_state y state.
           Itera en orden de poker y retorna acciones a insertar."""
        if self.last_state is None or self.hand is None:
            return []
        street = self.hand['current_street']
        order = self._get_street_order(state, street)
        pos_map = self._get_pos_map(state)  # position → pid
        actions = []

        old_pot = self.last_state.get('pot') or 0
        new_pot = state.get('pot') or 0
        hand_ending = old_pot > 0 and new_pot == 0

        for pos_name in order:
            pid = pos_map.get(pos_name)
            if pid is None or pid in self._inactive_players:
                continue
            if pos_name in self._folded_positions:
                continue  # fold ya registrado: la insignia 'retirarse' persiste
                         # entre calles y no debe repetirse
            if pid in self._allin_players:
                continue  # all-in players don't fold or have further actions
            old_stake = self.last_state.get(f'{pid}_stake')
            new_stake = state.get(f'{pid}_stake')
            new_st = state.get(f'{pid}_state')
            new_bet = state.get(f'{pid}_bet')

            was_active = old_stake is not None
            now_active = new_stake is not None and new_st not in NULL_STATES

            # Fold o all-in call
            if was_active and not now_active:
                # Etiqueta de acción visible (igualar, subir, apostar, etc.) →
                # lo procesa process_street_labels
                if new_st in STATE_ACTIONS and new_st != 'retirarse':
                    continue
                # Estado None (OCR no leyó label) → podría ser all-in call
                if new_st is None:
                    if pid not in self._allin_players:
                        mb = self._get_max_bet(street)
                        if mb > 0 and (old_stake or 0) > 0:
                            diff = round(old_stake or 0, 2)
                            if diff > 0.01:
                                prior_total = 0.0
                                for a in self.hand['streets'][street]['actions']:
                                    if a['pos'] == pos_name and a['action'] not in ('f', 'x'):
                                        prior_total = a['amount']
                                        break
                                amt = round(diff + prior_total, 2)
                                atype = 'r' if amt > mb else 'c'
                                duplicate = any(
                                    ea['pos'] == pos_name
                                    and abs(ea['amount'] - amt) < 0.3
                                    for ea in self.hand['streets'][street]['actions']
                                )
                                if not duplicate:
                                    actions.append((street, pos_name, atype, round(amt, 2)))
                                    self._allin_players.add(pid)
                    continue  # None nunca es fold
                # Solo 'retirarse'/'ausente' es un fold real
                if new_st in ('retirarse', 'ausente'):
                    if not hand_ending:
                        has_fold_already = any(a['pos'] == pos_name and a['action'] == 'f'
                                                for a in self.hand['streets'][street]['actions'])
                        if not has_fold_already:
                            actions.append((street, pos_name, 'f', 0.0))
                    continue

            # Lag: stake decrease sin label visible (label a�n no aparece)
            if was_active and now_active and new_st is None:
                old_bet = self.last_state.get(f'{pid}_bet') or 0
                new_bet_val = new_bet or 0
                old_stake_val = old_stake or 0
                new_stake_val = new_stake or 0
                if new_stake_val + 0.01 < old_stake_val:
                    diff = round(old_stake_val - new_stake_val, 2)
                    if diff >= 0.25:
                        # Cumulative total (sum of prior actions + this diff)
                        prior_total = 0.0
                        for a in self.hand['streets'][street]['actions']:
                            if a['pos'] == pos_name and a['action'] not in ('f', 'x'):
                                prior_total = a['amount']
                                break
                        amt = round(diff + prior_total, 2)
                        max_bet = self._get_max_bet(street)
                        atype = 'r' if amt > max_bet else 'c'
                        actions.append((street, pos_name, atype, round(amt, 2)))

        return actions

    def _get_max_bet(self, street_name):
        max_amt = getattr(self, '_preflop_current_bet', 0.0) if street_name == 'preflop' else 0.0
        for a in self.hand['streets'][street_name]['actions']:
            if a['action'] in ('b', 'r'):
                max_amt = max(max_amt, a['amount'])
        return max_amt

    def _process_labels(self, state, street_name):
        """Procesa state labels de la frame actual para la calle dada."""
        pos_map = self._get_pos_map(state)
        action_order = self._get_street_order(state, street_name)
        street_actions = self.hand['streets'][street_name].setdefault('actions', [])
        street_has_bet = self.street_has_bet
        max_bet = self._get_max_bet(street_name)

        new_actions = []

        for pos_name in action_order:
            pid = pos_map.get(pos_name)
            if pid is None or pid in self._inactive_players:
                continue
            stake = state.get(f'{pid}_stake')
            label = state.get(f'{pid}_state')
            bet = state.get(f'{pid}_bet')
            if stake is None:
                # Permitir all-in con label visible (stake=0, bet>0)
                if not (label in STATE_ACTIONS and (bet or 0) > 0):
                    continue

            if label is None or label.lower() not in STATE_ACTIONS:
                continue
            if label == 'retirarse':
                continue  # folds handled by _process_folds_and_lag / _reconstruct_preflop
            if pid in self._allin_players:
                continue  # already all-in, action already recorded

            # Showdown: 'mostrar cartas' — detect pending payment via stake decrease
            if label == 'mostrar cartas':
                if self.last_state and stake is not None:
                    old_stake = self.last_state.get(f'{pid}_stake')
                    if old_stake is not None and stake + 0.01 < old_stake:
                        diff = round(old_stake - stake, 2)
                        prior_total = 0.0
                        for a in street_actions:
                            if a['pos'] == pos_name and a['action'] not in ('f', 'x'):
                                prior_total = a['amount']
                                break
                        amt = round(diff + prior_total, 2)
                        mb = self._get_max_bet(street_name)
                        atype = 'r' if amt > mb else 'c'
                        duplicate = any(
                            ea['pos'] == pos_name
                            and abs(ea['amount'] - amt) < 0.3
                            for ea in street_actions
                        )
                        if not duplicate and amt > 0.01:
                            new_actions.append((pos_name, atype, amt))
                            if atype in ('b', 'r'):
                                street_has_bet = True
                            if state.get(f'{pid}_stake') is None or (stake is not None and stake < 0.01):
                                self._allin_players.add(pid)
                continue  # skip normal action processing for showdown

            action = STATE_ACTIONS[label.lower()]
            raw_amt = round(bet or 0, 2) if action in ('b', 'r', 'c') else 0.0
            # Subtract pending blind from raw amount (blind added by _add_action)
            if pos_name in self._blinds_by_pos:
                raw_amt = max(0.0, round(raw_amt - self._blinds_by_pos[pos_name], 2))

            # Determine actual action type from context (like _reconstruct_preflop)
            if action in ('f', 'x'):
                atype, amt = action, 0.0
            elif action == 'c':
                atype, amt = 'c', raw_amt
                # Call-0: UI ya borró el monto — usar max_bet si hay apuesta activa
                if amt < 0.01 and street_has_bet and max_bet > 0:
                    amt = max_bet
                    if pos_name in self._blinds_by_pos:
                        amt = max(0.0, round(amt - self._blinds_by_pos[pos_name], 2))
                # Call fantasma: etiqueta 'igualar' persistió de calle anterior
                elif amt < 0.01 and not street_has_bet:
                    continue
            else:  # 'b', 'r' — use street context for bet vs raise
                amt = raw_amt
                atype = 'b' if not street_has_bet else ('r' if amt > max_bet else 'c')

            # Amount-tolerance dedup: skip if same (pos, ~amount) already recorded.
            # A player can never have two different actions with the same amount on one street.
            duplicate = any(
                ea['pos'] == pos_name
                and abs(ea['amount'] - amt) < 0.3
                for ea in street_actions
            )
            if duplicate:
                continue

            new_actions.append((pos_name, atype, amt))
            if atype in ('b', 'r'):
                street_has_bet = True
                max_bet = max(max_bet, amt)
            # Track all-in: apostar todo or bet consumes entire remaining stake
            if label == 'apostar todo':
                self._allin_players.add(pid)
            elif atype in ('b', 'r', 'c') and state.get(f'{pid}_stake') is None and (bet or 0) > 0:
                self._allin_players.add(pid)

        # Implied checks for players with stake but no bet/label before first bet
        first_bet_idx = next((i for i, (_, a, _) in enumerate(new_actions) if a in ('b', 'r')), None)
        if first_bet_idx is not None:
            first_bet_pos = new_actions[first_bet_idx][0]
            before = []
            for pos_name in action_order:
                # Stop at the first bettor: only positions before the bettor may have checked
                if pos_name == first_bet_pos:
                    break
                pid = pos_map.get(pos_name)
                if pid is None or pid in self._inactive_players:
                    continue
                if pos_name in self._folded_positions:
                    continue  # folded earlier in the hand: no implied actions
                if state.get(f'{pid}_stake') is None:
                    continue
                # Skip positions that already posted a blind (not a voluntary action)
                if pos_name in self._blinds_by_pos:
                    continue
                had_bet = (state.get(f'{pid}_bet') or 0) > 0
                had_label = state.get(f'{pid}_state') is not None
                if had_bet or had_label:
                    continue
                if not any(a['pos'] == pos_name and a['action'] == 'x' for a in street_actions):
                    before.append((pos_name, 'x', 0.0))
            for item in reversed(before):
                new_actions.insert(first_bet_idx, item)

        # Implied checks for folded players (check then fold) — solo postflop
        if first_bet_idx is not None and street_name != 'preflop':
            for pos_name in action_order:
                pid = pos_map.get(pos_name)
                if pid is None or pid in self._inactive_players:
                    continue
                if state.get(f'{pid}_stake') is not None:
                    continue  # still active
                has_fold = any(a['pos'] == pos_name and a['action'] == 'f' for a in street_actions)
                if not has_fold:
                    continue
                has_x = any(a['pos'] == pos_name and a['action'] == 'x' for a in street_actions)
                if has_x:
                    continue
                old_stake = self.last_state.get(f'{pid}_stake') if self.last_state else None
                if old_stake is not None:
                    new_actions.insert(first_bet_idx, (pos_name, 'x', 0.0))
                    first_bet_idx += 1

        for pos, act, amt in new_actions:
            self._add_action(street_name, pos, act, amt)

        self.street_has_bet = street_has_bet

    def detect_actions(self, state):
        """Detecta folds y lag entre last_state y state."""
        if self.last_state is None or self.hand is None:
            return []
        actions = self._process_folds_and_lag(state)
        for s, pos, a, amt in actions:
            self._add_action(s, pos, a, amt)
        return actions

    def process_street_labels(self, state, street_name):
        """Procesa labels del state para la calle street_name (llamar tras detect_actions)."""
        self._process_labels(state, street_name)

    # ---------- calles ----------

    def detect_street_change(self, state):
        if self.hand is None:
            return None
        visible = self._visible_coms(state)
        cur = self.hand['current_street']
        if cur == 'preflop' and visible >= 3:
            return 'flop'
        if cur == 'flop' and visible >= 4:
            return 'turn'
        if cur == 'turn' and visible >= 5:
            return 'river'
        return None

    def change_street(self, new_street, state):
        cards = self._get_com_list(state)
        visible = [c for c in cards if c]
        if new_street == 'flop':
            self.hand['comunitarias']['flop'] = visible[:3]
            self.hand['streets']['flop']['board'] = visible[:3]
        elif new_street == 'turn':
            self.hand['comunitarias']['turn'] = [visible[3]]
            self.hand['streets']['turn']['board'] = [visible[3]]
        elif new_street == 'river':
            self.hand['comunitarias']['river'] = [visible[4]]
            self.hand['streets']['river']['board'] = [visible[4]]
        self._finalize_street(self.hand['current_street'], state)
        self.hand['current_street'] = new_street
        self.street_has_bet = False

    def _finalize_street(self, street_name, state=None):
        # Add implied checks first (modifies the list in place via re-assign)
        if state is not None:
            self._add_implied_checks(street_name, state)

        actions = self.hand['streets'][street_name].setdefault('actions', [])
        if not actions:
            return

        ORDER = self._get_street_order(None, street_name)
        pos_ord = {p: i for i, p in enumerate(ORDER)}

        # Merge consecutive same-position actions
        merged = []
        for a in actions:
            if merged and merged[-1]['pos'] == a['pos'] and a['action'] in ('c', 'b'):
                merged[-1]['amount'] = round(merged[-1]['amount'] + a['amount'], 2)
            else:
                merged.append(dict(a))
        actions[:] = merged

        if not actions:
            return

        checks = [a for a in actions if a['action'] == 'x']
        non_checks = [a for a in actions if a['action'] != 'x']

        bettor_pos = None
        for a in non_checks:
            if a['action'] in ('b', 'r'):
                bettor_pos = a['pos']
                break

        checks.sort(key=lambda a: pos_ord.get(a['pos'], 99))

        if bettor_pos is None:
            if street_name == 'preflop':
                actions[:] = non_checks + checks
            else:
                actions[:] = checks + non_checks
            return

        # Preflop: el primer en hablar es siempre UTG
        if street_name == 'preflop':
            bettor_pos = 'UTG'
        bettor_idx = ORDER.index(bettor_pos)
        n = len(ORDER)
        used = set()
        ordered = []

        # Multi-pass: una acci&oacute;n por posici&oacute;n por pasada (soporta multi-ronda)
        remaining = len(non_checks)
        while remaining > 0:
            prev_remaining = remaining
            for i in range(n):
                idx = (bettor_idx + i) % n
                pos = ORDER[idx]
                for a in non_checks:
                    if a['pos'] == pos and id(a) not in used:
                        ordered.append(a)
                        used.add(id(a))
                        remaining -= 1
                        break
            if remaining == prev_remaining:
                for a in non_checks:
                    if id(a) not in used:
                        ordered.append(a)
                        used.add(id(a))
                        remaining -= 1
                break
            if remaining == 0:
                break

        if street_name == 'preflop':
            actions[:] = ordered + checks
        else:
            actions[:] = checks + ordered

    def _add_implied_checks(self, street_name, state):
        """Agrega checks implícitos a la calle para jugadores activos sin acción registrada.
        Si ya hay una apuesta en la calle, no se agregan (los que faltan deben responder)."""
        existing = self.hand['streets'][street_name].setdefault('actions', [])
        existing_pos = {a['pos'] for a in existing}
        has_bet = any(a['action'] in ('b', 'r') for a in existing)
        if has_bet:
            return
        pos_map = self._get_pos_map(state)
        ORDER = self._get_street_order(None, street_name)
        checks = []
        for pos in ORDER:
            pid = pos_map.get(pos)
            if pid and state.get(f'{pid}_stake') is not None and pos not in existing_pos and pid not in self._inactive_players and pos not in self._folded_positions:
                checks.append({'pos': pos, 'action': 'x', 'amount': 0.0})
        if checks:
            if street_name == 'preflop':
                existing.extend(checks)
            else:
                existing[0:0] = checks

    # ---------- finalizar mano ----------

    def finalize_hand(self, state):
        self._finalize_street(self.hand['current_street'], state)
        pot = state.get('pot')
        if pot and pot > 0:
            self.hand['final_pot'] = pot
        else:
            self.hand['final_pot'] = self.hand.get('max_pot', 0)

        if MANUAL_WINNER is not None:
            self.hand['winner'] = MANUAL_WINNER
            non_folded = [p for p in self.hand['players'] if p['_id'] in MANUAL_WINNER]
            if len(non_folded) == 1:
                self.hand['showdown'] = {
                    'winner1': f'{non_folded[0]["pos"]} ({non_folded[0]["name"]})'
                }
        else:
            # Ganadores: jugadores con stake activo, no retirarse, o all-in
            all_still_in = [p for p in self.hand['players']
                            if p['active'] and p['_id'] not in self._inactive_players
                            and state.get(f'{p["_id"]}_state') not in ('retirarse', 'ausente')]
            with_stake = [p for p in all_still_in
                          if state.get(f'{p["_id"]}_stake') is not None]
            non_folded = [p for p in with_stake if
                          state.get(f'{p["_id"]}_state') not in (None, 'retirarse', 'ausente')]
            # Include all-in players who have no stake but are tracked as all-in
            allin_here = [p for p in all_still_in
                          if p['_id'] in self._allin_players
                          and p['_id'] not in [x['_id'] for x in non_folded]]
            non_folded.extend(allin_here)
            # Si solo hay uno con stake pero su estado es None, igual es ganador
            if not non_folded and len(with_stake) == 1:
                non_folded = with_stake
            if non_folded:
                self.hand['winner'] = [p['_id'] for p in non_folded]
                if len(non_folded) == 1:
                    self.hand['showdown'] = {
                        'winner1': f'{non_folded[0]["pos"]} ({non_folded[0]["name"]})'
                    }
            else:
                self.hand['winner'] = []

        out = {k: v for k, v in self.hand.items()
               if k not in ('current_street', 'max_pot')}
        out['allin'] = [p['_id'] for p in self.hand['players']
                        if p['_id'] in self._allin_players and p['active']]
        for p in out['players']:
            del p['_id']

        with open(self.output_path, 'a') as f:
            f.write(json.dumps(out) + '\n')

        log = getattr(self, '_last_log', print)
        log(f'  -> Saved H_{self.hand_id:04d}')
        if self.on_hand_saved is not None:
            self.on_hand_saved()
        self.hand = None
        self.street_has_bet = False

    def _is_effectively_over(self, state):
        """True si hay all-in y solo 1 jugador no-allin puede actuar (o ninguno)."""
        if self.hand is None or not self._allin_players:
            return False
        active = [p for p in PLAYER_IDS
                  if state.get(f'{p}_stake') is not None
                  and state.get(f'{p}_state') not in NULL_STATES]
        non_allin_active = [p for p in active if p not in self._allin_players]
        return len(non_allin_active) == 0

    # ---------- procesar un frame (usado por run y por captura manual) ----------

    def process_frame(self, state, img_arr, log=print):
        pot = state.get('pot')
        if pot is not None and self.hand is not None:
            self.hand['max_pot'] = max(self.hand.get('max_pot', 0), pot)

        if self.hand is None and not self._can_start_hand(state, log=log):
            self.last_state = state
            self.last_img = img_arr
            return

        if self._is_new_hand(state):
            if self.hand is not None:
                log(f'H_{self.hand_id:04d}: replaced by new hand')
                self.finalize_hand(self.last_state)
            self._assign_cards_by_name(state)
            self.start_hand(state)
            log(f'H_{self.hand_id:04d}: started')
            for a in self.hand['streets']['preflop']['actions']:
                log(f'  preflop: {a["pos"]} {a["action"]} {a["amount"]}')

        if self.hand is not None:
            # Aplicar inactivos manuales del GUI (inmediatamente, cualquier calle)
            pid_map_cur = self._get_pid_map(state)
            for pid in MANUAL_INACTIVE:
                if pid not in self._inactive_players:
                    pos_name = pid_map_cur.get(pid)
                    self._mark_inactive(pid, pos_name)

            # 0. Detectar jugadores inactivos antes de procesar acciones
            self._detect_inactive(state)

            cur = self.hand['current_street']
            ns = self.detect_street_change(state)

            # 1. Detect folds/lag between frames — skip when effectively over
            if not self._is_effectively_over(state):
                actions = self.detect_actions(state)
                for a in actions:
                    log(f'  {cur}: {a[1]} {a[2]} {a[3]}')

                # 2. Process labels for CURRENT street BEFORE change
                self.process_street_labels(state, cur)
            elif ns:
                log('  (all-in: no actions)')

            # 3. If street changed, finalize old street and process new
            if ns:
                log(f'  >> {ns}')
                self.change_street(ns, state)
                if not self._is_effectively_over(state):
                    self.process_street_labels(state, ns)
                else:
                    log('  (all-in: no actions)')

            # 4. Check hand over (finalizar con el último frame de la mano vieja)
            if self._is_hand_over(state):
                log(f'H_{self.hand_id:04d}: ended')
                self.finalize_hand(self.last_state or state)

        if self.hand is not None:
            cur = self.hand['current_street']
            n = len(self.hand['streets'][cur]['actions'])
            log(f'  -> H_{self.hand_id:04d} | {cur} | {n} actions')

        self.last_state = state
        self.last_img = img_arr

    # ---------- bucle principal ----------

    def run(self, stop_event=None, log_func=print):
        log = log_func or (lambda *a, **kw: None)
        self._last_log = log
        log('LiveRecorder started — waiting for hand...')
        self._last_bet = 0.0

        while True:
            if stop_event and stop_event.is_set():
                if self.hand is not None:
                    log('Saving current hand on stop...')
                    self.finalize_hand(self.last_state)
                log('Stopped.')
                break

            try:
                state, img_arr, pil = self.capture()
                self.process_frame(state, img_arr, log=log)
                time.sleep(POLL_INTERVAL)

            except KeyboardInterrupt:
                if self.hand is not None and self.last_state is not None:
                    log('Saving current hand on exit...')
                    self.finalize_hand(self.last_state)
                log('Stopped.')
                break


if __name__ == '__main__':
    hr = LiveRecorder()
    hr.run()
