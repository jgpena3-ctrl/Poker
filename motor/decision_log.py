"""Append-only JSONL log for motor recommendations and later hand outcomes.

This sidecar is intentionally separate from ``hands_db.jsonl``. A decision
event contains only information known when the recommendation was emitted;
later execution/outcome information is appended as a distinct resolution event.
"""
from __future__ import annotations

import json
import math
import os
import threading
import uuid
from collections import Counter
from datetime import datetime, timezone


SCHEMA_VERSION = 3
DEFAULT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data',
                            'decisions.jsonl')


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _clean(value):
    """Convert values to strict JSON, representing non-finite numbers as null."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_clean(v) for v in value]
    # numpy scalars/arrays and similar objects expose these conversion hooks.
    if hasattr(value, 'item'):
        try:
            return _clean(value.item())
        except (TypeError, ValueError):
            pass
    if hasattr(value, 'tolist'):
        try:
            return _clean(value.tolist())
        except (TypeError, ValueError):
            pass
    return None


class DecisionLog:
    """Append recommendation snapshots and separate hand-resolution events."""

    def __init__(self, path=None):
        self.path = os.path.abspath(path or os.environ.get(
            'POKER_DECISIONS_PATH', DEFAULT_PATH))
        self._lock = threading.Lock()
        self._pending = {}
        self._load_pending()

    def _append(self, event):
        line = json.dumps(_clean(event), ensure_ascii=False,
                          allow_nan=False, separators=(',', ':'))
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with self._lock:
            with open(self.path, 'a', encoding='utf-8', newline='\n') as f:
                f.write(line + '\n')
                f.flush()
                os.fsync(f.fileno())

    def _load_pending(self):
        """Recover unresolved ids if the assistant is restarted mid-session."""
        if not os.path.isfile(self.path):
            return
        resolved = set()
        decisions = []
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event = json.loads(line)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if not isinstance(event, dict):
                        continue
                    if event.get('event_type') == 'decision':
                        decisions.append(event)
                    elif event.get('event_type') == 'resolution':
                        resolved.add(event.get('decision_id'))
        except OSError:
            return
        for event in decisions:
            decision_id = event.get('decision_id')
            hand_id = event.get('hand_id')
            if not decision_id or not hand_id or decision_id in resolved:
                continue
            known = event.get('known_at_decision') or {}
            seen_actions = [a for a in known.get('actions_before_decision') or []
                            if a.get('street') == known.get('street')]
            self._pending.setdefault(hand_id, []).append({
                'decision_id': decision_id,
                'street': known.get('street'),
                'hero_position': known.get('hero_position'),
                'actions_seen_count': known.get('actions_seen_count'),
                'actions_seen': seen_actions,
            })

    def record_decision(self, snapshot, *, hand_id=None, street=None,
                        hero_position=None, actions_seen_count=None):
        decision_id = uuid.uuid4().hex
        event = {
            'schema_version': SCHEMA_VERSION,
            'event_type': 'decision',
            'decision_id': decision_id,
            'hand_id': hand_id,
            'recorded_at': _utc_now(),
            'motor_version': os.environ.get('POKER_MOTOR_VERSION') or None,
            'known_at_decision': snapshot,
            'execution': {'status': 'pending', 'action': None},
            'outcome': {'status': 'pending'},
        }
        self._append(event)
        if hand_id:
            self._pending.setdefault(hand_id, []).append({
                'decision_id': decision_id,
                'street': street,
                'hero_position': hero_position,
                'actions_seen_count': actions_seen_count,
                'actions_seen': [a for a in
                                 snapshot.get('actions_before_decision') or []
                                 if a.get('street') == street],
            })
        return decision_id

    def resolve_hand(self, hand):
        """Append later observed action/outcome events for this hand's decisions."""
        hand_id = hand.get('hand_id')
        if not hand_id:
            return 0
        pending = list(self._pending.get(hand_id, []))
        written = 0
        streets = hand.get('streets') or {}
        for item in pending:
            street = item.get('street')
            street_record = streets.get(street) or {}
            actions = street_record.get('actions') or []
            def signature(a):
                return (a.get('pos'), a.get('action'), a.get('amount'),
                        a.get('amount_type'))
            seen = Counter(signature(a) for a in item.get('actions_seen', []))
            new_actions = []
            for candidate in actions:
                key = signature(candidate)
                if seen[key]:
                    seen[key] -= 1
                else:
                    new_actions.append(candidate)
            action = next((a for a in new_actions
                           if a.get('pos') == item.get('hero_position')), None)
            execution = {
                'status': 'recorded' if action is not None else 'not_observed',
                'action': ({k: action.get(k) for k in
                            ('pos', 'action', 'amount', 'amount_type')
                            if k in action} if action is not None else None),
            }
            players = hand.get('players') or []
            revealed = {p.get('pos'): p.get('cards') for p in players
                        if p.get('cards')}
            outcome = {
                'status': 'recorded',
                'final_pot': hand.get('final_pot'),
                'winner_ids': hand.get('winner'),
                'showdown': hand.get('showdown'),
                'revealed_cards': revealed,
            }
            self._append({
                'schema_version': SCHEMA_VERSION,
                'event_type': 'resolution',
                'decision_id': item['decision_id'],
                'hand_id': hand_id,
                'recorded_at': _utc_now(),
                'execution': execution,
                'outcome': outcome,
            })
            remaining = self._pending.get(hand_id, [])
            self._pending[hand_id] = [
                current for current in remaining
                if current['decision_id'] != item['decision_id']]
            if not self._pending[hand_id]:
                self._pending.pop(hand_id, None)
            written += 1
        return written
