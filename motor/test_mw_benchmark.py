from dataclasses import replace

from motor.mw_benchmark import default_fixtures, run_benchmark
from motor.mw_response_tree import MWTreeLimits


STAGES = {'state', 'ranges', 'equity', 'tree', 'ev', 'total'}


def _tiny_fixtures():
    limits = MWTreeLimits(
        exact_equity=False, equity_samples=10, runout_samples=1,
        max_nodes=5, max_depth=6, timeout_seconds=10.0, seed=7)
    return [replace(fixture, limits=limits)
            for fixture in default_fixtures()]


def test_benchmark_reports_every_stage_with_percentiles():
    report = run_benchmark(repeats=1, fixtures=_tiny_fixtures())
    assert set(report) == {'river_forced_showdown', 'flop_to_turn'}
    for stages in report.values():
        assert STAGES <= set(stages)
        assert stages['meta']['tree_nodes'] >= 1
        for stage in STAGES:
            stats = stages[stage]
            assert stats['n'] == 1
            assert 0 <= stats['p50_ms'] <= stats['p95_ms'] <= stats['max_ms']
            assert stats['mean_ms'] >= 0
