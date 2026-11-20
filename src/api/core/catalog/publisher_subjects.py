"""Write MonHoc once at its Publisher; verify replicas after that local commit."""

from contextlib import ExitStack
import hashlib
import json

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, IntegrityError, connections, transaction

from core.academics.common import AcademicInfrastructureUnavailable, acquire_record_lock, active_site_state
from core.auth.service_common import AuthInfrastructureUnavailable
from core.catalog.services import SharedCatalogConflict, SharedCatalogNotFound, SharedCatalogUnavailable
from core.sites.connections import UnknownSiteError, get_site_connection, get_site_database_alias
from core.slug_utils import make_slug


_UNAVAILABLE = (DatabaseError, ImproperlyConfigured, UnknownSiteError, KeyError,
                AcademicInfrastructureUnavailable, AuthInfrastructureUnavailable)
_FIELDS = ("ma_mon", "slug", "ten_mon", "mo_ta", "phien_ban")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_subject(site, *, record_id=None, slug=None, locked=False):
    with get_site_connection(site).cursor() as cursor:
        # Check both identities to detect a slug reused for another record.
        lock_hint = " WITH (UPDLOCK, HOLDLOCK)" if locked else ""
        cursor.execute(
            "SELECT ma_mon, slug, ten_mon, mo_ta, phien_ban FROM dbo.MonHoc"
            + lock_hint + " WHERE ma_mon = %s OR slug = %s", [record_id, slug],
        )
        rows = cursor.fetchall()
    if len(rows) > 1:
        raise SharedCatalogConflict("Mã và slug môn học đang trỏ tới hai bản ghi.")
    return dict(zip(_FIELDS, rows[0])) if rows else None


def _read_receipt(cursor, event_id, publisher):
    cursor.execute(
        "SELECT bang_tac_dong, hanh_dong, site_dich, ket_qua, du_lieu_cu, du_lieu_moi "
        "FROM dbo.Logs WHERE ma_log = %s AND loai_log = 'sync'", [event_id],
    )
    row = cursor.fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(row[5])
        before = json.loads(row[4]) if row[4] else None
        if (row[0] != "MonHoc" or row[2] != publisher or row[3] != "thanh_cong"
                or payload["mechanism"] != "sql-publication"
                or row[1] != payload["action"]):
            raise ValueError
        return {**payload, "before": before}
    except (ValueError, TypeError, KeyError) as exc:
        raise SharedCatalogConflict("Biên nhận Publisher không hợp lệ; cần đối soát.") from exc


def _preflight(sites, *, action, before, after):
    expected = None if action == "tao" else before
    identity = after if action == "tao" else before
    for site in sites:
        try:
            current = _read_subject(site, record_id=identity["ma_mon"], slug=identity["slug"])
            if current != expected:
                raise SharedCatalogConflict(f"Bản sao môn học tại {site} chưa đồng nhất; cần đối soát.")
            if action == "sua" and after["slug"] != before["slug"]:
                other = _read_subject(site, slug=after["slug"])
                if other is not None:
                    raise SharedCatalogConflict(f"Slug mới đã được dùng tại {site}.")
            if action == "xoa":
                with get_site_connection(site).cursor() as cursor:
                    cursor.execute("SELECT TOP (1) ma_khoa_hoc FROM dbo.KhoaHoc WHERE ma_mon = %s",
                                   [before["ma_mon"]])
                    if cursor.fetchone():
                        raise SharedCatalogConflict(f"Môn học đang được khóa học sử dụng tại {site}.")
        except _UNAVAILABLE as exc:
            raise SharedCatalogUnavailable("Chưa ghi môn học: một site chưa sẵn sàng.",
                                           missing_sites=(site,)) from exc


def _apply_change(cursor, *, action, before, after, publisher, event_id, request_hash, actor_id):
    if action == "tao":
        cursor.execute(
            "INSERT INTO dbo.MonHoc (ma_mon, slug, ten_mon, mo_ta, phien_ban) VALUES (%s, %s, %s, %s, 1)",
            [after[field] for field in _FIELDS[:4]],
        )
    elif action == "sua":
        cursor.execute(
            "UPDATE dbo.MonHoc SET slug = %s, ten_mon = %s, mo_ta = %s, "
            "phien_ban = phien_ban + 1, cap_nhat_luc = SYSUTCDATETIME() "
            "WHERE ma_mon = %s AND phien_ban = %s",
            [after["slug"], after["ten_mon"], after["mo_ta"], before["ma_mon"], before["phien_ban"]],
        )
    else:
        cursor.execute("DELETE FROM dbo.MonHoc WHERE ma_mon = %s AND phien_ban = %s",
                       [before["ma_mon"], before["phien_ban"]])
    payload = {"mechanism": "sql-publication", "action": action,
               "request_hash": request_hash, "after": after}
    cursor.execute(
        "INSERT INTO dbo.Logs (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, "
        "bang_tac_dong, ma_ban_ghi, du_lieu_cu, du_lieu_moi, ket_qua, site_dich) "
        "VALUES (%s, 'sync', %s, %s, %s, 'MonHoc', %s, %s, %s, 'thanh_cong', %s)",
        [event_id, publisher, actor_id, action, (after or before)["ma_mon"],
         _json(before) if before else None, _json(payload), publisher],
    )


def _verify(sites, *, before, after, unavailable=()):
    confirmed, pending = [], []
    identity = after or before
    for site in sites:
        try:
            current = _read_subject(site, record_id=identity["ma_mon"], slug=identity["slug"])
            matches = site not in unavailable and current == after
        except (*_UNAVAILABLE, SharedCatalogConflict):
            matches = False
        (confirmed if matches else pending).append(site)
    result = after or {"ma_mon": before["ma_mon"], "slug": before["slug"], "deleted": True}
    return {**result, "complete": not pending, "sites": confirmed, "missing_sites": pending}


def write_subject(*, action, slug, payload, idempotency_key, actor_id):
    publisher = settings.MONHOC_PUBLISHER_SITE_CODE
    identity = {"action": action, "slug": slug, "payload": payload, "actor_id": actor_id}
    request_hash = hashlib.sha256(_json(identity).encode()).hexdigest()
    event_id = "MHSQL-" + hashlib.sha256(idempotency_key.encode()).hexdigest()
    try:
        alias = get_site_database_alias(publisher)
        available, missing = active_site_state()
        sites = tuple(sorted(set(available) | set(missing)))
        if publisher not in available:
            raise SharedCatalogUnavailable("Publisher môn học chưa sẵn sàng.", missing_sites=(publisher,))

        with ExitStack() as stack:
            if action == "xoa":
                # Serialize with existing API KhoaHoc writers before checking remote references.
                registry = get_site_database_alias(settings.AUTH_SESSION_SITE_CODE)
                stack.enter_context(transaction.atomic(using=registry))
                with connections[registry].cursor() as cursor:
                    acquire_record_lock(cursor, "shared-catalog:KhoaHoc")
            stack.enter_context(transaction.atomic(using=alias))
            with connections[alias].cursor() as cursor:
                acquire_record_lock(cursor, "shared-catalog:MonHoc")
                receipt = _read_receipt(cursor, event_id, publisher)
                replay = receipt is not None
                if replay:
                    if receipt["request_hash"] != request_hash:
                        raise SharedCatalogConflict("Idempotency-Key đã dùng với người dùng/route/nội dung khác.")
                    before, after = receipt["before"], receipt["after"]
                    if _read_subject(publisher, record_id=(after or before)["ma_mon"],
                                     slug=(after or before)["slug"], locked=True) != after:
                        raise SharedCatalogConflict("Publisher đã thay đổi sau yêu cầu này; cần đối soát, không phát lại.")
                else:
                    if missing:
                        raise SharedCatalogUnavailable("Chưa ghi: cần đối soát đủ các site hoạt động.",
                                                       missing_sites=missing)
                    before = _read_subject(publisher, record_id=payload.get("ma_mon"), slug=slug, locked=True)
                    if action == "tao":
                        if before is not None:
                            raise SharedCatalogConflict("Mã môn hoặc slug đã tồn tại.")
                        after = {**payload, "phien_ban": 1}
                    else:
                        if before is None:
                            raise SharedCatalogNotFound("Không tìm thấy môn học tại Publisher.")
                        after = None if action == "xoa" else {
                            **before, **payload, "phien_ban": before["phien_ban"] + 1,
                            "slug": make_slug(payload.get("ten_mon", before["ten_mon"]), max_length=120),
                        }
                    _preflight(sites, action=action, before=before, after=after)
                    _apply_change(cursor, action=action, before=before, after=after, publisher=publisher,
                                  event_id=event_id, request_hash=request_hash, actor_id=actor_id)
                    identity = after or before
                    if _read_subject(publisher, record_id=identity["ma_mon"], slug=identity["slug"]) != after:
                        raise SharedCatalogConflict("Không xác nhận được kết quả ghi tại Publisher.")
        # Subscribers cannot see the new version until the Publisher transaction commits.
        result = _verify(sites, before=before, after=after, unavailable=missing)
        return {**result, "idempotent_replay": replay}
    except IntegrityError as exc:
        raise SharedCatalogConflict("Mã/slug bị trùng hoặc môn học còn dữ liệu tham chiếu.") from exc
    except _UNAVAILABLE as exc:
        raise SharedCatalogUnavailable("Chưa xác nhận kết quả; thử lại cùng Idempotency-Key và nội dung.") from exc
