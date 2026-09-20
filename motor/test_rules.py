"""Test de motor/rules.py — reglas postflop (pegar.txt §2-§22)."""
import pytest

from motor.decision import compute_evs
from motor.rules import board_class, plan, select_best


# ---------------------------------------------------------------------------
# §23 textura
# ---------------------------------------------------------------------------

def test_board_class_dry():
    assert board_class(['Ac', '7d', '2s']) == 'DRY'
    assert board_class(['Ac', '7d', '2s', '9h']) == 'DRY'


def test_board_class_semi_dry():
    # two-tone sin corrida fuerte → SEMI_DRY (draws de color)
    assert board_class(['Qs', '8s', '5d']) == 'SEMI_DRY'
    # rainbow corrida 3 → SEMI_DRY (draws de escalera)
    assert board_class(['2c', '3h', '4d']) == 'SEMI_DRY'


def test_board_class_wet():
    # two-tone + corrida 3 → WET (9s8s7d de pegar.txt)
    assert board_class(['9s', '8s', '7d']) == 'WET'
    # monotone → WET
    assert board_class(['Ah', 'Kh', '2h']) == 'WET'
    # corrida 4 → WET
    assert board_class(['9s', '8s', '7d', '6c']) == 'WET'


def test_board_class_incomplete():
    assert board_class([]) is None
    assert board_class(['Ah', 'Kd']) is None


# ---------------------------------------------------------------------------
# §3/§4 c-bet (hero PFA, flop, rival checkea)
# ---------------------------------------------------------------------------

def test_plan_cbet_dry_small_only():
    rp = plan('flop', True, 0.0, ['Qh', '7s', '2c'], pot=12.5, stack=90,
              n_players=2)
    assert rp.spot == 'cbet'
    assert rp.texture == 'DRY'
    assert rp.bet_sizes == (0.25,)
    assert rp.candidates == ('check', 'bet_25')
    assert 'c-bet' in rp.note


def test_plan_cbet_wet_big_sizes():
    rp = plan('flop', True, 0.0, ['9s', '8s', '7d'], pot=12.5, stack=90)
    assert rp.spot == 'cbet' and rp.texture == 'WET'
    assert rp.bet_sizes == (0.66, 0.75)
    assert rp.candidates == ('check', 'bet_66', 'bet_75')


# ---------------------------------------------------------------------------
# §5 multiway
# ---------------------------------------------------------------------------

def test_plan_multiway_drops_small_sizes():
    # DRY + 3 jugadores → no hay c-bet chica: solo check (§5)
    hu = plan('flop', True, 0.0, ['Qh', '7s', '2c'], pot=12.5, stack=90,
              n_players=2)
    mw = plan('flop', True, 0.0, ['Qh', '7s', '2c'], pot=12.5, stack=90,
              n_players=3)
    assert hu.bet_sizes == (0.25,)
    assert mw.bet_sizes == ()
    assert mw.candidates == ('check',)


# ---------------------------------------------------------------------------
# §14/§15 facing bet / facing raise
# ---------------------------------------------------------------------------

def test_plan_facing_bet_only_call_raise():
    rp = plan('flop', True, 5.0, ['Qh', '7s', '2c'], pot=12.5, stack=90,
              n_players=2)
    assert rp.spot == 'facing_bet'
    assert rp.candidates == ('fold', 'call', 'raise', 'all_in')
    assert not rp.raise_all_in
    # §10: ratio = apuesta / bote ANTES de la apuesta (12.5 - 5 = 7.5)
    # → 5/7.5 = 67% → ~2.6× = 13.0 (§12)
    assert rp.raise_to == pytest.approx(13.0)


def test_plan_facing_raise_uses_bigger_reraise():
    # §15: reraise > raise del mismo enfrentamiento (§12 del doc)
    bet = plan('flop', True, 10.0, ['Qh', '7s', '2c'], pot=30, stack=160,
               n_players=2, facing_raise=False)
    reraise = plan('flop', True, 10.0, ['Qh', '7s', '2c'], pot=30, stack=160,
                   n_players=2, facing_raise=True)
    assert reraise.spot == 'facing_raise'
    assert bet.spot == 'facing_bet'
    assert reraise.candidates == ('fold', 'call', 'raise', 'all_in')
    # 10 vs bote previo 20 → ratio 50% → raise 2.8x = 28 vs reraise 3.2x = 32
    assert bet.raise_to == pytest.approx(28.0)
    assert reraise.raise_to == pytest.approx(32.0)
    assert reraise.raise_to > bet.raise_to


def test_plan_raise_too_big_prefers_all_in():
    # §11: raise computado supera el 98% del stack → raise_to None pero
    # se marca ALL_IN como la única subida (sin mezclar con "sin raise").
    rp = plan('flop', True, 9.0, ['Qh', '7s', '2c'], pot=10, stack=20,
              n_players=2)
    assert rp.raise_to is None
    assert rp.raise_all_in
    assert rp.candidates == ('fold', 'call', 'all_in')
    assert 'raise' not in rp.candidates


def test_plan_raise_too_small_no_raise():
    # §11: raise con extra < 0.5 BB → sin raise, y sin all-in obligatorio
    rp = plan('flop', True, 0.1, ['Qh', '7s', '2c'], pot=30, stack=90,
              n_players=2)
    assert rp.raise_to is None
    assert not rp.raise_all_in
    assert rp.candidates == ('fold', 'call')


# ---------------------------------------------------------------------------
# §8 barrel turn, §9 donk flop, §16 probe turn, §17 value river
# ---------------------------------------------------------------------------

def test_plan_barrel_turn_after_flop_cbet():
    rp = plan('turn', True, 0.0, ['Qh', '7s', '2c', '9d'], pot=25, stack=85,
              n_players=2, hero_bet_flop=True)
    assert rp.spot == 'barrel'
    assert rp.bet_sizes == (0.5, 0.66)


def test_plan_donk_flop_oop():
    # §9: donk SOLO cuando hero es caller OOP y el PFA checkea
    rp = plan('flop', False, 0.0, ['9s', '8s', '7d'], pot=10, stack=95,
              n_players=2, hero_oop=True)
    assert rp.spot == 'donk'
    assert rp.bet_sizes == (0.33, 0.5)


def test_plan_donk_requires_oop():
    # caller IP tras check → bet IP, NO donk (§3 del doc)
    rp = plan('flop', False, 0.0, ['9s', '8s', '7d'], pot=10, stack=95,
              n_players=2, hero_oop=False)
    assert rp.spot == 'flop'
    assert rp.bet_sizes == (0.66, 0.75)      # sizing de textura WET
    rp2 = plan('flop', False, 0.0, ['Qh', '7s', '2c'], pot=10, stack=95,
               n_players=2, hero_oop=True)
    assert rp2.spot == 'donk'

def test_plan_probe_turn_requires_flop_check():
    # §16: probe solo tras flop check-check (§13 del doc)
    rp = plan('turn', False, 0.0, ['Qh', '7s', '2c', '9d'], pot=20, stack=90,
              n_players=2, flop_checked=True)
    assert rp.spot == 'probe'
    assert rp.bet_sizes == (0.25, 0.5)


def test_plan_probe_turn_after_flop_action():
    # turn sin apuesta tras agresión en flop NO es probe
    rp = plan('turn', False, 0.0, ['Qh', '7s', '2c', '9d'], pot=20, stack=90,
              n_players=2, flop_checked=False)
    assert rp.spot == 'turn'
    assert rp.bet_sizes == (0.5, 0.66)


def test_plan_river_generic_value_or_bluff():
    # §14 doc: todo river sin apuesta es 'river' (value O bluff)
    rp = plan('river', False, 0.0, ['Qh', '7s', '2c', '9d', '5h'], pot=40,
              stack=90, n_players=2)
    assert rp.spot == 'river'
    # §15: incluye sizing 100%
    assert rp.bet_sizes == (0.5, 0.75, 1.0)


# ---------------------------------------------------------------------------
# §21 select_best respeta los candidatos
# ---------------------------------------------------------------------------

def test_select_best_uses_candidates():
    # facing bet: 'raise' con EV correcto puede ganar sobre call(all-in no)
    rp = plan('flop', True, 5.0, ['Qh', '7s', '2c'], pot=12.5, stack=90,
              n_players=2)
    evs = compute_evs(['As', 'Kd'], ['Qh', '7s', '2c'],
                      pot=12.5, to_call=5.0, stack=90,
                      bet_sizes=rp.bet_sizes, raise_to=rp.raise_to,
                      candidates=rp.candidates)
    label, _ = select_best(evs, rp)
    assert label in rp.candidates


def test_select_best_never_leaves_candidates():
    # §21: la acción elegida siempre es una candidata del plan
    for board, to_call in ((['Qh', '7s', '2c'], 0.0), (['9s', '8s', '7d'], 0.0)):
        rp = plan('flop', True, 0.0, board, pot=10, stack=50, n_players=2)
        evs = compute_evs(['As', 'Kd'], board, pot=10, to_call=0.0, stack=50,
                          bet_sizes=rp.bet_sizes, candidates=rp.candidates)
        label, _ = select_best(evs, rp)
        assert label in rp.candidates
    rp = plan('flop', True, 5.0, ['Qh', '7s', '2c'], pot=12.5, stack=90,
              n_players=2)
    evs = compute_evs(['As', 'Kd'], ['Qh', '7s', '2c'],
                      pot=12.5, to_call=5.0, stack=90,
                      raise_to=rp.raise_to, candidates=rp.candidates)
    label, _ = select_best(evs, rp)
    assert label in rp.candidates


# ---------------------------------------------------------------------------
# §3/§4/§6/§18 filtros por hand_role y rango (§4 y §5 del doc)
# ---------------------------------------------------------------------------

def test_plan_cbet_wet_villain_range_advantage_checks():
    # §3: rango rival domina + board WET → solo check
    rp = plan('flop', True, 0.0, ['9s', '8s', '7d'], pot=12.5, stack=90,
              n_players=2, range_advantage='VILLAIN')
    assert rp.spot == 'cbet'
    assert rp.candidates == ('check',)


def test_plan_cbet_hero_advantage_wet_still_bets():
    rp = plan('flop', True, 0.0, ['9s', '8s', '7d'], pot=12.5, stack=90,
              n_players=2, range_advantage='HERO')
    assert rp.candidates == ('check', 'bet_66', 'bet_75')


def test_plan_cbet_multiway_filters_by_hand_role():
    # §4: multiway y mano media → solo check aunque el board pida c-bet
    rp = plan('flop', True, 0.0, ['9s', '8s', '7d'], pot=12.5, stack=90,
              n_players=3, hand_role='MEDIUM')
    assert rp.spot == 'cbet'
    assert rp.candidates == ('check',)
    # con mano de valor se mantienen los c-bet grandes del §5
    strong = plan('flop', True, 0.0, ['9s', '8s', '7d'], pot=12.5, stack=90,
                  n_players=3, hand_role='STRONG_VALUE')
    assert strong.candidates == ('check', 'bet_66', 'bet_75')


def test_plan_donk_blocks_weak_hand():
    # §6/§9: donk OOP solo con valor/equity fuerte; mano débil → check
    rp = plan('flop', False, 0.0, ['Qh', '7s', '2c'], pot=12.5, stack=90,
              n_players=2, hero_oop=True, hand_role='AIR')
    assert rp.spot == 'donk'
    assert rp.candidates == ('check',)
    strong = plan('flop', False, 0.0, ['Qh', '7s', '2c'], pot=12.5, stack=90,
                  n_players=2, hero_oop=True, hand_role='STRONG_VALUE')
    assert 'bet_33' in strong.candidates


def test_plan_facing_raise_filters_raise_by_hand_role():
    # §18: check-raise requiere mano de valor/equity fuerte
    rp = plan('flop', False, 10.0, ['Qh', '7s', '2c'], pot=30, stack=100,
              n_players=2, facing_raise=True, hero_bet_flop=True,
              hand_role='AIR')
    assert rp.spot == 'facing_raise'
    assert 'raise' not in rp.candidates
    assert 'all_in' not in rp.candidates
    strong = plan('flop', False, 10.0, ['Qh', '7s', '2c'], pot=30, stack=100,
                  n_players=2, facing_raise=True, hero_bet_flop=True,
                  hand_role='STRONG_VALUE')
    assert 'raise' in strong.candidates


def test_plan_facing_raise_filtra_semibluff():
    # §15: contra UNA SUBIDA no se reraisea con draws (solo valor hecha),
    # para no bluffear de más; frente a una apuesta normal sí (§14).
    rp = plan('flop', False, 10.0, ['Qh', '7s', '2c'], pot=30, stack=100,
              n_players=2, facing_raise=True, hand_role='STRONG_DRAW')
    assert rp.spot == 'facing_raise'
    assert rp.candidates == ('fold', 'call')
    bet = plan('flop', False, 10.0, ['Qh', '7s', '2c'], pot=30, stack=100,
               n_players=2, facing_raise=False, hand_role='STRONG_DRAW')
    assert bet.spot == 'facing_bet'
    assert 'raise' in bet.candidates


def test_plan_facing_raise_river_filtra_value():
    # §15 river: contra un raise en RIVER solo STRONG_VALUE puede
    # reraisear/all_in; el 2 par (VALUE) queda en fold/call.
    rp = plan('river', False, 25.0, ['9h', '9s', '6h', 'Ks', 'As'], pot=56,
              stack=80, n_players=2, facing_raise=True, hand_role='VALUE')
    assert rp.spot == 'facing_raise'
    assert rp.candidates == ('fold', 'call')
    strong = plan('river', False, 25.0, ['9h', '9s', '6h', 'Ks', 'As'],
                  pot=56, stack=80, n_players=2, facing_raise=True,
                  hand_role='STRONG_VALUE')
    assert any(c in strong.candidates for c in ('raise', 'all_in'))
    # en flop, VALUE sigue pudiendo reraisear (regresión §15 pre-river)
    flop = plan('flop', False, 10.0, ['Qh', '7s', '2c'], pot=30, stack=100,
                n_players=2, facing_raise=True, hand_role='VALUE')
    assert 'raise' in flop.candidates


# ---------------------------------------------------------------------------
# §6/§7 paired y estructura del board
# ---------------------------------------------------------------------------

def test_plan_exposes_paired_and_structure():
    rp = plan('flop', True, 0.0, ['Ac', '7d', '2s'], pot=12.5, stack=90)
    assert rp.paired == 'UNPAIRED'
    assert rp.structure == 'DISCONNECTED'
    rp = plan('flop', True, 0.0, ['Ac', '7d', '7s'], pot=12.5, stack=90)
    assert rp.paired == 'PAIRED'
    assert rp.structure == 'PAIRED'


def test_plan_broadway_and_connected():
    rp = plan('flop', True, 0.0, ['Ac', 'Kc', 'Qd'], pot=12.5, stack=90)
    assert rp.structure == 'BROADWAY'
    rp = plan('flop', True, 0.0, ['9c', '8c', '7d'], pot=12.5, stack=90)
    assert rp.structure == 'MID_CONNECTED'


def test_plan_double_paired_turn():
    rp = plan('turn', True, 0.0, ['7c', '7d', '2s', '2h'], pot=12.5, stack=90)
    assert rp.paired == 'DOUBLE_PAIRED'


# ---------------------------------------------------------------------------
# §5/§9 multiway como umbral (no eliminación ciega de sizings)
# ---------------------------------------------------------------------------

def test_plan_multiway_threshold_with_strong_hand():
    # 3-way DRY: la mano fuerte recupera el tramo 33/50 (§9)
    strong = plan('flop', True, 0.0, ['Qh', '7s', '2c'], pot=12.5, stack=90,
                  n_players=3, hand_role='STRONG_VALUE')
    assert strong.bet_sizes == (0.33, 0.5)
    assert strong.candidates == ('check', 'bet_33', 'bet_50')
    # 4-way: tramo 50/66
    four = plan('flop', True, 0.0, ['Qh', '7s', '2c'], pot=12.5, stack=90,
                n_players=4, hand_role='VALUE')
    assert four.bet_sizes == (0.5, 0.66)


def test_plan_multiway_threshold_keeps_big_sizes_wet():
    # WET 3-way: los sizings grandes sobreviven al umbral 33%
    rp = plan('flop', True, 0.0, ['9s', '8s', '7d'], pot=12.5, stack=90,
              n_players=3, hand_role='STRONG_VALUE')
    assert rp.bet_sizes == (0.66, 0.75)


# ---------------------------------------------------------------------------
# §5 frecuencias de c-bet: WET + rango neutro → solo 66%
# ---------------------------------------------------------------------------

def test_plan_cbet_wet_neutral_range_low_frequency():
    rp = plan('flop', True, 0.0, ['9s', '8s', '7d'], pot=12.5, stack=90,
              n_players=2, range_advantage='NEUTRAL')
    assert rp.spot == 'cbet'
    assert rp.bet_sizes == (0.66,)
    assert rp.candidates == ('check', 'bet_66')
    assert 'LOW' in rp.note


# ---------------------------------------------------------------------------
# §18-§19 tabla de reglas v1 (estructura de las filas)
# ---------------------------------------------------------------------------

def test_rule_table_v1():
    from motor.rules import RULES
    spots = [r.spot for r in RULES]
    # Las filas 'facing' encabezan (to_call > 0) y luego las de bet/check
    assert spots == ['facing_raise', 'facing_bet', 'cbet', 'donk', 'flop',
                     'barrel', 'probe', 'turn', 'river']
    assert len(set(spots)) == len(spots)          # sin duplicados
    for r in RULES:
        assert callable(r.when)                   # IF (condición mínima)
        assert r.kind in ('bet', 'facing')
        assert all(callable(g) for g in r.filtering)