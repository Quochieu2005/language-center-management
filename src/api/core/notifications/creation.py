"""Create admin notifications in existing site-local notification tables."""

from __future__ import annotations

import hashlib

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction

from core.academics.common import append_audit
from core.notifications.publisher import publish_notification
from core.notifications.services import (
    NotificationInfrastructureUnavailable,
    _global_sites,
    _local_site,
)
from core.sites.connections import UnknownSiteError, get_site_database_alias


class NotificationCreateConflict(Exception):
    """An idempotency key was reused with a different notification body."""


def _write_site(*, site_code: str, event_key: str, actor_id: str, notification: dict) -> dict:
    try:
        alias = get_site_database_alias(site_code)
        with transaction.atomic(using=alias), connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT slug, ma_co_so, danh_muc, muc_do, doi_tuong, tieu_de, noi_dung, duong_dan
                FROM dbo.ThongBao WITH (UPDLOCK, HOLDLOCK)
                WHERE event_key = %s
                """,
                [event_key],
            )
            existing = cursor.fetchone()
            expected = (
                site_code, notification["category"], notification["severity"],
                notification["audience"], notification["title"], notification["message"],
                notification["target_path"],
            )
            if existing:
                actual = tuple(str(value) if value is not None else None for value in existing[1:])
                if actual != expected:
                    raise NotificationCreateConflict(
                        "Idempotency-Key đã được dùng cho nội dung thông báo khác."
                    )
                return {"site_code": site_code, "slug": str(existing[0]), "created": False}

            slug = publish_notification(
                cursor,
                site_code=site_code,
                event_key=event_key,
                category=notification["category"],
                severity=notification["severity"],
                audience=notification["audience"],
                title=notification["title"],
                message=notification["message"],
                target_path=notification["target_path"],
            )
            append_audit(
                cursor,
                site_code=site_code,
                actor_id=actor_id,
                action="create_notification",
                table_name="ThongBao",
                record_id=slug,
                after={
                    "slug": slug,
                    "danh_muc": notification["category"],
                    "muc_do": notification["severity"],
                    "doi_tuong": notification["audience"],
                    "tieu_de": notification["title"],
                },
            )
            return {"site_code": site_code, "slug": slug, "created": True}
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise NotificationInfrastructureUnavailable from exc


def create_notification(
    *, role: str, user_site_code: str | None, actor_id: str, idempotency_key: str,
    notification: dict,
) -> dict:
    if role == "admin_small":
        sites, missing = _local_site(user_site_code), ()
    elif role == "admin_big":
        sites, missing = _global_sites()
    else:
        raise PermissionError("Chỉ Admin Big hoặc Admin Small được tạo thông báo.")

    key_material = f"{actor_id}:{role}:{user_site_code or 'global'}:{idempotency_key}"
    event_key = f"manual:{hashlib.sha256(key_material.encode('utf-8')).hexdigest()}"
    results, unavailable = [], list(missing)
    for site in sites:
        try:
            results.append(
                _write_site(
                    site_code=site, event_key=event_key, actor_id=actor_id,
                    notification=notification,
                )
            )
        except NotificationCreateConflict:
            raise
        except NotificationInfrastructureUnavailable:
            unavailable.append(site)

    missing_sites = sorted(set(unavailable))
    return {
        "complete": not missing_sites,
        "site_codes": [item["site_code"] for item in results],
        "missing_sites": missing_sites,
        "results": results,
    }
