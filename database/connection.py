"""
database/connection.py
Handles PostgreSQL connection via SQLAlchemy 2.x.
Credentials come from DATABASE_URL in the environment; never hardcoded.
"""
import os
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

load_dotenv()

_engine = None
_SessionLocal = None


def _build_engine():
    """Build the SQLAlchemy engine from DATABASE_URL."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        return None

    # Supabase pooled URLs use postgresql+psycopg2 scheme;
    # ensure the async-incompatible psycopg2 variant is used for sync code.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    try:
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )
        return engine
    except Exception:
        return None


def get_engine():
    """Return the global engine, building it once."""
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session() -> Optional[Session]:
    """Return a new database session, or None if not configured."""
    global _SessionLocal
    engine = get_engine()
    if engine is None:
        return None
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return _SessionLocal()


def db_health_check() -> dict:
    """
    Run a simple SELECT 1 to check DB connectivity.
    Returns {"ok": True} or {"ok": False, "error": str}.
    Never surfaces credentials in the error message.
    """
    engine = get_engine()
    if engine is None:
        return {"ok": False, "error": "DATABASE_URL not configured."}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:
        # Strip potential credential fragment from error message
        msg = str(exc).split("\n")[0][:200]
        return {"ok": False, "error": f"Database connection failed: {msg}"}
