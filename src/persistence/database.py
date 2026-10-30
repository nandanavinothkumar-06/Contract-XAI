"""
Database engine configuration, session management, and schema initialization.
Supports SQLite for lightweight local development and testing, and PostgreSQL for production.
"""

import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

Base = declarative_base()

def get_database_url() -> str:
    """
    Retrieves database connection string from environment variables.
    Defaults to local SQLite database in data/contracts/contractrisk.db.
    """
    url = os.getenv("CONTRACTRISK_DB_URL") or os.getenv("DATABASE_URL")
    if url:
        return url
        
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "contracts"))
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "contractrisk.db")
    return f"sqlite:///{db_path}"

def create_db_engine(database_url: str = None, echo: bool = False):
    """
    Creates SQLAlchemy engine with connection pooling and dialect-specific parameters.
    """
    url = database_url or get_database_url()
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        
    return create_engine(url, connect_args=connect_args, echo=echo)

# Global default engine and session factory
_DEFAULT_ENGINE = None
_SESSION_FACTORY = None

def get_engine():
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = create_db_engine()
    return _DEFAULT_ENGINE

def get_session_factory(engine=None):
    global _SESSION_FACTORY
    if engine is not None:
        return sessionmaker(autocommit=False, autoflush=False, bind=engine)
    if _SESSION_FACTORY is None:
        target_engine = get_engine()
        _SESSION_FACTORY = sessionmaker(autocommit=False, autoflush=False, bind=target_engine)
    return _SESSION_FACTORY

def reset_db_state():
    """Resets the default engine and session factory."""
    global _DEFAULT_ENGINE, _SESSION_FACTORY
    _DEFAULT_ENGINE = None
    _SESSION_FACTORY = None

def init_db(engine=None):
    """Creates all database tables defined in models and ensures schema compatibility."""
    target_engine = engine or get_engine()
    Base.metadata.create_all(bind=target_engine)

    try:
        from sqlalchemy import text
        with target_engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info(clause_findings)")).fetchall()
            existing_cols = {row[1] for row in res}
            if existing_cols:
                if "ai_metadata_json" not in existing_cols:
                    conn.execute(text("ALTER TABLE clause_findings ADD COLUMN ai_metadata_json TEXT"))
                if "model_attribution_json" not in existing_cols:
                    conn.execute(text("ALTER TABLE clause_findings ADD COLUMN model_attribution_json TEXT"))
                if "evidence_quality_status" not in existing_cols:
                    conn.execute(text("ALTER TABLE clause_findings ADD COLUMN evidence_quality_status VARCHAR(64)"))
                conn.commit()
    except Exception:
        pass

def drop_db(engine=None):
    """Drops all database tables (useful for isolated testing)."""
    target_engine = engine or get_engine()
    Base.metadata.drop_all(bind=target_engine)

@contextmanager
def get_db_session(engine=None) -> Generator[Session, None, None]:
    """
    Transactional context manager ensuring commit on success and rollback on exception.
    """
    factory = get_session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# Convenient alias
get_db = get_db_session

