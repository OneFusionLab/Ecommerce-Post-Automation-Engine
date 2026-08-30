"""Facebook Marketplace scraper backed by a manually-authenticated session.

Facebook's Marketplace is login-gated and heavily bot-protected, so it cannot
be fetched anonymously like Daraz/Bikroy. Instead this adapter uses a real,
*visible* Chromium browser and a persistent session-cookie file:

1. ``login()``  - Open facebook.com/login in a visible browser and wait for the
                  user to sign in interactively. The resulting session cookies
                  are saved to a JSON file for reuse.
2. ``scrape()`` - Launch a browser seeded with the saved session cookies, then
                  parse the listing's title, price, images and seller.

Session files live under MEDIA_DIR (``fb_session_cookies.json``).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scrape_engine.models.schemas import ImageData, ProductData, SellerInfo
from scrape_engine.scrapers.base import BaseScraper

DEFAULT_SESSION_FILENAME = "fb_session_cookies.json"

# Cookie that Facebook sets when the user is authenticated.
_AUTH_COOKIE = "c_user"
_LOGIN_URL = "https://www.facebook.com/login"
_CHECK_INTERVAL_S = 2.0


def _session_file_path() -> Path:
    media = os.getenv("MEDIA_DIR", "./media")
    return Path(media) / DEFAULT_SESSION_FILENAME


def session_status() -> dict:
    """Return (logged_in, cookie_file, cookie_count) for the saved session."""
    path = _session_file_path()
    if not path.exists():
        return {"logged_in": False, "cookie_file": str(path), "cookie_count": 0}
    try:
        cookies = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - corrupt file -> treat as logged out
        return {"logged_in": False, "cookie_file": str(path), "cookie_count": 0}
    authed = any(c.get("name") == _AUTH_COOKIE for c in cookies)
    return {
        "logged_in": authed,
        "cookie_file": str(path),
        "cookie_count": len(cookies),
    }


def _launch_kwargs(headless: bool, proxy_url: str | None) -> dict:
    kwargs: dict = {"headless": headless}
    if proxy_url:
        kwargs["proxy"] = {"server": proxy_url}
    return kwargs


async def login(timeout: int = 180, *, headless: bool = False, proxy_url: str | None = None) -> dict:
    """Open Facebook in a visible browser and wait for the user to sign in.

    Blocks until the ``c_user`` cookie appears (or ``timeout`` elapses), then
    persists all session cookies to disk.
    """
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Playwright is not installed. Run: uv run playwright install"
        ) from exc

    path = _session_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(**_launch_kwargs(headless, proxy_url))
        try:
            context = await browser.new_context(
                viewport={"width": 1366, "height": 900},
                locale="en-US",
            )
            page = await context.new_page()
            await page.goto(_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)

            elapsed = 0.0
            while elapsed < timeout:
                await page.wait_for_timeout(int(_CHECK_INTERVAL_S * 1000))
                elapsed += _CHECK_INTERVAL_S
                cookies = await context.cookies()
                if any(c.get("name") == _AUTH_COOKIE for c in cookies):
                    _save_cookies(cookies)
                    return {
                        "logged_in": True,
                        "message": "Logged in and Facebook session saved.",
                        "cookies_saved": True,
                    }

            return {
                "logged_in": False,
                "message": (
                    f"Login timed out after {timeout}s. The browser is now "
                    "closed; run login again when you are ready."
                ),
                "cookies_saved": False,
            }
        finally:
            await browser.close()


def _save_cookies(cookies: list[dict]) -> None:
    path = _session_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([_serializable_cookie(c) for c in cookies]),
        encoding="utf-8",
    )


def _serializable_cookie(cookie: dict) -> dict:
    """Return a JSON-safe copy of a Playwright cookie dict."""
    keep = ("name", "value", "domain", "path", "expires")
    return {k: cookie.get(k) for k in keep}


class FacebookScraper(BaseScraper):
    """Scrape a Facebook Marketplace listing using a saved logged-in session."""

    name = "facebook"

    # Forces the browser (never the anonymous httpx path).
    async def scrape(self) -> ProductData:
        html = await self._fetch_with_session()
        return await self.extract(html)

    async def fetch_session_html(self) -> str:
        """Fetch and return the raw HTML using the saved session (debugging)."""
        return await self._fetch_with_session()

    # ------------------------------------------------------------------
    # Fetching with a logged-in session
    # ------------------------------------------------------------------
    async def _fetch_with_session(self) -> str:
        status = session_status()
        if not status["logged_in"]:
            raise RuntimeError(
                "No Facebook session found. Log in first via POST "
                "/scrape/facebook/login, then re-run the scrape."
            )

        try:
            from playwright.async_api import async_playwright  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Playwright is not installed. Run: uv run playwright install"
            ) from exc

        cookies = self._load_cookies()
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                **_launch_kwargs(self.headless, self.proxy_url)
            )
            try:
                context = await browser.new_context(
                    viewport={"width": 1366, "height": 900},
                    locale="en-US",
                )
                await context.add_cookies(cookies)
                page = await context.new_page()
                await page.goto(
                    self.page_url, wait_until="domcontentloaded", timeout=60000
                )
                # Give the logged-in content a moment to hydrate.
                await page.wait_for_timeout(5000)
                return await page.content()
            finally:
                await browser.close()

    def _load_cookies(self) -> list[dict]:
        path = _session_file_path()
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return []
        return [
            {
                "name": c.get("name"),
                "value": c.get("value"),
                "domain": c.get("domain"),
                "path": c.get("path") or "/",
                "expires": c.get("expires") or -1,
            }
            for c in raw
            if c.get("name") and c.get("value") is not None
        ]

    # ------------------------------------------------------------------
    # Extraction (best-effort; leans on og: meta tags shared on listings)
    # ------------------------------------------------------------------
    async def extract(self, html: str) -> ProductData:
        soup = self.soup(html)

        title = self._extract_title(soup)
        price = self._extract_price(soup)
        currency = self._extract_currency(soup)
        description = self._extract_description(soup)
        images = await self._extract_images(soup)
        seller = self._extract_seller(soup)

        return ProductData(
            title=title or self.make_slug("facebook-marketplace-listing"),
            source=self.name,
            url=self.page_url,
            price=price,
            currency=currency,
            description=description,
            images=images,
            seller=seller,
            meta={
                "scraper": self.name,
                "full_title": title,
                "session_based": True,
            },
        )

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        for sel in ("h1", "[data-testid*='ad-title']", "div[class*='title'] h1"):
            node = soup.select_one(sel)
            if node and node.get_text(strip=True):
                return node.get_text(strip=True)
        og = soup.select_one('meta[property="og:title"]')
        if og and og.get("content"):
            return og["content"]
        return None

    _CURRENCY_SYMBOLS = {
        "$": "USD", "€": "EUR", "£": "GBP", "৳": "BDT", "₹": "INR",
        "₩": "KRW", "₺": "TRY", "₱": "PHP", "R$": "BRL", "RM": "MYR",
    }

    def _extract_price(self, soup: BeautifulSoup) -> str | None:
        # 1) Structured meta (when present on shared listings).
        node = soup.select_one('meta[property="product:price:amount"]')
        if node and node.get("content"):
            cur = self._extract_currency(soup) or ""
            return f"{cur} {node['content']}".strip()

        # 2) Scan DOM for a currency+amount pattern. The listing's price is the
        #    first *currency-labeled* amount in document order (the "Today's
        #    picks" recommendations sit below/after it). We require a currency
        #    marker so bare numbers like "3000" are never mistaken for a price.
        price_pat = re.compile(
            r"(?:(?:BDT|Tk|Taka)\s?|[$€£৳₹₩₺₱]|R\$|RM)\s?\d+(?:[\.,]\d+)*"
            r"(?:\s?(?:[$€£৳₹₩₺₱]|BDT|Tk|USD|EUR|GBP))?",
            re.I,
        )
        for el in soup.select(
            "span, div, li, h2, h3, span[dir='ltr'], div[style*='font-size']"
        ):
            text = el.get_text(" ", strip=True)
            if not text or len(text) > 60:
                continue
            m = price_pat.fullmatch(re.sub(r"\s+", " ", text).strip())
            if m:
                val = m.group(0).strip()
                if val:
                    return val or None
        return None

    def _extract_currency(self, soup: BeautifulSoup) -> str | None:
        node = soup.select_one('meta[property="product:price:currency"]')
        if node and node.get("content"):
            return node["content"].upper()
        price = self._extract_price(soup) or ""
        for sym, code in self._CURRENCY_SYMBOLS.items():
            if sym in price:
                return code
        if re.match(r"(BDT|Tk|Taka)\s?\d", price, re.I):
            return "BDT"
        return None

    def _extract_description(self, soup: BeautifulSoup) -> str | None:
        # 1) og:description / meta description.
        for sel in (
            'meta[property="og:description"]',
            'meta[name="description"]',
            'meta[name="twitter:description"]',
        ):
            node = soup.select_one(sel)
            if node and node.get("content") and len(node["content"]) > 20:
                candidate = node["content"].strip()
                if candidate and len(candidate) > 20:
                    return candidate

        # 1b) The listing description sits just before a "See more"/"See less"
        #     truncation control (Facebook collapses long descriptions).
        trunc = None
        for node in soup.find_all(string=re.compile(r"^(See more|See less)$", re.I)):
            t = str(node).strip()
            if t.lower() in ("see more", "see less"):
                trunc = node
                break
        if trunc:
            block = None
            for lev in range(1, 7):
                anc = trunc.find_parent("div")
                if anc is None:
                    break
                ancestor = anc
                for _ in range(lev):
                    ancestor = ancestor.find_parent(["div", "li", "section"]) if ancestor else None
                if ancestor is None:
                    break
                text = ancestor.get_text("\n", strip=True)
                # The description is the text BEFORE the "See more" control,
                # and it should not be the whole recommendations feed.
                pre = re.split(r"See more\b", text, flags=re.I)[0].strip()
                if (
                    len(pre) >= 25
                    and pre.lower().count(" in ") <= 2
                    and "today's picks" not in pre.lower()
                ):
                    block = " ".join(pre.split())
                    break
            if block:
                return block[:2000]

        # 2) Longest meaningful text block (listing descriptions are paragraphs).
        #    Skip the "Today's picks" recommendation feed, which is a big block
        #    joining many "<other item> in <location>" + prices.
        best = None
        best_len = 0
        for el in soup.select("div[dir='auto'], p, div[class*='description'], div[class*='About']"):
            text = el.get_text(" ", strip=True)
            if not text or len(text) < 30:
                continue
            if any(k in text.lower() for k in ("log in", "sign up", "cookies")):
                continue
            # Skip the recommendations feed / grouped other-listings text.
            if (
                len(text) > 250
                and (text.lower().count(" in ") > 2 or "today's picks" in text.lower())
            ):
                continue
            if len(text) > best_len:
                best = text
                best_len = len(text)
        return best[:2000] if best else None

    async def _extract_images(self, soup: BeautifulSoup) -> list[ImageData]:
        urls: list[str] = []
        seen_alts: set[str] = set()

        # 1) Primary signal: <img> marked "Product photo of ...". Facebook
        #    tags the listing's OWN gallery this way, while the page is flooded
        #    with "Today's picks" recommendation cards (alt="... in Dhaka").
        #    This filter cleanly keeps only the actual product photos.
        for node in soup.find_all("img"):
            alt = (node.get("alt") or "").strip()
            if alt.lower().startswith("product photo of "):
                key = alt + "|" + (node.get("src") or "")
                if key in seen_alts:
                    continue
                seen_alts.add(key)
                src = node.get("src") or node.get("data-src")
                if src:
                    urls.append(src)

        # 2) Fallbacks (used only if the "Product photo of" markers are absent).
        if not urls:
            for prop in ("og:image", "og:image:secure_url", "og:image:url", "twitter:image"):
                node = soup.select_one(f'meta[property="{prop}"], meta[name="{prop}"]')
                if node and node.get("content"):
                    urls.append(node["content"])

            cdn_imgs = soup.select(
                "img[src*='fbcdn.net'], img[src*='scontent'], img[src*='lookaside'], "
                "img[data-src*='fbcdn.net'], img[data-src*='scontent'], img[data-src*='lookaside']"
            )
            for node in cdn_imgs:
                src = node.get("src") or node.get("data-src")
                if src:
                    urls.append(src)

            for node in soup.select("div[style*='background-image']"):
                style = node.get("style", "")
                m = re.search(r"url\(['\"]?(https?://[^)'\"]+)['\"]?\)", style, re.I)
                if m:
                    urls.append(m.group(1))

        # Normalize + filter to real product photos.
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in urls:
            url = urljoin(self.page_url, raw)
            if not url.startswith("http"):
                continue
            key = self._photo_key(url)
            if key in seen:
                continue
            if self._looks_like_photo(url):
                seen.add(key)
                cleaned.append(url)

        # Dedupe by path.
        deduped: list[str] = []
        seen_path: set[str] = set()
        for url in cleaned:
            path = urlparse(url).path
            if path not in seen_path:
                seen_path.add(path)
                deduped.append(url)

        images: list[ImageData] = []
        for url in deduped[:12]:
            images.append(ImageData(url=url))
        return images

    @staticmethod
    def _photo_key(url: str) -> str:
        """A stable key for a photo URL ignoring fbcdn size params quirks."""
        parsed = urlparse(url)
        return f"{parsed.hostname}{parsed.path}"

    @staticmethod
    def _looks_like_photo(url: str) -> bool:
        """Keep real photos, drop FB icons/avatars/sprites/tiny thumbnails."""
        lowered = url.lower()
        junk = (
            "/static_facebook.",
            "/static.xx.",
            "emoji",
            "avataaars",
            "/p50x50",
            "/p100x100",
            "/rsrc.php",
            "/sprite",
            "_q.md",
        )
        if any(j in lowered for j in junk):
            return False
        # Product photos on fbcdn use /v/ versioned paths or lookaside or
        # scontent; also accept og:image from other hosts.
        return "fbcdn.net" in lowered or "lookaside" in lowered or "scontent" in lowered

    def _extract_seller(self, soup: BeautifulSoup) -> SellerInfo:
        seller = SellerInfo()

        # Profile URL — almost always present as a link into the seller's page.
        prof_link = (
            soup.select_one("a[href*='profile.php']")
            or soup.select_one("a[href*='/profile/']")
            or soup.select_one("a[href*='/people/']")
        )
        if prof_link:
            href = prof_link.get("href")
            seller.profile_url = urljoin(self.page_url, href) if href else None

        # Seller / author from og / structured data.
        og_seller = soup.select_one('meta[property="article:author"], meta[name="author"]')
        if og_seller and og_seller.get("content"):
            seller.name = og_seller["content"]

        # Location often appears between seller name and 'Seller information'.
        loc = (
            soup.select_one("div[data-testid*='location']")
            or soup.select_one("div[class*='location']")
            or soup.select_one("span[dir*='ltr']")
        )

        # Name: look in a container near seller/testid, largest short text.
        if not seller.name:
            for sel in (
                "div[data-testid*='seller']",
                "div[data-testid*='marketplace_pdp']",
                "[data-testid*='seller-name']",
                "div[class*='SellerProfile']",
            ):
                node = soup.select_one(sel)
                if not node:
                    continue
                # Prefer an explicit link/strong text, else the first meaningful text.
                text = node.get_text(" ", strip=True)
                if text:
                    seller.name = self._pick_seller_name(text)
                if seller.name:
                    break

        # Name fallback: the seller's display name is usually the text immediately
        # before the "Seller details" heading, or tied to their profile link.
        if not seller.name:
            seller_heading = soup.find(string=re.compile(r"Seller details", re.I))
            if seller_heading:
                node = seller_heading.find_parent(["div", "li"])
                if node:
                    # Grab text from the profile link within/near this block.
                    prof = node.select_one("a[href*='profile'], a[href*='people']")
                    if prof:
                        txt = prof.get_text(" ", strip=True)
                        if self._is_person_name(txt):
                            seller.name = txt

        # Marketplace "Seller information" card: the name reads "<Name> ( nn )"
        # (e.g. "Yusuf Hasan Sifat ( 11 )") or "<Name> Joined Facebook in YYYY"
        # / "<Name> Member since YYYY" (e.g. "Shourov Rahman Joined Facebook
        # in 2011"). Extract the leading name.
        if not seller.name:
            name_pat = re.compile(
                r"^\s*([A-Za-z][A-Za-z .'\-]{1,40}?)"
                r"\s*(?:\(\s*\d|Joined\b|Member since\b)",
                re.I,
            )
            for el in soup.find_all(["div", "span"]):
                txt = el.get_text(" ", strip=True)
                m = name_pat.match(txt)
                if not m:
                    continue
                cand = m.group(1).strip()
                if 3 <= len(cand) <= 40 and cand.lower() not in ("seller", "seller details", "profile"):
                    seller.name = cand
                    break

        return seller

    @staticmethod
    def _is_person_name(text: str) -> bool:
        """Heuristic: a short human name (2-4 words, letters only, no numbers)."""
        t = text.strip()
        low = t.lower()
        if any(k in low for k in ("seller details", "marketplace", "profile", "seller", "buying", "selling")):
            return False
        words = [w for w in re.split(r"\s+", t) if w]
        if not 1 <= len(words) <= 5:
            return False
        return all(w.isalpha() or "'" in w or "-" in w or "." in w and w.endswith(".") for w in words)

    @staticmethod
    def _pick_seller_name(text: str) -> str | None:
        """Return the most likely seller name (a multi-word human name,
        never a heading like "Seller details" or a stray single token)."""
        if not text:
            return None
        low = text.lower()
        if any(k in low for k in (
            "seller details", "seller information", "member since",
            "marketplace", "notification", "inbox", "buy and sell",
        )):
            return None
        skip_tokens = {"seller", "marketplace", "profile", "details", "member", "since"}
        # Split into whitespace runs; pick the longest run of alphabetic words.
        best = ""
        for chunk in re.split(r"[\s]+", text.strip()):
            token = chunk.strip(" ()\n\t")
            if not token or not token.replace(".", "").replace("-", "").replace("'", "").isalpha():
                continue
            if token.lower() in skip_tokens:
                continue
            if len(token) < 2:
                continue
            # Grow the best run while tokens remain consecutive.
            best = token
        # Prefer a full multi-word name if we can spot one as "<A B C> ( n )".
        m = re.match(r"^([A-Za-z][A-Za-z .'\-]{1,50}?)\s*\(\s*\d", text)
        if m:
            cand = m.group(1).strip()
            if 3 <= len(cand) <= 40 and "seller" not in cand.lower():
                return cand
        if best and not any(k in best.lower() for k in ("seller", "details", "marketplace", "member")):
            return best
        return None

    @staticmethod
    def _dedupe(urls: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for url in urls:
            base = urlparse(url).path
            if base not in seen:
                seen.add(base)
                out.append(url)
        return out
