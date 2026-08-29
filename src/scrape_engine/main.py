"""FastAPI application entrypoint for the Scrape-and-Publish backend.

Flow:  POST /scrape  ->  {url, source?, publish?}
        1. Resolve a scraper (explicit `source` or auto-detect from host).
        2. Scrape -> ProductData (title, price, description, images).
        3. Optionally publish to WordPress -> PublishResponse.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import HttpUrl

from scrape_engine.db import SessionLocal, init_db
from scrape_engine.models.post import Post
from scrape_engine.models.schemas import ScrapeRequest, ScrapeResponse
from scrape_engine.routers import posts as posts_router
from scrape_engine.scrapers.base import BaseScraper

load_dotenv()

MEDIA_DIR = os.getenv("MEDIA_DIR", "./media")
HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
PROXY_URL = os.getenv("PROXY_URL")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)
    try:
        await init_db()
    except Exception as exc:  # noqa: BLE001 - don't crash startup on DB issues
        print(f"[warn] Database init failed: {exc}")
    yield


app = FastAPI(
    title="Scrape-and-Publish Backend",
    description="Extract product data from e-commerce URLs and publish to WordPress.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(posts_router.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _persist_post(product, status: str) -> Post | None:
    """Save a scraped product to the database (best-effort)."""
    from scrape_engine.publishers.wp_publisher import build_post_content_html

    post = Post(
        title=product.title,
        slug=product.meta.get("slug") or product.title,
        source=product.source,
        source_url=str(product.url),
        price=product.price,
        currency=product.currency,
        description=product.description,
        images=[im.model_dump(mode="json") for im in product.images],
        seller=product.seller.model_dump(mode="json") if product.seller else {},
        meta=dict(product.meta),
        content_html=build_post_content_html(product),
        status=status,
    )
    return post


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape(payload: ScrapeRequest) -> ScrapeResponse:
    url = str(payload.url)
    source = payload.source or BaseScraper.detect(url)

    scraper_class = BaseScraper.get_scraper_class(source)
    scraper = scraper_class(url, headless=HEADLESS, proxy_url=PROXY_URL)
    try:
        product = await scraper.scrape()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Scraping failed: {exc}") from exc
    finally:
        await scraper.close()

    published = None
    if payload.publish:
        from scrape_engine.publishers.wp_publisher import WPPublisher

        publisher = WPPublisher()
        try:
            published = await publisher.publish(product)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=500, detail=f"Publishing failed: {exc}"
            ) from exc
        finally:
            await publisher.aclose()

    # Persist to the database (best-effort; never fail the scrape on DB errors).
    post_id: int | None = None
    try:
        status = "published" if (published and published.success) else (
            "failed" if (published and not published.success) else "scraped"
        )
        post = _persist_post(product, status=status)
        if published and published.success:
            post.wp_post_id = published.post_id
            post.wp_post_url = published.post_url
        async with SessionLocal() as session:
            session.add(post)
            await session.commit()
            await session.refresh(post)
            post_id = post.id
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] Failed to persist post: {exc}")
        post_id = None

    # Attach the DB id to the response metadata.
    if post_id is not None:
        product.meta["post_id"] = post_id

    return ScrapeResponse(
        product=product,
        published=bool(published and published.success),
        publish_detail=published,
    )


@app.get("/detect")
async def detect(url: Annotated[HttpUrl, Query(...)]) -> dict[str, str | None]:
    """Auto-detect which scraper would handle a given URL."""
    return {"url": str(url), "source": BaseScraper.detect(str(url))}
