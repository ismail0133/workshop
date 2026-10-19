import pytest
from pydantic import ValidationError
from resilience_common.app import RateLimiter
from resilience_common.errors import APIError
from resilience_common.pagination import Cursor
from resilience_common.schemas import PaymentRequest


def test_rate_limiter_enforces_five_attempts():
    limiter = RateLimiter(5)
    for _ in range(5):
        limiter.check("test-source")
    with pytest.raises(APIError) as exc:
        limiter.check("test-source")
    assert exc.value.status == 429
    limiter.check("another-source")


def test_cursor_tampering():
    codec = Cursor("unit-test-key-only")
    value = codec.encode("user-one", ["id"])
    assert codec.decode(value, "user-one") == ["id"]
    with pytest.raises(APIError):
        codec.decode(value, "user-two")
    with pytest.raises(APIError):
        codec.decode(value[:-5] + "AAAAA", "user-one")


def test_strict_money_schema():
    with pytest.raises(ValidationError):
        PaymentRequest(
            source_account_id="20000000-0000-4000-8000-000000000001",
            destination_account_id="20000000-0000-4000-8000-000000000002",
            amount_minor=True,
            currency="EUR",
        )
