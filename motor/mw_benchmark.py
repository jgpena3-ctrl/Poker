"""Synthetic, local-only benchmark for the experimental MW evaluator.

This module never reads historical hands, never writes derived artifacts and is
not imported by live serving. It measures each stage separately so a claim such
as "8 seconds" can only be made after an end-to-end measurement on the target
machine and fixture set.

Stages:
    state  -> interpret_mw_state(raw)
    ranges -> build_ranges_from_state(state, ...)
    equity -> calculate_multiway_equity(...)
    tree   -> evaluate_mw_action_tree(...)   (includes internal terminal EV)
    ev     -> calculate_mw_ev(...)           (forced-showdown contract)
    total  -> interpret + ranges + tree input + tree (routing-equivalent)
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import statistics
import time
from typing import Callable, Mapping, Optional, Sequence, Tuple

from .mw_equity import calculate_multiway_equity
from .mw_ev import EquityEvidence, MWGameEVInput, calculate_mw_ev
from .mw_ranges import build_ranges_from_state
from .mw_response_tree import (
    ActionSpec, MWTreeInput, MWTreeLimits, ResponseAssessment,
    ResponseDistribution, ResponseOutcome, evaluate_mw_action_tree,
)
from .mw_state import interpret_mw_state


RIVER = ('2c', '3d', '4h', '5s', '9c')
FLOP = RIVER[:3]
HERO = ('As', 'Ad')
HANDS = {'v1': ('Kc', 'Kd'), 'v2': ('Qc', 'Qd')}
EQUITY_STAGE_SAMPLES = 200


class SyntheticResponseProvider:
    """Deterministic synthetic counts, never presented as poker evidence."""

    def __init__(self, weights: Optional[Mapping[str, int]] = None):
        self.weights = dict(weights or {
            'fold': 98, 'check': 98, 'call': 98,
            'bet': 1, 'raise': 1, 'all_in': 1,
        })
        self.calls = 0

    def assess(self, context):
        self.calls += 1
        counts = [max(1, int(self.weights.get(spec.action, 1)))
                  for spec in context.legal_actions]
        denominator = sum(counts)
        outcomes = tuple(
            ResponseOutcome(
                spec=spec, probability=count / denominator,
                numerator=count, denominator=denominator,
                source='synthetic_benchmark_counts', coverage='exact',
                uncertainty='not_quantified')
            for spec, count in zip(context.legal_actions, counts))
        distribution = ResponseDistribution(
            player_id=context.player_id,
            context_key=context.context_key,
            source='synthetic_benchmark_counts', source_kind='synthetic',
            outcomes=outcomes, conditional_on_history=True,
            action_space_complete=True, coverage='exact')
        return ResponseAssessment('available', distribution, None,
                                  {'synthetic_benchmark': True})


@dataclass(frozen=True)
class BenchmarkFixture:
    name: str
    raw: Mapping
    pending: Tuple[str, ...]
    hero_actions: Tuple[ActionSpec, ...]
    limits: MWTreeLimits


def _raw(*, street, board, history=()):
    players = []
    positions = {'hero': 'BTN', 'v1': 'SB', 'v2': 'BB'}
    for identity in ('hero', 'v1', 'v2'):
        cards = HERO if identity == 'hero' else HANDS[identity]
        players.append({
            'identity': identity, 'position': positions[identity],
            'status': 'active', 'hole_cards': list(cards),
            'stack': 5.0, 'contribution': 20.0,
        })
    return {
        'hero_id': 'hero', 'street': street, 'board': list(board),
        'pot': 60.0, 'players': players, 'actions': list(history),
        'sequence_complete': True,
        'decision': {'actor_id': 'hero', 'to_call': 0.0,
                     'facing_action': None},
    }


def _tree_input(state, pending):
    ranges = build_ranges_from_state(state, {}, {})
    order = tuple(p.identity for p in state.active_opponents
                  if p.status.value == 'active')
    return MWTreeInput(
        state=state, ranges=ranges,
        street_bets={p.identity: 0.0 for p in state.players},
        action_order=order, pending_opponents=tuple(pending),
        min_bet=5.0, min_raise=5.0,
        action_order_source='synthetic', pending_source='synthetic',
        response_sizes={}, action_space_complete=True,
        action_space_scope='synthetic benchmark')


def default_fixtures() -> Tuple[BenchmarkFixture, ...]:
    river_limits = MWTreeLimits(
        exact_equity=False, equity_samples=200, runout_samples=2,
        max_nodes=80, max_depth=16, timeout_seconds=90.0, seed=7)
    flop_limits = MWTreeLimits(
        exact_equity=False, equity_samples=200, runout_samples=2,
        max_nodes=80, max_depth=16, timeout_seconds=90.0, seed=7)
    return (
        BenchmarkFixture(
            name='river_forced_showdown',
            raw=_raw(street='river', board=RIVER),
            pending=('v1', 'v2'),
            hero_actions=(ActionSpec('check', 0.0),
                          ActionSpec('bet', 5.0)),
            limits=river_limits),
        BenchmarkFixture(
            name='flop_to_turn',
            raw=_raw(street='flop', board=FLOP, history=(
                {'index': 0, 'player_id': 'v1', 'action': 'check',
                 'street': 'flop', 'amount': 0.0, 'facing': None},
                {'index': 1, 'player_id': 'v2', 'action': 'check',
                 'street': 'flop', 'amount': 0.0, 'facing': None},
            )),
            pending=(),
            hero_actions=(ActionSpec('check', 0.0),),
            limits=flop_limits),
    )


def _locked_ev_input() -> MWGameEVInput:
    return MWGameEVInput(
        hero_id='hero',
        contributions={'hero': 20.0, 'v1': 20.0, 'v2': 20.0},
        player_status={'hero': 'active', 'v1': 'all_in', 'v2': 'all_in'},
        hero_stack=5.0, to_call=0.0,
        equity_by_opponents={
            ('v1', 'v2'): EquityEvidence(
                equity=0.4, exact=False, standard_error=0.01,
                model='synthetic_monte_carlo', opponents=('v1', 'v2')),
        })


def _timed(call: Callable):
    started = time.perf_counter()
    value = call()
    return (time.perf_counter() - started) * 1_000.0, value


def percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError('values no puede estar vacío')
    if not 0 < q <= 1:
        raise ValueError('q debe estar en (0,1]')
    index = max(0, math.ceil(q * len(ordered)) - 1)
    return ordered[min(index, len(ordered) - 1)]


def summarize(samples: Sequence[float]) -> dict:
    if not samples:
        raise ValueError('samples no puede estar vacío')
    return {
        'n': len(samples),
        'mean_ms': statistics.fmean(samples),
        'p50_ms': percentile(samples, 0.50),
        'p95_ms': percentile(samples, 0.95),
        'max_ms': max(samples),
    }


def run_benchmark(*, repeats: int = 20,
                  fixtures: Optional[Sequence[BenchmarkFixture]] = None
                  ) -> dict:
    """Measure every stage per fixture. Returns raw per-stage summaries."""
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError('repeats debe ser entero positivo')
    fixtures = tuple(fixtures or default_fixtures())
    report = {}
    ev_input = _locked_ev_input()
    for fixture in fixtures:
        state_samples, ranges_samples, equity_samples = [], [], []
        tree_samples, ev_samples, total_samples = [], [], []
        tree_status, tree_nodes = None, None
        for _ in range(repeats):
            elapsed, state = _timed(lambda: interpret_mw_state(fixture.raw))
            state_samples.append(elapsed)

            elapsed, ranges = _timed(
                lambda: build_ranges_from_state(state, {}, {}))
            ranges_samples.append(elapsed)

            active_ranges = tuple(
                ranges[p.identity] for p in state.active_opponents)
            elapsed, _ = _timed(lambda: calculate_multiway_equity(
                HERO, state.board,
                tuple(value.to_equity_range() for value in active_ranges),
                exact=False, samples=EQUITY_STAGE_SAMPLES, seed=7))
            equity_samples.append(elapsed)

            data = _tree_input(state, fixture.pending)
            elapsed, tree_result = _timed(lambda: evaluate_mw_action_tree(
                data, fixture.hero_actions, SyntheticResponseProvider(),
                limits=fixture.limits))
            tree_samples.append(elapsed)
            tree_status, tree_nodes = tree_result.status, tree_result.nodes

            elapsed, _ = _timed(lambda: calculate_mw_ev(ev_input))
            ev_samples.append(elapsed)

            def full_pipeline():
                fresh_state = interpret_mw_state(fixture.raw)
                fresh_data = _tree_input(fresh_state, fixture.pending)
                return evaluate_mw_action_tree(
                    fresh_data, fixture.hero_actions,
                    SyntheticResponseProvider(), limits=fixture.limits)

            elapsed, _ = _timed(full_pipeline)
            total_samples.append(elapsed)
        report[fixture.name] = {
            'state': summarize(state_samples),
            'ranges': summarize(ranges_samples),
            'equity': summarize(equity_samples),
            'tree': summarize(tree_samples),
            'ev': summarize(ev_samples),
            'total': summarize(total_samples),
            'meta': {
                'tree_status': tree_status, 'tree_nodes': tree_nodes,
                'limits': {
                    'max_nodes': fixture.limits.max_nodes,
                    'max_depth': fixture.limits.max_depth,
                    'max_branches_per_node':
                        fixture.limits.max_branches_per_node,
                    'timeout_seconds': fixture.limits.timeout_seconds,
                    'equity_samples': fixture.limits.equity_samples,
                    'runout_samples': fixture.limits.runout_samples,
                    'exact_equity': fixture.limits.exact_equity,
                },
                'equity_stage_samples': EQUITY_STAGE_SAMPLES,
            },
        }
    return report


def format_report(report: Mapping[str, Mapping[str, Mapping[str, float]]]
                  ) -> str:
    lines = []
    header = ('%-24s %-7s %5s %9s %9s %9s %9s'
              % ('fixture', 'stage', 'n', 'mean_ms', 'p50_ms',
                 'p95_ms', 'max_ms'))
    lines.append(header)
    lines.append('-' * len(header))
    for fixture, stages in report.items():
        for stage in ('state', 'ranges', 'equity', 'tree', 'ev', 'total'):
            stats = stages[stage]
            lines.append('%-24s %-7s %5d %9.3f %9.3f %9.3f %9.3f' % (
                fixture, stage, stats['n'], stats['mean_ms'],
                stats['p50_ms'], stats['p95_ms'], stats['max_ms']))
        meta = stages.get('meta') or {}
        lines.append('%-24s tree_status=%s tree_nodes=%s' % (
            '', meta.get('tree_status'), meta.get('tree_nodes')))
        limits = meta.get('limits') or {}
        lines.append('%-24s limits=%s equity_stage_samples=%s' % (
            '', limits, meta.get('equity_stage_samples')))
    lines.append('')
    lines.append('Synthetic fixtures only; local timings are not a budget '
                 'guarantee and are not real response evidence.')
    return '\n'.join(lines)
