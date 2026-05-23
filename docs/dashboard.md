# Live Dashboard

RaceGuard ships with a **premium real-time monitoring dashboard** served as part of the Locust web UI.

## Starting the Dashboard

```bash
# Terminal 1 — start the API server
make run

# Terminal 2 — start Locust with the web UI
make load-test
```

Then open your browser:

| URL | Purpose |
|-----|---------|
| **http://localhost:8089/dashboard** | 🎛️ RaceGuard live dashboard |
| http://localhost:8089 | Standard Locust UI |
| http://localhost:8089/live_stats | Raw JSON feed (polled by dashboard) |

---

## Dashboard Features

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

---

## How It Works

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

---

## Automatic Test Lifecycle

| Event | Action |
|-------|--------|
| **Test Start** | Auto-resets API stocks + clears session counters |
| **Test Stop** | Prints a full concurrency comparison table to the terminal |
