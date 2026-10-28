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
import hashlib, json, os, time, datetime
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


def _es_ciega_obligatoria(action, bb_amount, blind, tol=0.05):
    """True si una acción existente del BB es realmente la ciega obligatoria.

    No basta con que sea `pos == 'BB' and action == 'b'`: un 'b' del BB por
    encima de la ciega es una subida voluntaria y marcarla como ciega sería
    inventar una decisión que no ocurrió (revision_2, P1).
    """
    try:
        amt = float(action.get('amount') or 0.0)
    except (TypeError, ValueError):
        return False
    return amt <= blind + tol and bb_amount <= blind + tol
MANUAL_POSITIONS = {}      # pid -> position override from GUI (e.g. {'hero': 'BTN'})
STATE_ACTIONS = {'retirarse': 'f', 'igualar': 'c', 'subir': 'r', 'apostar': 'b', 'apostar todo': 'b', 'pasar': 'x', 'mostrar cartas': 'c'}


def _json_safe(value):
    """Copia JSON de un estado de frame, sin tipos raros de numpy/PIL."""
    try:
        return json.loads(json.dumps(value, default=str))
    except (TypeError, ValueError):
        return str(value)


class LiveRecorder:
    def __init__(self, output_path=None, capture_dir=None, session_dir=None,
                 test_targets=None):
        self.output_path = output_path or OUTPUT_PATH
        self.capture_dir = capture_dir
        # Estos datos viven exclusivamente en el sidecar de la sesión.  No se
        # mezclan con el contrato de una mano de la base canónica.
        self.session_dir = session_dir
        self.test_targets = list(test_targets or [])
        self._target_index = 0
        self.capture_index_path = (
            os.path.join(capture_dir, 'index.jsonl') if capture_dir else None)
        self._capture_seq = self._last_capture_seq(self.capture_index_path)
        self.hand_id = None
        self.hand = None
        self.last_state = None
        self.last_img = None
        self.street_has_bet = False
        self._inactive_players = set()
        self._allin_players = set()
        self._stake_history = {}
        self._initial_stakes = {}
        self._hand_ambiguities = []
        self._completed_streets = set()
        self._returned_by_pos = {}
        self._inferred_action_keys = set()
        self._ambiguous_action_keys = set()
        self._award_display_pids = set()
        self._award_display_events = {}
        self._just_changed_street = False
        self._carryover_calls = {}
        self._adjusted_last_state = None
        self._hand_positions = None
        self._folded_positions = set()
        self.on_hand_saved = None
        # Sidecar consumers (e.g. the assistant's decision log) receive the
        # completed in-memory hand without changing the hands DB schema.
        self.on_hand_finalized = None
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

    def _last_capture_seq(self, path):
        if not path or not os.path.exists(path):
            return 0
        last = 0
        try:
            with open(path, encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        last = max(last, int(json.loads(line).get('seq') or 0))
        except Exception:
            pass
        return last

    def save_frame(self, state, img_arr, log=print):
        """Guarda el frame y su estado en la sesion de prueba, en orden.

        Solo actua si `capture_dir` esta configurado. El nombre lleva un
        secuencial global, el hand_id del recorder y la calle, para que la
        reproduccion posterior sea determinista aunque se reinicie la GUI.
        """
        if not self.capture_dir or img_arr is None:
            return None
        try:
            self._capture_seq += 1
            hid = f'H_{self.hand_id:04d}' if self.hand_id is not None else 'H_0000'
            street = ((self.hand or {}).get('current_street') or 'sin_mano')
            stamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
            stem = f'{self._capture_seq:04d}_{hid}_{street}_{stamp}'
            hand_dir = os.path.join(self.capture_dir, hid)
            os.makedirs(hand_dir, exist_ok=True)
            img_path = os.path.join(hand_dir, stem + '.png')
            from PIL import Image
            Image.fromarray(img_arr).save(img_path)
            with open(img_path, 'rb') as f:
                digest = hashlib.sha256(f.read()).hexdigest()
            meta = {
                'seq': self._capture_seq,
                'frame': os.path.relpath(img_path, self.capture_dir),
                'timestamp': datetime.datetime.now().isoformat(),
                'hand_id': hid,
                'street': street,
                'sha256': digest,
                'state': _json_safe(state),
                'manual_cards': dict(MANUAL_CARDS),
                'manual_inactive': sorted(MANUAL_INACTIVE),
                'manual_positions': dict(MANUAL_POSITIONS),
                'manual_winner': MANUAL_WINNER,
                'test_targets': self.test_targets,
                'target_hand_id': self._current_target,
            }
            json_path = os.path.join(hand_dir, stem + '.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=1)
            index_path = self.capture_index_path or os.path.join(
                self.capture_dir, 'index.jsonl')
            with open(index_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(meta, ensure_ascii=False) + '\n')
            return img_path
        except Exception as exc:
            log(f'  [captura] no se pudo guardar: {exc}')
            return None

    @property
    def _current_target(self):
        if 0 <= self._target_index < len(self.test_targets):
            return self.test_targets[self._target_index]
        return None

    def _record_session_result(self, hand):
        """Añade la relación prueba→resultado fuera del JSONL de manos."""
        if not self.session_dir:
            return
        try:
            path = os.path.join(self.session_dir, 'resultados',
                                'registro_sesion.jsonl')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            target_id = self._current_target
            record = {
                'timestamp': datetime.datetime.now().isoformat(),
                'recorded_hand_id': hand.get('hand_id'),
                'target_hand_id': target_id,
                'test_targets': self.test_targets,
                'target_index': self._target_index,
                'output': os.path.relpath(self.output_path, self.session_dir),
            }
            if target_id is not None:
                self._target_index += 1
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        except OSError:
            # El recorder no debe perder una mano porque falle el índice de
            # conveniencia de una sesión de prueba.
            pass

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

    def _new_street_bets_visible(self, state):
        """True si la calle nueva ya tiene una apuesta propia.

        Una casilla con el mismo importe que ya estaba en `last_state` es
        una apuesta heredada de la calle vieja (captura lenta o UI que aun
        no limpio el fieltro), no una apuesta nueva. Solo cuenta como nueva
        si el importe aparecio o cambio.
        """
        if self.last_state is None:
            return self._any_bet(state)
        for p in PLAYER_IDS:
            cur_bet = state.get(f'{p}_bet') or 0
            if cur_bet <= 0:
                continue
            prev_bet = self.last_state.get(f'{p}_bet') or 0
            if prev_bet <= 0 or not self._near(cur_bet, prev_bet):
                return True
        return False

    def _get_com_list(self, state):
        cards = state.get('community', [])
        return [(f'{c["rank"]}{c["suit"]}' if c and c.get('rank') and c.get('suit') else '')
                for c in cards[:5]]

    def _street_rank(self, street):
        return {'preflop': 0, 'flop': 1, 'turn': 2, 'river': 3}.get(street, 0)

    def _target_street(self, state):
        visible = self._visible_coms(state)
        if visible >= 5:
            return 'river'
        if visible >= 4:
            return 'turn'
        if visible >= 3:
            return 'flop'
        return 'preflop'

    def _create_street_board(self, street, state):
        cards = self._get_com_list(state)
        visible = [c for c in cards if c]
        if street == 'flop':
            self.hand['comunitarias']['flop'] = visible[:3]
            self.hand['streets']['flop']['board'] = visible[:3]
        elif street == 'turn':
            self.hand['comunitarias']['turn'] = [visible[3]] if len(visible) > 3 else []
            self.hand['streets']['turn']['board'] = [visible[3]] if len(visible) > 3 else []
        elif street == 'river':
            self.hand['comunitarias']['river'] = [visible[4]] if len(visible) > 4 else []
            self.hand['streets']['river']['board'] = [visible[4]] if len(visible) > 4 else []

    def _infer_street_actions(self, street, prev_state, cur_state, log):
        if self.hand is None or prev_state is None:
            return {}
        pid_map = self._get_pid_map(cur_state)
        contributions = {}
        fold_candidates = []
        for pid in PLAYER_IDS:
            pos = pid_map.get(pid)
            if not pos or pid in self._inactive_players:
                continue
            prev_stake = prev_state.get(f'{pid}_stake')
            cur_stake = cur_state.get(f'{pid}_stake')
            if prev_stake is None:
                continue
            prev_bet = prev_state.get(f'{pid}_bet') or 0
            total_level = round(prev_bet + max(0.0, (prev_stake or 0) - (cur_stake or 0)), 2)
            turn_level = round(cur_state.get(f'{pid}_bet') or 0, 2)
            level = round(max(0.0, total_level - turn_level), 2)
            if level > 0.05:
                contributions[pos] = max(contributions.get(pos, 0.0), level)
            elif (cur_stake is not None and prev_stake is not None
                  and cur_state.get(f'{pid}_state') in ('retirarse', 'ausente')):
                fold_candidates.append(pos)
        if not contributions:
            return {}
        max_level = max(contributions.values())
        actions = []
        for pos in self._get_street_order(None, street):
            if pos in contributions:
                level = contributions[pos]
                atype = 'b' if level >= max_level - 0.05 else 'c'
                actions.append({'pos': pos, 'action': atype, 'amount': round(level, 2),
                                'amount_type': 'observed', 'inferred': True,
                                'ambiguous': True})
            elif pos in fold_candidates:
                actions.append({'pos': pos, 'action': 'f', 'amount': 0.0,
                                'amount_type': 'observed', 'inferred': True,
                                'ambiguous': True})
        self.hand['streets'][street]['actions'] = actions
        for action in actions:
            if action['action'] in ('b', 'r'):
                self._ambiguous_action_keys.add(
                    (street, action['pos'], round(action['amount'], 2)))
        self._add_ambiguity(
            'street_inferred_from_stack_delta', street,
            contributions=contributions,
            note='Calle no capturada: acciones inferidas desde la diferencia de stacks.')
        return contributions

    def _make_synthetic_state(self, prev_state, cur_state, contributions, street):
        synth = dict(cur_state)
        pid_map = self._get_pid_map(cur_state)
        for pid in PLAYER_IDS:
            pos = pid_map.get(pid)
            level = contributions.get(pos, 0.0) if pos else 0.0
            prev_stake = (prev_state or {}).get(f'{pid}_stake')
            if prev_stake is not None:
                synth[f'{pid}_stake'] = round(max(0.0, (prev_stake or 0) - level), 2)
            synth[f'{pid}_bet'] = None
        if len(contributions) > 1:
            matched = sum(sorted(contributions.values())[1:])
        else:
            matched = 0.0
        prev_pot = (prev_state or {}).get('pot') or 0
        synth['pot'] = round(prev_pot + matched + max(contributions.values(), default=0.0), 2)
        return synth

    def _handle_street_jump(self, target, state, log):
        if self.hand is None:
            return
        cur = self.hand['current_street']
        streets = ['preflop', 'flop', 'turn', 'river']
        ci = streets.index(cur)
        ti = streets.index(target)
        intermediates = streets[ci + 1:ti]
        if not intermediates:
            return
        prev_state = self.last_state
        log(f'  [salto de calle] {cur} -> {target}: infiriendo {", ".join(intermediates)}')
        for index, street in enumerate(intermediates):
            self._create_street_board(street, state)
            if index == 0:
                self._finalize_street(cur, prev_state, confirm_all_check=False)
                contrib = self._infer_street_actions(street, prev_state, state, log)
                synth = self._make_synthetic_state(prev_state, state, contrib, street)
                self._completed_streets.add(cur)
                prev_state = synth
            else:
                self._finalize_street(intermediates[index - 1], prev_state, confirm_all_check=False)
                self._add_ambiguity('street_not_captured', street,
                                    note='Calle intermedia no capturada.')
                self.hand['streets'][street]['actions'] = []
                self._completed_streets.add(intermediates[index - 1])
            self.hand['current_street'] = street
            self.last_state = prev_state

    def _visible_coms(self, state):
        return sum(1 for c in self._get_com_list(state) if c)

    def _add_ambiguity(self, code, street=None, **detail):
        """Registra una duda auditable una sola vez por firma."""
        if self.hand is None:
            return
        row = {'code': code}
        if street:
            row['street'] = street
        row.update(_json_safe(detail))
        identity = (row.get('code'), row.get('street'), row.get('pos'))
        for i, old in enumerate(self._hand_ambiguities):
            if (old.get('code'), old.get('street'), old.get('pos')) == identity:
                self._hand_ambiguities[i] = row
                return
        self._hand_ambiguities.append(row)

    def _street_contributions(self, street):
        """Aporte absoluto por posición en una calle; nunca suma niveles."""
        contributions = {}
        actions = (((self.hand or {}).get('streets') or {}).get(street) or {}).get('actions') or []
        for action in actions:
            pos = action.get('pos')
            if not pos or action.get('action') not in ('p', 'b', 'c', 'r'):
                continue
            try:
                amount = max(0.0, float(action.get('amount') or 0.0))
            except (TypeError, ValueError):
                continue
            contributions[pos] = max(contributions.get(pos, 0.0), amount)
        for (returned_street, pos), returned in (self._returned_by_pos or {}).items():
            if returned_street == street and pos in contributions:
                contributions[pos] = max(0.0, contributions[pos] - returned)
        return contributions

    @staticmethod
    def _matched_and_uncalled(contributions):
        values = sorted(contributions.values(), reverse=True)
        gross = sum(values)
        uncalled = max(0.0, values[0] - (values[1] if len(values) > 1 else 0.0)) if values else 0.0
        return gross - uncalled, uncalled, gross

    def _pot_breakdown(self, final=False, fold_win=False):
        """Calcula bote y comisión desde las acciones absolutas.

        Se cobra rake únicamente sobre aportes igualados. En una calle en
        curso no se considera visible hasta que cierra; al finalizar sí se
        incorpora la calle final, salvo que la mano acabara preflop.
        """
        gross_total = matched_total = rake_basis = 0.0
        streets = ('preflop', 'flop', 'turn', 'river')
        has_postflop = any(
            (((self.hand or {}).get('streets') or {}).get(s) or {}).get('board')
            for s in ('flop', 'turn', 'river')) or any(
                ((self.hand or {}).get('comunitarias') or {}).get(s)
                for s in ('flop', 'turn', 'river'))
        board_data = (self.hand or {}).get('comunitarias') or {}
        for street in streets:
            contrib = self._street_contributions(street)
            matched, _uncalled, gross = self._matched_and_uncalled(contrib)
            matched_total += matched
            gross_total += gross
            completed = street in self._completed_streets
            if street == 'preflop' and has_postflop:
                completed = True
            elif street == 'flop' and (board_data.get('turn') or board_data.get('river')):
                completed = True
            elif street == 'turn' and board_data.get('river'):
                completed = True
            is_final_street = final and street == (self.hand or {}).get('current_street')
            if completed or is_final_street:
                if street != 'preflop' or has_postflop:
                    rake_basis += matched
        rake = min(0.05 * rake_basis, 2.5 * float(self._blind_bb or 1.0))
        # La modalidad fold conserva el excedente no igualado en el bote
        # registrado; en showdown los excedentes se devuelven.
        pot_inflated = (gross_total if fold_win else matched_total) - rake
        pot_not_inflated = matched_total - rake
        return {
            'gross_contributions': round(gross_total, 2),
            'matched_contributions': round(matched_total, 2),
            'uncalled': round(max(0.0, gross_total - matched_total), 2),
            'rake_basis': round(rake_basis, 2),
            'rake': round(rake, 2),
            'pot_calculated': round(max(0.0, pot_inflated), 2),
            'pot_calculated_noninflated': round(max(0.0, pot_not_inflated), 2),
            'pot_live_calculated': round(max(0.0, gross_total - rake), 2),
        }

    def _audit_live_pot(self, state):
        if self.hand is None:
            return
        reading = state.get('pot')
        if reading is None:
            reading = state.get('pot_wide')
        if reading is None:
            return
        breakdown = self._pot_breakdown(final=False)
        expected = breakdown['pot_live_calculated']
        raw_difference = abs(float(reading) - expected)
        difference = round(raw_difference, 2)
        if raw_difference > self._ambiguity_tolerance():
            self._add_ambiguity(
                'pot_read_vs_contributions', self.hand.get('current_street'),
                pot_read=round(float(reading), 2),
                contributions=breakdown['gross_contributions'],
                completed_street_rake=breakdown['rake'],
                pot_expected=expected, difference=difference)

        pos_map = self._get_pos_map(state)
        current_contrib = self._street_contributions(self.hand['current_street'])
        for pos, pid in pos_map.items():
            if pid in self._award_display_pids:
                continue
            bet = state.get(f'{pid}_bet')
            if bet is None:
                continue
            recorded = current_contrib.get(pos, 0.0)
            if abs(float(bet or 0.0) - recorded) > self._ambiguity_tolerance():
                self._add_ambiguity(
                    'bet_read_vs_recorded', self.hand.get('current_street'),
                    pos=pos, bet_read=round(float(bet or 0.0), 2),
                    amount_recorded=round(recorded, 2),
                    difference=round(abs(float(bet or 0.0) - recorded), 2))

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

        left_players = []
        cur = (btn_idx + 1) % n
        for _ in range(n - 1):
            p = SCREEN_SEATS[cur]
            if p in active:
                left_players.append(p)
            cur = (cur + 1) % n

        sb_player = bb_player = None
        if len(left_players) >= 2:
            sb_player, bb_player = left_players[0], left_players[1]
        elif len(left_players) == 1:
            bb_player = left_players[0]

        if sb_player is not None:
            positions[sb_player] = 'SB'
        if bb_player is not None:
            positions[bb_player] = 'BB'

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

    def _award_overlay_candidates(self, state):
        """Seats with a rising stack and a nonzero bet-box value this frame."""
        if self.hand is None or self.last_state is None:
            return {}
        out = {}
        for pid in PLAYER_IDS:
            before = self.last_state.get(f'{pid}_stake')
            after = state.get(f'{pid}_stake')
            bet = state.get(f'{pid}_bet')
            if (before is not None and after is not None and bet is not None
                    and after > before + 0.05 and float(bet or 0) > 0):
                out[pid] = {'before': before, 'after': after, 'bet': bet}
        return out

    def _without_award_bet_overlay(self, state, candidates):
        """No reutiliza el premio visible como apuesta de la mano siguiente."""
        if not candidates:
            return state
        clean = dict(state)
        positions = self._assign_positions(state)
        for pid, values in candidates.items():
            pos = positions.get(pid)
            expected_blind = (self._blind_sb if pos == 'SB' else
                              self._blind_bb if pos == 'BB' else None)
            bet = values['bet']
            if expected_blind is None or not self._near(bet, expected_blind, tol=0.05):
                clean[f'{pid}_bet'] = None
        return clean

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
        self._hand_ambiguities = []
        self._completed_streets = set()
        self._returned_by_pos = {}
        self._inferred_action_keys = set()
        self._ambiguous_action_keys = set()
        self._award_display_pids = set()
        self._award_display_events = {}
        self._just_changed_street = False
        self._carryover_calls = {}
        self._adjusted_last_state = None
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
        """Reconstruye el preflop desde un snapshot, en el formato canonico.

        Las ciegas obligatorias se escriben como `p` (posta forzada, no
        decision): primero SB 0.5 y despues BB 1.0. El resto de acciones
        (folds, limps, opens, calls y raises) se emiten en el orden real de
        actuacion 6-max (UTG, MP, CO, BTN, SB, BB) y con importe absoluto.

        `p` no sube el nivel: la referencia para decidir si una accion es
        call o raise sigue siendo `_blind_bb`, no el importe de la posta.
        Si el snapshot llega con el SB/BB ya actuado, la posta se emite igual
        y la accion voluntaria va despues, como en la base canonica.

        ORDEN: INFERIDO POR POSICION, NO OBSERVADO frame a frame
        ------------------------------------------------------------
        Lo que sigue siendo inferido es el instante exacto dentro de la
        calle. PREFLOP_ORDER (UTG, MP, CO, BTN, SB, BB) SI es el orden real
        de actuacion en 6-max, asi que para la primera decision de cada
        jugador la inferencia coincide con la realidad. Lo que no puede
        reconstruir es una segunda actuacion del mismo jugador.

        NO se ordena por importe: `amount` es la aportacion total observada,
        no un delta, y usarla para reordenar seria inventar un orden.
        """
        PREFLOP_ORDER = ['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB']
        pos_map = self._get_pos_map(state)
        self._blinds_by_pos = {}

        bids = {}
        for pos_name in PREFLOP_ORDER:
            pid = pos_map.get(pos_name)
            if pid is not None:
                bids[pos_name] = state.get(f'{pid}_bet')

        max_bet = self._blind_bb
        sb_bet = bids.get('SB')
        bb_bet = bids.get('BB')

        if pos_map.get('SB') is not None and sb_bet is not None and sb_bet > 0:
            self._add_action('preflop', 'SB', 'p',
                             round(self._blind_sb, 2), 'observed')
        if pos_map.get('BB') is not None:
            self._add_action('preflop', 'BB', 'p',
                             round(self._blind_bb, 2), 'observed')

        for pos_name in PREFLOP_ORDER:
            pid = pos_map.get(pos_name)
            if pid is None or pid in self._inactive_players:
                continue
            st = state.get(f'{pid}_state')

            if st in ('retirarse', 'ausente', 'inactivo'):
                self._add_action('preflop', pos_name, 'f', 0.0, 'observed')
                continue

            bet = bids.get(pos_name)
            if bet is None or bet <= 0:
                continue

            if pos_name == 'SB':
                if bet <= self._blind_sb + 0.05:
                    continue
            elif pos_name == 'BB':
                if bet <= self._blind_bb + 0.05:
                    continue

            amt = round(bet, 2)
            if amt > max_bet + 0.15:
                self._add_action('preflop', pos_name, 'r', amt, 'observed')
                max_bet = amt
            else:
                self._add_action('preflop', pos_name, 'c', amt, 'observed')

        for b in bids.values():
            if b is not None and b > max_bet:
                max_bet = b

        self.street_has_bet = True
        self._preflop_current_bet = max_bet

    def _add_action(self, street, pos, action, amount, amount_type='observed',
                    inferred=False, ambiguous=False):
        """Añade una acción a la calle con su semántica de importe explícita.

        `amount` siempre es el nivel absoluto comprometido en la calle. Si la
        lectura se reconstruyó desde el stack, `inferred` lo declara; nunca se
        persiste un incremento como si fuera el total.
        """
        if self.hand is None:
            return
        if amount_type != 'observed':
            raise ValueError(
                f'_add_action: los importes deben ser absolutos '
                f"(observed), recibido {amount_type!r}")
        self.hand['streets'][street]['actions'].append({
            'pos': pos, 'action': action, 'amount': round(amount, 2),
            'amount_type': amount_type,
            **({'inferred': True} if inferred else {}),
            **({'ambiguous': True} if ambiguous else {}),
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
        self._inferred_action_keys = set()
        self._ambiguous_action_keys = set()
        self._award_display_pids = set()

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

            prev_stake = (self._adjusted_last_state or self.last_state).get(f'{pid}_stake')
            cur_stake = state.get(f'{pid}_stake')
            cur_st = state.get(f'{pid}_state')
            prev_bet = (0.0 if self._just_changed_street else
                        ((self._adjusted_last_state or self.last_state).get(f'{pid}_bet') or 0))
            raw_cur_bet = state.get(f'{pid}_bet')
            cur_bet = raw_cur_bet or 0

            was_active = prev_stake is not None
            dimmed = cur_st in ('retirarse', 'ausente', 'inactivo', 'sin jugador', 'fuera')

            # ---- All-in: el stake pasó de x a None (jugador activo, sin fold) ----
            # Se detecta primero porque el all-in deja el stack en None.
            if was_active and cur_stake is None and not dimmed:
                amt = round((prev_stake or 0) + prev_bet, 2)
                if amt <= 0:
                    continue
                self._allin_players.add(pid)
                if not has_bet:
                    atype = 'b'
                elif amt <= run_max + 0.15:
                    atype = 'c'
                else:
                    atype = 'r'
                if not self._dup(street, pos_name, amt):
                    actions.append((street, pos_name, atype, round(amt, 2)))
                    self._inferred_action_keys.add((street, pos_name, round(amt, 2)))
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

            # El saldo subió: es un premio o una devolución, no una apuesta.
            # En particular, el premio suele aparecer en la casilla de bet.
            if (prev_stake is not None and cur_stake is not None
                    and cur_stake > prev_stake + 0.05):
                self._award_display_pids.add(pid)
                self._award_display_events[pid] = {
                    'street': street, 'pos': pos_name,
                    'stack_before': round(float(prev_stake), 2),
                    'stack_after': round(float(cur_stake), 2),
                    'bet_display_ignored': round(float(cur_bet or 0.0), 2),
                }
                returned = cur_stake - prev_stake
                if prev_bet > 0 and cur_bet < prev_bet:
                    self._returned_by_pos[(street, pos_name)] = round(
                        self._returned_by_pos.get((street, pos_name), 0.0)
                        + min(returned, prev_bet - cur_bet), 2)
                continue

            # ---- Dinero comprometido: el stake bajó (bet / call / raise) ----
            if cur_stake is not None:
                delta = round((prev_stake or 0) - cur_stake, 2)
                if delta > 0.05:
                    stack_level = round(prev_bet + delta, 2)
                    bet_matches_stack = (raw_cur_bet is not None and
                                         abs(float(raw_cur_bet) - stack_level)
                                         <= self._ambiguity_tolerance())
                    if bet_matches_stack:
                        amt = round(cur_bet, 2)
                    else:
                        amt = stack_level
                        self._inferred_action_keys.add((street, pos_name, amt))
                        if raw_cur_bet is not None and abs(
                                float(raw_cur_bet) - stack_level) > self._ambiguity_tolerance():
                            self._add_ambiguity(
                                'bet_vs_stack_disagreement', street, pos=pos_name,
                                bet_read=round(float(raw_cur_bet), 2),
                                bet_before=prev_bet, stack_delta=delta,
                                absolute_from_stack=stack_level,
                                difference=round(abs(float(raw_cur_bet) - stack_level), 2))
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

        inferred = [a for a in actions
                    if (a[0], a[1], round(a[3], 2)) in self._inferred_action_keys]
        inferred_types = {a[2] for a in inferred}
        if len(inferred) >= 2 and 'b' in inferred_types and 'c' in inferred_types:
            keys = {(a[0], a[1], round(a[3], 2)) for a in inferred}
            self._ambiguous_action_keys.update(keys)
            self._add_ambiguity(
                'bet_call_order_inferred', street,
                positions=[a[1] for a in inferred],
                actions=[a[2] for a in inferred],
                note='La secuencia bet/call se infirió de stacks; no se observó el orden.')

        # Público actualizado de la ronda para los siguientes frames
        self.street_has_bet = has_bet
        self._just_changed_street = False
        self._adjusted_last_state = None
        self._carryover_calls = {}
        if street != 'preflop' or run_max > getattr(self, '_preflop_current_bet', 0.0):
            self._preflop_current_bet = run_max

        return actions

    def _ambiguity_tolerance(self):
        return 0.2 * float(self._blind_bb or 1.0)

    def _dup(self, street, pos_name, amt, tol=0.05):
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
            key = (s, pos, round(amt, 2))
            self._add_action(
                s, pos, a, amt, 'observed',
                inferred=key in self._inferred_action_keys,
                ambiguous=key in self._ambiguous_action_keys)
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

    def _settle_pending_bets(self, street, prev_state, cur_state):
        """Cierra en la calle anterior los calls/folds que ocurrieron en el
        frame de transición.

        Cuando la captura salta de calle, el primer frame de la calle nueva
        puede mostrar ya el stack descontado por:
          - el call que completaba la apuesta de la calle anterior, y
          - la apuesta propia de la calle nueva.

        Si no se separan, ambos importes se suman y la calle nueva recibe un
        bet inflado. Aquí se registra la parte del call en la calle anterior y
        se devuelve cuánto hay que descontar del delta de la calle nueva.
        """
        carryover = {}
        if self.hand is None or prev_state is None or cur_state is None:
            return carryover
        max_level = self._get_max_bet(street)
        if max_level is None or max_level <= 0:
            return carryover
        contributions = self._street_contributions(street)
        pos_map = self._get_pos_map(prev_state)
        actions = self.hand['streets'][street].setdefault('actions', [])

        def already_has(pos, kind, amount=None):
            for action in actions:
                if action.get('pos') != pos or action.get('action') != kind:
                    continue
                if amount is None or abs(float(action.get('amount') or 0.0) - amount) < 0.05:
                    return True
            return False

        for pos in self._get_street_order(None, street):
            pid = pos_map.get(pos)
            if not pid or pid in self._inactive_players:
                continue
            if pos in self._folded_positions or pid in self._allin_players:
                continue
            # Si ni siquiera estaba en la mano al cerrar la calle, no hay
            # nada que completar.
            if prev_state.get(f'{pid}_stake') is None and not prev_state.get(f'{pid}_bet'):
                continue
            already = contributions.get(pos, 0.0)
            pending = round(max_level - already, 2)
            if pending <= 0.05:
                continue

            cur_stake = cur_state.get(f'{pid}_stake')
            cur_st = cur_state.get(f'{pid}_state')
            dimmed = cur_st in ('retirarse', 'ausente', 'inactivo',
                                'sin jugador', 'fuera')
            prev_stake = prev_state.get(f'{pid}_stake')
            drop = round((prev_stake or 0) - (cur_stake or 0), 2) \
                if cur_stake is not None else None

            if dimmed:
                if drop is not None and drop + 0.05 >= pending:
                    # Completó la apuesta de la calle anterior y el fold es de
                    # la calle nueva: se registra el call aquí y se deja que
                    # `_detect_deltas` registre el fold en su calle.
                    if not already_has(pos, 'c', max_level):
                        self.hand['streets'][street]['actions'].append({
                            'pos': pos, 'action': 'c',
                            'amount': round(max_level, 2),
                            'amount_type': 'observed', 'inferred': True,
                            'ambiguous': True})
                    carryover[pos] = pending
                    self._add_ambiguity(
                        'pending_call_before_fold', street, pos=pos,
                        amount=round(max_level, 2),
                        note='Completó la calle anterior; el fold pertenece a '
                             'la calle siguiente.')
                else:
                    # Fold en la calle anterior: no llegó a igualar.
                    if not already_has(pos, 'f'):
                        self.hand['streets'][street]['actions'].append({
                            'pos': pos, 'action': 'f', 'amount': 0.0,
                            'amount_type': 'observed', 'inferred': True,
                            'ambiguous': True})
                        self._folded_positions.add(pos)
                continue

            if cur_stake is not None and drop + 0.05 < pending:
                # No hay evidencia de que completara la apuesta: mejor no
                # inventar un call.
                continue

            if not already_has(pos, 'c', max_level):
                self.hand['streets'][street]['actions'].append({
                    'pos': pos, 'action': 'c', 'amount': round(max_level, 2),
                    'amount_type': 'observed', 'inferred': True,
                    'ambiguous': True})
            carryover[pos] = pending
            self._add_ambiguity(
                'pending_call_settled_on_previous_street', street, pos=pos,
                amount=round(max_level, 2),
                note='Call completado en el frame de cambio de calle; se '
                     'contabiliza en la calle anterior.')

        return carryover

    def change_street(self, new_street, state, carryover=False):
        prev_street = self.hand['current_street']
        prev_state = self.last_state or state
        cards = self._get_com_list(state)
        visible = [c for c in cards if c]
        self.hand.setdefault('comunitarias', {})
        if new_street == 'flop':
            self.hand['comunitarias']['flop'] = visible[:3]
            self.hand['streets']['flop']['board'] = visible[:3]
        elif new_street == 'turn':
            card = visible[3] if len(visible) > 3 else ''
            self.hand['comunitarias']['turn'] = [card] if card else []
            self.hand['streets']['turn']['board'] = [card] if card else []
        elif new_street == 'river':
            card = visible[4] if len(visible) > 4 else ''
            self.hand['comunitarias']['river'] = [card] if card else []
            self.hand['streets']['river']['board'] = [card] if card else []

        pending = self._settle_pending_bets(prev_street, prev_state, state)
        if carryover and pending:
            # El primer frame de la calle nueva ya incluye el call pendiente;
            # se descuenta para no sumarlo a la apuesta nueva.
            adjusted = dict(prev_state)
            pos_map = self._get_pos_map(prev_state)
            for pos, amount in pending.items():
                pid = pos_map.get(pos)
                if not pid:
                    continue
                stake = adjusted.get(f'{pid}_stake')
                if stake is not None:
                    adjusted[f'{pid}_stake'] = round(max(0.0, stake - amount), 2)
            self._adjusted_last_state = adjusted
            self._carryover_calls = pending

        # Confirmación de "todos fallaron chequeo": se mide con el último
        # frame de la calle anterior, no con el frame que ya pertenece a la
        # calle nueva.
        now_pot = prev_state.get('pot') or 0
        confirm_all_check = prev_street != 'preflop' \
            and abs(now_pot - (getattr(self, '_street_pot', 0) or 0)) < 0.15
        self._finalize_street(prev_street, prev_state,
                              confirm_all_check=confirm_all_check)
        self._completed_streets.add(prev_street)
        self._street_pot = now_pot
        self.hand['current_street'] = new_street
        self.street_has_bet = False
        self._just_changed_street = True

    def _finalize_street(self, street_name, state=None, confirm_all_check=False):
        if street_name in self._completed_streets:
            # Ya cerrada: no volver a inferir ni reordenar acciones. Evita que
            # un frame posterior reescriba folds/calls de una calle pasada.
            return
        # Add implied checks first (modifies the list in place via re-assign)
        if state is not None:
            self._add_implied_checks(street_name, state, confirm_all_check=confirm_all_check)

        actions = self.hand['streets'][street_name].setdefault('actions', [])
        if not actions:
            return

        ORDER = self._get_street_order(None, street_name)
        pos_ord = {p: i for i, p in enumerate(ORDER)}

        blind_posts = []
        if street_name == 'preflop':
            rest = []
            for a in actions:
                if a['action'] == 'p':
                    blind_posts.append(a)
                else:
                    rest.append(a)
            actions[:] = rest

        # Merge consecutive same-position actions
        merged = []
        for a in actions:
            if merged and merged[-1]['pos'] == a['pos'] and a['action'] in ('c', 'b'):
                # Importes absolutos: una actualización de la misma acción
                # sustituye el nivel, nunca se suma como si fuera un delta.
                merged[-1]['amount'] = max(merged[-1]['amount'], a['amount'])
                if a['action'] in ('b', 'r'):
                    merged[-1]['action'] = a['action']
                for flag in ('inferred', 'ambiguous'):
                    if a.get(flag):
                        merged[-1][flag] = True
            else:
                merged.append(dict(a))
        actions[:] = merged

        if not actions and not blind_posts:
            return

        checks = [a for a in actions if a['action'] == 'x']
        non_checks = [a for a in actions if a['action'] != 'x']

        # Preflop sin subidas: si la acción dio la vuelta y volvió al BB
        # (hay al menos un call) y el BB sigue vivo sin haber actuado desde
        # la ciega, el BB pasó la opción -> 'x' cerrando la ronda.
        if street_name == 'preflop' and blind_posts:
            has_raise = any(a['action'] == 'r' for a in actions)
            bb_acted = any(a['pos'] == 'BB' for a in actions)
            has_call = any(a['action'] == 'c' for a in actions)
            bb_alive = 'BB' not in self._folded_positions
            bb_checked = any(a['pos'] == 'BB' and a['action'] == 'x'
                             for a in actions)
            if (not has_raise and not bb_acted and has_call
                    and bb_alive and not bb_checked):
                actions.append({'pos': 'BB', 'action': 'x', 'amount': 0.0,
                                'inferred': True, 'ambiguous': True})
                checks = [a for a in actions if a['action'] == 'x']
                non_checks = [a for a in actions if a['action'] != 'x']

        bettor_pos = None
        for a in non_checks:
            if a['action'] in ('b', 'r'):
                bettor_pos = a['pos']
                break

        checks.sort(key=lambda a: pos_ord.get(a['pos'], 99))

        head = blind_posts

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
                checks.append({'pos': pos, 'action': 'x', 'amount': 0.0,
                               'inferred': True, 'ambiguous': True})
        if checks and street_name != 'preflop':
            existing[0:0] = checks

    # ---------- finalizar mano ----------

    def finalize_hand(self, state):
        self._finalize_street(self.hand['current_street'], state)
        live_players = [p for p in self.hand['players']
                        if p.get('active') and p.get('pos')
                        and p.get('pos') not in self._folded_positions
                        and p['_id'] not in self._inactive_players
                        and (not state or state.get(f'{p["_id"]}_state')
                             not in ('retirarse', 'ausente'))]
        fold_win = len(live_players) <= 1
        breakdown = self._pot_breakdown(final=True, fold_win=fold_win)
        pot_read = (state.get('pot') if state else None)
        if pot_read is None and state:
            pot_read = state.get('pot_wide')
        calculated = breakdown['pot_calculated']
        noninflated = breakdown['pot_calculated_noninflated']
        resolution = 'calculated'
        if pot_read is not None:
            pot_read = round(float(pot_read), 2)
            tol = self._ambiguity_tolerance()
            if (fold_win and abs(pot_read - noninflated) <= tol
                    and abs(pot_read - calculated) > 0.005):
                # La pantalla muestra el bote igualado; el formato histórico
                # de una victoria por fold conserva además la última apuesta
                # no igualada (sin cobrar rake sobre ese excedente).
                resolution = 'read_noninflated_to_inflated'
            elif abs(pot_read - calculated) <= tol:
                resolution = 'read_confirms_calculated'
            else:
                resolution = 'ambiguous_read_mismatch'
                self._add_ambiguity(
                    'pot_read_vs_calculated', self.hand.get('current_street'),
                    pot_read=pot_read, pot_calculated=calculated,
                    pot_calculated_noninflated=noninflated,
                    fold_win=fold_win,
                    difference=round(abs(pot_read - calculated), 2))
        self.hand['final_pot'] = calculated

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

        ambiguous_actions = [
            {'street': street,
             'pos': action.get('pos'),
             'action': action.get('action'),
             'amount': action.get('amount'),
             'inferred': bool(action.get('inferred'))}
            for street, data in (self.hand.get('streets') or {}).items()
            for action in (data or {}).get('actions') or []
            if action.get('ambiguous')]
        self.hand['recorder_audit'] = {
            'ambiguous': bool(self._hand_ambiguities or ambiguous_actions),
            'ambiguities': list(self._hand_ambiguities),
            'ambiguous_actions': ambiguous_actions,
            'pot_read': pot_read,
            'pot_calculated': calculated,
            'pot_calculated_noninflated': noninflated,
            'pot_resolution': resolution,
            'gross_contributions': breakdown['gross_contributions'],
            'matched_contributions': breakdown['matched_contributions'],
            'uncalled': breakdown['uncalled'],
            'rake_basis': breakdown['rake_basis'],
            'rake': breakdown['rake'],
            'big_blind': round(float(self._blind_bb or 1.0), 2),
            'rake_cap': round(2.5 * float(self._blind_bb or 1.0), 2),
            'ambiguity_tolerance': round(self._ambiguity_tolerance(), 2),
            'fold_win': fold_win,
            'award_display_ignored': list(self._award_display_events.values()),
        }
        out = {k: v for k, v in self.hand.items()
               if k not in ('current_street', 'max_pot')}
        # INC-002: `p['active']` significa "estaba sentado al empezar la
        # mano", NO "no ha foldeado". Sin este filtro extra, un jugador que
        # se compromete y despues foldea se queda en `allin` (caso H_0851,
        # 1 de 138 entradas en la ventana fiable). El clasificador lo creeria
        # y declararia bloqueado a alguien que ya se fue. Arreglo hacia
        # adelante: las manos ya grabadas no se tocan.
        out['allin'] = [p['_id'] for p in self.hand['players']
                        if p['_id'] in self._allin_players and p['active']
                        and p['pos'] not in self._folded_positions]
        for p in out['players']:
            del p['_id']

        output_dir = os.path.dirname(os.path.abspath(self.output_path))
        os.makedirs(output_dir, exist_ok=True)
        with open(self.output_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(out) + '\n')

        self._record_session_result(out)

        if self.on_hand_finalized is not None:
            try:
                self.on_hand_finalized(out)
            except Exception as e:
                log = getattr(self, '_last_log', print)
                log(f'  [decision-log] no se pudo resolver H_{self.hand_id:04d}: {e}')

        log = getattr(self, '_last_log', print)
        log(f'  -> Saved H_{self.hand_id:04d}')
        if out['recorder_audit']['ambiguous']:
            log('  [AMBIGUO] ' + ', '.join(
                x.get('code', '?') for x in out['recorder_audit']['ambiguities']))
        log('  [bote] calculado=%s leido=%s rake=%s' % (
            calculated, pot_read, breakdown['rake']))
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
            self.save_frame(state, img_arr, log=log)
            self.last_state = state
            self.last_img = img_arr
            return

        award_candidates = self._award_overlay_candidates(state)
        if self._is_new_hand(state):
            if self.hand is not None:
                log(f'H_{self.hand_id:04d}: replaced by new hand')
                for pid, values in award_candidates.items():
                    self._award_display_events[pid] = {
                        'street': self.hand.get('current_street'),
                        'pos': self._get_pid_map(state).get(pid),
                        'stack_before': round(float(values['before']), 2),
                        'stack_after': round(float(values['after']), 2),
                        'bet_display_ignored': round(float(values['bet']), 2),
                    }
                self.finalize_hand(self.last_state)
            state = self._without_award_bet_overlay(state, award_candidates)
            self._assign_cards_by_name(state)
            self.start_hand(state)
            log(f'H_{self.hand_id:04d}: started')
            for a in self.hand['streets']['preflop']['actions']:
                log(f'  preflop: {a["pos"]} {a["action"]} {a["amount"]}')

        self.save_frame(state, img_arr, log=log)

        if self.hand is not None:
            # Aplicar inactivos manuales del GUI (inmediatamente, cualquier calle)
            pid_map_cur = self._get_pid_map(state)
            for pid in MANUAL_INACTIVE:
                if pid not in self._inactive_players:
                    pos_name = pid_map_cur.get(pid)
                    self._mark_inactive(pid, pos_name)

            # 0. Detectar jugadores inactivos antes de procesar acciones
            self._detect_inactive(state)

            if self.hand is not None:
                target = self._target_street(state)
                if self._street_rank(target) > self._street_rank(self.hand['current_street']) + 1:
                    self._handle_street_jump(target, state, log)
            cur = self.hand['current_street']
            ns = self.detect_street_change(state)
            new_street_has_bets = bool(ns and self._new_street_bets_visible(state))

            if ns and new_street_has_bets:
                log(f'  >> {ns}')
                self.change_street(ns, state, carryover=True)
                if not self._is_effectively_over(state):
                    actions = self.detect_actions(state)
                    for a in actions:
                        log(f'  {ns}: {a[1]} {a[2]} {a[3]}')
                    self.process_street_labels(state, ns)
                else:
                    log('  (all-in: no actions)')
            else:
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

            hand_over = self._is_hand_over(state)
            if not hand_over:
                self._audit_live_pot(state)
            # 4. Conservar el frame de pago para distinguir el premio mostrado
            # sobre la casilla de apuestas.
            if hand_over:
                log(f'H_{self.hand_id:04d}: ended')
                self.finalize_hand(state)

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
