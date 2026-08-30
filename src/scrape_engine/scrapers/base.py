"""Abstract base class and shared infrastructure for scrapers.

Every concrete scraper (Daraz, Bikroy, generic) implements
:meth:`BaseScraper.extract`. The base class owns:

* a tiny hostname registry used for auto-detection,
* a lazily-initialized shared matplotlib-free fetch layer built on
  httpx (fast path) and Playwright (fallback for JS-heavy / bot-protected
  pages), and
* helpers to render a full HTML document from raw bytes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Type

import httpx
from bs4 import BeautifulSoup
from slugify import slugify

from scrape_engine.models.schemas import ProductData
from scrape_engine.utils import image_utils


class BaseScraper(ABC):
    """Abstract scraper interface plus shared HTTP/Playwright plumbing."""

    # Identifier used in ProductData.source and request routing.
    name: str = "base"

    def __init__(self, page_url: str, *, headless: bool = True, proxy_url: str | None = None) -> None:
        self.page_url = page_url
        self.headless = headless
        self.proxy_url = proxy_url
        self._client: httpx.AsyncClient | None = None
        self._playwright_available: bool | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def scrape(self) -> ProductData:
        """Fetch the page and extract structured product data."""
        html = await self.fetch_html()
        return await self.extract(html)

    @abstractmethod
    async def extract(self, html: str) -> ProductData:
        """Parse ``html`` into a :class:`ProductData`."""

    # ------------------------------------------------------------------
    # Fetching (httpx fast path + Playwright fallback)
    # ------------------------------------------------------------------
    async def fetch_html(self) -> str:
        """Fetch the page, falling back to a real browser if the fast path
        looks blocked (challenge/cloudflare/403) or the content is empty."""
        client = self._get_client()
        try:
            resp = await client.get(self.page_url)
        except httpx.HTTPError:
            return await self._fetch_with_playwright()

        if resp.status_code in (403, 429, 503) or self._looks_blocked(resp.text):
            return await self._fetch_with_playwright()
        if not resp.text.strip():
            return await self._fetch_with_playwright()
        return resp.text

    def _looks_blocked(self, html: str) -> bool:
        lowered = html[:20_000].lower()
        markers = ("captcha", "cloudflare", "attention required", "enable javascript", "are you a human")
        return any(m in lowered for m in markers)

    async def _fetch_with_playwright(self) -> str:
        """Use a real Chromium via Playwright to defeat basic bot protection."""
        try:
            from playwright.async_api import async_playwright  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Playwright is not installed. Run: uv run playwright install") from exc

        self._playwright_available = True
        kwargs: dict[str, Any] = {"headless": self.headless}
        if self.proxy_url:
            kwargs["proxy"] = {"server": self.proxy_url}

        async with async_playwright() as p:
            browser = await p.chromium.launch(**kwargs)
            try:
                context = await browser.new_context(
                    user_agent=image_utils.browser_headers()["User-Agent"],
                    locale="en-US",
                    viewport={"width": 1366, "height": 900},
                )
                page = await context.new_page()
                # Wait for the network to settle a bit so JS renders the content.
                await page.goto(self.page_url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(4000)
                html = await page.content()
                return html
            finally:
                await browser.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            kwargs: dict[str, Any] = {}
            if self.proxy_url:
                kwargs["proxy"] = self.proxy_url
            self._client = image_utils.as_client(**kwargs)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def make_slug(self, text: str) -> str:
        return slugify(text)

    @staticmethod
    def soup(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    # ------------------------------------------------------------------
    # Registry / auto-detection
    # ------------------------------------------------------------------
    @staticmethod
    def detect(url: str) -> str | None:
        """Return the scraper name for a URL hostname, or None if unknown.

        ``generic`` is the fallback and matches anything else.
        """
        from urllib.parse import urlparse

        host = (urlparse(url).hostname or "").lower()
        if "daraz" in host:
            return "daraz"
        if "bikroy" in host:
            return "bikroy"
        if "facebook" in host or host.startswith("fb.") or "fbclid" in url:
            return "facebook"
        # Generic fallback catches everything else.
        return "generic"

    @staticmethod
    def get_scraper_class(name: str) -> Type["BaseScraper"]:
        from scrape_engine.scrapers.bikroy_scraper import BikroyScraper
        from scrape_engine.scrapers.daraz_scraper import DarazScraper
        from scrape_engine.scrapers.facebook_scraper import FacebookScraper
        from scrape_engine.scrapers.generic_scraper import GenericScraper

        mapping: dict[str, Type[BaseScraper]] = {
            "daraz": DarazScraper,
            "bikroy": BikroyScraper,
            "facebook": FacebookScraper,
            "generic": GenericScraper,
        }
        return mapping[name]
