"""Shared mapping of the six phase-0 tables. Alembic alone owns DDL."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = {"schema": "bank"}
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("auth.users.id", ondelete="RESTRICT"))
    label: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(3), server_default="EUR")
    balance_minor: Mapped[int] = mapped_column(BigInteger, server_default="0")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    status: Mapped[str] = mapped_column(String(12), server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = {"schema": "bank"}
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("auth.users.id", ondelete="RESTRICT"))
    source_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("bank.accounts.id", ondelete="RESTRICT")
    )
    destination_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("bank.accounts.id", ondelete="RESTRICT")
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(12))
    failure_code: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = {"schema": "ops"}
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    parent_incident_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ops.incidents.id", ondelete="RESTRICT")
    )
    service: Mapped[str] = mapped_column(String(32))
    scenario: Mapped[str] = mapped_column(String(16), server_default="SC-01")
    fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))
    severity: Mapped[str] = mapped_column(String(12))
    source_ip: Mapped[str | None] = mapped_column(INET)
    summary: Mapped[str] = mapped_column(String(500))
    policy_version: Mapped[str | None] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, server_default="0")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("bank.transactions.id", ondelete="RESTRICT")
    )


class IncidentEvent(Base):
    __tablename__ = "incident_events"
    __table_args__ = {"schema": "ops"}
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("ops.incidents.id", ondelete="RESTRICT"))
    sequence: Mapped[int] = mapped_column(BigInteger)
    event_type: Mapped[str] = mapped_column(String(40))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    request_id: Mapped[UUID | None]
    payload: Mapped[dict] = mapped_column(JSONB)


class RemediationAction(Base):
    __tablename__ = "remediation_actions"
    __table_args__ = {"schema": "ops"}
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("ops.incidents.id", ondelete="RESTRICT"))
    related_action_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ops.remediation_actions.id", ondelete="RESTRICT")
    )
    kind: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(16), server_default="PENDING")
    target_ip: Mapped[str] = mapped_column(INET)
    ttl_seconds: Mapped[int] = mapped_column(Integer)
    policy_version: Mapped[str] = mapped_column(String(32))
    attempt: Mapped[int] = mapped_column(Integer, server_default="0")
    fencing_token: Mapped[int] = mapped_column(BigInteger, server_default="0")
    lease_token: Mapped[UUID | None]
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
