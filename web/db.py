"""Database utilities for SQLAlchemy session and engine management."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

Base = declarative_base()
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False))
_ENGINE: Optional[Engine] = None


def init_db(app) -> Engine:
    """Initialize DB engine and scoped session for the application."""
    global _ENGINE

    db_url = app.config["DATABASE_URL"]
    kwargs = {"future": True, "pool_pre_ping": True}
    if db_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}

    _ENGINE = create_engine(db_url, **kwargs)
    SessionLocal.configure(bind=_ENGINE)

    from web import models  # noqa: F401 - registers model metadata

    if app.config.get("AUTO_CREATE_SCHEMA", False):
        Base.metadata.create_all(bind=_ENGINE)
        _ensure_schema_updates(_ENGINE)

    @app.teardown_appcontext
    def remove_session(exception=None):  # pylint: disable=unused-argument
        SessionLocal.remove()

    return _ENGINE


def _ensure_schema_updates(engine: Engine) -> None:
    """Apply lightweight additive schema upgrades for local/dev environments."""
    inspector = inspect(engine)
    if "audit_jobs" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("audit_jobs")}
    statements = []
    if "crawl_mode" not in columns:
        statements.append("ALTER TABLE audit_jobs ADD COLUMN crawl_mode VARCHAR(16) NOT NULL DEFAULT 'all'")
    if "max_videos_override" not in columns:
        statements.append("ALTER TABLE audit_jobs ADD COLUMN max_videos_override INTEGER")

    if not statements:
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def get_engine() -> Engine:
    if _ENGINE is None:
        raise RuntimeError("Database engine has not been initialized. Call init_db(app) first.")
    return _ENGINE
