"""
redis_atomic.py — Atomic Redis-based purchase strategy.

Delegates the check-and-decrement to Redis using the DECR command, which
is guaranteed atomic by Redis's single-threaded command processing model.
No in-process locking is required — Redis serializes all DECR calls itself.

This is the recommended strategy for distributed systems where multiple
application servers share a single Redis instance.

Requires: a running Redis server (see docker-compose.yml).
"""

import logging
import redis
from app.config import REDIS_URL, INITIAL_STOCK

logger = logging.getLogger(__name__)

STOCK_KEY: str = "stock"

# Module-level Redis client (connection pooled by default in redis-py)
try:
    _r: redis.Redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    _r.ping()
    logger.info("Redis connection established at %s", REDIS_URL)
except redis.exceptions.ConnectionError as exc:
    logger.warning("Redis unavailable at startup: %s", exc)
    _r = None  # type: ignore[assignment]


def _get_client() -> redis.Redis | None:
    """Return the Redis client, or None if unavailable."""
    return _r


def seed_redis(stock: int = INITIAL_STOCK) -> None:
    """
    (Re)seed the Redis stock key to the given value.

    Called on app startup and by the /reset endpoint.

    Args:
        stock: Value to write to the Redis stock key.
    """
    client = _get_client()
    if client is None:
        logger.error("Cannot seed Redis — connection unavailable.")
        return
    client.set(STOCK_KEY, stock)
    logger.info("Redis stock seeded to %d", stock)


def buy_redis() -> tuple[bool, int]:
    """
    Attempt to purchase one item via Redis atomic DECR.

    DECR is a single Redis command, fully atomic — no race window exists.
    If the resulting value is negative the decrement is rolled back with
    INCR so Redis stock never goes below 0.

    Returns:
        (success, remaining_stock): success is True if DECR produced >= 0.
        Returns (False, -1) if Redis is unavailable.
    """
    client = _get_client()
    if client is None:
        logger.error("buy_redis: Redis connection unavailable — skipping purchase.")
        return False, -1

    try:
        new_value: int = client.decr(STOCK_KEY)

        if new_value < 0:
            # Undo the phantom decrement — restore the floor at 0
            client.incr(STOCK_KEY)
            return False, 0

        return True, new_value

    except redis.exceptions.ConnectionError as exc:
        logger.error("buy_redis: Redis connection error during DECR: %s", exc)
        return False, -1


def get_redis_stock() -> int:
    """
    Return the current Redis stock as an integer.

    Returns:
        Current stock value, or -1 if Redis is unavailable.
    """
    client = _get_client()
    if client is None:
        return -1
    try:
        value = client.get(STOCK_KEY)
        return int(value) if value is not None else INITIAL_STOCK
    except redis.exceptions.ConnectionError:
        return -1
