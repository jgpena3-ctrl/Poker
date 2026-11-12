# -*- coding: utf-8 -*-
"""P0-6 — regresiones transversales sin activar contratos."""
import hashlib
import json
import os
import subprocess
import sys
import contextlib
import io
from types import SimpleNamespace

import pytest

from .action_amount import (
    ABSENT,
    INVALID,
    KNOWN_POSITIVE,
    KNOWN_ZERO,
    ORIGIN_CANONICAL,
    ORIGIN_DERIVED,
    ORIGIN_NON_CANONICAL,
    ORIGIN_UNKNOWN,
    classify_amount,
)
from .field_eligibility import (
    CONSUMER_POSTFLOP_RANGE,
    CONSUMER_PREFLOP_STATS,
    assess_hand,
    load_declared,
    observation_eligibility,
    preflop_event_contexts,
    preflop_event_eligibility,
)
from .label_contract import LABEL_UNKNOWN, label_audit
from .learn import load_hands
from .observations import extract_hand
from .preflop_contract import walk_preflop
from .profile import PEZ, TIBURON

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WRITERS_P06 = (
    'tools/corregir_anotaciones_20261110.py',
    'tools/corregir_bote_inflado_fold.py',
    'tools/corregir_folds_showdown.py',
    'tools/corregir_mano_H_1333.py',
    'tools/corregir_resultados_20261029.py',
    'tools/corregir_resultados_20261104.py',
    'tools/corregir_sesion_20261104.py',
    'tools/corregir_showdown_posicion.py',
    'tools/eliminar_mano_H_1323.py',
    'tools/limpiar_anotaciones_ruido.py',
    'tools/limpiar_notas_inferidas.py',
)

PROTECTED_DATA = (
    'hands_db.jsonl', 'calibration_window.json', 'preflop_matrices.json',
    'profile_ranges.json', 'postflop_ranges.json', 'preflop_stats.json',
    'player_stats.json', 'profiles.json', 'behavior.json',
    'observations.json',
)


def _hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


def _data_tree_hashes():
    data_root = os.path.join(ROOT, 'data')
    result = {}
    for parent, _dirs, files in os.walk(data_root):
        for name in files:
            path = os.path.join(parent, name)
            result[os.path.relpath(path, ROOT)] = _hash(path)
    return result


def _synthetic_amount_hand():
    return {
        'hand_id': 'P06_AMOUNT_SYNTHETIC',
        'players': [
            {'name': 'Alpha', 'pos': 'UTG', 'cards': 'AsKd', 'stack': 100.0},
            {'name': 'Bravo', 'pos': 'BB', 'cards': 'QhQs', 'stack': 100.0},
        ],
        'streets': {
            'preflop': {'actions': [
                {'pos': 'UTG', 'action': 'b', 'amount': None},
                {'pos': 'BB', 'action': 'f', 'amount': 0.0,
                 'amount_type': 'observed'},
            ]},
            'flop': {'board': ['2c', '7s', 'Qh'], 'actions': [
                {'pos': 'UTG', 'action': 'b', 'amount': None},
                {'pos': 'BB', 'action': 'c', 'amount': 0.0,
                 'amount_type': 'observed'},
            ]},
            'turn': {'board': [], 'actions': []},
            'river': {'board': [], 'actions': []},
        },
        'final_pot': 5.0,
    }


def test_amount_value_and_origin_are_separate_and_not_imputed():
    zero = classify_amount({'amount': 0.0, 'amount_type': 'observed'})
    positive = classify_amount({'amount': 2.5, 'amount_type': 'observed'})
    absent = classify_amount({'amount': None, 'amount_type': 'observed'})
    invalid = classify_amount({'amount': 'not-a-number',
                               'amount_type': 'observed'})
    invalid_numeric_string = classify_amount({'amount': '2.5',
                                               'amount_type': 'observed'})
    derived = classify_amount({'amount': 2.5, 'amount_type': 'delta'})
    noncanonical = classify_amount({'amount': 2.5, 'amount_type': 'box-total'})
    unknown_source = classify_amount({'amount': 2.5})

    assert (zero.value, zero.value_status, zero.origin_status) == (
        0.0, KNOWN_ZERO, ORIGIN_CANONICAL)
    assert (positive.value, positive.value_status, positive.origin_status) == (
        2.5, KNOWN_POSITIVE, ORIGIN_CANONICAL)
    assert absent.value is None and absent.value_status == ABSENT
    assert invalid.value is None and invalid.value_status == INVALID
    assert invalid_numeric_string.value is None
    assert invalid_numeric_string.value_status == INVALID
    assert derived.value == 2.5 and derived.origin_status == ORIGIN_DERIVED
    assert noncanonical.value == 2.5
    assert noncanonical.origin_status == ORIGIN_NON_CANONICAL
    assert unknown_source.value == 2.5
    assert unknown_source.origin_status == ORIGIN_UNKNOWN


def test_amount_absence_survives_preflop_and_p02_consumers():
    hand = _synthetic_amount_hand()
    strict = walk_preflop(hand)
    first = strict[0].classification
    assert first.status == 'unresolved'
    assert first.reason == 'importe_ausente'
    assert first.raw.amount is None
    assert first.as_dict()['amount_evidence']['value_status'] == ABSENT

    eligibility = assess_hand(hand, load_declared())
    issue = next(i for i in eligibility.issues
                 if i.street == 'preflop' and i.index == 0)
    assert issue.amount is None
    assert issue.amount_value_status == ABSENT
    assert issue.severity == 'ambiguous'  # no new restriction activation

    events = list(preflop_event_contexts(hand))
    utg = next((ev, seq, step) for ev, seq, step in events
               if ev.pos == 'UTG')
    projected = preflop_event_eligibility(
        eligibility, utg[0], utg[1], CONSUMER_PREFLOP_STATS)
    assert projected.amount_value_status == ABSENT
    assert projected.amount_usable is False
    assert projected.restricted is True

    observations = extract_hand(hand)
    flop_bet = next(o for o in observations
                    if o.street == 'flop' and o.player == 'Alpha')
    assert flop_bet.amount is None
    assert flop_bet.amount_evidence['value_status'] == ABSENT
    p02 = observation_eligibility(
        eligibility, flop_bet, 'flop', 0, CONSUMER_POSTFLOP_RANGE)
    assert p02.amount_value_status == ABSENT
    assert p02.amount_origin_status == ORIGIN_UNKNOWN
    assert p02.amount_usable is False


def test_h0357_has_one_common_unresolved_root_and_four_dependents():
    hands = load_hands(reliable_only=True)
    hand = next(h for h in hands if h.get('hand_id') == 'H_0357')
    steps = walk_preflop(hand)
    root = next(s for s in steps if s.raw.index == 2)
    assert root.raw.pos == 'BB'
    assert root.raw.action == 'b'
    assert root.raw.amount == 0.5
    assert root.classification.status == 'unresolved'
    assert root.classification.reason == 'subida_sin_incremento'
    assert root.classification.context.current_level == 1.0
    assert root.after.tainted_reason == 'subida_sin_incremento'
    assert all(s.classification.status == 'unresolved'
               and s.classification.reason.startswith('secuencia_ambigua:')
               for s in steps[3:7])

    he = assess_hand(hand, load_declared())
    issue = next(i for i in he.issues
                 if i.street == 'preflop' and i.index == 2)
    assert issue.code == root.classification.reason
    assert issue.severity == 'invalid'
    dependents = [d for d in he.dependent if d.root is issue]
    assert [(d.seq_index, d.pos) for d in dependents] == [
        (3, 'CO'), (4, 'BTN'), (5, 'SB'), (6, 'BB')]
    restricted = []
    for event, seq, _step in preflop_event_contexts(hand):
        row = preflop_event_eligibility(
            he, event, seq, CONSUMER_PREFLOP_STATS)
        if row.restricted:
            restricted.append((event.player, seq, row.root_code))
    assert len(restricted) == 4
    assert all(code == 'subida_sin_incremento'
               for _name, _seq, code in restricted)


def test_range_lab_fails_closed_instead_of_mixing_current_and_historical():
    from tools.range_lab_gui import load_models

    with pytest.raises(RuntimeError, match='no apta.*mezclar'):
        load_models()


def test_all_eleven_new_database_writers_default_to_read_only_dry_run():
    before = _data_tree_hashes()
    for rel in WRITERS_P06:
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, rel)], cwd=ROOT,
            capture_output=True, text=True, timeout=120)
        assert proc.returncode == 0, '%s failed:\n%s\n%s' % (
            rel, proc.stdout[-2000:], proc.stderr[-2000:])
        assert ('dry-run: no se ha escrito nada' in proc.stdout
                or 'nada que cambiar' in proc.stdout
                or 'nada que eliminar' in proc.stdout), rel
    assert _data_tree_hashes() == before


def test_p06_audits_do_not_write_canonical_or_historical_artifacts():
    paths = [os.path.join(ROOT, 'data', name) for name in PROTECTED_DATA]
    before = {path: _hash(path) for path in paths}
    tree_before = _data_tree_hashes()
    label_audit()
    after = {path: _hash(path) for path in paths}
    assert after == before
    assert _data_tree_hashes() == tree_before


def test_p06_preserves_effective_model_fingerprints_and_labels():
    from .asistente_live import build_models
    from .field_eligibility import model_fingerprint

    with contextlib.redirect_stdout(io.StringIO()):
        models = build_models(verbose=False)
        result = label_audit()
    fingerprints = model_fingerprint(
        models.range_model, models.oracle, models.postflop_model)
    assert fingerprints == {
        'profile_range': (
            '1070d92669a90818b50a940ac4202ecb796ec27e06aa129db5d83849c425e7f9'),
        'oracle': (
            '50b254d7cce40ad3b9a97dc156505624aeeb3745d312335fd43b6e3f73f6edf5'),
        'postflop_range': (
            '0369560a2da2f4b1a2c9eb75ff3306d8ddfd24360354c7f5ec36434b5829d413'),
        'oracle_inside_postflop': (
            '50b254d7cce40ad3b9a97dc156505624aeeb3745d312335fd43b6e3f73f6edf5'),
    }
    assert result['training']['labels'] == {TIBURON: 60, PEZ: 78}
    assert result['training']['labels_sha256'] == \
        'dca28d2607e817b8794b4579602bbe8cedf456754377d17dfa5b9e39cb8e6060'


def test_all_five_audits_leave_deterministic_recommendation_unchanged():
    from .asistente_live import Asistente
    from .behavior import Oracle, build
    from .field_eligibility import _stable_payload, shadow_report
    from .player_ranges import ProfileRangeModel
    from .postflop_ranges import PostflopRangeModel
    from tools.auditar_contrato_preflop import informe as audit_preflop
    from tools.auditar_muestra_postflop import audit as audit_postflop
    from .provenance_contract import audit_provenance

    def sample(hid, rival_action, cards):
        return {
            'hand_id': hid,
            'players': [
                {'name': 'Hero', 'pos': 'BTN', 'cards': cards[0],
                 'stack': 90.0},
                {'name': 'Rival', 'pos': 'BB', 'cards': cards[1],
                 'stack': 90.0},
            ],
            'streets': {
                'preflop': {'actions': [
                    {'pos': 'BTN', 'action': 'r', 'amount': 2.5},
                    {'pos': 'BB', 'action': 'c', 'amount': 2.5},
                ]},
                'flop': {'board': ['Qh', '7s', '2c'], 'actions': [
                    {'pos': 'BTN', 'action': 'b', 'amount': 3.0},
                    {'pos': 'BB', 'action': rival_action, 'amount': 0.0},
                ]},
                'turn': {'board': [], 'actions': []},
                'river': {'board': [], 'actions': []},
            },
        }

    synthetic = [sample(
        'p06-live-%d' % i, 'f' if i % 2 else 'c',
        ('7c', '2d') if i % 2 else ('Ac', 'Ad')) for i in range(6)]
    labels = {'Hero': PEZ, 'Rival': TIBURON}
    range_model = ProfileRangeModel.from_hands(synthetic, labels=labels)
    oracle = Oracle(build(synthetic, labels=labels, min_n=1))
    postflop = PostflopRangeModel.from_hands(synthetic, labels=labels)
    postflop._oracle = oracle
    models = SimpleNamespace(
        range_model=range_model, oracle=oracle, postflop_model=postflop)
    recorded = sample('P06_RECOMMENDATION', 'c', ('As', 'Kd'))
    assistant = Asistente.__new__(Asistente)
    assistant.models = models
    assistant.oracle = oracle
    assistant.rec = SimpleNamespace(
        hand=recorded, _hand_positions={'hero': 'BTN', 'p1': 'BB'})
    assistant.verbose = False
    assistant.shadow = False
    assistant.runout = False
    assistant.live_stacks = {}
    assistant._last_seen_stake = {}
    assistant.decision_log = None
    state = {
        'pot': 20.0, 'hero_state': 'activo', 'hero_stake': 90.0,
        'hero_bet': 0.0, 'p1_state': 'activo', 'p1_stake': 90.0,
        'p1_bet': 5.0, 'p2_state': 'inactivo', 'p3_state': 'inactivo',
        'p4_state': 'inactivo', 'p5_state': 'inactivo',
    }

    def snapshot():
        payload = {
            'labels': dict(range_model.perfil),
            'range_model': range_model.to_json(),
            'postflop_model': postflop.to_json(),
            'oracle': oracle.to_dict(),
            'preflop_vector': range_model.prob_vec(
                TIBURON, 'OR', 'open', pos='BTN',
                villain_pos='BB').tolist(),
            'postflop_vector': postflop.prob_vec(
                TIBURON, 'flop', 'bet', ['Qh', '7s', '2c'], 'c').tolist(),
            'oracle_distribution': oracle.p_action(TIBURON, 'flop', 'bet'),
        }
        raw = json.dumps(_stable_payload(payload), sort_keys=True,
                         ensure_ascii=False, separators=(',', ':'),
                         default=lambda obj: obj.tolist()
                         if hasattr(obj, 'tolist') else str(obj))
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def recommendation():
        visible = []
        result = assistant._recomendacion_para(
            state, 'hero', ['As', 'Kd'], ['Qh', '7s', '2c'], 'p1', [],
            verbose=False,
            on_reco=lambda text, ev, _s, _label: visible.append(
                (text, ev.chosen, dict(ev.ev))),
            seed=19)
        assert result is not None
        return visible

    before_model = snapshot()
    before_recommendation = recommendation()
    hands = load_hands(reliable_only=True)
    with contextlib.redirect_stdout(io.StringIO()):
        audit_preflop(hands)
        shadow_report(hands)
        audit_postflop(hands)
        audit_provenance()
        label_audit()
    after_recommendation = recommendation()
    after_model = snapshot()
    assert after_model == before_model
    assert after_recommendation == before_recommendation
    assert before_recommendation[0][1] in ('fold', 'call', 'raise', 'check')
