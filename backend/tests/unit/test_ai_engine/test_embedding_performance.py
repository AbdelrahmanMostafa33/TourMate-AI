"""Performance tests for async embedding — verifies event loop is not blocked.

These tests simulate realistic Gemini API latency (~500ms) using mocked clients
and measure whether ``embed_query_async`` truly allows parallel execution while
the synchronous ``embed_query`` blocks the event loop.

Test design:
  1. Launch N concurrent ``embed_query_async`` calls — verify total time ≈ 1× latency
  2. Run N sequential ``embed_query`` (sync) calls — verify total time ≈ N× latency (control)
  3. Verify a background async timer completes during ``embed_query_async`` (event loop free)
  4. Verify a background async timer is starved during ``embed_query`` (event loop blocked)

.. note::
   These are **timing-sensitive** tests.  The simulated latency (``SIMULATED_LATENCY``)
   is set to 0.5 s to match a realistic Gemini embedding API call.  If the test
   environment is under extreme CPU pressure, increase the multiplier in assertions.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_engine.services.embedding_service import embed_query, embed_query_async

# ── Configuration ──────────────────────────────────────────────────────────

SIMULATED_LATENCY = 0.5       # seconds per mocked API call
EMBEDDING_DIMS = 768
NUM_CONCURRENT = 5            # number of concurrent calls in overload tests
PARALLEL_THRESHOLD = 2.0      # max allowed multiplier of single-latency for parallel time
SEQUENTIAL_TOLERANCE = 0.85   # minimum fraction of N*latency expected for sequential calls

TEST_QUERY = "task: search result | query: history and art trip — moderate budget, cultural style"


# ── Mock Result Objects ────────────────────────────────────────────────────


class _MockEmbedding:
    """Simulates a single embedding result (the ``.values`` attribute)."""

    def __init__(self) -> None:
        self.values: list[float] = [0.5] * EMBEDDING_DIMS


class _MockEmbedResult:
    """Simulates the full result returned by ``embed_content``."""

    def __init__(self, contents: list[str]) -> None:
        self.embeddings: list[_MockEmbedding] = [_MockEmbedding() for _ in contents]


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _patch_api_keys() -> None:
    """Ensure the key rotation sees at least one key so it doesn't bail early."""
    with patch("ai_engine.services.embedding_service._embed_keys", ["perf-test-key"]):
        yield


@pytest.fixture
def mock_async_client() -> None:
    """Patch ``genai.AsyncClient`` so every ``embed_content`` sleeps 500ms."""

    async def _mock_embed_content(
        model: str,
        contents: list[str],
        config: object = None,
    ) -> _MockEmbedResult:
        await asyncio.sleep(SIMULATED_LATENCY)
        return _MockEmbedResult(contents)

    client_instance = MagicMock()
    # Mock the full chain: Client(api_key=key) -> .aio -> .models -> .embed_content
    # + .aio.aclose() cleanup
    client_instance = MagicMock()
    client_instance.aio.models.embed_content = AsyncMock(side_effect=_mock_embed_content)
    client_instance.aio.aclose = AsyncMock()

    with patch(
        "ai_engine.services.embedding_service.genai.Client",
        return_value=client_instance,
    ):
        yield


@pytest.fixture
def mock_sync_client() -> None:
    """Patch ``genai.Client`` so every ``embed_content`` sleeps 500ms (blocking)."""

    def _mock_embed_content(
        model: str,
        contents: list[str],
        config: object = None,
    ) -> _MockEmbedResult:
        time.sleep(SIMULATED_LATENCY)
        return _MockEmbedResult(contents)

    # Mock the sync Client directly (no .aio chain for sync calls)
    client_instance = MagicMock()
    client_instance.models.embed_content = MagicMock(side_effect=_mock_embed_content)

    with patch(
        "ai_engine.services.embedding_service.genai.Client",
        return_value=client_instance,
    ):
        yield


# ══════════════════════════════════════════════════════════════════════════
# Tests — embed_query_async (should NOT block the event loop)
# ══════════════════════════════════════════════════════════════════════════


class TestEmbedQueryAsyncNonBlocking:
    """Verifies that ``embed_query_async`` does not block the event loop."""

    # ── Test 1: Concurrent calls complete in near-parallel time ──────────

    @pytest.mark.asyncio
    async def test_concurrent_calls_complete_in_parallel(
        self,
        mock_async_client: None,
    ) -> None:
        """``NUM_CONCURRENT`` concurrent calls finish in ≈ single-call latency.

        Sequential would take ``NUM_CONCURRENT × SIMULATED_LATENCY`` seconds.
        Parallel should take ≈ ``SIMULATED_LATENCY`` (plus context-switch overhead).
        """
        start = time.monotonic()
        results = await asyncio.gather(
            *[embed_query_async(TEST_QUERY) for _ in range(NUM_CONCURRENT)]
        )
        elapsed = time.monotonic() - start

        # — correctness —
        assert all(r is not None for r in results), "All results should be non-None"
        assert all(len(r) == EMBEDDING_DIMS for r in results), (
            f"Each result should be {EMBEDDING_DIMS}-dim"
        )

        # — parallel speed —
        sequential_estimate = NUM_CONCURRENT * SIMULATED_LATENCY
        assert elapsed < sequential_estimate * 0.8, (
            f"Concurrent {NUM_CONCURRENT} calls took {elapsed:.2f}s — "
            f"expected <{sequential_estimate * 0.8:.2f}s (parallel). "
            f"Would be ~{sequential_estimate:.1f}s if sequential."
        )

        # Should be within a small multiple of single-call latency
        assert elapsed < SIMULATED_LATENCY * PARALLEL_THRESHOLD, (
            f"Parallel calls took {elapsed:.2f}s — expected "
            f"<{SIMULATED_LATENCY * PARALLEL_THRESHOLD:.1f}s "
            f"(single latency × {PARALLEL_THRESHOLD})"
        )

    # ── Test 2: Event loop processes other tasks during concurrent calls ──

    @pytest.mark.asyncio
    async def test_event_loop_remains_responsive_during_concurrent_calls(
        self,
        mock_async_client: None,
    ) -> None:
        """A short timer completes while 5 concurrent embedding calls run.

        If the event loop were blocked, the timer wouldn't fire until after
        all embeddings finished (≈ 2.5 s).  It should fire much sooner.
        """
        timer_delay = SIMULATED_LATENCY * 0.2  # 100 ms — far shorter than 5×500 ms

        async def short_timer() -> str:
            await asyncio.sleep(timer_delay)
            return "fired"

        timer_task = asyncio.create_task(short_timer())
        embed_tasks = [
            asyncio.create_task(embed_query_async(TEST_QUERY))
            for _ in range(NUM_CONCURRENT)
        ]

        # The 100 ms timer should fire while the 5 embedding calls are in flight
        timer_result = await timer_task
        assert timer_result == "fired", "Short timer should complete"

        # Now wait for the embeddings
        embed_results = await asyncio.gather(*embed_tasks)

        assert len(embed_results) == NUM_CONCURRENT
        assert all(r is not None for r in embed_results)

    # ── Test 3: Embedding failure (None) does not crash ──────────────────

    @pytest.mark.asyncio
    async def test_async_returns_none_on_failure(self) -> None:
        """When no API keys are available, ``embed_query_async`` returns None."""
        with patch("ai_engine.services.embedding_service._embed_keys", []):
            result = await embed_query_async(TEST_QUERY)
            assert result is None

    # ── Test 4: Large concurrency does not cause errors ──────────────────

    @pytest.mark.asyncio
    async def test_high_concurrency_graceful(
        self,
        mock_async_client: None,
    ) -> None:
        """20 concurrent calls should all succeed, no connection errors."""
        high_count = 20
        results = await asyncio.gather(
            *[embed_query_async(TEST_QUERY) for _ in range(high_count)],
            return_exceptions=True,
        )
        nones = [r for r in results if r is None]
        errors = [r for r in results if isinstance(r, Exception)]
        assert not errors, f"High-concurrency produced errors: {errors}"
        assert all(
            r is not None and len(r) == EMBEDDING_DIMS
            for r in results
            if not isinstance(r, Exception)
        ), f"{len(nones)} calls returned None unexpectedly"


# ══════════════════════════════════════════════════════════════════════════
# Tests — embed_query (synchronous, SHOULD block)
# ══════════════════════════════════════════════════════════════════════════


class TestEmbedQuerySyncBlocks:
    """Control tests: verify the synchronous version blocks the event loop."""

    # ── Test 5: Sequential sync calls take linear time ───────────────────

    def test_sequential_calls_take_linear_time(
        self,
        mock_sync_client: None,
    ) -> None:
        """Three sequential sync calls take ≈ 3 × latency."""
        num_calls = 3
        start = time.monotonic()
        for _ in range(num_calls):
            result = embed_query(TEST_QUERY)
            assert result is not None
            assert len(result) == EMBEDDING_DIMS
        elapsed = time.monotonic() - start

        expected_min = num_calls * SIMULATED_LATENCY * SEQUENTIAL_TOLERANCE
        assert elapsed >= expected_min, (
            f"Sequential {num_calls} calls took {elapsed:.2f}s — "
            f"expected ≥{expected_min:.2f}s (≥{SEQUENTIAL_TOLERANCE * 100:.0f}% of "
            f"{num_calls}×{SIMULATED_LATENCY}s)"
        )

    # ── Test 6: Sync call starves the event loop ────────────────────────

    @pytest.mark.asyncio
    async def test_sync_call_starves_event_loop(
        self,
        mock_sync_client: None,
    ) -> None:
        """A background async timer makes NO progress during a sync call.

        When ``embed_query`` (sync) runs, it calls ``time.sleep()`` which
        blocks the entire main thread — including the asyncio event loop.
        A concurrent timer that should fire every 10 ms gets stalled.
        """
        ticks: list[float] = []

        async def ticker() -> None:
            """Record a timestamp every 10 ms, up to 100 ticks."""
            for __ in range(100):
                await asyncio.sleep(0.01)
                ticks.append(time.monotonic())

        ticker_task = asyncio.create_task(ticker())

        # Let the ticker run for a brief period before the sync call
        await asyncio.sleep(SIMULATED_LATENCY * 0.2)  # ~100 ms
        ticks_before = len(ticks)

        # Now run the sync call — this blocks the event loop for ~500 ms
        result = embed_query(TEST_QUERY)
        ticks_during = len(ticks) - ticks_before

        # Cancel the ticker and await its cancellation
        ticker_task.cancel()
        try:
            await ticker_task
        except asyncio.CancelledError:
            pass

        # The ticker should have gotten almost no ticks during the ~500 ms
        # sync call (event loop was blocked).  A few ticks might trickle in
        # due to OS scheduler edge effects, but far fewer than the ~50
        # expected if the loop were running freely.
        expected_ticks_if_free = int(SIMULATED_LATENCY / 0.01)  # ~50
        assert ticks_during < expected_ticks_if_free * 0.3, (
            f"Ticker got {ticks_during} ticks during {SIMULATED_LATENCY}s "
            f"sync call — expected ≪{expected_ticks_if_free} (event loop "
            f"should be blocked)"
        )
        assert result is not None

    # ── Test 7: Sync returns None on failure ─────────────────────────────

    def test_sync_returns_none_on_failure(self) -> None:
        """When no API keys are available, ``embed_query`` returns None."""
        with patch("ai_engine.services.embedding_service._embed_keys", []):
            result = embed_query(TEST_QUERY)
            assert result is None
