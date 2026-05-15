"""
atomic.py — Atomic Compare-and-Swap (CAS) purchase strategy.

Simulates a hardware CAS instruction in Python using a threading.Lock
to implement a strictly atomic read-modify-write pattern. The lock is
held only for the duration of the CAS check+swap — no I/O or sleeping
occurs inside the critical section, making this suitable as a model for
lock-free-style programming in Python.

This is functionally equivalent to lock.py but structured to mirror
CAS semantics used in databases (e.g., UPDATE ... WHERE version = ?).
"""

import threading
from app.config import INITIAL_STOCK

# Internal mutable state — never touch directly outside CAS helper
_atomic_stock: int = INITIAL_STOCK
_cas_lock: threading.Lock = threading.Lock()


def _compare_and_swap(expected: int, new_value: int) -> bool:
    """
    Atomically swap _atomic_stock to new_value only if it equals expected.

    Args:
        expected: The value we expect _atomic_stock to currently hold.
        new_value: The value to write if the expectation holds.

    Returns:
        True if the swap succeeded, False if the value had changed.
    """
    global _atomic_stock
    with _cas_lock:
        if _atomic_stock == expected:
            _atomic_stock = new_value
            return True
        return False


def buy_atomic() -> tuple[bool, int]:
    """
    Attempt to purchase one item via a CAS loop.

    Reads the current stock, computes the desired new value (stock - 1),
    then issues a CAS. If another thread modified stock between our read
    and our CAS, the CAS fails and we retry automatically.

    Returns:
        (success, remaining_stock): success is True if stock was > 0
        and CAS succeeded.
    """
    global _atomic_stock

    while True:
        # Snapshot current value (outside the lock — cheap read)
        current = _atomic_stock

        if current <= 0:
            return False, current

        # Attempt CAS: only succeeds if nobody changed current meanwhile
        if _compare_and_swap(current, current - 1):
            return True, current - 1
        # CAS failed → another thread raced us, retry with fresh snapshot


def reset_atomic() -> None:
    """Reset atomic stock to INITIAL_STOCK."""
    global _atomic_stock
    with _cas_lock:
        _atomic_stock = INITIAL_STOCK


def get_atomic_stock() -> int:
    """Return current atomic stock value."""
    with _cas_lock:
        return _atomic_stock
