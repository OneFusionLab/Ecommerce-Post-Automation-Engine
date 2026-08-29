"""REST endpoints for the persistent posts collection."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from scrape_engine.db import get_session
from scrape_engine.models.post import Post
from scrape_engine.models.schemas import ProductData
from scrape_engine.publishers.wp_publisher import build_post_content_html

router = APIRouter(prefix="/posts", tags=["posts"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _product_to_post(product: ProductData, *, status: str = "scraped") -> Post:
    """Build a persistent :class:`Post` from normalized product data."""
    return Post(
        title=product.title,
        slug=product.meta.get("slug") or product.title,
        source=product.source,
        source_url=str(product.url),
        price=product.price,
        currency=product.currency,
        description=product.description,
        images=[m.model_dump(mode="json") for m in product.images],
        seller=product.seller.model_dump(mode="json") if product.seller else {},
        meta=dict(product.meta),
        content_html=build_post_content_html(product),
        status=status,
    )


@router.get("")
async def list_posts(
    session: SessionDep,
    source: str | None = None,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[Post]:
    """List persisted posts, newest first, with optional filters."""
    stmt = select(Post).order_by(Post.created_at.desc()).limit(limit)
    if source:
        stmt = stmt.where(Post.source == source)
    if status:
        stmt = stmt.where(Post.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("", status_code=201)
async def create_post(
    product: ProductData, session: SessionDep, status: str = "scraped"
) -> Post:
    """Persist a scraped product as a post."""
    post = _product_to_post(product, status=status)
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return post


@router.get("/count")
async def count_posts(session: SessionDep) -> dict[str, int]:
    """Return the total number of persisted posts."""
    result = await session.execute(select(func.count()).select_from(Post))
    return {"count": int(result.scalar_one())}


@router.get("/{post_id}")
async def get_post(post_id: int, session: SessionDep) -> Post:
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.delete("/{post_id}", status_code=204)
async def delete_post(post_id: int, session: SessionDep) -> None:
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    await session.delete(post)
    await session.commit()
