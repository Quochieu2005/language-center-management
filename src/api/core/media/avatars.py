"""Cloudinary avatar upload and replicated TaiKhoan metadata services."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
import uuid
from contextlib import contextmanager
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.core import signing
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction

from core.academics.common import AcademicInfrastructureUnavailable, active_site_state
from core.media.folders import build_asset_folder
from core.sites.connections import UnknownSiteError, get_site_database_alias


class AvatarUnavailable(Exception):
    """Cloudinary or one of the required site databases is unavailable."""

    def __init__(self, message: str = "", *, missing_sites: tuple[str, ...] = ()):
        self.missing_sites = tuple(missing_sites)
        super().__init__(message)


class AvatarConflict(Exception):
    """Replicated avatar state differs or an operation acknowledgement conflicts."""


class AvatarInvalidIntent(Exception):
    """The signed upload intent is invalid, expired, or belongs to another user."""


class AvatarInvalidUpload(Exception):
    """The uploaded Cloudinary resource does not match the issued intent."""


_INTENT_SALT = "core.media.admin-avatar.v1"
_INTENT_TTL_SECONDS = 3600
_MAX_FILE_BYTES = 5 * 1024 * 1024
_ALLOWED_FORMATS = "jpg,jpeg,png,webp"
_ACCOUNT_ROLE = {"admin_big": "admin_big", "admin_small": "nhan_vien"}
_PUBLIC_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")


def _cloudinary_config() -> tuple[str, str, str]:
    cloud_name = str(getattr(settings, "CLOUDINARY_CLOUD_NAME", "")).strip()
    api_key = str(getattr(settings, "CLOUDINARY_API_KEY", "")).strip()
    api_secret = str(getattr(settings, "CLOUDINARY_API_SECRET", "")).strip()
    if not cloud_name or not api_key or not api_secret:
        raise AvatarUnavailable("Thiếu cấu hình Cloudinary phía máy chủ.")
    return cloud_name, api_key, api_secret


def _active_sites() -> tuple[str, ...]:
    try:
        sites, missing = active_site_state()
    except (AcademicInfrastructureUnavailable, DatabaseError, ImproperlyConfigured,
            KeyError, UnknownSiteError) as exc:
        raise AvatarUnavailable from exc
    if missing or not sites:
        raise AvatarUnavailable(
            "Một hoặc nhiều cơ sở đang hoạt động chưa kết nối được.",
            missing_sites=missing,
        )
    return tuple(sorted(sites))


def _read_account(site_code: str, account_id: str, role: str, account_site: str | None) -> dict:
    alias = get_site_database_alias(site_code)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "SELECT TOP (2) vai_tro, ma_co_so, trang_thai, avatar_public_id, avatar_secure_url "
            "FROM dbo.TaiKhoan WHERE ma_tai_khoan = %s",
            [account_id],
        )
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise AvatarConflict("Không xác nhận được tài khoản trên tất cả cơ sở.")
    row = rows[0]
    expected_role = _ACCOUNT_ROLE.get(role)
    if str(row[0]).lower() != expected_role or not bool(row[2]):
        raise AvatarConflict("Tài khoản không còn quyền cập nhật ảnh đại diện.")
    site_value = str(row[1]).upper() if row[1] is not None else None
    if (role == "admin_big" and site_value is not None) or (
        role == "admin_small" and site_value != account_site
    ):
        raise AvatarConflict("Phạm vi tài khoản không khớp với cơ sở.")
    public_id = str(row[3]) if row[3] is not None else None
    secure_url = str(row[4]) if row[4] is not None else None
    if (public_id is None) != (secure_url is None):
        raise AvatarConflict("Metadata ảnh đại diện chưa đồng nhất trong một cơ sở.")
    return {"avatar_public_id": public_id, "avatar_secure_url": secure_url}


def _replicated_avatar(
    account_id: str, role: str, account_site: str | None, sites: tuple[str, ...]
) -> dict:
    states = [_read_account(site, account_id, role, account_site) for site in sites]
    if not states or any(state != states[0] for state in states[1:]):
        raise AvatarConflict("Ảnh đại diện giữa các cơ sở chưa đồng bộ; cần đối soát trước.")
    return states[0]


def get_admin_avatar_url(account_id: str, role: str, account_site: str | None = None) -> str | None:
    if role not in _ACCOUNT_ROLE:
        raise AvatarConflict("Vai trò không được phép xem ảnh đại diện này.")
    try:
        site = str(account_site).upper() if account_site else None
        state = _replicated_avatar(account_id, role, site, _active_sites())
        return state["avatar_secure_url"]
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AvatarUnavailable from exc


@contextmanager
def _account_lock(account_id: str):
    """Serialize avatar intents and fan-out writes using the configured auth site."""
    coordinator = str(getattr(settings, "AUTH_SESSION_SITE_CODE", "")).strip().upper()
    try:
        alias = get_site_database_alias(coordinator)
        connection = connections[alias]
        cursor = connection.cursor()
        lock_name = "qlttnn:avatar:" + hashlib.sha256(account_id.encode("utf-8")).hexdigest()
        cursor.execute(
            "DECLARE @result INT; "
            "EXEC @result = sys.sp_getapplock @Resource = %s, @LockMode = 'Exclusive', "
            "@LockOwner = 'Session', @LockTimeout = 10000; SELECT @result;",
            [lock_name],
        )
        result = cursor.fetchone()
        if result is None or int(result[0]) < 0:
            cursor.close()
            raise AvatarUnavailable("Không lấy được khóa điều phối ảnh đại diện.")
    except AvatarUnavailable:
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AvatarUnavailable from exc
    try:
        yield
    finally:
        try:
            cursor.execute(
                "DECLARE @result INT; "
                "EXEC @result = sys.sp_releaseapplock @Resource = %s, "
                "@LockOwner = 'Session'; SELECT @result;",
                [lock_name],
            )
            cursor.fetchone()
        except DatabaseError:
            connection.close()
        finally:
            cursor.close()


def _upload_signature(params: dict[str, str], api_secret: str) -> str:
    canonical = "&".join(f"{key}={params[key]}" for key in sorted(params))
    return hashlib.sha1(f"{canonical}{api_secret}".encode("utf-8")).hexdigest()


def _create_admin_avatar_upload_intent(user) -> dict:
    role = str(getattr(user, "role", ""))
    account_id = str(getattr(user, "account_id", ""))
    if role not in _ACCOUNT_ROLE or not account_id:
        raise AvatarConflict("Chỉ Admin Big và Admin Small được tải ảnh đại diện.")
    account_site = str(getattr(user, "site_code", "") or "").strip().upper() or None
    if (role == "admin_small" and not account_site) or (role == "admin_big" and account_site):
        raise AvatarConflict("Phạm vi tài khoản không hợp lệ.")
    cloud_name, api_key, api_secret = _cloudinary_config()
    with _account_lock(account_id):
        sites = _active_sites()
        old_avatar = _replicated_avatar(account_id, role, account_site, sites)
        image_id = str(uuid.uuid4())
        try:
            asset_folder = build_asset_folder(
                "account", asset_id=image_id, record_code=account_id
            )
        except ValueError as exc:
            raise AvatarUnavailable("Cấu hình thư mục Cloudinary không hợp lệ.") from exc
        timestamp = str(int(time.time()))
        fields = {
            "allowed_formats": _ALLOWED_FORMATS,
            "asset_folder": asset_folder,
            "overwrite": "false",
            "public_id": image_id,
            "timestamp": timestamp,
        }
        token = signing.dumps(
            {
                "account_id": account_id,
                "role": role,
                "account_site": account_site,
                "public_id": image_id,
                "asset_folder": asset_folder,
                "old_avatar": old_avatar,
            },
            salt=_INTENT_SALT,
            compress=True,
        )
    return {
        "intent_token": token,
        "upload_url": f"https://api.cloudinary.com/v1_1/{quote(cloud_name, safe='')}/image/upload",
        "cloud_name": cloud_name,
        "api_key": api_key,
        "fields": {**fields, "signature": _upload_signature(fields, api_secret)},
        "max_file_bytes": _MAX_FILE_BYTES,
    }


def create_admin_avatar_upload_intent(user) -> dict:
    try:
        return _create_admin_avatar_upload_intent(user)
    except (AvatarConflict, AvatarUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AvatarUnavailable from exc


def _load_intent(token: str, user, public_id: str) -> dict:
    if not _PUBLIC_ID.fullmatch(public_id):
        raise AvatarInvalidIntent("Mã ảnh tải lên không hợp lệ.")
    try:
        data = signing.loads(token, salt=_INTENT_SALT, max_age=_INTENT_TTL_SECONDS)
    except signing.BadSignature as exc:
        raise AvatarInvalidIntent("Yêu cầu tải ảnh không hợp lệ hoặc đã hết hạn.") from exc
    if (
        not isinstance(data, dict)
        or data.get("account_id") != str(getattr(user, "account_id", ""))
        or data.get("role") != str(getattr(user, "role", ""))
        or data.get("account_site") != (str(getattr(user, "site_code", "") or "").strip().upper() or None)
        or data.get("public_id") != public_id
        or not isinstance(data.get("asset_folder"), str)
        or not isinstance(data.get("old_avatar"), dict)
        or set(data["old_avatar"]) != {"avatar_public_id", "avatar_secure_url"}
    ):
        raise AvatarInvalidIntent("Yêu cầu tải ảnh không thuộc phiên đăng nhập hiện tại.")
    return data


def _cloudinary_resource(public_id: str, asset_folder: str) -> dict:
    cloud_name, api_key, api_secret = _cloudinary_config()
    url = (
        f"https://api.cloudinary.com/v1_1/{quote(cloud_name, safe='')}"
        f"/resources/image/upload/{quote(public_id, safe='')}"
    )
    credentials = base64.b64encode(f"{api_key}:{api_secret}".encode("utf-8")).decode("ascii")
    request = Request(url, headers={"Authorization": f"Basic {credentials}"})
    try:
        with urlopen(request, timeout=12) as response:
            resource = json.loads(response.read(64 * 1024 + 1))
    except HTTPError as exc:
        if exc.code == 404:
            raise AvatarInvalidUpload("Không tìm thấy ảnh vừa tải lên Cloudinary.") from exc
        raise AvatarUnavailable("Không xác minh được ảnh trên Cloudinary.") from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise AvatarUnavailable("Cloudinary hiện không phản hồi.") from exc
    if not isinstance(resource, dict) or resource.get("public_id") != public_id:
        raise AvatarInvalidUpload("Tài nguyên ảnh không khớp yêu cầu tải lên.")
    secure_url = resource.get("secure_url")
    parsed = urlparse(secure_url if isinstance(secure_url, str) else "")
    expected_prefix = f"/{cloud_name}/image/upload/"
    image_format = str(resource.get("format", "")).lower()
    byte_count = resource.get("bytes")
    width = resource.get("width")
    height = resource.get("height")
    if (
        resource.get("resource_type") != "image"
        or resource.get("asset_folder") != asset_folder
        or image_format not in {"jpg", "jpeg", "png", "webp"}
        or not isinstance(byte_count, int) or isinstance(byte_count, bool)
        or byte_count < 1 or byte_count > _MAX_FILE_BYTES
        or not isinstance(width, int) or isinstance(width, bool)
        or not isinstance(height, int) or isinstance(height, bool)
        or width < 1 or height < 1 or width > 8000 or height > 8000
        or width * height > 40_000_000
        or parsed.scheme != "https" or parsed.hostname != "res.cloudinary.com"
        or not parsed.path.startswith(expected_prefix)
    ):
        raise AvatarInvalidUpload("Ảnh phải là JPG, PNG hoặc WebP hợp lệ, tối đa 5 MB.")
    return {"avatar_public_id": public_id, "avatar_secure_url": secure_url}


def _event_id(token: str, site_code: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"AVREP-{site_code}-{digest[:64]}"


def _apply_site(site_code: str, account_id: str, role: str, account_site: str | None,
                old: dict, new: dict,
                token: str, actor_id: str, remote_ip: str) -> None:
    alias = get_site_database_alias(site_code)
    event_id = _event_id(token, site_code)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                "SELECT bang_tac_dong, ma_ban_ghi, hanh_dong, site_dich, ket_qua, "
                "du_lieu_cu, du_lieu_moi FROM dbo.Logs "
                "WHERE loai_log = 'sync' AND ma_log = %s",
                [event_id],
            )
            event = cursor.fetchone()
            cursor.execute(
                "SELECT vai_tro, ma_co_so, trang_thai, avatar_public_id, avatar_secure_url "
                "FROM dbo.TaiKhoan WITH (UPDLOCK, ROWLOCK) WHERE ma_tai_khoan = %s",
                [account_id],
            )
            row = cursor.fetchone()
            if row is None or str(row[0]).lower() != _ACCOUNT_ROLE[role] or not bool(row[2]):
                raise AvatarConflict("Tài khoản không còn hoạt động tại một cơ sở.")
            current = {
                "avatar_public_id": str(row[3]) if row[3] is not None else None,
                "avatar_secure_url": str(row[4]) if row[4] is not None else None,
            }
            if role == "admin_big" and row[1] is not None:
                raise AvatarConflict("Phạm vi Admin Big không hợp lệ tại một cơ sở.")
            if role == "admin_small" and str(row[1]).upper() != account_site:
                raise AvatarConflict("Cơ sở Admin Small không khớp bản sao tài khoản.")

            if event is not None:
                try:
                    event_old = json.loads(event[5])
                    event_new = json.loads(event[6])
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise AvatarConflict("ACK ảnh đại diện không đọc được.") from exc
                if (
                    tuple(str(value) for value in event[:5])
                    != ("TaiKhoan", account_id, "cap_nhat_anh_dai_dien", site_code, "thanh_cong")
                    or event_old != old or event_new != new or current != new
                ):
                    raise AvatarConflict("ACK ảnh đại diện không khớp dữ liệu tại cơ sở.")
                return

            if current != old:
                raise AvatarConflict("Ảnh tại cơ sở đã thay đổi; cần đối soát trước khi tiếp tục.")
            cursor.execute(
                "UPDATE dbo.TaiKhoan SET avatar_public_id = %s, avatar_secure_url = %s, "
                "cap_nhat_luc = SYSUTCDATETIME() "
                "OUTPUT INSERTED.ma_tai_khoan "
                "WHERE ma_tai_khoan = %s AND vai_tro = %s "
                "AND ((avatar_public_id = %s) OR (avatar_public_id IS NULL AND %s IS NULL)) "
                "AND ((avatar_secure_url = %s) OR (avatar_secure_url IS NULL AND %s IS NULL))",
                [new["avatar_public_id"], new["avatar_secure_url"], account_id,
                 _ACCOUNT_ROLE[role], old["avatar_public_id"], old["avatar_public_id"],
                 old["avatar_secure_url"], old["avatar_secure_url"]],
            )
            if cursor.fetchone() is None:
                raise AvatarConflict("Không cập nhật được metadata ảnh tại cơ sở.")
            cursor.execute(
                "INSERT INTO dbo.Logs "
                "(ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, "
                "ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua, site_dich) "
                "VALUES (%s, 'sync', %s, %s, 'cap_nhat_anh_dai_dien', 'TaiKhoan', %s, %s, %s, %s, 'thanh_cong', %s)",
                [event_id, site_code, actor_id, account_id,
                 json.dumps(old, sort_keys=True, separators=(",", ":")),
                 json.dumps(new, sort_keys=True, separators=(",", ":")),
                 str(remote_ip or "")[:45], site_code],
            )


def _complete_admin_avatar_upload(user, token: str, public_id: str, remote_ip: str) -> dict:
    role = str(getattr(user, "role", ""))
    account_id = str(getattr(user, "account_id", ""))
    if role not in _ACCOUNT_ROLE or not account_id:
        raise AvatarConflict("Chỉ Admin Big và Admin Small được đổi ảnh đại diện.")
    account_site = str(getattr(user, "site_code", "") or "").strip().upper() or None
    intent = _load_intent(token, user, public_id)
    new_avatar = _cloudinary_resource(public_id, intent["asset_folder"])
    old_avatar = intent["old_avatar"]
    with _account_lock(account_id):
        sites = _active_sites()
        for site in sites:
            try:
                _apply_site(
                    site, account_id, role, account_site, old_avatar, new_avatar, token,
                    account_id, remote_ip,
                )
            except (AvatarConflict, AvatarUnavailable):
                raise
            except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
                raise AvatarUnavailable(
                    "Đồng bộ chưa hoàn tất; gửi lại cùng yêu cầu để tiếp tục.",
                    missing_sites=(site,),
                ) from exc
        states = [_read_account(site, account_id, role, account_site) for site in sites]
        if any(state != new_avatar for state in states):
            raise AvatarUnavailable("Đồng bộ ảnh đại diện chưa hoàn tất; hãy tiếp tục thử lại.")
    return {
        "account_id": account_id,
        "role": role,
        "avatar_secure_url": new_avatar["avatar_secure_url"],
        "complete": True,
        "site_codes": list(sites),
    }


def complete_admin_avatar_upload(user, token: str, public_id: str, remote_ip: str) -> dict:
    try:
        return _complete_admin_avatar_upload(user, token, public_id, remote_ip)
    except (AvatarConflict, AvatarInvalidIntent, AvatarInvalidUpload, AvatarUnavailable):
        raise
    except (DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError) as exc:
        raise AvatarUnavailable from exc
