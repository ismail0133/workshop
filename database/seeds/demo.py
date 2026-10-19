"""Idempotent fictional seed: never resets an existing balance or password."""

from pathlib import Path
from uuid import UUID

from argon2 import PasswordHasher
from resilience_common.config import database_url
from resilience_common.models import Account, User
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert

USERS = {
    name: UUID(f"10000000-0000-4000-8000-{n:012d}")
    for n, name in enumerate(("alice", "bob", "operator", "admin", "validator"), 1)
}
ACCOUNTS = {
    name: UUID(f"20000000-0000-4000-8000-{n:012d}")
    for n, name in enumerate(("A", "B", "V1", "V2"), 1)
}


def main():
    engine = create_engine(database_url(), hide_parameters=True)
    hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
    with engine.begin() as conn:
        for name, ident in USERS.items():
            password = Path(f"/run/secrets/demo_{name}_password").read_text().strip()
            conn.execute(
                insert(User)
                .values(
                    id=ident,
                    email=f"{name}@resilience.test",
                    password_hash=hasher.hash(password),
                    role="USER" if name in ("alice", "bob") else name.upper(),
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
        for name, owner, balance in (
            ("A", "alice", 100000),
            ("B", "bob", 50000),
            ("V1", "validator", 10000),
            ("V2", "validator", 10000),
        ):
            conn.execute(
                insert(Account)
                .values(
                    id=ACCOUNTS[name],
                    owner_user_id=USERS[owner],
                    label=f"Compte {name}",
                    currency="EUR",
                    balance_minor=balance,
                    is_synthetic=name.startswith("V"),
                    status="ACTIVE",
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
    engine.dispose()
    print("Fictional seed ready; existing balances/passwords preserved.")


if __name__ == "__main__":
    main()
