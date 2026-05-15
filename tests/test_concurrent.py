"""
test_concurrent.py — Concurrent purchase tests for RaceGuard.

Fires many parallel requests at the running server to verify that each
concurrency strategy behaves correctly under load. Uses ThreadPoolExecutor
for true concurrent HTTP requests.

Run with:
    pytest tests/test_concurrent.py -v

Requirements:
    - Server must be running: uvicorn app.main:app --port 8000
"""

import pytest
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://127.0.0.1:8000"
INITIAL_STOCK = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def reset_server() -> None:
    """Call /reset before each test to guarantee a clean slate."""
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        resp = client.post("/reset")
        assert resp.status_code == 200, f"Reset failed: {resp.text}"


def fire_concurrent_buys(mode: str, n: int) -> list[dict]:
    """
    Fire n concurrent POST /buy?mode=<mode> requests.

    Returns:
        List of response JSON dicts from all requests.
    """
    results: list[dict] = []

    def _buy(_: int) -> dict:
        with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
            r = client.post("/buy", params={"mode": mode})
            return r.json()

    with ThreadPoolExecutor(max_workers=n) as executor:
        futures = [executor.submit(_buy, i) for i in range(n)]
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({"success": False, "remaining_stock": -999, "error": str(exc)})

    return results


def get_stock(mode: str) -> int:
    """Fetch the stock for a single strategy from /stock."""
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        resp = client.get("/stock")
        data = resp.json()
        return data[mode]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLockStrategy:
    """Lock strategy must NEVER allow overselling."""

    def test_no_oversell_lock(self) -> None:
        """100 concurrent lock-mode buys → success count == 10, stock == 0."""
        reset_server()
        results = fire_concurrent_buys("lock", 100)

        successes = [r for r in results if r.get("success") is True]
        failures  = [r for r in results if r.get("success") is False]
        final_stock = get_stock("lock")

        print(f"\n[lock] success={len(successes)}, fail={len(failures)}, final={final_stock}")

        assert len(successes) == INITIAL_STOCK, (
            f"Expected exactly {INITIAL_STOCK} successes, got {len(successes)}"
        )
        assert final_stock == 0, f"Expected final stock 0, got {final_stock}"
        assert final_stock >= 0, "OVERSELL DETECTED — stock went negative!"

        # No individual remaining_stock should be negative
        for r in results:
            assert r.get("remaining_stock", 0) >= 0, f"Negative stock in response: {r}"


class TestAtomicStrategy:
    """Atomic CAS strategy must also prevent overselling."""

    def test_no_oversell_atomic(self) -> None:
        """100 concurrent atomic-mode buys → success count == 10, stock == 0."""
        reset_server()
        results = fire_concurrent_buys("atomic", 100)

        successes = [r for r in results if r.get("success") is True]
        final_stock = get_stock("atomic")

        print(f"\n[atomic] success={len(successes)}, final={final_stock}")

        assert len(successes) == INITIAL_STOCK
        assert final_stock == 0
        assert final_stock >= 0


class TestRedisStrategy:
    """Redis DECR strategy must NEVER allow overselling."""

    def test_no_oversell_redis(self) -> None:
        """100 concurrent redis-mode buys → success count == 10, stock == 0."""
        reset_server()
        results = fire_concurrent_buys("redis", 100)

        successes = [r for r in results if r.get("success") is True]
        failures  = [r for r in results if r.get("success") is False]
        final_stock = get_stock("redis")

        print(f"\n[redis] success={len(successes)}, fail={len(failures)}, final={final_stock}")

        assert len(successes) == INITIAL_STOCK, (
            f"Expected exactly {INITIAL_STOCK} successes, got {len(successes)}"
        )
        assert final_stock == 0
        assert final_stock >= 0


class TestOptimisticStrategy:
    """Optimistic locking should prevent overselling (with retries)."""

    def test_no_oversell_optimistic(self) -> None:
        """50 concurrent optimistic-mode buys → success count <= 10, no negative stock."""
        reset_server()
        results = fire_concurrent_buys("optimistic", 50)

        successes = [r for r in results if r.get("success") is True]
        final_stock = get_stock("optimistic")

        print(f"\n[optimistic] success={len(successes)}, final={final_stock}")

        assert len(successes) <= INITIAL_STOCK
        assert final_stock >= 0


class TestNaiveStrategy:
    """
    Naive strategy WILL oversell under concurrency.

    This test DOCUMENTS the race condition rather than asserting correctness.
    It passes regardless of outcome — the output shows the oversell behavior.
    """

    def test_naive_may_oversell(self) -> None:
        """50 concurrent naive-mode buys — overselling is expected and documented."""
        reset_server()
        results = fire_concurrent_buys("naive", 50)

        successes = [r for r in results if r.get("success") is True]
        final_stock = get_stock("naive")
        oversold = final_stock < 0 or len(successes) > INITIAL_STOCK

        print(f"\n[naive] success={len(successes)}, final={final_stock}, oversold={oversold}")
        print("  ⚠️  Naive strategy intentionally has no protection against overselling.")
        print(f"  ⚠️  Expected oversell: up to {len(successes) - INITIAL_STOCK} units over-sold.")

        # We intentionally do NOT assert correctness here — race condition is the point
        assert True, "Naive strategy documented — no assertion on correctness."


class TestQueueStrategy:
    """Queue strategy serialises all buys — must never oversell."""

    def test_queue_sequential(self) -> None:
        """30 concurrent queue-mode buys → success count <= 10, no negative stock."""
        reset_server()
        results = fire_concurrent_buys("queue", 30)

        successes = [r for r in results if r.get("success") is True]
        failures  = [r for r in results if r.get("success") is False]
        final_stock = get_stock("queue")

        print(f"\n[queue] success={len(successes)}, fail={len(failures)}, final={final_stock}")

        assert len(successes) <= INITIAL_STOCK, (
            f"Queue strategy oversold! {len(successes)} successes for stock of {INITIAL_STOCK}"
        )
        assert final_stock >= 0, "OVERSELL DETECTED in queue strategy — stock went negative!"


class TestResetEndpoint:
    """Verify that /reset correctly restores all stocks."""

    def test_reset_restores_all_stocks(self) -> None:
        """After buying some items and resetting, all stocks return to INITIAL_STOCK."""
        # Drain some stock first
        fire_concurrent_buys("lock", 5)
        fire_concurrent_buys("redis", 5)

        reset_server()

        with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
            resp = client.get("/stock")
            data = resp.json()

        for strategy in ("lock", "atomic", "optimistic", "queue"):
            assert data[strategy] == INITIAL_STOCK, (
                f"{strategy} stock after reset: expected {INITIAL_STOCK}, got {data[strategy]}"
            )
        # Redis may return INITIAL_STOCK or slightly different if unavailable
        assert data["redis"] in (INITIAL_STOCK, -1)
