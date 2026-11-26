"""Site-local Cloudinary avatar uploads for student profiles."""

from __future__ import annotations

import uuid
from urllib.parse import quote

from django.core import signing
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, transaction
from django.utils import timezone

from core.auth.service_common import AuthInfrastructureUnavailable, active_site_codes
from core.media.avatars import (
    AvatarConflict,
    AvatarInvalidIntent,
    AvatarInvalidUpload,
    AvatarUnavailable,
    _ALLOWED_FORMATS,
    _MAX_FILE_BYTES,
    _cloudinary_config,
    _cloudinary_resource,
    _upload_signature,
)
from core.media.folders import build_avatar_public_id
from core.slug_utils import make_slug
from core.sites.connections import UnknownSiteError, get_site_database_alias
from core.students.services import (
    StudentConflict,
    StudentNotFound,
    StudentSiteUnavailable,
    _append_audit,
)


_SETUP_SALT = "core.media.student-avatar.v1"
_INTENT_TTL_SECONDS = 3600


def _site_and_actor(actor, site_code: str) -> tuple[str, str, str, str | None]:
    role = str(getattr(actor, "role", ""))
    actor_id = str(getattr(actor, "account_id", ""))
    actor_site = str(getattr(actor, "site_code", "") or "").strip().upper() or None
    site = str(site_code or "").strip().upper()
    if role not in {"admin_big", "admin_small"} or not actor_id:
        raise AvatarConflict("Chỉ Admin Big hoặc Admin Small được quản lý ảnh học viên.")
    if role == "admin_small" and (not actor_site or actor_site != site):
        raise AvatarConflict("Admin Small chỉ được tải ảnh tại cơ sở của mình.")
    try:
        sites = active_site_codes()
    except (AuthInfrastructureUnavailable, DatabaseError, ImproperlyConfigured,
            KeyError, UnknownSiteError) as exc:
        raise AvatarUnavailable("Không xác định được danh sách cơ sở đang hoạt động.") from exc
    if site not in sites:
        raise StudentSiteUnavailable
    return site, actor_id, role, actor_site


def _profile(cursor, site_code: str, slug: str, *, lock: bool = False) -> dict:
    hint = " WITH (UPDLOCK, HOLDLOCK)" if lock else ""
    cursor.execute(
        "SELECT TOP (2) ma_hoc_vien, slug, ma_co_so, trang_thai, "
        "avatar_public_id, avatar_secure_url FROM dbo.HocVien" + hint +
        " WHERE slug = %s AND ma_co_so = %s",
        [slug, site_code],
    )
    rows = cursor.fetchall()
    if len(rows) > 1:
        raise AvatarConflict("Slug không định danh duy nhất một hồ sơ tại cơ sở.")
    if not rows:
        raise StudentNotFound
    row = rows[0]
    return {
        "student_id": str(row[0]),
        "slug": str(row[1]),
        "site_code": str(row[2]).upper(),
        "status": str(row[3]).lower(),
        "avatar_public_id": str(row[4]) if row[4] is not None else None,
        "avatar_secure_url": str(row[5]) if row[5] is not None else None,
    }


def _avatar_state(profile: dict) -> dict[str, str | None]:
    state = {
        "avatar_public_id": profile["avatar_public_id"],
        "avatar_secure_url": profile["avatar_secure_url"],
    }
    if bool(state["avatar_public_id"]) != bool(state["avatar_secure_url"]):
        raise AvatarConflict("Metadata ảnh học viên chưa đầy đủ; cần đối soát trước.")
    return state


def create_student_avatar_upload_intent(actor, site_code: str, slug: str) -> dict:
    try:
        site, actor_id, actor_role, actor_site = _site_and_actor(actor, site_code)
        alias = get_site_database_alias(site)
        with connections[alias].cursor() as cursor:
            profile = _profile(cursor, site, slug)
        if profile["status"] == "da_chuyen_di":
            raise StudentConflict
        old_avatar = _avatar_state(profile)
        cloud_name, api_key, api_secret = _cloudinary_config()
        try:
            folder, image_id = build_avatar_public_id(
                "student", slug=make_slug(slug, max_length=52), on_date=timezone.localdate(), site_code=site,
            )
        except ValueError as exc:
            raise AvatarUnavailable("Cấu hình thư mục Cloudinary không hợp lệ.") from exc
        fields = {
            "allowed_formats": _ALLOWED_FORMATS,
            "asset_folder": folder,
            # Same student, same day => same name; the new upload replaces that day's photo.
            "invalidate": "true",
            "overwrite": "true",
            "public_id": image_id,
            "timestamp": str(int(timezone.now().timestamp())),
        }
        token = signing.dumps(
            {
                "actor_id": actor_id,
                "actor_role": actor_role,
                "actor_site": actor_site,
                "student_id": profile["student_id"],
                "student_slug": slug,
                "site_code": site,
                "public_id": image_id,
                "asset_folder": folder,
                "old_avatar": old_avatar,
            },
            salt=_SETUP_SALT,
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
    except (AvatarConflict, AvatarUnavailable, StudentConflict, StudentNotFound,
            StudentSiteUnavailable):
        raise
    except (AuthInfrastructureUnavailable, DatabaseError, ImproperlyConfigured,
            KeyError, UnknownSiteError) as exc:
        raise AvatarUnavailable("Site hoặc SQL Server chưa sẵn sàng.") from exc


def complete_student_avatar_upload(
    actor, site_code: str, slug: str, token: str, public_id: str, remote_ip: str,
) -> dict:
    try:
        site, actor_id, actor_role, actor_site = _site_and_actor(actor, site_code)
        try:
            intent = signing.loads(token, salt=_SETUP_SALT, max_age=_INTENT_TTL_SECONDS)
        except signing.BadSignature as exc:
            raise AvatarInvalidIntent("Yêu cầu tải ảnh không hợp lệ hoặc đã hết hạn.") from exc
        if (
            not isinstance(intent, dict)
            or intent.get("actor_id") != actor_id
            or intent.get("actor_role") != actor_role
            or intent.get("actor_site") != actor_site
            or intent.get("student_slug") != slug
            or intent.get("site_code") != site
            or intent.get("public_id") != public_id
            or not isinstance(intent.get("student_id"), str)
            or not isinstance(intent.get("asset_folder"), str)
            or not isinstance(intent.get("old_avatar"), dict)
            or set(intent["old_avatar"]) != {"avatar_public_id", "avatar_secure_url"}
        ):
            raise AvatarInvalidIntent("Yêu cầu tải ảnh không thuộc hồ sơ hoặc phiên hiện tại.")
        new_avatar = _cloudinary_resource(public_id, intent["asset_folder"])
        alias = get_site_database_alias(site)
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                profile = _profile(cursor, site, slug, lock=True)
                if profile["student_id"] != intent["student_id"] or profile["status"] == "da_chuyen_di":
                    raise StudentConflict
                cursor.execute(
                    "SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.GiaoDichChuyenCoSo "
                    "WHERE ma_hoc_vien = %s AND co_so_nguon = %s AND trang_thai = 'dang_xu_ly') "
                    "THEN 1 ELSE 0 END",
                    [profile["student_id"], site],
                )
                if cursor.fetchone()[0]:
                    raise StudentConflict
                current = _avatar_state(profile)
                if current != new_avatar:
                    if current != intent["old_avatar"]:
                        raise AvatarConflict("Ảnh hồ sơ đã được thay đổi; cần tạo yêu cầu tải mới.")
                    cursor.execute(
                        "UPDATE dbo.HocVien SET avatar_public_id = %s, avatar_secure_url = %s "
                        "WHERE ma_hoc_vien = %s AND ma_co_so = %s AND slug = %s "
                        "AND ((avatar_public_id = %s) OR (avatar_public_id IS NULL AND %s IS NULL)) "
                        "AND ((avatar_secure_url = %s) OR (avatar_secure_url IS NULL AND %s IS NULL))",
                        [new_avatar["avatar_public_id"], new_avatar["avatar_secure_url"],
                         profile["student_id"], site, slug,
                         current["avatar_public_id"], current["avatar_public_id"],
                         current["avatar_secure_url"], current["avatar_secure_url"]],
                    )
                    if cursor.rowcount != 1:
                        raise AvatarConflict("Không cập nhật được metadata ảnh học viên.")
                    _append_audit(
                        cursor, site, actor_id, "cap_nhat_anh_hoc_vien", "HocVien",
                        profile["student_id"], remote_ip, uuid.uuid4().hex,
                        {"avatar_public_id": new_avatar["avatar_public_id"]},
                    )
        return {
            "student_id": intent["student_id"],
            "slug": slug,
            "site_code": site,
            "avatar_secure_url": new_avatar["avatar_secure_url"],
            "complete": True,
        }
    except (AvatarConflict, AvatarInvalidIntent, AvatarInvalidUpload, AvatarUnavailable,
            StudentConflict, StudentNotFound, StudentSiteUnavailable):
        raise
    except (AuthInfrastructureUnavailable, DatabaseError, ImproperlyConfigured,
            KeyError, UnknownSiteError) as exc:
        raise AvatarUnavailable("Site, SQL Server hoặc Cloudinary chưa sẵn sàng.") from exc
