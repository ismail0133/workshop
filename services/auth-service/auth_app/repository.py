from resilience_common.models import User
from sqlalchemy import select
from sqlalchemy.orm import Session


def find_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email))
