from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def init_db():
    """Create all tables that don't exist yet. Safe to call repeatedly."""
    import models  # noqa: F401 — ensures all model classes are registered on Base
    Base.metadata.create_all(bind=engine)
