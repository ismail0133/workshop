"""Run the requested EUR200 scenario and inspect PostgreSQL without printing credentials."""

import json
import os
from pathlib import Path

import httpx
from resilience_common.config import database_url
from sqlalchemy import create_engine, text

from database.seeds.demo import ACCOUNTS


def validate_demo():
    engine = create_engine(database_url(), hide_parameters=True)

    def snapshot():
        with engine.connect() as conn:
            return {
                name: amount
                for name, amount in conn.execute(
                    text(
                        "SELECT label,balance_minor FROM bank.accounts WHERE label IN ('Compte A','Compte B')"
                    )
                )
            }

    before = snapshot()
    password = Path("/run/secrets/demo_alice_password").read_text().strip()
    with httpx.Client(timeout=15) as client:
        login = client.post(
            os.getenv("AUTH_URL", "http://auth-service:8001") + "/api/auth/login",
            json={"email": "alice@resilience.test", "password": password},
        )
        login.raise_for_status()
        headers = {
            "Authorization": "Bearer " + login.json()["access_token"],
            "Idempotency-Key": "phase1-demo-transfer-200-eur",
        }
        body = {
            "source_account_id": str(ACCOUNTS["A"]),
            "destination_account_id": str(ACCOUNTS["B"]),
            "amount_minor": 20000,
            "currency": "EUR",
        }
        url = os.getenv("PAYMENT_URL", "http://payment-api:8000") + "/api/payments"
        first = client.post(url, headers=headers, json=body)
        assert first.status_code in (200, 201), first.status_code
        repeated = client.post(url, headers=headers, json=body)
        assert repeated.status_code == 200 and repeated.json() == first.json()
        assert first.json()["status"] == "SUCCESS"
        assert snapshot() == {"Compte A": 80000, "Compte B": 70000}
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id,status,amount_minor FROM bank.transactions WHERE idempotency_key='phase1-demo-transfer-200-eur'"
                )
            ).all()
        assert (
            len(rows) == 1
            and str(rows[0].id) == first.json()["id"]
            and rows[0].amount_minor == 20000
        )
        history = client.get(url, headers=headers).json()["items"]
        assert sum(t["id"] == first.json()["id"] for t in history) == 1
        result = {
            "before_minor": before,
            "after_minor": snapshot(),
            "status": first.json()["status"],
            "first_http": first.status_code,
            "replay_http": repeated.status_code,
            "transaction_id": first.json()["id"],
            "matching_database_rows": len(rows),
            "sum_minor": sum(snapshot().values()),
            "direct_postgresql_check": "PASS",
        }
    engine.dispose()
    return result


if __name__ == "__main__":
    print(json.dumps(validate_demo(), indent=2))
