"""Scraper implementation for Bikroy (bikroy.com).

Bikroy single-item pages render most content client-side too, so we use
Playwright for the DOM and parse with BeautifulSoup. Product prices on Bikroy
often show as "Negotiable" — we capture whatever price text is present.
"""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrape_engine.models.schemas import ImageData, ProductData, SellerInfo
from scrape_engine.scrapers.base import BaseScraper


class BikroyScraper(BaseScraper):
    name = "bikroy"

    async def scrape(self) -> ProductData:
        html = await self._fetch_with_playwright()
        return await self.extract(html)

    async def extract(self, html: str) -> ProductData:
        soup = self.soup(html)

        title = self._extract_title(soup)
        price = self._extract_price(soup)
        currency = "BDT"  # Bikroy operates in Bangladesh (Taka).
        description = self._extract_description(soup)
        images = await self._extract_images(soup)
        seller = self._extract_seller(soup, html)

        return ProductData(
            title=title or self.make_slug("bikroy-item"),
            source=self.name,
            url=self.page_url,
            price=price,
            currency=currency,
            description=description,
            images=images,
            seller=seller,
            meta={"scraper": self.name},
        )

    # ------------------------------------------------------------------
    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        og = soup.select_one('meta[property="og:title"]')
        if og and og.get("content"):
            return og["content"]
        h1 = soup.select_one("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)
        return None

    def _extract_price(self, soup: BeautifulSoup) -> str | None:
        selectors = [
            "div[class*='amount']",
            "span[class*='price']",
            "div[class*='price']",
            "span[data-testid='price']",
        ]
        for sel in selectors:
            for node in soup.select(sel):
                text = node.get_text(" ", strip=True)
                if text and any(ch.isdigit() for ch in text):
                    return text
        return None

    def _extract_description(self, soup: BeautifulSoup) -> str | None:
        metas = [
            'meta[property="og:description"]',
            'meta[name="description"]',
        ]
        for meta in metas:
            node = soup.select_one(meta)
            if node and node.get("content"):
                text = node["content"].strip()
                if text:
                    return text
        # Fall back to an element that looks like the description block.
        container = soup.select_one(
            "section[class*='description'], div[class*='description'], div[data-testid='description']"
        )
        if container:
            for tag in container.find_all(["script", "style"]):
                tag.decompose()
            text = container.get_text("\n", strip=True)
            if text:
                return text
        return None

    def _extract_seller(self, soup: BeautifulSoup, raw_html: str) -> SellerInfo:
        seller = SellerInfo()

        name = soup.select_one("[class*='seller-block__name']")
        if name and name.get_text(strip=True):
            seller.name = name.get_text(strip=True)

        profile = soup.select_one("a[href*='/sellerpage-'], a[href*='/member-']")
        if profile:
            href = profile.get("href")
            if href:
                seller.profile_url = urljoin(self.page_url, href)

        avatar = soup.select_one(
            "[class*='seller-avatar'] img, [class*='seller-block__avatar'] img"
        )
        if avatar:
            src = avatar.get("src") or avatar.get("data-src") or avatar.get("data-lazy-src")
            if src:
                seller.avatar_url = urljoin(self.page_url, src)

        badge = soup.select_one("[class*='seller-badge']")
        if badge and badge.get_text(strip=True):
            seller.badge = badge.get_text(strip=True)

        # Bikroy shows the seller's join age and response speed in labels, e.g.
        # "New on Bikroy" and "Typically replies within a few hours".
        resp = soup.find(string=self._is_response_time)
        if resp:
            resp_el = resp.parent
            # Prefer the closest sized label element containing the text.
            parent_text = resp_el.get_text(" ", strip=True) if resp_el else ""
            if len(parent_text) > 60 and resp_el.find_parent(["div", "span"]):
                resp_el = resp_el.find_parent(["div", "span"])
            seller.response_time = resp_el.get_text(" ", strip=True)[:80] if resp_el else resp.strip()

        # Listing region, e.g. "Rangpur, Jahaj Company More, 23/08".
        region = soup.select_one("[class*='info-statistics--region']")
        if region and region.get_text(" ", strip=True):
            seller.location = self._split_date(region.get_text(" ", strip=True))

        # The phone is embedded in the Nuxt page state even though the
        # "Show contact" button is gated behind login.
        seller.phone = self._extract_phone(raw_html)

        return seller

    @staticmethod
    def _split_date(text: str) -> str | None:
        """Separate a trailing DD/MM (or DD Month) date from a location string."""
        import re

        parts = [p.strip() for p in text.split(",")]
        if len(parts) >= 2 and re.match(r"^\d{1,2}/\d{2}$", parts[-1]):
            return ", ".join(parts[:-1])
        return text

    @staticmethod
    def _is_response_time(text: str) -> bool:
        t = (text or "").strip().lower()
        return "typically replies" in t or "replies within" in t

    @staticmethod
    def _extract_phone(raw_html: str) -> str | None:
        """Find a Bangladesh mobile number anywhere in the page's raw HTML.

        Bikroy embeds the seller's contact into the Nuxt serialized state, so a
        ``01XXXXXXXXX`` pattern is typically present without needing to click
        the gated "Show contact" button.
        """
        import re

        match = re.search(r"\b(?<![\d/])01[3-9]\d{8}\b", raw_html)
        return match.group(0) if match else None

    def _image_urls(self, soup: BeautifulSoup) -> list[str]:
        seen: set[str] = set()
        seen_picture_id: set[str] = set()
        urls: list[str] = []

        # Gallery images are frequently lazy-loaded with data attributes.
        for node in soup.select("img"):
            src = (
                node.get("src")
                or node.get("data-src")
                or node.get("data-lazy-src")
                or node.get("data-original")
            )
            if not src:
                continue
            url = urljoin(self.page_url, src)
            if not url.startswith("http") or url in seen:
                continue

            from urllib.parse import urlparse

            host = (urlparse(url).hostname or "").lower()
            path = url.split("?", 1)[0].lower()
            # Bikroy listing photos are served from the jijistatic.com CDN.
            # Anything else (tracking pixels, t.co trackers, avatars, GIFs) is
            # not a real product image and is dropped.
            if "jijistatic.com" not in host:
                continue
            if path.endswith((".svg", ".ico", ".gif")):
                continue
            # Thumbnails share the picture numeric id and differ only by size
            # suffix; keep the first (larger) variant per id.
            picture_id = self._picture_id(url)
            if picture_id and picture_id in seen_picture_id:
                continue
            # Skip tiny assets (96px avatars / logos) that aren't listing photos.
            size = self._picture_size(url)
            if size is not None and min(size) < 300:
                continue

            seen.add(url)
            if picture_id:
                seen_picture_id.add(picture_id)
            urls.append(url)

        return urls[:12]

    @staticmethod
    def _picture_id(url: str) -> str | None:
        """Extract the numeric photo id used by Bikroy's CDN.

        e.g. https://pictures-bangladesh.jijistatic.com/7988056_MTIw...webp
        -> "7988056"
        """
        from urllib.parse import urlparse

        path = urlparse(url).path
        filename = path.rsplit("/", 1)[-1]
        if not filename:
            return None
        stem = filename.split("_", 1)[0]
        return stem if stem.isdigit() else None

    @staticmethod
    def _picture_size(url: str) -> tuple[int, int] | None:
        """Decode the image dimensions baked into the jijistatic filename.

        Files look like ``<id>_<base64("<w>-<h>-...")>.<ext>``; the base64 token
        encodes the original width/height. Returns None when it cannot be parsed
        (so callers can treat 'unknown' leniently).
        """
        import base64

        from urllib.parse import urlparse

        filename = urlparse(url).path.rsplit("/", 1)[-1]
        if not filename:
            return None
        stem = filename.rsplit(".", 1)[0]
        parts = stem.split("_")
        if len(parts) < 2:
            return None
        token = parts[1] + "=" * (-len(parts[1]) % 4)
        try:
            decoded = base64.urlsafe_b64decode(token).decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            return None
        dims = decoded.split("-")
        if len(dims) >= 2 and dims[0].isdigit() and dims[1].isdigit():
            return int(dims[0]), int(dims[1])
        return None

    async def _extract_images(self, soup: BeautifulSoup) -> list[ImageData]:
        from scrape_engine.utils.image_utils import download_image

        client = self._get_client()
        images: list[ImageData] = []
        for url in self._image_urls(soup):
            try:
                images.append(await download_image(url, "./media", client))
            except Exception:  # noqa: BLE001 - keep going on a bad image
                images.append(ImageData(url=url))
        return images
