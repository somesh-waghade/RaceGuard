"""
lock.py — Thread-safe purchase strategy using a threading.Lock.

Uses Python's threading.Lock as a mutex around the critical section
(check-and-decrement). Guarantees exactly INITIAL_STOCK successful
purchases, no matter how many concurrent threads compete.

Trade-off: Serializes all purchases — only one thread can be inside the
critical section at any moment. Safe, but limits throughput under extreme
concurrency.
"""

import threading
from app.config import INITIAL_STOCK

lock_stock: int = INITIAL_STOCK
_lock: threading.Lock = threading.Lock()


def buy_lock() -> tuple[bool, int]:
    """
    Attempt to purchase one item using a threading.Lock.

    Acquires the global lock before the check-and-decrement operation,
    ensuring atomicity. No two threads can race on the critical section.

    Returns:
        (success, remaining_stock): success is True if stock was
        available and decremented successfully.
    """
    global lock_stock

    with _lock:
        if lock_stock > 0:
            lock_stock -= 1
            return True, lock_stock
        return False, lock_stock


def reset_lock() -> None:
    """Reset lock-protected stock to INITIAL_STOCK (acquires lock)."""
    global lock_stock
    with _lock:
        lock_stock = INITIAL_STOCK


def get_lock_stock() -> int:
    """Return current lock-protected stock value."""
    with _lock:
        return lock_stock
