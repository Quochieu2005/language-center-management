"""Public contact form and authenticated site-aware inbox endpoints."""

import hashlib
import re

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle
from rest_framework.views import APIView

from core.academics.common import (
    AcademicConflict,
    AcademicForbidden,
    AcademicInfrastructureUnavailable,
    AcademicInvalid,
    AcademicNotFound,
    AcademicSiteUnavailable,
    site_scope,
)
from core.auth.authentication import AuthCookieAuthentication
from core.contacts.serializers import (
    AdminContactListSerializer,
    AdminContactQuerySerializer,
    ContactReplyResponseSerializer,
    ContactReplySerializer,
    ContactSiteListSerializer,
    ContactSubmissionResponseSerializer,
    ContactSubmissionSerializer,
)
from core.contacts.services import (
    CONTACT_ROLES,
    ContactEmailUnavailable,
    create_contact_request,
    list_admin_contact_requests,
    list_contact_sites,
    send_contact_reply,
)


_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


# shortcut: default LocMemCache limits per worker; configure a shared cache before running multiple API workers.
class PublicContactEmailThrottle(SimpleRateThrottle):
    scope = "public_contact_email"

    def get_cache_key(self, request, view):
        email = str(request.data.get("email", "")).strip().casefold()
        if not email:
            return None
        identity = hashlib.sha256(f"{self.get_ident(request)}:{email}".encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": identity}


def _contact_error(exc):
    if isinstance(exc, ContactEmailUnavailable):
        return Response(
            {
                "code": "smtp_unavailable",
                "detail": "SMTP không chấp nhận email phản hồi; yêu cầu vẫn chờ xử lý. Kiểm tra cấu hình và log API.",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if isinstance(exc, AcademicNotFound):
        return Response({"detail": "Không tìm thấy yêu cầu liên hệ trong cơ sở đã chọn."}, status=404)
    if isinstance(exc, AcademicForbidden):
        return Response({"detail": "Tài khoản không có quyền xem hoặc phản hồi yêu cầu này."}, status=403)
    if isinstance(exc, AcademicInvalid):
        return Response({"detail": str(exc)}, status=400)
    if isinstance(exc, AcademicConflict):
        return Response({"detail": str(exc)}, status=409)
    if isinstance(exc, AcademicSiteUnavailable):
        return Response({"detail": "Cơ sở đã chọn không hoạt động hoặc chưa sẵn sàng."}, status=409)
    return Response(
        {"detail": "CSDL cơ sở hoặc dịch vụ email chưa sẵn sàng; chưa xác nhận hoàn tất thao tác."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _valid_idempotency_key(request):
    key = str(request.headers.get("Idempotency-Key", "")).strip()
    if not _IDEMPOTENCY_KEY.fullmatch(key):
        return None
    return key


class PublicContactSiteListView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="public_contact_sites",
        tags=["Liên hệ"],
        summary="Liệt kê cơ sở đang nhận yêu cầu liên hệ",
        responses={200: ContactSiteListSerializer, 503: OpenApiResponse(description="Danh mục site chưa sẵn sàng.")},
    )
    def get(self, request):
        try:
            result = list_contact_sites()
        except AcademicInfrastructureUnavailable as exc:
            return _contact_error(exc)
        return Response(result)


class PublicContactCreateView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle, PublicContactEmailThrottle]
    throttle_scope = "public_contact_write"

    @extend_schema(
        operation_id="public_contact_create",
        tags=["Liên hệ"],
        summary="Gửi yêu cầu từ biểu mẫu liên hệ công khai",
        description=(
            "Khách chọn một cơ sở hoạt động. API xác nhận danh sách site, sau đó chỉ ghi "
            "YeuCauLienHe và Logs tại CSDL của cơ sở được chọn trong một transaction LOCAL. "
            "Idempotency-Key chống tạo yêu cầu trùng khi retry; không gửi thư tự động khi khách gửi form."
        ),
        parameters=[OpenApiParameter(
            "Idempotency-Key", str, OpenApiParameter.HEADER, required=True,
            description="8–128 ký tự; giữ nguyên key và body khi retry.",
        )],
        request=ContactSubmissionSerializer,
        responses={
            201: ContactSubmissionResponseSerializer,
            200: ContactSubmissionResponseSerializer,
            400: OpenApiResponse(description="Dữ liệu form hoặc Idempotency-Key không hợp lệ."),
            409: OpenApiResponse(description="Site không sẵn sàng hoặc key trùng nội dung khác."),
            429: OpenApiResponse(description="Vượt giới hạn gửi theo IP/email; kèm Retry-After."),
            503: OpenApiResponse(description="Danh mục site hoặc CSDL của site chưa sẵn sàng."),
        },
    )
    def post(self, request):
        serializer = ContactSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = _valid_idempotency_key(request)
        if not idempotency_key:
            return Response(
                {"detail": "Idempotency-Key phải có 8–128 ký tự chữ, số hoặc . _ : -."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = create_contact_request(
                contact=serializer.validated_data,
                idempotency_key=idempotency_key,
                remote_ip=request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except (AcademicConflict, AcademicInfrastructureUnavailable, AcademicInvalid,
                AcademicNotFound, AcademicSiteUnavailable) as exc:
            return _contact_error(exc)
        return Response(result, status=status.HTTP_200_OK if result["replayed"] else status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name="dispatch")
class AdminContactListView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "contact_read"

    @extend_schema(
        operation_id="admin_contact_list",
        tags=["Liên hệ"],
        summary="Xem hộp thư liên hệ theo phạm vi quản trị",
        description=(
            "Admin Big đọc GLOBAL từ từng CSDL site hoạt động hoặc lọc một site; Admin Small và Tư vấn & "
            "xếp lớp chỉ đọc site được gán. API tổng hợp Global Query trong bộ nhớ, không có CSDL trung tâm. Nếu thiếu "
            "site, response 503 kèm complete=false và missing_sites; kết quả một phần không được coi là đầy đủ."
        ),
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
            OpenApiParameter("status", str, OpenApiParameter.QUERY),
            OpenApiParameter("search", str, OpenApiParameter.QUERY),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY),
            OpenApiParameter("offset", int, OpenApiParameter.QUERY),
        ],
        responses={
            200: AdminContactListSerializer,
            400: OpenApiResponse(description="Bộ lọc không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Vai trò không được phép hoặc site vượt phạm vi được gán."),
            503: AdminContactListSerializer,
        },
    )
    def get(self, request):
        if request.user.role not in CONTACT_ROLES:
            return Response({"detail": "Tài khoản không được phép xem hộp thư liên hệ."}, status=403)
        query = AdminContactQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        options = query.validated_data
        try:
            result = list_admin_contact_requests(
                user=request.user,
                site_code=options.get("site_code"),
                status_filter=options.get("status"),
                search=options.get("search"),
                limit=options["limit"],
                offset=options["offset"],
            )
        except (AcademicConflict, AcademicForbidden, AcademicInfrastructureUnavailable,
                AcademicInvalid, AcademicNotFound, AcademicSiteUnavailable) as exc:
            return _contact_error(exc)
        response_status = status.HTTP_200_OK if result["complete"] else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(result, status=response_status)


@method_decorator(csrf_protect, name="dispatch")
class AdminContactReplyView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "contact_reply"

    @extend_schema(
        operation_id="admin_contact_reply",
        tags=["Liên hệ"],
        summary="Gửi email phản hồi cho yêu cầu liên hệ",
        description=(
            "Admin Big, Admin Small và Tư vấn & xếp lớp chỉ phản hồi tại site sở hữu yêu cầu trong phạm vi được gán. API lấy địa chỉ nhận từ bản ghi, "
            "gửi plain-text email qua SMTP đã cấu hình rồi lưu nội dung phản hồi, trạng thái và Logs trong "
            "transaction cục bộ. Yêu cầu chỉ được phản hồi một lần; xác nhận gửi SMTP không chứng minh email đã đến inbox."
        ),
        parameters=[OpenApiParameter("site_code", str, OpenApiParameter.PATH),
                    OpenApiParameter("request_id", str, OpenApiParameter.PATH)],
        request=ContactReplySerializer,
        responses={
            200: ContactReplyResponseSerializer,
            400: OpenApiResponse(description="Nội dung phản hồi không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Không có quyền tại site sở hữu yêu cầu."),
            404: OpenApiResponse(description="Không tìm thấy yêu cầu."),
            409: OpenApiResponse(description="Yêu cầu đã được phản hồi."),
            503: OpenApiResponse(description="SMTP hoặc CSDL site chưa sẵn sàng."),
        },
    )
    def post(self, request, site_code, request_id):
        if request.user.role not in CONTACT_ROLES:
            return Response({"detail": "Tài khoản không được phép phản hồi liên hệ."}, status=403)
        query = AdminContactQuerySerializer(data={"site_code": site_code})
        query.is_valid(raise_exception=True)
        serializer = ContactReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            site = site_scope(
                request.user, query.validated_data["site_code"], roles=CONTACT_ROLES
            )
            result = send_contact_reply(
                site_code=site,
                request_id=request_id,
                reply_body=serializer.validated_data["reply_body"],
                actor_id=str(request.user.account_id),
                remote_ip=request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except (AcademicConflict, AcademicForbidden, AcademicInfrastructureUnavailable,
                AcademicInvalid, AcademicNotFound, AcademicSiteUnavailable) as exc:
            return _contact_error(exc)
        return Response(result)
