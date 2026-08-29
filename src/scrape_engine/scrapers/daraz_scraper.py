"""Scraper implementation for Daraz (daraz.com / daraz.com.bd / daraz.lk ...).

Daraz product pages are heavily JS-rendered and are somewhat bot-protected, so
we rely primarily on Playwright to obtain the rendered DOM, then parse with
BeautifulSoup.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scrape_engine.models.schemas import ImageData, ProductData
from scrape_engine.scrapers.base import BaseScraper


class DarazScraper(BaseScraper):
    name = "daraz"

    async def scrape(self) -> ProductData:
        # Override to force the browser path for JS-heavy Daraz pages.
        html = await self._fetch_with_playwright()
        return await self.extract(html)

    async def extract(self, html: str) -> ProductData:
        soup = self.soup(html)

        title = self._extract_title(soup)
        price = self._extract_price(soup)
        currency = self._extract_currency(soup)
        description = self._extract_description(soup)
        images = await self._extract_images(soup)

        return ProductData(
            title=title or self.make_slug("daraz-product"),
            source=self.name,
            url=self.page_url,
            price=price,
            currency=currency,
            description=description,
            images=images,
            meta={"scraper": self.name, "full_title": title},
        )

    # ------------------------------------------------------------------
    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        # Daraz uses a h1 inside a specific container.
        selectors = [
            "h1",
            "[data-spm*='productTitle']",
            "div[class*='pdp-mod-product-badge']",  # sometimes wraps title
        ]
        for sel in selectors:
            node = soup.select_one(sel)
            if node and node.get_text(strip=True):
                return node.get_text(strip=True)
        # Fallback to open-graph title.
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title and og_title.get("content"):
            return og_title["content"]
        return None

    def _extract_price(self, soup: BeautifulSoup) -> str | None:
        selectors = [
            "span.pdp-price",
            "span[class*='pdp-price']",
            "div[class*='pdp-product-price'] span",
            "span[data-qa='pdp-price']",
        ]
        for sel in selectors:
            node = soup.select_one(sel)
            if node:
                text = node.get_text(strip=True)
                if text:
                    return text
        return None

    def _extract_currency(self, soup: BeautifulSoup) -> str | None:
        price = self._extract_price(soup)
        if price:
            for symbol in (u"\u09f3", "৳", "Rs.", "Rp", "RM", "₱", "₹", "PKR", "LKR"):
                if symbol in price:
                    # Give back a normalized currency hint.
                    hints = {
                        u"\u09f3": "BDT",
                        "৳": "BDT",
                        "Rs.": "PKR",
                        "Rp": "IDR",
                        "RM": "MYR",
                        "₱": "PHP",
                        "₹": "INR",
                        "PKR": "PKR",
                        "LKR": "LKR",
                    }
                    return hints.get(symbol) or symbol
        return None

    def _extract_description(self, soup: BeautifulSoup) -> str | None:
        # The detailed description region; fall back to a generic selector.
        container = soup.select_one("div[class*='detail-content'], div#module_product_detail")
        if container:
            # Drop script/style noise.
            for tag in container.find_all(["script", "style"]):
                tag.decompose()
            text = container.get_text("\n", strip=True)
            if text:
                return text
        meta_desc = soup.select_one('meta[name="description"]')
        if meta_desc and meta_desc.get("content"):
            return meta_desc["content"]
        return None

    async def _extract_images(self, soup: BeautifulSoup) -> list[ImageData]:
        seen: set[str] = set()
        urls: list[str] = []

        # Daraz stores the preview thumbnails and the main gallery in <img>/JSON.
        for node in soup.select("div[class*='gallery'] img, div[class*='pdp'] img"):
            src = node.get("src") or node.get("data-src") or node.get("data-lazy-src")
            url = urljoin(self.page_url, src) if src else None
            if url and url.startswith("http") and url not in seen:
                seen.add(url)
                urls.append(url)

        # Dedupe list-style thumbnails: keep only the largest variant if a
        # thumbnail and full image share the same base path.
        cleaned = self._prefer_large_variants(urls)

        client = self._get_client()
        images: list[ImageData] = []
        for url in cleaned[:12]:
            try:
                from scrape_engine.utils.image_utils import download_image

                images.append(await download_image(url, "./media", client))
            except Exception:  # noqa: BLE001 - skip one bad image, keep the rest
                # Record the URL as metadata even if download failed.
                images.append(ImageData(url=url))
        return images

    @staticmethod
    def _prefer_large_variants(urls: list[str]) -> list[str]:
        """Dedupe images that share the same normalized resource path.

        Daraz often serves the same photo via multiple thumbnail sizes;
        collapsing them keeps the list clean while preserving order.
        """
        seen_base: set[str] = set()
        result: list[str] = []
        for url in urls:
            parts = urlparse(url)
            segments = [seg for seg in parts.path.split("/") if seg not in ("", ".")]
            while ".." in segments:
                idx = segments.index("..")
                segments = segments[: max(0, idx - 1)] + segments[idx + 1 :]
            base = "/".join(segments)
            if base not in seen_base:
                seen_base.add(base)
                result.append(url)
        return result
