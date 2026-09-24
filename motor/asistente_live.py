"""asistente_live.py — asistente de póker en vivo (2 perfiles: PEZ/TIBURON).

Pipeline en cada pantallazo (polling ~0.5 s):
    capture_live.capture()
        → lectores (cartas hero + community, stacks, bets, bote, BTN, estados)
        → RANGO RIVAL por perfil en vivo (PEZ si stack < 50 BB, si no TIBURON):
            rango preflop (grid 13×13 por perfil) + blockers (hero+board)
            + actualizaciones postflop con P(A|H, street, facing) del rival
        → Situation (equity, SPR, pot-odds, textura)
        → EV por acción (fold/check/call/bet25/50/75/all_in)
        → RECOMENDACIÓN: "haz X (+Y BB)"
    En paralelo, el LiveRecorder registra la mano completa en
    data/hands_db.jsonl (base para el reentrenamiento offline).

El asistente NUNCA ejecuta por sí solo: solo recomienda; el humano decide.

Uso:  python -m motor.asistente_live [--poll 0.5] [--hero-nombre Jarduan]
"""
import os
import random
import sys
import time

import numpy as np

_pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('tools', 'recorder'):
    sys.path.insert(0, os.path.join(_pkg_root, sub))
from capture_live import capture, get_readers
from recorder_live import LiveRecorder, POSITION_ORDER

from .behavior import Oracle, build
from .cards import card_id
from .decision import EvTable, OracleResponse, compute_evs
from .learn import load_hands
from .observations import _texture_class, lead_label
from .panel import format_insight
from .player_ranges import ProfileRangeModel
from .postflop_ranges import PostflopRangeModel
from .preflop import load_tables
from .profile import PEZ, Profiles, TIBURON, STACK_FISH_BB
from .ranges import COMBO0, COMBO1, RangeState
from .rules import plan as rules_plan
from .rules import select_best as rules_select_best
from .situation import Situation, situation
from .hand_state import classify as hand_classify
from .hand_state import range_advantage as range_adv

POLL_DEFAULT = 0.5
HERO_NAME_DEFAULT = 'Jarduan'

HERO_PID = 'hero'
PLAYER_IDS = ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']
_DEFAULT_NAMES = {'hero': 'Hero', 'p1': 'Player1', 'p2': 'Player2',
                  'p3': 'Player3', 'p4': 'Player4', 'p5': 'Player5'}


def _is_default_names(names):
    try:
        return all(names.get(k) == v for k, v in _DEFAULT_NAMES.items())
    except Exception:
        return True

# Botones de acción que indican "turno de hero" (el resto = inactivo/fold)
HERO_ACTION_LABELS = {'igualar', 'subir', 'pasar', 'apostar',
                      'apostar todo', 'mostrar cartas'}


# ---------------------------------------------------------------------------
# utilidades de estado / cartas
# ---------------------------------------------------------------------------

def _cards_to_codes(cards):
    """[{'rank','suit'}] → ['As','Kd'] (o '' si no se detectó)."""
    if isinstance(cards, str):
        return [cards[i:i + 2] for i in range(0, len(cards), 2)]
    out = []
    for c in (cards or []):
        if isinstance(c, dict):
            r, s = c.get('rank', ''), c.get('suit', '')
            if r and s:
                out.append(f'{r}{s}')
        elif isinstance(c, str) and len(c) >= 2:
            out.append(c[:2])
    return out


def _hero_cards(state):
    cards = _cards_to_codes(state.get('hero_cards'))
    return [c for c in cards if c][:2]


def _board_codes(state):
    return [c for c in _cards_to_codes(state.get('community')) if c][:5]


def _street_of(n_coms):
    if n_coms >= 5:
        return 'river'
    if n_coms >= 4:
        return 'turn'
    if n_coms >= 3:
        return 'flop'
    return 'preflop'


# ---------------------------------------------------------------------------
# Preflop del rival → spot/acción del rango inicial
# ---------------------------------------------------------------------------

def _preflop_spot(hand, villain_pos):
    """(spot, action) del rango inicial del rival según lo que hizo preflop.

    'b' → open (no_raise/open); 'r' → 3bet (facing_open/3bet);
    'c' → call a open (facing_open/call_open); 'x' → BB check (no_raise/limp);
    sin acción → open por posición (no_raise/open).
    """
    if hand is not None:
        acts = (hand.get('streets', {}).get('preflop', {}) or {})
        for a in reversed(acts.get('actions', [])):
            if a.get('pos') != villain_pos:
                continue
            action = a.get('action')
            if action == 'b':
                return 'no_raise', 'open'
            if action == 'r':
                return 'facing_open', '3bet'
            if action == 'c':
                return 'facing_open', 'call_open'
            if action == 'x':
                return 'no_raise', 'limp'
            return 'no_raise', 'open'
    return 'no_raise', 'open'


def _villain_postflop_actions(hand, villain_pos):
    """[(street, facing, action, board)] de acciones ya observadas del rival
    por calle (formato que consume postflop.prob_vec), para actualizar su rango.

    Usa lead_label() (observations) para que los leads caigan en las MISMA
    celdas del entrenamiento: la apuesta propia del rival (sin apuesta
    vigente) se etiqueta facing 'none', y las respuestas usan el label del
    lead ('cbet'/'donk'/'barrel'/'bet'/'raise')."""
    if hand is None:
        return []
    out = []
    streets = hand.get('streets', {})
    pf_acts = (streets.get('preflop', {}) or {}).get('actions', [])
    pf_initiator = next((a.get('pos') for a in reversed(pf_acts)
                         if a.get('action') in ('b', 'r')), '')
    pot_raised = bool(pf_initiator)
    for street in ('flop', 'turn', 'river'):
        acts = (streets.get(street, {}) or {}).get('actions', [])
        board = streets.get(street, {}).get('board', [])
        board_str = ','.join(str(c) for c in board) if board else ''
        facing = ''
        for a in acts:
            pos, action = a.get('pos'), a.get('action')
            if action == 'x':
                continue
            if pos == villain_pos and action in ('b', 'c', 'r', 'f'):
                out.append((street, facing or 'none', action, board_str))
            if action in ('b', 'r'):
                facing = ('raise' if facing else
                          lead_label(street, pos, pf_initiator, pot_raised))
    return out


_POSTFLOP_ORDER = POSITION_ORDER[1:] + POSITION_ORDER[:1]  # SB,BB,CO,MP,UTG,BTN


def _is_hero_pos(pos, hero_pos):
    """¿La posición 'pos' (acción grabada) es la del hero? Acepta el asiento
    sintético 'hero' y la posición de mesa real (el recorder guarda posiciones
    como 'CO'/'BTN')."""
    return pos in (HERO_PID, hero_pos)


def _hero_oop(hero_pos, villain_pos, flop_acts):
    """¿Hero actúa primero postflop vs el rival (OOP)?

    Prioriza el orden real de las acciones del flop; si aún no hay acciones,
    usa el orden relativo de posición (el primero en actuar tras el BTN es
    OOP; el BTN actúa último). Desconocido → False (conservador: el donk
    exige OOP, §3 del doc).
    """
    if flop_acts:
        return bool(_is_hero_pos((flop_acts[0] or {}).get('pos'), hero_pos))
    try:
        return (_POSTFLOP_ORDER.index(hero_pos)
                < _POSTFLOP_ORDER.index(villain_pos))
    except (ValueError, TypeError):
        return False


def _hero_is_initiator(hand, hero_pos):
    """¿Hero es el último agresor preflop? (el que iniciaría el beater).

    Compara por posición de mesa (el recorder graba 'CO'/'BTN'...) o por el
    asiento sintético 'hero'; nunca debe asumir el asiento físico."""
    if hand is None:
        return False
    acts = (hand.get('streets', {}).get('preflop', {}) or {}).get('actions', [])
    last = next((a.get('pos') for a in reversed(acts)
                 if a.get('action') in ('b', 'r')), '')
    return _is_hero_pos(last, hero_pos)


def _hand_was_raised(hand):
    """¿Bote subido preflop (no limpeado)? Cualquier 'b'/'r' preflop
    (incluye el blind del BB en aperturas) cuenta como subida."""
    if hand is None:
        return False
    acts = (hand.get('streets', {}).get('preflop', {}) or {}).get('actions', [])
    return any(a.get('action') in ('b', 'r') for a in acts)


def _hero_bet_facing(street, is_initiator, pot_raised=False):
    """Facing que ve el rival ante una apuesta del hero (observations):
    'cbet' si hero es iniciador en flop, 'barrel' en turn, 'donk' si el hero
    lidera sin ser iniciador en bote subido (flop/turn), 'bet' si no."""
    if street in ('flop', 'turn') and not is_initiator and pot_raised:
        return 'donk'
    if is_initiator and street == 'flop':
        return 'cbet'
    if is_initiator and street == 'turn':
        return 'barrel'
    return 'bet'


# ---------------------------------------------------------------------------
# Preflop del hero → recomendación desde las matrices preflop
# ---------------------------------------------------------------------------

def _combo_index(hero_codes):
    """['6c', '4s'] → índice del combo 0..1325 (None si no resuelve)."""
    try:
        a, b = sorted((card_id(c) for c in hero_codes))
    except Exception:
        return None
    hits = np.where((COMBO0 == a) & (COMBO1 == b))[0]
    return int(hits[0]) if len(hits) else None


def _pf_table_probs(base, hero_pos='', vs_pos=''):
    """Vector P(A|H) (1326,) de la matriz `base` más específica disponible:
    `BASE_{hero}_vs_{vs}` → `BASE_{hero}` → None.

    No se usa ninguna tabla de otra posición (ni el residuo por `action`);
    si no existe la tabla exacta para la posición del hero, devuelve None
    para no inventar frecuencias ajenas a las tablas (preflop_matrices.json).
    """
    tables = load_tables()
    if hero_pos and vs_pos:
        t = tables.get(f'{base}_{hero_pos}_vs_{vs_pos}')
        if t is not None:
            return t['probs']
    if hero_pos:
        for t in tables.values():
            if t['action'] == base and t['pos'] == hero_pos:
                return t['probs']
    return None


def _pf_freq(base, hero_pos, vs_pos, hand_idx):
    probs = _pf_table_probs(base, hero_pos, vs_pos)
    if probs is None or hand_idx is None:
        return None
    return float(probs[hand_idx])


def _preflop_raises(actions, hero_pos):
    """(n_raises, vs_pos, vs_amount) de los raises que el hero aún debe
    enfrentar: acciones 'r' (el blind BB se registra como 'b' y se ignora)"""
    n, vs_pos, vs_amount = 0, '', 0.0
    for a in actions:
        if a.get('pos') == hero_pos:
            continue
        if a.get('action') == 'r':
            n += 1
            vs_pos = a.get('pos') or vs_pos
            vs_amount = a.get('amount') or vs_amount
    return n, vs_pos, vs_amount


def _pf_evs(f_raise, f_call):
    """Frecuencias preflop como rango ponderado que suma 1 (100%).

    Las frecuencias de raise y call vienen de matrices INDEPENDIENTES y una
    misma mano puede quedar por encima del 100% en ambas; en ese caso se
    escalan proporcionalmente para que subir + igualar + retirar = 1 (el
    fold queda en 0). Nunca se muestra una suma > 100%. El argmax = la
    acción más jugada = recomendación."""
    fr = f_raise or 0.0
    fc = f_call or 0.0
    total = fr + fc
    if total > 1.0:
        fr, fc = fr / total, fc / total
    return {'retirar': 1.0 - fr - fc, 'igualar': fc, 'subir': fr}


def _format_preflop(hero, hero_pos, label_spot, pot, to_call, ev, action,
                    perfil_label):
    rule = '=' * max(len(f'{hero} | preflop | {hero_pos}'), 30)
    lines = [
        rule,
        f'== {hero} | preflop | {hero_pos}',
        f'  Rival: {perfil_label}',
        f'  Spot : {label_spot}   (pot {pot:.1f}, a pagar {to_call:.1f})',
    ]
    for name in ('subir', 'igualar', 'retirar', 'pasar'):
        if name in ev:
            lines.append(f'  {name:8s} {ev[name]:6.1%}')
    lines += [f'-> Mejor accion: {action}', rule]
    return '\n'.join(lines)

# ---------------------------------------------------------------------------
# Modelos del asistente (perfiles PEZ/TIBURON desde hands_db)
# ---------------------------------------------------------------------------

def build_models(verbose=True):
    """Construye los modelos de 2 perfiles desde data/hands_db.jsonl.

    labels          {jugador: 'PEZ'|'TIBURON'}   (regla stack < 50 BB)
    range_model     ProfileRangeModel  (P(A|H) preflop por perfil)
    oracle          Oracle             (P(A|C) postflop por perfil)
    postflop_model  PostflopRangeModel (P(A|H) postflop por perfil)
    """
    hands = load_hands()
    profs = Profiles.from_hands(hands)
    labels = {name: p.label for name, p in profs.profiles.items()}
    t0 = time.perf_counter()
    range_model = ProfileRangeModel.from_hands(hands, labels=labels)
    oracle = Oracle(build(hands, labels=labels))
    postflop_model = PostflopRangeModel.from_hands(hands, labels=labels)
    postflop_model._oracle = oracle          # reutiliza el Oracle
    dt = (time.perf_counter() - t0) * 1000
    if verbose:
        n_pez = sum(1 for l in labels.values() if l == PEZ)
        n_tib = sum(1 for l in labels.values() if l == TIBURON)
        print(f'  modelos 2 perfiles: {n_pez} PEZ / {n_tib} TIBURON '
              f'· {len(hands)} manos · build {dt:.0f} ms')
    return _Models(labels=labels, range_model=range_model,
                   oracle=oracle, postflop_model=postflop_model)


class _Models:
    def __init__(self, labels, range_model, oracle, postflop_model):
        self.labels = labels
        self.range_model = range_model
        self.oracle = oracle
        self.postflop_model = postflop_model


# ---------------------------------------------------------------------------
# Asistente en vivo
# ---------------------------------------------------------------------------

class Asistente:
    def __init__(self, models=None, hero_name=HERO_NAME_DEFAULT,
                 poll_s=POLL_DEFAULT, verbose=True):
        self.models = models or build_models(verbose=verbose)
        self.oracle = self.models.oracle
        self.poll = poll_s
        self.hero_name = hero_name
        self.verbose = verbose
        self.reader, _ = get_readers()

        # Recorder para registro continuo (guardar manos en hands_db.jsonl)
        self.rec = LiveRecorder()
        module = sys.modules.get('recorder_live')
        if module is not None and _is_default_names(module.PLAYER_NAMES):
            module.PLAYER_NAMES = {
                'hero': hero_name,
                'p1': 'P1', 'p2': 'P2', 'p3': 'P3', 'p4': 'P4', 'p5': 'P5',
            }

        self.last_reco_key = None
        self.last_state = None
        self.last_img = None
        self.runout = True
        # Perfilado en vivo: stacks observados por jugador durante la sesión
        # (para "juega mayoritariamente por debajo de 50 ciegas", sin necesitar
        # coincidencia de nombres con el dataset).
        self.live_stacks = {}        # pid -> [stacks observados]
        self._last_seen_stake = {}   # pid -> último stack visto (dedup frames)

    # ------------------------------------------------------------------

    def _hero_pid(self):
        """pid del hero: primero el asiento cuyo nombre configurado sea
        'Jarduan' (hero_name), si no, el asiento 'hero'."""
        target = (getattr(self, 'hero_name', '') or HERO_NAME_DEFAULT).strip().lower()
        module = sys.modules.get('recorder_live')
        names = (getattr(module, 'PLAYER_NAMES', None) or {}) \
            if module is not None else {}
        for pid in PLAYER_IDS:
            if str(names.get(pid, '')).strip().lower() == target:
                return pid
        return HERO_PID

    def _hero_cards_of(self, state):
        """Cartas del hero desde el state: del asiento que ocupa el hero
        (si no es 'hero', el recorder las reasignó ahí al empezar la mano),
        con respaldo al OCR del asiento físico 'hero'."""
        hp = self._hero_pid()
        src = f'{hp}_cards' if hp != HERO_PID else 'hero_cards'
        cards = _cards_to_codes(state.get(src))
        if not cards and state.get('hero_cards'):
            cards = _cards_to_codes(state.get('hero_cards'))
        return [c for c in cards if c][:2]

    def _observe_stacks(self, state):
        """Acumula los stacks visibles por jugador (un registro por cambio)
        para el perfilado en vivo por media de la sesión."""
        for pid in PLAYER_IDS:
            s = state.get(f'{pid}_stake')
            if s is None or state.get(f'{pid}_state') != 'activo':
                continue
            if self._last_seen_stake.get(pid) == s:
                continue
            self._last_seen_stake[pid] = s
            self.live_stacks.setdefault(pid, []).append(s)

    def _live_mean(self, player_id):
        stacks = self.live_stacks.get(player_id)
        if not stacks:
            return None
        return sum(stacks) / len(stacks)

    def _perfil_for(self, player_id, state):
        """PEZ si juega MAYORITARIAMENTE por debajo de 50 BB:
        1) con historial de la sesión → media de stacks; 2) sin historial →
        stack actual; 3) sin información → TIBURON."""
        mean = self._live_mean(player_id)
        if mean is None:
            stake = state.get(f'{player_id}_stake')
            if stake is None:
                return TIBURON
            return PEZ if stake < STACK_FISH_BB else TIBURON
        return PEZ if mean < STACK_FISH_BB else TIBURON

    def _villain_name(self, villain_id):
        """Nombre configurado en la GUI (si lo hay) para la etiqueta del rival."""
        module = sys.modules.get('recorder_live')
        if module is None:
            return villain_id
        name = (module.PLAYER_NAMES or {}).get(villain_id, '')
        if name and name.upper() != villain_id.upper():
            return name
        return villain_id

    def _villain_id(self, state):
        """Rival para recomendar: si el hero ENFRENTA una apuesta, quien la
        hizo (máximo {pid}_bet → el agresor real; su rango estrecha de
        verdad la equity). Si el hero apuesta (to_call=0), el activo de
        mayor stack (rival principal para value)."""
        hero_pid = self._hero_pid()
        hero_bet = state.get(f'{hero_pid}_bet') or 0.0
        max_bet, aggressor = 0.0, None
        for pid in PLAYER_IDS:
            if pid == hero_pid:
                continue
            if state.get(f'{pid}_state') != 'activo':
                continue
            bet = state.get(f'{pid}_bet') or 0.0
            if bet > max_bet:
                max_bet, aggressor = bet, pid
        if max_bet > hero_bet and aggressor is not None:
            return aggressor
        best, best_stack = None, -1
        for pid in PLAYER_IDS:
            if pid == hero_pid:
                continue
            if state.get(f'{pid}_state') != 'activo':
                continue
            stake = state.get(f'{pid}_stake')
            if stake is None:
                continue
            if stake > best_stack:
                best, best_stack = pid, stake
        return best

    def _pos_of(self, pid, state):
        """Posición de un pid (del recorder, o por asiento si no hay mano)."""
        if self.rec.hand is not None and self.rec._hand_positions:
            return self.rec._hand_positions.get(pid)
        positions = self.rec._assign_positions(state)
        return positions.get(pid)

    def _hero_act(self, state, pil):
        """True si es el turno del hero.

        Primero intenta el botón de acción visible (StateMatcher); si el botón
        no se reconoce (o es None), cae a un fallback LÓGICO: hero activo +
        rival activo + bote > 0 (spot vivo)."""
        if state.get(f'{self._hero_pid()}_state') != 'activo':
            return False
        try:
            label = self.reader.sm.read(pil, self._hero_pid())
        except Exception:
            label = None
        if label in HERO_ACTION_LABELS:
            return True
        return self._hero_maybe_to_act(state)

    def _hero_maybe_to_act(self, state):
        """Fallback sin OCR de botones: hay un spot vivo pendiente."""
        if state.get(f'{self._hero_pid()}_state') != 'activo':
            return False
        if self._villain_id(state) is None:
            return False
        return (state.get('pot') or 0.0) > 0

    # ------------------------------------------------------------------

    def _max_bet(self, state):
        vals = [state.get(f'{p}_bet') or 0 for p in PLAYER_IDS]
        return max(vals)

    def _state_key(self, state):
        """Firma de la situación para deduplicar recomendaciones (incluye el
        hand_id para que una MANO NUEVA siempre recomiende de nuevo)."""
        hid = self.rec.hand.get('hand_id') if self.rec.hand is not None else ''
        return (hid, len(_board_codes(state)), (state.get('pot') or 0.0),
                (state.get(f'{self._hero_pid()}_bet') or 0.0),
                self._max_bet(state))

    # ------------------------------------------------------------------

    def _hero_cards_fallback(self):
        """Cartas del hero registradas al INICIO de la mano (fuente de verdad).

        Se congelan en `start_hand` y no cambian (ni siquiera con el OCR en
        vivo) hasta que la mano anterior se haya guardado (`rec.hand` None):
        tras un fold el OCR pueda leer basura que NO debe reescribir la mano."""
        h = self.rec.hand
        if h is None:
            return []
        hp = self._hero_pid()
        for p in h.get('players', []):
            if p.get('_id') == hp:
                cards = p.get('cards') or ''
                return [c for c in _cards_to_codes(cards) if c][:2]
        return []

    def _board_fallback(self):
        """Board del street actual registrado (si OCR no vio comunitarias)."""
        h = self.rec.hand
        if h is None:
            return []
        st = h.get('current_street', 'flop')
        s = (h.get('streets', {}) or {}).get(st, {}) or {}
        return [c for c in _cards_to_codes(s.get('board', [])) if c][:5]

    def _recom_preflop(self, state, hero, hero_pos, hero_bet, pot, to_call,
                       perfil, name, on_reco, verbose, seed=None):
        """Recomendación PREFLOP desde las matrices (data/preflop_matrices.json).

        Spot por las acciones previas: OR si nadie abrió, ROL si hay limp
        delante (fold implícito), 3B/Call_OR/4B/Call_3B/5B/Call_4B/Call_5B
        vs el último raiser. La acción se SORTEA con las frecuencias de la
        matriz (incluido el fold implícito del residuo 1 − Σ), no un argmax
        seco: ante "subir 40% / igualar 35% / fold 25%" puede sugerir las tres
        con esos pesos. Devuelve un EvTable con `preflop=True`, la acción
        sorteada en `evs.chosen` y las frecuencias en `ev` para el panel."""
        actions = []
        if self.rec.hand is not None:
            actions = (self.rec.hand.get('streets', {}).get('preflop', {})
                       or {}).get('actions', [])
        n_raises, vs_pos, vs_amount = _preflop_raises(actions, hero_pos)
        hand_idx = _combo_index(hero)
        if hand_idx is None:
            return None

        limp = False
        raise_seen = False
        for a in actions:
            if a.get('pos') == hero_pos:
                continue
            if a.get('action') == 'r':
                raise_seen = True
            elif a.get('action') == 'c' and not raise_seen:
                limp = True

        if n_raises == 0 and limp:
            # Limp delante → tabla ROL de la posición (el fold es el residuo)
            f_rol = _pf_freq('ROL', hero_pos, '', hand_idx) or 0.0
            if hero_pos == 'BB':
                ev = {'pasar': f_rol, 'subir': max(0.0, 1.0 - f_rol)}
                label_spot = f'vs limp (BB: pasar {f_rol:.0%} / subir {1 - f_rol:.0%})'
            else:
                ev = {'igualar': f_rol,
                      'retirar': max(0.0, 1.0 - f_rol)}
                label_spot = f'vs limp (over-limp {f_rol:.0%}, fold resto)'
        elif n_raises == 0:
            f_open = _pf_freq('OR', hero_pos, '', hand_idx)
            if f_open is None:
                # No hay tabla OR para la posición (p.ej. BB: nadie abrió y la
                # opción es pasar). No se inventa la tabla de otra posición.
                if hero_pos == 'BB' and to_call <= 0:
                    f_open = 0.0
                else:
                    return None
            if hero_pos == 'BB' and to_call <= 0:
                ev = {'pasar': max(0.0, 1.0 - f_open), 'subir': f_open}
            else:
                ev = {'retirar': max(0.0, 1.0 - f_open), 'subir': f_open}
            label_spot = 'apertura (sin raise previo)'
        elif n_raises == 1:
            f_r = _pf_freq('3B', hero_pos, vs_pos, hand_idx) or 0.0
            f_c = _pf_freq('Call_OR', hero_pos, vs_pos, hand_idx) or 0.0
            ev = _pf_evs(f_r, f_c)
            label_spot = f'vs apertura {vs_pos} ({vs_amount:.1f})'
        elif n_raises == 2:
            f_r = _pf_freq('4B', hero_pos, vs_pos, hand_idx) or 0.0
            f_c = _pf_freq('Call_3B', hero_pos, vs_pos, hand_idx) or 0.0
            ev = _pf_evs(f_r, f_c)
            label_spot = f'vs 3-bet {vs_pos} ({vs_amount:.1f})'
        elif n_raises == 3:
            f_r = _pf_freq('5B', hero_pos, vs_pos, hand_idx) or 0.0
            f_c = _pf_freq('Call_4B', hero_pos, vs_pos, hand_idx) or 0.0
            ev = _pf_evs(f_r, f_c)
            label_spot = f'vs 4-bet {vs_pos} ({vs_amount:.1f})'
        elif n_raises == 4:
            f_c = _pf_freq('Call_5B', hero_pos, vs_pos, hand_idx) or 0.0
            ev = {'igualar': f_c, 'retirar': max(0.0, 1.0 - f_c)}
            label_spot = f'vs 5-bet {vs_pos} ({vs_amount:.1f})'
        else:
            ev = {'retirar': 1.0, 'igualar': 0.0, 'subir': 0.0}
            label_spot = f'vs multi-raise {vs_pos}'

        # Sorteo ponderado por las frecuencias de la matriz (incluye el fold
        # implícito del residuo): la recomendación sigue la distribución del
        # spot, no el argmax seco. `seed` fijo → determinista (tests).
        rng = random.Random(seed) if seed is not None else random
        acts = [a for a, v in ev.items() if v > 0.0]
        action = rng.choices(acts, weights=[ev[a] for a in acts])[0] \
            if acts else 'retirar'

        evs = EvTable(ev=ev, pot=pot, hero_equity=0.0)
        evs.preflop = True
        evs.chosen = action
        label = f'{perfil} {name}'
        text = _format_preflop(' '.join(hero), hero_pos, label_spot, pot,
                               to_call, ev, action, label)
        if on_reco is not None:
            on_reco(text, evs, Situation(hero_codes=tuple(hero),
                                         board_codes=(), street='preflop',
                                         position=hero_pos), label)
        elif verbose or self.verbose:
            print(text)
        return evs

    def recomendacion(self, state, verbose=None, on_reco=None, runout=None,
                      seed=None):
        """Calcula la recomendación actual (None si el hero no está en mano).

        `on_reco(texto, evs, sit, label)` se invoca con el panel formateado;
        si no, se imprime en consola (según `verbose`). `seed` fijo →
        determinista el sorteo preflop (tests)."""
        hero = self._hero_cards_fallback()
        if len(hero) < 2:
            hero = self._hero_cards_of(state)
        if len(hero) < 2:
            return None
        board = _board_codes(state)
        if not board:
            board = self._board_fallback()
        villain = self._villain_id(state)
        if villain is None:
            return None

        # Perfil PEZ/TIBURON del rival (por STACK, sin coincidencia de nombres)
        perfil = self._perfil_for(villain, state)
        villain_pos = self._pos_of(villain, state) or 'UTG'

        pot = state.get('pot') or 0.0
        hero_pid = self._hero_pid()
        hero_bet = state.get(f'{hero_pid}_bet') or 0.0
        to_call = max(self._max_bet(state) - hero_bet, 0.0)
        hero_stake = state.get(f'{hero_pid}_stake')
        stack = hero_stake or 0.0
        villain_stack = state.get(f'{villain}_stake') or 0.0
        effective_stack = min(stack, villain_stack)
        street = _street_of(len(board))
        hero_pos = self._pos_of(hero_pid, state) or ''
        if verbose is None:
            verbose = self.verbose
        name = self._villain_name(villain)

        if street == 'preflop':
            return self._recom_preflop(state, hero, hero_pos, hero_bet, pot,
                                       to_call, perfil, name, on_reco,
                                       verbose, seed=seed)

        # Rango inicial del rival según su preflop + blockers
        spot, action = _preflop_spot(self.rec.hand, villain_pos)
        reach = self.models.range_model.prob_vec(perfil, spot, action,
                                                 pos=villain_pos)
        rs = RangeState(reach=reach)
        rs.set_known_cards(list(hero) + list(board))

        # Refina el rango con las acciones postflop ya observadas del rival
        postflop = self.models.postflop_model
        for street, facing, act, board_str in _villain_postflop_actions(
                self.rec.hand, villain_pos):
            board = [c.strip() for c in board_str.split(',')] if board_str else []
            vec = postflop.prob_vec(perfil, street, facing, board, act)
            rs.update(vec)

        sit = situation(hero, board, villain_reach=rs,
                        pot_before_call=pot, to_call=to_call,
                        stack_effective=effective_stack, position=hero_pos,
                        street=street)
        # Respuesta del rival vs la apuesta del hero: P(A|C) del perfil
        # (funde el Oracle con la heurística según la n de la celda).
        is_initiator = _hero_is_initiator(self.rec.hand, hero_pos)
        resp = OracleResponse(
            self.oracle, perfil,
            (street, _hero_bet_facing(street, is_initiator,
                                      _hand_was_raised(self.rec.hand)),
             _texture_class(board)))
        # Reglas postflop (pegar.txt §2-§22): la situación fija los
        # candidatos y sizings; el EV solo se considera sobre ellos (§21).
        n_players = sum(1 for pid in PLAYER_IDS
                        if state.get(f'{pid}_state') == 'activo')
        acts_this = ((self.rec.hand or {}).get('streets', {}).get(street, {})
                     or {}).get('actions', []) or []
        villain_here = [a for a in acts_this if a.get('pos') == villain_pos]
        facing_raise = bool(villain_here
                            and villain_here[-1].get('action') == 'r')
        flop_acts = ((self.rec.hand or {}).get('streets', {}).get('flop', {})
                     or {}).get('actions', []) or []
        hero_bet_flop = any(a.get('pos') == hero_pos
                            and a.get('action') in ('b', 'r')
                            for a in flop_acts)
        villain_bet_flop = any(a.get('pos') == villain_pos
                               and a.get('action') in ('b', 'r')
                               for a in flop_acts)
        flop_checked = not any(a.get('action') in ('b', 'r')
                               for a in flop_acts)
        hero_oop = _hero_oop(hero_pos, villain_pos, flop_acts)
        # Mano del hero: hand_role para los filtros §§4/6/18, y las ventajas
        # de rango/nuts (§3) a partir de la equity vs el rango rival.
        hs = hand_classify(hero, board)
        rp = rules_plan(street, is_initiator, to_call, board, pot,
                        effective_stack,
                        n_players=max(1, n_players),
                        facing_raise=facing_raise,
                        hero_bet_flop=hero_bet_flop,
                        hero_oop=hero_oop,
                        flop_checked=flop_checked,
                        villain_bet_flop=villain_bet_flop,
                        hand_role=hs.role,
                        range_advantage=range_adv(sit.equity),
                        nut_advantage=hs.nut_advantage())
        evs = compute_evs(hero, board, villain_reach=rs, pot=pot,
                          to_call=to_call, stack=stack,
                          villain_stack=villain_stack, response_fn=resp,
                          runout=(self.runout if runout is None else runout),
                          bet_sizes=rp.bet_sizes,
                          raise_to=rp.raise_to,
                          candidates=rp.candidates)
        label = f'{perfil} {name}'
        evs.spot = rp.spot
        evs.rule_note = rp.note
        action = rules_select_best(evs, rp)[0]
        evs.chosen = action
        text = format_insight(sit, evs, villain_label=label, plan=rp)
        if on_reco is not None:
            on_reco(text, evs, sit, label)
        elif self.verbose or verbose:
            print(text)
        return evs

    # ------------------------------------------------------------------

    def step(self, state, img_arr, pil, log=print, on_reco=None,
             require_turn=True, force_reco=False, runout=None):
        """Procesa UN fotograma: registro continuo + recomendación (si toca a
        hero y la situación cambió). Lo usan `run()` y la GUI.

        require_turn=True  → solo recomienda si `_hero_act` (botón o fallback
                            lógico). require_turn=False (manual) → recomienda
                            en cada frame si cambió la situación.
        force_reco=True    → ignora el dedupe (un clic manual = una reconsulta).
        runout             → True: EV a showdown con sorteo de runout en ramas
                            pasivas (modo manual, ~1-2 s); None: usa self.runout.
        Devuelve la EvTable de la recomendación o None."""
        try:
            self.rec.process_frame(state, img_arr, log=log)
            self._observe_stacks(state)

            turn = self._hero_act(state, pil) if require_turn else True
            res = None
            if turn:
                key = self._state_key(state)
                if force_reco or key != self.last_reco_key:
                    try:
                        res = self.recomendacion(state, verbose=False,
                                                 on_reco=on_reco)
                        self.last_reco_key = key
                    except Exception as e:
                        log(f'  [rec] error: {e}')
            else:
                self.last_reco_key = None   # hero ya actuó: nueva vez

            self.last_state = state
            self.last_img = img_arr
            return res
        except Exception as e:
            log(f'  [capture] error: {e}')
            return None

    def run(self, stop_event=None, log=print):
        log('AsistenteLive iniciado — leyendo pantalla cada '
            f'{self.poll:.1f} s...')
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            try:
                state, img_arr, pil = capture()
                self.step(state, img_arr, pil, log=log)
            except KeyboardInterrupt:
                if self.rec.hand is not None:
                    log('Guardando mano en curso...')
                    self.rec.finalize_hand(self.last_state)
                log('Detenido.')
                break
            except Exception as e:
                log(f'  [capture] error: {e}')
            time.sleep(self.poll)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description='Asistente de póker en vivo')
    parser.add_argument('--poll', type=float, default=POLL_DEFAULT,
                        help='segundos entre pantallazos (default 0.5)')
    parser.add_argument('--hero-nombre', default=HERO_NAME_DEFAULT,
                        help='nombre de tu jugador (default Jarduan)')
    parser.add_argument('--quiet', action='store_true',
                        help='no imprimir el panel completo en cada turno')
    args = parser.parse_args(argv)

    models = build_models()
    asis = Asistente(models=models, hero_name=args.hero_nombre,
                     poll_s=args.poll, verbose=not args.quiet)
    asis.run()


if __name__ == '__main__':
    main()
