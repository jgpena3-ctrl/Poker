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
        # Ciegas detectadas desde los bets (BB tamaño unidad, SB = 0.5×)
        self._blind_sb = 0.5
        self._blind_bb = 1.0
        self._blinds_by_pos = {}
        # Conteo de frames sin cambios en river (detección de check general)
        self._river_stable_count = 0
        self._last_state_sig = None

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
        """Jugadores con asiento en la mesa.

        El OCR 'inactivo' NO excluye: si el usuario no marcó al jugador como
        inactivo (MANUAL_INACTIVE), ese asiento jugó la mano. Al iniciar
        recibirá posición y, si su estado es 'inactivo', se registrará su fold
        en preflop. Solo las sillas vacías ('sin jugador'/'fuera') quedan
        fuera; quién "no jugó la mano" lo declara el usuario, no el estado."""
        return [p for p in PLAYER_IDS if state.get(f'{p}_state') not in ('sin jugador', 'fuera')]


    # ---------- utilidades de monto/ciegas ----------

    @staticmethod
    def _near(a, b, tol=0.15):
        """True si a y b coinciden (los valores pueden variar por redondeo)."""
        if a is None or b is None:
            return False
        return abs(a - b) <= tol

    def _round_bet(self, amount, max_bet):
        """Ajusta el monto detectado a la lógica de apuestas: si la diferencia
        con el monto objetivo (max_bet) es solo de décimas, se redondea a ese
        monto (p.ej. un call que detecta 3.1 con apuesta de 3.0 → 3.0)."""
        if amount is None:
            return 0.0
        if max_bet is not None and max_bet > 0:
            d = round(abs(amount - max_bet), 2)
            if 0 < d <= 0.1:
                return round(max_bet, 2)
        return round(amount, 2)

    def _blind_of(self, pos_name):
        if pos_name == 'SB':
            return self._blind_sb
        if pos_name == 'BB':
            return self._blind_bb
        return 0.0


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

        # ---- SB / BB: detectados por el valor de la apuesta ciega ----
        # A la izquierda del BTN (sentido horario), el bet 0.5 → SB y el bet 1 → BB.
        # Si no hay apuesta 0.5 es porque SB no entró a la ronda: se salta esa pos.
        left_players = []
        cur = (btn_idx + 1) % n
        for _ in range(n - 1):
            p = SCREEN_SEATS[cur]
            left_players.append(p)
            cur = (cur + 1) % n

        bet_by_player = {}
        for p in left_players:
            b = state.get(f'{p}_bet')
            if b is not None and b > 0 and p in active:
                bet_by_player[p] = b

        bb_player = sb_player = None
        # BB: primer jugador a la izquierda con apuesta ≈ 1 (tamaño ciega grande)
        for p in left_players:
            if p in bet_by_player and self._near(bet_by_player[p], self._blind_bb):
                bb_player = p
                break
        # SB: primer jugador a la izquierda (distinto del BB) con apuesta ≈ 0.5
        if bb_player is not None:
            for p in left_players:
                if p == bb_player or p not in bet_by_player:
                    continue
                if self._near(bet_by_player[p], self._blind_sb) and bet_by_player[p] < bet_by_player.get(bb_player, 1):
                    sb_player = p
                    break

        # Fallback por asiento (btn+1 → SB, btn+2 → BB) cuando la apuesta no
        # identifica al jugador (p.ej. la mano ya está asentada y la SB/BB subió).
        # Estructura: saltar asientos inactivos/vacíos.
        def _next_seated(start_idx, skip=()):
            c = start_idx % n
            for _ in range(n):
                p = SCREEN_SEATS[c]
                if p in active and p not in positions and p not in skip:
                    return p
                c = (c + 1) % n
            return None

        # Determinar BB: si no se encontró por apuesta, usar el asiento btn+2 (o el
        # siguiente ocupado tras el asiento btn+1) que aún no tenga posición.
        if bb_player is None:
            cand = _next_seated(btn_idx + 2)
            if cand is not None:
                bb_player = cand
        if bb_player is not None:
            positions[bb_player] = 'BB'
            if bb_player in bet_by_player and self._near(bet_by_player[bb_player], self._blind_bb):
                self._blind_bb = bet_by_player[bb_player]
        # Determinar SB: si no se encontró por apuesta, usar el asiento btn+1
        # SOLO si ese asiento está ocupado/activo (si está vacío, SB no entró
        # a la ronda y se salta la posición).
        if sb_player is None and bb_player is not None:
            sb_seat = SCREEN_SEATS[(btn_idx + 1) % n]
            if sb_seat in active:
                sb_player = sb_seat
        if sb_player is not None:
            positions[sb_player] = 'SB'
            if sb_player in bet_by_player and self._near(bet_by_player[sb_player], self._blind_sb):
                self._blind_sb = bet_by_player[sb_player]

        # ---- CO / MP / UTG: antihorario desde el más próximo a BTN ----
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
        # Confirmar nueva mano por la presencia de ciegas (bet ≈ 0.5 / 1),
        # ya que los labels de estado (SB/BB) ya no se muestran.
        bets = [state.get(f'{p}_bet') for p in PLAYER_IDS]
        if not any(b is not None and self._near(b, self._blind_sb) for b in bets) \
           and not any(b is not None and self._near(b, self._blind_bb) for b in bets):
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
        # Cada mano parte de cero: los inactivos solo son los marcados por el
        # usuario (MANUAL_INACTIVE), que el proceso_frames vuelve a aplicar.
        self._inactive_players = set()
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
                'active': bool(positions.get(pid)) and pid not in MANUAL_INACTIVE,
                'name': PLAYER_NAMES.get(pid, pid),
                'pos': positions.get(pid, ''),
                'stack': stack,
                'cards': cards,
                '_id': pid,
            })

        self._allin_players = set()
        self._folded_positions = set()
        self._stake_history = {}
        self._initial_stakes = {}
        self._river_stable_count = 0
        self._last_state_sig = None
        for pid in PLAYER_IDS:
            self._initial_stakes[pid] = state.get(f'{pid}_stake')

        self.hand = hand
        self.last_state = state
        self.street_has_bet = False
        self._street_pot = state.get('pot') or 0

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
        """Detecta acciones preflop desde bets/pot/stack (sin labels).
        La ciega del BB abre la ronda ('b 1.0'); los limps son calls ('c') y
        el primer subidor es raise ('r'). Las ciegas pendientes (SB) se
        acumulan en _blinds_by_pos para sumarlas a su primer movimiento.
        En frame inicial puede no haber bets aún: la referencia a igualar
        es la ciega BB (_blind_bb)."""
        PREFLOP_ORDER = ['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB']
        pos_map = self._get_pos_map(state)
        self._blinds_by_pos = {}

        bids = {}
        for pos_name in PREFLOP_ORDER:
            pid = pos_map.get(pos_name)
            if pid is not None:
                bids[pos_name] = state.get(f'{pid}_bet')

        # 1) Folds visibles en el snapshot inicial
        for pos_name in PREFLOP_ORDER:
            pid = pos_map.get(pos_name)
            if pid is None:
                continue
            st = state.get(f'{pid}_state')
            if st in ('retirarse', 'ausente', 'inactivo') or pid in self._inactive_players:
                self._add_action('preflop', pos_name, 'f', 0.0)

        # Referencia a igualar = ciega BB (el primer movimiento por encima
        # de ella es raise; los que igualan son calls)
        max_bet = self._blind_bb

        # 2) La ciega del BB abre la ronda (primera apuesta 'b')
        bb_pid = pos_map.get('BB')
        bb_bet = bids.get('BB')
        bb_open = bb_bet if (bb_bet is not None and bb_bet > 0) else self._blind_bb
        if bb_pid is not None and bb_open > 0:
            if not any(a['pos'] == 'BB' and a['action'] == 'b' for a
                       in self.hand['streets']['preflop']['actions']):
                self.hand['streets']['preflop']['actions'].append(
                    {'pos': 'BB', 'action': 'b', 'amount': round(bb_open, 2)})
            max_bet = max(max_bet, bb_open)

        # 3) Movimientos voluntarios de los demás (c / r)
        for pos_name in PREFLOP_ORDER:
            if pos_name == 'BB':
                continue
            pid = pos_map.get(pos_name)
            if pid is None:
                continue
            bet = bids.get(pos_name)
            blind = self._blind_of(pos_name)
            if bet is None or bet <= 0:
                continue
            if bet <= blind + 0.05:
                # Solo su ciega (sin movimiento voluntario aún) → pendiente
                self._blinds_by_pos[pos_name] = bet
                continue
            amt = round(bet, 2)
            if amt > max_bet + 0.15:
                self._add_action('preflop', pos_name, 'r', amt)
                max_bet = max(max_bet, amt)
            else:
                self._add_action('preflop', pos_name, 'c', amt)

        # Máxima apuesta de la ronda (referencia para deltas posteriores)
        for b in bids.values():
            if b is not None and b > max_bet:
                max_bet = b

        # El BB abrió preflop → la ronda ya tiene una apuesta
        self.street_has_bet = True
        self._preflop_current_bet = max_bet

    def _add_action(self, street, pos, action, amount):
        if self.hand is None:
            return
        # Si hay ciega pendiente para esta posici&oacute;n, sumarla al monto
        # (un fold NO arrastra su ciega: el monto del fold es 0.0)
        if pos in self._blinds_by_pos and action != 'f':
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

    def _detect_deltas(self, state):
        """Detecta acciones entre last_state y state usando únicamente
        deltas de stack / bet / pot (sin depender de labels de acción).
        Retorna [(street, pos, action, amount), ...]."""
        if self.last_state is None or self.hand is None:
            return []
        street = self.hand['current_street']
        order = self._get_street_order(state, street)
        pos_map = self._get_pos_map(state)
        actions = []
        street_actions = self.hand['streets'][street].setdefault('actions', [])

        old_pot = self.last_state.get('pot') or 0
        new_pot = state.get('pot') or 0
        hand_ending = old_pot > 0 and new_pot == 0

        # Estado de la ronda de apuestas mientras recorremos la calle
        has_bet = self.street_has_bet
        run_max = self._get_max_bet(street)

        for pos_name in order:
            pid = pos_map.get(pos_name)
            if pid is None or pid in self._inactive_players:
                continue
            if pos_name in self._folded_positions:
                continue
            if pid in self._allin_players:
                continue

            prev_stake = self.last_state.get(f'{pid}_stake')
            cur_stake = state.get(f'{pid}_stake')
            cur_st = state.get(f'{pid}_state')
            prev_bet = self.last_state.get(f'{pid}_bet') or 0
            cur_bet = state.get(f'{pid}_bet') or 0

            was_active = prev_stake is not None
            dimmed = cur_st in ('retirarse', 'ausente', 'inactivo', 'sin jugador', 'fuera')

            # ---- All-in: el stake pasó de x a None (jugador activo, sin fold) ----
            # Se detecta primero porque el all-in deja el stack en None.
            if was_active and cur_stake is None and not dimmed:
                amt = round((prev_stake or 0) + prev_bet, 2)
                if amt <= 0:
                    continue
                if not has_bet:
                    atype = 'b'
                elif amt <= run_max + 0.15:
                    atype = 'c'
                else:
                    atype = 'r'
                if not self._dup(street, pos_name, amt):
                    actions.append((street, pos_name, atype, round(amt, 2)))
                    self._allin_players.add(pid)
                    if atype in ('b', 'r'):
                        has_bet = True
                        run_max = max(run_max, amt)
                continue

            # ---- Fold: estaba en la mano y ahora difuminado/inactivo ----
            # (conserva el stake visible pero la casilla se apaga, como los
            # 'inactivo' de antes)
            if was_active and dimmed:
                if not hand_ending and not any(a['pos'] == pos_name and a['action'] == 'f'
                                               for a in street_actions):
                    actions.append((street, pos_name, 'f', 0.0))
                    self._folded_positions.add(pos_name)
                continue

            # ---- Dinero comprometido: el stake bajó (bet / call / raise) ----
            if cur_stake is not None:
                delta = round((prev_stake or 0) - cur_stake, 2)
                if delta > 0.05:
                    amt = self._round_bet(delta, run_max)
                    if amt <= 0:
                        continue
                    if not has_bet:
                        atype = 'b'
                    elif amt <= run_max + 0.15:
                        atype = 'c'
                    else:
                        atype = 'r'
                    if not self._dup(street, pos_name, amt):
                        actions.append((street, pos_name, atype, round(amt, 2)))
                        if atype in ('b', 'r'):
                            has_bet = True
                            run_max = max(run_max, amt)

        # Público actualizado de la ronda para los siguientes frames
        self.street_has_bet = has_bet
        if street != 'preflop' or run_max > getattr(self, '_preflop_current_bet', 0.0):
            self._preflop_current_bet = run_max

        return actions

    def _dup(self, street, pos_name, amt, tol=0.3):
        """True si ya existe una acción (pos, ~amount) en la calle."""
        return any(a['pos'] == pos_name and abs(a['amount'] - amt) < tol
                   for a in self.hand['streets'][street]['actions'])

    def _get_max_bet(self, street_name):
        max_amt = getattr(self, '_preflop_current_bet', 0.0) if street_name == 'preflop' else 0.0
        for a in self.hand['streets'][street_name]['actions']:
            if a['action'] in ('b', 'r'):
                max_amt = max(max_amt, a['amount'])
        return max_amt

    def detect_actions(self, state):
        """Detecta folds, all-ins, bets/calls/raises entre last_state y state."""
        if self.last_state is None or self.hand is None:
            return []
        street = self.hand['current_street']
        actions = self._detect_deltas(state)
        for s, pos, a, amt in actions:
            self._add_action(s, pos, a, amt)
        # Checks por lógica de juego (posflop): rellenar checks de los que
        # hablan antes que una apuesta, o todos si no hay apuesta.
        self._add_implied_checks(street, state)
        # Detección de check general en river (sin cambios entre pantallazos)
        self._detect_river_check(state, street)
        return actions

    def _detect_river_check(self, state, street_name):
        """En river no hay cambios de calle: si dos pantallazos consecutivos no
        muestran ningún cambio de stack/bet, todos los jugadores activos
        hicieron check. Se registran los checks que falten."""
        if self.hand is None or street_name != 'river':
            return
        if self.last_state is None:
            return
        cur_sig = self._state_sig(state)
        if not self._river_stable_count:
            # primer pantallazo: guardamos la firma
            self._river_stable_count = 1
            self._last_state_sig = cur_sig
            return
        if cur_sig == self._last_state_sig:
            self._river_stable_count += 1
        else:
            self._river_stable_count = 1
            self._last_state_sig = cur_sig
        if self._river_stable_count < 2:
            return
        # Dos pantallazos idénticos: nadie apostó → checks implícitos
        self._add_implied_checks('river', state)

    def _state_sig(self, state):
        """Firma del estado de stacks/bets para detectar ausencia de cambios."""
        vals = []
        for p in PLAYER_IDS:
            vals.append((state.get(f'{p}_stake'), state.get(f'{p}_bet')))
        vals.append(state.get('pot'))
        return tuple(vals)

    def process_street_labels(self, state, street_name):
        """Método mantenido por compatibilidad (la detección ya es por deltas)."""
        return

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
        # Confirmación de "todos fallaron chequeo": si el pot quedó igual que
        # al empezar la calle, nadie apostó → todos los que siguen activos
        # hicieron check en la calle que termina.
        now_pot = state.get('pot') or 0
        confirm_all_check = (street := self.hand['current_street']) != 'preflop' \
            and abs(now_pot - (self._street_pot or 0)) < 0.15
        self._finalize_street(street, state, confirm_all_check=confirm_all_check)
        self._street_pot = now_pot
        self.hand['current_street'] = new_street
        self.street_has_bet = False

    def _finalize_street(self, street_name, state=None, confirm_all_check=False):
        # Add implied checks first (modifies the list in place via re-assign)
        if state is not None:
            self._add_implied_checks(street_name, state, confirm_all_check=confirm_all_check)

        actions = self.hand['streets'][street_name].setdefault('actions', [])
        if not actions:
            return

        ORDER = self._get_street_order(None, street_name)
        pos_ord = {p: i for i, p in enumerate(ORDER)}

        # Preflop: la ciega del BB abre la ronda. Se extrae aquí para que
        # vaya siempre primera y no participe del merge ni del orden rotado.
        blind = None
        if street_name == 'preflop':
            for i, a in enumerate(actions):
                if a['pos'] == 'BB' and a['action'] == 'b':
                    blind = actions.pop(i)
                    break

        # Merge consecutive same-position actions
        merged = []
        for a in actions:
            if merged and merged[-1]['pos'] == a['pos'] and a['action'] in ('c', 'b'):
                merged[-1]['amount'] = round(merged[-1]['amount'] + a['amount'], 2)
            else:
                merged.append(dict(a))
        actions[:] = merged

        if not actions and blind is None:
            return

        checks = [a for a in actions if a['action'] == 'x']
        non_checks = [a for a in actions if a['action'] != 'x']

        # Preflop sin subidas: si la acción dio la vuelta y volvió al BB
        # (hay al menos un call) y el BB sigue vivo sin haber actuado desde
        # la ciega, el BB pasó la opción -> 'x' cerrando la ronda.
        if street_name == 'preflop' and blind is not None:
            has_raise = any(a['action'] == 'r' for a in actions)
            bb_acted = any(a['pos'] == 'BB' for a in actions)
            has_call = any(a['action'] == 'c' for a in actions)
            bb_alive = 'BB' not in self._folded_positions
            bb_checked = any(a['pos'] == 'BB' and a['action'] == 'x'
                             for a in actions)
            if (not has_raise and not bb_acted and has_call
                    and bb_alive and not bb_checked):
                actions.append({'pos': 'BB', 'action': 'x', 'amount': 0.0})
                checks = [a for a in actions if a['action'] == 'x']
                non_checks = [a for a in actions if a['action'] != 'x']

        bettor_pos = None
        for a in non_checks:
            if a['action'] in ('b', 'r'):
                bettor_pos = a['pos']
                break

        checks.sort(key=lambda a: pos_ord.get(a['pos'], 99))

        # La ciega abre el preflop (si existe).
        head = [blind] if blind is not None else []

        if bettor_pos is None and street_name != 'preflop':
            actions[:] = checks + non_checks
            return

        # Preflop: el primer en hablar (acción voluntaria) es siempre UTG;
        # la ciega ya va primera en `head`. Sin apuestas también se ordena
        # por rotación desde UTG (una acción por posición por pasada).
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
            actions[:] = head + ordered + checks
        else:
            actions[:] = checks + ordered

    def _add_implied_checks(self, street_name, state, confirm_all_check=False):
        """Detecta checks por lógica de juego en calles posflop.

        - Con apuesta en la calle: los jugadores activos que hablan ANTES que
          el primer apostador (y no apostaron ni tienen acción) checkearon
          antes. Es lógica sólida: si SB habla primero y BB apuesta, SB ya
          habló → check.
        - Sin apuesta: aquí NO se puede afirmar que todos hayan hablado solo
          por falta de botón; los jugadores pueden estar todavía decidiendo.
          Solo se marca "todos check" cuando hay confirmación (double-frame en
          river o pot sin cambios al pasar de calle) vía confirm_all_check.
        Se salta preflop (las ciegas abren la ronda)."""
        if street_name == 'preflop':
            return
        existing = self.hand['streets'][street_name].setdefault('actions', [])
        existing_pos = {a['pos'] for a in existing}
        pos_map = self._get_pos_map(state)
        ORDER = self._get_street_order(None, street_name)

        def in_hand(pos):
            pid = pos_map.get(pos)
            if not pid:
                return False
            if pid in self._inactive_players:
                return False
            if pos in self._folded_positions:
                return False
            if pid in self._allin_players:
                return False
            if state.get(f'{pid}_stake') is None:
                return False
            return True

        # Botones de apuesta visibles ahora (quien tiene dinero en juego no
        # checkeó en este pantallazo)
        bettors = [a for a in existing if a['action'] in ('b', 'r')]
        if bettors:
            first_idx = min(ORDER.index(b['pos']) for b in bettors)
            leading = ORDER[:first_idx]
        elif confirm_all_check:
            # Confirmado (pot sin cambios o double-frame): sin apuesta en toda
            # la calle → todos los jugadores hablaron, es decir checkearon.
            first_idx = None
            leading = ORDER
        else:
            # Sin apuesta Y sin confirmación: no sabemos si todos hablaron.
            # Solo podemos suponer checks para quienes ya no tienen decisión
            # (fold/absent/out), que quedan cubiertos por los filtros de
            # in_hand. No inventamos checks para los que estarían aún decidiendo.
            first_idx = None
            leading = []

        # Quitar checks obsoletos: nadie que esté en/a partir del apostador
        # pudo haber checkeado y luego apostado en la misma calle.
        if first_idx is not None:
            keep = set(leading)
            existing[:] = [a for a in existing if not (a['action'] == 'x' and a['pos'] not in keep)]

        existing_pos = {a['pos'] for a in existing}
        checks = []
        for pos in ORDER:
            if pos not in leading:
                continue
            if pos in existing_pos:
                continue
            if in_hand(pos):
                checks.append({'pos': pos, 'action': 'x', 'amount': 0.0})
        if checks and street_name != 'preflop':
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
            # Ganador automático: solo un superviviente claro (los demás
            # foldearon). En showdown multiway no se puede determinar el
            # ganador sin evaluar manos → se deja vacío (el GUI lo ajusta).
            all_still_in = [p for p in self.hand['players']
                            if p['active'] and p['_id'] not in self._inactive_players
                            and p['pos'] not in self._folded_positions
                            and state.get(f'{p["_id"]}_state') not in ('retirarse', 'ausente', 'inactivo')]
            if len(all_still_in) == 1:
                self.hand['winner'] = [all_still_in[0]['_id']]
                self.hand['showdown'] = {
                    'winner1': f'{all_still_in[0]["pos"]} ({all_still_in[0]["name"]})'
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
        # Jugador cuyo stack desapareció sin fold ni all-in registrado (p.ej.
        # el badge 'apostar todo' tapa su stack tras un call all-in): su
        # acción sigue pendiente y debe detectarse antes de declarar el fin.
        if self.last_state is not None:
            for p in PLAYER_IDS:
                if p in active or p in self._allin_players or p in self._inactive_players:
                    continue
                if p in self._folded_positions:
                    continue
                if self.last_state.get(f'{p}_stake') is None:
                    continue
                st = state.get(f'{p}_state')
                if st in ('retirarse', 'ausente', 'inactivo'):
                    continue
                if st is None or st == 'apostar todo':
                    return False
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
