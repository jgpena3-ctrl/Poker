"""stats.py — estadísticas de transición por jugador (APRENDIZAJE.md §5.2).

Para cada jugador se agregan contadores (oportunidad, acción) de las
estadísticas de la tabla de transiciones: VPIP, PFR, 3BET, 4BET, C-BET,
Fold/Call/Raise-C-BET, Turn barrel, Fold-to-barrel, River bet, WTSD y W$SD.
Cada frecuencia es un par acción/denominador con las mismas reglas que las
frecuencias preflop (nunca "sobre showdowns" salvo las W*SD propias).

Reglas clave:
- hero solo si el nombre está en HERO_NAMES (Jarduan).
- Denominador 0 => freq = None (nunca 0 % inventado).
- Las manos se cargan con learn.load_hands (las líneas rotas se descartan).
"""
import json
import os
import re
from collections import defaultdict

from .learn import HERO_NAMES, load_hands, preflop_events

SHOWDOWN_RE = re.compile(r'\(([^)]+)\)')

MONEY_CATS = ('limp', 'call_limp', 'open', 'rol', 'call_open', '3bet',
              'squeeze', 'call_3bet', '4bet')
RAISE_CATS = ('open', 'rol', '3bet', 'squeeze', '4bet')

STAT_LABELS = {
    'vpip': 'VPIP', 'pfr': 'PFR', 'b3': '3BET', 'b4': '4BET',
    'cbet': 'C-BET', 'f2cb': 'F2CB', 'c2cb': 'C2CB', 'r2cb': 'R2CB',
    'bar': 'BAR', 'f2bar': 'F2BAR', 'rb': 'RIVER',
    'wtsd': 'WTSD', 'wsd': 'W$SD',
}


class PlayerStats:
    """Contadores de transición de un jugador: dict[stat] -> [opp, act]."""

    def __init__(self, player):
        self.player = player
        self.hero = player in HERO_NAMES
        self.c = defaultdict(lambda: [0, 0])

    def opp(self, stat, n=1):
        self.c[stat][0] += n

    def act(self, stat):
        self.c[stat][1] += 1

    def freq(self, stat):
        opp, act = self.c[stat]
        return act / opp if opp else None

    def to_dict(self):
        return {'hero': self.hero, 'stats': {k: list(v) for k, v in sorted(self.c.items())}}


class TransitionStats:
    """Estadísticas agregadas: player_name -> PlayerStats."""

    def __init__(self):
        self.players = {}

    def _st(self, name):
        st = self.players.get(name)
        if st is None:
            st = PlayerStats(name)
            self.players[name] = st
        return st

    @classmethod
    def from_hands(cls, hands):
        agg = cls()
        for hand in hands:
            agg._collect_hand(hand)
        return agg

    # ------------------------------------------------------------------
    # Recolección por mano
    # ------------------------------------------------------------------

    def _collect_hand(self, hand):
        names_by_pos = {p.get('pos'): (p.get('name') or p.get('pos'))
                        for p in hand.get('players', [])}

        def name(pos):
            return names_by_pos.get(pos, pos)

        evs = preflop_events(hand)
        if not evs:
            return

        # --- preflop: primera decisión + último agresor ---------------
        last_aggressor = None
        for ev in evs:
            st = self._st(ev.player)
            st.opp('vpip')
            st.opp('pfr')
            if ev.category in MONEY_CATS:
                st.act('vpip')
            if ev.category in RAISE_CATS:
                st.act('pfr')
                last_aggressor = ev.pos
            if ev.category in ('call_open', '3bet', 'squeeze', 'fold_vs_open'):
                st.opp('b3')
            if ev.category in ('3bet', 'squeeze'):
                st.act('b3')
            if ev.category in ('call_3bet', '4bet', 'fold_vs_3bet'):
                st.opp('b4')
            if ev.category == '4bet':
                st.act('b4')

        # --- showdown (WTSD / W$SD) -----------------------------------
        # Un jugador "llegó a showdown" solo si la mano registró showdown
        # (el recorder guarda las cartas de hero SIEMPRE, por lo que para
        # hero WTSD/W$SD no son inferibles -> no se cuentan; son features
        # solo de rivales). Sin sección showdown: sin oportunidades.
        has_sd = bool(hand.get('showdown'))
        revealed = set()
        if has_sd:
            revealed = {name(pl.get('pos')) for pl in hand.get('players', [])
                        if pl.get('cards')}
        winners = set()
        for v in (hand.get('showdown') or {}).values():
            m = SHOWDOWN_RE.search(str(v))
            if m:
                winners.add(m.group(1).strip())
        for ev in evs:
            if ev.category == 'fold' or ev.player in HERO_NAMES:
                continue                    # no vio el flop / hero sin WTSD
            if not has_sd:
                continue                    # sin showdown no hay llegada
            st = self._st(ev.player)
            st.opp('wtsd')
            if ev.player in revealed:
                st.act('wtsd')
                st.opp('wsd')
                if ev.player in winners:
                    st.act('wsd')

        # --- postflop: iniciativa y defensas --------------------------
        initiator = last_aggressor            # última posición que metió dinero preflop
        for street in ('flop', 'turn', 'river'):
            act_seq = _actions(hand.get('streets', {}).get(street, {}) or {})
            if not act_seq:
                continue
            first_bettor = None
            for pos, act, _amt in act_seq:
                st = self._st(name(pos))
                if first_bettor is None:
                    # nadie ha apostado aún en la calle: ¿oportunidad con iniciativa?
                    if street == 'flop' and pos == initiator:
                        st.opp('cbet')
                    elif street == 'turn' and pos == initiator:
                        st.opp('bar')
                    elif street == 'river' and pos == initiator:
                        st.opp('rb')
                    if act in ('b', 'r'):
                        first_bettor = pos
                        if street == 'flop' and pos == initiator:
                            st.act('cbet')
                        elif street == 'turn' and pos == initiator:
                            st.act('bar')
                        elif street == 'river' and pos == initiator:
                            st.act('rb')
                elif act != 'x':
                    if street == 'flop' and first_bettor == initiator:
                        if act == 'f':
                            st.opp('f2cb'); st.act('f2cb')
                        elif act == 'c':
                            st.opp('c2cb'); st.act('c2cb')
                        elif act == 'r':
                            st.opp('r2cb'); st.act('r2cb')
                    elif street != 'flop' and first_bettor == initiator:
                        st.opp('f2bar')
                        if act == 'f':
                            st.act('f2bar')
            # la iniciativa pasa al último que apostó en la calle
            last_bet = [pos for pos, act, _amt in reversed(act_seq) if act in ('b', 'r')]
            if last_bet:
                initiator = last_bet[0]

    # ------------------------------------------------------------------

    def report(self, players=None, cols=None):
        cols = cols or ('vpip', 'pfr', 'b3', 'b4', 'cbet', 'f2cb', 'bar',
                        'f2bar', 'wtsd', 'wsd')
        head = 'PLAYER'.ljust(12) + ' H'.rjust(2) + ''.join(
            f'{STAT_LABELS[k]:>7}' for k in cols)
        lines = [head, '-' * len(head)]
        for pname in (players or sorted(self.players)):
            st = self.players[pname]
            row = []
            for k in cols:
                f = st.freq(k)
                row.append(f'{f * 100:6.0f}%' if f is not None else '     -')
            mark = '*' if st.hero else ' '
            lines.append(f'{pname[:12]:<12}{mark}' + ''.join(row))
        return '\n'.join(lines)

    def to_dict(self):
        return {name: st.to_dict() for name, st in sorted(self.players.items())}


def _actions(street):
    """[(pos, action, amount)] normalizados desde la calle del dict."""
    out = []
    for a in street.get('actions', []) or []:
        if isinstance(a, dict):
            pos, act = a.get('pos'), a.get('action')
            try:
                amt = float(a.get('amount') or 0.0)
            except (TypeError, ValueError):
                amt = 0.0
        else:
            try:
                pos, act, amt = a[0], a[1], float(a[2] or 0.0)
            except (IndexError, TypeError, ValueError):
                continue
        if pos and act:
            out.append((pos, act, amt))
    return out


def main(argv=None):
    """CLI: python -m motor.stats [--json] [--out PATH]"""
    import sys
    argv = list(argv or sys.argv[1:])
    write_json = '--json' in argv
    out_path = ''
    if '--out' in argv:
        idx = argv.index('--out')
        out_path = argv[idx + 1] if len(argv) > idx + 1 else ''
    hands = load_hands()
    agg = TransitionStats.from_hands(hands)
    print(f'Manos: {len(hands)}\n')
    print(agg.report())
    if write_json:
        path = out_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'player_stats.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(agg.to_dict(), f, indent=2, ensure_ascii=False)
        print(f'\n-> {path}')


if __name__ == '__main__':
    main()