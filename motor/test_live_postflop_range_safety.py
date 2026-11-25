"""Regresiones de contexto, replay e inhibición del recomendador live."""
from types import SimpleNamespace

import numpy as np

from motor import asistente_live as live
from motor.asistente_live import (
    Asistente, _strict_preflop_range_query, _villain_postflop_actions,
)
from motor.decision import EvTable
from motor.ranges import N_COMBOS, RangeState


def _hand(preflop, flop=None, turn=None, river=None):
    return {
        'hand_id': 'RANGE-SAFETY',
        'streets': {
            'preflop': {'actions': list(preflop)},
            'flop': {'actions': list(flop or []),
                     'board': ['Qh', '7s', '2c']},
            'turn': {'actions': list(turn or []), 'board': ['3d']},
            'river': {'actions': list(river or []), 'board': ['4c']},
        },
        'current_street': 'flop',
    }


def _asistente(hand, postflop_model=None):
    a = Asistente.__new__(Asistente)
    a.rec = SimpleNamespace(
        hand=hand,
        _hand_positions={'hero': 'UTG', 'p1': 'BB', 'p2': 'CO',
                         'p3': 'BTN', 'p4': 'SB', 'p5': 'MP'},
    )
    a.models = SimpleNamespace(
        range_model=SimpleNamespace(
            prob_vec=lambda *args, **kwargs: np.ones(N_COMBOS, dtype=np.float32)),
        postflop_model=postflop_model,
    )
    a.live_stacks = {}
    a._last_seen_stake = {}
    a.verbose = False
    a.shadow = False
    a.runout = False
    a.hero_name = live.HERO_NAME_DEFAULT
    a.oracle = SimpleNamespace(p_action=lambda *args, **kwargs: None)
    return a


class _LikelihoodModel:
    def __init__(self, supported=True, vectors=None):
        self.supported = supported
        self.vectors = vectors or {}
        self.calls = []

    def prob_vec(self, profile, street, facing, board, action):
        self.calls.append((street, facing, action, tuple(board)))
        value = self.vectors.get((street, action))
        if value is None:
            value = np.ones(N_COMBOS, dtype=np.float32)
        return np.asarray(value, dtype=np.float32)

    def evidence_for_vector(self, profile, street, facing, board, action):
        if not self.supported:
            source, count = None, 0
        else:
            source, count = 'por_facing', 12
        return {
            'buckets': [
                {'bucket': bucket, 'observation_count': 0,
                 'prior_evidence': {
                     'source': source,
                     'distribution_available': self.supported,
                     'support_observations': count,
                 }}
                for bucket in range(5)
            ]
        }


def test_preflop_open_utg_se_resuelve_como_or_no_como_3bet():
    hand = _hand([
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
    ])
    query = _strict_preflop_range_query(hand, 'UTG')
    assert query['status'] == 'resolved'
    assert (query['denom'], query['category'], query['table_action']) == (
        'no_raise', 'open', 'OR')
    assert query['classification']['context']['raises_before'] == 0
    assert query['classification']['context']['aggressors'] == []


def test_preflop_3bet_requiere_open_previo_y_conserva_agresor():
    hand = _hand([
        {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        {'pos': 'CO', 'action': 'r', 'amount': 8.0},
    ])
    query = _strict_preflop_range_query(hand, 'CO')
    assert (query['status'], query['denom'], query['category']) == (
        'resolved', 'facing_open', '3bet')
    assert query['villain_pos'] == 'UTG'
    assert query['classification']['context']['aggressors'] == ['UTG']


def test_preflop_4bet_requiere_3bet_previo_y_usa_segundo_agresor():
    hand = _hand([
        {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        {'pos': 'MP', 'action': 'r', 'amount': 8.0},
        {'pos': 'CO', 'action': 'r', 'amount': 22.0},
    ])
    query = _strict_preflop_range_query(hand, 'CO')
    assert (query['status'], query['denom'], query['category']) == (
        'resolved', 'facing_3bet', '4bet')
    assert query['villain_pos'] == 'MP'
    assert query['classification']['context']['aggressors'] == ['UTG', 'MP']


def test_preflop_limp_raise_y_blinds_no_se_confunden():
    hand = _hand([
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'b', 'amount': 1.0},
        {'pos': 'MP', 'action': 'r', 'amount': 3.0},
    ])
    query = _strict_preflop_range_query(hand, 'MP')
    assert query['status'] == 'resolved'
    assert (query['denom'], query['category']) == ('no_raise', 'rol')
    assert query['classification']['context']['limps_before'] == 1
    assert query['classification']['context']['blind_posts'] == ['SB', 'BB']


def test_preflop_history_missing_ambiguous_o_incompleto_no_inventa_nodo():
    assert _strict_preflop_range_query(None, 'UTG')['reason'] == \
        'preflop_history_missing'
    no_amount = _strict_preflop_range_query(
        _hand([{'pos': 'UTG', 'action': 'r'}]), 'UTG')
    assert no_amount['status'] == 'unresolved'
    repeated = _strict_preflop_range_query(_hand([
        {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        {'pos': 'UTG', 'action': 'r', 'amount': 8.0},
    ]), 'UTG')
    assert repeated['status'] == 'unresolved'
    assert repeated['reason'] == 'multiple_preflop_decisions_unmodeled'


def test_tabla_preflop_faltante_abstiene_antes_de_consultar_prior_plano():
    hand = _hand([{'pos': 'BB', 'action': 'r', 'amount': 2.5}])
    called = []
    a = _asistente(hand)
    a.models.range_model.prob_vec = lambda *args, **kwargs: called.append(args)
    rs, info = a._initial_range_for_villain('TIBURON', 'BB')
    assert rs is None
    assert info['status'] == 'coverage_insufficient'
    assert info['prior']['classification'] == 'missing'
    assert called == []


def test_prior_exacto_y_fuente_quedan_sellados_en_rangestate():
    a = _asistente(_hand([{'pos': 'UTG', 'action': 'r', 'amount': 2.5}]))
    rs, info = a._initial_range_for_villain('TIBURON', 'UTG')
    assert rs is not None
    assert rs.source == 'profile_range:prior_exact:OR_UTG'
    assert info['prior']['classification'] == 'exact'
    assert info['prior']['matrix_provenance'] == 'unknown'
    assert info['prior']['strategic_validation'] == 'not_established'


def test_nombre_estable_activa_rango_individual_y_desconocido_usa_grupo():
    class _RangeModel:
        def __init__(self):
            self.perfil = {'Alice': 'PEZ', 'Bob': 'PEZ'}
            self.profiles = SimpleNamespace(profiles={
                'Alice': SimpleNamespace(
                    label='PEZ', n=30,
                    stats={'vpip': 0.45, 'pfr': 0.05},
                    counts={'vpip': (20, 9), 'pfr': (20, 1)},
                    stack_mean=120.0),
                'Bob': SimpleNamespace(
                    label='PEZ', n=30,
                    stats={'vpip': 0.45, 'pfr': 0.08},
                    counts={'vpip': (20, 9), 'pfr': (20, 2)},
                    stack_mean=120.0),
            })
            self.player_calls = []
            self.group_calls = []

        def prob_vec_player(self, player, *args, **kwargs):
            self.player_calls.append(player)
            base = np.linspace(0.1, 0.9, N_COMBOS, dtype=np.float32)
            return base if player == 'Alice' else base[::-1].copy()

        def player_omega(self, player, spot):
            return 0.8 if player == 'Alice' else 1.2

        def prob_vec(self, profile, *args, **kwargs):
            self.group_calls.append(profile)
            return np.full(N_COMBOS, 0.4, dtype=np.float32)

    hand = _hand([{'pos': 'UTG', 'action': 'r', 'amount': 2.5}])
    a = _asistente(hand)
    range_model = _RangeModel()
    a.models = SimpleNamespace(
        labels={'Alice': 'PEZ', 'Bob': 'PEZ'}, range_model=range_model,
        postflop_model=_LikelihoodModel())
    names = {'p1': 'Alice', 'p2': 'Bob', 'p3': 'NewPlayer'}
    a._villain_name = lambda pid: names.get(pid, pid)

    assert a._perfil_for('p1', {'p1_stake': 25.0}) == 'PEZ'
    assert a._perfil_for('p2', {'p2_stake': 200.0}) == 'PEZ'
    assert a._perfil_for('p3', {'p3_stake': 25.0}) == live.UNKNOWN_PROFILE

    alice, alice_info = a._initial_range_for_villain(
        'PEZ', 'UTG', player_id='p1')
    bob, bob_info = a._initial_range_for_villain(
        'PEZ', 'UTG', player_id='p2')
    unknown, unknown_info = a._initial_range_for_villain(
        live.UNKNOWN_PROFILE, 'UTG', player_id='p3')
    assert range_model.player_calls == ['Alice', 'Bob']
    assert range_model.group_calls == [live.UNKNOWN_PROFILE]
    assert not np.array_equal(alice.reach, bob.reach)
    assert alice_info['prior']['individual_opportunities'] == 20
    assert alice_info['prior']['individual_range_used'] is True
    assert bob_info['prior']['individual_actions'] == 2
    assert unknown_info['prior']['identity_resolution'] == 'no_exact_history_match'
    assert unknown.source == 'profile_range:prior_exact:OR_UTG'


def test_check_observado_actualiza_rango_con_likelihood_y_no_es_ausencia():
    board = ['Qh', '7s', '2c']
    check_vector = np.full(N_COMBOS, 0.8, dtype=np.float32)
    check_vector[:N_COMBOS // 2] = 0.2
    model = _LikelihoodModel(vectors={('flop', 'x'): check_vector})
    a = _asistente(_hand([{'pos': 'UTG', 'action': 'r', 'amount': 2.5}],
                         flop=[{'pos': 'BB', 'action': 'x', 'amount': 0.0}]),
                   model)
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    before = rs.reach.copy()
    usable, trace, reason = a._replay_postflop_range(rs, 'TIBURON', 'BB')
    assert usable and reason is None
    assert model.calls == [('flop', 'none', 'x', tuple(board))]
    assert trace[0]['applied'] is True
    assert trace[0]['provenance'] == 'observed'
    assert not np.array_equal(rs.reach, before)


def test_prior_poblacional_mismo_facing_es_usable_sin_fingir_individualidad():
    from motor.behavior import Oracle
    from motor.postflop_ranges import PostflopRangeModel

    actions = {'x': 0.5, 'b': 0.1, 'c': 0.2, 'f': 0.1, 'r': 0.1}
    oracle = Oracle({'profiles': {}, 'granular': {}, 'por_facing': {
        ('PEZ', 'flop', 'none'): dict(actions, n=10),
        ('TIBURON', 'flop', 'none'): dict(actions, n=10),
    }})
    model = PostflopRangeModel(alpha=2.0)
    model._oracle = oracle
    hand = _hand([{'pos': 'UTG', 'action': 'r', 'amount': 2.5}],
                 flop=[{'pos': 'BB', 'action': 'x', 'amount': 0.0}])
    a = _asistente(hand, model)
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    before = rs.weights.copy()

    usable, trace, reason = a._replay_postflop_range(
        rs, live.UNKNOWN_PROFILE, 'BB')

    assert usable and reason is None
    assert trace[0]['applied'] is True
    assert trace[0]['likelihood']['evidence']['buckets'][0][
        'model_prior_source'] == 'poblacion_facing'
    # El prior sólo conoce acción/contexto poblacional, no fuerza de mano:
    # conserva la distribución de combos y no inventa un posterior individual.
    np.testing.assert_allclose(rs.weights, before)


def test_check_observado_sin_likelihood_invalida_y_no_modifica_reach():
    model = _LikelihoodModel(supported=False)
    a = _asistente(_hand([{'pos': 'UTG', 'action': 'r', 'amount': 2.5}],
                         flop=[{'pos': 'BB', 'action': 'x', 'amount': 0.0}]),
                   model)
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    before = rs.reach.copy()
    usable, trace, reason = a._replay_postflop_range(rs, 'TIBURON', 'BB')
    assert not usable
    assert reason == 'postflop_action_without_supported_likelihood'
    assert trace[0]['status'] == 'unincorporated'
    assert trace[0]['provenance'] == 'observed'
    assert np.array_equal(rs.reach, before)


def test_fallback_uniforme_no_se_acepta_como_likelihood_observado():
    class _FlatFallback(_LikelihoodModel):
        def evidence_for_vector(self, profile, street, facing, board, action):
            return {'buckets': [
                {'bucket': i, 'observation_count': 8,
                 'model_prior_source': 'flat_no_oracle',
                 'prior_evidence': {'source': None,
                                    'distribution_available': False,
                                    'support_observations': 0}}
                for i in range(5)]}

    model = _FlatFallback(supported=True)
    hand = _hand([{'pos': 'UTG', 'action': 'r', 'amount': 2.5}],
                 flop=[{'pos': 'BB', 'action': 'x', 'amount': 0.0}])
    a = _asistente(hand, model)
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    usable, trace, reason = a._replay_postflop_range(rs, 'TIBURON', 'BB')
    assert not usable
    assert reason == 'postflop_action_without_supported_likelihood'
    assert trace[0]['status'] == 'unincorporated'


def test_probabilidad_cero_sin_observaciones_de_accion_no_simula_imposibilidad():
    class _Evidence:
        def evidence_for_vector(self, *args):
            return {'buckets': [
                {'bucket': bucket, 'estimate': 0.0 if bucket == 2 else 0.2,
                 'observation_count': 10,
                 'action_observation_count': 0 if bucket == 2 else 1,
                 'model_prior_source': 'oracle',
                 'prior_evidence': {'source': 'por_facing',
                                    'distribution_available': True,
                                    'support_observations': 10}}
                for bucket in range(5)]}

    usable, evidence = Asistente._postflop_likelihood_coverage(
        _Evidence(), 'PEZ', 'flop', 'cbet', ['Qh', '7s', '2c'], 'r',
        np.full(N_COMBOS, 0.2, dtype=np.float32), active_buckets={2})
    assert not usable
    assert evidence['reason'] == 'zero_likelihood_without_action_observations'


def test_frecuencia_empirica_sin_prior_compatible_no_se_toma_como_precisa():
    class _EmpiricalOnly:
        def evidence_for_vector(self, *args):
            return {'buckets': [
                {'bucket': bucket, 'estimate': 0.5,
                 'observation_count': 1,
                 'action_observation_count': 1,
                 'model_prior_source': 'empirical_no_compatible_prior',
                 'prior_evidence': {'source': 'label',
                                    'distribution_available': True,
                                    'support_observations': 60}}
                for bucket in range(5)]}

    usable, evidence = Asistente._postflop_likelihood_coverage(
        _EmpiricalOnly(), 'PEZ', 'flop', 'cbet', ['Qh', '7s', '2c'], 'c',
        np.full(N_COMBOS, 0.5, dtype=np.float32), active_buckets={0, 1, 2, 3, 4})
    assert not usable
    assert evidence['reason'] == 'postflop_action_without_supported_likelihood'


def test_ausencia_de_accion_no_se_convierte_en_check():
    model = _LikelihoodModel()
    a = _asistente(_hand([{'pos': 'UTG', 'action': 'r', 'amount': 2.5}],
                         flop=[]), model)
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    before = rs.reach.copy()
    usable, trace, reason = a._replay_postflop_range(rs, 'TIBURON', 'BB')
    assert usable and trace == [] and reason is None
    assert model.calls == []
    assert np.array_equal(rs.reach, before)


def test_accion_inferida_se_distingue_y_accion_desconocida_bloquea():
    inferred_hand = _hand(
        [{'pos': 'UTG', 'action': 'r', 'amount': 2.5}],
        flop=[{'pos': 'BB', 'action': 'x', 'amount': 0.0,
               'inferred': True}])
    inferred_model = _LikelihoodModel()
    a = _asistente(inferred_hand, inferred_model)
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    usable, trace, _reason = a._replay_postflop_range(rs, 'TIBURON', 'BB')
    assert usable and trace[0]['provenance'] == 'inferred'
    assert trace[0]['applied'] is True

    unknown_hand = _hand(
        [{'pos': 'UTG', 'action': 'r', 'amount': 2.5}],
        flop=[{'pos': 'BB', 'action': '?', 'amount': None}])
    unknown_model = _LikelihoodModel()
    a = _asistente(unknown_hand, unknown_model)
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    usable, trace, reason = a._replay_postflop_range(
        rs, 'TIBURON', 'BB')
    assert not usable and reason == 'postflop_action_unrecognized'
    assert trace[0]['provenance'] == 'observed'
    assert unknown_model.calls == []


def test_accion_duplicada_y_pendiente_no_se_aplica_dos_veces():
    check = {'pos': 'BB', 'action': 'x', 'amount': 0.0, 'event_id': 'evt-1'}
    pending = {'pos': 'BB', 'action': 'c', 'amount': 3.0,
               'event_id': 'evt-pending', 'pending': True}
    hand = _hand([{'pos': 'UTG', 'action': 'r', 'amount': 2.5}],
                 flop=[check, dict(check), pending])
    records = _villain_postflop_actions(hand, 'BB', with_metadata=True)
    assert len(records) == 1
    assert records[0][2] == 'x'
    model = _LikelihoodModel()
    a = _asistente(hand, model)
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    usable, trace, _reason = a._replay_postflop_range(rs, 'TIBURON', 'BB')
    assert usable and len(trace) == 1 and len(model.calls) == 1


def test_replay_multicalle_multiplica_sobre_el_posterior_anterior():
    flop = np.full(N_COMBOS, 0.8, dtype=np.float32)
    turn = np.full(N_COMBOS, 0.7, dtype=np.float32)
    flop[0], turn[0] = 0.2, 0.3
    model = _LikelihoodModel(vectors={('flop', 'b'): flop,
                                     ('turn', 'c'): turn})
    hand = _hand(
        [{'pos': 'UTG', 'action': 'r', 'amount': 2.5}],
        flop=[{'pos': 'BB', 'action': 'b', 'amount': 3.0}],
        turn=[{'pos': 'CO', 'action': 'b', 'amount': 6.0},
              {'pos': 'BB', 'action': 'c', 'amount': 6.0}],
    )
    a = _asistente(hand, model)
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    usable, trace, reason = a._replay_postflop_range(rs, 'TIBURON', 'BB')
    assert usable and reason is None
    assert [event['street'] for event in trace] == ['flop', 'turn']
    assert [call[0] for call in model.calls] == ['flop', 'turn']
    assert np.isclose(rs.reach[0], 0.2 * 0.3)
    assert np.isclose(rs.reach[1], 0.8 * 0.7)


def test_blockers_siguen_cero_y_posterior_normaliza():
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(['As', 'Kd', 'Qh', '7s', '2c']).nullify_blocked()
    assert np.all(rs.reach[~rs.legal_mask] == 0.0)
    assert np.isclose(float(rs.weights.sum()), 1.0)


def _public_recommendation_fixture(folded_extra=False, villain_action=None,
                                   supported=True):
    flop_actions = ([{'pos': 'CO', 'action': 'f', 'amount': 0.0}]
                    if folded_extra else [])
    if villain_action is not None:
        flop_actions.append(villain_action)
    hand = _hand([
        {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        {'pos': 'BB', 'action': 'c', 'amount': 2.5},
    ], flop=flop_actions)
    hand['players'] = [{'pos': 'UTG', '_id': 'hero'},
                       {'pos': 'BB', '_id': 'p1'},
                       {'pos': 'CO', '_id': 'p2'}]
    a = _asistente(hand, _LikelihoodModel(supported=supported))
    a.rec._hand_positions = {'hero': 'UTG', 'p1': 'BB', 'p2': 'CO',
                             'p3': 'BTN', 'p4': 'SB', 'p5': 'MP'}
    return a


def _install_recommendation_stubs(monkeypatch, calls):
    class _Response:
        pf_p, pc_p, pr_p = 0.2, 0.7, 0.1
        alpha, source, sizing = 1.0, 'test', None
        evidence = {'source': 'test'}

        def __call__(self, equity, amount, pot):
            return np.full_like(equity, 0.2), np.full_like(equity, 0.7), \
                np.full_like(equity, 0.1)

    monkeypatch.setattr(live, 'OracleResponse', lambda *a, **k: _Response())
    monkeypatch.setattr(live, 'situation', lambda *a, **k:
                        SimpleNamespace(equity=0.5))
    monkeypatch.setattr(live, 'hand_classify', lambda *a, **k:
                        SimpleNamespace(role=None,
                                        nut_advantage=lambda: 'NEUTRAL'))

    def plan(*args, **kwargs):
        calls['plan'] = calls.get('plan', 0) + 1
        return SimpleNamespace(
            candidates=['fold', 'check'], bet_sizes=[], raise_to=None,
            spot='fixture', note='', multiway=False,
            multiway_soportado=True, multiway_motivo=None)

    def compute(*args, **kwargs):
        calls['compute'] = calls.get('compute', 0) + 1
        return EvTable(ev={'fold': 0.0, 'check': 0.1}, pot=10.0)

    def select(evs, rp):
        calls['select'] = calls.get('select', 0) + 1
        return 'check', 0.1

    monkeypatch.setattr(live, 'rules_plan', plan)
    monkeypatch.setattr(live, 'compute_evs', compute)
    monkeypatch.setattr(live, 'rules_select_best', select)
    monkeypatch.setattr(live, 'format_insight', lambda *a, **k: 'fixture')


def test_public_flow_mw_se_abstiene_antes_de_ev_y_select_best(monkeypatch):
    calls = {}
    _install_recommendation_stubs(monkeypatch, calls)
    a = _public_recommendation_fixture(folded_extra=False)
    state = {
        'hero_state': 'activo', 'hero_stake': 90.0, 'hero_bet': 0.0,
        'hero_cards': [{'rank': 'A', 'suit': 's'}, {'rank': 'K', 'suit': 'd'}],
        'p1_state': 'activo', 'p1_stake': 90.0, 'p1_bet': 0.0,
        'p2_state': 'activo', 'p2_stake': 80.0, 'p2_bet': 0.0,
        'p3_state': 'inactivo', 'p4_state': 'inactivo', 'p5_state': 'inactivo',
        'pot': 10.0,
        'community': [{'rank': 'Q', 'suit': 'h'}, {'rank': '7', 'suit': 's'},
                      {'rank': '2', 'suit': 'c'}],
    }
    result = a.recomendacion(state, verbose=False)
    assert result is None
    assert a.last_reco_abstention['status'] == 'no_recommendation'
    assert 'multiway_no_soportado' in a.last_reco_reason
    assert calls == {}


def test_rival_que_checkeo_y_aparece_inactivo_sigue_contando_en_la_mano():
    a = _asistente(_hand(
        [{'pos': 'UTG', 'action': 'r', 'amount': 2.5}],
        flop=[{'pos': 'BB', 'action': 'x', 'amount': 0.0}]))
    state = {'hero_state': 'activo', 'p1_state': 'inactivo'}
    assert a._active_contenders(state) == ['hero', 'p1']


def test_public_flow_mw_que_termina_hu_vuelve_a_evaluarse(monkeypatch):
    calls = {}
    _install_recommendation_stubs(monkeypatch, calls)
    a = _public_recommendation_fixture(folded_extra=True)
    state = {
        'hero_state': 'activo', 'hero_stake': 90.0, 'hero_bet': 0.0,
        'hero_cards': [{'rank': 'A', 'suit': 's'}, {'rank': 'K', 'suit': 'd'}],
        'p1_state': 'activo', 'p1_stake': 90.0, 'p1_bet': 0.0,
        # OCR atrasado: el fold registrado hace que este asiento ya no cuente.
        'p2_state': 'activo', 'p2_stake': 80.0, 'p2_bet': 0.0,
        'p3_state': 'inactivo', 'p4_state': 'inactivo', 'p5_state': 'inactivo',
        'pot': 10.0,
        'community': [{'rank': 'Q', 'suit': 'h'}, {'rank': '7', 'suit': 's'},
                      {'rank': '2', 'suit': 'c'}],
    }
    result = a.recomendacion(state, verbose=False)
    assert result is not None and result.chosen == 'check'
    assert calls == {'plan': 1, 'compute': 1, 'select': 1}
    assert a.last_reco_abstention is None


def test_public_flow_check_observado_llega_al_ev_y_actualiza_rango(monkeypatch):
    calls = {}
    _install_recommendation_stubs(monkeypatch, calls)
    check_likelihood = np.full(N_COMBOS, 0.8, dtype=np.float32)
    check_likelihood[:N_COMBOS // 2] = 0.2
    a = _public_recommendation_fixture(
        folded_extra=True,
        villain_action={'pos': 'BB', 'action': 'x', 'amount': 0.0})
    a.models.postflop_model.vectors[('flop', 'x')] = check_likelihood

    # El stub evita EV real; captura que el mismo RangeState ya condicionado
    # entra a EV, sin cambiar el comportamiento del recomendador.
    def compute(*args, **kwargs):
        reach = kwargs['villain_reach'].reach
        calls['check_updated_before_ev'] = not np.allclose(reach, reach[0])
        calls['compute'] = calls.get('compute', 0) + 1
        return EvTable(ev={'fold': 0.0, 'check': 0.1}, pot=10.0)

    monkeypatch.setattr(live, 'compute_evs', compute)
    state = {
        'hero_state': 'activo', 'hero_stake': 90.0, 'hero_bet': 0.0,
        'hero_cards': [{'rank': 'A', 'suit': 's'}, {'rank': 'K', 'suit': 'd'}],
        'p1_state': 'activo', 'p1_stake': 90.0, 'p1_bet': 0.0,
        'p2_state': 'activo', 'p2_stake': 80.0, 'p2_bet': 0.0,
        'p3_state': 'inactivo', 'p4_state': 'inactivo', 'p5_state': 'inactivo',
        'pot': 10.0,
        'community': [{'rank': 'Q', 'suit': 'h'}, {'rank': '7', 'suit': 's'},
                      {'rank': '2', 'suit': 'c'}],
    }
    result = a.recomendacion(state, verbose=False)
    assert result is not None
    assert calls['check_updated_before_ev'] is True
    assert a.models.postflop_model.calls == [
        ('flop', 'none', 'x', ('Qh', '7s', '2c'))]
    assert result.model_evidence['postflop_range_queries'][0]['applied']


def test_public_flow_check_sin_likelihood_abstiene_antes_de_ev(monkeypatch):
    calls = {}
    _install_recommendation_stubs(monkeypatch, calls)
    a = _public_recommendation_fixture(
        folded_extra=True,
        villain_action={'pos': 'BB', 'action': 'x', 'amount': 0.0},
        supported=False)
    state = {
        'hero_state': 'activo', 'hero_stake': 90.0, 'hero_bet': 0.0,
        'hero_cards': [{'rank': 'A', 'suit': 's'}, {'rank': 'K', 'suit': 'd'}],
        'p1_state': 'activo', 'p1_stake': 90.0, 'p1_bet': 0.0,
        'p2_state': 'activo', 'p2_stake': 80.0, 'p2_bet': 0.0,
        'p3_state': 'inactivo', 'p4_state': 'inactivo', 'p5_state': 'inactivo',
        'pot': 10.0,
        'community': [{'rank': 'Q', 'suit': 'h'}, {'rank': '7', 'suit': 's'},
                      {'rank': '2', 'suit': 'c'}],
    }
    result = a.recomendacion(state, verbose=False)
    assert result is None
    assert 'postflop_range_incomplete' in a.last_reco_reason
    assert a.last_reco_abstention['details']['range_status'] == \
        'observed_action_without_usable_likelihood'
    assert calls == {}


def test_public_flow_sin_historial_preflop_abstiene_antes_de_ev(monkeypatch):
    calls = {}
    _install_recommendation_stubs(monkeypatch, calls)
    a = _public_recommendation_fixture(folded_extra=True)
    a.rec.hand['streets']['preflop']['actions'] = []
    state = {
        'hero_state': 'activo', 'hero_stake': 90.0, 'hero_bet': 0.0,
        'hero_cards': [{'rank': 'A', 'suit': 's'}, {'rank': 'K', 'suit': 'd'}],
        'p1_state': 'activo', 'p1_stake': 90.0, 'p1_bet': 0.0,
        'p2_state': 'activo', 'p2_stake': 80.0, 'p2_bet': 0.0,
        'p3_state': 'inactivo', 'p4_state': 'inactivo', 'p5_state': 'inactivo',
        'pot': 10.0,
        'community': [{'rank': 'Q', 'suit': 'h'}, {'rank': '7', 'suit': 's'},
                      {'rank': '2', 'suit': 'c'}],
    }
    result = a.recomendacion(state, verbose=False)
    assert result is None
    assert 'initial_range_unresolved_or_uncovered' in a.last_reco_reason
    assert a.last_reco_abstention['details']['initial_range']['status'] == \
        'initial_range_unresolved'
    assert calls == {}
