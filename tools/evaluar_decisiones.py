"""Read-only integrity and availability report for the decision JSONL log.

This first-stage evaluator does not recalculate equity/EV or score strategy.
It joins decision/resolution events by ``decision_id`` and reports which
subsequent analyses are possible from the data that was actually recorded.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import defaultdict


SCHEMA_VERSION = 1
DEFAULT_INPUT = os.path.join(os.path.dirname(__file__), '..', 'data',
                             'decisions.jsonl')

_DECISION_KEYS = {
    'schema_version', 'event_type', 'decision_id', 'hand_id', 'recorded_at',
    'motor_version', 'known_at_decision', 'execution', 'outcome',
}
_RESOLUTION_KEYS = {
    'schema_version', 'event_type', 'decision_id', 'hand_id', 'recorded_at',
    'execution', 'outcome',
}
_SNAPSHOT_KEYS = {
    'street', 'hero_id', 'villain_id', 'hero_position', 'villain_position',
    'positions', 'stacks', 'bets', 'pot', 'to_call', 'effective_stack',
    'cards_known', 'actions_before_decision', 'actions_seen_count',
    'villain_range', 'villain_range_status', 'equity', 'pot_odds', 'spr',
    'candidate_actions', 'ev_by_action', 'preflop_action_frequencies',
    'action_values_kind', 'recommended_action', 'villain_label',
}
_CARDS_KNOWN_KEYS = {
    'hero', 'board', 'other_hole_cards', 'unknown_opponent_holes',
    'opponent_hole_cards_complete',
}
_RANGE_KEYS = {
    'representation', 'normalized', 'source', 'position', 'confidence',
    'combo_weights',
}
_EXECUTION_KEYS = {'status', 'action'}
_OUTCOME_KEYS = {
    'status', 'final_pot', 'winner_ids', 'showdown', 'revealed_cards',
}


def _nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _number_or_none(value):
    if value is None:
        return True
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _safe_value(value):
    """Keep reports strict JSON even when an input uses non-finite numbers."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    return value


def _reject_json_constant(value):
    raise ValueError(f'non-standard JSON constant: {value}')


def _validate_snapshot(snapshot):
    errors = []
    expected = {
        'street': str,
        'hero_id': str,
        'villain_id': str,
        'hero_position': str,
        'villain_position': str,
        'positions': dict,
        'stacks': dict,
        'bets': dict,
        'cards_known': dict,
        'actions_before_decision': list,
        'villain_range': dict,
        'villain_range_status': str,
        'candidate_actions': list,
        'ev_by_action': dict,
        'preflop_action_frequencies': dict,
        'action_values_kind': str,
        'recommended_action': str,
        'villain_label': str,
    }
    numeric = {'pot', 'to_call', 'effective_stack', 'equity', 'pot_odds',
               'spr', 'actions_seen_count'}
    for key, expected_type in expected.items():
        if key in snapshot and snapshot[key] is not None:
            if not isinstance(snapshot[key], expected_type):
                errors.append(f'invalid_known_at_decision_{key}')
    for key in numeric:
        if key in snapshot and not _number_or_none(snapshot[key]):
            errors.append(f'invalid_known_at_decision_{key}')
    for key in ('stacks', 'bets'):
        values = snapshot.get(key)
        if isinstance(values, dict) and any(
                not _number_or_none(value) for value in values.values()):
            errors.append(f'invalid_known_at_decision_{key}_value')
    positions = snapshot.get('positions')
    if isinstance(positions, dict) and any(
            value is not None and not isinstance(value, str)
            for value in positions.values()):
        errors.append('invalid_known_at_decision_positions_value')
    cards = snapshot.get('cards_known')
    if isinstance(cards, dict):
        for key in ('hero', 'board', 'unknown_opponent_holes'):
            value = cards.get(key)
            if value is not None and (not isinstance(value, list)
                                      or any(not isinstance(c, str) for c in value)):
                errors.append(f'invalid_cards_known_{key}')
        other = cards.get('other_hole_cards')
        if other is not None and not isinstance(other, dict):
            errors.append('invalid_cards_known_other_hole_cards')
        complete = cards.get('opponent_hole_cards_complete')
        if complete is not None and not isinstance(complete, bool):
            errors.append('invalid_cards_known_opponent_hole_cards_complete')
    actions = snapshot.get('actions_before_decision')
    if isinstance(actions, list) and any(not isinstance(a, dict) for a in actions):
        errors.append('invalid_actions_before_decision_entry')
    for key in ('ev_by_action', 'preflop_action_frequencies'):
        values = snapshot.get(key)
        if isinstance(values, dict) and any(
                not _number_or_none(value) for value in values.values()):
            errors.append(f'invalid_known_at_decision_{key}_value')
    range_data = snapshot.get('villain_range')
    if isinstance(range_data, dict):
        normalized = range_data.get('normalized')
        if normalized is not None and not isinstance(normalized, bool):
            errors.append('invalid_villain_range_normalized')
        weights = range_data.get('combo_weights')
        if weights is not None and not isinstance(weights, list):
            errors.append('invalid_villain_range_combo_weights')
        elif isinstance(weights, list):
            if any(not isinstance(row, list) or len(row) != 2
                   or not isinstance(row[0], str)
                   or not _number_or_none(row[1]) for row in weights):
                errors.append('invalid_villain_range_combo_weight_entry')
    recommended = snapshot.get('recommended_action')
    if recommended is not None and not _nonempty_string(recommended):
        errors.append('invalid_recommended_action')
    candidates = snapshot.get('candidate_actions')
    if isinstance(candidates, list) and any(not isinstance(a, str) for a in candidates):
        errors.append('invalid_candidate_action_entry')
    return errors


def _validate_event(event):
    """Return schema problems for a parsed object; unknown keys are allowed."""
    errors = []
    kind = event.get('event_type')
    if (type(event.get('schema_version')) is not int
            or event.get('schema_version') != SCHEMA_VERSION):
        errors.append('unsupported_or_missing_schema_version')
    if kind not in ('decision', 'resolution'):
        errors.append('unknown_or_missing_event_type')
        return errors
    if not _nonempty_string(event.get('decision_id')):
        errors.append('missing_or_invalid_decision_id')
    if not _nonempty_string(event.get('recorded_at')):
        errors.append('missing_or_invalid_recorded_at')

    hand_id = event.get('hand_id')
    if kind == 'decision':
        if hand_id is not None and not _nonempty_string(hand_id):
            errors.append('invalid_hand_id')
        if not isinstance(event.get('known_at_decision'), dict):
            errors.append('missing_or_invalid_known_at_decision')
        else:
            errors.extend(_validate_snapshot(event['known_at_decision']))
        if not isinstance(event.get('execution'), dict):
            errors.append('missing_or_invalid_execution')
        elif (event['execution'].get('status') != 'pending'
              or 'action' not in event['execution']
              or event['execution'].get('action') is not None):
            errors.append('invalid_decision_execution_state')
        if not isinstance(event.get('outcome'), dict):
            errors.append('missing_or_invalid_outcome')
        elif event['outcome'].get('status') != 'pending':
            errors.append('invalid_decision_outcome_state')
        version = event.get('motor_version')
        if version is not None and not isinstance(version, str):
            errors.append('invalid_motor_version')
    else:
        if not _nonempty_string(hand_id):
            errors.append('missing_or_invalid_hand_id')
        execution = event.get('execution')
        if not isinstance(execution, dict):
            errors.append('missing_or_invalid_execution')
        else:
            status = execution.get('status')
            action = execution.get('action')
            if status == 'recorded':
                if (not isinstance(action, dict)
                        or not _nonempty_string(action.get('action'))):
                    errors.append('recorded_execution_missing_action')
                elif 'amount' in action and not _number_or_none(action['amount']):
                    errors.append('invalid_recorded_action_amount')
            elif status == 'not_observed':
                if action is not None:
                    errors.append('not_observed_execution_has_action')
            else:
                errors.append('invalid_resolution_execution_status')
        outcome = event.get('outcome')
        if not isinstance(outcome, dict):
            errors.append('missing_or_invalid_outcome')
        elif outcome.get('status') != 'recorded':
            errors.append('invalid_resolution_outcome_status')
        else:
            if ('final_pot' in outcome
                    and not _number_or_none(outcome['final_pot'])):
                errors.append('invalid_outcome_final_pot')
            if ('winner_ids' in outcome and outcome['winner_ids'] is not None
                    and (not isinstance(outcome['winner_ids'], list)
                         or any(not isinstance(w, str)
                                for w in outcome['winner_ids']))):
                errors.append('invalid_outcome_winner_ids')
            for key in ('showdown', 'revealed_cards'):
                if (key in outcome and outcome[key] is not None
                        and not isinstance(outcome[key], dict)):
                    errors.append(f'invalid_outcome_{key}')
    return errors


def _unknown_fields(event):
    """List extension keys without interpreting or discarding their values."""
    unknown = []

    def collect(obj, allowed, prefix):
        if not isinstance(obj, dict):
            return
        for key in obj:
            if key not in allowed:
                unknown.append(f'{prefix}{key}')

    kind = event.get('event_type')
    collect(event, _DECISION_KEYS if kind == 'decision' else _RESOLUTION_KEYS,
            'event.')
    snapshot = event.get('known_at_decision')
    collect(snapshot, _SNAPSHOT_KEYS, 'known_at_decision.')
    if isinstance(snapshot, dict):
        cards = snapshot.get('cards_known')
        collect(cards, _CARDS_KNOWN_KEYS, 'known_at_decision.cards_known.')
        range_data = snapshot.get('villain_range')
        collect(range_data, _RANGE_KEYS, 'known_at_decision.villain_range.')
    collect(event.get('execution'), _EXECUTION_KEYS, 'execution.')
    collect(event.get('outcome'), _OUTCOME_KEYS, 'outcome.')
    return sorted(unknown)


def _read_jsonl(path):
    events = []
    malformed = []
    blank_lines = 0
    physical_lines = 0
    try:
        with open(path, 'r', encoding='utf-8') as stream:
            for line_number, raw in enumerate(stream, start=1):
                physical_lines = line_number
                if not raw.strip():
                    blank_lines += 1
                    continue
                try:
                    event = json.loads(raw, parse_constant=_reject_json_constant)
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                    malformed.append({
                        'line': line_number,
                        'errors': ['invalid_json'],
                    })
                    continue
                if not isinstance(event, dict):
                    malformed.append({
                        'line': line_number,
                        'errors': ['event_is_not_an_object'],
                    })
                    continue
                errors = _validate_event(event)
                entry = {
                    'line': line_number,
                    'event': event,
                    'errors': errors,
                    'unknown_fields': _unknown_fields(event),
                }
                events.append(entry)
                if errors:
                    malformed.append({'line': line_number, 'errors': errors})
    except (OSError, UnicodeError) as exc:
        return events, malformed, blank_lines, physical_lines, str(exc)
    return events, malformed, blank_lines, physical_lines, None


def _index_events(events):
    by_kind_id = {
        'decision': defaultdict(list),
        'resolution': defaultdict(list),
    }
    for entry in events:
        event = entry['event']
        kind = event.get('event_type')
        decision_id = event.get('decision_id')
        if kind in by_kind_id and _nonempty_string(decision_id):
            by_kind_id[kind][decision_id].append(entry)
    return by_kind_id


def _action_code(recommended):
    """Normalize only action labels with an unambiguous recorder equivalent."""
    if not _nonempty_string(recommended):
        return None
    aliases = {
        'fold': 'f', 'retirar': 'f',
        'check': 'x', 'pasar': 'x',
        'call': 'c', 'igualar': 'c',
        'raise': 'r',
    }
    action = recommended.strip().lower()
    if action in aliases:
        return aliases[action]
    if re.fullmatch(r'bet_\d+', action):
        return 'b'
    # `subir` and `all_in` may encode either a bet or raise in the recorder.
    return None


def _observed_code(action):
    if not _nonempty_string(action):
        return None
    action = action.strip().lower()
    aliases = {
        'f': 'f', 'fold': 'f', 'retirar': 'f',
        'x': 'x', 'check': 'x', 'pasar': 'x',
        'c': 'c', 'call': 'c', 'igualar': 'c',
        'b': 'b', 'bet': 'b', 'apostar': 'b',
        'r': 'r', 'raise': 'r',
    }
    return aliases.get(action)


def _field_present(obj, key):
    return isinstance(obj, dict) and key in obj and obj[key] is not None


def _calculation_report(event):
    snapshot = event.get('known_at_decision')
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    cards = snapshot.get('cards_known')
    cards = cards if isinstance(cards, dict) else {}
    available = []
    field_values = (
        ('street', snapshot.get('street')),
        ('hero_position', snapshot.get('hero_position')),
        ('villain_position', snapshot.get('villain_position')),
        ('positions', snapshot.get('positions')),
        ('stacks', snapshot.get('stacks')),
        ('bets', snapshot.get('bets')),
        ('pot', snapshot.get('pot')),
        ('to_call', snapshot.get('to_call')),
        ('hero_cards', cards.get('hero')),
        ('board_cards', cards.get('board')),
        ('villain_range', snapshot.get('villain_range')),
        ('equity', snapshot.get('equity')),
        ('candidate_actions', snapshot.get('candidate_actions')),
        ('ev_by_action', snapshot.get('ev_by_action')),
        ('preflop_action_frequencies',
         snapshot.get('preflop_action_frequencies')),
    )
    for name, value in field_values:
        if value is not None:
            available.append(name)

    blockers = ['recalculation_not_implemented_in_this_version']
    if not _nonempty_string(event.get('motor_version')):
        blockers.append('motor_version_unknown')
    for key, code in (
            ('street', 'street_unknown'),
            ('hero_position', 'hero_position_unknown'),
            ('pot', 'pot_unknown'),
            ('to_call', 'to_call_unknown')):
        if not _field_present(snapshot, key):
            blockers.append(code)
    if not cards.get('hero'):
        blockers.append('hero_cards_unknown')
    if snapshot.get('street') != 'preflop' and not cards.get('board'):
        blockers.append('board_unknown')
    if snapshot.get('street') == 'preflop' and snapshot.get('villain_range') is None:
        blockers.append('preflop_villain_range_not_exposed')
    if snapshot.get('street') != 'preflop' and snapshot.get('villain_range') is None:
        blockers.append('villain_range_unknown')
    # These settings affect which actions/EVs are produced but are not in the
    # current decision snapshot.
    blockers.extend(('active_player_count_not_recorded',
                     'runout_and_sampling_settings_not_recorded',
                     'response_model_state_not_recorded'))
    return {
        'status': 'not_attempted',
        'can_reproduce': None,
        'available_data': sorted(available),
        'blockers': sorted(set(blockers)),
    }


def _reasonableness_report(snapshot):
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    recommended = snapshot.get('recommended_action')
    candidates = snapshot.get('candidate_actions')
    consistency = None
    if _nonempty_string(recommended) and isinstance(candidates, list):
        consistency = recommended in candidates
    return {
        'status': 'not_evaluated',
        'recommendation_in_recorded_candidates': consistency,
        'limitations': ['strategic_reasonableness_not_scored_in_this_version'],
    }


def _result_report(resolution_entry):
    if resolution_entry is None:
        return {
            'status': 'pending',
            'available_fields': [],
            'empty_fields': [],
            'missing_fields': ['final_pot', 'winner_ids', 'showdown',
                               'revealed_cards'],
        }
    outcome = resolution_entry['event'].get('outcome')
    outcome = outcome if isinstance(outcome, dict) else {}
    names = ('final_pot', 'winner_ids', 'showdown', 'revealed_cards')
    present = [name for name in names if _field_present(outcome, name)]
    empty = [name for name in present
             if outcome.get(name) == [] or outcome.get(name) == {}]
    available = [name for name in present if name not in empty]
    missing = [name for name in names if name not in outcome
               or outcome.get(name) is None]
    if not available:
        status = 'unavailable'
    elif missing or empty:
        status = 'partial'
    else:
        status = 'available'
    return {
        'status': status,
        'available_fields': available,
        'empty_fields': empty,
        'missing_fields': missing,
        'values': _safe_value({name: outcome.get(name) for name in names
                               if name in outcome}),
    }


def _decision_report(entry, resolution_entry, duplicate_decision,
                     duplicate_resolution, malformed_pair, hand_id_mismatch):
    event = entry['event']
    snapshot = event.get('known_at_decision')
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    execution = None
    if resolution_entry is not None:
        execution = resolution_entry['event'].get('execution')
        if not isinstance(execution, dict):
            execution = {}

    recommended = snapshot.get('recommended_action')
    observed = None
    if execution and execution.get('status') == 'recorded':
        action = execution.get('action')
        if isinstance(action, dict):
            observed = action.get('action')

    if duplicate_decision:
        comparison = {'status': 'excluded', 'reason': 'duplicate_decision_id'}
    elif duplicate_resolution:
        comparison = {'status': 'excluded', 'reason': 'duplicate_resolution_id'}
    elif malformed_pair:
        comparison = {'status': 'excluded', 'reason': 'malformed_event'}
    elif hand_id_mismatch:
        comparison = {'status': 'excluded', 'reason': 'hand_id_mismatch'}
    elif resolution_entry is None:
        comparison = {'status': 'excluded', 'reason': 'decision_pending'}
    elif not _nonempty_string(recommended):
        comparison = {'status': 'excluded',
                      'reason': 'recommended_action_missing'}
    elif execution.get('status') != 'recorded' or not _nonempty_string(observed):
        comparison = {'status': 'excluded', 'reason': 'observed_action_missing'}
    else:
        recommended_code = _action_code(recommended)
        observed_code = _observed_code(observed)
        if recommended_code is None:
            comparison = {'status': 'excluded',
                          'reason': 'recommended_action_mapping_ambiguous',
                          'recommended_action': recommended,
                          'observed_action': observed}
        elif observed_code is None:
            comparison = {'status': 'excluded',
                          'reason': 'observed_action_unrecognized',
                          'recommended_action': recommended,
                          'observed_action': observed}
        else:
            comparison = {
                'status': ('concordant' if recommended_code == observed_code
                           else 'discordant'),
                'recommended_action': recommended,
                'observed_action': observed,
                'normalized_recommended_action': recommended_code,
                'normalized_observed_action': observed_code,
                'comparison_method': 'unambiguous_action_code_mapping',
            }

    absent = []
    if event.get('motor_version') is None:
        absent.append('motor_version')
    absent.extend(
        f'known_at_decision.{key}'
        for key in sorted(_SNAPSHOT_KEYS)
        if key not in snapshot or snapshot.get(key) is None)
    cards_known = snapshot.get('cards_known')
    if not isinstance(cards_known, dict):
        absent.append('known_at_decision.cards_known')
    else:
        absent.extend(
            f'known_at_decision.cards_known.{key}'
            for key in sorted(_CARDS_KNOWN_KEYS)
            if key not in cards_known or cards_known.get(key) is None)
    not_applicable = []
    if snapshot.get('action_values_kind') == 'ev':
        not_applicable.append(
            'known_at_decision.preflop_action_frequencies')
    elif snapshot.get('action_values_kind') == 'frequency':
        not_applicable.append('known_at_decision.ev_by_action')
    resolution_line = resolution_entry['line'] if resolution_entry else None
    integrity_status = 'valid'
    if entry['errors'] or (resolution_entry and resolution_entry['errors']):
        integrity_status = 'malformed'
    if duplicate_decision or duplicate_resolution:
        integrity_status = 'ambiguous_duplicate_id'
    if hand_id_mismatch:
        integrity_status = 'hand_id_mismatch'
    if (resolution_entry is None and not duplicate_decision
            and integrity_status == 'valid'):
        integrity_status = 'pending'

    action_values_kind = snapshot.get('action_values_kind')
    limitations = list(_calculation_report(event)['blockers'])
    if action_values_kind == 'frequency':
        limitations.append('preflop_values_are_frequencies_not_ev')
    cards = snapshot.get('cards_known')
    cards = cards if isinstance(cards, dict) else None
    range_data = snapshot.get('villain_range')
    range_summary = None
    if isinstance(range_data, dict):
        combo_weights = range_data.get('combo_weights')
        range_summary = {
            'representation': range_data.get('representation'),
            'position': range_data.get('position'),
            'source': range_data.get('source'),
            'normalized': range_data.get('normalized'),
            'confidence': range_data.get('confidence'),
            'combo_count': (len(combo_weights)
                            if isinstance(combo_weights, list) else None),
        }
    decision_data = {
        'motor_version': event.get('motor_version'),
        'street': snapshot.get('street'),
        'hero_id': snapshot.get('hero_id'),
        'villain_id': snapshot.get('villain_id'),
        'hero_position': snapshot.get('hero_position'),
        'villain_position': snapshot.get('villain_position'),
        'positions': snapshot.get('positions'),
        'stacks': snapshot.get('stacks'),
        'bets': snapshot.get('bets'),
        'pot': snapshot.get('pot'),
        'to_call': snapshot.get('to_call'),
        'effective_stack': snapshot.get('effective_stack'),
        'cards_known': cards,
        'actions_before_decision': snapshot.get('actions_before_decision'),
        'villain_range': range_summary,
        'villain_range_status': snapshot.get('villain_range_status'),
        'equity': snapshot.get('equity'),
        'pot_odds': snapshot.get('pot_odds'),
        'spr': snapshot.get('spr'),
        'candidate_actions': snapshot.get('candidate_actions'),
        'ev_by_action': snapshot.get('ev_by_action'),
        'preflop_action_frequencies': snapshot.get(
            'preflop_action_frequencies'),
        'action_values_kind': action_values_kind,
        'recommended_action': recommended,
    }
    return {
        'decision_id': event.get('decision_id'),
        'hand_id': event.get('hand_id'),
        'decision_line': entry['line'],
        'resolution_line': resolution_line,
        'integrity': {
            'status': integrity_status,
            'errors': list(entry['errors']) + (
                list(resolution_entry['errors']) if resolution_entry else []),
            'unknown_fields': sorted(set(
                entry['unknown_fields'] +
                (resolution_entry['unknown_fields'] if resolution_entry else []))),
        },
        'information_available': sorted(
            key for key, value in snapshot.items() if value is not None),
        'decision_data': _safe_value(decision_data),
        'fields_absent_or_null': absent,
        'fields_not_applicable': not_applicable,
        'concordance': comparison,
        'calculation_reproducibility': _calculation_report(event),
        'reasonableness': _reasonableness_report(snapshot),
        'observed_result': _result_report(resolution_entry),
        'limitations': sorted(set(limitations)),
    }


def evaluate_events(entries, malformed, blank_lines=0, physical_lines=0,
                    input_path=None, input_error=None):
    by_kind_id = _index_events(entries)
    decisions = by_kind_id['decision']
    resolutions = by_kind_id['resolution']

    duplicate_decisions = [
        {'decision_id': decision_id,
         'lines': [entry['line'] for entry in group]}
        for decision_id, group in sorted(decisions.items()) if len(group) > 1
    ]
    duplicate_resolutions = [
        {'decision_id': decision_id,
         'lines': [entry['line'] for entry in group]}
        for decision_id, group in sorted(resolutions.items()) if len(group) > 1
    ]
    orphan_resolutions = sorted(
        decision_id for decision_id in resolutions if decision_id not in decisions)
    pending_decisions = sorted(
        decision_id for decision_id in decisions
        if decision_id not in resolutions and len(decisions[decision_id]) == 1)
    ambiguous_ids = sorted(
        {i for i, group in decisions.items() if len(group) > 1}
        | {i for i, group in resolutions.items() if len(group) > 1}
    )

    decision_reports = []
    counts = {
        'compared': 0,
        'concordant': 0,
        'discordant': 0,
    }
    excluded = defaultdict(int)
    for decision_id, group in sorted(
            decisions.items(), key=lambda pair: pair[1][0]['line']):
        duplicate_decision = len(group) > 1
        resolution_group = resolutions.get(decision_id, [])
        duplicate_resolution = len(resolution_group) > 1
        resolution_entry = resolution_group[0] if len(resolution_group) == 1 else None
        for entry in group:
            bad_pair = (bool(entry['errors']) or
                        bool(resolution_entry and resolution_entry['errors']))
            mismatch = bool(
                resolution_entry
                and entry['event'].get('hand_id') is not None
                and entry['event'].get('hand_id')
                != resolution_entry['event'].get('hand_id'))
            report = _decision_report(
                entry, resolution_entry, duplicate_decision,
                duplicate_resolution, bad_pair, mismatch)
            decision_reports.append(report)
            state = report['concordance']['status']
            if state in ('concordant', 'discordant'):
                counts['compared'] += 1
                counts[state] += 1
            else:
                excluded[report['concordance'].get('reason', 'unknown')] += 1

    # Invalid recognized events with a line are already included above when
    # they have a decision_id. Keep their line details in the global list.
    valid_events = sum(1 for entry in entries if not entry['errors'])
    report = {
        'report_schema_version': 1,
        'input_path': os.path.abspath(input_path) if input_path else None,
        'integrity': {
            'physical_lines': physical_lines,
            'blank_lines_ignored': blank_lines,
            'parsed_events': len(entries),
            'valid_events': valid_events,
            'malformed_events': malformed,
            'unknown_fields': [
                {'line': entry['line'],
                 'event_type': entry['event'].get('event_type'),
                 'decision_id': entry['event'].get('decision_id'),
                 'fields': entry['unknown_fields']}
                for entry in entries if entry['unknown_fields']
            ],
            'duplicate_ids': {
                'decision_events': duplicate_decisions,
                'resolution_events': duplicate_resolutions,
            },
            'orphan_resolutions': orphan_resolutions,
            'pending_decisions': pending_decisions,
            'ambiguous_decision_ids': ambiguous_ids,
            'linked_decisions': sum(
                1 for decision_id, group in decisions.items()
                if len(group) == 1 and len(resolutions.get(decision_id, [])) == 1),
            'input_error': input_error,
        },
        'concordance': {
            'scope': ('acción normalizada únicamente; no compara sizing, '
                      'importe ni resultado'),
            'numerator': counts['concordant'],
            'denominator': counts['compared'],
            'concordant': counts['concordant'],
            'discordant': counts['discordant'],
            'excluded_by_reason': dict(sorted(excluded.items())),
        },
        'calculation_reproducibility': {
            'status': 'not_attempted',
            'decisions': 'reported individually; no equity/EV recalculation',
        },
        'reasonableness': {
            'status': 'not_evaluated',
            'decisions': 'no strategic score or quality metric is computed',
        },
        'observed_result': {
            'status': 'reported_separately_per_decision',
            'decisions': 'outcomes are not used to score recommendation quality',
        },
        'decisions': decision_reports,
    }
    return report


def evaluate_file(path):
    entries, malformed, blank_lines, physical_lines, error = _read_jsonl(path)
    return evaluate_events(entries, malformed, blank_lines, physical_lines,
                           input_path=path, input_error=error)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Evalúa integridad y disponibilidad del registro JSONL; '
                    'no recalcula equity/EV ni modifica archivos de entrada.')
    parser.add_argument('entrada', nargs='?', default=DEFAULT_INPUT,
                        help='JSONL de decisiones (default: data/decisions.jsonl)')
    parser.add_argument('--salida', help='ruta opcional del informe JSON; '
                        'por defecto se escribe en stdout')
    args = parser.parse_args(argv)
    report = evaluate_file(args.entrada)
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True,
                          indent=2, allow_nan=False) + '\n'
    if args.salida:
        if os.path.realpath(args.salida) == os.path.realpath(args.entrada):
            parser.error('la salida no puede sobrescribir el registro de entrada')
        with open(args.salida, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(rendered)
    else:
        sys.stdout.write(rendered)
    return 2 if report['integrity']['input_error'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
