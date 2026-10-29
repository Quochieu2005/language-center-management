"""HTTP endpoint for requesting class-local unpaid tuition email reminders."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.academics.common import AcademicError, AcademicForbidden, AcademicInvalid, AcademicNotFound, site_scope
from core.academics.email_reminders import ReminderInfrastructureUnavailable, send_class_unpaid_tuition_reminders
from core.academics.http import validate_record_id
from core.auth.authentication import AuthCookieAuthentication
from core.auth.serializers import EmptyRequestSerializer


class ClassTuitionReminderView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "tuition_management"

    @extend_schema(
        operation_id="class_unpaid_tuition_reminders",
        tags=["Học phí - Nhắc nhở"],
        summary="Gửi email nhắc học phí còn thiếu của học viên trong lớp",
        description=(
            "LOCAL tại CSDL của một lớp. Admin Big/Admin Small/kế toán được gọi; kế toán phải có "
            "hồ sơ NhanVien đang làm tại site. API tính số dư từ HocPhi, gửi email cho học viên có "
            "dư nợ dương và có email, dùng Logs để không gửi lặp trong cùng ngày Việt Nam. "
            "Không đọc hoặc ghi CSDL của site khác."
        ),
        parameters=[
            OpenApiParameter("class_id", str, OpenApiParameter.PATH),
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
        ],
        request=EmptyRequestSerializer,
        responses={200: OpenApiResponse(), 400: OpenApiResponse(), 401: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 429: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def post(self, request, class_id):
        body = EmptyRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        invalid = validate_record_id(class_id)
        if invalid:
            return invalid
        try:
            site = site_scope(
                request.user, request.query_params.get("site_code"),
                roles={"admin_big", "admin_small", "ke_toan"},
            )
            result = send_class_unpaid_tuition_reminders(
                site_code=site, class_id=class_id, actor_id=request.user.account_id,
                actor_role=request.user.role, employee_id=request.user.profile_id,
            )
        except PermissionError:
            return Response({"detail": "Kế toán không còn hồ sơ đang làm tại cơ sở này."}, status=403)
        except AcademicError as exc:
            if isinstance(exc, AcademicForbidden):
                return Response({"detail": "Bạn không có quyền truy cập cơ sở này."}, status=403)
            if isinstance(exc, AcademicInvalid):
                return Response({"detail": str(exc)}, status=400)
            if isinstance(exc, AcademicNotFound):
                return Response({"detail": "Không tìm thấy lớp trong cơ sở đã chọn."}, status=404)
            return Response({"detail": "CSDL của cơ sở chưa sẵn sàng."}, status=503)
        except ReminderInfrastructureUnavailable:
            return Response({"detail": "SMTP chưa sẵn sàng; không gửi email nhắc học phí."}, status=503)
        except Exception:
            return Response({"detail": "Không thể xử lý nhắc học phí tại CSDL cơ sở."}, status=503)
        if result["unpaid_students"] == 0:
            # The service distinguishes a valid class with no balance from an unknown class.
            return Response(result)
        return Response(result)
