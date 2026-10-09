import threading
import sqlite3
from sqlalchemy import create_engine, text
from sqlmodel import SQLModel, Session
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite:///prioritygrid.db"

# Using a single serialized writer engine for all writes
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 15},
    pool_size=5,
    max_overflow=10
)

_db_lock = threading.Lock()
_db_degraded = False

def init_db():
    try:
        with engine.begin() as conn:
            # Enable WAL mode for concurrency
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.execute(text("PRAGMA synchronous=NORMAL;"))
        SQLModel.metadata.create_all(engine)
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        global _db_degraded
        _db_degraded = True

def is_degraded() -> bool:
    return _db_degraded

def set_degraded(status: bool):
    global _db_degraded
    _db_degraded = status

def commit_safely(session: Session):
    """Commits a session with a serialized writer lock and handles degradation."""
    global _db_degraded
    if _db_degraded:
        # DB is in a degraded state, do not attempt to write
        # Wait, if we're degraded, we might retry or just drop. The issue says "Handle full disk/busy/corruption with a visible degraded state and conservative restoration policy"
        return False
        
    with _db_lock:
        try:
            session.commit()
            return True
        except Exception as e:
            logger.error(f"DB write failed: {e}")
            session.rollback()
            _db_degraded = True
            return False
