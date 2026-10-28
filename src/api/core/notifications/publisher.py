"""Append-only, idempotent notification event writer for an existing site transaction."""

from __future__ import annotations

import hashlib
import re


_CATEGORIES = {
    "system", "tuition", "account", "teacher", "enrollment", "class",
    "grade", "transfer", "payment", "security",
}
_SEVERITIES = {"info", "success", "warning", "critical"}
_AUDIENCES = {"admin_all", "admin_big", "admin_small"}
_SITE_CODE = re.compile(r"^[A-Za-z0-9_-]{2,10}$")


def publish_notification(
    cursor,
    *,
    site_code: str,
    event_key: str,
    category: str,
    title: str,
    message: str,
    severity: str = "info",
    audience: str = "admin_all",
    target_path: str | None = None,
) -> str:
    """Insert one immutable event; safe to call again when a site job is retried."""
    site = str(site_code).strip().upper()
    key = str(event_key).strip()
    category = str(category).strip().lower()
    severity = str(severity).strip().lower()
    audience = str(audience).strip().lower()
    title = str(title).strip()
    message = str(message).strip()
    if not _SITE_CODE.fullmatch(site) or not key or len(key) > 160:
        raise ValueError("Mã site hoặc event_key thông báo không hợp lệ.")
    if category not in _CATEGORIES or severity not in _SEVERITIES or audience not in _AUDIENCES:
        raise ValueError("Loại, mức độ hoặc nhóm nhận thông báo không hợp lệ.")
    if not title or len(title) > 160 or len(message) > 500:
        raise ValueError("Tiêu đề hoặc nội dung thông báo không hợp lệ.")
    if target_path is not None and (not target_path.startswith("/admin/") or len(target_path) > 300):
        raise ValueError("Đường dẫn thông báo phải là đường dẫn nội bộ trong khu vực admin.")

    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    slug = f"{site.lower()}-{category}-{digest}"
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM dbo.ThongBao WITH (UPDLOCK, HOLDLOCK) WHERE event_key = %s
        )
        BEGIN
            INSERT INTO dbo.ThongBao
                (slug, event_key, ma_co_so, danh_muc, muc_do, doi_tuong,
                 tieu_de, noi_dung, duong_dan)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        END
        """,
        [key, slug, key, site, category, severity, audience, title, message, target_path],
    )
    return slug
