# RaceGuard 🏁

> An overselling prevention system that **demonstrates and solves race conditions** under high concurrency using six distinct concurrency strategies — with a **real-time live dashboard** to watch them race.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Setup](#setup)
- [Running the Server](#running-the-server)
- [API Endpoints](#api-endpoints)
- [Concurrency Strategies](#concurrency-strategies)
- [Live Dashboard](#live-dashboard)
- [Running Tests](#running-tests)
- [Load Testing with Locust](#load-testing-with-locust)
- [Sample Results](#sample-results)
- [Sample curl Commands](#sample-curl-commands)
- [Makefile Targets](#makefile-targets)
- [Project Structure](#project-structure)

---

## Overview

Flash sales create a classic concurrency problem: thousands of users race to buy the last few items simultaneously. Without proper synchronisation, a naive system will:

1. Let Thread A read `stock = 1`
2. Let Thread B read `stock = 1` (before A writes)
3. Both decrement → `stock = -1`
4. Both report **success** — item sold **twice** from one unit of stock

RaceGuard benchmarks six concurrency strategies side-by-side through the same `POST /buy?mode=<strategy>` endpoint, making it trivial to observe and compare outcomes — including via a **live browser dashboard** that updates every second.

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
                                    
┌────────────────────────────────────────────────────────────┐
│               Locust Web UI  (Flask, port 8089)            │
│                                                            │
│   /dashboard        ← Premium real-time GUI dashboard      │
│   /live_stats       ← JSON feed polled every 1 s           │
│   /reset_live_stocks← One-click reset from dashboard       │
└────────────────────────────────────────────────────────────┘
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
python -m uvicorn app.main:app --reload --port 8000
# or
make run

# Production (multi-worker)
make run-prod
```

Server starts at: **http://127.0.0.1:8000**  
Interactive API docs: **http://127.0.0.1:8000/docs**

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
Plain global integer, zero synchronisation. Classic TOCTOU race condition — exists purely to show what goes wrong without protection.

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

## Live Dashboard

RaceGuard ships with a **premium real-time monitoring dashboard** served as part of the Locust web UI.

### Screenshot

<!-- 📸 Add a screenshot of the dashboard here once captured -->
<!-- Example: ![RaceGuard Dashboard](./docs/dashboard-screenshot.png) -->

> _Screenshot coming soon — run `make load-test` and open http://localhost:8089/dashboard to see it live._

---

### Starting the dashboard

```bash
# Start the API server first (Terminal 1)
make run

# Start Locust with the web UI (Terminal 2)
make load-test
```

Then open your browser:

| URL | Purpose |
|-----|---------|
| **http://localhost:8089/dashboard** | 🎛️ RaceGuard live dashboard |
| http://localhost:8089 | Standard Locust UI |
| http://localhost:8089/live_stats | Raw JSON feed (polled by dashboard) |

### Dashboard Features

| Feature | Detail |
|---------|--------|
| **Strategy Cards** | One card per strategy — shows DB stock level, progress bar, successful purchases, out-of-stock hits, and system errors |
| **Live Stock Bar** | Animated progress bar; turns red when stock goes negative (oversell) |
| **Oversell Badge** | Per-card badge: `SAFE` (green) or `OVERSELL: N` (red, shaking animation) |
| **Global Alert Banner** | Full-width warning banner when *any* strategy oversells |
| **Comparison Table** | All 6 strategies side-by-side with numeric columns |
| **Runner Status** | Active user count and Locust runner state shown in the header |
| **Reset Button** | One-click resets both API inventory and Locust session counters |
| **Auto-refresh** | Polls `/live_stats` every **1 second** — no page reload needed |

### How it works

The dashboard is injected into Locust's embedded Flask application via the `@events.init` hook:

```python
@events.init.add_listener
def on_locust_init(environment, **kwargs):
    if environment.web_ui:
        @environment.web_ui.app.route("/dashboard")
        def custom_dashboard(): ...          # serves the HTML/JS UI

        @environment.web_ui.app.route("/live_stats")
        def live_stats(): ...                # JSON: per-strategy metrics

        @environment.web_ui.app.route("/reset_live_stocks", methods=["POST"])
        def reset_live_stocks(): ...         # resets API + session counters
```

Locust tracks per-strategy business metrics (`success_buys`, `out_of_stock`, `failures`) in a shared `test_stats` dict updated inside `@task` callbacks. The dashboard fetches these alongside live stock levels from the FastAPI `/stock` endpoint and calculates oversell in real time.

### Automatic test lifecycle

| Event | Action |
|-------|--------|
| **Test Start** | Auto-resets API stocks + clears session counters |
| **Test Stop** | Prints a full concurrency comparison table to the terminal |

---

## Running Tests

> **The server must be running** before executing tests.

```bash
# Terminal 1 — start server
make run

# Terminal 2 — run tests
make test
# or
python -m pytest tests/ -v
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
# Interactive UI at http://localhost:8089 (includes /dashboard)
make load-test

# Headless — 50 users, spawn 10/s, run 30 seconds
make load-test-headless

# Or directly:
python -m locust -f locustfile.py --host=http://127.0.0.1:8000
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
curl.exe -X POST "http://localhost:8000/buy?mode=redis"

# Buy with lock strategy
curl.exe -X POST "http://localhost:8000/buy?mode=lock"

# Buy with naive strategy (intentional race condition)
curl.exe -X POST "http://localhost:8000/buy?mode=naive"

# Buy with atomic CAS strategy
curl.exe -X POST "http://localhost:8000/buy?mode=atomic"

# Buy with optimistic locking
curl.exe -X POST "http://localhost:8000/buy?mode=optimistic"

# Buy via queue worker
curl.exe -X POST "http://localhost:8000/buy?mode=queue"

# Check all stocks
curl "http://localhost:8000/stock"

# Reset all stocks to INITIAL_STOCK
curl.exe -X POST "http://localhost:8000/reset"
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
| `make run` | `python -m uvicorn app.main:app --reload` | Dev server with hot-reload |
| `make run-prod` | `python -m uvicorn ... --workers 4` | Production multi-worker server |
| `make test` | `python -m pytest tests/ -v` | Run full test suite |
| `make load-test` | `python -m locust -f locustfile.py ...` | Locust UI (+ live dashboard at /dashboard) |
| `make load-test-headless` | `python -m locust --headless ...` | Headless load test |
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
├── locustfile.py            ← Locust load test + live dashboard GUI
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
