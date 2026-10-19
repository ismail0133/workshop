from datetime import datetime
from uuid import UUID

from resilience_common.errors import APIError
from resilience_common.models import Account, Transaction
from resilience_common.schemas import Role
from sqlalchemy import or_, select, tuple_
from sqlalchemy.orm import Session


def visible_accounts(principal):
    condition = Account.owner_user_id == principal.id
    if principal.role == Role.VALIDATOR:
        condition &= Account.is_synthetic.is_(True)
    return condition


def account(session: Session, principal, account_id: UUID) -> Account:
    value = session.scalar(
        select(Account).where(Account.id == account_id, visible_accounts(principal))
    )
    if value is None:
        raise APIError(404, "NOT_FOUND", "Compte introuvable")
    return value


def accounts(session: Session, principal, limit: int, after: list[str] | None):
    query = select(Account).where(visible_accounts(principal)).order_by(Account.id).limit(limit + 1)
    if after:
        try:
            if len(after) != 1:
                raise ValueError
            query = query.where(Account.id > UUID(after[0]))
        except (ValueError, TypeError):
            raise APIError(422, "INVALID_CURSOR", "Curseur invalide") from None
    return list(session.scalars(query))


def visible_payments(principal):
    owned = select(Account.id).where(visible_accounts(principal))
    return or_(
        Transaction.source_account_id.in_(owned), Transaction.destination_account_id.in_(owned)
    )


def payment(session: Session, principal, transaction_id: UUID) -> Transaction:
    value = session.scalar(
        select(Transaction).where(Transaction.id == transaction_id, visible_payments(principal))
    )
    if value is None:
        raise APIError(404, "NOT_FOUND", "Paiement introuvable")
    return value


def payments(session: Session, principal, limit: int, after: list[str] | None):
    query = (
        select(Transaction)
        .where(visible_payments(principal))
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .limit(limit + 1)
    )
    if after:
        try:
            if len(after) != 2:
                raise ValueError
            when, ident = datetime.fromisoformat(after[0]), UUID(after[1])
            if when.tzinfo is None:
                raise ValueError
            query = query.where(
                tuple_(Transaction.created_at, Transaction.id) < tuple_(when, ident)
            )
        except (ValueError, TypeError):
            raise APIError(422, "INVALID_CURSOR", "Curseur invalide") from None
    return list(session.scalars(query))


def previous_payment(session: Session, actor: UUID, key: str):
    return session.scalar(
        select(Transaction).where(
            Transaction.actor_user_id == actor, Transaction.idempotency_key == key
        )
    )


def lock_accounts(session: Session, ids: list[UUID]):
    return {
        a.id: a
        for a in session.scalars(
            select(Account).where(Account.id.in_(ids)).order_by(Account.id).with_for_update()
        )
    }
