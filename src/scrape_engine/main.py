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
from scrape_engine.models.schemas import (
    FacebookLoginRequest,
    FacebookLoginResponse,
    FacebookStatusResponse,
    ScrapeRequest,
    ScrapeResponse,
)
from scrape_engine.routers import posts as posts_router
from scrape_engine.scrapers.base import BaseScraper
from scrape_engine.scrapers.facebook_scraper import login as fb_login
from scrape_engine.scrapers.facebook_scraper import session_status as fb_status

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


@app.get("/scrape/facebook/status", response_model=FacebookStatusResponse)
async def facebook_status() -> FacebookStatusResponse:
    """Report whether a usable Facebook session exists."""
    return FacebookStatusResponse(**fb_status())


@app.post("/scrape/facebook/login", response_model=FacebookLoginResponse)
async def facebook_login(payload: FacebookLoginRequest) -> FacebookLoginResponse:
    """Open a visible browser and wait for the user to log in to Facebook.

    Blocks until a session is established (or the timeout elapses), then
    saves the session cookies to disk for reuse by the facebook scraper.
    """
    try:
        result = await fb_login(
            timeout=payload.timeout,
            headless=False,
            proxy_url=PROXY_URL,
        )
    except Exception as exc:  # noqa: BLE001
        return FacebookLoginResponse(
            logged_in=False,
            message=f"Login could not start: {exc}",
            cookies_saved=False,
        )
    return FacebookLoginResponse(**result)


@app.get("/scrape/facebook/html")
async def facebook_debug_html(url: Annotated[HttpUrl, Query(...)]) -> dict:
    """Fetch a Facebook URL with the saved session and return deep introspection.

    Debugging aid: scans the full page for price/description and classifies every
    image URL so the Facebook scraper can target the real listing data.
    """
    import re as _re

    from bs4 import BeautifulSoup

    from scrape_engine.scrapers.facebook_scraper import FacebookScraper

    scraper = FacebookScraper(str(url), headless=HEADLESS, proxy_url=PROXY_URL)
    try:
        html = await scraper.fetch_session_html()
    except Exception as exc:  # noqa: BLE001
        return {"url": str(url), "error": str(exc)}
    finally:
        await scraper.close()

    soup = BeautifulSoup(html, "html.parser")

    # ---- Title ----
    title = (soup.title.get_text(strip=True) if soup.title else None) or ""
    if " – " in title:
        title = title.split(" – ")[-1]
    elif " | " in title:
        title = title.split(" | ")[-1]

    # ---- Price: scan every visible text node + raw HTML for currency amounts ----
    price_pat = _re.compile(
        r"(?:[$€£৳₹₩₺₱]|R\$|RM|BDT|Tk|Taka)\s?[\d][\d,\.]*",
        _re.I,
    )
    found_prices: list[str] = []
    for el in soup.find_all(["span", "div", "strong", "h2", "h3", "li"]):
        t = el.get_text(" ", strip=True)
        m = price_pat.fullmatch(_re.sub(r"\s+", " ", t))
        if m:
            found_prices.append(m.group(0))
    # also scan raw html text
    html_prices = _re.findall(
        r"(?:[$€£৳₹₩₺₱]|R\$|RM|BDT|Tk|Taka)\s?[\d][\d,\.]{1,12}", html
    )[:20]

    # ---- Description: longest text block that's not nav/meta ----
    desc_nodes = []
    for el in soup.find_all(["div", "p", "span"]):
        t = el.get_text(" ", strip=True)
        if not t or len(t) < 40:
            continue
        if any(k in t.lower() for k in ("log in", "sign up", "seller details",
                                         "marketplace", "cookies", "privacy")):
            continue
        if len(t) > 2000:
            continue
        desc_nodes.append(t)

    # ---- Images: classify all fbcdn image URLs ----
    img_urls: list[str] = []
    for node in soup.find_all("img"):
        s = node.get("src") or node.get("data-src")
        a = node.get("alt") or ""
        cls = node.get("class") or []
        if s and ("fbcdn" in s or "lookaside" in s or "scontent" in s):
            img_urls.append({"url": s[:160], "alt": a[:80], "class": " ".join(cls)[:60]})

    # Listing photos are marked with alt="Product photo of ..."
    listing_imgs = [i["url"] for i in img_urls if i["alt"].lower().startswith("product photo of ")]

    # ---- Isolate the listing region (exclude the "Today's picks" recommendations) ----
    # Recommendation cards contain links to other items; the listing's own block
    # holds the price and description. We find elements whose text is a price
    # (or a description) but is NOT one of the many recommendation prices.
    rec_titles = ["today's picks", "recommended", "similar", "you may also like"]
    price_nodes = []
    for el in soup.find_all(["span", "div", "strong", "h2"]):
        t = el.get_text(" ", strip=True)
        if not t or len(t) > 24:
            continue
        if price_pat.fullmatch(_re.sub(r"\s+", " ", t)):
            # skip if this price element belongs to a recommendation card
            parent = el.find_parent(["div", "li", "span"])
            if parent and any(
                k in parent.get_text(" ", strip=True)[:150].lower()
                for k in ("group", "similar", "facebook.com/marketplace/item/")
            ):
                continue
            price_nodes.append({"text": t, "cls": " ".join(el.get("class") or [])[:60]})

    # Description: longest block that isn't the recommendations feed (it would
    # contain several other-item prices / 'in Dhaka, Bangladesh').
    desc_final = []
    for el in soup.find_all(["div", "p", "span"]):
        t = el.get_text(" ", strip=True)
        if not t or len(t) < 40:
            continue
        if any(k in t.lower() for k in rec_titles):
            continue
        # recommendation feed joins many '<title> in <loc>' and prices
        if t.lower().count(" in dhaka, bangladesh") > 0 or t.lower().count(" in ") > 2:
            continue
        if "seller details" in t.lower():
            continue
        desc_final.append(t)

    # Seller context: text around the first market profile link, to see where
    # the seller's display name lives in the DOM.
    seller_context = None
    prof_link = soup.select_one(
        "a[href*='marketplace/profile/'], a[href*='/profile/'], a[href*='profile.php']"
    )
    if prof_link:
        base = prof_link.get_text(" ", strip=True) or ""
        parent = prof_link.find_parent(["div", "li", "span"])
        ctx = parent.get_text(" ", strip=True) if parent else base
        seller_context = {
            "link_text": base,
            "link_href": (prof_link.get("href") or "")[:120],
            "context": ctx[:200],
        }

    # Page-wide scan for person-name text nodes (the seller's display name is
    # rendered in a "Seller information" card, not under "Seller details").
    name_scan = []
    seen_names: set[str] = set()
    for el in soup.find_all(["span", "div", "a", "strong", "h1", "h2", "h3"]):
        t = el.get_text(" ", strip=True)
        if not t or len(t) > 40 or len(t) < 3 or t in seen_names:
            continue
        if not all(c.isalpha() or c in " .'-" for c in t):
            continue
        low = t.lower()
        if low in ("seller details", "seller", "marketplace", "profile", "buy", "sell", "home", "shorts", "groups", "menu", "notifications", "inbox", "create new listing") or " " not in t:
            continue
        if any(k in low for k in ("seller details", "dhaka", "bangladesh", "availability", "listed a week ago")):
            continue
        seen_names.add(t)
        parent = el.find_parent(["div", "li", "span"])
        ctx = parent.get_text(" ", strip=True)[:60] if parent else ""
        name_scan.append({
            "name": t,
            "cls": " ".join(el.get("class") or [])[:50],
            "ctx": ctx,
        })
    seller_context = dict(seller_context or {}) | {
        "name_scan": name_scan[:25],
    }

    return {
        "url": str(url),
        "html_len": len(html),
        "title": title,
        "listing_images_count": len(listing_imgs),
        "listing_images": listing_imgs[:12],
        "total_img_count": len(img_urls),
        "price_in_listing_region": list(dict.fromkeys(p["text"] for p in price_nodes))[:15],
        "description_candidates_non_rec": (sorted(desc_final, key=len, reverse=True) or [None])[:6],
        "seller_context": seller_context,
    }
