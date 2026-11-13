"""Replicated writes for the shared MonHoc catalog."""

from __future__ import annotations

import hashlib
import json

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, IntegrityError, connections, transaction

from core.academics.common import AcademicInfrastructureUnavailable, acquire_record_lock, active_site_state
from core.catalog.services import SharedCatalogConflict, SharedCatalogNotFound, SharedCatalogUnavailable
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias


_SUBJECT_FIELDS = {"ma_mon", "slug", "ten_mon", "mo_ta", "phien_ban"}


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _subject(row) -> dict | None:
    if row is None:
        return None
    return {
        "ma_mon": str(row[0]), "slug": str(row[1]), "ten_mon": str(row[2]),
        "mo_ta": None if row[3] is None else str(row[3]), "phien_ban": int(row[4]),
    }


def _read_site(site: str, *, ma_mon: str | None, slug: str, event_id: str):
    with get_site_connection(site).cursor() as cursor:
        if ma_mon:
            cursor.execute(
                "SELECT ma_mon, slug, ten_mon, mo_ta, phien_ban FROM dbo.MonHoc "
                "WHERE ma_mon = %s OR slug = %s", [ma_mon, slug],
            )
        else:
            cursor.execute(
                "SELECT ma_mon, slug, ten_mon, mo_ta, phien_ban FROM dbo.MonHoc WHERE slug = %s",
                [slug],
            )
        rows = cursor.fetchall()
        if len(rows) > 1:
            raise SharedCatalogConflict("Mã môn và slug đang trỏ tới nhiều bản ghi trong một site.")
        cursor.execute(
            "SELECT bang_tac_dong, ma_ban_ghi, hanh_dong, site_dich, ket_qua, "
            "du_lieu_cu, du_lieu_moi FROM dbo.Logs WHERE loai_log = 'sync' AND ma_log = %s",
            [event_id],
        )
        events = cursor.fetchall()
        if len(events) > 1:
            raise SharedCatalogConflict("Có nhiều ACK cho cùng một yêu cầu môn học.")

    current = _subject(rows[0]) if rows else None
    event = None
    if events:
        raw = events[0]
        if str(raw[0]) != "MonHoc" or str(raw[3]) != site or str(raw[4]) != "thanh_cong":
            raise SharedCatalogConflict("ACK trong Logs không khớp bảng hoặc site.")
        try:
            before = json.loads(raw[5]) if raw[5] else None
            payload = json.loads(raw[6]) if raw[6] else {}
            event = {
                "record_id": str(raw[1]), "action": str(raw[2]), "before": before,
                "after": payload.get("after"), "request_hash": payload.get("request_hash"),
            }
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SharedCatalogConflict("ACK không đọc được; cần đối soát thủ công.") from exc
    return current, event


def _check_event(event, *, action: str, record_id: str, request_hash: str, slug: str | None = None):
    before, after = event.get("before"), event.get("after")
    valid = (
        event.get("action") == action
        and event.get("record_id") == record_id
        and event.get("request_hash") == request_hash
        and ((action == "tao" and before is None and isinstance(after, dict)
              and set(after) == _SUBJECT_FIELDS and after["phien_ban"] == 1)
             or (action == "xoa" and isinstance(before, dict)
                 and set(before) == _SUBJECT_FIELDS and after is None
                 and before.get("slug") == slug and before.get("ma_mon") == record_id))
    )
    if not valid:
        raise SharedCatalogConflict("Idempotency-Key đã dùng với nội dung khác hoặc ACK không hợp lệ.")
    return before, after


def _event_id(action: str, site: str, key_digest: str) -> str:
    prefix = "MHCR" if action == "tao" else "MHDEL"
    return f"{prefix}-{site}-{key_digest[:64]}"


def _apply_create(*, site: str, subject: dict, event_id: str, request_hash: str, actor_id: str):
    alias = get_site_database_alias(site)
    with transaction.atomic(using=alias), connections[alias].cursor() as cursor:
        cursor.execute(
            "SELECT ma_mon FROM dbo.MonHoc WITH (UPDLOCK, HOLDLOCK) "
            "WHERE ma_mon = %s OR slug = %s", [subject["ma_mon"], subject["slug"]],
        )
        if cursor.fetchall():
            raise SharedCatalogConflict("Mã môn học hoặc slug đã tồn tại tại một cơ sở.")
        cursor.execute(
            "INSERT INTO dbo.MonHoc (ma_mon, slug, ten_mon, mo_ta, phien_ban) "
            "VALUES (%s, %s, %s, %s, 1)",
            [subject["ma_mon"], subject["slug"], subject["ten_mon"], subject["mo_ta"]],
        )
        cursor.execute(
            "SELECT ma_mon, slug, ten_mon, mo_ta, phien_ban FROM dbo.MonHoc WHERE ma_mon = %s",
            [subject["ma_mon"]],
        )
        if _subject(cursor.fetchone()) != subject:
            raise SharedCatalogConflict("Không xác nhận được môn học sau khi tạo.")
        cursor.execute(
            "INSERT INTO dbo.Logs (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, "
            "bang_tac_dong, ma_ban_ghi, du_lieu_cu, du_lieu_moi, ket_qua, site_dich) "
            "VALUES (%s, 'sync', %s, %s, 'tao', 'MonHoc', %s, NULL, %s, 'thanh_cong', %s)",
            [event_id, site, actor_id, subject["ma_mon"],
             _json({"request_hash": request_hash, "after": subject}), site],
        )


def _apply_delete(*, site: str, before: dict, event_id: str, request_hash: str, actor_id: str):
    alias = get_site_database_alias(site)
    with transaction.atomic(using=alias), connections[alias].cursor() as cursor:
        cursor.execute(
            "SELECT ma_mon, slug, ten_mon, mo_ta, phien_ban FROM dbo.MonHoc WITH (UPDLOCK, HOLDLOCK) "
            "WHERE ma_mon = %s AND slug = %s", [before["ma_mon"], before["slug"]],
        )
        if _subject(cursor.fetchone()) != before:
            raise SharedCatalogConflict("Bản sao môn học đã thay đổi; hãy tải lại trước khi xóa.")
        cursor.execute(
            "SELECT TOP (1) ma_khoa_hoc FROM dbo.KhoaHoc WITH (UPDLOCK, HOLDLOCK) WHERE ma_mon = %s",
            [before["ma_mon"]],
        )
        if cursor.fetchone():
            raise SharedCatalogConflict(f"Không thể xóa môn học đang được khóa học sử dụng tại {site}.")
        cursor.execute(
            "DELETE FROM dbo.MonHoc WHERE ma_mon = %s AND slug = %s AND phien_ban = %s",
            [before["ma_mon"], before["slug"], before["phien_ban"]],
        )
        cursor.execute("SELECT ma_mon FROM dbo.MonHoc WHERE ma_mon = %s OR slug = %s", [before["ma_mon"], before["slug"]])
        if cursor.fetchone():
            raise SharedCatalogConflict("Không xác nhận được việc xóa môn học tại một cơ sở.")
        cursor.execute(
            "INSERT INTO dbo.Logs (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, "
            "bang_tac_dong, ma_ban_ghi, du_lieu_cu, du_lieu_moi, ket_qua, site_dich) "
            "VALUES (%s, 'sync', %s, %s, 'xoa', 'MonHoc', %s, %s, %s, 'thanh_cong', %s)",
            [event_id, site, actor_id, before["ma_mon"], _json(before),
             _json({"request_hash": request_hash, "after": None}), site],
        )


def _site_context():
    registry_site = str(getattr(settings, "AUTH_SESSION_SITE_CODE", "")).strip().upper()
    try:
        registry_alias = get_site_database_alias(registry_site)
        sites, missing = active_site_state()
    except (AcademicInfrastructureUnavailable, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise SharedCatalogUnavailable from exc
    if missing or not sites:
        raise SharedCatalogUnavailable(
            "Một hoặc nhiều site hoạt động chưa sẵn sàng; không thể xác nhận ghi danh mục.",
            missing_sites=missing,
        )
    ordered = (registry_site,) + tuple(site for site in sorted(sites) if site != registry_site)
    return registry_site, registry_alias, ordered


def _write_subject(*, action: str, subject: dict | None, slug: str, idempotency_key: str, actor_id: str):
    registry_site, registry_alias, sites = _site_context()
    record_id = subject["ma_mon"] if subject else None
    request_data = subject if action == "tao" else {"slug": slug}
    request_hash = hashlib.sha256(_json({"action": action, "payload": request_data}).encode()).hexdigest()
    key_digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
    event_ids = {site: _event_id(action, site, key_digest) for site in sites}
    try:
        with transaction.atomic(using=registry_alias):
            with connections[registry_alias].cursor() as cursor:
                if action == "xoa":
                    acquire_record_lock(cursor, "shared-catalog:KhoaHoc")
                acquire_record_lock(cursor, f"shared-catalog:MonHoc:{slug}" if action == "xoa" else "shared-catalog:MonHoc")
            states = {
                site: _read_site(site, ma_mon=record_id, slug=subject["slug"] if subject else slug,
                                 event_id=event_ids[site])
                for site in sites
            }
            current = {site: state[0] for site, state in states.items()}
            events = {site: state[1] for site, state in states.items()}
            replay_events = [event for event in events.values() if event]

            if action == "tao":
                if replay_events:
                    transitions = [_check_event(event, action=action, record_id=record_id,
                                                request_hash=request_hash) for event in replay_events]
                    after = transitions[0][1]
                    if any(transition != transitions[0] for transition in transitions[1:]) or after != {**subject, "phien_ban": 1}:
                        raise SharedCatalogConflict("ACK tạo môn học không thống nhất giữa các site.")
                    for site in sites:
                        if (events[site] and current[site] != after) or (not events[site] and current[site] is not None):
                            raise SharedCatalogConflict("Dữ liệu môn học lệch ACK; cần đối soát trước khi retry.")
                else:
                    if any(value is not None for value in current.values()):
                        raise SharedCatalogConflict("Mã môn học hoặc slug đã có tại một site.")
                    after = {**subject, "phien_ban": 1}
                before = None
            else:
                if replay_events:
                    transitions = [_check_event(event, action=action, record_id=event["record_id"],
                                                request_hash=request_hash, slug=slug) for event in replay_events]
                    before = transitions[0][0]
                    record_id = before["ma_mon"]
                    if any(transition != transitions[0] for transition in transitions[1:]):
                        raise SharedCatalogConflict("ACK xóa môn học không thống nhất giữa các site.")
                    for site in sites:
                        if (events[site] and current[site] is not None) or (not events[site] and current[site] != before):
                            raise SharedCatalogConflict("Bản sao môn học lệch ACK; cần đối soát trước khi retry.")
                else:
                    copies = list(current.values())
                    if all(copy is None for copy in copies):
                        raise SharedCatalogNotFound("Không tìm thấy môn học tại các site hoạt động.")
                    if any(copy is None or copy != copies[0] for copy in copies):
                        raise SharedCatalogConflict("Các bản sao môn học không đồng nhất; không thể xóa an toàn.")
                    before = copies[0]
                after = None
                # The coordinator lock serializes this check with API course writes.
                for site in sites:
                    with get_site_connection(site).cursor() as cursor:
                        cursor.execute("SELECT TOP (1) ma_khoa_hoc FROM dbo.KhoaHoc WHERE ma_mon = %s", [before["ma_mon"]])
                        if cursor.fetchone():
                            raise SharedCatalogConflict(f"Không thể xóa môn học đang được khóa học sử dụng tại {site}.")

            failed = []
            for site in sites:
                if events[site]:
                    continue
                try:
                    if action == "tao":
                        _apply_create(site=site, subject=after, event_id=event_ids[site],
                                      request_hash=request_hash, actor_id=actor_id)
                    else:
                        _apply_delete(site=site, before=before, event_id=event_ids[site],
                                      request_hash=request_hash, actor_id=actor_id)
                except (SharedCatalogConflict, IntegrityError):
                    raise
                except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
                    if site == registry_site:
                        raise SharedCatalogUnavailable(
                            "Site điều phối chưa xác nhận được thao tác; retry bằng cùng Idempotency-Key."
                        ) from exc
                    failed.append(site)

            result = after if action == "tao" else {"ma_mon": before["ma_mon"], "slug": before["slug"], "deleted": True}
            return {
                **result, "complete": not failed,
                "sites": [site for site in sites if site not in failed],
                "missing_sites": failed, "idempotent_replay": bool(replay_events),
            }
    except (SharedCatalogConflict, SharedCatalogNotFound, SharedCatalogUnavailable):
        raise
    except IntegrityError as exc:
        raise SharedCatalogConflict("Không thể thay đổi môn học do có dữ liệu nghiệp vụ đang tham chiếu.") from exc
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise SharedCatalogUnavailable("Không xác nhận được kết quả; retry cùng Idempotency-Key để đối soát.") from exc


def create_shared_subject(*, subject: dict, idempotency_key: str, actor_id: str) -> dict:
    return _write_subject(action="tao", subject=subject, slug=subject["slug"],
                          idempotency_key=idempotency_key, actor_id=actor_id)


def delete_shared_subject(*, slug: str, idempotency_key: str, actor_id: str) -> dict:
    return _write_subject(action="xoa", subject=None, slug=slug,
                          idempotency_key=idempotency_key, actor_id=actor_id)
