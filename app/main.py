"""
main.py — RaceGuard FastAPI application entry point.

Exposes three endpoints:
  POST /buy?mode=<strategy>  — attempt to buy one item
  GET  /stock                — current stock for all strategies
  POST /reset                — reset all strategies to INITIAL_STOCK
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from app.config import INITIAL_STOCK
from app.strategies.naive import buy_naive, reset_naive, get_naive_stock
from app.strategies.lock import buy_lock, reset_lock, get_lock_stock
from app.strategies.atomic import buy_atomic, reset_atomic, get_atomic_stock
from app.strategies.optimistic import buy_optimistic, reset_optimistic, get_optimistic_stock
from app.strategies.redis_atomic import buy_redis, seed_redis, get_redis_stock
from app.strategies.queue_strategy import buy_queue, reset_queue, get_queue_stock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------

STRATEGIES: dict = {
    "naive":      buy_naive,
    "lock":       buy_lock,
    "atomic":     buy_atomic,
    "optimistic": buy_optimistic,
    "redis":      buy_redis,
    "queue":      buy_queue,
}

VALID_MODES = set(STRATEGIES.keys())


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Seed all in-memory and Redis stocks on startup."""
    logger.info("RaceGuard starting up — seeding all stocks to %d", INITIAL_STOCK)
    reset_naive()
    reset_lock()
    reset_atomic()
    reset_optimistic()
    reset_queue()
    seed_redis(INITIAL_STOCK)
    yield
    logger.info("RaceGuard shutting down.")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RaceGuard",
    description=(
        "Flash-sale inventory management API that demonstrates and prevents "
        "race conditions under high concurrency."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/buy")
def buy_item(
    mode: str = Query(default="redis", description="Concurrency strategy to use"),
) -> JSONResponse:
    """
    Attempt to purchase one item using the specified concurrency strategy.

    Query params:
        mode: one of naive | lock | atomic | optimistic | redis | queue

    Returns:
        JSON with success flag, mode used, and remaining stock.
    """
    if mode not in VALID_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown mode '{mode}'. Valid modes: {sorted(VALID_MODES)}",
        )

    strategy_fn = STRATEGIES[mode]
    success, remaining_stock = strategy_fn()

    return JSONResponse(
        content={
            "success": success,
            "mode": mode,
            "remaining_stock": remaining_stock,
        }
    )


@app.get("/stock")
def get_stock() -> JSONResponse:
    """
    Return current stock values for all concurrency strategies.

    Returns:
        JSON dict mapping each strategy name to its current stock level.
    """
    return JSONResponse(
        content={
            "naive":      get_naive_stock(),
            "lock":       get_lock_stock(),
            "atomic":     get_atomic_stock(),
            "optimistic": get_optimistic_stock(),
            "redis":      get_redis_stock(),
            "queue":      get_queue_stock(),
            "initial_stock": INITIAL_STOCK,
        }
    )


@app.post("/reset")
def reset_all() -> JSONResponse:
    """
    Reset all strategy stocks back to INITIAL_STOCK.

    Useful between load-test runs. Also reseeds Redis.

    Returns:
        Confirmation JSON with reset stock value.
    """
    reset_naive()
    reset_lock()
    reset_atomic()
    reset_optimistic()
    reset_queue()
    seed_redis(INITIAL_STOCK)

    logger.info("All stocks reset to %d", INITIAL_STOCK)
    return JSONResponse(
        content={
            "reset": True,
            "initial_stock": INITIAL_STOCK,
            "strategies": list(VALID_MODES),
        }
    )
