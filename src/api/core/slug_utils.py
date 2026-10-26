"""Helpers for stable, editable slugs derived from Vietnamese display names."""

from __future__ import annotations

from django.utils.text import slugify


def make_slug(name: str, custom_slug: str | None = None, *, max_length: int = 160) -> str:
    """Use an optional operator-edited slug, or derive one from the display name.

    The database's unique constraint remains the final guard against collisions.
    """
    source = (custom_slug or "").strip() or (name or "").strip()
    source = source.replace("đ", "d").replace("Đ", "D")
    value = slugify(source, allow_unicode=False)[:max_length].strip("-")
    if not value:
        raise ValueError("Không thể tạo slug từ tên hoặc slug được cung cấp.")
    return value
