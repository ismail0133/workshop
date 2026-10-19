from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from conftest import ACCOUNTS, USERS, balances, credentials, payload
from sqlalchemy import text


def send(api, headers, body=None, key=None):
    return api.post(
        "/api/payments",
        json=payload() if body is None else body,
        headers={**headers, "Idempotency-Key": key or str(uuid4())},
    )


def test_valid_login(auth):
    response = auth.post("/api/auth/login", json=credentials())
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["role"] == "USER" and data["expires_in"] == 900
    assert "password_hash" not in data["user"]
    me = auth.get("/api/auth/me", headers={"Authorization": "Bearer " + data["access_token"]})
    assert me.status_code == 200 and me.json()["id"] == str(USERS["alice"])


@pytest.mark.parametrize(
    "email,password", [("alice@resilience.test", "wrong"), ("absent@resilience.test", "wrong")]
)
def test_invalid_login(auth, email, password):
    response = auth.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401 and response.json()["code"] == "INVALID_CREDENTIALS"
    assert password not in response.text


@pytest.mark.parametrize(
    "path", ["/api/accounts", "/api/payments", "/api/accounts/" + str(ACCOUNTS["A"])]
)
def test_unauthorized(api, path):
    assert api.get(path).status_code == 401


@pytest.mark.parametrize("role", ["operator", "admin"])
def test_management_roles_cannot_spend_or_read_others(api, tokens, role):
    assert api.get("/api/accounts", headers=tokens[role]).status_code == 403
    assert send(api, tokens[role]).status_code == 403


def test_accounts_ownership(api, tokens):
    result = api.get("/api/accounts", headers=tokens["alice"])
    assert result.status_code == 200
    assert [a["id"] for a in result.json()["items"]] == [str(ACCOUNTS["A"])]
    assert result.json()["items"][0]["balance_minor"] == 100000
    assert api.get(f"/api/accounts/{ACCOUNTS['B']}", headers=tokens["alice"]).status_code == 404


def test_success_and_exact_idempotent_replay(api, tokens, db):
    first = send(api, tokens["alice"], key="scenario-transfer-200")
    assert first.status_code == 201 and first.json()["status"] == "SUCCESS"
    assert balances(db) == {"Compte A": 80000, "Compte B": 70000}
    replay = send(api, tokens["alice"], key="scenario-transfer-200")
    assert replay.status_code == 200 and replay.json() == first.json()
    assert balances(db) == {"Compte A": 80000, "Compte B": 70000}
    with db.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM bank.transactions")).scalar_one() == 1
        assert conn.execute(text("SELECT status FROM bank.transactions")).scalar_one() == "SUCCESS"
    history = api.get("/api/payments", headers=tokens["alice"]).json()
    assert len(history["items"]) == 1
    assert api.get(f"/api/payments/{first.json()['id']}", headers=tokens["bob"]).status_code == 200


def test_insufficient_funds_persisted_rejection(api, tokens, db):
    first = send(api, tokens["alice"], payload(100001), "insufficient-key")
    assert first.status_code == 409 and first.json()["failure_code"] == "INSUFFICIENT_FUNDS"
    assert send(api, tokens["alice"], payload(100001), "insufficient-key").json() == first.json()
    assert balances(db) == {"Compte A": 100000, "Compte B": 50000}


@pytest.mark.parametrize("amount", [0, -1, 1.5, 20000.0, True, "20000", 1000000000001, None])
def test_invalid_amount(api, tokens, amount):
    assert send(api, tokens["alice"], payload(amount)).status_code == 422


def test_missing_currency_and_extra_field(api, tokens):
    body = payload()
    body.pop("currency")
    assert send(api, tokens["alice"], body).status_code == 422
    assert send(api, tokens["alice"], {**payload(), "admin": True}).status_code == 422


def test_same_account_rejected(api, tokens):
    assert send(api, tokens["alice"], payload(destination="A")).status_code == 422


def test_nonexistent_or_unauthorized_account(api, tokens):
    assert (
        send(
            api, tokens["alice"], {**payload(), "destination_account_id": str(uuid4())}
        ).status_code
        == 404
    )
    assert send(api, tokens["alice"], payload(source="B", destination="A")).status_code == 404


def test_conflicting_idempotency_key(api, tokens, db):
    assert send(api, tokens["alice"], key="same-key-different-body").status_code == 201
    other = send(api, tokens["alice"], payload(100), "same-key-different-body")
    assert other.status_code == 409 and other.json()["code"] == "IDEMPOTENCY_CONFLICT"
    assert balances(db)["Compte A"] == 80000


def test_idempotency_key_required(api, tokens):
    assert api.post("/api/payments", json=payload(), headers=tokens["alice"]).status_code == 422


def test_concurrent_same_key_fifty_requests(api, tokens, db):
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(
            pool.map(lambda _: send(api, tokens["alice"], key="concurrency-same-key"), range(50))
        )
    assert sorted(r.status_code for r in results) == [200] * 49 + [201]
    assert len({r.json()["id"] for r in results}) == 1
    assert balances(db) == {"Compte A": 80000, "Compte B": 70000}


def test_concurrent_distinct_keys_no_overdraft(api, tokens, db):
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: send(api, tokens["alice"], payload(10000)), range(20)))
    assert sum(r.status_code == 201 for r in results) == 10
    assert sum(r.status_code == 409 for r in results) == 10
    assert balances(db) == {"Compte A": 0, "Compte B": 150000}


def test_concurrent_opposite_transfers_lock_order(api, tokens, db):
    def pay(i):
        return send(
            api,
            tokens["alice" if i % 2 == 0 else "bob"],
            payload(100, "A", "B") if i % 2 == 0 else payload(100, "B", "A"),
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(pay, range(20)))
    assert all(r.status_code == 201 for r in results)
    assert balances(db) == {"Compte A": 100000, "Compte B": 50000}


def test_atomic_rollback_on_insert_error(api, tokens, db):
    with db.begin() as conn:
        conn.execute(
            text(
                "CREATE FUNCTION bank.test_reject_insert() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'test insert failure'; END; $$"
            )
        )
        conn.execute(
            text(
                "CREATE TRIGGER test_reject BEFORE INSERT ON bank.transactions FOR EACH ROW EXECUTE FUNCTION bank.test_reject_insert()"
            )
        )
    try:
        assert send(api, tokens["alice"]).status_code == 503
        assert balances(db) == {"Compte A": 100000, "Compte B": 50000}
    finally:
        with db.begin() as conn:
            conn.execute(text("DROP TRIGGER test_reject ON bank.transactions"))
            conn.execute(text("DROP FUNCTION bank.test_reject_insert()"))


@pytest.mark.parametrize("state,code", [("frozen", "ACCOUNT_FROZEN"), ("limit", "BALANCE_LIMIT")])
def test_business_limits(api, tokens, db, state, code):
    with db.begin() as conn:
        if state == "frozen":
            conn.execute(
                text("UPDATE bank.accounts SET status='FROZEN' WHERE id=:id"), {"id": ACCOUNTS["B"]}
            )
        else:
            conn.execute(
                text("UPDATE bank.accounts SET balance_minor=1000000000000 WHERE id=:id"),
                {"id": ACCOUNTS["B"]},
            )
    result = send(api, tokens["alice"])
    assert result.status_code == 409 and result.json()["failure_code"] == code
    assert balances(db)["Compte A"] == 100000


def test_validator_isolation(api, tokens):
    assert send(api, tokens["validator"], payload(1, "V1", "V2")).status_code == 201
    assert send(api, tokens["validator"], payload(1, "V1", "A")).status_code == 404
    assert send(api, tokens["alice"], payload(1, "A", "V1")).status_code == 404


def test_pagination_scoped_signed_cursor(api, tokens):
    for _ in range(3):
        assert send(api, tokens["alice"], payload(1)).status_code == 201
    first = api.get("/api/payments?limit=2", headers=tokens["alice"]).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = api.get(
        "/api/payments",
        params={"limit": 2, "cursor": first["next_cursor"]},
        headers=tokens["alice"],
    ).json()
    assert len(second["items"]) == 1 and second["next_cursor"] is None
    assert (
        api.get(
            "/api/payments", params={"cursor": first["next_cursor"]}, headers=tokens["bob"]
        ).status_code
        == 422
    )
    assert api.get("/api/payments?cursor=invalid", headers=tokens["alice"]).status_code == 422


@pytest.mark.parametrize("fault", ["expired", "audience", "signature", "algorithm"])
def test_invalid_jwt(api, fault):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(USERS["alice"]),
        "role": "USER",
        "iss": "resilience-alpha-auth",
        "aud": "resilience-alpha",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=5),
        "jti": str(uuid4()),
    }
    if fault == "expired":
        claims["exp"] = now - timedelta(minutes=5)
    if fault == "audience":
        claims["aud"] = "wrong"
    if fault == "algorithm":
        token = jwt.encode(claims, "test-only-key-not-rsa", algorithm="HS256")
    else:
        token = jwt.encode(
            claims, Path("/run/secrets/jwt_private.pem").read_text(), algorithm="RS256"
        )
        if fault == "signature":
            token = token[:-10] + "XXXXXXXXXX"
    assert api.get("/api/accounts", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_disabled_user_immediately_denied(api, tokens, db):
    with db.begin() as conn:
        conn.execute(
            text("UPDATE auth.users SET is_active=false WHERE id=:id"), {"id": USERS["alice"]}
        )
    assert api.get("/api/accounts", headers=tokens["alice"]).status_code == 401


def test_health_metrics_and_request_id(api, auth, tokens):
    assert api.get("/health/live").json()["status"] == "ok"
    assert api.get("/health/ready").status_code == 200
    assert auth.get("/health").status_code == 200
    response = send(api, tokens["alice"])
    assert response.headers["X-Request-ID"]
    metrics = api.get("/metrics")
    assert metrics.status_code == 200
    for name in [
        "http_requests_total",
        "http_request_duration_seconds_bucket",
        "payment_attempts_total",
        "process_cpu_seconds_total",
        "payment_memory_limit_bytes",
    ]:
        assert name in metrics.text


def test_openapi_available(api, auth):
    assert "/api/payments" in api.get("/openapi.json").json()["paths"]
    assert "/api/auth/login" in auth.get("/openapi.json").json()["paths"]


def test_body_limit_and_no_password_echo(auth):
    result = auth.post(
        "/api/auth/login", json={"email": "x@resilience.test", "password": "x" * 17000}
    )
    assert result.status_code == 413 and "x" * 30 not in result.text


def test_database_role_separation(db):
    with db.connect() as conn:
        for role in ("resilience_auth", "resilience_bank", "resilience_ops", "resilience_migrator"):
            row = conn.execute(
                text("SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=:r"),
                {"r": role},
            ).one()
            assert not any(row)
        assert not conn.execute(
            text(
                "SELECT has_column_privilege('resilience_bank','auth.users','password_hash','SELECT')"
            )
        ).scalar_one()
        assert not conn.execute(
            text("SELECT has_table_privilege('resilience_auth','bank.accounts','UPDATE')")
        ).scalar_one()
        assert not conn.execute(
            text("SELECT has_table_privilege('resilience_ops','bank.accounts','UPDATE')")
        ).scalar_one()
        assert not conn.execute(
            text("SELECT has_table_privilege('resilience_bank','bank.transactions','DELETE')")
        ).scalar_one()
        assert not conn.execute(
            text("SELECT has_table_privilege('resilience_ops','ops.incident_events','UPDATE')")
        ).scalar_one()


def test_all_tables_and_utc(db):
    with db.connect() as conn:
        tables = set(
            conn.execute(
                text(
                    "SELECT table_schema,table_name FROM information_schema.tables WHERE table_schema IN ('auth','bank','ops')"
                )
            ).all()
        )
        assert tables == {
            ("auth", "users"),
            ("bank", "accounts"),
            ("bank", "transactions"),
            ("ops", "incidents"),
            ("ops", "incident_events"),
            ("ops", "remediation_actions"),
        }
        assert conn.execute(text("SHOW timezone")).scalar_one() in ("UTC", "Etc/UTC")
