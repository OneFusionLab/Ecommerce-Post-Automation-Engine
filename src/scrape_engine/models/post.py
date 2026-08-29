"""Persistent ``Post`` model — the database-backed representation of a scraped
and/or published piece of content."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, func
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Post(SQLModel, table=True):
    """A scraped item persisted to the database.

    Holds both the raw normalized product data and the rendered post content
    (plus the WordPress publish result when applicable).
    """

    __tablename__ = "posts"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    slug: str = Field(index=True)
    source: str = Field(default="generic", index=True)
    source_url: str = Field(default="")

    price: str | None = None
    currency: str | None = None
    description: str | None = None

    # Nested / variable data stored as JSON.
    images: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    seller: dict = Field(default_factory=dict, sa_column=Column(JSON))
    meta: dict = Field(default_factory=dict, sa_column=Column(JSON))

    # Rendered content (HTML) for the post.
    content_html: str | None = None

    # Publish state.
    status: str = Field(default="scraped", index=True)  # scraped | published | failed
    wp_post_id: int | None = None
    wp_post_url: str | None = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )

    @property
    def published(self) -> bool:
        return self.status == "published" and self.wp_post_id is not None
