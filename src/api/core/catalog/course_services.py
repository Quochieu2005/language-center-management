"""Replicated writes for the shared KhoaHoc catalog."""

from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, IntegrityError, connections, transaction

from core.academics.common import AcademicInfrastructureUnavailable, acquire_record_lock, active_site_state
from core.catalog.services import (
    SharedCatalogConflict,
    SharedCatalogNotFound,
    SharedCatalogUnavailable,
)
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias


_COURSE_FIELDS = {
    "ma_khoa_hoc", "slug", "ma_mon", "ten_khoa_hoc", "trinh_do",
    "so_buoi", "hoc_phi_chuan", "phien_ban",
}


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _course(row) -> dict | None:
    if row is None:
        return None
    return {
        "ma_khoa_hoc": str(row[0]), "slug": str(row[1]), "ma_mon": str(row[2]),
        "ten_khoa_hoc": str(row[3]), "trinh_do": str(row[4]), "so_buoi": int(row[5]),
        "hoc_phi_chuan": int(row[6]), "phien_ban": int(row[7]),
    }


def _read_site_course(site: str, *, slug: str, course_id: str | None, event_id: str):
    with get_site_connection(site).cursor() as cursor:
        if course_id:
            cursor.execute(
                "SELECT ma_khoa_hoc, slug, ma_mon, ten_khoa_hoc, trinh_do, so_buoi, "
                "hoc_phi_chuan, phien_ban FROM dbo.KhoaHoc "
                "WHERE ma_khoa_hoc = %s OR slug = %s",
                [course_id, slug],
            )
        else:
            cursor.execute(
                "SELECT ma_khoa_hoc, slug, ma_mon, ten_khoa_hoc, trinh_do, so_buoi, "
                "hoc_phi_chuan, phien_ban FROM dbo.KhoaHoc WHERE slug = %s",
                [slug],
            )
        rows = cursor.fetchall()
        if len(rows) > 1:
            raise SharedCatalogConflict("Mã khóa học và slug đang trỏ tới các bản ghi khác nhau.")
        cursor.execute(
            "SELECT bang_tac_dong, ma_ban_ghi, hanh_dong, site_dich, ket_qua, "
            "du_lieu_cu, du_lieu_moi FROM dbo.Logs WHERE loai_log = 'sync' AND ma_log = %s",
            [event_id],
        )
        events = cursor.fetchall()
        if len(events) > 1:
            raise SharedCatalogConflict("Có nhiều ACK cho cùng một thao tác khóa học.")
    current = _course(rows[0]) if rows else None
    event = None
    if events:
        raw = events[0]
        if (
            str(raw[0]) != "KhoaHoc" or str(raw[3]) != site
            or str(raw[4]) != "thanh_cong" or str(raw[2]) not in {"tao", "sua"}
            or (current is not None and str(raw[1]) != current["ma_khoa_hoc"])
        ):
            raise SharedCatalogConflict("ACK trong Logs không khớp khóa học/site.")
        try:
            before = json.loads(raw[5]) if raw[5] is not None else None
            payload = json.loads(raw[6]) if raw[6] is not None else {}
            event = {"record_id": str(raw[1]), "action": str(raw[2]), "before": before, **payload}
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SharedCatalogConflict("ACK khóa học không đọc được; cần đối soát thủ công.") from exc
    return current, event


def _validate_event(event: dict, *, action: str, course_id: str, request_hash: str):
    before, after = event.get("before"), event.get("after")
    valid_before = before is None if action == "tao" else isinstance(before, dict) and set(before) == _COURSE_FIELDS
    valid_transition = (
        isinstance(after, dict)
        and set(after) == _COURSE_FIELDS
        and after.get("ma_khoa_hoc") == course_id
        and isinstance(after.get("phien_ban"), int)
        and not isinstance(after.get("phien_ban"), bool)
        and (
            (action == "tao" and after["phien_ban"] == 1)
            or (
                action == "sua" and valid_before
                and isinstance(before.get("phien_ban"), int)
                and after["phien_ban"] == before["phien_ban"] + 1
            )
        )
    )
    if (
        event.get("action") != action or event.get("record_id") != course_id
        or event.get("request_hash") != request_hash or not valid_before or not valid_transition
    ):
        raise SharedCatalogConflict("Idempotency-Key đã dùng với nội dung khác hoặc ACK không hợp lệ.")
    return before, after


def _check_subject_replicas(sites: tuple[str, ...], subject_id: str) -> None:
    snapshots = []
    for site in sites:
        with get_site_connection(site).cursor() as cursor:
            cursor.execute(
                "SELECT ma_mon, slug, ten_mon, mo_ta, phien_ban "
                "FROM dbo.MonHoc WHERE ma_mon = %s",
                [subject_id],
            )
            rows = cursor.fetchall()
        if len(rows) != 1:
            raise SharedCatalogNotFound("Môn học không tồn tại trên tất cả site hoạt động.")
        snapshots.append(tuple(rows[0]))
    if any(snapshot != snapshots[0] for snapshot in snapshots[1:]):
        raise SharedCatalogConflict("Các bản sao môn học đang khác nhau; cần đồng bộ trước khi tạo/sửa khóa học.")


def _apply_site(
    *, site: str, before: dict | None, after: dict, event_id: str,
    request_hash: str, actor_id: str,
) -> None:
    alias = get_site_database_alias(site)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            if before is None:
                cursor.execute(
                    "SELECT ma_khoa_hoc FROM dbo.KhoaHoc WITH (UPDLOCK, HOLDLOCK) "
                    "WHERE ma_khoa_hoc = %s OR slug = %s",
                    [after["ma_khoa_hoc"], after["slug"]],
                )
                if cursor.fetchall():
                    raise SharedCatalogConflict("Mã khóa học hoặc slug đã tồn tại ở một site.")
                cursor.execute(
                    "INSERT INTO dbo.KhoaHoc "
                    "(ma_khoa_hoc, slug, ma_mon, ten_khoa_hoc, trinh_do, so_buoi, hoc_phi_chuan, phien_ban) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    [after["ma_khoa_hoc"], after["slug"], after["ma_mon"], after["ten_khoa_hoc"],
                     after["trinh_do"], after["so_buoi"], after["hoc_phi_chuan"], after["phien_ban"]],
                )
            else:
                cursor.execute(
                    "SELECT ma_khoa_hoc, slug, ma_mon, ten_khoa_hoc, trinh_do, so_buoi, "
                    "hoc_phi_chuan, phien_ban FROM dbo.KhoaHoc WITH (UPDLOCK, HOLDLOCK) "
                    "WHERE ma_khoa_hoc = %s",
                    [before["ma_khoa_hoc"]],
                )
                rows = cursor.fetchall()
                if len(rows) != 1 or _course(rows[0]) != before:
                    raise SharedCatalogConflict("Bản sao khóa học đã thay đổi; cần đối soát trước khi ghi.")
                cursor.execute(
                    "UPDATE dbo.KhoaHoc SET ma_mon = %s, ten_khoa_hoc = %s, trinh_do = %s, "
                    "so_buoi = %s, hoc_phi_chuan = %s, phien_ban = %s, cap_nhat_luc = SYSUTCDATETIME() "
                    "WHERE ma_khoa_hoc = %s AND phien_ban = %s",
                    [after["ma_mon"], after["ten_khoa_hoc"], after["trinh_do"], after["so_buoi"],
                     after["hoc_phi_chuan"], after["phien_ban"], before["ma_khoa_hoc"], before["phien_ban"]],
                )
            cursor.execute(
                "SELECT ma_khoa_hoc, slug, ma_mon, ten_khoa_hoc, trinh_do, so_buoi, hoc_phi_chuan, phien_ban "
                "FROM dbo.KhoaHoc WHERE ma_khoa_hoc = %s",
                [after["ma_khoa_hoc"]],
            )
            rows = cursor.fetchall()
            if len(rows) != 1 or _course(rows[0]) != after:
                raise SharedCatalogConflict("Không xác nhận được dữ liệu khóa học sau khi ghi.")
            cursor.execute(
                "INSERT INTO dbo.Logs "
                "(ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, "
                "ma_ban_ghi, du_lieu_cu, du_lieu_moi, ket_qua, site_dich) "
                "VALUES (%s, 'sync', %s, %s, %s, 'KhoaHoc', %s, %s, %s, 'thanh_cong', %s)",
                [event_id, site, actor_id, "tao" if before is None else "sua", after["ma_khoa_hoc"],
                 _json(before), _json({"request_hash": request_hash, "after": after}), site],
            )


def _write_course(*, action: str, slug: str, payload: dict, idempotency_key: str, actor_id: str):
    registry_site = str(getattr(settings, "AUTH_SESSION_SITE_CODE", "")).strip().upper()
    try:
        registry_alias = get_site_database_alias(registry_site)
        sites, missing_sites = active_site_state()
    except (AcademicInfrastructureUnavailable, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise SharedCatalogUnavailable from exc
    if missing_sites or not sites:
        raise SharedCatalogUnavailable(
            "Một hoặc nhiều site đang hoạt động chưa sẵn sàng; chưa bắt đầu ghi khóa học.",
            missing_sites=missing_sites,
        )

    course_id = payload["ma_khoa_hoc"] if action == "tao" else None
    identity = {"action": action, "slug": slug, "payload": payload}
    request_hash = hashlib.sha256(_json(identity).encode("utf-8")).hexdigest()
    key_digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    ordered_sites = (registry_site,) + tuple(site for site in sorted(sites) if site != registry_site)
    event_ids = {site: f"KHREP-{site}-{key_digest[:64]}" for site in ordered_sites}

    try:
        with transaction.atomic(using=registry_alias):
            with connections[registry_alias].cursor() as cursor:
                acquire_record_lock(cursor, "shared-catalog:KhoaHoc")
            states = {
                site: _read_site_course(site, slug=slug, course_id=course_id, event_id=event_ids[site])
                for site in ordered_sites
            }
            current = {site: state[0] for site, state in states.items()}
            events = {site: state[1] for site, state in states.items()}
            if action == "tao":
                existing_events = [event for event in events.values() if event]
                if existing_events:
                    transitions = [
                        _validate_event(event, action=action, course_id=course_id, request_hash=request_hash)
                        for event in existing_events
                    ]
                    before, after = transitions[0]
                    if any(transition != transitions[0] for transition in transitions[1:]):
                        raise SharedCatalogConflict("ACK tạo khóa học không thống nhất giữa các site.")
                    for site in ordered_sites:
                        if events[site]:
                            if current[site] is None or current[site]["phien_ban"] < after["phien_ban"]:
                                raise SharedCatalogConflict("ACK tồn tại nhưng bản sao khóa học bị thiếu hoặc cũ.")
                            if current[site]["phien_ban"] == after["phien_ban"] and current[site] != after:
                                raise SharedCatalogConflict("Bản sao khóa học không khớp ACK; cần đối soát.")
                        elif current[site] is not None:
                            raise SharedCatalogConflict("Site chưa ACK nhưng đã có dữ liệu khóa học khác.")
                else:
                    if any(course is not None for course in current.values()):
                        raise SharedCatalogConflict("Mã khóa học hoặc slug đã tồn tại; hãy chọn mã/slug khác.")
                    before = None
                    after = {**payload, "phien_ban": 1}
            else:
                if any(course is None for course in current.values()):
                    raise SharedCatalogNotFound("Không tìm thấy khóa học đồng nhất ở mọi site hoạt động.")
                ids = {course["ma_khoa_hoc"] for course in current.values()}
                if len(ids) != 1:
                    raise SharedCatalogConflict("Các site đang gán slug khóa học cho mã khác nhau.")
                course_id = next(iter(ids))
                existing_events = [event for event in events.values() if event]
                if existing_events:
                    transitions = [
                        _validate_event(event, action=action, course_id=course_id, request_hash=request_hash)
                        for event in existing_events
                    ]
                    before, after = transitions[0]
                    if any(transition != transitions[0] for transition in transitions[1:]):
                        raise SharedCatalogConflict("ACK cập nhật khóa học không thống nhất giữa các site.")
                    for site in ordered_sites:
                        if events[site]:
                            if current[site]["phien_ban"] < after["phien_ban"]:
                                raise SharedCatalogConflict("ACK tồn tại nhưng bản sao khóa học thấp hơn phiên bản.")
                            if current[site]["phien_ban"] == after["phien_ban"] and current[site] != after:
                                raise SharedCatalogConflict("Bản sao khóa học không khớp ACK; cần đối soát.")
                        elif current[site] != before:
                            raise SharedCatalogConflict("Site chưa ACK nhưng dữ liệu khóa học đã thay đổi.")
                else:
                    before_values = list(current.values())
                    if any(course != before_values[0] for course in before_values[1:]):
                        raise SharedCatalogConflict("Các bản sao khóa học đang khác nhau; cần đồng bộ trước khi sửa.")
                    before = before_values[0]
                    after = {**before, **payload, "phien_ban": before["phien_ban"] + 1}

            _check_subject_replicas(ordered_sites, after["ma_mon"])
            failed_sites = []
            for site in ordered_sites:
                if events[site]:
                    continue
                try:
                    _apply_site(
                        site=site, before=before, after=after, event_id=event_ids[site],
                        request_hash=request_hash, actor_id=actor_id,
                    )
                except SharedCatalogConflict:
                    raise
                except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
                    if site == registry_site:
                        raise SharedCatalogUnavailable from exc
                    failed_sites.append(site)
            return {
                **after, "complete": not failed_sites,
                "sites": [site for site in ordered_sites if site not in failed_sites],
                "missing_sites": failed_sites, "idempotent_replay": bool(existing_events),
            }
    except (SharedCatalogConflict, SharedCatalogNotFound, SharedCatalogUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise SharedCatalogUnavailable from exc


def create_shared_course(*, course: dict, idempotency_key: str, actor_id: str) -> dict:
    return _write_course(
        action="tao", slug=course["slug"], payload=course,
        idempotency_key=idempotency_key, actor_id=actor_id,
    )


def update_shared_course(*, slug: str, patch: dict, idempotency_key: str, actor_id: str) -> dict:
    return _write_course(
        action="sua", slug=slug, payload=patch,
        idempotency_key=idempotency_key, actor_id=actor_id,
    )


def _validate_delete_event(event: dict, *, course_id: str, request_hash: str) -> dict:
    before = event.get("before")
    if (
        event.get("action") != "xoa"
        or event.get("record_id") != course_id
        or event.get("request_hash") != request_hash
        or "after" not in event
        or event["after"] is not None
        or not isinstance(before, dict)
        or set(before) != _COURSE_FIELDS
    ):
        raise SharedCatalogConflict("Idempotency-Key đã dùng với nội dung khác hoặc ACK xóa không hợp lệ.")
    return before


def _delete_course_replicas(
    *, sites: tuple[str, ...], registry_alias: str, before: dict,
    events: dict, event_ids: dict, request_hash: str, actor_id: str,
) -> None:
    aliases = {site: get_site_database_alias(site) for site in sites}
    with ExitStack() as stack:
        for site in sites:
            if aliases[site] != registry_alias:
                stack.enter_context(transaction.atomic(using=aliases[site]))

        for site in sites:
            with connections[aliases[site]].cursor() as cursor:
                cursor.execute(
                    "SELECT ma_khoa_hoc, slug, ma_mon, ten_khoa_hoc, trinh_do, so_buoi, "
                    "hoc_phi_chuan, phien_ban FROM dbo.KhoaHoc WITH (UPDLOCK, HOLDLOCK) "
                    "WHERE ma_khoa_hoc = %s OR slug = %s",
                    [before["ma_khoa_hoc"], before["slug"]],
                )
                rows = cursor.fetchall()
                current = _course(rows[0]) if len(rows) == 1 else None
                if len(rows) > 1 or (events[site] and current is not None):
                    raise SharedCatalogConflict("Khóa học đã thay đổi trong lúc xóa; hãy tải lại danh mục.")
                if not events[site] and current != before:
                    raise SharedCatalogConflict("Bản sao khóa học đã thay đổi; không thể xóa an toàn.")

                cursor.execute(
                    "SELECT TOP (1) ma_lop FROM dbo.LopHoc WITH (HOLDLOCK) WHERE ma_khoa_hoc = %s",
                    [before["ma_khoa_hoc"]],
                )
                if cursor.fetchall():
                    raise SharedCatalogConflict(
                        f"Không thể xóa khóa học đang được lớp sử dụng tại cơ sở {site}."
                    )

        for site in sites:
            if events[site]:
                continue
            with connections[aliases[site]].cursor() as cursor:
                cursor.execute(
                    "DELETE FROM dbo.KhoaHoc WHERE ma_khoa_hoc = %s AND slug = %s AND phien_ban = %s",
                    [before["ma_khoa_hoc"], before["slug"], before["phien_ban"]],
                )
                cursor.execute(
                    "SELECT ma_khoa_hoc FROM dbo.KhoaHoc WHERE ma_khoa_hoc = %s OR slug = %s",
                    [before["ma_khoa_hoc"], before["slug"]],
                )
                if cursor.fetchall():
                    raise SharedCatalogConflict("Không xác nhận được việc xóa khóa học tại một site.")
                cursor.execute(
                    "INSERT INTO dbo.Logs "
                    "(ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, "
                    "ma_ban_ghi, du_lieu_cu, du_lieu_moi, ket_qua, site_dich) "
                    "VALUES (%s, 'sync', %s, %s, 'xoa', 'KhoaHoc', %s, %s, %s, 'thanh_cong', %s)",
                    [event_ids[site], site, actor_id, before["ma_khoa_hoc"], _json(before),
                     _json({"request_hash": request_hash, "after": None}), site],
                )


def delete_shared_course(*, slug: str, idempotency_key: str, actor_id: str) -> dict:
    """Hard-delete an unused shared course; preserve per-site ACKs for safe retries."""
    registry_site = str(getattr(settings, "AUTH_SESSION_SITE_CODE", "")).strip().upper()
    try:
        registry_alias = get_site_database_alias(registry_site)
        sites, missing_sites = active_site_state()
    except (AcademicInfrastructureUnavailable, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise SharedCatalogUnavailable from exc
    if missing_sites or not sites:
        raise SharedCatalogUnavailable(
            "Một hoặc nhiều site hoạt động chưa sẵn sàng; không bắt đầu xóa khóa học.",
            missing_sites=missing_sites,
        )

    key_digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    request_hash = hashlib.sha256(_json({"action": "xoa", "slug": slug, "payload": {}}).encode("utf-8")).hexdigest()
    ordered_sites = (registry_site,) + tuple(site for site in sorted(sites) if site != registry_site)
    event_ids = {site: f"KHDEL-{site}-{key_digest}" for site in ordered_sites}

    try:
        with transaction.atomic(using=registry_alias):
            with connections[registry_alias].cursor() as cursor:
                acquire_record_lock(cursor, "shared-catalog:KhoaHoc")
            states = {
                site: _read_site_course(site, slug=slug, course_id=None, event_id=event_ids[site])
                for site in ordered_sites
            }
            current = {site: state[0] for site, state in states.items()}
            events = {site: state[1] for site, state in states.items()}
            existing_events = [event for event in events.values() if event]
            if existing_events:
                before = _validate_delete_event(
                    existing_events[0], course_id=existing_events[0]["record_id"], request_hash=request_hash
                )
                course_id = before["ma_khoa_hoc"]
                for event in existing_events[1:]:
                    if _validate_delete_event(event, course_id=course_id, request_hash=request_hash) != before:
                        raise SharedCatalogConflict("ACK xóa khóa học không thống nhất giữa các site.")
                for site in ordered_sites:
                    if events[site] and current[site] is not None:
                        raise SharedCatalogConflict("Khóa học đã được tạo lại sau khi ghi ACK xóa.")
                    if not events[site] and current[site] != before:
                        raise SharedCatalogConflict("Bản sao chưa ACK đã thay đổi; cần đối soát trước khi xóa tiếp.")
            else:
                values = list(current.values())
                if all(course is None for course in values):
                    raise SharedCatalogNotFound("Không tìm thấy khóa học.")
                if any(course is None for course in values) or any(course != values[0] for course in values[1:]):
                    raise SharedCatalogConflict("Các bản sao khóa học không thống nhất; cần đối soát trước khi xóa.")
                before = values[0]
                course_id = before["ma_khoa_hoc"]

            _delete_course_replicas(
                sites=ordered_sites, registry_alias=registry_alias, before=before, events=events,
                event_ids=event_ids, request_hash=request_hash, actor_id=actor_id,
            )
            return {
                "ma_khoa_hoc": course_id,
                "slug": slug,
                "deleted": True,
                "complete": True,
                "sites": list(ordered_sites),
                "missing_sites": [],
                "idempotent_replay": bool(existing_events),
            }
    except SharedCatalogConflict:
        raise
    except IntegrityError as exc:
        raise SharedCatalogConflict(
            "Khóa học vừa được sử dụng bởi một lớp hoặc ACK bị xung đột; tải lại dữ liệu trước khi thử lại."
        ) from exc
    except (SharedCatalogNotFound, SharedCatalogUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise SharedCatalogUnavailable(
            "Không xác nhận được kết quả xóa; retry bằng cùng Idempotency-Key để đối soát."
        ) from exc
