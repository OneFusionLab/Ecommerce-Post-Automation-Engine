"""Generic fallback scraper based on HTML meta tags.

Used when the URL host isn't a known e-commerce platform. It prefers the
lightweight httpx fetch and only falls back to Playwright when the page looks
blocked. Open Graph / Twitter Card meta tags provide title, description and
the primary image.
"""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrape_engine.models.schemas import ImageData, ProductData
from scrape_engine.scrapers.base import BaseScraper


class GenericScraper(BaseScraper):
    name = "generic"

    async def extract(self, html: str) -> ProductData:
        soup = self.soup(html)

        title = self._meta(soup, "og:title") or self._title(soup)
        description = (
            self._meta(soup, "og:description")
            or self._meta(soup, "twitter:description")
            or self._meta(soup, "name", "description")
        )
        image_url = self._meta(soup, "og:image") or self._meta(soup, "twitter:image")
        image = await self._first_image(image_url, soup)

        return ProductData(
            title=title or self.make_slug("generic-page"),
            source=self.name,
            url=self.page_url,
            description=description,
            images=[image] if image is not None else [],
            meta={"scraper": self.name, "title": title},
        )

    # ------------------------------------------------------------------
    async def _first_image(
        self, og_image: str | None, soup: BeautifulSoup
    ) -> ImageData | None:
        if og_image:
            url = urljoin(self.page_url, og_image)
            return await self._download(url)
        # Fall back to the first meaningful <img> on the page.
        for node in soup.select("article img, main img, img"):
            src = node.get("src") or node.get("data-src")
            if src and not src.lower().endswith((".svg", ".ico")):
                url = urljoin(self.page_url, src)
                if url.startswith("http"):
                    return await self._download(url)
        return None

    async def _download(self, url: str) -> ImageData | None:
        try:
            from scrape_engine.utils.image_utils import download_image

            return await download_image(url, "./media", self._get_client())
        except Exception:  # noqa: BLE001
            return ImageData(url=url)

    @staticmethod
    def _meta(soup: BeautifulSoup, *keys: str) -> str | None:
        """Read an Open Graph / Twitter / standard meta property or name."""
        for key in keys:
            node = soup.find(
                "meta", attrs={"property": key, "content": True}
            ) or soup.find("meta", attrs={"name": key, "content": True})
            if node:
                value = node["content"].strip()
                if value:
                    return value
        return None

    @staticmethod
    def _title(soup: BeautifulSoup) -> str | None:
        node = soup.find("title")
        if node and node.get_text(strip=True):
            return node.get_text(strip=True)
        return None
