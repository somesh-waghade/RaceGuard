"""
locustfile.py — Locust load test for RaceGuard.

Simulates concurrent flash-sale users hammering the /buy endpoint with
all 6 concurrency strategies, plus periodic /stock checks.

Run with:
    locust -f locustfile.py --host=http://127.0.0.1:8000

Then open http://localhost:8089 in your browser to configure and start
the load test interactively, or use headless mode:

    locust -f locustfile.py --host=http://127.0.0.1:8000 \\
           --headless -u 50 -r 10 --run-time 30s
"""

import random
from locust import HttpUser, task, between


STRATEGIES = ["naive", "lock", "atomic", "optimistic", "redis", "queue"]


class RaceGuardUser(HttpUser):
    """
    Simulates a flash-sale shopper hitting the RaceGuard API.

    Task weights:
      - buy  (weight 5): POST /buy with a randomly chosen strategy
      - stock (weight 1): GET /stock to check current inventory
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
                    response.success()
                else:
                    # Legitimate failure (out of stock) — not an error
                    response.success()
            else:
                response.failure(f"Unexpected status {response.status_code}")

    @task(1)
    def check_stock(self) -> None:
        """GET /stock to observe live inventory levels."""
        with self.client.get("/stock", name="/stock", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status {response.status_code}")
