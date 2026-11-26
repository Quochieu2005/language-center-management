"""Cloudinary uploads for Blog covers and in-article pictures (signed intent, then server-side verification)."""

from __future__ import annotations

import time
from urllib.parse import quote

from django.core import signing
from django.utils import timezone

from core.media.avatars import (
    _ALLOWED_FORMATS, _INTENT_TTL_SECONDS, _MAX_FILE_BYTES, AvatarInvalidIntent, AvatarUnavailable,
    _cloudinary_config, _cloudinary_resource, _upload_signature,
)
from core.media.folders import build_blog_image_public_id, is_blog_public_id
from core.slug_utils import make_slug

_SALT = "core.blog.image.v1"
_KINDS = {"cover", "content"}


def create_blog_image_intent(actor, slug: str, kind: str) -> dict:
    if kind not in _KINDS:
        raise AvatarInvalidIntent("Loại ảnh Blog không hợp lệ.")
    cloud_name, api_key, api_secret = _cloudinary_config()
    now = timezone.localtime()
    try:
        asset_folder, public_id = build_blog_image_public_id(
            kind, slug=make_slug(slug, max_length=40), on_date=now.date(), stamp=f"{now:%H%M%S}",
        )
    except ValueError as exc:
        raise AvatarUnavailable("Cấu hình thư mục Cloudinary không hợp lệ.") from exc
    fields = {
        "allowed_formats": _ALLOWED_FORMATS, "asset_folder": asset_folder, "invalidate": "true",
        "overwrite": "true", "public_id": public_id, "timestamp": str(int(time.time())),
    }
    token = signing.dumps(
        {"actor_id": str(actor.account_id), "public_id": public_id, "asset_folder": asset_folder},
        salt=_SALT, compress=True,
    )
    return {
        "intent_token": token,
        "upload_url": f"https://api.cloudinary.com/v1_1/{quote(cloud_name, safe='')}/image/upload",
        "cloud_name": cloud_name, "api_key": api_key,
        "fields": {**fields, "signature": _upload_signature(fields, api_secret)},
        "max_file_bytes": _MAX_FILE_BYTES,
    }


def complete_blog_image(actor, intent_token: str, public_id: str) -> dict:
    if not is_blog_public_id(public_id):
        raise AvatarInvalidIntent("Mã ảnh Blog không hợp lệ.")
    try:
        data = signing.loads(intent_token, salt=_SALT, max_age=_INTENT_TTL_SECONDS)
    except signing.BadSignature as exc:
        raise AvatarInvalidIntent("Yêu cầu tải ảnh không hợp lệ hoặc đã hết hạn.") from exc
    if (
        not isinstance(data, dict) or data.get("actor_id") != str(actor.account_id)
        or data.get("public_id") != public_id or not isinstance(data.get("asset_folder"), str)
    ):
        raise AvatarInvalidIntent("Yêu cầu tải ảnh không thuộc phiên đăng nhập hiện tại.")
    resource = _cloudinary_resource(public_id, data["asset_folder"])
    return {"public_id": resource["avatar_public_id"], "secure_url": resource["avatar_secure_url"]}
