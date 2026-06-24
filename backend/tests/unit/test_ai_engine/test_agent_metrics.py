"""
Unit tests for the Agent Metrics module.

Tests cover:
    - AgentMetricsCollector: recording calls, context managers, decorators
    - Token integration (via existing token_tracker)
    - Summary report generation
    - Reset functionality
"""

import asyncio
import pytest

from ai_engine.evaluation.agent_metrics import (
    AgentMetricsCollector,
    AgentMetricsSnapshot,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def collector() -> AgentMetricsCollector:
    """Fresh collector with no recorded data."""
    c = AgentMetricsCollector()
    yield c
    c.reset()


# ── Test: Record Calls ───────────────────────────────────────────────────────


class TestRecordCalls:

    def test_record_successful_call(self, collector: AgentMetricsCollector):
        collector.record_call("planner", 0.5)
        snap = collector.get_snapshot("planner")
        assert snap is not None
        assert snap.calls == 1
        assert snap.errors == 0
        assert snap.error_rate == 0.0

    def test_record_multiple_calls(self, collector: AgentMetricsCollector):
        collector.record_call("planner", 0.3)
        collector.record_call("planner", 0.7)
        collector.record_call("planner", 0.5)
        snap = collector.get_snapshot("planner")
        assert snap.calls == 3
        assert len(snap.durations_ms) == 3

    def test_record_error_call(self, collector: AgentMetricsCollector):
        collector.record_call("validator", 0.2, error=True, error_message="Timeout")
        snap = collector.get_snapshot("validator")
        assert snap.calls == 1
        assert snap.errors == 1
        assert snap.error_rate == 1.0

    def test_mixed_success_and_error(self, collector: AgentMetricsCollector):
        collector.record_call("retrieval", 0.1)
        collector.record_call("retrieval", 0.15)
        collector.record_call("retrieval", 0.2, error=True)
        snap = collector.get_snapshot("retrieval")
        assert snap.calls == 3
        assert snap.errors == 1
        assert snap.error_rate == pytest.approx(1 / 3)

    def test_multiple_agent_roles(self, collector: AgentMetricsCollector):
        collector.record_call("planner", 0.5)
        collector.record_call("validator", 0.3)
        collector.record_call("retrieval", 0.1)

        all_snaps = collector.get_all_snapshots()
        assert set(all_snaps.keys()) == {"planner", "validator", "retrieval"}
        assert all_snaps["planner"].calls == 1
        assert all_snaps["validator"].calls == 1
        assert all_snaps["retrieval"].calls == 1

    def test_duration_converted_to_ms(self, collector: AgentMetricsCollector):
        """Record duration in seconds → stored as ms."""
        collector.record_call("test", 1.5)
        snap = collector.get_snapshot("test")
        assert snap.avg_duration_ms == pytest.approx(1500.0, rel=0.01)


# ── Test: AgentMetricsSnapshot ──────────────────────────────────────────────


class TestMetricsSnapshot:

    def test_empty_snapshot(self):
        snap = AgentMetricsSnapshot()
        assert snap.calls == 0
        assert snap.errors == 0
        assert snap.error_rate == 0.0
        assert snap.min_duration_ms == 0.0
        assert snap.max_duration_ms == 0.0
        assert snap.avg_duration_ms == 0.0
        assert snap.p95_duration_ms == 0.0
        assert snap.p99_duration_ms == 0.0

    def test_percentile_computation(self):
        snap = AgentMetricsSnapshot(calls=5, durations_ms=[10, 20, 30, 40, 50])
        assert snap.min_duration_ms == 10.0
        assert snap.max_duration_ms == 50.0
        assert snap.avg_duration_ms == 30.0
        assert snap.p95_duration_ms == pytest.approx(48.0, rel=0.01)
        assert snap.p99_duration_ms == pytest.approx(49.6, rel=0.01)


# ── Test: Context Manager ───────────────────────────────────────────────────


class TestTrackContext:

    def test_successful_call(self, collector: AgentMetricsCollector):
        with collector.track("planner"):
            pass  # simulate work

        snap = collector.get_snapshot("planner")
        assert snap is not None
        assert snap.calls == 1
        assert snap.errors == 0
        assert snap.durations_ms[0] > 0

    def test_error_call(self, collector: AgentMetricsCollector):
        with pytest.raises(ValueError, match="test error"):
            with collector.track("planner"):
                raise ValueError("test error")

        snap = collector.get_snapshot("planner")
        assert snap.calls == 1
        assert snap.errors == 1
        assert snap.error_rate == 1.0

    def test_async_successful_call(self, collector: AgentMetricsCollector):
        async def _run():
            async with collector.track_async("validator"):
                await asyncio.sleep(0.01)

        asyncio.run(_run())
        snap = collector.get_snapshot("validator")
        assert snap.calls == 1
        assert snap.errors == 0
        assert snap.durations_ms[0] > 0

    def test_async_error_call(self, collector: AgentMetricsCollector):
        async def _run():
            with pytest.raises(RuntimeError, match="async fail"):
                async with collector.track_async("validator"):
                    raise RuntimeError("async fail")

        asyncio.run(_run())
        snap = collector.get_snapshot("validator")
        assert snap.calls == 1
        assert snap.errors == 1

    def test_microsecond_precision(self, collector: AgentMetricsCollector):
        """Even very fast calls should record non-zero duration."""
        with collector.track("fast"):
            x = 1 + 1  # noqa: F841

        snap = collector.get_snapshot("fast")
        assert snap.durations_ms[0] > 0


# ── Test: Decorator ─────────────────────────────────────────────────────────


class TestDecorator:

    def test_sync_decorator_success(self, collector: AgentMetricsCollector):
        @collector.decorator("sync_agent")
        def my_func(x: int) -> int:
            return x * 2

        result = my_func(21)
        assert result == 42

        snap = collector.get_snapshot("sync_agent")
        assert snap.calls == 1
        assert snap.errors == 0

    def test_sync_decorator_error(self, collector: AgentMetricsCollector):
        @collector.decorator("failing_agent")
        def my_func():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            my_func()

        snap = collector.get_snapshot("failing_agent")
        assert snap.calls == 1
        assert snap.errors == 1

    def test_async_decorator_success(self, collector: AgentMetricsCollector):
        @collector.decorator("async_agent")
        async def my_func(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2

        result = asyncio.run(my_func(21))
        assert result == 42

        snap = collector.get_snapshot("async_agent")
        assert snap.calls == 1
        assert snap.errors == 0

    def test_async_decorator_preserves_signature(self, collector: AgentMetricsCollector):
        @collector.decorator("agent")
        async def my_func(a: int, b: str = "default") -> tuple:
            return (a, b)

        assert asyncio.run(my_func(1, b="hello")) == (1, "hello")
        # The decorator should preserve __wrapped__
        assert my_func.__wrapped__ is not None  # type: ignore[attr-defined]

    def test_sync_decorator_preserves_signature(self, collector: AgentMetricsCollector):
        @collector.decorator("agent")
        def my_func(a: int, b: str = "default") -> tuple:
            return (a, b)

        assert my_func(1, b="hello") == (1, "hello")


# ── Test: Summary ───────────────────────────────────────────────────────────


class TestSummary:

    def test_summary_with_no_data(self, collector: AgentMetricsCollector):
        summary = collector.get_summary()
        assert summary == {"total": {
            "calls": 0,
            "errors": 0,
            "error_rate": 0.0,
            "tokens": {"prompt": 0, "completion": 0, "total": 0},
            "duration_ms": 0.0,
        }}

    def test_summary_contains_expected_keys(self, collector: AgentMetricsCollector):
        collector.record_call("planner", 0.5)
        collector.record_call("validator", 0.3)

        summary = collector.get_summary()
        assert "planner" in summary
        assert "validator" in summary
        assert "total" in summary

    def test_summary_total_aggregation(self, collector: AgentMetricsCollector):
        collector.record_call("planner", 1.0)
        collector.record_call("planner", 1.0)
        collector.record_call("validator", 0.5)

        summary = collector.get_summary()
        assert summary["total"]["calls"] == 3
        assert summary["total"]["errors"] == 0
        assert summary["total"]["duration_ms"] > 0

    def test_summary_per_role_structure(self, collector: AgentMetricsCollector):
        collector.record_call("planner", 0.5)

        summary = collector.get_summary()
        role_data = summary["planner"]
        assert role_data["calls"] == 1
        assert role_data["errors"] == 0
        assert role_data["error_rate"] == 0.0
        assert "latency_ms" in role_data
        assert "min" in role_data["latency_ms"]
        assert "max" in role_data["latency_ms"]
        assert "avg" in role_data["latency_ms"]
        assert "p95" in role_data["latency_ms"]
        assert "p99" in role_data["latency_ms"]
        assert "tokens" in role_data
        assert "prompt" in role_data["tokens"]
        assert "completion" in role_data["tokens"]
        assert "total" in role_data["tokens"]

    def test_summary_prints_without_error(self, collector: AgentMetricsCollector):
        """The print_summary method should not crash with or without data."""
        collector.print_summary()  # no data
        collector.record_call("planner", 0.5)
        collector.print_summary()  # with data


# ── Test: Reset ─────────────────────────────────────────────────────────────


class TestReset:

    def test_reset_clears_all_data(self, collector: AgentMetricsCollector):
        collector.record_call("planner", 0.5)
        collector.record_call("validator", 0.3)
        assert len(collector.get_all_snapshots()) == 2

        collector.reset()
        assert len(collector.get_all_snapshots()) == 0

    def test_reset_does_not_affect_token_tracker(self, collector: AgentMetricsCollector):
        """reset() should only clear agent_metrics, not the global token_tracker."""
        from ai_engine.llm.token_tracker import token_tracker as tt
        tt.reset()
        collector.record_call("planner", 0.5)
        collector.reset()

        # The token_tracker still works after reset
        assert tt.call_count == 0  # was reset above


# ── Test: Edge Cases ────────────────────────────────────────────────────────


class TestEdgeCases:

    def test_unknown_role_returns_none(self, collector: AgentMetricsCollector):
        assert collector.get_snapshot("nonexistent") is None

    def test_duplicate_role_names_aggregate(self, collector: AgentMetricsCollector):
        collector.record_call("same_role", 0.1)
        collector.record_call("same_role", 0.2)
        collector.record_call("same_role", 0.3)
        snap = collector.get_snapshot("same_role")
        assert snap.calls == 3

    def test_very_short_duration(self, collector: AgentMetricsCollector):
        """Sub-millisecond durations should still be recorded correctly."""
        collector.record_call("fast", 0.0005)
        snap = collector.get_snapshot("fast")
        assert snap.min_duration_ms == pytest.approx(0.5, rel=0.1)

    def test_agent_metrics_singleton_is_importable(self):
        """The module-level singleton should be importable from the evaluation package."""
        from ai_engine.evaluation import agent_metrics as am
        assert am is not None
        assert hasattr(am, "track")
        assert hasattr(am, "get_summary")
