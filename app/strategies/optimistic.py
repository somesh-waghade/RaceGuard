"""
optimistic.py — Optimistic concurrency control purchase strategy.

Models the Optimistic Locking pattern used in databases (e.g., JPA/Hibernate
@Version, SQL "UPDATE ... WHERE version = ?"). Instead of blocking threads
with a lock upfront, threads read the current state freely, compute the
desired change, then commit ONLY if the state hasn't changed underneath them.

Conflict → retry (up to MAX_RETRIES times) before giving up.

Good for low-contention workloads; degrades under heavy contention due to
repeated retries.
"""

import threading
from app.config import INITIAL_STOCK

MAX_RETRIES: int = 5

# Shared state — a version-stamped record
_state: dict = {"version": 0, "stock": INITIAL_STOCK}
_commit_lock: threading.Lock = threading.Lock()


def buy_optimistic() -> tuple[bool, int]:
    """
    Attempt to purchase one item using optimistic concurrency control.

    Algorithm per attempt:
      1. Read current (version, stock) snapshot — no lock held.
      2. If stock == 0, fail immediately.
      3. Acquire lock only for the tiny commit window.
      4. If version still matches snapshot → commit (decrement stock,
         bump version), release lock, return success.
      5. If version changed → another thread committed first; release
         lock and retry from step 1.

    Returns:
        (success, remaining_stock): success is True if a commit landed
        within MAX_RETRIES attempts.
    """
    for attempt in range(MAX_RETRIES):
        # --- Optimistic read (lock-free) ---
        snap_version: int = _state["version"]
        snap_stock: int = _state["stock"]

        if snap_stock <= 0:
            return False, snap_stock

        # --- Commit window (brief lock) ---
        with _commit_lock:
            if _state["version"] == snap_version:  # No one else committed
                _state["stock"] -= 1
                _state["version"] += 1
                return True, _state["stock"]
            # Version mismatch → conflict detected, will retry

    # Exhausted retries under heavy contention
    return False, _state["stock"]


def reset_optimistic() -> None:
    """Reset optimistic state to INITIAL_STOCK with version 0."""
    with _commit_lock:
        _state["version"] = 0
        _state["stock"] = INITIAL_STOCK


def get_optimistic_stock() -> int:
    """Return current optimistic stock value."""
    return _state["stock"]
