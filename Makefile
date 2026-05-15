.PHONY: run test load-test reset docker-up docker-down install

# ── Configuration ────────────────────────────────────────────────────────────
HOST      ?= 127.0.0.1
PORT      ?= 8000
WORKERS   ?= 4
LOCUST_USERS ?= 50
LOCUST_RATE  ?= 10
LOCUST_TIME  ?= 30s

# ── Development server ───────────────────────────────────────────────────────
run:
	uvicorn app.main:app --host $(HOST) --port $(PORT) --reload

run-prod:
	uvicorn app.main:app --host $(HOST) --port $(PORT) --workers $(WORKERS)

# ── Tests ────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v --tb=short

test-ci:
	pytest tests/ -v --tb=short --no-header -q

# ── Load testing ─────────────────────────────────────────────────────────────
load-test:
	locust -f locustfile.py --host=http://$(HOST):$(PORT)

load-test-headless:
	locust -f locustfile.py \
	       --host=http://$(HOST):$(PORT) \
	       --headless \
	       -u $(LOCUST_USERS) \
	       -r $(LOCUST_RATE) \
	       --run-time $(LOCUST_TIME)

# ── Reset stock via API ───────────────────────────────────────────────────────
reset:
	curl -s -X POST http://$(HOST):$(PORT)/reset | python -m json.tool

stock:
	curl -s http://$(HOST):$(PORT)/stock | python -m json.tool

# ── Docker ───────────────────────────────────────────────────────────────────
docker-up:
	docker compose up -d redis

docker-down:
	docker compose down

# ── Dependencies ─────────────────────────────────────────────────────────────
install:
	pip install -r requirements.txt
