from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.auth.authentication import AuthCookieAuthentication
from core.notifications.serializers import NotificationListResponseSerializer, NotificationQuerySerializer
from core.notifications.services import NotificationInfrastructureUnavailable, NotificationNotFound, list_notifications


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
