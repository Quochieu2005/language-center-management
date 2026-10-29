"""Shared HTTP helpers for academic workflow views."""

import re

from rest_framework import status
from rest_framework.response import Response

from core.academics.common import (
    AcademicConflict,
    AcademicForbidden,
    AcademicInfrastructureUnavailable,
    AcademicInvalid,
    AcademicNotFound,
    AcademicSiteUnavailable,
)


_RECORD_ID = re.compile(r"^[A-Za-z0-9_-]{1,24}$")


def remote_ip(request) -> str:
    return str(request.META.get("REMOTE_ADDR", ""))[:45]


def validate_record_id(value: str):
    if not _RECORD_ID.fullmatch(value or ""):
        return Response({"detail": "Mã bản ghi không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)
    return None


def academic_error(exc):
    if isinstance(exc, AcademicForbidden):
        return Response({"detail": "Bạn không có quyền hoặc đã vượt phạm vi cơ sở."}, status=403)
    if isinstance(exc, AcademicNotFound):
        return Response({"detail": "Không tìm thấy dữ liệu trong cơ sở được phép truy cập."}, status=404)
    if isinstance(exc, AcademicInvalid):
        return Response({"detail": str(exc)}, status=400)
    if isinstance(exc, AcademicSiteUnavailable):
        return Response({"detail": "Cơ sở không hoạt động hoặc chưa có kết nối."}, status=409)
    if isinstance(exc, AcademicConflict):
        return Response({"detail": str(exc)}, status=409)
    if isinstance(exc, AcademicInfrastructureUnavailable):
        return Response(
            {"detail": "CSDL site chưa sẵn sàng; thao tác chưa được xác nhận hoàn tất."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({"detail": "Không thể xử lý yêu cầu hiện tại."}, status=500)


def user_site(user) -> str | None:
    value = str(getattr(user, "site_code", "") or "").strip().upper()
    return value or None


def user_profile(user) -> str | None:
    value = str(getattr(user, "profile_id", "") or "").strip()
    return value or None
