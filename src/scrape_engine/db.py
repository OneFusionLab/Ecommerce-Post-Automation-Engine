"""Async database setup (SQLModel + SQLAlchemy over PostgreSQL via psycopg).

The connection string is read from ``DATABASE_URL`` (or the ``.env`` file).
Example::

    DATABASE_URL=postgresql+psycopg://scrape:scrape_secret@127.0.0.1:5432/scrape_engine
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel

load_dotenv()

DEFAULT_DATABASE_URL = "postgresql+psycopg://scrape:scrape_secret@127.0.0.1:5432/scrape_engine"

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncSession:  # pragma: no cover - FastAPI dependency
    """FastAPI dependency that yields an async DB session."""
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables. Import models that register tables first."""
    from scrape_engine.models import post  # noqa: F401  (registers the Post table)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
