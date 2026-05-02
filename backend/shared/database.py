# backend/shared/database.py
"""
Shared database configuration — used by all modules.
SQLite via SQLAlchemy (synchronous).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path
import os

# Store database in backend/data/
_data_dir = Path(__file__).parent.parent / "data"
_data_dir.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{(_data_dir / 'research_platform.db').as_posix()}"
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Create all tables that don't already exist."""
    from shared.models import UserDB, SummaryHistoryDB, SearchHistoryDB, UploadedPaperDB  # noqa: F401
    Base.metadata.create_all(bind=engine)
    print("INFO: Database tables verified / created")


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()