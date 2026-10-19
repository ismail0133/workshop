import hashlib
import json
from datetime import datetime, timezone

from resilience_common.errors import APIError
from resilience_common.models import Transaction
from resilience_common.schemas import PaymentView, Role
from sqlalchemy import text

from .repository import lock_accounts, previous_payment


def transfer(session, principal, body, key: str) -> tuple[PaymentView, int]:
    canonical = json.dumps(body.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(canonical.encode()).hexdigest()
    lock_key = int.from_bytes(
        hashlib.sha256(f"{principal.id}:{key}".encode()).digest()[:8], "big", signed=True
    )
    with session.begin():
        # Serialize intentions BEFORE touching balances. The unique constraint is a final backstop.
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
        old = previous_payment(session, principal.id, key)
        if old is not None:
            if old.request_hash != request_hash:
                raise APIError(
                    409, "IDEMPOTENCY_CONFLICT", "Clé déjà utilisée avec une autre demande"
                )
            return PaymentView.model_validate(old), 200 if old.status == "SUCCESS" else 409
        locked = lock_accounts(session, [body.source_account_id, body.destination_account_id])
        source, destination = (
            locked.get(body.source_account_id),
            locked.get(body.destination_account_id),
        )
        if source is None or destination is None or source.owner_user_id != principal.id:
            raise APIError(404, "NOT_FOUND", "Compte introuvable")
        if principal.role == Role.VALIDATOR and not (
            source.is_synthetic
            and destination.is_synthetic
            and destination.owner_user_id == principal.id
        ):
            raise APIError(404, "NOT_FOUND", "Compte introuvable")
        # Synthetic validation accounts may never receive customer payments.
        if principal.role == Role.USER and (source.is_synthetic or destination.is_synthetic):
            raise APIError(404, "NOT_FOUND", "Compte introuvable")
        failure = None
        if source.status != "ACTIVE" or destination.status != "ACTIVE":
            failure = "ACCOUNT_FROZEN"
        elif source.balance_minor < body.amount_minor:
            failure = "INSUFFICIENT_FUNDS"
        elif destination.balance_minor + body.amount_minor > 10**12:
            failure = "BALANCE_LIMIT"
        if failure is None:
            source.balance_minor -= body.amount_minor
            destination.balance_minor += body.amount_minor
            source.updated_at = destination.updated_at = datetime.now(timezone.utc)
        record = Transaction(
            actor_user_id=principal.id,
            idempotency_key=key,
            request_hash=request_hash,
            **body.model_dump(),
            status="REJECTED" if failure else "SUCCESS",
            failure_code=failure,
        )
        session.add(record)
        session.flush()
        result = PaymentView.model_validate(record)
    # A commit failure never returns SUCCESS.
    return result, 409 if failure else 201
