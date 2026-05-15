# RaceGuard 🏁

> An overselling prevention system that **demonstrates and solves race conditions** under high concurrency using six distinct concurrency strategies.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Setup](#setup)
- [Running the Server](#running-the-server)
- [API Endpoints](#api-endpoints)
- [Concurrency Strategies](#concurrency-strategies)
- [Running Tests](#running-tests)
- [Load Testing with Locust](#load-testing-with-locust)
- [Sample Results](#sample-results)
- [Sample curl Commands](#sample-curl-commands)
- [Makefile Targets](#makefile-targets)

---

## Overview

Flash sales create a classic concurrency problem: thousands of users race to buy the last few items simultaneously. Without proper synchronization, a naive system will:

1. Let Thread A read `stock = 1`
2. Let Thread B read `stock = 1` (before A writes)
3. Both decrement → `stock = -1`
4. Both report **success** — item sold **twice** from one unit of stock

RaceGuard benchmarks six concurrency strategies side-by-side through the same `POST /buy?mode=<strategy>` endpoint, making it trivial to observe and compare outcomes.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                      HTTP Clients                          │
│          (curl / Locust / ThreadPoolExecutor tests)        │
└──────────────────────────┬─────────────────────────────────┘
                           │ POST /buy?mode=<strategy>
                           ▼
┌────────────────────────────────────────────────────────────┐
│                    FastAPI  (Uvicorn)                       │
│                       app/main.py                          │
│                                                            │
│   ┌────────────────────────────────────────────────────┐   │
│   │              Strategy Router                       │   │
│   │  mode param → dispatches to correct strategy fn   │   │
│   └──────┬──────┬──────┬──────┬──────┬────────────────┘   │
│          │      │      │      │      │                     │
│        naive  lock  atomic optim queue  redis              │
│          │      │      │      │      │      │              │
│       global threading threading dict  Queue  Redis        │
│        int    Lock    CAS    +ver  Worker  DECR            │
└────────────────────────────────────────────────────────────┘
                                                │
                                    ┌───────────▼───────────┐
                                    │   Redis 7 (Docker)    │
                                    │   stock key (DECR)    │
                                    └───────────────────────┘
```

---

## Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for Redis)

### 1. Clone & create virtual environment

```bash
git clone <repo-url>
cd raceguard

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
# or
make install
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env if needed (defaults work out of the box)
```

### 4. Start Redis via Docker

```bash
docker compose up -d redis
# or
make docker-up
```

---

## Running the Server

```bash
# Development (auto-reload)
uvicorn app.main:app --reload --port 8000
# or
make run

# Production (multi-worker)
make run-prod
```

Server starts at: **http://127.0.0.1:8000**  
Interactive docs: **http://127.0.0.1:8000/docs**

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/buy?mode=<strategy>` | Buy one item using the specified strategy |
| `GET`  | `/stock` | Current stock for all strategies |
| `POST` | `/reset` | Reset all strategies to INITIAL_STOCK |

### Valid `mode` values

`naive` · `lock` · `atomic` · `optimistic` · `redis` · `queue`

---

## Concurrency Strategies

| Strategy | Thread-Safe | Oversell Risk | Throughput | Use Case |
|----------|:-----------:|:-------------:|:----------:|----------|
| **naive** | ❌ No | 🔴 High | 🟢 Highest | Demo / educational only |
| **lock** | ✅ Yes | 🟢 None | 🟡 Medium | Single-server, low contention |
| **atomic** | ✅ Yes | 🟢 None | 🟡 Medium | Single-server CAS pattern |
| **optimistic** | ✅ Yes | 🟢 None* | 🟡 Medium | Low-to-medium contention |
| **redis** | ✅ Yes | 🟢 None | 🟢 High | Distributed / multi-server |
| **queue** | ✅ Yes | 🟢 None | 🔴 Lowest | Max safety, audit-trail systems |

\* Optimistic may fail under very high contention (retries exhausted) but will never oversell.

### Strategy Deep Dive

#### 🔴 naive
Plain global integer, zero synchronization. Classic TOCTOU race condition — exists purely to show what goes wrong without protection.

#### 🔒 lock
`threading.Lock()` wraps the check-and-decrement. Simple, correct, and the go-to solution for single-process servers.

#### ⚛️ atomic
Implements a Compare-and-Swap (CAS) loop in Python. Mirrors the pattern used by `java.util.concurrent.AtomicInteger` and PostgreSQL's `SELECT FOR UPDATE`.

#### 🔄 optimistic
Version-stamped dict: reads are lock-free; commits acquire a brief lock only to check-and-bump the version. Models JPA `@Version` / Hibernate optimistic locking. Retries up to 5× on conflict.

#### 🟥 redis
Delegates to `redis.DECR` — a single atomic Redis command. The only strategy that works correctly across **multiple application servers**. Recommended for production.

#### 📬 queue
Routes all purchases through a single background thread via `queue.Queue`. Eliminates concurrency at the purchase layer entirely. Highest safety, lowest throughput — ideal for financial ledgers.

---

## Running Tests

> **The server must be running** before executing tests.

```bash
# Terminal 1 — start server
make run

# Terminal 2 — run tests
make test
# or
pytest tests/ -v
```

### Test Coverage

| Test | Concurrency | Assertion |
|------|------------|-----------|
| `test_no_oversell_lock` | 100 threads | success == 10, stock == 0 |
| `test_no_oversell_atomic` | 100 threads | success == 10, stock == 0 |
| `test_no_oversell_redis` | 100 threads | success == 10, stock == 0 |
| `test_no_oversell_optimistic` | 50 threads | success <= 10, stock >= 0 |
| `test_naive_may_oversell` | 50 threads | documented only (no assert) |
| `test_queue_sequential` | 30 threads | success <= 10, stock >= 0 |
| `test_reset_restores_all_stocks` | sequential | all stocks == INITIAL_STOCK |

---

## Load Testing with Locust

```bash
# Interactive UI at http://localhost:8089
make load-test

# Headless — 50 users, spawn 10/s, run 30 seconds
make load-test-headless
```

The Locust file defines two tasks:
- **buy** (weight 5): `POST /buy?mode=<random>` across all 6 strategies
- **stock** (weight 1): `GET /stock` to observe live inventory

---

## Sample Results

```
Mode: REDIS
Total Requests: 1000
Success:        10
Failed:         990
Final Stock:    0
Oversell:       false

Mode: NAIVE
Total Requests: 1000
Success:        ~47          ← varies per run (race condition)
Failed:         ~953
Final Stock:    ~-37         ← negative = oversold!
Oversell:       TRUE ⚠️

Mode: LOCK
Total Requests: 1000
Success:        10
Failed:         990
Final Stock:    0
Oversell:       false

Mode: QUEUE
Total Requests: 1000
Success:        10
Failed:         990
Final Stock:    0
Oversell:       false
```

---

## Sample curl Commands

```bash
# Buy with Redis strategy (default)
curl -X POST "http://localhost:8000/buy?mode=redis"

# Buy with lock strategy
curl -X POST "http://localhost:8000/buy?mode=lock"

# Buy with naive strategy (intentional race condition)
curl -X POST "http://localhost:8000/buy?mode=naive"

# Buy with atomic CAS strategy
curl -X POST "http://localhost:8000/buy?mode=atomic"

# Buy with optimistic locking
curl -X POST "http://localhost:8000/buy?mode=optimistic"

# Buy via queue worker
curl -X POST "http://localhost:8000/buy?mode=queue"

# Check all stocks
curl "http://localhost:8000/stock"

# Reset all stocks to INITIAL_STOCK
curl -X POST "http://localhost:8000/reset"
```

### Example Response

```json
{
  "success": true,
  "mode": "redis",
  "remaining_stock": 9
}
```

---

## Makefile Targets

| Target | Command | Description |
|--------|---------|-------------|
| `make run` | `uvicorn app.main:app --reload` | Dev server with hot-reload |
| `make run-prod` | `uvicorn ... --workers 4` | Production multi-worker server |
| `make test` | `pytest tests/ -v` | Run full test suite |
| `make load-test` | `locust -f locustfile.py ...` | Interactive Locust UI |
| `make load-test-headless` | `locust --headless ...` | Headless load test |
| `make reset` | `curl POST /reset` | Reset all stocks via API |
| `make stock` | `curl GET /stock` | Print current stock JSON |
| `make docker-up` | `docker compose up -d redis` | Start Redis container |
| `make docker-down` | `docker compose down` | Stop all containers |
| `make install` | `pip install -r requirements.txt` | Install Python deps |

---

## Project Structure

```
raceguard/
├── app/
│   ├── __init__.py
│   ├── main.py              ← FastAPI app, /buy /stock /reset
│   ├── config.py            ← INITIAL_STOCK, REDIS_URL
│   └── strategies/
│       ├── __init__.py
│       ├── naive.py         ← No sync (race condition demo)
│       ├── lock.py          ← threading.Lock
│       ├── atomic.py        ← Compare-and-Swap loop
│       ├── optimistic.py    ← Versioned optimistic locking
│       ├── redis_atomic.py  ← Redis DECR (distributed-safe)
│       └── queue_strategy.py← Single-worker queue
├── tests/
│   └── test_concurrent.py  ← ThreadPoolExecutor concurrent tests
├── locustfile.py            ← Locust load test
├── docker-compose.yml       ← Redis service
├── Makefile                 ← Convenience targets
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## License

MIT — free to use, modify, and distribute.
