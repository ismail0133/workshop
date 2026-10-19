"""Idempotent role provisioning. Run only with the bootstrap secret in a tools container."""

import os
from pathlib import Path

import psycopg
from psycopg import sql


def main():
    database = os.getenv("DB_NAME", "resilience")
    with psycopg.connect(
        host=os.getenv("DB_HOST", "postgres"),
        dbname=database,
        user="resilience_bootstrap",
        password=Path("/run/secrets/postgres_password").read_text().strip(),
    ) as conn:
        for suffix in ("migrator", "auth", "bank", "ops"):
            role = "resilience_" + suffix
            password = Path(f"/run/secrets/{suffix}_password").read_text().strip()
            if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                conn.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION"
                    ).format(sql.Identifier(role))
                )
            conn.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
            conn.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(database), sql.Identifier(role)
                )
            )
        conn.execute(
            sql.SQL("REVOKE CONNECT, TEMPORARY ON DATABASE {} FROM PUBLIC").format(
                sql.Identifier(database)
            )
        )
        conn.execute(
            sql.SQL("GRANT CREATE ON DATABASE {} TO resilience_migrator").format(
                sql.Identifier(database)
            )
        )
        conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        conn.execute("GRANT USAGE, CREATE ON SCHEMA public TO resilience_migrator")
        conn.execute("ALTER ROLE resilience_auth SET statement_timeout = '5s'")
        conn.execute("ALTER ROLE resilience_bank SET statement_timeout = '5s'")
        conn.execute("ALTER ROLE resilience_bank SET lock_timeout = '2s'")
    print("Database roles provisioned; credentials not printed.")


if __name__ == "__main__":
    main()
