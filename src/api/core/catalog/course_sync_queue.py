"""Durable coordinator queue for shared KhoaHoc writes awaiting site recovery."""

from __future__ import annotations

import json

from django.db import connections


_COLUMNS = (
    "ma_giao_dich, ma_tai_khoan, hanh_dong, slug, ma_khoa_hoc, request_hash, "
    "du_lieu_truoc, du_lieu_moi, site_muc_tieu, site_cho_dong_bo, trang_thai, loi"
)


def _decode(row) -> dict | None:
    if row is None:
        return None
    return {
        "operation_id": str(row[0]).strip(),
        "actor_id": str(row[1]),
        "action": str(row[2]),
        "slug": str(row[3]),
        "course_id": str(row[4]) if row[4] is not None else None,
        "request_hash": str(row[5]),
        "before": json.loads(row[6]) if row[6] else None,
        "after": json.loads(row[7]) if row[7] else None,
        "target_sites": tuple(json.loads(row[8]) or ()),
        "pending_sites": tuple(json.loads(row[9]) or ()),
        "status": str(row[10]),
        "detail": str(row[11]) if row[11] else None,
    }


def get_operation(alias: str, operation_id: str) -> dict | None:
    with connections[alias].cursor() as cursor:
        cursor.execute(
            f"SELECT {_COLUMNS} FROM dbo.GiaoDichDongBoKhoaHoc WHERE ma_giao_dich = %s",
            [operation_id],
        )
        return _decode(cursor.fetchone())


def get_pending_operations(alias: str, *, limit: int = 20) -> list[dict]:
    with connections[alias].cursor() as cursor:
        cursor.execute(
            f"SELECT TOP (%s) {_COLUMNS} FROM dbo.GiaoDichDongBoKhoaHoc "
            "WHERE trang_thai <> 'hoan_tat' ORDER BY tao_luc_utc, ma_giao_dich",
            [limit],
        )
        return [operation for row in cursor.fetchall() if (operation := _decode(row))]


def insert_operation(alias: str, operation: dict) -> dict:
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "INSERT INTO dbo.GiaoDichDongBoKhoaHoc "
            "(ma_giao_dich, ma_tai_khoan, hanh_dong, slug, ma_khoa_hoc, request_hash, "
            "du_lieu_truoc, du_lieu_moi, site_muc_tieu, site_cho_dong_bo, trang_thai) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'cho_dong_bo')",
            [operation["operation_id"], operation["actor_id"], operation["action"],
             operation["slug"], operation.get("course_id"), operation["request_hash"],
             json.dumps(operation.get("before"), ensure_ascii=False, default=str) if operation.get("before") is not None else None,
             json.dumps(operation.get("after"), ensure_ascii=False, default=str),
             json.dumps(operation["target_sites"], ensure_ascii=False),
             json.dumps(operation["pending_sites"], ensure_ascii=False)],
        )
    return operation


def save_progress(alias: str, operation_id: str, *, pending_sites, detail: str | None = None,
                  needs_review: bool = False) -> None:
    pending = sorted(set(pending_sites))
    status = "can_doi_soat" if needs_review else "cho_dong_bo" if pending else "hoan_tat"
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "UPDATE dbo.GiaoDichDongBoKhoaHoc SET site_cho_dong_bo = %s, trang_thai = %s, "
            "loi = %s, cap_nhat_luc_utc = SYSUTCDATETIME() WHERE ma_giao_dich = %s",
            [json.dumps(pending, ensure_ascii=False), status, (detail or "")[:500] or None, operation_id],
        )
