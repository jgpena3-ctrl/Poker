"""rules.py — reglas postflop (pegar.txt §2-§22).

Clasifica la situación (§2/§22) y reduce las acciones del EV a los
candidatos razonables antes de calcular (§21: 10 acciones → 3 → EV → 1).
La decisión es una TABLA DE REGLAS v1 (§18-§19): cada fila tiene
IF (situación) → filtros (board/multiway/mano/rango) → acciones → sizing.

Uso típico en el asistente:

    from .rules import plan, RULES, select_best
    rp = plan(street, hero_initiator, to_call, board, pot, stack,
              n_players, hero_bet_flop=..., facing_raise=...)
    evs = compute_evs(..., bet_sizes=rp.bet_sizes,
                      raise_to=rp.raise_to, candidates=rp.candidates)
    action, value = select_best(evs, rp)
"""
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from .situation import board_texture


# ---------------------------------------------------------------------------
# Textura (§23): DRY / SEMI_DRY / WET
# ---------------------------------------------------------------------------

def board_class(board_codes):
    """Clasificación simplificada del board (pegar.txt §23).

    DRY      → rainbow, corrida <= 2, sin draws (p.ej. A72r)
    SEMI_DRY → two-tone sin corrida fuerte, o rainbow corrida=3 (p.ej. JT9r, Q85ss)
    WET      → monotone, corrida >= 4, o two-tone con corrida >= 3 (p.ej. 987s, 876ss)
    None     → board incompleto (< 3 cartas)
    """
    if board_codes is None or len(board_codes) not in (3, 4, 5):
        return None
    t = board_texture(board_codes)
    run = t['straight_run']
    if t['monotone'] or run >= 4 or (t['two_tone'] and run >= 3):
        return 'WET'
    if t['two_tone'] or run >= 3:
        return 'SEMI_DRY'
    return 'DRY'


# ---------------------------------------------------------------------------
# Paired y estructura (§8 del doc: PAIRED / §7: board_structure)
# ---------------------------------------------------------------------------

def _paired(board_codes):
    """§8: board emparejado (UNPAIRED / PAIRED / DOUBLE_PAIRED).

    Independiente de DRY/SEMI_DRY/WET: A72r y A77r son texturas distintas.
    """
    if board_codes is None or len(board_codes) < 3:
        return 'UNPAIRED'
    from collections import Counter
    from .cards import card_id, rank_of
    cnt = Counter(rank_of(card_id(c)) for c in board_codes)
    repeated = sum(1 for v in cnt.values() if v >= 2)
    if repeated == 0:
        return 'UNPAIRED'
    if repeated == 1:
        return 'PAIRED'
    return 'DOUBLE_PAIRED'


def _board_structure(board_codes):
    """§7: estructura estratégica aparte de DRY/WET.

    BROADWAY (T-J-Q-K-A) · HIGH/MID/LOW_CONNECTED · DISCONNECTED · PAIRED.
    AKQr es BROADWAY (nut distribution) y no se trunca como JT9r (HIGH_CONNECTED).
    """
    if board_codes is None or len(board_codes) not in (3, 4, 5):
        return None
    if _paired(board_codes) != 'UNPAIRED':
        return 'PAIRED'
    from .cards import card_id, rank_of
    ranks = sorted({rank_of(card_id(c)) + 2 for c in board_codes})  # 2..14
    if all(r >= 10 for r in ranks):                  # T-J-Q-K-A
        return 'BROADWAY'
    run = best = 1
    for a, b in zip(ranks, ranks[1:]):
        run = run + 1 if b == a + 1 else 1
        best = max(best, run)
    top = ranks[-1]
    if best >= 4:
        return 'HIGH_CONNECTED'
    if best == 3:
        return ('HIGH_CONNECTED' if top >= 11
                else ('MID_CONNECTED' if top >= 8 else 'LOW_CONNECTED'))
    if best == 2:
        return 'MID_CONNECTED' if top >= 11 else 'LOW_CONNECTED'
    return 'DISCONNECTED'


# ---------------------------------------------------------------------------
# Sizing por textura (§3-§4, §8, §10, §16-§17)
# ---------------------------------------------------------------------------

CBET_SIZES = {'DRY': (0.25,), 'SEMI_DRY': (0.33, 0.5), 'WET': (0.66, 0.75)}
BARREL_SIZES = (0.5, 0.66)        # §8: turn 50-75%
DONK_SIZES = (0.33, 0.5)          # §10
PROBE_SIZES = (0.25, 0.5)         # §16
VALUE_SIZES = (0.5, 0.75, 1.0)    # §17: value bet river (incluye 100%, §15)

_BET_LABEL = lambda frac: f'bet_{int(round(frac * 100))}'


def _bet_labels(sizes):
    return tuple(_BET_LABEL(s) for s in sizes)


# ---------------------------------------------------------------------------
# Multiway (§5)
# ---------------------------------------------------------------------------

# hand_role con los que se apuesta/subida con valor o equity fuerte
# (§4 c-bet multiway, §6 donk, §18 check-raise). Los demás → check/pass.
_BET_ROLES = ('STRONG_VALUE', 'VALUE', 'STRONG_DRAW')


def _multi_sizes(sizes, multiway, n_players, strong_hand=False):
    """§5/§9: multiway modifica el umbral mínimo, no elimina sizings.

    HU 25/33/50 · 3-way 33/50 · 4-way 50/66. Si el set natural del board
    queda vacío por el umbral pero la mano es de valor/equity fuerte, se
    ofrece el tramo mínimo del multiway (§9: la mano también interviene).
    """
    if not multiway or not sizes:
        return sizes
    min_ok = 0.33 if n_players <= 3 else 0.50
    kept = tuple(s for s in sizes if s >= min_ok)
    if kept or not strong_hand:
        return kept
    return (0.33, 0.5) if n_players <= 3 else (0.5, 0.66)


# ---------------------------------------------------------------------------
# Sizing de raise / reraise (§12/§9) con convención de pot (§10)
# ---------------------------------------------------------------------------
# El ratio de la apuesta rival se mide contra el bote ANTES de su apuesta
# (pot_total - to_call ≈ bote previo cuando el hero aún no aportó en la calle).
_RAISE_MULTS = ((0.25, 3.0), (0.50, 2.8), (0.75, 2.6), (1.0, 2.5))
_RERAISE_MULTS = ((0.25, 3.4), (0.50, 3.2), (0.75, 3.0), (1.0, 2.9))


def _pot_before_bet(pot, to_call):
    """§10: bote previo a la apuesta rival (pot total - to_call), nunca <= 0."""
    return max(pot - to_call, to_call, 1.0)


def _mult_for(mults, ratio):
    for limit, m in mults:
        if ratio <= limit:
            return m
    return mults[-1][1]


def _raise_plan(to_call, pot, stack, mults):
    """Talla de la subida. Devuelve (raise_to, all_in_only).

    raise_to      : total al que sube el hero (incluye to_call) o None.
    all_in_only   : True si el raise computado supera el 98% del stack
                    (§11: la única subida razonable es el all-in).
    raise_to None y all_in_only False → sin raise razonable (extra < 0.5):
                    NO_RAISE (§11). Nunca None para ambos casos.
    """
    if to_call <= 0:
        return None, False
    ratio = to_call / _pot_before_bet(pot, to_call)
    total = to_call * _mult_for(mults, ratio)
    if total > stack * 0.98:
        return None, True          # ALL_IN es la subida
    if total - to_call < 0.5:
        return None, False         # sin raise razonable
    return min(round(total, 2), stack), False


# ---------------------------------------------------------------------------
# RulePlan — resultado del clasificador
# ---------------------------------------------------------------------------

@dataclass
class RulePlan:
    """Plan de acción postflop según las reglas de pegar.txt §22.

    spot        : 'cbet' | 'donk' | 'flop' | 'barrel' | 'probe' | 'turn' |
                  'river' | 'facing_bet' | 'facing_raise' | 'preflop' |
                  'unknown'
    texture     : 'DRY' | 'SEMI_DRY' | 'WET' | None
    candidates  : labels de acciones permitidas (incluye 'fold')
    bet_sizes   : fracciones de bote para las bets candidatas
    raise_to    : total al que el hero sube (incluye to_call), o None
    raise_all_in: True si la única subida razonable es el all-in (§11)
    paired      : 'UNPAIRED' | 'PAIRED' | 'DOUBLE_PAIRED'
    structure   : 'BROADWAY' | *_CONNECTED | 'DISCONNECTED' | 'PAIRED' | None
    note        : nota corta para el panel (regla aplicada)
    n_players   : jugadores activos en la mano
    """
    spot: str = 'unknown'
    texture: Optional[str] = None
    candidates: Tuple[str, ...] = ('fold', 'check')
    bet_sizes: Tuple[float, ...] = ()
    raise_to: Optional[float] = None
    raise_all_in: bool = False
    paired: str = 'UNPAIRED'
    structure: Optional[str] = None
    note: str = ''
    n_players: int = 1


# ---------------------------------------------------------------------------
# Tabla de reglas v1 (pegar.txt §18-§19): IF → filtros → acciones → sizing
# ---------------------------------------------------------------------------

@dataclass
class Ctx:
    """Situación completa que consultan las filas de la tabla (Nivel 1+2)."""
    street: str
    hero_initiator: bool
    hero_oop: bool
    to_call: float
    board_codes: object
    pot: float
    stack: float
    n_players: int
    facing_raise: bool
    hero_bet_flop: bool
    flop_checked: bool
    villain_bet_flop: bool
    hand_role: Optional[str]
    range_advantage: Optional[str]
    nut_advantage: Optional[str]
    tx: Optional[str] = None

    @property
    def multi(self):
        return self.n_players > 2

    @property
    def strong(self):
        return bool(self.hand_role) and self.hand_role in _BET_ROLES


@dataclass(frozen=True)
class Row:
    """Fila de la tabla de reglas v1 (§19):

    IF (situación) → filtros (mano/board/rango) → acciones → sizing.
    kind  : 'bet' (CHECK + BET) | 'facing' (FOLD + CALL + RAISE).
    filtering : guardas (Nivel 2) que, si devuelven nota, anulan el spot
                con solo CHECK (check-only plan) en vez de las acciones base.
    """
    spot: str
    kind: str
    when: Callable[[Ctx], bool]
    doc: str = ''
    sizes: object = ()
    by_texture: bool = False
    sizing: Optional[Callable[[Ctx], Tuple[float, ...]]] = None
    mults: Tuple = ()
    filtering: Tuple[Callable[[Ctx], Optional[str]], ...] = ()
    show_sizes: bool = True


def _ml(ctx):
    return ' · multiway' if ctx.multi else ''


def _multi_sizes_ctx(ctx, base):
    """Sizing base con multiway como umbral (§5/§9)."""
    return _multi_sizes(base, ctx.multi, ctx.n_players, ctx.strong)


def _base_bet_sizes(ctx, row):
    """Sizing por textura (CEBET) o fijo, con el umbral multiway aplicado."""
    if row.by_texture:
        base = CBET_SIZES.get(ctx.tx, (0.25, 0.5))
    else:
        base = row.sizes
    return _multi_sizes_ctx(ctx, base)


def _sizes_cbet(ctx):
    """§3/§5: c-bet por textura + frecuencia LOW en WET con rango neutro."""
    sizes = _multi_sizes_ctx(ctx, CBET_SIZES.get(ctx.tx, (0.25, 0.5)))
    if ctx.tx == 'WET' and ctx.range_advantage == 'NEUTRAL':
        sizes = tuple(s for s in sizes if s < CBET_SIZES['WET'][-1])
    return sizes


# -- IF (Nivel 1): condiciones mínimas de situación (§19) ----------------

def _en_facing(flag):
    return lambda c: c.to_call > 0 and c.facing_raise == flag


def _en_flop_init(c):
    return c.street == 'flop' and c.hero_initiator


def _en_donk(c):
    return c.street == 'flop' and not c.hero_initiator and c.hero_oop


def _en_flop_ip(c):
    return c.street == 'flop' and not c.hero_initiator


def _en_barrel(c):
    return c.street == 'turn' and c.hero_initiator and c.hero_bet_flop


def _en_probe(c):
    return c.street == 'turn' and c.flop_checked


def _en_turn(c):
    return c.street == 'turn'


def _en_river(c):
    return c.street == 'river'


# -- Filtros (Nivel 2): board / multiway / hand_role / rango --------------

def _cbet_wet_villain(c):
    """§3: rango rival domina en board WET → solo check."""
    if c.range_advantage == 'VILLAIN' and c.tx == 'WET':
        return f'§3 c-bet · {c.tx} rango rival → check'
    return None


def _cbet_multi_weak(c):
    """§4: multiway sin mano de valor/equity → solo check."""
    if c.multi and c.hand_role is not None and c.hand_role not in _BET_ROLES:
        return f'§4 c-bet multiway · {c.hand_role} → check'
    return None


def _donk_weak(c):
    """§6/§9: donk solo con valor/equity fuerte; si no → check."""
    if c.hand_role is not None and c.hand_role not in _BET_ROLES:
        return f'§9 donk OOP · {c.hand_role} → check'
    return None


def _flop_ip_multi_weak(c):
    """§4: flop IP multiway sin mano fuerte → solo check."""
    if c.multi and c.hand_role is not None and c.hand_role not in _BET_ROLES:
        return f'flop IP · {c.hand_role} → check'
    return None


# -- Tabla (§19: fila = IF → filtros → acciones → sizing) -----------------

RULES = (
    Row('facing_raise', 'facing', _en_facing(True), doc='§15 reraise vs raise',
        mults=_RERAISE_MULTS),
    Row('facing_bet', 'facing', _en_facing(False), doc='§14 facing bet',
        mults=_RAISE_MULTS),
    Row('cbet', 'bet', _en_flop_init, doc='§3 c-bet', by_texture=True,
        sizing=_sizes_cbet,
        filtering=(_cbet_wet_villain, _cbet_multi_weak)),
    Row('donk', 'bet', _en_donk, doc='§9 donk OOP', sizes=DONK_SIZES,
        show_sizes=False, filtering=(_donk_weak,)),
    Row('flop', 'bet', _en_flop_ip, doc='flop IP · bet tras check',
        by_texture=True, show_sizes=False, filtering=(_flop_ip_multi_weak,)),
    Row('barrel', 'bet', _en_barrel, doc='§8 barrel turn', sizes=BARREL_SIZES),
    Row('probe', 'bet', _en_probe, doc='§16 probe · flop check-check',
        sizes=PROBE_SIZES, show_sizes=False),
    Row('turn', 'bet', _en_turn, doc='turn · check tras agresión',
        sizes=BARREL_SIZES, show_sizes=False),
    Row('river', 'bet', _en_river, doc='§17 river · value/bluff',
        sizes=VALUE_SIZES),
)


# -- Árbol: recorre la tabla, la primera fila que matchea decide -----------

def _bet_note(ctx, row, sizes, freq=''):
    head = f'{row.doc} · {ctx.tx or "?"}'
    if row.show_sizes:
        head += f' sizes {tuple(round(s * 100) for s in sizes)}'
    if freq:
        head += f' {freq}'
    return head + _ml(ctx)


def _facing_plan(ctx, row):
    ratio = ctx.to_call / _pot_before_bet(ctx.pot, ctx.to_call)
    mult = _mult_for(row.mults, ratio)
    r_to, all_in_only = _raise_plan(ctx.to_call, ctx.pot, ctx.stack, row.mults)
    note = f'{row.doc}{_ml(ctx)} (~{mult:.1f}×)'
    if all_in_only:
        cands = ('fold', 'call', 'all_in')
        note += ' · raise > 98% stack → all-in'
    elif r_to is not None:
        cands = ('fold', 'call', 'raise', 'all_in')
    else:
        cands = ('fold', 'call')
        note += ' · sin raise razonable'
    # §18: check-raise solo con fuerza/equity fuerte. None = sin dato.
    # Vs una SUBIDA (facing_raise) se reraisea solo con valor HECHA:
    # en flop/turn STRONG_VALUE+VALUE; en river solo STRONG_VALUE (el
    # raise rival en river pide fold/call; se retira el 2 par y los
    # draws para no "bluffear de más contra raisers" §15).
    if row.spot == 'facing_raise':
        bet_roles = ('STRONG_VALUE',) if ctx.street == 'river' \
            else ('STRONG_VALUE', 'VALUE')
    else:
        bet_roles = _BET_ROLES
    if 'raise' in cands and ctx.hand_role is not None \
            and ctx.hand_role not in bet_roles:
        cands = tuple(c for c in cands if c not in ('raise', 'all_in'))
        note += f' · raise filtrado ({ctx.hand_role})'
    return RulePlan(row.spot, ctx.tx, cands, raise_to=r_to,
                    raise_all_in=all_in_only, note=note,
                    n_players=ctx.n_players)


def _apply(ctx, row):
    # Nivel 2: el primer filtro que bloquea anula el spot → solo CHECK.
    for guarda in row.filtering:
        nota = guarda(ctx)
        if nota:
            return RulePlan(row.spot, ctx.tx, ('check',), note=nota,
                            n_players=ctx.n_players)
    if row.kind == 'facing':
        return _facing_plan(ctx, row)
    sizes = (row.sizing(ctx) if row.sizing is not None
             else _base_bet_sizes(ctx, row))
    freq = ''
    if row.spot == 'cbet':
        freq = ('LOW' if ctx.tx == 'WET'
                and ctx.range_advantage == 'NEUTRAL' else 'HIGH')
    cands = ('check',) + _bet_labels(sizes)
    return RulePlan(row.spot, ctx.tx, cands, sizes,
                    note=_bet_note(ctx, row, sizes, freq),
                    n_players=ctx.n_players)


def _decide(ctx):
    for row in RULES:
        if row.when(ctx):
            return _apply(ctx, row)
    return RulePlan('unknown', ctx.tx, ('fold', 'check'),
                    n_players=ctx.n_players)


def plan(street, hero_initiator, to_call, board_codes, pot, stack,
         n_players=1, facing_raise=False, hero_bet_flop=False,
         hero_oop=False, flop_checked=False, villain_bet_flop=False,
         hand_role=None, range_advantage=None, nut_advantage=None):
    """Clasifica la situación recorriendo la tabla de reglas v1 (§18-§19).

    Parámetros
    ----------
    street           : 'flop' | 'turn' | 'river'
    hero_initiator   : bool — hero fue el último agresor preflop (§3: PFA)
    to_call          : 0 si no hay bet en curso, > 0 si hay apuesta/raise
    board_codes      : cartas del board (3..5)
    pot              : bote actual (incluye la apuesta rival si la hay;
                       la talla de raise usa el bote previo, §10)
    stack            : stack efectivo restante del hero
    n_players        : jugadores aún en la mano
    facing_raise     : True si la apuesta rival es un raise (§15: reraise)
    hero_bet_flop    : True si hero apostó en el flop (para §8: barrel)
    hero_oop         : True si hero actúa primero postflop (donk OOP, §3 doc)
    flop_checked     : True si el flop fue check-check (para §16 probe)
    villain_bet_flop : True si el rival apostó en el flop
    hand_role        : STRONG_VALUE/VALUE/MEDIUM/STRONG_DRAW/WEAK_DRAW/AIR
                       (§1). None = desconocido (no filtra).
    range_advantage  : 'HERO' | 'NEUTRAL' | 'VILLAIN' (equity vs rango rival).
    nut_advantage    : 'HERO' | 'NEUTRAL' | 'VILLAIN' (aproximado).
    """
    ctx = Ctx(street, hero_initiator, hero_oop, to_call, board_codes,
              pot, stack, n_players, facing_raise, hero_bet_flop,
              flop_checked, villain_bet_flop, hand_role, range_advantage,
              nut_advantage, tx=board_class(board_codes))
    rp = _decide(ctx)
    if rp.spot != 'unknown':
        rp.paired = _paired(ctx.board_codes)
        rp.structure = _board_structure(ctx.board_codes)
    return rp


# ---------------------------------------------------------------------------
# Selección de la mejor acción candidata (§21)
# ---------------------------------------------------------------------------

def select_best(evs, rp=None):
    """Mejor acción por EV entre las candidatas del plan (fold si nada la
    supera). Se usa en vez de `evs.best()` cuando hay un plan de reglas.

    Si no hay plan, devuelve el equivalente a `evs.best()`.
    """
    labels = rp.candidates if rp is not None else tuple(evs.ev)
    best_label = 'fold'
    best_ev = evs.ev.get('fold', 0.0)
    for label in labels:
        val = evs.ev.get(label)
        if val is not None and val > best_ev:
            best_label, best_ev = label, val
    return best_label, best_ev
