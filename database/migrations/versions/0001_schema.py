"""Six tables and integrity constraints from the reviewed phase-0 design."""

from pathlib import Path

from alembic import op

revision = "0001_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    sql = Path(__file__).with_suffix(".sql").read_text()
    # The frozen DDL has no procedural blocks or semicolons inside literals.
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade():
    for table in (
        "ops.remediation_actions",
        "ops.incident_events",
        "ops.incidents",
        "bank.transactions",
        "bank.accounts",
        "auth.users",
    ):
        op.execute(f"DROP TABLE {table}")
    for schema in ("ops", "bank", "auth"):
        op.execute(f"DROP SCHEMA {schema}")
