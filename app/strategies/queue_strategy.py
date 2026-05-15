"""
queue_strategy.py — Single-worker queue-based purchase strategy.

Serializes ALL purchase requests through a single background worker thread.
This eliminates concurrency at the purchase level entirely — no two purchases
ever execute simultaneously. The trade-off is throughput: latency per request
increases proportionally with queue depth.

Architectural pattern: "Actor model" / "Single-writer principle".
Use cases: financial ledgers, sequential ticket issuance, audit logs.

The worker thread is started lazily on first import and runs as a daemon
so it does not prevent process shutdown.
"""

import queue
import threading
import logging
from app.config import INITIAL_STOCK

logger = logging.getLogger(__name__)

WORKER_TIMEOUT: float = 5.0  # seconds to wait for a result before giving up

# Internal queue: items are (event, result_container) tuples
_task_queue: queue.Queue = queue.Queue()
_queue_stock: int = INITIAL_STOCK
_worker_thread: threading.Thread | None = None
_worker_lock: threading.Lock = threading.Lock()  # protects worker startup


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def _worker() -> None:
    """
    Dedicated worker thread — processes purchase tasks one at a time.

    Reads tasks from _task_queue, performs the stock check-and-decrement,
    writes the result into the task's result container, then signals the
    waiting caller via threading.Event.
    """
    global _queue_stock
    logger.info("QueueStrategy worker thread started.")

    while True:
        try:
            event: threading.Event
            result: list
            event, result = _task_queue.get(timeout=1.0)
        except queue.Empty:
            continue

        # --- Sequential purchase logic (no concurrent access possible) ---
        if _queue_stock > 0:
            _queue_stock -= 1
            result.append((True, _queue_stock))
        else:
            result.append((False, _queue_stock))

        event.set()          # Unblock the waiting HTTP handler thread
        _task_queue.task_done()


def _ensure_worker() -> None:
    """Start the worker thread exactly once (thread-safe)."""
    global _worker_thread
    with _worker_lock:
        if _worker_thread is None or not _worker_thread.is_alive():
            _worker_thread = threading.Thread(
                target=_worker, daemon=True, name="queue-strategy-worker"
            )
            _worker_thread.start()


# Start worker on module import
_ensure_worker()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def buy_queue() -> tuple[bool, int]:
    """
    Attempt to purchase one item via the single-worker queue.

    Enqueues a task for the background worker and blocks (up to
    WORKER_TIMEOUT seconds) until the worker processes it.

    Returns:
        (success, remaining_stock): success is True if stock was
        available. Returns (False, -1) on timeout.
    """
    _ensure_worker()

    event: threading.Event = threading.Event()
    result: list = []

    _task_queue.put((event, result))

    signaled = event.wait(timeout=WORKER_TIMEOUT)
    if not signaled:
        logger.warning("buy_queue: worker did not respond within %.1fs", WORKER_TIMEOUT)
        return False, -1

    return result[0]


def reset_queue() -> None:
    """Reset the queue-managed stock to INITIAL_STOCK."""
    global _queue_stock

    # Drain any pending tasks first to avoid stale completions
    while not _task_queue.empty():
        try:
            _task_queue.get_nowait()
            _task_queue.task_done()
        except queue.Empty:
            break

    _queue_stock = INITIAL_STOCK
    _ensure_worker()


def get_queue_stock() -> int:
    """Return current queue-managed stock value."""
    return _queue_stock
