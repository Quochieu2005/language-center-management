from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.audit.serializers import AuditLogListResponseSerializer, AuditLogQuerySerializer
from core.audit.services import AuditInfrastructureUnavailable, AuditNotFound, list_audit_logs
from core.auth.authentication import AuthCookieAuthentication


@method_decorator(csrf_protect, name="dispatch")
class AdminAuditLogListView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "report_read"

    @extend_schema(
        operation_id="admin_audit_log_list",
        tags=["Nhật ký quản trị"],
        summary="Đọc nhật ký thao tác theo phạm vi quản trị",
        description=(
            "Admin Big đọc GLOBAL qua các CSDL site riêng hoặc lọc một site; Admin Small chỉ đọc site được gán. "
            "Đọc dbo.Logs không sửa/xóa dữ liệu. Response chỉ gồm thông tin định danh thao tác; không trả IP, "
            "hash định danh, JSON trước/sau, token hay ghi chú tự do. Nếu thiếu site, trả 503 cùng complete=false."
        ),
        parameters=[
            OpenApiParameter("ma_co_so", str, OpenApiParameter.QUERY),
            OpenApiParameter("ma_tai_khoan", str, OpenApiParameter.QUERY),
            OpenApiParameter("loai_log", str, OpenApiParameter.QUERY),
            OpenApiParameter("tu_ngay", str, OpenApiParameter.QUERY, description="Ngày Việt Nam, YYYY-MM-DD."),
            OpenApiParameter("den_ngay", str, OpenApiParameter.QUERY, description="Ngày Việt Nam, YYYY-MM-DD."),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY),
            OpenApiParameter("offset", int, OpenApiParameter.QUERY),
        ],
        responses={
            200: AuditLogListResponseSerializer,
            400: OpenApiResponse(description="Bộ lọc không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Không có quyền đọc nhật ký của site được yêu cầu."),
            404: OpenApiResponse(description="Không tìm thấy site đang hoạt động."),
            503: AuditLogListResponseSerializer,
        },
    )
    def get(self, request):
        query = AuditLogQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        filters = query.validated_data
        role = request.user.role
        if role not in {"admin_big", "admin_small"}:
            return Response({"detail": "Chỉ Admin Big hoặc Admin Small được xem nhật ký."}, status=403)
        if role == "admin_small" and filters.get("ma_co_so"):
            return Response({"detail": "Admin Small không được chọn cơ sở khác."}, status=403)
        try:
            result = list_audit_logs(
                role=role,
                user_site_code=request.user.site_code,
                site_code=filters.get("ma_co_so"),
                account_id=filters.get("ma_tai_khoan"),
                log_type=filters.get("loai_log"),
                from_date=filters.get("tu_ngay"),
                to_date=filters.get("den_ngay"),
                limit=filters["limit"],
                offset=filters["offset"],
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except AuditNotFound:
            return Response({"detail": "Không tìm thấy cơ sở đang hoạt động."}, status=404)
        except AuditInfrastructureUnavailable:
            return Response({"detail": "Không thể xác định danh sách site hoặc kết nối nhật ký."}, status=503)
        return Response(result, status=200 if result["complete"] else status.HTTP_503_SERVICE_UNAVAILABLE)
