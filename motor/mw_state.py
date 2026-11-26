"""Conservative interpretation of a multiway hand snapshot.

The parser keeps observed, inferred and unknown fields distinct. A player is
never considered active merely because a fold was not seen in an incomplete
action log.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Optional, Tuple

from .cards import card_id


class MWStateError(ValueError):
    """Malformed state input; callers must abstain rather than guess."""


@dataclass(frozen=True)
class Evidence:
    value: Any
    source: str
    reason: Optional[str] = None

    def __post_init__(self):
        if self.source not in ('observed', 'inferred', 'unknown'):
            raise MWStateError('evidence source inválido')
        if self.source == 'unknown':
            if self.value is not None or not self.reason:
                raise MWStateError('unknown requiere value=None y reason')
        elif self.value is None and not (
                self.source == 'observed' and self.reason == 'no_action_faced'):
            raise MWStateError('evidence observada/inferida requiere value')


@dataclass(frozen=True)
class MWPlayer:
    identity: str
    position: Evidence
    status: Evidence
    hole_cards: Evidence
    stack: Evidence
    contribution: Evidence


@dataclass(frozen=True)
class MWAction:
    index: int
    street: str
    player_id: str
    action: str
    amount: Evidence
    facing: Evidence


@dataclass(frozen=True)
class MWHandState:
    status: str
    hero_id: str
    street: str
    board: Tuple[str, ...]
    board_evidence: Evidence
    players: Tuple[MWPlayer, ...]
    actions: Tuple[MWAction, ...]
    actor: Evidence
    facing_action: Evidence
    to_call: Evidence
    pot: Evidence
    sequence_complete: Evidence
    issues: Tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return self.status == 'ready'

    @property
    def hero(self) -> Optional[MWPlayer]:
        return next((p for p in self.players if p.identity == self.hero_id), None)

    @property
    def active_opponents(self) -> Tuple[MWPlayer, ...]:
        return tuple(p for p in self.players
                     if p.identity != self.hero_id
                     and p.status.source != 'unknown'
                     and p.status.value in ('active', 'all_in'))

    @property
    def can_proceed_strategically(self) -> bool:
        return self.ready and self.actor.value == self.hero_id

    @property
    def mode(self) -> Optional[str]:
        if not self.ready:
            return None
        count = len(self.active_opponents)
        if count == 1:
            return 'HU'
        if count >= 2:
            return 'MW'
        return None

    def as_dict(self) -> dict:
        def e(value):
            return {'value': value.value, 'source': value.source,
                    'reason': value.reason}
        return {
            'status': self.status, 'hero_id': self.hero_id,
            'mode': self.mode,
            'street': self.street, 'board': list(self.board),
            'board_evidence': e(self.board_evidence),
            'players': [{
                'identity': p.identity, 'position': e(p.position),
                'status': e(p.status), 'hole_cards': e(p.hole_cards),
                'stack': e(p.stack), 'contribution': e(p.contribution),
            } for p in self.players],
            'actions': [{
                'index': a.index, 'street': a.street,
                'player_id': a.player_id, 'action': a.action,
                'amount': e(a.amount), 'facing': e(a.facing),
            } for a in self.actions],
            'actor': e(self.actor), 'facing_action': e(self.facing_action),
            'to_call': e(self.to_call), 'pot': e(self.pot),
            'sequence_complete': e(self.sequence_complete),
            'issues': list(self.issues),
        }


STREET_BOARD = {'preflop': 0, 'flop': 3, 'turn': 4, 'river': 5}
PLAYER_STATUSES = ('active', 'folded', 'all_in')
ACTION_NAMES = ('post', 'check', 'fold', 'call', 'bet', 'raise', 'all_in')


def _evidence(raw, *, missing_reason, validator=None):
    if raw is None:
        return Evidence(None, 'unknown', missing_reason)
    if isinstance(raw, Mapping) and 'source' in raw:
        source = raw.get('source')
        value = raw.get('value')
        reason = raw.get('reason')
    else:
        source, value, reason = 'observed', raw, None
    if source == 'unknown':
        return Evidence(None, 'unknown', reason or missing_reason)
    if source not in ('observed', 'inferred') or value is None:
        return Evidence(None, 'unknown', 'invalid_evidence')
    if validator is not None:
        try:
            value = validator(value)
        except (TypeError, ValueError, MWStateError):
            return Evidence(None, 'unknown', 'invalid_value')
    return Evidence(value, source, reason)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('must be numeric')
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError('must be finite and nonnegative')
    return result


def _position(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('position missing')
    return value.strip()


def _cards(value, allowed_lengths=(0, 2)):
    if value is None or value == () or value == []:
        return ()
    if isinstance(value, str):
        if len(value) % 2:
            raise ValueError('invalid compact card sequence')
        value = [value[i:i + 2] for i in range(0, len(value), 2)]
    if not isinstance(value, (tuple, list)):
        raise ValueError('cards must be sequence')
    cards = tuple(value)
    for card in cards:
        card_id(card)
    if len(cards) not in allowed_lengths:
        raise ValueError('card count not valid for this field')
    if len(set(cards)) != len(cards):
        raise ValueError('duplicate hole card')
    return cards


def interpret_mw_state(raw: Mapping[str, Any]) -> MWHandState:
    """Parse a complete snapshot without filling unknown active-player state.

    Required raw shape: ``hero_id``, ``street``, ``board``, ``players``,
    ``actions`` and ``decision``. Each player's ``status`` must be explicitly
    observed/inferred or derivable from an explicitly complete action sequence.
    """
    if not isinstance(raw, Mapping):
        raise MWStateError('state debe ser Mapping')
    hero_id = raw.get('hero_id')
    street = raw.get('street')
    if not isinstance(hero_id, str) or not hero_id.strip():
        raise MWStateError('hero_id ausente')
    hero_id = hero_id.strip()
    if not isinstance(street, str) or street not in STREET_BOARD:
        raise MWStateError('street inválida')
    board_raw = raw.get('board')
    board_issues = []
    if isinstance(board_raw, Mapping) and 'source' in board_raw:
        board_evidence = _evidence(
            board_raw, missing_reason='board_unknown',
            validator=lambda value: _cards(
                value, allowed_lengths=(0, 3, 4, 5)))
        if board_evidence.source == 'unknown':
            board = ()
            board_issues.append('board_unknown')
        else:
            board = board_evidence.value
    else:
        try:
            board = _cards(board_raw, allowed_lengths=(0, 3, 4, 5))
        except (ValueError, TypeError) as exc:
            raise MWStateError(f'board inválido: {exc}') from exc
        board_evidence = Evidence(board, 'observed')
    if (board_evidence.source != 'unknown'
            and len(board) != STREET_BOARD[street]):
        raise MWStateError('board no corresponde a la calle')
    if len({card_id(c) for c in board}) != len(board):
        raise MWStateError('board contiene duplicados')

    sequence_complete = _evidence(
        raw.get('sequence_complete'), missing_reason='action_sequence_unknown',
        validator=lambda x: x if isinstance(x, bool) else (_ for _ in ()).throw(
            ValueError('bool required')))
    actions_raw = raw.get('actions')
    actions_missing = not isinstance(actions_raw, (tuple, list))
    if actions_missing:
        actions_raw = []
    actions = []
    previous_index = -1
    previous_street_index = -1
    player_ids = set()
    raw_player_rows = []
    if not isinstance(raw.get('players'), (tuple, list)):
        raise MWStateError('players debe ser una lista')
    for item in raw['players']:
        if not isinstance(item, Mapping):
            raise MWStateError('player inválido')
        identity = item.get('identity')
        if not isinstance(identity, str) or not identity.strip():
            raise MWStateError('player identity ausente')
        identity = identity.strip()
        item = dict(item, identity=identity)
        # Normalize in a private copy; raw capture input remains untouched.
        raw_player_rows.append(item)
        if identity in player_ids:
            raise MWStateError('identidad de jugador duplicada')
        player_ids.add(identity)
    if hero_id not in player_ids:
        raise MWStateError('hero no está en players')

    for pos, item in enumerate(actions_raw):
        if not isinstance(item, Mapping):
            raise MWStateError('acción inválida')
        index = item.get('index', pos)
        if isinstance(index, bool) or not isinstance(index, int) or index <= previous_index:
            raise MWStateError('secuencia de acciones ambigua/no ordenada')
        previous_index = index
        actor_id = item.get('player_id')
        if isinstance(actor_id, str):
            actor_id = actor_id.strip()
        action = item.get('action')
        action_street = item.get('street', street)
        if (not isinstance(actor_id, str) or actor_id not in player_ids
                or action not in ACTION_NAMES
                or not isinstance(action_street, str)
                or action_street not in STREET_BOARD):
            raise MWStateError('acción sin jugador/categoría/calle válida')
        street_index = tuple(STREET_BOARD).index(action_street)
        if street_index < previous_street_index:
            raise MWStateError('orden cronológico de calles contradictorio')
        previous_street_index = street_index
        amount = _evidence(item.get('amount'),
                           missing_reason='action_amount_not_observed',
                           validator=_number)
        if 'facing' not in item:
            facing = Evidence(None, 'unknown', 'action_facing_unknown')
        elif item['facing'] is None:
            facing = Evidence(None, 'observed', 'no_action_faced')
        elif item['facing'] in ('check', 'bet', 'raise', 'all_in'):
            facing = Evidence(item['facing'], 'observed')
        else:
            facing = Evidence(None, 'unknown', 'invalid_action_facing')
        actions.append(MWAction(index, action_street, actor_id, action,
                                amount, facing))

    actions_by_player = {}
    closed_by_player = {}
    chronology_issues = []
    for action in actions:
        if action.player_id in closed_by_player:
            chronology_issues.append(
                f'{action.player_id}:action_after_{closed_by_player[action.player_id]}')
        if action.action in ('fold', 'all_in'):
            closed_by_player[action.player_id] = action.action
        actions_by_player.setdefault(action.player_id, []).append(action)

    players = []
    all_known = list(board)
    unresolved = []
    unresolved.extend(board_issues)
    if actions_missing:
        unresolved.append('action_sequence_unknown')
    for item in raw_player_rows:
        identity = item['identity']
        try:
            hole = _evidence(item.get('hole_cards'),
                             missing_reason='hole_cards_unknown',
                             validator=_cards)
        except (ValueError, TypeError):
            hole = Evidence(None, 'unknown', 'invalid_hole_cards')
        pos = _evidence(item.get('position'),
                        missing_reason='position_unknown', validator=_position)
        status = _evidence(item.get('status'),
                           missing_reason='player_status_unknown')
        if status.source != 'unknown' and status.value not in PLAYER_STATUSES:
            status = Evidence(None, 'unknown', 'invalid_player_status')
        history = actions_by_player.get(identity, [])
        if status.source == 'unknown' and sequence_complete.value is True:
            last = history[-1].action if history else None
            inferred = ('folded' if last == 'fold' else
                        'all_in' if last == 'all_in' else 'active')
            status = Evidence(inferred, 'inferred',
                              'complete_action_sequence')
        elif status.source == 'unknown' and history \
                and history[-1].action in ('fold', 'all_in'):
            status = Evidence(
                'folded' if history[-1].action == 'fold' else 'all_in',
                'inferred', 'explicit_terminal_action')
        stack = _evidence(item.get('stack'),
                          missing_reason='stack_unknown', validator=_number)
        contribution = _evidence(
            item.get('contribution'), missing_reason='contribution_unknown',
            validator=_number)
        if status.source == 'unknown':
            unresolved.append(f'{identity}:player_status_unknown')
        if identity == hero_id and (
                hole.source == 'unknown' or len(hole.value) != 2):
            unresolved.append('hero_hole_cards_unknown')
        if hole.source == 'unknown' and hole.reason == 'invalid_value':
            unresolved.append(f'{identity}:invalid_hole_cards')
        if hole.source != 'unknown':
            if len(hole.value) not in (0, 2):
                unresolved.append(f'{identity}:invalid_hole_cards')
            all_known.extend(hole.value)
        if history and history[-1].action == 'fold' \
                and status.value not in ('folded', None):
            unresolved.append(f'{identity}:fold_status_contradiction')
        if history and history[-1].action == 'all_in' \
                and status.value not in ('all_in', None):
            unresolved.append(f'{identity}:all_in_status_contradiction')
        if status.value == 'folded' and history and history[-1].action == 'all_in':
            unresolved.append(f'{identity}:all_in_fold_status_contradiction')
        if sequence_complete.value is True:
            last_action = history[-1].action if history else None
            if status.value == 'folded' and last_action != 'fold':
                unresolved.append(f'{identity}:fold_missing_from_complete_sequence')
            if status.value == 'all_in' and last_action != 'all_in':
                unresolved.append(f'{identity}:all_in_missing_from_complete_sequence')
        players.append(MWPlayer(identity, pos, status, hole, stack, contribution))

    ids = [card_id(c) for c in all_known]
    if len(ids) != len(set(ids)):
        unresolved.append('known_cards_overlap')
    unresolved.extend(chronology_issues)

    decision = raw.get('decision')
    if not isinstance(decision, Mapping):
        decision = {}
    actor = _evidence(decision.get('actor_id'),
                      missing_reason='decision_actor_unknown',
                      validator=_position)
    to_call = _evidence(decision.get('to_call'),
                        missing_reason='to_call_unknown', validator=_number)
    pot = _evidence(raw.get('pot'), missing_reason='pot_unknown',
                    validator=_number)
    if pot.source != 'unknown' and all(
            p.contribution.source != 'unknown' for p in players):
        committed = sum(p.contribution.value for p in players)
        if not math.isclose(committed, pot.value, rel_tol=1e-9, abs_tol=1e-6):
            unresolved.append('pot_contribution_mismatch')
    if 'facing_action' in decision:
        facing_raw = decision['facing_action']
        if facing_raw is None:
            facing = Evidence(None, 'observed', 'no_action_faced')
        elif isinstance(facing_raw, Mapping) and 'source' in facing_raw:
            source = facing_raw.get('source')
            payload = facing_raw.get('value')
            if source == 'unknown':
                facing = Evidence(None, 'unknown',
                                  facing_raw.get('reason') or
                                  'facing_action_unknown')
            elif source in ('observed', 'inferred') and payload is None \
                    and source == 'observed':
                facing = Evidence(None, 'observed', 'no_action_faced')
            elif source in ('observed', 'inferred') \
                    and isinstance(payload, Mapping) \
                    and isinstance(payload.get('player_id'), str) \
                    and payload.get('player_id') in player_ids \
                    and payload.get('action') in ACTION_NAMES:
                facing = Evidence(dict(payload), source)
            else:
                facing = Evidence(None, 'unknown', 'invalid_facing_action')
        elif isinstance(facing_raw, Mapping) \
                and isinstance(facing_raw.get('player_id'), str) \
                and facing_raw.get('player_id') in player_ids \
                and facing_raw.get('action') in ACTION_NAMES:
            facing = Evidence(dict(facing_raw), 'observed')
        else:
            facing = Evidence(None, 'unknown', 'invalid_facing_action')
    else:
        facing = Evidence(None, 'unknown', 'facing_action_unknown')
    if actor.source == 'unknown' or actor.value != hero_id:
        unresolved.append('hero_decision_actor_unknown_or_mismatch')
    if to_call.source == 'unknown':
        unresolved.append('to_call_unknown')
    if facing.source == 'unknown':
        unresolved.append('facing_action_unknown')
    if facing.source != 'unknown' and to_call.source != 'unknown':
        if facing.value is None and to_call.value != 0:
            unresolved.append('to_call_without_facing_action')
        if facing.value is not None and to_call.value <= 0:
            unresolved.append('facing_action_without_to_call')
    if sequence_complete.value is True and facing.value is not None:
        latest_wager_this_street = next(
            (event for event in reversed(actions)
             if event.street == street
             and event.action in ('bet', 'raise', 'all_in')), None)
        if (latest_wager_this_street is None
                or latest_wager_this_street.player_id
                != facing.value['player_id']
                or latest_wager_this_street.action != facing.value['action']):
            unresolved.append('facing_action_sequence_mismatch')
    hero = next(p for p in players if p.identity == hero_id)
    if hero.status.value not in ('active', None):
        unresolved.append('hero_not_able_to_act')
    if not any(p.identity != hero_id and p.status.value in ('active', 'all_in')
               for p in players):
        unresolved.append('no_active_opponents')
    status = 'ready' if not unresolved else 'unresolved'
    return MWHandState(
        status=status, hero_id=hero_id, street=street, board=board,
        board_evidence=board_evidence,
        players=tuple(players), actions=tuple(actions), actor=actor,
        facing_action=facing, to_call=to_call,
        pot=pot,
        sequence_complete=sequence_complete,
        issues=tuple(dict.fromkeys(unresolved)))
