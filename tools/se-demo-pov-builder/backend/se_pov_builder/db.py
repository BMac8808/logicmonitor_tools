"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateColumn


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str) -> Engine:
    kwargs: dict = {}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if database_url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
        else:
            path = database_url.removeprefix("sqlite:///")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, **kwargs)
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):  # pragma: no cover - trivial
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    from . import models  # noqa: F401  (register tables)

    Base.metadata.create_all(engine)
    _add_missing_nullable_columns(engine)


def _add_missing_nullable_columns(engine: Engine) -> None:
    """Additive upgrade for local databases created by an older version: add new nullable
    columns. Anything more involved needs real migrations (planned: Alembic)."""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing and column.nullable:
                    ddl = CreateColumn(column).compile(dialect=engine.dialect)
                    conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ADD COLUMN {ddl}')


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
    finally:
        session.close()
