"""Normalize the binary active/inactive state stored on TaiKhoan."""

from __future__ import annotations

from typing import Any


def account_status_bit(value: Any) -> int | None:
    """Return 1/0 for current BIT values and legacy strings during migration."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value if value in (0, 1) else None
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "active", "hoat_dong"}:
        return 1
    if normalized in {"0", "false", "inactive", "vo_hieu", "khoa"}:
        return 0
    return None


def account_is_active(value: Any) -> bool:
    return account_status_bit(value) == 1


def account_status_label(value: Any) -> str | None:
    bit = account_status_bit(value)
    return "active" if bit == 1 else "inactive" if bit == 0 else None
