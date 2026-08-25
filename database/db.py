"""
Database connection and session management for WiFiSense.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from database.models import Base
import os

# Default SQLite URL, can be overridden by configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "wifisense.db").replace("\\", "/")
DEFAULT_DB_URL = f"sqlite:///{DB_PATH}"

_engine = None
_SessionFactory = None


def init_db(db_url: str = DEFAULT_DB_URL):
    """
    Initializes the database engine and creates tables if they don't exist.
    """
    global _engine, _SessionFactory
    if _engine is not None:
        current_url = str(_engine.url).replace("\\", "/").rstrip("/")
        target_url = db_url.replace("\\", "/").rstrip("/")
        if current_url != target_url:
            close_db()

    if _engine is None:
        # SQLite-specific optimization: disable same thread check for multithreaded workers
        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        _engine = create_engine(
            db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        _SessionFactory = sessionmaker(bind=_engine)
        
        # Create all tables (fallback/convenience for testing before full Alembic stage)
        Base.metadata.create_all(_engine)



def get_session():
    """
    Creates and returns a new SQLAlchemy session.
    """
    if _SessionFactory is None:
        init_db()
    return _SessionFactory()


def get_scoped_session():
    """
    Creates and returns a scoped session. Useful for multi-threaded applications.
    """
    if _SessionFactory is None:
        init_db()
    return scoped_session(_SessionFactory)


def close_db():
    """
    Disposes the database engine and releases all connections.
    """
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionFactory = None


def reset_all_tables():
    """
    Drops and recreates all database tables cleanly.
    """
    global _engine
    if _engine is None:
        init_db()
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)


