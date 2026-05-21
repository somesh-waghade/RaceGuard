"""
locustfile.py — Locust load test for RaceGuard.

Simulates concurrent flash-sale users hammering the /buy endpoint with
all 6 concurrency strategies, plus periodic /stock checks.

Run with:
    locust -f locustfile.py --host=http://127.0.0.1:8000

Then open http://localhost:8089 in your browser to configure and start
the load test interactively, or use headless mode:

    locust -f locustfile.py --host=http://127.0.0.1:8000 \
           --headless -u 50 -r 10 --run-time 30s
"""

import random
import logging
import requests
from flask import jsonify
from locust import HttpUser, task, between, events

logger = logging.getLogger(__name__)

STRATEGIES = ["naive", "lock", "atomic", "optimistic", "redis", "queue"]

# Global statistics to track business-level metrics
test_stats = {
    strategy: {
        "success_buys": 0,
        "out_of_stock": 0,
        "failures": 0,
    }
    for strategy in STRATEGIES
}

initial_stock_val = {}


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Registers real-time statistics and premium dashboard routes on the Locust Flask app."""
    if environment.web_ui:
        @environment.web_ui.app.route("/live_stats")
        def live_stats():
            final_stock_val = {}
            if environment.host:
                try:
                    r = requests.get(f"{environment.host}/stock", timeout=2)
                    if r.status_code == 200:
                        final_stock_val = r.json()
                except Exception as e:
                    pass

            comparison = []
            for strategy in STRATEGIES:
                init_stock = initial_stock_val.get(strategy, 10)  # default to 10
                success_req = test_stats[strategy]["success_buys"]
                out_of_stock = test_stats[strategy]["out_of_stock"]
                errors = test_stats[strategy]["failures"]
                fin_stock = final_stock_val.get(strategy, "Unknown")
                
                # Calculate oversell
                oversell = 0
                if isinstance(init_stock, int) and isinstance(fin_stock, int):
                    physical_decrement = max(0, init_stock - max(0, fin_stock))
                    client_discrepancy = max(0, success_req - physical_decrement)
                    negative_stock = abs(fin_stock) if fin_stock < 0 else 0
                    oversell = max(client_discrepancy, negative_stock)
                else:
                    oversell = "N/A"
                    
                comparison.append({
                    "strategy": strategy,
                    "initial_stock": init_stock,
                    "success_buys": success_req,
                    "out_of_stock": out_of_stock,
                    "current_stock": fin_stock,
                    "oversell": oversell,
                    "failures": errors
                })
                
            return jsonify({
                "strategies": comparison,
                "host": environment.host,
                "user_count": environment.runner.user_count if environment.runner else 0,
                "state": environment.runner.state if environment.runner else "unknown"
            })

        @environment.web_ui.app.route("/reset_live_stocks", methods=["POST"])
        def reset_live_stocks():
            if environment.host:
                try:
                    r = requests.post(f"{environment.host}/reset", timeout=5)
                    if r.status_code == 200:
                        # Reset local counters
                        for strategy in STRATEGIES:
                            test_stats[strategy]["success_buys"] = 0
                            test_stats[strategy]["out_of_stock"] = 0
                            test_stats[strategy]["failures"] = 0
                        return jsonify({"success": True})
                except Exception as e:
                    logger.warning(f"Could not reset API stocks: {e}")
            return jsonify({"success": False}), 500

        @environment.web_ui.app.route("/dashboard")
        def custom_dashboard():
            return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RaceGuard Concurrency Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: #151c2c;
            --border-color: #232d42;
            --text-color: #e2e8f0;
            --text-muted: #8892b0;
            --primary: #6366f1;
            --primary-hover: #4f46e5;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --accent: #a78bfa;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.5;
            padding: 2rem;
            min-height: 100vh;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }

        .logo {
            font-size: 2rem;
            font-weight: 800;
            background: linear-gradient(135deg, var(--primary), var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .status-badge {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-family: 'JetBrains Mono', monospace;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--success);
            box-shadow: 0 0 10px var(--success);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.9); opacity: 0.6; }
            50% { transform: scale(1.1); opacity: 1; }
            100% { transform: scale(0.9); opacity: 0.6; }
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 1.5rem;
            margin-bottom: 3rem;
        }

        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, var(--primary), var(--accent));
            opacity: 0.8;
        }

        .card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 20px -8px rgba(99, 102, 241, 0.15);
            border-color: rgba(99, 102, 241, 0.4);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.25rem;
        }

        .strategy-title {
            font-size: 1.25rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .oversell-indicator {
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }

        .oversell-indicator.safe {
            background-color: rgba(16, 185, 129, 0.1);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.2);
        }

        .oversell-indicator.danger {
            background-color: rgba(239, 68, 68, 0.1);
            color: var(--danger);
            border: 1px solid rgba(239, 68, 68, 0.2);
            animation: shake 0.5s infinite;
        }

        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            25% { transform: translateX(-2px); }
            75% { transform: translateX(2px); }
        }

        .metric-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.75rem;
            font-size: 0.95rem;
        }

        .metric-label {
            color: var(--text-muted);
        }

        .metric-val {
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }

        .progress-container {
            height: 10px;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 5px;
            overflow: hidden;
            margin-top: 1rem;
            margin-bottom: 0.5rem;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }

        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, var(--primary), var(--accent));
            width: 100%;
            transition: width 0.5s ease-out;
            border-radius: 5px;
        }

        .table-container {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            overflow-x: auto;
        }

        .table-title {
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }

        th, td {
            padding: 1rem;
            border-bottom: 1px solid var(--border-color);
        }

        th {
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.8rem;
            letter-spacing: 0.05em;
        }

        td {
            font-size: 0.95rem;
        }

        tr:last-child td {
            border-bottom: none;
        }

        .mono {
            font-family: 'JetBrains Mono', monospace;
        }

        .btn {
            background-color: var(--primary);
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.2s;
            font-family: inherit;
        }

        .btn:hover {
            background-color: var(--primary-hover);
        }

        .alert-bar {
            display: none;
            background-color: rgba(239, 68, 68, 0.15);
            border: 1px solid var(--danger);
            color: #fca5a5;
            padding: 1rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            align-items: center;
            justify-content: space-between;
            font-weight: 500;
        }
        
        .danger {
            color: var(--danger) !important;
        }
    </style>
</head>
<body>
    <div class="alert-bar" id="oversell-alert">
        <span>⚠️ CRITICAL: Overselling detected in one or more strategies! Under concurrent load, unsynchronized strategies will allow stock to drop below 0.</span>
        <button class="btn" onclick="resetBackend()">Reset API Stocks</button>
    </div>

    <header>
        <div>
            <div class="logo">RaceGuard 🏁 <span style="font-size: 1rem; font-weight: 400; color: var(--text-muted);">Concurrency Monitor</span></div>
            <p style="color: var(--text-muted); margin-top: 0.25rem; font-size: 0.9rem;" id="host-label">Connecting to Locust host...</p>
        </div>
        <div style="display: flex; gap: 1rem; align-items: center;">
            <button class="btn" style="background-color: transparent; border: 1px solid var(--border-color); color: var(--text-color);" onclick="resetBackend()">Reset Stocks</button>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span id="runner-state">RUNNING</span> | <span id="user-count">0</span> Users
            </div>
        </div>
    </header>

    <div class="grid" id="strategies-grid">
        <!-- Cards will be populated dynamically -->
    </div>

    <div class="table-container">
        <div class="table-title">
            <span>Detailed Comparison Table</span>
            <span style="font-size: 0.875rem; font-weight: 400; color: var(--text-muted);">Updates every 1s</span>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Strategy</th>
                    <th>Initial Stock</th>
                    <th>Successful Buys</th>
                    <th>Out of Stock</th>
                    <th>Current DB Stock</th>
                    <th>Oversell</th>
                    <th>Failures</th>
                </tr>
            </thead>
            <tbody id="comparison-tbody">
                <!-- Table rows populated dynamically -->
            </tbody>
        </table>
    </div>

    <script>
        async function fetchStats() {
            try {
                const response = await fetch('/live_stats');
                const data = await response.json();
                
                document.getElementById('host-label').innerText = `Target Host: ${data.host || 'Unknown'}`;
                document.getElementById('runner-state').innerText = data.state.toUpperCase();
                document.getElementById('user-count').innerText = data.user_count;

                const grid = document.getElementById('strategies-grid');
                const tbody = document.getElementById('comparison-tbody');
                
                grid.innerHTML = '';
                tbody.innerHTML = '';
                
                let anyOversell = false;

                data.strategies.forEach(s => {
                    const oversellVal = s.oversell;
                    const hasOversell = typeof oversellVal === 'number' && oversellVal > 0;
                    if (hasOversell) anyOversell = true;

                    const stockPct = s.initial_stock > 0 ? Math.max(0, Math.min(100, (s.current_stock / s.initial_stock) * 100)) : 0;
                    
                    const card = document.createElement('div');
                    card.className = 'card';
                    card.innerHTML = `
                        <div class="card-header">
                            <span class="strategy-title">${s.strategy}</span>
                            <span class="oversell-indicator ${hasOversell ? 'danger' : 'safe'}">
                                ${hasOversell ? `OVERSELL: ${s.oversell}` : 'SAFE'}
                            </span>
                        </div>
                        <div>
                            <div class="metric-row">
                                <span class="metric-label">DB Stock Level</span>
                                <span class="metric-val ${s.current_stock < 0 ? 'danger' : ''}">${s.current_stock} / ${s.initial_stock}</span>
                            </div>
                            <div class="progress-container">
                                <div class="progress-bar" style="width: ${stockPct}%; background: ${s.current_stock < 0 ? 'var(--danger)' : 'linear-gradient(90deg, var(--primary), var(--accent))'}"></div>
                            </div>
                            <div class="metric-row">
                                <span class="metric-label">Successful Purchases</span>
                                <span class="metric-val" style="color: var(--success);">${s.success_buys}</span>
                            </div>
                            <div class="metric-row">
                                <span class="metric-label">Out of Stock Hits</span>
                                <span class="metric-val" style="color: var(--warning);">${s.out_of_stock}</span>
                            </div>
                            <div class="metric-row">
                                <span class="metric-label">Network/System Errors</span>
                                <span class="metric-val" style="color: var(--danger);">${s.failures}</span>
                            </div>
                        </div>
                    `;
                    grid.appendChild(card);

                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><strong>${s.strategy}</strong></td>
                        <td class="mono">${s.initial_stock}</td>
                        <td class="mono" style="color: var(--success);">${s.success_buys}</td>
                        <td class="mono" style="color: var(--warning);">${s.out_of_stock}</td>
                        <td class="mono ${s.current_stock < 0 ? 'danger' : ''}" style="font-weight: bold;">${s.current_stock}</td>
                        <td class="mono" style="font-weight: bold; color: ${hasOversell ? 'var(--danger)' : 'var(--success)'};">${s.oversell}</td>
                        <td class="mono">${s.failures}</td>
                    `;
                    tbody.appendChild(tr);
                });

                const alertBar = document.getElementById('oversell-alert');
                if (anyOversell) {
                    alertBar.style.display = 'flex';
                } else {
                    alertBar.style.display = 'none';
                }

            } catch (err) {
                console.error("Error fetching live stats:", err);
            }
        }

        async function resetBackend() {
            try {
                const resetRes = await fetch('/reset_live_stocks', { method: 'POST' });
                if (resetRes.ok) {
                    alert("API inventory and load test statistics successfully reset!");
                    fetchStats();
                } else {
                    alert("Failed to reset API inventory.");
                }
            } catch (err) {
                alert("Error connecting to server to reset: " + err);
            }
        }

        setInterval(fetchStats, 1000);
        fetchStats();
    </script>
</body>
</html>
"""


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Automatically resets the backend database and caches before the load test starts."""
    global initial_stock_val
    
    # Reset local counters
    for strategy in STRATEGIES:
        test_stats[strategy]["success_buys"] = 0
        test_stats[strategy]["out_of_stock"] = 0
        test_stats[strategy]["failures"] = 0

    if environment.host:
        try:
            logger.info("Automatically resetting API stocks before starting load test...")
            r = requests.post(f"{environment.host}/reset", timeout=5)
            if r.status_code == 200:
                data = r.json()
                init_val = data.get("initial_stock", 10)
                for strategy in STRATEGIES:
                    initial_stock_val[strategy] = init_val
                logger.info(f"API stocks successfully reset to {init_val}!")
            else:
                logger.warning(f"Reset endpoint returned status code {r.status_code}")
        except Exception as e:
            logger.warning(f"Could not automatically reset API stocks: {e}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Fetches final stock levels from the database and prints a comprehensive comparison table."""
    if not environment.host:
        return

    logger.info("Load test completed. Fetching final database stocks...")
    final_stock_val = {}
    try:
        r = requests.get(f"{environment.host}/stock", timeout=5)
        if r.status_code == 200:
            final_stock_val = r.json()
    except Exception as e:
        logger.warning(f"Could not fetch final database stock levels: {e}")

    # Print custom summary report
    print("\n" + "=" * 90)
    print("                      CONCURRENCY STRATEGIES PERFORMANCE REPORT")
    print("=" * 90)
    print(f"{'Strategy':<12} | {'Initial Stock':<13} | {'Success Req':<12} | {'Out of Stock':<12} | {'Final Stock':<11} | {'Oversell':<8} | {'Errors':<6}")
    print("-" * 90)

    for strategy in STRATEGIES:
        init_stock = initial_stock_val.get(strategy, "Unknown")
        success_req = test_stats[strategy]["success_buys"]
        out_of_stock = test_stats[strategy]["out_of_stock"]
        errors = test_stats[strategy]["failures"]
        
        fin_stock = final_stock_val.get(strategy, "Unknown")
        
        # Calculate oversell
        oversell = 0
        if isinstance(init_stock, int) and isinstance(fin_stock, int):
            # Client discrepancy: client got more successful HTTP 200 than inventory decremented
            physical_decrement = max(0, init_stock - max(0, fin_stock))
            client_discrepancy = max(0, success_req - physical_decrement)
            # DB negative stock: DB physically allowed stock to drop below 0
            negative_stock = abs(fin_stock) if fin_stock < 0 else 0
            
            oversell = max(client_discrepancy, negative_stock)
        else:
            oversell = "N/A"

        print(f"{strategy:<12} | {init_stock:<13} | {success_req:<12} | {out_of_stock:<12} | {fin_stock:<11} | {oversell:<8} | {errors:<6}")
    print("=" * 90 + "\n")


class RaceGuardUser(HttpUser):
    """
    Simulates a flash-sale shopper hitting the RaceGuard API.

    Task weights:
      - buy  (weight 5): POST /buy with a randomly chosen strategy
      - stock (weight 1): GET /stock to observe live inventory levels.
    """

    wait_time = between(0.01, 0.1)  # tight timing to maximise concurrency

    @task(5)
    def buy_item(self) -> None:
        """POST /buy with a random concurrency strategy."""
        mode = random.choice(STRATEGIES)
        with self.client.post(
            "/buy",
            params={"mode": mode},
            name=f"/buy?mode={mode}",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    response.name = f"/buy?mode={mode} [SUCCESS]"
                    response.success()
                    test_stats[mode]["success_buys"] += 1
                else:
                    # Legitimate out-of-stock event — not an error
                    response.name = f"/buy?mode={mode} [OUT_OF_STOCK]"
                    response.success()
                    test_stats[mode]["out_of_stock"] += 1
            else:
                response.name = f"/buy?mode={mode} [FAILED]"
                response.failure(f"Unexpected status {response.status_code}")
                test_stats[mode]["failures"] += 1

    @task(1)
    def check_stock(self) -> None:
        """GET /stock to observe live inventory levels."""
        with self.client.get("/stock", name="/stock", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status {response.status_code}")
