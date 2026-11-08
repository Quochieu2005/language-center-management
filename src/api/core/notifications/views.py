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
    NotificationCreateResponseSerializer,
    NotificationCreateSerializer,
    NotificationListResponseSerializer,
    NotificationQuerySerializer,
)
from core.notifications.creation import NotificationCreateConflict, create_notification
from core.notifications.services import NotificationInfrastructureUnavailable, NotificationNotFound, list_notifications


_ADMIN_ROLES = {"admin_big", "admin_small"}


def _role_error(user):
    if getattr(user, "role", None) in _ADMIN_ROLES:
        return None
    return Response(
        {"detail": "Chỉ Admin Big hoặc Admin Small được quản lý thông báo."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _service_error(exc):
    if isinstance(exc, NotificationNotFound):
        return Response({"detail": "Không tìm thấy thông báo trong phạm vi được phép."}, status=404)
    return Response(
        {"detail": "Danh mục site hoặc CSDL thông báo chưa sẵn sàng; không thể xác nhận dữ liệu đầy đủ."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@method_decorator(csrf_protect, name="dispatch")
class AdminNotificationListView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "notification_read"

    def get_throttles(self):
        self.throttle_scope = "notification_write" if self.request.method == "POST" else "notification_read"
        return super().get_throttles()

    @extend_schema(
        operation_id="admin_notification_list",
        tags=["Thông báo quản trị"],
        summary="Liệt kê thông báo theo phạm vi admin",
        description=(
            "Admin Small chỉ đọc CSDL của cơ sở được gán. Admin Big đọc các CSDL site đang hoạt động "
            "qua Global Query; API gộp kết quả tại tầng ứng dụng, không JOIN xuyên site. "
            "Hệ thống không lưu trạng thái ai đã đọc thông báo. Nếu thiếu site, response báo complete=false "
            "và missing_sites, không giả định danh sách là đầy đủ."
        ),
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("category", str, OpenApiParameter.QUERY, required=False),
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

        query = NotificationQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        options = query.validated_data
        if request.user.role == "admin_small" and options.get("site_code"):
            return Response(
                {"detail": "Admin Small chỉ được xem thông báo tại cơ sở được gán."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            result = list_notifications(
                role=request.user.role,
                user_site_code=request.user.site_code,
                site_code=options.get("site_code"),
                category=options.get("category"),
                limit=options["limit"],
                offset=options["offset"],
            )
        except (NotificationInfrastructureUnavailable, NotificationNotFound) as exc:
            return _service_error(exc)

        response_status = status.HTTP_200_OK if result["complete"] else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(result, status=response_status)

    @extend_schema(
        operation_id="admin_notification_create",
        tags=["Thông báo quản trị"],
        summary="Tạo thông báo quản trị",
        description=(
            "Admin Small chỉ ghi tại site được gán (LOCAL). Admin Big ghi tới mọi site đang hoạt động "
            "theo chính sách đồng bộ tầng API (REPLICATED-WRITE). Dữ liệu dùng dbo.ThongBao hiện có; "
            "ghi nhật ký dbo.Logs trong cùng transaction cục bộ. Nếu thiếu site, trả 202 complete=false; "
            "retry cùng Idempotency-Key và body để hoàn tất. Không có giao dịch ACID xuyên site."
        ),
        parameters=[OpenApiParameter(
            "Idempotency-Key", str, OpenApiParameter.HEADER, required=True,
            description="8–128 ký tự; dùng lại đúng key và body khi retry.",
        )],
        request=NotificationCreateSerializer,
        responses={
            200: NotificationCreateResponseSerializer,
            202: NotificationCreateResponseSerializer,
            400: OpenApiResponse(description="Body hoặc Idempotency-Key không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Vai trò không được phép hoặc Admin Small chọn nhóm ngoài quyền."),
            409: OpenApiResponse(description="Idempotency-Key được dùng lại với nội dung khác."),
            503: OpenApiResponse(description="Không xác định được site hoạt động hoặc CSDL chưa sẵn sàng."),
        },
    )
    def post(self, request):
        denied = _role_error(request.user)
        if denied:
            return denied

        serializer = NotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notification = serializer.validated_data
        if request.user.role == "admin_small" and notification["audience"] == "admin_big":
            return Response(
                {"detail": "Admin Small không được tạo thông báo riêng cho Admin Big."},
                status=status.HTTP_403_FORBIDDEN,
            )

        key = str(request.headers.get("Idempotency-Key", "")).strip()
        if (
            len(key) < 8 or len(key) > 128
            or not all(character.isalnum() or character in "._:-" for character in key)
        ):
            return Response(
                {"detail": "Idempotency-Key phải có 8–128 ký tự chữ, số hoặc . _ : -."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = create_notification(
                role=request.user.role,
                user_site_code=request.user.site_code,
                actor_id=str(request.user.account_id),
                idempotency_key=key,
                notification=notification,
            )
        except NotificationCreateConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except NotificationNotFound as exc:
            return _service_error(exc)
        except NotificationInfrastructureUnavailable as exc:
            return _service_error(exc)

        response_status = status.HTTP_200_OK if result["complete"] else status.HTTP_202_ACCEPTED
        return Response(result, status=response_status)
