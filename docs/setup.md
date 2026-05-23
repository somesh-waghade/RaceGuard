# Setup & Development Guide

## Prerequisites

- Python 3.11+
- Docker & Docker Compose (for Redis)

---

## Installation

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

## API Reference

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/buy?mode=<strategy>` | Buy one item using the specified strategy |
| `GET`  | `/stock` | Current stock for all strategies |
| `POST` | `/reset` | Reset all strategies to INITIAL_STOCK |

### Valid `mode` values

`naive` · `lock` · `atomic` · `optimistic` · `redis` · `queue`

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
