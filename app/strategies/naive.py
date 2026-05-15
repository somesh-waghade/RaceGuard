"""
naive.py — Naive (unsynchronized) purchase strategy.

Deliberately has NO thread synchronization to demonstrate the classic
check-then-act race condition that causes overselling.

THIS STRATEGY WILL OVERSELL UNDER CONCURRENCY. It exists only to
illustrate the problem RaceGuard is designed to prevent.
"""

from app.config import INITIAL_STOCK

# Global stock counter — no lock protection whatsoever
naive_stock: int = INITIAL_STOCK


def buy_naive() -> tuple[bool, int]:
    """
    Attempt to purchase one item with no synchronization.

    Susceptible to TOCTOU (time-of-check-time-of-use) race conditions:
    two threads can both read stock > 0, both decrement, resulting in
    stock going negative (overselling).

    Returns:
        (success, remaining_stock): success is True if purchase
        was logically attempted (stock > 0 at read time).
    """
    global naive_stock

    # --- RACE WINDOW STARTS HERE ---
    if naive_stock > 0:          # Thread A and Thread B both read 1
        naive_stock -= 1         # Both decrement → stock becomes -1
        return True, naive_stock  # Both report success!
    # --- RACE WINDOW ENDS HERE ---

    return False, naive_stock


def reset_naive() -> None:
    """Reset naive stock to INITIAL_STOCK."""
    global naive_stock
    naive_stock = INITIAL_STOCK


def get_naive_stock() -> int:
    """Return current naive stock value."""
    return naive_stock
