"""Image utilities: safe downloading, validation and dimension reading.

Media is downloaded to a local cache directory before being uploaded to
WordPress. Pillow is used to validate that the payload is a real image and
to extract dimensions/format.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError

from scrape_engine.models.schemas import ImageData

_SAFE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
# Maximum accepted image size in bytes (8 MB) — protects against abuse.
MAX_IMAGE_BYTES = 8 * 1024 * 1024
DEFAULT_TIMEOUT = httpx.Timeout(30.0)


async def download_image(
    url: str,
    media_dir: str | Path,
    client: httpx.AsyncClient | None = None,
    max_bytes: int = MAX_IMAGE_BYTES,
) -> ImageData:
    """Download and validate an image, writing it to ``media_dir``.

    Returns an :class:`ImageData` populated with local path and dimensions.
    The HTTP client is created lazily if not provided.
    """
    media_dir_path = Path(media_dir)
    media_dir_path.mkdir(parents=True, exist_ok=True)

    own_client = client is None
    http = client or httpx.AsyncClient(follow_redirects=True, timeout=DEFAULT_TIMEOUT)

    try:
        resp = await http.get(url, headers=browser_headers())
        resp.raise_for_status()

        content = resp.content
        if len(content) > max_bytes:
            raise ValueError(f"Image exceeds {max_bytes // (1024 * 1024)} MB limit: {url}")
        if len(content) == 0:
            raise ValueError(f"Empty body while downloading image: {url}")

        # Validate with Pillow before trusting the payload.
        width, height, fmt = _probe_image(content)

        # Derive a safe filename from a hash of the URL to avoid collisions/weird names.
        filename = _filename_from_url(url, fmt)
        local_path = media_dir_path / filename
        local_path.write_bytes(content)

        return ImageData(
            url=url,
            local_path=str(local_path),
            width=width,
            height=height,
            size_bytes=len(content),
            format=fmt,
        )
    finally:
        if own_client:
            await http.aclose()


def _probe_image(content: bytes) -> tuple[int, int, str]:
    """Return (width, height, format) after validating that content is an image."""
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()
        # verify() closes the file-like, so re-open to read size safely.
        with Image.open(io.BytesIO(content)) as img:
            fmt = (img.format or "UNKNOWN").upper()
            width, height = img.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(f"Payload is not a valid image: {exc}") from exc

    if fmt not in _SAFE_FORMATS:
        raise ValueError(f"Unsupported image format: {fmt}")
    return width, height, fmt


def _filename_from_url(url: str, fmt: str) -> str:
    """Build a unique, websafe local filename for a URL."""
    import hashlib

    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    ext = {"JPEG": "jpg", "GIF": "gif", "PNG": "png", "WEBP": "webp"}.get(fmt, "img")
    return f"{digest}.{ext}"


def browser_headers() -> dict[str, str]:
    """Mimic a real browser to reduce the chance of being blocked."""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }


def local_file_size(path: str) -> int:
    """Return the byte size of a local file, or 0 if it does not exist."""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def as_client(**kwargs: Any) -> httpx.AsyncClient:
    """Create a pre-configured httpx async client with browser-like defaults."""
    kwargs.setdefault("follow_redirects", True)
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    return httpx.AsyncClient(**kwargs)
