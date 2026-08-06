from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import DATABASE_URL, DATABASE_READ_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Read-only engine/session for the data agent -- a different connection to
# the SAME database and the SAME tables, so it reuses the one `Base` above
# instead of declaring a second, disconnected model registry. The safety
# here comes entirely from the Postgres role DATABASE_READ_URL points at
# (SELECT-only grants), not from anything in this file.
ro_engine = create_engine(DATABASE_READ_URL)
ROSessionLocal = sessionmaker(bind=ro_engine)


def init_db():
    """Create all tables that don't exist yet. Safe to call repeatedly."""
    import backend.models  # noqa: F401 — ensures all model classes are registered on Base
    Base.metadata.create_all(bind=engine)
