"""Append-only course sync intents and acknowledgements in the existing Logs table."""

from __future__ import annotations

import json
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, IntegrityError, connections

from core.sites.fanout import read_sites_concurrently
from core.sites.connections import UnknownSiteError, get_site_connection


_INTENT_PREFIX = "KHINT-"


def _json(value) -> str:
    return json.dumps(
        value, cls=DjangoJSONEncoder, ensure_ascii=False,
        sort_keys=True, separators=(",", ":"),
    )


def _intent_id(operation_id: str) -> str:
    return f"{_INTENT_PREFIX}{operation_id}"


def _read_intent(alias: str, operation_id: str) -> dict | None:
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "SELECT ma_tai_khoan, hanh_dong, ma_ban_ghi, dinh_danh_bam, "
            "du_lieu_cu, du_lieu_moi FROM dbo.Logs "
            "WHERE ma_log = %s AND loai_log = 'sync' AND bang_tac_dong = 'KhoaHoc'",
            [_intent_id(operation_id)],
        )
        row = cursor.fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(row[5])
        if (
            not isinstance(payload, dict)
            or payload.get("queue_kind") != "course_sync"
            or payload.get("operation_id") != operation_id
            or not isinstance(payload.get("target_sites"), list)
        ):
            raise ValueError
        before = json.loads(row[4]) if row[4] else None
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DatabaseError("Bản ghi chờ đồng bộ khóa học trong Logs không hợp lệ.") from exc
    return {
        "operation_id": operation_id,
        "actor_id": str(row[0]),
        "action": str(row[1]),
        "course_id": payload.get("course_id") or (str(row[2]) if row[2] else None),
        "request_hash": str(row[3]),
        "slug": str(payload.get("slug") or ""),
        "before": before,
        "after": payload.get("after"),
        "target_sites": tuple(str(site) for site in payload["target_sites"]),
        "initial_pending_sites": tuple(str(site) for site in payload.get("pending_sites", ())),
        "detail": payload.get("detail"),
    }


def _acknowledged(site: str, operation: dict) -> bool:
    prefix = "KHDEL" if operation["action"] == "xoa" else "KHREP"
    event_id = f"{prefix}-{site}-{operation['operation_id']}"
    try:
        with get_site_connection(site).cursor() as cursor:
            cursor.execute(
                "SELECT TOP (1) ma_log FROM dbo.Logs WHERE ma_log = %s "
                "AND loai_log = 'sync' AND bang_tac_dong = 'KhoaHoc' AND ket_qua = 'thanh_cong'",
                [event_id],
            )
            return cursor.fetchone() is not None
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
        return False


def _status(alias: str, operation: dict) -> tuple[str, str | None]:
    operation_id = operation["operation_id"]
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "SELECT TOP (1) ma_log FROM dbo.Logs WHERE ma_log = %s "
            "AND loai_log = 'sync' AND bang_tac_dong = 'KhoaHoc' AND ket_qua = 'thanh_cong'",
            [f"KHFIN-{operation_id}"],
        )
        if cursor.fetchone():
            return "hoan_tat", None
        cursor.execute(
            "SELECT TOP (1) hanh_dong, du_lieu_moi FROM dbo.Logs "
            "WHERE loai_log = 'sync' AND bang_tac_dong = 'KhoaHoc' "
            "AND (ma_log LIKE %s OR ma_log LIKE %s) "
            "ORDER BY thoi_diem_utc DESC, ma_log DESC",
            [f"KHREV-{operation_id}-%", f"KHRETRY-{operation_id}-%"],
        )
        row = cursor.fetchone()
    if row and str(row[0]) == "can_doi_soat":
        try:
            payload = json.loads(row[1]) if row[1] else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        return "can_doi_soat", payload.get("detail")
    return "cho_dong_bo", operation.get("detail")


def get_operation(alias: str, operation_id: str, *, available_sites=None) -> dict | None:
    operation = _read_intent(alias, operation_id)
    if operation is None:
        return None
    status, detail = _status(alias, operation)
    if status == "hoan_tat":
        pending = ()
    else:
        sites_to_check = set(available_sites) if available_sites is not None else set(operation["target_sites"])
        sites_to_check.intersection_update(operation["target_sites"])
        acknowledgements, _ = read_sites_concurrently(
            tuple(sites_to_check), lambda site: _acknowledged(site, operation),
        )
        acknowledged_sites = {site for site, acknowledged in acknowledgements.items() if acknowledged}
        pending = tuple(site for site in operation["target_sites"] if site not in acknowledged_sites)
    return {**operation, "pending_sites": pending, "status": status, "detail": detail}


def get_pending_operations(alias: str, *, limit: int = 20, available_sites=None) -> list[dict]:
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "SELECT TOP (%s) ma_log FROM dbo.Logs WHERE loai_log = 'sync' "
            "AND bang_tac_dong = 'KhoaHoc' AND LEFT(ma_log, %s) = %s "
            "AND NOT EXISTS (SELECT 1 FROM dbo.Logs AS finished "
            "WHERE finished.ma_log = N'KHFIN-' + SUBSTRING(dbo.Logs.ma_log, 7, 64) "
            "AND finished.ket_qua = 'thanh_cong') "
            "ORDER BY COALESCE(TRY_CONVERT(bigint, JSON_VALUE(du_lieu_moi, '$.queue_sequence')), 0), "
            "thoi_diem_utc, ma_log",
            [limit, len(_INTENT_PREFIX), _INTENT_PREFIX],
        )
        operation_ids = [str(row[0])[len(_INTENT_PREFIX):] for row in cursor.fetchall()]
    pending = []
    for operation_id in operation_ids:
        operation = get_operation(alias, operation_id, available_sites=available_sites)
        if operation and operation["status"] != "hoan_tat":
            pending.append(operation)
    return pending


def get_review_operations(alias: str) -> list[dict]:
    """Read review blockers from coordinator Logs without contacting remote sites."""
    return [operation for operation in get_open_operations(alias) if operation["status"] == "can_doi_soat"]


def get_open_operations(alias: str) -> list[dict]:
    """Read unfinished intent metadata from coordinator Logs without site connections."""
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "SELECT intent.ma_log FROM dbo.Logs AS intent WHERE intent.loai_log = 'sync' "
            "AND intent.bang_tac_dong = 'KhoaHoc' AND LEFT(intent.ma_log, %s) = %s "
            "AND NOT EXISTS (SELECT 1 FROM dbo.Logs AS finished "
            "WHERE finished.ma_log = N'KHFIN-' + SUBSTRING(intent.ma_log, 7, 64) "
            "AND finished.ket_qua = 'thanh_cong') "
            "ORDER BY thoi_diem_utc, ma_log",
            [len(_INTENT_PREFIX), _INTENT_PREFIX],
        )
        operation_ids = [str(row[0])[len(_INTENT_PREFIX):] for row in cursor.fetchall()]
    operations = []
    for operation_id in operation_ids:
        operation = _read_intent(alias, operation_id)
        if operation is None:
            continue
        status, detail = _status(alias, operation)
        if status != "hoan_tat":
            operations.append({
                **operation, "status": status, "detail": detail,
                "pending_sites": operation["initial_pending_sites"],
            })
    return operations


def insert_operation(alias: str, operation: dict) -> dict:
    with connections[alias].cursor() as cursor:
        cursor.execute("SELECT NEXT VALUE FOR dbo.Seq_NK")
        queue_sequence = int(cursor.fetchone()[0])
    payload = {
        "queue_kind": "course_sync",
        "operation_id": operation["operation_id"],
        "queue_sequence": queue_sequence,
        "slug": operation["slug"],
        "course_id": operation.get("course_id"),
        "after": operation.get("after"),
        "target_sites": list(operation["target_sites"]),
        "pending_sites": list(operation.get("pending_sites", operation["target_sites"])),
        "detail": operation.get("detail"),
    }
    record_id = str(operation.get("course_id") or operation["slug"])[:100]
    site_code = str(getattr(settings, "AUTH_SESSION_SITE_CODE", "")).strip().upper() or None
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "INSERT INTO dbo.Logs "
            "(ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, "
            "ma_ban_ghi, du_lieu_cu, du_lieu_moi, dinh_danh_bam, ket_qua) "
            "VALUES (%s, 'sync', %s, %s, %s, 'KhoaHoc', %s, %s, %s, %s, NULL)",
            [_intent_id(operation["operation_id"]), site_code, operation["actor_id"],
             operation["action"], record_id,
             _json(operation.get("before")) if operation.get("before") is not None else None,
             _json(payload), operation["request_hash"]],
        )
    return operation


def _insert_status_event(alias: str, operation: dict, *, prefix: str, action: str,
                         result: str | None, pending_sites=(), detail: str | None = None) -> None:
    site_code = str(getattr(settings, "AUTH_SESSION_SITE_CODE", "")).strip().upper() or None
    payload = {
        "operation_id": operation["operation_id"],
        "pending_sites": sorted(set(pending_sites)),
        "detail": (detail or "")[:500] or None,
    }
    event_id = (
        f"KHFIN-{operation['operation_id']}"
        if prefix == "KHFIN"
        else f"{prefix}-{operation['operation_id']}-{uuid4().hex}"
    )
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "INSERT INTO dbo.Logs "
            "(ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, "
            "ma_ban_ghi, du_lieu_moi, ket_qua) "
            "VALUES (%s, 'sync', %s, %s, %s, 'KhoaHoc', %s, %s, %s)",
            [event_id, site_code, operation["actor_id"], action,
             str(operation.get("course_id") or operation["slug"])[:100],
             _json(payload), result],
        )


def mark_manual_retry(alias: str, operation_id: str) -> None:
    operation = _read_intent(alias, operation_id)
    if operation is not None:
        _insert_status_event(
            alias, operation, prefix="KHRETRY", action="thu_lai", result=None,
            pending_sites=operation.get("initial_pending_sites", ()),
        )


def save_progress(alias: str, operation_id: str, *, pending_sites, detail: str | None = None,
                  needs_review: bool = False) -> None:
    operation = _read_intent(alias, operation_id)
    if operation is None:
        return
    pending = sorted(set(pending_sites))
    if needs_review:
        _insert_status_event(
            alias, operation, prefix="KHREV", action="can_doi_soat", result="that_bai",
            pending_sites=pending, detail=detail,
        )
    elif not pending:
        with connections[alias].cursor() as cursor:
            cursor.execute("SELECT TOP (1) ma_log FROM dbo.Logs WHERE ma_log = %s", [f"KHFIN-{operation_id}"])
            if cursor.fetchone():
                return
        try:
            _insert_status_event(
                alias, operation, prefix="KHFIN", action="hoan_tat", result="thanh_cong",
            )
        except IntegrityError:
            with connections[alias].cursor() as cursor:
                cursor.execute("SELECT TOP (1) ma_log FROM dbo.Logs WHERE ma_log = %s", [f"KHFIN-{operation_id}"])
                if not cursor.fetchone():
                    raise
