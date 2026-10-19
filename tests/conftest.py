"""Integration tests are destructive ONLY inside the dedicated resilience_test database."""

import os
from pathlib import Path

import httpx
import pytest
from resilience_common.config import database_url
from sqlalchemy import create_engine, text

from database.seeds.demo import ACCOUNTS, USERS
from database.seeds.demo import main as seed


@pytest.fixture(scope="session")
def db():
    if os.getenv("DB_NAME") != "resilience_test":
        pytest.fail("Refusing destructive tests outside dedicated resilience_test database")
    engine = create_engine(database_url(), hide_parameters=True, pool_size=5)
    yield engine
    engine.dispose()


@pytest.fixture
def clean_db(db):
    with db.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE ops.remediation_actions, ops.incident_events, ops.incidents, bank.transactions, bank.accounts, auth.users CASCADE"
            )
        )
    seed()
    return db


@pytest.fixture
def api(clean_db):
    with httpx.Client(
        base_url=os.getenv("PAYMENT_URL", "http://payment-api:8000"), timeout=30
    ) as client:
        yield client


@pytest.fixture
def auth(clean_db):
    with httpx.Client(
        base_url=os.getenv("AUTH_URL", "http://auth-service:8001"), timeout=15
    ) as client:
        yield client


def credentials(name="alice"):
    return {
        "email": f"{name}@resilience.test",
        "password": Path(f"/run/secrets/demo_{name}_password").read_text().strip(),
    }


@pytest.fixture
def tokens(auth):
    result = {}
    for name in USERS:
        response = auth.post("/api/auth/login", json=credentials(name))
        assert response.status_code == 200, response.status_code
        result[name] = {"Authorization": "Bearer " + response.json()["access_token"]}
    return result


def payload(amount=20000, source="A", destination="B"):
    return {
        "source_account_id": str(ACCOUNTS[source]),
        "destination_account_id": str(ACCOUNTS[destination]),
        "amount_minor": amount,
        "currency": "EUR",
    }


def balances(db):
    with db.connect() as conn:
        return dict(
            conn.execute(
                text("SELECT label, balance_minor FROM bank.accounts WHERE NOT is_synthetic")
            ).all()
        )
