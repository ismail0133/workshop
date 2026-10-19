from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import Settings


def create_database(settings: Settings):
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=8,
        max_overflow=0,
        pool_timeout=3,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 3,
            "options": "-c timezone=UTC -c statement_timeout=5000 -c lock_timeout=2000",
        },
    )
    return engine, sessionmaker(engine, expire_on_commit=False)
