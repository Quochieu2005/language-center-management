"""Durable queue for Blog writes that could not reach every active site.

The intent lives in the coordinator's ``Logs`` (like the course queue). ``write_blog`` is idempotent per
``Idempotency-Key``: replaying an intent only writes the sites that have no ACK yet, so the worker just replays.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, connections

from core.blog.services import PublicBlogConflict, PublicBlogNotFound, PublicBlogUnavailable
from core.sites.connections import get_site_database_alias

_INTENT = "BLINT-"
_DONE = "BLFIN-"
_REVIEW = "BLREV-"
_TABLES = {"category": "DanhMucBlog", "article": "BaiVietBlog"}


def _json(value) -> str:
    return json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _registry_alias() -> str:
    return get_site_database_alias(str(settings.AUTH_SESSION_SITE_CODE).strip().upper())


def intent_id(idempotency_key: str) -> str:
    return _INTENT + hashlib.sha256(idempotency_key.encode()).hexdigest()[:64]


def enqueue(alias: str, *, entity: str, action: str, slug: str, payload: dict | None,
            idempotency_key: str, request_hash: str, actor_id: str) -> None:
    """Record the intent once; called inside the write transaction on the coordinator."""
    ma_log = intent_id(idempotency_key)
    with connections[alias].cursor() as cursor:
        cursor.execute("SELECT TOP (1) 1 FROM dbo.Logs WHERE ma_log = %s", [ma_log])
        if cursor.fetchone() is not None:
            return
        cursor.execute("SELECT NEXT VALUE FOR dbo.Seq_NK")
        sequence = int(cursor.fetchone()[0])
        cursor.execute(
            "INSERT INTO dbo.Logs (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, "
            "ma_ban_ghi, du_lieu_moi, dinh_danh_bam, ket_qua) VALUES (%s, 'sync', %s, %s, %s, %s, %s, %s, %s, NULL)",
            [ma_log, str(settings.AUTH_SESSION_SITE_CODE).strip().upper() or None, actor_id, action, _TABLES[entity],
             slug[:100], _json({
                 "queue_kind": "blog_sync", "queue_sequence": sequence, "entity": entity, "slug": slug,
                 "payload": payload, "idempotency_key": idempotency_key,
             }), request_hash],
        )


def _marker(alias: str, ma_log: str, actor_id: str, *, prefix: str, action: str, result: str, detail: str | None = None):
    suffix = ma_log[len(_INTENT):]
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "INSERT INTO dbo.Logs (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, "
            "ma_ban_ghi, du_lieu_moi, ket_qua) VALUES (%s, 'sync', %s, %s, %s, 'BaiVietBlog', %s, %s, %s)",
            [prefix + suffix, str(settings.AUTH_SESSION_SITE_CODE).strip().upper() or None, actor_id, action,
             suffix[:100], _json({"detail": (detail or "")[:500] or None}), result],
        )


def _open_filter() -> str:
    return (
        "AND NOT EXISTS (SELECT 1 FROM dbo.Logs AS closed WHERE closed.ma_log IN "
        "(N'BLFIN-' + SUBSTRING(i.ma_log, 7, 64), N'BLREV-' + SUBSTRING(i.ma_log, 7, 64)))"
    )


def list_pending(alias: str, limit: int = 50) -> list[dict]:
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "SELECT TOP (%s) i.ma_log, i.ma_tai_khoan, i.hanh_dong, i.du_lieu_moi FROM dbo.Logs AS i "
            "WHERE i.loai_log = 'sync' AND LEFT(i.ma_log, 6) = %s " + _open_filter() +
            " ORDER BY COALESCE(TRY_CONVERT(bigint, JSON_VALUE(i.du_lieu_moi, '$.queue_sequence')), 0), i.thoi_diem_utc, i.ma_log",
            [limit, _INTENT],
        )
        rows = cursor.fetchall()
    operations = []
    for ma_log, actor_id, action, raw in rows:
        data = json.loads(raw)
        payload = data.get("payload")
        if payload and data["entity"] == "article" and payload.get("published_at"):
            payload = {**payload, "published_at": datetime.fromisoformat(payload["published_at"])}
        operations.append({
            "ma_log": str(ma_log), "actor_id": str(actor_id), "action": str(action), "entity": data["entity"],
            "slug": data["slug"], "payload": payload, "idempotency_key": data["idempotency_key"],
        })
    return operations


def status(alias: str | None = None) -> dict:
    alias = alias or _registry_alias()
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "SELECT COUNT_BIG(*) FROM dbo.Logs AS i WHERE i.loai_log = 'sync' AND LEFT(i.ma_log, 6) = %s " + _open_filter(),
            [_INTENT],
        )
        pending = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT_BIG(*) FROM dbo.Logs WHERE loai_log = 'sync' AND LEFT(ma_log, 6) = %s AND ket_qua = 'that_bai'",
            [_REVIEW],
        )
        review = int(cursor.fetchone()[0])
    return {"pending_count": pending, "review_count": review}


def reconcile_pending_blog_writes(limit: int = 20) -> dict:
    """Replay queued writes oldest first; stop at the first one that still cannot finish (order matters)."""
    from core.blog.write_services import write_blog

    alias = _registry_alias()
    done = 0
    for operation in list_pending(alias, limit):
        try:
            result = write_blog(
                entity=operation["entity"], action=operation["action"], slug=operation["slug"],
                payload=operation["payload"], idempotency_key=operation["idempotency_key"],
                actor_id=operation["actor_id"],
            )
        except PublicBlogUnavailable:
            break
        except (PublicBlogConflict, PublicBlogNotFound) as exc:
            _marker(alias, operation["ma_log"], operation["actor_id"], prefix=_REVIEW, action="can_doi_soat",
                    result="that_bai", detail=str(exc))
            continue
        if not result["complete"]:
            break
        _marker(alias, operation["ma_log"], operation["actor_id"], prefix=_DONE, action="hoan_tat", result="thanh_cong")
        done += 1
    return {**status(alias), "completed": done}
