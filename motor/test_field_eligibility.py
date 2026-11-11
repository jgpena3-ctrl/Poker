# -*- coding: utf-8 -*-
"""Tests P0-2: elegibilidad por campo y por observación, en sombra.

No tocan `data/`: construyen manos sintéticas y, para las pruebas de
integración, leen la base actual con `load_hands`. La sombra nunca filtra los
modelos; estos tests lo comprueban con hashes estables.
"""
import contextlib
import copy
import io

import pytest

from motor.field_eligibility import (
    ABSENT, AMBIGUOUS, CONSUMER_ECONOMIC, CONSUMER_ORACLE_GRANULAR,
    CONSUMER_ORACLE_MARGINAL, CONSUMER_POSTFLOP_RANGE,
    CONSUMER_PREFLOP_STATS, CONSUMER_PROFILE_RANGE, CONSUMER_SHOWDOWN,
    CONSUMER_STACK, DERIVED, FIELD_ACTION_ORDER, FIELD_ACTIONS, FIELD_BOARD,
    FIELD_ECONOMIC_RESULTS, FIELD_PLAYER_CARDS, FIELD_POSITION, FIELD_POT,
    FIELD_SHOWDOWN, FIELD_STACK, FIELD_WINNER, INVALID, VALID,
    DeclaredDefects, EligibilityShadow, assess_hand, collect_counts,
    load_declared, model_fingerprint, observation_eligibility,
    oracle_breakdown, preflop_event_contexts, preflop_event_eligibility,
    stats_counts, iter_observation_contexts)
from motor.learn import load_hands, preflop_events
from motor.observations import extract_hand
from motor.profile import Profiles
from motor.stats import TransitionStats


# ---------------------------------------------------------------------------
# Constructores de manos sintéticas
# ---------------------------------------------------------------------------
def p(pos, name, stack=100.0, cards=''):
    return {'pos': pos, 'name': name, 'stack': stack, 'cards': cards,
            'active': True}


def a(pos, action, amount=0.0):
    return {'pos': pos, 'action': action, 'amount': amount}


def hand(hid, players, preflop, flop=None, turn=None, river=None,
         flop_board=(), turn_board=(), river_board=(), pot=100.0,
         showdown=None, winner=None, comunitarias=None):
    streets = {
        'preflop': {'actions': preflop, 'board': []},
        'flop': {'actions': flop or [], 'board': list(flop_board)},
        'turn': {'actions': turn or [], 'board': list(turn_board)},
        'river': {'actions': river or [], 'board': list(river_board)},
    }
    com = comunitarias if comunitarias is not None else {
        'flop': list(flop_board), 'turn': list(turn_board),
        'river': list(river_board)}
    return {'hand_id': hid, 'players': players, 'streets': streets,
            'comunitarias': com, 'final_pot': pot,
            'showdown': showdown or {}, 'winner': winner or []}


def valid_hand(hid='H_VALID'):
    return hand(
        hid,
        [p('UTG', 'Alice', 100.0, 'AhKh'),
         p('SB', 'Bob', 100.0, 'QhJh'),
         p('BB', 'Carol', 100.0, '')],
        [a('SB', 'p', 0.5), a('BB', 'p', 1.0), a('UTG', 'b', 3.0),
         a('SB', 'c', 3.0), a('BB', 'c', 3.0)],
        [a('SB', 'x'), a('BB', 'x'), a('UTG', 'b', 4.0),
         a('SB', 'f'), a('BB', 'f')],
        flop_board=('2h', '7d', '9c'), pot=20.0,
        showdown={'winner1': 'UTG (Alice)'}, winner=['p1'])


def fold_then_check_hand(hid='H_FOLD'):
    """SB se retira en flop y luego aparece checkeando turn (tipo H_0926)."""
    return hand(
        hid,
        [p('UTG', 'Alice', 100.0, 'AhKh'),
         p('SB', 'Bob', 100.0, 'QhJh'),
         p('BB', 'Carol', 100.0, 'KsQs')],
        [a('SB', 'p', 0.5), a('BB', 'p', 1.0), a('UTG', 'b', 3.0),
         a('SB', 'c', 3.0), a('BB', 'c', 3.0)],
        [a('SB', 'x'), a('BB', 'x'), a('UTG', 'b', 4.0),
         a('SB', 'f'), a('BB', 'c', 4.0)],
        [a('SB', 'x'), a('BB', 'x'), a('UTG', 'b', 5.0),
         a('BB', 'c', 5.0)],
        flop_board=('2h', '7d', '9c'), turn_board=('Ts',), pot=30.0)


def zero_bet_hand(hid='H_ZERO'):
    return hand(
        hid,
        [p('UTG', 'Alice', 100.0, 'AhKh'),
         p('MP', 'Bob', 100.0, 'KsQs'),
         p('CO', 'Carol', 100.0, 'QhJh')],
        [a('SB', 'p', 0.5), a('BB', 'p', 1.0), a('UTG', 'f'),
         a('MP', 'b', 3.0), a('CO', 'c', 3.0),
         a('SB', 'f'), a('BB', 'f')],
        [a('CO', 'x')], [a('CO', 'x')],
        [a('CO', 'x'), a('MP', 'b', 0.0), a('CO', 'f')],
        flop_board=('2h', '7d', '9c'), turn_board=('Ts',),
        river_board=('4d',), pot=10.0)


def short_limp_hand(hid='H_LIMP'):
    return hand(
        hid,
        [p('CO', 'Alice', 100.0, 'AhKh'),
         p('BTN', 'Dan', 100.0, ''),
         p('SB', 'Bob', 100.0, ''),
         p('BB', 'Carol', 100.0, '')],
        [a('SB', 'p', 0.5), a('BB', 'p', 1.0), a('CO', 'b', 1.0),
         a('BTN', 'f'), a('SB', 'f'), a('BB', 'x')],
        [a('BB', 'x'), a('CO', 'x')],
        flop_board=('2h', '7d', '9c'), pot=10.0)


def no_cards_hand(hid='H_NOCARDS'):
    h = valid_hand(hid)
    for pl in h['players']:
        pl['cards'] = ''
    return h


# ---------------------------------------------------------------------------
# Fixtures de integración
# ---------------------------------------------------------------------------
@pytest.fixture(scope='module')
def window_hands():
    return load_hands(reliable_only=True)


@pytest.fixture(scope='module')
def base_hands():
    return load_hands(reliable_only=False)


@pytest.fixture(scope='module')
def window_counts(window_hands):
    labels = {n: pr.label
              for n, pr in Profiles.from_hands(window_hands).profiles.items()}
    return collect_counts(window_hands, labels, load_declared())


# ---------------------------------------------------------------------------
# Acciones: restricción por observación, no por mano
# ---------------------------------------------------------------------------
def test_action_after_fold_only_restricts_that_observation():
    h = fold_then_check_hand()
    he = assess_hand(h)
    invalid = [i for i in he.issues if i.severity == INVALID]
    assert len(invalid) == 1
    assert invalid[0].code == 'accion_tras_fold'
    assert invalid[0].street == 'turn' and invalid[0].index == 0
    # La mano no se excluye: todas sus observaciones siguen existiendo.
    assert len(iter_observation_contexts(h)) == len(extract_hand(h))


def test_h0926_like_only_sb_x_restricted():
    h = fold_then_check_hand('H_0926_LIKE')
    declared = DeclaredDefects(hard_sequence={
        h['hand_id']: {'street': 'turn', 'index': 0,
                       'evidence': 'SB x después de retirarse'}})
    he = assess_hand(h, declared)
    restricted = []
    for o, (st, si, _ri, pos, act, _amt) in iter_observation_contexts(h):
        e = observation_eligibility(he, o, st, si,
                                    CONSUMER_ORACLE_MARGINAL)
        if e.restricted:
            restricted.append((st, pos, act))
    assert restricted == [('turn', 'SB', 'x')]
    # Las demás acciones del turn siguen siendo usables.
    turn_obs = [(o, c) for o, c in iter_observation_contexts(h)
                if c[0] == 'turn']
    assert len(turn_obs) == 4
    for o, (st, si, _ri, _pos, _act, _amt) in turn_obs:
        if o.pos != 'SB':
            e = observation_eligibility(
                he, o, st, si, CONSUMER_ORACLE_MARGINAL)
            assert e.usable


def test_zero_bet_restricts_bet_and_dependent_fold():
    h = zero_bet_hand()
    he = assess_hand(h)
    river = [(o, c) for o, c in iter_observation_contexts(h)
             if c[0] == 'river']
    status = []
    for o, (st, si, _ri, pos, act, _amt) in river:
        e = observation_eligibility(he, o, st, si,
                                    CONSUMER_ORACLE_MARGINAL)
        status.append((pos, act, e.usable, e.direct, e.dependent))
    # CO x es anterior y válido; MP b 0.0 es directo; CO f depende del b 0.
    assert status[0] == ('CO', 'x', True, False, False)
    assert status[1][0:2] == ('MP', 'b') and status[1][2] is False
    assert status[1][3] is True
    assert status[2][0:2] == ('CO', 'f') and status[2][2] is False
    assert status[2][4] is True


def test_action_order_is_separate_from_action_validity():
    h = zero_bet_hand()
    he = assess_hand(h)
    # La apuesta cero invalida la acción, no el orden de las acciones.
    assert he.field(FIELD_ACTIONS).status == INVALID
    assert he.field(FIELD_ACTION_ORDER).status == VALID


def test_check_facing_bet_is_restricted_without_excluding_prior_bet():
    h = valid_hand('H_CHECK_BET')
    h['streets']['flop']['actions'] = [a('UTG', 'b', 4.0), a('SB', 'x')]
    he = assess_hand(h)
    issue = next(i for i in he.issues
                 if i.code == 'check_enfrentando_apuesta')
    obs = list(iter_observation_contexts(h))
    first = observation_eligibility(
        he, obs[0][0], obs[0][1][0], obs[0][1][1],
        CONSUMER_ORACLE_MARGINAL)
    second = next(observation_eligibility(
        he, o, ctx[0], ctx[1], CONSUMER_ORACLE_MARGINAL)
        for o, ctx in obs if ctx[0] == 'flop' and ctx[3] == 'SB')
    assert issue.pos == 'SB'
    assert first.usable
    assert second.restricted and second.direct


def test_calling_own_bet_restricts_call_not_bet():
    h = valid_hand('H_OWN_CALL')
    h['streets']['flop']['actions'] = [a('UTG', 'b', 4.0),
                                       a('UTG', 'c', 4.0)]
    he = assess_hand(h)
    own_call = next(i for i in he.issues
                    if i.code == 'call_su_propia_apuesta')
    rows = [(o, ctx) for o, ctx in iter_observation_contexts(h)
            if ctx[0] == 'flop']
    assert own_call.pos == 'UTG'
    assert observation_eligibility(
        he, rows[0][0], rows[0][1][0], rows[0][1][1],
        CONSUMER_ORACLE_MARGINAL).usable
    call = observation_eligibility(
        he, rows[1][0], rows[1][1][0], rows[1][1][1],
        CONSUMER_ORACLE_MARGINAL)
    assert call.restricted and call.direct


def test_repeated_check_restricts_only_repeat():
    h = valid_hand('H_REPEAT')
    h['streets']['flop']['actions'] = [a('UTG', 'x'), a('UTG', 'x')]
    he = assess_hand(h)
    issue = next(i for i in he.issues
                 if i.code == 'check_repetido_sin_apuesta')
    rows = [(o, ctx) for o, ctx in iter_observation_contexts(h)
            if ctx[0] == 'flop']
    assert issue.index == 1
    assert observation_eligibility(
        he, rows[0][0], rows[0][1][0], rows[0][1][1],
        CONSUMER_ORACLE_MARGINAL).usable
    assert observation_eligibility(
        he, rows[1][0], rows[1][1][0], rows[1][1][1],
        CONSUMER_ORACLE_MARGINAL).restricted


def test_declared_index_resolved_by_evidence_not_by_number():
    h = zero_bet_hand('H_0327_LIKE')
    # El índice declarado apunta a CO f; la evidencia describe MP b 0.0.
    declared = DeclaredDefects(hard_sequence={
        h['hand_id']: {'street': 'river', 'index': 2,
                       'evidence': 'MP b 0.0 apuesta de importe cero'}})
    he = assess_hand(h, declared)
    invalid = [i for i in he.issues if i.severity == INVALID]
    assert len(invalid) == 1
    assert invalid[0].pos == 'MP' and invalid[0].amount == 0.0
    assert invalid[0].index == 1
    assert not any(i.index == 2 and i.severity == INVALID
                   for i in he.issues)


def test_short_limp_is_reclassified_not_restricted():
    h = short_limp_hand()
    declared = DeclaredDefects(order_or_code={
        h['hand_id']: 'preflop.actions[2]: CO b 1.0 limp corto'})
    he = assess_hand(h, declared)
    issue = next(i for i in he.issues if i.code == 'subida_sin_incremento')
    assert issue.severity == 'code_ambiguous'
    assert issue.source == 'declared+detected'
    event = next(e for e in preflop_events(h) if e.pos == 'CO')
    seq_i = next(si for e, si, _st in preflop_event_contexts(h)
                 if e.pos == 'CO')
    elig = preflop_event_eligibility(
        he, event, seq_i, CONSUMER_PROFILE_RANGE)
    assert elig.usable
    assert any('corregida a limp' in r for r in elig.reasons)
    # En Oracle la celda preflop b no distingue limp de subida: se restringe
    # solo esa observación, no la mano ni el evento de rangos.
    o, ctx = next(x for x in iter_observation_contexts(h)
                  if x[1][3] == 'CO' and x[1][4] == 'b')
    oe = observation_eligibility(he, o, ctx[0], ctx[1],
                                 CONSUMER_ORACLE_MARGINAL)
    assert oe.restricted
    assert any('limp corto' in r for r in oe.reasons)
    # Un detector similar sin respaldo declarativo se informa, pero no se
    # convierte en una restricción automática.
    undeclared = assess_hand(h, DeclaredDefects(hard_sequence={
        'H_OTHER': {'street': 'river', 'index': 0, 'evidence': 'otra'}}))
    o2, ctx2 = next(x for x in iter_observation_contexts(h)
                    if x[1][3] == 'CO' and x[1][4] == 'b')
    oe2 = observation_eligibility(undeclared, o2, ctx2[0], ctx2[1],
                                  CONSUMER_ORACLE_MARGINAL)
    assert oe2.usable


def test_non_declared_detected_issue_is_not_activated():
    h = fold_then_check_hand()
    # Un inventario no vacío activa solo sus claves. Otra mano no declarada
    # conserva el detector como ambiguo, no como restricción.
    declared = DeclaredDefects(hard_sequence={
        'H_OTHER': {'street': 'turn', 'index': 0,
                    'evidence': 'otra mano'}})
    he = assess_hand(h, declared)
    assert all(i.severity != INVALID for i in he.issues)
    for o, (st, si, _ri, _pos, _act, _amt) in iter_observation_contexts(h):
        e = observation_eligibility(he, o, st, si,
                                    CONSUMER_ORACLE_MARGINAL)
        assert e.usable


# ---------------------------------------------------------------------------
# Tablero: marginal vs granular
# ---------------------------------------------------------------------------
def test_board_contradiction_keeps_streets_board():
    h = valid_hand('H_CONTRA')
    h['comunitarias']['flop'] = ['2h', '2h', '9c']   # duplicada
    he = assess_hand(h)
    b = he.boards['flop']
    assert b.status == VALID
    assert b.contradiction
    assert b.granular_usable
    assert not b.comunitarias_usable
    o, (st, si, _ri, _pos, _act, _amt) = next(
        x for x in iter_observation_contexts(h) if x[1][0] == 'flop')
    m = observation_eligibility(he, o, st, si, CONSUMER_ORACLE_MARGINAL)
    g = observation_eligibility(he, o, st, si, CONSUMER_ORACLE_GRANULAR)
    p = observation_eligibility(he, o, st, si, CONSUMER_POSTFLOP_RANGE)
    assert m.usable and m.board_warning
    assert g.usable and g.board_warning   # usa streets, no comunitarias
    assert p.usable and p.board_warning


def test_absent_board_marginal_usable_granular_not():
    h = fold_then_check_hand('H_NOBOARD')
    # El turn no tiene tablero; el flop sí.
    h['streets']['turn']['board'] = []
    h['comunitarias']['turn'] = []
    he = assess_hand(h)
    assert he.boards['turn'].status == ABSENT
    turn = [(o, c) for o, c in iter_observation_contexts(h)
            if c[0] == 'turn']
    o, (st, si, _ri, _pos, _act, _amt) = turn[-1]   # UTG b
    m = observation_eligibility(he, o, st, si, CONSUMER_ORACLE_MARGINAL)
    g = observation_eligibility(he, o, st, si, CONSUMER_ORACLE_GRANULAR)
    p = observation_eligibility(he, o, st, si, CONSUMER_POSTFLOP_RANGE)
    assert m.usable
    assert not g.usable
    assert not p.usable


def test_absent_board_does_not_invalidate_preflop():
    h = fold_then_check_hand('H_NOBOARD2')
    h['streets']['turn']['board'] = []
    h['comunitarias']['turn'] = []
    he = assess_hand(h)
    o, (st, si, _ri, _pos, _act, _amt) = next(
        x for x in iter_observation_contexts(h) if x[1][0] == 'preflop')
    m = observation_eligibility(he, o, st, si, CONSUMER_ORACLE_MARGINAL)
    g = observation_eligibility(he, o, st, si, CONSUMER_ORACLE_GRANULAR)
    assert m.usable and g.usable


# ---------------------------------------------------------------------------
# Bote, stack, cartas, showdown
# ---------------------------------------------------------------------------
def test_pot_nada_restricts_economic_only():
    h = valid_hand('H_NADA')
    h['final_pot'] = 'NADA'
    he = assess_hand(h)
    assert he.field(FIELD_POT).status == ABSENT
    assert he.field(FIELD_ECONOMIC_RESULTS).status == INVALID
    # Las acciones y el tablero no se contaminan.
    assert he.field(FIELD_ACTIONS).status == VALID
    assert he.field(FIELD_BOARD).status == VALID


def test_pot_unreliable_restricts_economic():
    h = valid_hand('H_POTBAD')
    he = assess_hand(h, DeclaredDefects(pot_unreliable={h['hand_id']}))
    assert he.field(FIELD_POT).status == DERIVED
    assert he.field(FIELD_ECONOMIC_RESULTS).status == INVALID


def test_pot_conflict_only_is_not_activated():
    h = valid_hand('H_POTCONF')
    he = assess_hand(h, DeclaredDefects(
        pot_internal_conflict={h['hand_id']: {}}))
    assert he.field(FIELD_POT).status == AMBIGUOUS
    assert he.field(FIELD_ECONOMIC_RESULTS).status == VALID


def test_pot_absent_restricts_economic():
    h = valid_hand('H_POTNONE')
    h['final_pot'] = None
    he = assess_hand(h)
    assert he.field(FIELD_POT).status == ABSENT
    assert he.field(FIELD_ECONOMIC_RESULTS).status == INVALID


def test_null_stack_not_canonical_but_action_usable():
    h = valid_hand('H_NULLSTACK')
    h['players'][0]['stack'] = None
    he = assess_hand(h)
    assert he.field(FIELD_STACK).status == DERIVED
    assert 'Alice' in he.null_stack_names
    o, (st, si, _ri, _pos, _act, _amt) = next(
        x for x in iter_observation_contexts(h)
        if x[0].player == 'Alice')
    e = observation_eligibility(he, o, st, si, CONSUMER_ORACLE_MARGINAL)
    assert e.usable
    assert e.label_warning


def test_derived_stack_not_canonical():
    h = valid_hand('H_DERIVEDSTACK')
    he = assess_hand(h, DeclaredDefects(recovered_values={
        h['hand_id']: {'stack_initial_candidate': 50.0,
                       'status': 'derived'}}))
    assert he.field(FIELD_STACK).status == DERIVED
    assert not he.field(FIELD_STACK).canonical


def test_missing_allin_is_for_future_conditioned_consumers_only():
    h = valid_hand('H_NO_ALLIN')
    he = assess_hand(h, DeclaredDefects(missing_allin={h['hand_id']}))
    allin = he.field('allin')
    assert allin.status == ABSENT
    assert not allin.canonical
    assert allin.marginal_usable
    assert not allin.conditioned_usable
    for o, (st, si, _ri, _pos, _act, _amt) in iter_observation_contexts(h):
        assert observation_eligibility(
            he, o, st, si, CONSUMER_ORACLE_MARGINAL).usable


def test_player_identity_is_separate_from_position():
    h = valid_hand('H_DUP_NAME')
    h['players'][1]['name'] = h['players'][0]['name']
    he = assess_hand(h)
    assert he.field(FIELD_POSITION).status == VALID
    assert he.field('player_identity').status == INVALID
    # Oracle por posición sigue existiendo; no se invalida el orden de acción.
    assert he.field(FIELD_ACTION_ORDER).status == VALID


def test_every_field_decision_has_source_evidence():
    h = zero_bet_hand('H_EVIDENCE')
    he = assess_hand(h)
    assert set(he.fields) >= {
        FIELD_ACTIONS, FIELD_ACTION_ORDER, FIELD_POSITION,
        FIELD_PLAYER_CARDS, FIELD_BOARD, FIELD_POT, FIELD_STACK,
        FIELD_SHOWDOWN, FIELD_WINNER, FIELD_ECONOMIC_RESULTS,
    }
    for field_result in he.fields.values():
        assert field_result.evidence
        assert all(isinstance(item, str) for item in field_result.evidence)
    assert any('river.actions' in item
               for item in he.field(FIELD_ACTIONS).evidence)
    assert any('final_pot' in item
               for item in he.field(FIELD_POT).evidence)


def test_missing_cards_marginal_usable_conditioned_not():
    h = no_cards_hand()
    he = assess_hand(h)
    assert he.field(FIELD_PLAYER_CARDS).status == ABSENT
    o, (st, si, _ri, _pos, _act, _amt) = next(
        x for x in iter_observation_contexts(h))
    m = observation_eligibility(he, o, st, si, CONSUMER_ORACLE_MARGINAL)
    p = observation_eligibility(he, o, st, si, CONSUMER_POSTFLOP_RANGE)
    assert m.usable
    assert not p.usable


def test_showdown_incomplete_restricts_wsd_not_oracle():
    h = valid_hand('H_SPLIT')
    declared = DeclaredDefects(split_display_incomplete={h['hand_id']})
    he = assess_hand(h, declared)
    assert he.field(FIELD_WINNER).status == INVALID
    assert he.field(FIELD_SHOWDOWN).status == INVALID
    # Las observaciones de acción no dependen del texto de showdown.
    for o, (st, si, _ri, _pos, _act, _amt) in iter_observation_contexts(h):
        e = observation_eligibility(he, o, st, si,
                                    CONSUMER_ORACLE_MARGINAL)
        assert e.usable
    stats = stats_counts([h], declared)
    # El texto de split incompleto afecta al ganador (W$SD act), no a la
    # llegada al showdown (WTSD) ni al denominador de W$SD.
    assert stats['wsd_act']['restricted'] >= 1
    assert stats['wsd_opp']['restricted'] == 0
    assert stats['wtsd_opp']['restricted'] == 0
    assert stats['wtsd_act']['restricted'] == 0


def test_missing_position_identified_without_inventing_restriction():
    h = valid_hand('H_NOPOS')
    # Acción de una posición que no existe en players: extract_hand la
    # descarta; la política lo reporta, no la inventa.
    h['streets']['flop']['actions'].append(a('MP', 'x', 0.0))
    he = assess_hand(h)
    assert he.field(FIELD_POSITION).status == AMBIGUOUS
    assert he.field(FIELD_POSITION).detail['skipped_actions'] == 1
    assert len(iter_observation_contexts(h)) == len(extract_hand(h))
    # Declarada como activa, se marca ausente (no se activa una posición).
    he2 = assess_hand(h, DeclaredDefects(
        active_no_position_hands={h['hand_id']}))
    assert he2.field(FIELD_POSITION).status == ABSENT


# ---------------------------------------------------------------------------
# Integración: ventana 877
# ---------------------------------------------------------------------------
def test_window_consumer_counts(window_counts):
    c = window_counts
    m = c['consumers'][CONSUMER_ORACLE_MARGINAL]
    g = c['consumers'][CONSUMER_ORACLE_GRANULAR]
    p = c['consumers'][CONSUMER_POSTFLOP_RANGE]
    pr = c['consumers'][CONSUMER_PROFILE_RANGE]
    pre = c['consumers'][CONSUMER_PREFLOP_STATS]
    sd = c['consumers'][CONSUMER_SHOWDOWN]
    eco = c['consumers'][CONSUMER_ECONOMIC]
    assert c['oracle_total'] == 8657
    assert (m['before'], m['after'], m['restricted']) == (8657, 8633, 24)
    assert (m['restricted_direct'], m['restricted_dependent'],
            m['restricted_code']) == (9, 13, 2)
    assert (m['restricted_preflop'], m['restricted_postflop']) == (11, 13)
    assert (g['before'], g['after'], g['restricted']) == (3695, 3671, 24)
    assert (g['restricted_action'], g['restricted_board']) == (13, 11)
    assert (p['before'], p['after'], p['restricted']) == (1388, 1386, 2)
    assert p['known_with_cards'] == 1396
    assert p['dropped_by_absent_board'] == 8
    assert p['contradiction_warning'] == 16
    assert (pr['before'], pr['after'], pr['restricted']) == (1168, 1167, 1)
    assert (pre['before'], pre['after'], pre['restricted']) == \
        (4594, 4588, 6)
    assert (sd['before'], sd['after'], sd['restricted']) == (451, 450, 1)
    assert (eco['before'], eco['after'], eco['restricted']) == (877, 877, 0)


def test_window_oracle_breakdown_126(window_counts):
    b = window_counts['oracle_breakdown']
    total = {k: sum(x[k] for x in b.values())
             for k in ('total', 'directas', 'dependientes',
                       'codigo_restringido', 'ambiguas_no_activadas',
                       'independientes')}
    assert total == {'total': 126, 'directas': 9, 'dependientes': 13,
                     'codigo_restringido': 2, 'ambiguas_no_activadas': 1,
                     'independientes': 101}
    # H_0926: solo la SB x; no se descarta el resto.
    assert (b['H_0926']['directas'], b['H_0926']['dependientes'],
            b['H_0926']['independientes']) == (1, 0, 15)
    # H_0832: limp corto: restringido en la celda Oracle b, usable como limp
    # en preflop_stats/ProfileRange.
    assert (b['H_0832']['directas'], b['H_0832']['dependientes'],
            b['H_0832']['codigo_restringido']) == (0, 0, 1)
    # H_0005: 1 directa, 4 dependientes, 1 limp corto, resto intacto.
    assert (b['H_0005']['directas'], b['H_0005']['dependientes'],
            b['H_0005']['codigo_restringido'],
            b['H_0005']['ambiguas_no_activadas']) == (1, 4, 0, 1)
    for per_hand in b.values():
        for row in per_hand['rows']:
            assert '.actions[' in row['evidence']
            assert '%s %s ' % (row['pos'], row['action']) \
                in row['evidence']
            assert 'marginal_usable' in row and 'granular_usable' in row
            assert isinstance(row['consumer_reasons'], list)


def test_window_detected_but_not_declared_not_activated(window_hands):
    declared = load_declared()
    by_id = {h['hand_id']: h for h in window_hands}
    for hid in ('H_0475', 'H_0738'):
        he = assess_hand(by_id[hid], declared)
        assert any(i.code == 'posta_repetida' and i.severity == AMBIGUOUS
                   for i in he.issues)
        for o, (st, si, _ri, _pos, _act, _amt) in \
                iter_observation_contexts(by_id[hid]):
            e = observation_eligibility(he, o, st, si,
                                        CONSUMER_ORACLE_MARGINAL)
            assert e.usable


def test_base_economic_restricts_only_39(base_hands):
    c = collect_counts(base_hands, None, load_declared())
    assert c['consumers'][CONSUMER_ECONOMIC]['restricted'] == 39


def test_stats_before_matches_transition_stats(window_hands):
    actual = TransitionStats.from_hands(window_hands)
    from collections import Counter
    before = Counter()
    for _name, data in actual.to_dict().items():
        for stat, (opp, act) in data['stats'].items():
            before[stat + '_opp'] += opp
            before[stat + '_act'] += act
    ours = stats_counts(window_hands, load_declared())
    for stat in ('vpip', 'pfr', 'b3', 'b4', 'cbet', 'bar', 'rb',
                 'f2cb', 'c2cb', 'r2cb', 'f2bar', 'wtsd', 'wsd'):
        assert ours.get(stat + '_opp', {}).get('before', 0) == \
            before.get(stat + '_opp', 0), stat
        assert ours.get(stat + '_act', {}).get('before', 0) == \
            before.get(stat + '_act', 0), stat


def test_13_declared_sequences_are_found(base_hands):
    declared = load_declared()
    by_id = {h['hand_id']: h for h in base_hands}
    assert len(declared.hard_sequence) == 13
    for hid, d in declared.hard_sequence.items():
        he = assess_hand(by_id[hid], declared)
        invalid = [i for i in he.issues if i.severity == INVALID]
        assert invalid, hid
    # H_0327: índice declarado 2, acción real 1.
    he = assess_hand(by_id['H_0327'], declared)
    inv = [i for i in he.issues if i.severity == INVALID]
    assert len(inv) == 1 and inv[0].index == 1 and inv[0].amount == 0.0
    # H_0834: el detector no lo ve, lo aporta el declarado.
    he = assess_hand(by_id['H_0834'], declared)
    inv = [i for i in he.issues if i.severity == INVALID]
    assert len(inv) == 1 and inv[0].source == 'declared'
    # H_0832 no es una acción imposible: es un limp corto codificado.
    he = assess_hand(by_id['H_0832'], declared)
    assert all(i.severity != INVALID for i in he.issues)


# ---------------------------------------------------------------------------
# Sombra: no cambia modelos ni manos
# ---------------------------------------------------------------------------
def test_shadow_report_does_not_mutate_hands():
    hands = [valid_hand('H_S1'), fold_then_check_hand('H_S2'),
             zero_bet_hand('H_S3'), short_limp_hand('H_S4')]
    snapshot = copy.deepcopy(hands)
    collect_counts(hands, None, load_declared())
    assert hands == snapshot


def test_shadow_does_not_change_models(monkeypatch):
    import motor.asistente_live as live
    fixtures = [valid_hand('H_M1'), fold_then_check_hand('H_M2'),
                zero_bet_hand('H_M3'), short_limp_hand('H_M4')]
    monkeypatch.setattr(
        live, 'load_hands',
        lambda reliable_only=True: copy.deepcopy(fixtures))
    with contextlib.redirect_stdout(io.StringIO()):
        a = live.build_models(verbose=False)
        fp_a = model_fingerprint(a.range_model, a.oracle, a.postflop_model)
        shadow = EligibilityShadow()
        b = live.build_models(verbose=False, eligibility_shadow=shadow)
        fp_b = model_fingerprint(b.range_model, b.oracle, b.postflop_model)
    assert fp_a == fp_b
    assert shadow.report is not None
    assert shadow.report['oracle_total'] == len(extract_hand(fixtures[0])) + \
        sum(len(extract_hand(h)) for h in fixtures[1:])
    # Recorre también una salida de recomendación determinista con ambos
    # builds. El hook no participa en la elección.
    from types import SimpleNamespace
    aa = live.Asistente.__new__(live.Asistente)
    bb = live.Asistente.__new__(live.Asistente)
    for assistant, models in ((aa, a), (bb, b)):
        assistant.models = models
        assistant.oracle = models.oracle
        assistant.rec = SimpleNamespace(hand=None)
        assistant.verbose = False
        assistant.shadow = False
        assistant.decision_log = None
    state = {'p1_state': 'activo', 'p1_stake': 100.0, 'p1_bet': 0.0,
             'p2_state': 'activo', 'p2_stake': 100.0, 'p2_bet': 0.0,
             'p3_state': 'activo', 'p3_stake': 100.0, 'p3_bet': 0.0,
             'p4_state': 'activo', 'p4_stake': 100.0, 'p4_bet': 0.5,
             'p5_state': 'activo', 'p5_stake': 100.0, 'p5_bet': 1.0}
    args = (state, ['As', 'Ks'], 'BTN', 0.0, 1.5, 1.0,
            'TIBURON', 'villain', None, False)
    reco_a = aa._recom_preflop(*args, seed=37, effective_stack=100.0)
    reco_b = bb._recom_preflop(*args, seed=37, effective_stack=100.0)
    assert (reco_a.chosen, reco_a.ev, reco_a.candidate_actions,
            reco_a.preflop_sampling) == \
           (reco_b.chosen, reco_b.ev, reco_b.candidate_actions,
            reco_b.preflop_sampling)


def test_no_whole_hand_exclusion_in_breakdown():
    h = fold_then_check_hand('H_NOEXCL')
    b = oracle_breakdown([h], DeclaredDefects(hard_sequence={
        h['hand_id']: {'street': 'turn', 'index': 0,
                       'evidence': 'SB x después de retirarse'}}))
    assert b['H_NOEXCL']['total'] == len(extract_hand(h))
    assert b['H_NOEXCL']['independientes'] > 0
