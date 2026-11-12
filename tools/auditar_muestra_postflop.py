# -*- coding: utf-8 -*-
"""Audit de evidencia de PostflopRangeModel; solo lectura, sin filtrado.

Por defecto audita la ventana fiable. --base audita la base completa; --json
emite el inventario de celdas y consultas por acción, incluida la proyección
de elegibilidad P0-2 sin cambiar el modelo efectivo. --verify-no-change coteja
fingerprints antes/después de consultar los sidecars de evidencia.
"""
import argparse
import json
import os
import sys
import hashlib
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from motor.cards import card_id, is_card_code
from motor.field_eligibility import (
    CONSUMER_POSTFLOP_RANGE, assess_hand, load_declared,
    observation_eligibility, iter_observation_contexts)
from motor.learn import load_hands
from motor.observations import STREETS, extract_hands
from motor.postflop_ranges import (
    ACTIONS, PostflopRangeModel, _board_ids)


def _cards(o):
    raw = o.cards if isinstance(o.cards, (list, tuple)) else [
        o.cards[i:i + 2] for i in range(0, len(o.cards), 2)]
    return [c for c in raw if is_card_code(c)]


def _coverage(n, prior_available):
    if n == 0:
        return ('prior_only' if prior_available else 'no_evidence_no_prior')
    if n < 3:
        return 'thin_observations_n_lt_3'
    if n < 20:
        return 'limited_observations_n_lt_20'
    return 'observations_n_ge_20'


def _fingerprint(payload):
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                     separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _probability_table_payload(model):
    return {
        'alpha': model.alpha, 'n_buckets': model.n_buckets,
        'labels': model.labels,
        'opp': {'|'.join(map(str, k)): v for k, v in model.opp.items()},
        'cnt': {'|'.join(map(str, k)): v for k, v in model.cnt.items()},
    }


def _query_estimates(model):
    return [
        [*key, action, model.p_action(*key, action)]
        for key in sorted(model.opp)
        for action in ACTIONS
    ]


def verify_no_change(hands):
    """Comprueba tablas y consultas antes/después de pedir sidecars."""
    model = PostflopRangeModel.from_hands(hands)
    tables_before = _fingerprint(_probability_table_payload(model))
    estimates_before = _fingerprint(_query_estimates(model))
    baseline = {(tuple(row[:4]), row[4]): row[5]
                for row in _query_estimates(model)}
    for key in sorted(model.opp):
        for action in ACTIONS:
            detail = model.evidence_for(*key, action)
            if detail['estimate'] != baseline[(key, action)]:
                return {'same': False, 'reason': 'estimate/evidence mismatch',
                        'key': key, 'action': action}
    tables_after = _fingerprint(_probability_table_payload(model))
    estimates_after = _fingerprint(_query_estimates(model))
    return {
        'same': (tables_before == tables_after
                 and estimates_before == estimates_after),
        'probability_tables_sha256_before': tables_before,
        'probability_tables_sha256_after': tables_after,
        'query_estimates_sha256_before': estimates_before,
        'query_estimates_sha256_after': estimates_after,
        'queries': len(baseline),
    }


def audit(hands=None, declared=None):
    hands = load_hands(reliable_only=True) if hands is None else hands
    declared = declared if declared is not None else load_declared()
    model = PostflopRangeModel.from_hands(hands)
    observations = extract_hands(hands)
    observations_by_hand = defaultdict(list)
    for obs in observations:
        observations_by_hand[obs.hand_id].append(obs)
    hands_counted_by_legacy_meta = {
        o.hand_id for o in observations if o.hand_known and o.cards
    }
    hand_by_id = {h.get('hand_id'): h for h in hands}
    eligibility_by_hand = {}
    cells = {}
    hands_by_cell = defaultdict(set)
    action_hands_by_cell = defaultdict(lambda: defaultdict(set))
    observations_by_cell = defaultdict(list)
    eligible_obs_by_cell = Counter()
    eligible_action_by_cell = Counter()
    restricted_obs_by_cell = Counter()
    candidate_rows = 0

    for hand_id, hand in hand_by_id.items():
        hand_obs = observations_by_hand.get(hand_id, [])
        he = assess_hand(hand, declared)
        eligibility_by_hand[hand_id] = he
        for o, context in iter_observation_contexts(hand, hand_obs):
            if not o.hand_known or not o.cards or o.street == 'preflop':
                continue
            profile = model.labels.get(o.player)
            if profile is None:
                continue
            board_ids = _board_ids(o.board)
            if board_ids is None:
                continue
            cards = _cards(o)
            if len(cards) != 2:
                continue
            hand_cards = [card_id(c) for c in cards]
            bucket = model._bucket_of(hand_cards, board_ids)
            key = (profile, o.street, o.facing, bucket)
            candidate_rows += 1
            hands_by_cell[key].add(o.hand_id)
            action_hands_by_cell[key][o.action].add(o.hand_id)
            _street, seq_i = context[0], context[1]
            eligibility = observation_eligibility(
                he, o, o.street, seq_i, CONSUMER_POSTFLOP_RANGE)
            observations_by_cell[key].append({
                'hand_id': o.hand_id,
                'player': o.player,
                'street': o.street,
                'facing': o.facing,
                'bucket': bucket,
                'action': o.action,
                'amount': o.amount,
                'amount_evidence': dict(o.amount_evidence),
                'sizing': o.sizing,
                'cards': list(o.cards) if isinstance(o.cards, (list, tuple))
                else o.cards,
                'board': o.board,
                'eligible_p02_shadow': eligibility.usable,
                'restricted_p02_shadow': eligibility.restricted,
                'reason': list(eligibility.reasons),
                'direct': eligibility.direct,
                'dependent': eligibility.dependent,
                'root_code': eligibility.root_code,
            })
            if eligibility.usable:
                eligible_obs_by_cell[key] += 1
                eligible_action_by_cell[key + (o.action,)] += 1
            else:
                restricted_obs_by_cell[key] += 1

    for key, n in model.opp.items():
        profile, street, facing, bucket = key
        prior_result = (model._oracle.p_action(profile, street, facing)
                        if model._oracle is not None else None)
        prior_available = prior_result is not None
        prior_source = prior_result.get('source') if prior_result else (
            'flat_no_oracle' if model._oracle is None else
            'flat_oracle_no_cell')
        prior_returned_n = prior_result.get('n', 0) if prior_result else 0
        support_n = _oracle_support_n(model._oracle, profile, street, facing,
                                      prior_source)
        cell = {
            'profile': profile, 'street': street, 'facing': facing,
            'bucket': bucket, 'observations': n,
            'distinct_hands': len(hands_by_cell[key]),
            'shadow_eligible_observations': eligible_obs_by_cell[key],
            'shadow_restricted_observations': restricted_obs_by_cell[key],
            'prior_source': prior_source,
            'prior_support_observations': support_n,
            'oracle_returned_n': prior_returned_n,
            'prior_available': prior_available,
            'contributing_hand_ids': sorted(hands_by_cell[key]),
            'observation_trace': observations_by_cell[key],
            'queries': [],
        }
        for action in ACTIONS:
            cell_key = key + (action,)
            count_action = model.cnt.get(cell_key, 0)
            if prior_result is not None:
                p0 = prior_result['actions'].get(action, 0.0)
                used_prior = True
            elif n:
                p0 = 0.2
                used_prior = True
            else:
                p0 = 0.0
                used_prior = False
            estimate = model.p_action(profile, street, facing, bucket, action)
            if used_prior:
                prior_weight = model.alpha / (n + model.alpha)
                evidence_weight = n / (n + model.alpha)
                prior_dominated = prior_weight >= 0.5
            else:
                prior_weight = None
                evidence_weight = 0.0
                prior_dominated = False
            cell['queries'].append({
                'action': action, 'action_observations': count_action,
                'action_distinct_hands': len(action_hands_by_cell[key][action]),
                'action_contributing_hand_ids': sorted(
                    action_hands_by_cell[key][action]),
                'estimate': estimate, 'prior_probability': p0,
                'prior_source': prior_source,
                'prior_support_observations': support_n,
                'prior_weight': prior_weight,
                'observation_weight': evidence_weight,
                'prior_dominated': prior_dominated,
        'coverage': _coverage(n, used_prior),
                'confidence': 'not_quantified',
                'uncertainty_reason': _uncertainty_reason(
                    n, len(hands_by_cell[key]), prior_dominated, used_prior),
                'shadow_eligible_observations': eligible_obs_by_cell[key],
                'shadow_eligible_action_observations':
                    eligible_action_by_cell[cell_key],
                'shadow_restricted_observations': restricted_obs_by_cell[key],
            })
        cells[key] = cell

    populated_n = Counter(c['observations'] for c in cells.values())
    cell_bands = Counter(_coverage(c['observations'], c['prior_available'])
                         for c in cells.values())
    query_bands = Counter(
        _coverage(c['observations'], c['prior_available'])
        for c in cells.values() for _a in ACTIONS)
    prior_dominated_queries = sum(
        1 for c in cells.values() for q in c['queries']
        if q['prior_dominated'])
    prior_sources = Counter(c['prior_source'] for c in cells.values())
    prior_weights = Counter(
        round(q['prior_weight'], 6)
        for c in cells.values() for q in c['queries']
        if q['prior_weight'] is not None)
    oracle_query_evidence = {}
    for o in observations:
        if o.street == 'preflop':
            continue
        profile = model.labels.get(o.player)
        if profile is None:
            continue
        context = (profile, o.street, o.facing, o.texture_class or '-')
        if context in oracle_query_evidence:
            continue
        oracle_query_evidence[context] = model._oracle.evidence(
            profile, o.street, o.facing, o.texture_class or '-')
    oracle_sources = Counter(x['source'] for x in
                             oracle_query_evidence.values())
    oracle_returned_bands = Counter(
        ('n_lt_3' if x['returned_n'] < 3 else
         'n_lt_20' if x['returned_n'] < 20 else 'n_ge_20')
        for x in oracle_query_evidence.values())
    oracle_support_bands = Counter(
        ('support_lt_3' if x['support_observations'] < 3 else
         'support_lt_20' if x['support_observations'] < 20 else
         'support_ge_20') for x in oracle_query_evidence.values())
    oracle_fade = Counter(
        round(min(1.0, x['returned_n'] / 20.0), 6)
        for x in oracle_query_evidence.values())
    probe_facings = sorted({f for _p, _s, f in model._oracle.facing})
    fallback_probes = {}
    for profile in sorted(set(model.labels.values())):
        for street in STREETS:
            if street == 'preflop':
                continue
            for facing in probe_facings:
                key = (profile, street, facing, '__p03_no_granular_cell__')
                fallback_probes[key] = model._oracle.evidence(
                    profile, street, facing, key[3])
    for street in STREETS:
        if street == 'preflop':
            continue
        for facing in probe_facings:
            profile = '__p03_unknown_profile__'
            key = (profile, street, facing, '__p03_no_granular_cell__')
            fallback_probes[key] = model._oracle.evidence(
                profile, street, facing, key[3])
    fallback_probe_sources = Counter(
        x['source'] for x in fallback_probes.values())
    probability_fingerprint = _fingerprint({
        'alpha': model.alpha, 'n_buckets': model.n_buckets,
        'labels': model.labels,
        'opp': {'|'.join(map(str, k)): v for k, v in model.opp.items()},
        'cnt': {'|'.join(map(str, k)): v for k, v in model.cnt.items()},
    })
    query_estimates_fingerprint = _fingerprint([
        [cell['profile'], cell['street'], cell['facing'], cell['bucket'],
         query['action'], query['estimate']]
        for key in sorted(cells)
        for cell in [cells[key]]
        for query in cell['queries']
    ])
    return {
        'scope': 'input',
        'provenance': {
            'hands_source': 'data/hands_db.jsonl',
            'labels_source': 'Profiles.from_hands',
            'model': 'PostflopRangeModel.from_hands',
            'prior_model': 'Oracle built from same input hands',
            'eligibility_policy': 'P0-2 shadow; no observation filtering',
            'alpha': model.alpha,
            'n_buckets': model.n_buckets,
        },
        'hands': {
            'received': len(hands),
            'whole_hand_validation_in_builder': False,
            'rejected_as_whole_hand': 0,
            'counted_by_legacy_n_hands_used': model.n_hands_used,
            'meaning_of_legacy_count':
                'distinct hand IDs with any known-card observation, including preflop',
            'hands_with_known_card_observation':
                len(hands_counted_by_legacy_meta),
            'with_at_least_one_effective_postflop_observation':
                len({hand_id for key in model.opp
                     for hand_id in hands_by_cell[key]}),
        },
        'observations': {
            'all_extracted': len(observations),
            'effective_postflop': sum(model.opp.values()),
            'shadow_eligible': sum(eligible_obs_by_cell.values()),
            'shadow_restricted': sum(restricted_obs_by_cell.values()),
            'candidate_rows_matching_builder': candidate_rows,
            'cell_count': len(model.opp),
            'query_count_populated_cells': len(model.opp) * len(ACTIONS),
            'queries_prior_dominated': prior_dominated_queries,
            'prior_source_cells': dict(prior_sources),
            'prior_weight_distribution_queries': dict(prior_weights),
            'oracle_response_contexts': len(oracle_query_evidence),
            'oracle_response_sources': dict(oracle_sources),
            'oracle_response_returned_n_bands': dict(oracle_returned_bands),
            'oracle_response_support_n_bands': dict(oracle_support_bands),
            'oracle_response_fade_n20_distribution': dict(oracle_fade),
            'oracle_fallback_probe_count': len(fallback_probes),
            'oracle_fallback_probe_sources': dict(fallback_probe_sources),
            'cell_sample_bands': dict(cell_bands),
            'query_sample_bands': dict(query_bands),
            'cell_n_distribution': dict(sorted(populated_n.items())),
        },
        'definitions': {
            'hands_valid': 'No whole-hand validity filter exists in the current builder; see effective contributor count.',
            'observation_n': 'Number of action observations in a profile/street/facing/bucket cell.',
            'hand_n': 'Distinct hand IDs contributing one or more observations to that cell.',
            'prior_weight': 'alpha/(observation_n+alpha), exactly the coefficient in the current shrinkage formula when a prior is available.',
            'confidence': 'Not statistically quantified; coverage labels are sample-size diagnostics, not confidence intervals.',
        },
        'fingerprints': {
            'probability_tables_sha256': probability_fingerprint,
            'populated_query_estimates_sha256': query_estimates_fingerprint,
            'oracle_distribution_sha256': _fingerprint(
                model._oracle.to_dict()) if model._oracle is not None else None,
        },
        'oracle_response_query_inventory': [
            {'key': '|'.join(map(str, key)), **value,
             'fade_n': 20.0,
             'current_profile_exponent': min(
                 1.0, value['returned_n'] / 20.0)}
            for key, value in sorted(oracle_query_evidence.items())],
        'oracle_fallback_probe_inventory': [
            {'key': '|'.join(map(str, key)), **value}
            for key, value in sorted(fallback_probes.items())],
        'cells': [
            {'key': '|'.join(map(str, key)), **value}
            for key, value in sorted(cells.items())],
    }


def _oracle_support_n(oracle, profile, street, facing, source):
    if oracle is None:
        return 0
    if source == 'granular':
        return oracle.granular.get((profile, street, '-', facing), {}).get('n', 0)
    if source == 'por_facing':
        return oracle.facing.get((profile, street, facing), {}).get('n', 0)
    if source == 'label':
        return sum(c.get('n', 0) for (p, s, _f), c in oracle.facing.items()
                   if p == profile and s == street)
    if source == 'poblacion':
        return sum(c.get('n', 0) for (_p, s, _f), c in oracle.facing.items()
                   if s == street)
    return 0


def _uncertainty_reason(n, distinct_hands, prior_dominated, prior_available):
    reasons = []
    if n == 0:
        reasons.append('sin observaciones del bucket; la salida depende del prior'
                       if prior_available else 'sin observaciones ni prior')
    elif n < 3:
        reasons.append('menos de 3 observaciones en la celda')
    elif n < 20:
        reasons.append('menos de 20 observaciones; cobertura limitada')
    if distinct_hands == 1:
        reasons.append('la evidencia procede de una sola mano')
    if prior_dominated:
        reasons.append('el peso algebraico del prior es >= 50%')
    if not reasons:
        reasons.append('sin intervalo de incertidumbre calibrado')
    return reasons


def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--verify-no-change', action='store_true')
    args = parser.parse_args(argv)
    hands = load_hands(reliable_only=not args.base)
    if args.verify_no_change:
        result = verify_no_change(hands)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print('P0-3 no-change:', 'OK' if result.get('same') else 'FAIL')
            print('tablas:', result.get('probability_tables_sha256_before'),
                  '->', result.get('probability_tables_sha256_after'))
            print('consultas:', result.get('query_estimates_sha256_before'),
                  '->', result.get('query_estimates_sha256_after'),
                  'n=', result.get('queries'))
        return 0 if result.get('same') else 1
    result = audit(hands)
    result['scope'] = 'base_1344' if args.base else 'ventana_877'
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print('P0-3: %s · manos recibidas=%d · legacy hands_used=%d · '
          'manos con observación postflop=%d · obs=%d · celdas=%d' % (
              result['scope'], result['hands']['received'],
              result['hands']['counted_by_legacy_n_hands_used'],
              result['hands']['with_at_least_one_effective_postflop_observation'],
              result['observations']['effective_postflop'],
              result['observations']['cell_count']))
    print('Bandas de celdas:', result['observations']['cell_sample_bands'])
    print('Bandas de queries:', result['observations']['query_sample_bands'])
    print('OracleResponse contexts=%d sources=%s returned_n=%s support_n=%s' % (
        result['observations']['oracle_response_contexts'],
        result['observations']['oracle_response_sources'],
        result['observations']['oracle_response_returned_n_bands'],
        result['observations']['oracle_response_support_n_bands']))
    print('Oracle fallback probes=%d sources=%s' % (
        result['observations']['oracle_fallback_probe_count'],
        result['observations']['oracle_fallback_probe_sources']))
    print('P0-2 sombra: %d elegibles / %d restringidas; no se filtró el modelo.' % (
        result['observations']['shadow_eligible'],
        result['observations']['shadow_restricted']))
    print('Confianza estadística: no cuantificada; no se calculan intervalos.')
    return 0


if __name__ == '__main__':
    raise SystemExit(run())
