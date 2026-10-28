from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.auth.authentication import AuthCookieAuthentication
from core.notifications.serializers import (
    NotificationListResponseSerializer,
    NotificationQuerySerializer,
    NotificationReadAllResponseSerializer,
    NotificationReadResponseSerializer,
    NotificationUnreadCountResponseSerializer,
)
from core.notifications.services import (
    NotificationInfrastructureUnavailable,
    NotificationNotFound,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)


_ADMIN_ROLES = {"admin_big", "admin_small"}


def _role_error(user):
    if getattr(user, "role", None) in _ADMIN_ROLES:
        return None
    return Response(
        {"detail": "Chỉ Admin Big hoặc Admin Small được xem thông báo quản trị."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _service_error(exc):
    if isinstance(exc, NotificationNotFound):
        return Response({"detail": "Không tìm thấy thông báo trong phạm vi được phép."}, status=404)
    if isinstance(exc, PermissionError):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    return Response(
        {"detail": "Danh mục site hoặc CSDL thông báo chưa sẵn sàng; không thể xác nhận dữ liệu đầy đủ."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _query_options(request):
    serializer = NotificationQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _small_site_query_error(user, options):
    if user.role == "admin_small" and options.get("site_code"):
        return Response(
            {"detail": "Admin Small chỉ được xem thông báo tại cơ sở được gán."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


@method_decorator(csrf_protect, name="dispatch")
class AdminNotificationListView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "notification_read"

    @extend_schema(
        operation_id="admin_notification_list",
        tags=["Thông báo quản trị"],
        summary="Liệt kê thông báo theo phạm vi admin",
        description=(
            "Admin Small chỉ đọc CSDL của cơ sở được gán. Admin Big đọc các CSDL site đang hoạt động "
            "qua Global Query; API gộp kết quả tại tầng ứng dụng, không JOIN xuyên site. Nếu thiếu site, "
            "response báo complete=false và missing_sites, không giả định danh sách là đầy đủ."
        ),
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("category", str, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("unread_only", bool, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("offset", int, OpenApiParameter.QUERY, required=False),
        ],
        responses={
            200: NotificationListResponseSerializer,
            400: OpenApiResponse(description="Bộ lọc không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Vai trò không được phép hoặc Admin Small chọn site khác."),
            503: NotificationListResponseSerializer,
        },
    )
    def get(self, request):
        denied = _role_error(request.user)
        if denied:
            return denied
        options = _query_options(request)
        scope_error = _small_site_query_error(request.user, options)
        if scope_error:
            return scope_error
        try:
            result = list_notifications(
                user_id=request.user.account_id,
                role=request.user.role,
                user_site_code=request.user.site_code,
                site_code=options.get("site_code"),
                category=options.get("category"),
                unread_only=options["unread_only"],
                limit=options["limit"],
                offset=options["offset"],
            )
        except (NotificationInfrastructureUnavailable, NotificationNotFound, PermissionError) as exc:
            return _service_error(exc)
        code = status.HTTP_200_OK if result["complete"] else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(result, status=code)


@method_decorator(csrf_protect, name="dispatch")
class AdminNotificationUnreadCountView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "notification_read"

    @extend_schema(
        operation_id="admin_notification_unread_count",
        tags=["Thông báo quản trị"],
        summary="Đếm thông báo chưa đọc",
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("category", str, OpenApiParameter.QUERY, required=False),
        ],
        responses={
            200: NotificationUnreadCountResponseSerializer,
            503: NotificationUnreadCountResponseSerializer,
        },
    )
    def get(self, request):
        denied = _role_error(request.user)
        if denied:
            return denied
        options = _query_options(request)
        scope_error = _small_site_query_error(request.user, options)
        if scope_error:
            return scope_error
        try:
            result = list_notifications(
                user_id=request.user.account_id,
                role=request.user.role,
                user_site_code=request.user.site_code,
                site_code=options.get("site_code"),
                category=options.get("category"),
                limit=1,
                offset=0,
            )
        except (NotificationInfrastructureUnavailable, NotificationNotFound, PermissionError) as exc:
            return _service_error(exc)
        payload = {key: result[key] for key in ("complete", "missing_sites", "site_codes", "unread_count")}
        code = status.HTTP_200_OK if result["complete"] else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(payload, status=code)


@method_decorator(csrf_protect, name="dispatch")
class AdminNotificationReadAllView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "notification_write"

    @extend_schema(
        operation_id="admin_notification_read_all",
        tags=["Thông báo quản trị"],
        summary="Đánh dấu tất cả thông báo đã đọc",
        request=None,
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("category", str, OpenApiParameter.QUERY, required=False),
        ],
        responses={
            200: NotificationReadAllResponseSerializer,
            503: NotificationReadAllResponseSerializer,
        },
    )
    def post(self, request):
        denied = _role_error(request.user)
        if denied:
            return denied
        options = _query_options(request)
        scope_error = _small_site_query_error(request.user, options)
        if scope_error:
            return scope_error
        try:
            result = mark_all_notifications_read(
                user_id=request.user.account_id,
                role=request.user.role,
                user_site_code=request.user.site_code,
                site_code=options.get("site_code"),
                category=options.get("category"),
            )
        except (NotificationInfrastructureUnavailable, NotificationNotFound, PermissionError) as exc:
            return _service_error(exc)
        code = status.HTTP_200_OK if result["complete"] else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(result, status=code)


@method_decorator(csrf_protect, name="dispatch")
class AdminNotificationReadView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "notification_write"

    @extend_schema(
        operation_id="admin_notification_mark_read",
        tags=["Thông báo quản trị"],
        summary="Đánh dấu một thông báo đã đọc",
        request=None,
        responses={
            200: NotificationReadResponseSerializer,
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Ngoài phạm vi role/site."),
            404: OpenApiResponse(description="Không tìm thấy thông báo."),
            503: OpenApiResponse(description="Site/CSDL không sẵn sàng."),
        },
    )
    def patch(self, request, site_code: str, slug: str):
        denied = _role_error(request.user)
        if denied:
            return denied
        try:
            result = mark_notification_read(
                user_id=request.user.account_id,
                role=request.user.role,
                user_site_code=request.user.site_code,
                site_code=site_code,
                slug=slug,
            )
        except (NotificationInfrastructureUnavailable, NotificationNotFound, PermissionError) as exc:
            return _service_error(exc)
        return Response(result, status=status.HTTP_200_OK)
