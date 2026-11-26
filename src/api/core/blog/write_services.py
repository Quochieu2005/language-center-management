"""Coordinator writes for the replicated Blog catalog."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, IntegrityError, connections, transaction

from core.academics.common import AcademicInfrastructureUnavailable, acquire_record_lock, active_site_state
from core.blog import sync_queue
from core.blog.services import PublicBlogConflict, PublicBlogNotFound, PublicBlogUnavailable
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias


_TABLES = {
    "category": ("DanhMucBlog", "ma_danh_muc_blog"),
    "article": ("BaiVietBlog", "ma_bai_viet_blog"),
}


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=lambda item: item.isoformat())


def _utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _record(entity: str, row) -> dict | None:
    if row is None:
        return None
    if entity == "category":
        return {
            "slug": str(row[1]), "name": str(row[2]),
            "description": None if row[3] is None else str(row[3]), "status": str(row[4]),
        }
    return {
        "slug": str(row[1]), "category_slug": str(row[2]), "title": str(row[3]),
        "excerpt": str(row[4]), "content": str(row[5]), "reading_time_minutes": int(row[6]),
        "status": str(row[7]), "published_at": _utc(row[8]),
        "cover_public_id": None if row[9] is None else str(row[9]),
        "cover_url": None if row[10] is None else str(row[10]),
    }


def _decode_event_value(entity: str, raw):
    # `before` is stored as a JSON string, `after` as a nested object inside the ACK payload.
    value = raw if isinstance(raw, dict) else (json.loads(raw) if raw else None)
    if value is not None and not isinstance(value, dict):
        raise ValueError("ACK payload must be an object")
    if entity == "article" and value and value.get("published_at"):
        value["published_at"] = _utc(datetime.fromisoformat(value["published_at"]))
    return value


def _read_record(cursor, entity: str, *, slug: str | None = None, record_id: str | None = None, lock=False):
    table, pk = _TABLES[entity]
    hint = " WITH (UPDLOCK, HOLDLOCK)" if lock else ""
    if entity == "category":
        where, value = (f"category.{pk} = %s", record_id) if record_id else ("category.slug = %s", slug)
        cursor.execute(
            f"SELECT category.{pk}, category.slug, category.ten_danh_muc, category.mo_ta, category.trang_thai "
            f"FROM dbo.{table} AS category{hint} WHERE {where}", [value],
        )
    else:
        where, value = (f"post.{pk} = %s", record_id) if record_id else ("post.slug = %s", slug)
        cursor.execute(
            f"SELECT post.{pk}, post.slug, category.slug, post.tieu_de, post.tom_tat, post.noi_dung, "
            f"post.so_phut_doc, post.trang_thai, post.ngay_xuat_ban_utc, post.anh_bia_public_id, post.anh_bia_url "
            f"FROM dbo.{table} AS post{hint} INNER JOIN dbo.DanhMucBlog AS category "
            f"ON category.ma_danh_muc_blog = post.ma_danh_muc_blog WHERE {where}", [value],
        )
    rows = cursor.fetchall()
    if len(rows) > 1:
        raise PublicBlogConflict("Slug Blog không duy nhất tại một site.")
    return (str(rows[0][0]), _record(entity, rows[0])) if rows else (None, None)


def _read_site(site: str, entity: str, slug: str, event_id: str):
    table, _ = _TABLES[entity]
    with get_site_connection(site).cursor() as cursor:
        cursor.execute(
            "SELECT bang_tac_dong, ma_ban_ghi, hanh_dong, ma_co_so, ket_qua, du_lieu_cu, du_lieu_moi "
            "FROM dbo.Logs WHERE loai_log = 'sync' AND ma_log = %s", [event_id],
        )
        rows = cursor.fetchall()
        if len(rows) > 1:
            raise PublicBlogConflict("Có nhiều ACK cho cùng một thao tác Blog.")
        event = None
        record_id = None
        if rows:
            raw = rows[0]
            if str(raw[0]) != table or str(raw[3]) != site or str(raw[4]) != "thanh_cong":
                raise PublicBlogConflict("ACK đồng bộ Blog không khớp bảng hoặc site.")
            record_id = str(raw[1])
            try:
                payload = json.loads(raw[6]) if raw[6] else {}
                if not record_id.isdecimal() or not isinstance(payload, dict):
                    raise ValueError("ACK identity or payload is invalid")
                event = {
                    "record_id": record_id,
                    "action": str(raw[2]),
                    "before": _decode_event_value(entity, raw[5]),
                    "after": _decode_event_value(entity, payload.get("after")),
                    "request_hash": payload.get("request_hash"),
                }
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise PublicBlogConflict("ACK Blog không đọc được; cần đối soát thủ công.") from exc
        _, current = _read_record(cursor, entity, record_id=record_id, slug=slug)
        return current, event


def _site_context():
    registry_site = str(getattr(settings, "AUTH_SESSION_SITE_CODE", "")).strip().upper()
    try:
        registry_alias = get_site_database_alias(registry_site)
        available, missing = active_site_state()
    except (AcademicInfrastructureUnavailable, DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise PublicBlogUnavailable("Không xác định được các site Blog đang hoạt động.") from exc
    sites = tuple(sorted(set(available)))
    if not sites or registry_site not in sites:
        raise PublicBlogUnavailable(
            "Site điều phối Blog chưa sẵn sàng; chưa ghi Blog.",
            site_codes=tuple(sorted(set(available) | set(missing))),
            missing_sites=missing or (registry_site,),
        )
    # Sites are independent: write to every reachable one, report the rest as pending (retry with the same key).
    ordered = (registry_site,) + tuple(site for site in sites if site != registry_site)
    return registry_site, registry_alias, ordered, tuple(sorted(missing))


def _category_id(cursor, slug: str, *, require_active: bool):
    cursor.execute(
        "SELECT ma_danh_muc_blog, trang_thai FROM dbo.DanhMucBlog WITH (UPDLOCK, HOLDLOCK) WHERE slug = %s",
        [slug],
    )
    row = cursor.fetchone()
    if row is None or (require_active and str(row[1]) != "hoat_dong"):
        raise PublicBlogConflict("Danh mục bài viết không tồn tại hoặc đang ngừng hoạt động.")
    return int(row[0]), str(row[1])


def _preflight(entity: str, action: str, sites: tuple[str, ...], before, after):
    if entity == "category" and action == "xoa":
        for site in sites:
            with get_site_connection(site).cursor() as cursor:
                cursor.execute(
                    "SELECT TOP (1) ma_bai_viet_blog FROM dbo.BaiVietBlog WHERE ma_danh_muc_blog = "
                    "(SELECT ma_danh_muc_blog FROM dbo.DanhMucBlog WHERE slug = %s)", [before["slug"]],
                )
                if cursor.fetchone():
                    raise PublicBlogConflict(f"Không thể xóa danh mục đang được bài viết sử dụng tại {site}.")
    if entity == "article" and action != "xoa":
        category_states = {}
        for site in sites:
            with get_site_connection(site).cursor() as cursor:
                cursor.execute(
                    "SELECT ten_danh_muc, mo_ta, trang_thai FROM dbo.DanhMucBlog WHERE slug = %s",
                    [after["category_slug"]],
                )
                row = cursor.fetchone()
                if row is None:
                    raise PublicBlogConflict(f"Không tìm thấy danh mục bài viết tại {site}.")
                category_states[site] = (str(row[0]), None if row[1] is None else str(row[1]), str(row[2]))
        if len(set(category_states.values())) != 1:
            reference = next(iter(category_states.values()))
            inconsistent = tuple(site for site, value in category_states.items() if value != reference)
            raise PublicBlogConflict(
                "Bản sao danh mục bài viết đang lệch giữa các site.",
                site_codes=sites, inconsistent_sites=inconsistent,
            )
        if after["status"] == "da_xuat_ban" and next(iter(category_states.values()))[2] != "hoat_dong":
            raise PublicBlogConflict("Chỉ được xuất bản bài thuộc danh mục đang hoạt động.")
    if action in {"tao", "sua"} and after["slug"] != (before or {}).get("slug"):
        table, pk = _TABLES[entity]
        for site in sites:
            with get_site_connection(site).cursor() as cursor:
                cursor.execute(
                    f"SELECT {pk} FROM dbo.{table} WHERE slug = %s", [after["slug"]]
                )
                if cursor.fetchone():
                    # A slug change must not overwrite another record at any replica.
                    raise PublicBlogConflict(
                        f"Slug mới đã tồn tại tại {site}.", site_codes=sites, inconsistent_sites=(site,)
                    )


def _apply_site(*, site: str, entity: str, action: str, expected, after, event_id: str, request_hash: str, actor_id: str):
    table, _ = _TABLES[entity]
    alias = get_site_database_alias(site)
    slug = after["slug"] if action == "tao" else expected["slug"]
    with transaction.atomic(using=alias), connections[alias].cursor() as cursor:
        local_id, current = _read_record(cursor, entity, slug=slug, lock=True)
        if current != expected:
            raise PublicBlogConflict("Bản Blog đã thay đổi trong lúc đồng bộ; hãy tải lại dữ liệu.")
        if action == "tao":
            if entity == "category":
                cursor.execute(
                    "INSERT INTO dbo.DanhMucBlog (slug, ten_danh_muc, mo_ta, trang_thai) VALUES (%s, %s, %s, %s)",
                    [after["slug"], after["name"], after["description"], after["status"]],
                )
            else:
                category_id, _ = _category_id(cursor, after["category_slug"], require_active=after["status"] == "da_xuat_ban")
                cursor.execute(
                    "INSERT INTO dbo.BaiVietBlog (ma_danh_muc_blog, slug, tieu_de, tom_tat, noi_dung, "
                    "so_phut_doc, trang_thai, ngay_xuat_ban_utc, anh_bia_public_id, anh_bia_url) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    [category_id, after["slug"], after["title"], after["excerpt"], after["content"],
                     after["reading_time_minutes"], after["status"],
                     after["published_at"].replace(tzinfo=None) if after["published_at"] else None,
                     after.get("cover_public_id"), after.get("cover_url")],
                )
            # SCOPE_IDENTITY() is NULL here (the INSERT ran in another batch scope); slug is unique per site.
            cursor.execute(f"SELECT {_TABLES[entity][1]} FROM dbo.{table} WHERE slug = %s", [after["slug"]])
            local_id = str(cursor.fetchone()[0])
        elif action == "sua":
            if entity == "category":
                cursor.execute(
                    "UPDATE dbo.DanhMucBlog SET slug = %s, ten_danh_muc = %s, mo_ta = %s, trang_thai = %s, "
                    "cap_nhat_luc_utc = SYSUTCDATETIME() WHERE ma_danh_muc_blog = %s",
                    [after["slug"], after["name"], after["description"], after["status"], local_id],
                )
            else:
                category_id, _ = _category_id(cursor, after["category_slug"], require_active=after["status"] == "da_xuat_ban")
                cursor.execute(
                    "UPDATE dbo.BaiVietBlog SET ma_danh_muc_blog = %s, slug = %s, tieu_de = %s, tom_tat = %s, "
                    "noi_dung = %s, so_phut_doc = %s, trang_thai = %s, ngay_xuat_ban_utc = %s, "
                    "anh_bia_public_id = %s, anh_bia_url = %s, "
                    "cap_nhat_luc_utc = SYSUTCDATETIME() WHERE ma_bai_viet_blog = %s",
                    [category_id, after["slug"], after["title"], after["excerpt"], after["content"],
                     after["reading_time_minutes"], after["status"],
                     after["published_at"].replace(tzinfo=None) if after["published_at"] else None,
                     after.get("cover_public_id"), after.get("cover_url"), local_id],
                )
        else:
            if entity == "category":
                cursor.execute(
                    "DELETE FROM dbo.DanhMucBlog WHERE ma_danh_muc_blog = %s AND NOT EXISTS "
                    "(SELECT 1 FROM dbo.BaiVietBlog WHERE ma_danh_muc_blog = %s)", [local_id, local_id],
                )
            else:
                cursor.execute("DELETE FROM dbo.BaiVietBlog WHERE ma_bai_viet_blog = %s", [local_id])
            if cursor.rowcount != 1:
                raise PublicBlogConflict("Không xóa được Blog; có thể dữ liệu đã thay đổi hoặc còn bài viết tham chiếu.")
            local_id = str(local_id)
        _, actual = _read_record(cursor, entity, record_id=local_id, lock=True) if action != "xoa" else (None, None)
        if actual != after:
            raise PublicBlogConflict("Không xác nhận được nội dung Blog sau khi ghi tại một site.")
        cursor.execute(
            "INSERT INTO dbo.Logs (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, "
            "ma_ban_ghi, du_lieu_cu, du_lieu_moi, ket_qua, site_dich) "
            "VALUES (%s, 'sync', %s, %s, %s, %s, %s, %s, %s, 'thanh_cong', %s)",
            [event_id, site, actor_id, action, table, local_id, _json(expected),
             _json({"request_hash": request_hash, "after": after}), site],
        )


def write_blog(*, entity: str, action: str, slug: str, payload: dict | None,
               idempotency_key: str, actor_id: str) -> dict:
    if entity not in _TABLES or action not in {"tao", "sua", "xoa"}:
        raise ValueError("Unsupported Blog operation")
    slug = str(slug or "").strip().lower()
    if payload and entity == "article" and payload.get("published_at") is not None:
        payload = {**payload, "published_at": _utc(payload["published_at"])}
    registry_site, registry_alias, sites, offline = _site_context()
    request_hash = hashlib.sha256(_json({"entity": entity, "action": action, "slug": slug, "payload": payload}).encode()).hexdigest()
    key_digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
    event_ids = {site: f"BLOG-{entity[:3].upper()}-{site}-{key_digest[:64]}" for site in sites}
    try:
        with transaction.atomic(using=registry_alias):
            with connections[registry_alias].cursor() as cursor:
                acquire_record_lock(cursor, "shared-catalog:Blog")
            states = {site: _read_site(site, entity, slug, event_ids[site]) for site in sites}
            events = {site: state[1] for site, state in states.items()}
            replay = [event for event in events.values() if event]
            current = {site: state[0] for site, state in states.items()}

            if replay:
                transition = replay[0]
                if any(event["action"] != action or event["request_hash"] != request_hash
                       or event["before"] != transition["before"] or event["after"] != transition["after"]
                       for event in replay):
                    raise PublicBlogConflict(
                        "Idempotency-Key đã dùng với nội dung khác hoặc ACK không thống nhất.",
                        site_codes=sites,
                        inconsistent_sites=tuple(
                            site for site, event in events.items() if event and (
                                event["action"], event["request_hash"], event["before"], event["after"]
                            ) != (
                                transition["action"], transition["request_hash"],
                                transition["before"], transition["after"],
                            )
                        ),
                    )
                before, after = transition["before"], transition["after"]
                if action == "tao" and after != payload:
                    raise PublicBlogConflict("ACK tạo Blog không khớp nội dung yêu cầu.")
                if action == "sua" and (before is None or after != {**before, **payload}):
                    raise PublicBlogConflict("ACK sửa Blog không khớp nội dung yêu cầu.")
                if action == "xoa" and (before is None or after is not None):
                    raise PublicBlogConflict("ACK xóa Blog không hợp lệ.")
                inconsistent = tuple(
                    site for site in sites if current[site] != (after if events[site] else before)
                )
                if inconsistent:
                    raise PublicBlogConflict(
                        "Bản sao Blog lệch ACK; cần đối soát trước khi retry.",
                        site_codes=sites, inconsistent_sites=inconsistent,
                    )
            else:
                copies = list(current.values())
                if action == "tao":
                    if any(copy is not None for copy in copies):
                        raise PublicBlogConflict("Slug đã tồn tại tại một site.")
                    before, after = None, dict(payload)
                else:
                    if all(copy is None for copy in copies):
                        raise PublicBlogNotFound("Không tìm thấy Blog tại các site hoạt động.", site_codes=sites)
                    if any(copy is None or copy != copies[0] for copy in copies):
                        raise PublicBlogConflict(
                            "Các bản sao Blog không thống nhất; không thể sửa hoặc xóa an toàn.",
                            site_codes=sites,
                            inconsistent_sites=tuple(site for site in sites if current[site] != copies[0]),
                        )
                    before = copies[0]
                    after = {**before, **payload} if action == "sua" else None

            # Sites that already ACKed this operation are done; checking them again would reject a replay
            # (for example "slug already exists" on a create that this very operation made).
            todo = tuple(site for site in sites if not events[site])
            if todo:
                _preflight(entity, action, todo, before, after)
            failed = []
            # shortcut: commits are site-local and retried forward; use DBMS-wide coordination only if required by the course rubric.
            for site in sites:
                if events[site]:
                    continue
                expected = before
                try:
                    _apply_site(
                        site=site, entity=entity, action=action, expected=expected, after=after,
                        event_id=event_ids[site], request_hash=request_hash, actor_id=actor_id,
                    )
                except (PublicBlogConflict, IntegrityError):
                    raise
                except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
                    if site == registry_site:
                        raise PublicBlogUnavailable(
                            "Site điều phối chưa xác nhận được thao tác; retry bằng cùng Idempotency-Key.",
                            site_codes=sites, missing_sites=(site,),
                        ) from exc
                    failed.append(site)

            result = after if after is not None else {"slug": before["slug"], "deleted": True}
            if failed or offline:
                # Sites that missed it catch up through the worker (replay with the same key).
                sync_queue.enqueue(
                    registry_alias, entity=entity, action=action, slug=slug, payload=payload,
                    idempotency_key=idempotency_key, request_hash=request_hash, actor_id=actor_id,
                )
            return {
                "scope": "REPLICATED-WRITE", "complete": not failed and not offline,
                "site_codes": list(sites) + list(offline), "missing_sites": sorted(set(failed) | set(offline)),
                "idempotent_replay": bool(replay), "result": result,
            }
    except (PublicBlogConflict, PublicBlogNotFound, PublicBlogUnavailable):
        raise
    except IntegrityError as exc:
        raise PublicBlogConflict("Slug đã tồn tại hoặc dữ liệu Blog đang được tham chiếu.", site_codes=sites) from exc
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise PublicBlogUnavailable(
            "Không xác nhận được kết quả Blog; retry bằng cùng Idempotency-Key để đối soát.",
            site_codes=sites, missing_sites=sites,
        ) from exc


def create_blog_category(*, category: dict, idempotency_key: str, actor_id: str) -> dict:
    return write_blog(entity="category", action="tao", slug=category["slug"], payload=category,
                      idempotency_key=idempotency_key, actor_id=actor_id)


def update_blog_category(*, slug: str, patch: dict, idempotency_key: str, actor_id: str) -> dict:
    return write_blog(entity="category", action="sua", slug=slug, payload=patch,
                      idempotency_key=idempotency_key, actor_id=actor_id)


def delete_blog_category(*, slug: str, idempotency_key: str, actor_id: str) -> dict:
    return write_blog(entity="category", action="xoa", slug=slug, payload=None,
                      idempotency_key=idempotency_key, actor_id=actor_id)


def create_blog_article(*, article: dict, idempotency_key: str, actor_id: str) -> dict:
    return write_blog(entity="article", action="tao", slug=article["slug"], payload=article,
                      idempotency_key=idempotency_key, actor_id=actor_id)


def update_blog_article(*, slug: str, patch: dict, idempotency_key: str, actor_id: str) -> dict:
    return write_blog(entity="article", action="sua", slug=slug, payload=patch,
                      idempotency_key=idempotency_key, actor_id=actor_id)


def delete_blog_article(*, slug: str, idempotency_key: str, actor_id: str) -> dict:
    return write_blog(entity="article", action="xoa", slug=slug, payload=None,
                      idempotency_key=idempotency_key, actor_id=actor_id)
