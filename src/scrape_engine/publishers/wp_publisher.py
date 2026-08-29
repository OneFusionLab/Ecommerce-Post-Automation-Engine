"""WordPress REST API integration.

Publishes scraped product data as a formatted blog post:

1. Upload each local image to ``/wp-json/wp/v2/media`` (Basic auth using an
   application password), collecting the returned media IDs.
2. Build post content in HTML, embedding the media as a gallery.
3. Create the post via ``/wp-json/wp/v2/posts``.

Authentication uses WordPress "application passwords" which authenticate as
the user over Basic auth against the REST API.
"""

from __future__ import annotations

import base64
import os

import httpx
from slugify import slugify

from scrape_engine.models.schemas import ProductData, PublishResponse

DEFAULT_TIMEOUT = httpx.Timeout(60.0)


class WPPublisher:
    """Publish :class:`ProductData` to a WordPress site via its REST API."""

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        app_password: str | None = None,
        default_category: int | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("WP_BASE_URL", "")).rstrip("/")
        self.username = username or os.getenv("WP_USERNAME", "")
        self.app_password = app_password or os.getenv("WP_APPLICATION_PASSWORD", "")
        default_cat = default_category
        if default_cat is None:
            raw = os.getenv("WP_DEFAULT_CATEGORY")
            default_cat = int(raw) if raw and str(raw).isdigit() else None
        self.default_category = default_cat
        self.client = client or httpx.AsyncClient(
            follow_redirects=True, timeout=DEFAULT_TIMEOUT
        )

    # ------------------------------------------------------------------
    async def publish(
        self,
        product: ProductData,
        *,
        status: str = "publish",
        category: int | None = None,
    ) -> PublishResponse:
        if not self.base_url or not self.username or not self.app_password:
            return PublishResponse(
                success=False,
                error="WordPress is not configured (check WP_BASE_URL, WP_USERNAME, WP_APPLICATION_PASSWORD).",
            )

        auth_headers = self._auth_headers()

        media_ids: list[int] = []
        for image in product.images:
            if not image.local_path or not os.path.exists(image.local_path):
                continue
            media = await self._upload_media(image.local_path, auth_headers)
            if media:
                media_ids.append(media)

        content_html = self._build_content(product, media_ids)
        slug = slugify(product.title) or "scraped-post"

        payload: dict = {
            "title": product.title,
            "slug": slug,
            "content": content_html,
            "status": status,
            "meta": {"source_url": str(product.url)},
        }
        if category is not None:
            payload["categories"] = [category]
        elif self.default_category is not None:
            payload["categories"] = [self.default_category]
        if media_ids:
            payload["featured_media"] = media_ids[0]

        resp = await self.client.post(f"{self.base_url}/posts", json=payload, headers=auth_headers)
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}

        if resp.status_code in (200, 201):
            return PublishResponse(
                success=True,
                post_id=body.get("id"),
                post_url=body.get("link"),
                status=body.get("status", status),
                media_uploaded=len(media_ids),
            )

        return PublishResponse(
            success=False,
            error=body.get("message") or body.get("code") or f"HTTP {resp.status_code}",
            media_uploaded=len(media_ids),
        )

    # ------------------------------------------------------------------
    async def _upload_media(self, local_path: str, headers: dict[str, str]) -> int | None:
        try:
            with open(local_path, "rb") as fh:
                data = fh.read()
        except OSError:
            return None

        filename = os.path.basename(local_path)
        media_type = self._guess_mime(filename)
        resp = await self.client.post(
            f"{self.base_url}/media",
            headers={**headers, "Content-Type": media_type, "Content-Disposition": f'attachment; filename="{filename}"'},
            content=data,
        )
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code in (200, 201) and body.get("id"):
            return int(body["id"])
        return None

    # ------------------------------------------------------------------
    def _build_content(self, product: ProductData, media_ids: list[int]) -> str:
        return build_post_content_html(product, media_ids)

    @staticmethod
    def _guess_mime(filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
        }.get(ext, "application/octet-stream")

    def _auth_headers(self) -> dict[str, str]:
        token = base64.b64encode(f"{self.username}:{self.app_password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    async def aclose(self) -> None:
        await self.client.aclose()


def build_post_content_html(
    product: ProductData, media_ids: list[int] | None = None
) -> str:
    """Render a product into HTML for both DB persistence and the WP publish
    payload. When ``media_ids`` (WordPress media IDs) are provided they are used
    to build a native gallery; otherwise remote CDN URLs are embedded."""
    parts: list[str] = []

    if product.images:
        parts.append(
            _gallery_html(media_ids)
            if media_ids
            else _remote_images_html(product)
        )

    if product.price:
        price_row = f"<p><strong>Price:</strong> {product.price}"
        if product.currency:
            price_row += f" ({product.currency})"
        price_row += "</p>"
        parts.append(price_row)

    parts.append(f'<p><a href="{product.url}">View original listing</a></p>')

    if product.description:
        parts.append(_paragraphs(product.description))

    return "\n\n".join(parts)


def _gallery_html(media_ids: list[int]) -> str:
    gallery = '[gallery ids="' + ",".join(str(i) for i in media_ids) + '"]'
    return f"<!-- wp:gallery -->{gallery}<!-- /wp:gallery -->"


def _remote_images_html(product: ProductData) -> str:
    imgs = "".join(
        f'<img src="{img.url}" alt="{product.title}" loading="lazy" />'
        for img in product.images
        if img.url
    )
    return f'<div class="scrape-gallery">{imgs}</div>'


def _paragraphs(text: str) -> str:
    blocks = [b.strip() for b in text.split("\n") if b.strip()]
    if not blocks:
        return f"<p>{text}</p>"
    return "\n\n".join(f"<p>{b}</p>" for b in blocks)
