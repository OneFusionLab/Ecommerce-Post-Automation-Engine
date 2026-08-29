"""Pydantic schemas for requests and responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class ScrapeRequest(BaseModel):
    """Incoming request: a URL to scrape.

    The ``source`` is optional — if omitted the scraper is auto-detected
    from the hostname (daraz.* / bikroy.com* / generic fallback).
    """

    url: HttpUrl
    source: Literal["daraz", "bikroy", "generic"] | None = None
    publish: bool = Field(default=False, description="If True, publish to WordPress after scraping.")


class ImageData(BaseModel):
    """A single product image."""

    url: HttpUrl | None = None
    local_path: str | None = None
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None
    format: str | None = None


class SellerInfo(BaseModel):
    """Seller / advertiser information scraped from the listing."""

    name: str | None = None
    phone: str | None = None
    location: str | None = None
    profile_url: str | None = None
    avatar_url: str | None = None
    badge: str | None = None
    member_since: str | None = None
    response_time: str | None = None


class ProductData(BaseModel):
    """Normalized product data returned by every scraper."""

    title: str
    source: str
    url: HttpUrl
    price: str | None = None
    currency: str | None = None
    description: str | None = None
    images: list[ImageData] = Field(default_factory=list)
    seller: SellerInfo = Field(default_factory=SellerInfo)
    meta: dict[str, Any] = Field(default_factory=dict)


class PublishResponse(BaseModel):
    """Result of a WordPress REST API publish."""

    success: bool
    post_id: int | None = None
    post_url: str | None = None
    status: str | None = None
    error: str | None = None
    media_uploaded: int = 0


class ScrapeResponse(BaseModel):
    """Top-level response combining scrape + optional publish results."""

    product: ProductData
    published: bool = False
    publish_detail: PublishResponse | None = None
