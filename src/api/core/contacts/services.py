"""Site-local contact storage with a Global Query for the admin inbox."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import timezone as datetime_timezone
from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.db import connections, transaction

from core.academics.common import (
    AcademicConflict,
    AcademicForbidden,
    AcademicInfrastructureUnavailable,
    AcademicInvalid,
    AcademicNotFound,
    AcademicSiteUnavailable,
    active_site_state,
    append_audit,
    global_site_list,
    next_id,
    normalize_site,
    require_active_site,
    site_scope,
    translate_database_errors,
)
from core.sites.connections import get_site_connection, get_site_database_alias


logger = logging.getLogger(__name__)


class ContactEmailUnavailable(AcademicInfrastructureUnavailable):
    """SMTP is missing or could not accept the admin reply."""


def _iso_utc(value) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime_timezone.utc)
    return value.astimezone(datetime_timezone.utc).isoformat().replace("+00:00", "Z")


@translate_database_errors
def list_contact_sites() -> dict[str, Any]:
    available, initially_missing = active_site_state()
    registry_site = normalize_site(getattr(settings, "AUTH_SESSION_SITE_CODE", ""))
    with get_site_connection(registry_site).cursor() as cursor:
        cursor.execute(
            "SELECT ma_co_so, ten_co_so FROM dbo.CoSo "
            "WHERE trang_thai = 'hoat_dong' ORDER BY ma_co_so"
        )
        names = {str(code).upper(): str(name) for code, name in cursor.fetchall()}
    site_codes = sorted(set(available) | set(initially_missing))
    return {
        "complete": not initially_missing,
        "missing_sites": list(initially_missing),
        "site_codes": site_codes,
        "results": [
            {"site_code": site, "name": names[site]}
            for site in sorted(available) if site in names
        ],
    }


def _contact_fingerprint(contact: dict[str, Any]) -> str:
    canonical = json.dumps(contact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@translate_database_errors
def create_contact_request(
    *, contact: dict[str, Any], idempotency_key: str, remote_ip: str
) -> dict[str, Any]:
    site_code = normalize_site(contact["site_code"])
    available, _missing = active_site_state()
    if site_code not in available:
        raise AcademicSiteUnavailable
    alias = get_site_database_alias(site_code)
    fingerprint = _contact_fingerprint(contact)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            require_active_site(site_code)
            cursor.execute(
                "SELECT ma_yeu_cau, payload_hash, trang_thai, tao_luc_utc "
                "FROM dbo.YeuCauLienHe WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_co_so = %s AND khoa_chong_lap = %s",
                [site_code, idempotency_key],
            )
            existing = cursor.fetchone()
            if existing:
                if str(existing[1]) != fingerprint:
                    raise AcademicConflict("Idempotency-Key đã được dùng với nội dung khác.")
                return {
                    "request_id": str(existing[0]),
                    "site_code": site_code,
                    "status": str(existing[2]),
                    "received_at": _iso_utc(existing[3]),
                    "replayed": True,
                }

            request_id = next_id(cursor, site_code, "contact")
            cursor.execute(
                """
                INSERT INTO dbo.YeuCauLienHe
                    (ma_yeu_cau, ma_co_so, ho_ten, email, so_dien_thoai, tieu_de,
                     noi_dung, trang_thai, khoa_chong_lap, payload_hash)
                OUTPUT INSERTED.tao_luc_utc
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'cho_xu_ly', %s, %s)
                """,
                [
                    request_id, site_code, contact["full_name"], contact["email"],
                    contact.get("phone") or None, contact["subject"], contact["message"],
                    idempotency_key, fingerprint,
                ],
            )
            received_at = _iso_utc(cursor.fetchone()[0])
            append_audit(
                cursor,
                site_code=site_code,
                actor_id=None,
                action="tiep_nhan_yeu_cau_lien_he",
                table_name="YeuCauLienHe",
                record_id=request_id,
                remote_ip=remote_ip,
                after={"status": "cho_xu_ly"},
                note="Tiếp nhận yêu cầu từ biểu mẫu công khai.",
            )
    return {
        "request_id": request_id,
        "site_code": site_code,
        "status": "cho_xu_ly",
        "received_at": received_at,
        "replayed": False,
    }


def _list_site_contacts(
    *, site_code: str, status_filter: str | None, search: str | None, limit: int, offset: int
) -> dict[str, Any]:
    alias = require_active_site(site_code)
    conditions = ["ma_co_so = %s"]
    params: list[Any] = [site_code]
    if status_filter:
        conditions.append("trang_thai = %s")
        params.append(status_filter)
    if search:
        conditions.append(
            "(ho_ten LIKE %s OR email LIKE %s OR tieu_de LIKE %s OR noi_dung LIKE %s)"
        )
        params.extend([f"%{search}%"] * 4)
    where_sql = " AND ".join(conditions)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT_BIG(*) FROM dbo.YeuCauLienHe WHERE {where_sql}", params
        )
        count = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT ma_yeu_cau, ma_co_so, ho_ten, email, so_dien_thoai, tieu_de, "
            "noi_dung, trang_thai, tao_luc_utc, noi_dung_phan_hoi, phan_hoi_luc_utc "
            f"FROM dbo.YeuCauLienHe WHERE {where_sql} "
            "ORDER BY tao_luc_utc DESC, ma_yeu_cau DESC "
            "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            [*params, offset, limit],
        )
        results = [
            {
                "request_id": str(row[0]),
                "site_code": str(row[1]),
                "full_name": str(row[2]),
                "email": str(row[3]),
                "phone": str(row[4]) if row[4] is not None else None,
                "subject": str(row[5]),
                "message": str(row[6]),
                "status": str(row[7]),
                "received_at": _iso_utc(row[8]),
                "reply_body": str(row[9]) if row[9] is not None else None,
                "replied_at": _iso_utc(row[10]) if row[10] is not None else None,
            }
            for row in cursor.fetchall()
        ]
    return {"count": count, "limit": limit, "offset": offset, "results": results}


@translate_database_errors
def list_admin_contact_requests(
    *, user, site_code: str | None,
    status_filter: str | None, search: str | None, limit: int, offset: int,
) -> dict[str, Any]:
    if user.role == "admin_big" and not site_code:
        return global_site_list(
            lambda site, page_limit, page_offset: _list_site_contacts(
                site_code=site, status_filter=status_filter, search=search,
                limit=page_limit, offset=page_offset,
            ),
            limit=limit,
            offset=offset,
            unavailable_exceptions=(AcademicInfrastructureUnavailable, AcademicSiteUnavailable),
        )
    site = site_scope(user=user, requested_site=site_code, roles={"admin_big", "admin_small"})
    result = _list_site_contacts(
        site_code=site, status_filter=status_filter, search=search, limit=limit, offset=offset
    )
    return {
        "scope": "LOCAL", "complete": True, "missing_sites": [], "site_codes": [site], **result,
    }


@translate_database_errors
def send_contact_reply(
    *, site_code: str, request_id: str, reply_body: str, actor_id: str,
    remote_ip: str,
) -> dict[str, Any]:
    alias = require_active_site(site_code)
    smtp_backend = str(getattr(settings, "EMAIL_BACKEND", ""))
    if (
        not smtp_backend.endswith("smtp.EmailBackend")
        or not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD
        or not settings.DEFAULT_FROM_EMAIL
    ):
        raise ContactEmailUnavailable

    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                "SELECT email, tieu_de, trang_thai FROM dbo.YeuCauLienHe WITH (UPDLOCK, ROWLOCK) "
                "WHERE ma_co_so = %s AND ma_yeu_cau = %s",
                [site_code, request_id],
            )
            contact = cursor.fetchone()
            if contact is None:
                raise AcademicNotFound
            if str(contact[2]) != "cho_xu_ly":
                raise AcademicConflict("Yêu cầu này đã được phản hồi.")
            try:
                # shortcut: SMTP and SQL cannot commit atomically; use an outbox if delivery retries must avoid duplicates.
                sent = send_mail(
                    subject=f"Re: {str(contact[1])}",
                    message=reply_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[str(contact[0])],
                    fail_silently=False,
                    reply_to=[str(contact[0])],
                )
            except Exception as exc:
                logger.warning(
                    "Contact reply SMTP failed (site=%s request=%s error=%s)",
                    site_code,
                    request_id,
                    type(exc).__name__,
                )
                raise ContactEmailUnavailable from exc
            if sent != 1:
                raise ContactEmailUnavailable
            cursor.execute(
                "UPDATE dbo.YeuCauLienHe SET trang_thai = 'da_phan_hoi', "
                "noi_dung_phan_hoi = %s, ma_nguoi_phan_hoi = %s, "
                "phan_hoi_luc_utc = SYSUTCDATETIME(), cap_nhat_luc_utc = SYSUTCDATETIME() "
                "OUTPUT INSERTED.phan_hoi_luc_utc "
                "WHERE ma_co_so = %s AND ma_yeu_cau = %s",
                [reply_body, actor_id, site_code, request_id],
            )
            replied_at = _iso_utc(cursor.fetchone()[0])
            append_audit(
                cursor,
                site_code=site_code,
                actor_id=actor_id,
                action="phan_hoi_yeu_cau_lien_he",
                table_name="YeuCauLienHe",
                record_id=request_id,
                remote_ip=remote_ip,
                before={"status": "cho_xu_ly"},
                after={"status": "da_phan_hoi"},
                note="SMTP đã chấp nhận email phản hồi.",
            )
    return {"request_id": request_id, "site_code": site_code, "status": "da_phan_hoi", "replied_at": replied_at}
