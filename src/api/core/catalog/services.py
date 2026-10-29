"""Application-level replication for shared subject catalog updates.

Each site's MonHoc update and its append-only Logs acknowledgement commit in
one local transaction. A deterministic log key makes retries idempotent.
"""

from __future__ import annotations

import hashlib
import json

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction

from core.academics.common import AcademicInfrastructureUnavailable, acquire_record_lock, active_site_state
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias


class SharedCatalogError(Exception):
    """Base error for a replicated catalog write."""


class SharedCatalogConflict(SharedCatalogError):
    """The request key or an existing site copy conflicts with this write."""


class SharedCatalogNotFound(SharedCatalogError):
    """The shared subject does not exist at every active site."""


class SharedCatalogUnavailable(SharedCatalogError):
    """A required site or the coordinator registry is unavailable."""

    def __init__(self, message: str = "", *, missing_sites=()):
        self.missing_sites = tuple(missing_sites)
        super().__init__(message)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(patch: dict) -> str:
    return hashlib.sha256(_json(patch).encode("utf-8")).hexdigest()


def _event_id(key_digest: str, site_code: str) -> str:
    # Logs.ma_log is NVARCHAR(120); this deterministic ID is unique per key/site.
    return f"MHREP-{site_code}-{key_digest[:64]}"


def _subject(row) -> dict:
    if row is None:
        return {}
    return {
        "ma_mon": str(row[0]),
        "slug": str(row[1]),
        "ten_mon": str(row[2]),
        "mo_ta": None if row[3] is None else str(row[3]),
        "phien_ban": int(row[4]),
    }


def _read_site(site_code: str, slug: str, event_id: str) -> tuple[dict | None, dict | None]:
    with get_site_connection(site_code).cursor() as cursor:
        cursor.execute(
            "SELECT ma_mon, slug, ten_mon, mo_ta, phien_ban "
            "FROM dbo.MonHoc WHERE slug = %s",
            [slug],
        )
        rows = cursor.fetchall()
        if len(rows) > 1:
            raise SharedCatalogConflict("Slug môn học không duy nhất trong một site.")
        cursor.execute(
            "SELECT bang_tac_dong, ma_ban_ghi, hanh_dong, site_dich, ket_qua, "
            "du_lieu_cu, du_lieu_moi FROM dbo.Logs "
            "WHERE loai_log = 'sync' AND ma_log = %s",
            [event_id],
        )
        event_rows = cursor.fetchall()
        if len(event_rows) > 1:
            raise SharedCatalogConflict("Có nhiều ACK cho cùng một mã thao tác.")
    subject = _subject(rows[0]) if rows else None
    event = None
    if event_rows:
        raw = event_rows[0]
        if tuple(str(value) for value in raw[:5]) != (
            "MonHoc", str(subject["ma_mon"] if subject else raw[1]), "sua", site_code, "thanh_cong"
        ):
            raise SharedCatalogConflict("ACK trong Logs không khớp môn học/site.")
        try:
            before = json.loads(raw[5])
            payload = json.loads(raw[6])
            event = {"before": before, **payload}
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SharedCatalogConflict("Dữ liệu ACK không đọc được; cần đối soát thủ công.") from exc
    return subject, event


def _same_subject(actual: dict | None, expected: dict) -> bool:
    return actual == expected


def _validate_event(event: dict, *, slug: str, request_hash: str) -> tuple[dict, dict]:
    before = event.get("before")
    after = event.get("after")
    expected_fields = {"ma_mon", "slug", "ten_mon", "mo_ta", "phien_ban"}
    versions_are_next = (
        isinstance(before, dict)
        and isinstance(after, dict)
        and isinstance(before.get("phien_ban"), int)
        and not isinstance(before.get("phien_ban"), bool)
        and isinstance(after.get("phien_ban"), int)
        and not isinstance(after.get("phien_ban"), bool)
        and after["phien_ban"] == before["phien_ban"] + 1
    )
    if (
        event.get("request_hash") != request_hash
        or not isinstance(before, dict)
        or not isinstance(after, dict)
        or set(before) != expected_fields
        or set(after) != expected_fields
        or before.get("slug") != slug
        or after.get("slug") != slug
        or not versions_are_next
    ):
        raise SharedCatalogConflict("Idempotency-Key đã được dùng với nội dung khác hoặc ACK không hợp lệ.")
    return before, after


def _apply_site(
    *, site_code: str, subject_before: dict, subject_after: dict,
    event_id: str, request_hash: str, actor_id: str,
) -> None:
    alias = get_site_database_alias(site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                "SELECT ma_mon, slug, ten_mon, mo_ta, phien_ban "
                "FROM dbo.MonHoc WITH (UPDLOCK, HOLDLOCK) WHERE slug = %s",
                [subject_before["slug"]],
            )
            rows = cursor.fetchall()
            if len(rows) != 1 or not _same_subject(_subject(rows[0]), subject_before):
                raise SharedCatalogConflict("Một bản sao đã thay đổi; cần đối soát trước khi tiếp tục.")

            cursor.execute(
                "UPDATE dbo.MonHoc SET ten_mon = %s, mo_ta = %s, "
                "phien_ban = phien_ban + 1, cap_nhat_luc = SYSUTCDATETIME() "
                "WHERE ma_mon = %s AND slug = %s AND phien_ban = %s "
                "AND ten_mon = %s AND ((mo_ta = %s) OR (mo_ta IS NULL AND %s IS NULL))",
                [
                    subject_after["ten_mon"], subject_after["mo_ta"],
                    subject_before["ma_mon"], subject_before["slug"],
                    subject_before["phien_ban"], subject_before["ten_mon"],
                    subject_before["mo_ta"], subject_before["mo_ta"],
                ],
            )
            cursor.execute(
                "SELECT ma_mon, slug, ten_mon, mo_ta, phien_ban "
                "FROM dbo.MonHoc WHERE ma_mon = %s",
                [subject_before["ma_mon"]],
            )
            updated_rows = cursor.fetchall()
            if len(updated_rows) != 1 or not _same_subject(_subject(updated_rows[0]), subject_after):
                raise SharedCatalogConflict("Không xác nhận được phiên bản môn học sau cập nhật.")

            cursor.execute(
                "INSERT INTO dbo.Logs "
                "(ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, "
                "ma_ban_ghi, du_lieu_cu, du_lieu_moi, ket_qua, site_dich) "
                "VALUES (%s, 'sync', %s, %s, 'sua', 'MonHoc', %s, %s, %s, 'thanh_cong', %s)",
                [
                    event_id, site_code, actor_id, subject_before["ma_mon"],
                    _json(subject_before),
                    _json({"request_hash": request_hash, "after": subject_after}),
                    site_code,
                ],
            )


def update_shared_subject(
    *, slug: str, patch: dict, idempotency_key: str, actor_id: str,
) -> dict:
    """Update MonHoc at every active site, returning a retryable partial result."""
    registry_site = str(getattr(settings, "AUTH_SESSION_SITE_CODE", "")).strip().upper()
    try:
        registry_alias = get_site_database_alias(registry_site)
        active_sites, missing_sites = active_site_state()
    except (AcademicInfrastructureUnavailable, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise SharedCatalogUnavailable from exc
    if missing_sites or not active_sites:
        raise SharedCatalogUnavailable(
            "Một hoặc nhiều site hoạt động chưa sẵn sàng; không ghi bản sao nào.",
            missing_sites=missing_sites,
        )

    key_digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    request_hash = _fingerprint(patch)
    ordered_sites = (registry_site,) + tuple(site for site in sorted(active_sites) if site != registry_site)
    event_ids = {site: _event_id(key_digest, site) for site in ordered_sites}

    try:
        with transaction.atomic(using=registry_alias):
            with connections[registry_alias].cursor() as cursor:
                acquire_record_lock(cursor, f"shared-catalog:MonHoc:{slug}")

            states = {
                site: _read_site(site, slug, event_ids[site])
                for site in ordered_sites
            }
            subjects = {site: state[0] for site, state in states.items()}
            events = {site: state[1] for site, state in states.items()}
            if any(subject is None for subject in subjects.values()):
                raise SharedCatalogNotFound

            existing_events = [event for event in events.values() if event is not None]
            if existing_events:
                canonical_before, canonical_after = _validate_event(
                    existing_events[0], slug=slug, request_hash=request_hash
                )
                for event in existing_events[1:]:
                    before, after = _validate_event(event, slug=slug, request_hash=request_hash)
                    if before != canonical_before or after != canonical_after:
                        raise SharedCatalogConflict("Các ACK của cùng thao tác không thống nhất.")
                for site in ordered_sites:
                    subject = subjects[site]
                    if events[site] is not None:
                        if subject["phien_ban"] < canonical_after["phien_ban"]:
                            raise SharedCatalogConflict("ACK đã có nhưng dữ liệu site thấp hơn phiên bản ACK.")
                        if subject["phien_ban"] == canonical_after["phien_ban"] and subject != canonical_after:
                            raise SharedCatalogConflict("Dữ liệu site không khớp ACK; cần đối soát thủ công.")
                        continue
                    if subject != canonical_before:
                        raise SharedCatalogConflict("Site chưa ACK nhưng dữ liệu đã lệch; không áp dụng lại thay đổi cũ.")
                subject_before, subject_after = canonical_before, canonical_after
            else:
                subject_values = list(subjects.values())
                if any(value != subject_values[0] for value in subject_values[1:]):
                    raise SharedCatalogConflict("Các bản sao môn học đang khác nhau; cần đối soát trước khi sửa.")
                subject_before = subject_values[0]
                subject_after = {
                    **subject_before,
                    "ten_mon": patch.get("ten_mon", subject_before["ten_mon"]),
                    "mo_ta": patch.get("mo_ta", subject_before["mo_ta"]),
                    "phien_ban": subject_before["phien_ban"] + 1,
                }

            failed_sites = []
            for site in ordered_sites:
                if events[site] is not None:
                    continue
                try:
                    _apply_site(
                        site_code=site,
                        subject_before=subject_before,
                        subject_after=subject_after,
                        event_id=event_ids[site],
                        request_hash=request_hash,
                        actor_id=actor_id,
                    )
                except SharedCatalogConflict:
                    raise
                except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
                    if site == registry_site:
                        raise SharedCatalogUnavailable from exc
                    failed_sites.append(site)

            complete = not failed_sites
            return {
                **subject_after,
                "complete": complete,
                "sites": [site for site in ordered_sites if site not in failed_sites],
                "missing_sites": failed_sites,
                "idempotent_replay": bool(existing_events),
            }
    except SharedCatalogError:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise SharedCatalogUnavailable from exc
