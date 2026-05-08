"""SQLite/SQLModel database setup for the local API."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

_engine: Engine | None = None
_database_url: str | None = None


def _default_database_url() -> str:
    if os.environ.get("CONCORD_DATABASE_URL"):
        return os.environ["CONCORD_DATABASE_URL"]
    db_path = Path(os.environ.get("CONCORD_DB_PATH", "data/concord.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


def _connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def configure_database(database_url: str) -> None:
    global _database_url, _engine
    _database_url = database_url
    _engine = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = _database_url or _default_database_url()
        if url.startswith("sqlite:///"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, connect_args=_connect_args(url))
    return _engine


def init_db() -> None:
    from api import models  # noqa: F401

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _ensure_run_cost_columns(engine)
    _ensure_violation_recurrence_columns(engine)


def _ensure_run_cost_columns(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if not inspector.has_table("runs"):
        return
    existing = {column["name"] for column in inspector.get_columns("runs")}
    columns = {
        "daytona_seconds": "FLOAT DEFAULT 0.0",
        "llm_tokens": "INTEGER DEFAULT 0",
        "llm_cost_usd": "FLOAT DEFAULT 0.0",
        "daytona_cost_usd": "FLOAT DEFAULT 0.0",
    }
    with engine.begin() as connection:
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE runs ADD COLUMN {name} {definition}"))


def _ensure_violation_recurrence_columns(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if not inspector.has_table("violations"):
        return
    existing = {column["name"] for column in inspector.get_columns("violations")}
    columns = {
        "workflow_id": "VARCHAR DEFAULT ''",
        "recurrence_key": "VARCHAR DEFAULT ''",
        "rule": "VARCHAR DEFAULT ''",
    }
    with engine.begin() as connection:
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE violations ADD COLUMN {name} {definition}"))


def get_session() -> Iterator[Session]:
    init_db()
    with Session(get_engine()) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    init_db()
    with Session(get_engine()) as session:
        yield session
