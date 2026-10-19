"""Separate migration, auth, bank and operations database privileges."""

from alembic import op

revision = "0002_roles"
down_revision = "0001_schema"
branch_labels = None
depends_on = None


def upgrade():
    statements = [
        "REVOKE ALL ON SCHEMA auth, bank, ops FROM PUBLIC",
        "REVOKE ALL ON ALL TABLES IN SCHEMA auth, bank, ops FROM PUBLIC",
        "GRANT USAGE ON SCHEMA auth TO resilience_auth, resilience_bank",
        "GRANT SELECT ON auth.users TO resilience_auth",
        "GRANT SELECT(id, role, is_active) ON auth.users TO resilience_bank",
        "GRANT USAGE ON SCHEMA bank TO resilience_bank",
        "GRANT SELECT ON bank.accounts, bank.transactions TO resilience_bank",
        "GRANT UPDATE(balance_minor, updated_at) ON bank.accounts TO resilience_bank",
        "GRANT INSERT ON bank.transactions TO resilience_bank",
        "GRANT USAGE ON SCHEMA ops TO resilience_ops",
        "GRANT SELECT, INSERT, UPDATE ON ops.incidents, ops.remediation_actions TO resilience_ops",
        "GRANT SELECT, INSERT ON ops.incident_events TO resilience_ops",
        "GRANT SELECT ON public.alembic_version TO resilience_auth, resilience_bank, resilience_ops",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade():
    for role in ("resilience_auth", "resilience_bank", "resilience_ops"):
        op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA auth, bank, ops FROM {role}")
        op.execute(f"REVOKE ALL ON SCHEMA auth, bank, ops FROM {role}")
        op.execute(f"REVOKE ALL ON public.alembic_version FROM {role}")
    op.execute("REVOKE SELECT(id, role, is_active) ON auth.users FROM resilience_bank")
    op.execute("REVOKE UPDATE(balance_minor, updated_at) ON bank.accounts FROM resilience_bank")
