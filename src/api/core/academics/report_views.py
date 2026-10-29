"""Role-scoped local or global student count endpoint."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.academics.common import AcademicError
from core.academics.http import academic_error
from core.academics.reports import student_counts_by_site
from core.academics.serializers import StudentReportQuerySerializer
from core.auth.authentication import AuthCookieAuthentication


class StudentCountsBySiteView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "report_read"

    @extend_schema(
        operation_id="student_counts_by_site",
        tags=["Báo cáo phân tán"],
        summary="Thống kê học viên đang học theo cơ sở",
        description=(
            "Admin Big có thể đọc GLOBAL hoặc chọn một site. Admin Small chỉ đọc site của mình. "
            "Mỗi CSDL được truy vấn riêng rồi tổng hợp tại API; chỉ đếm HocVien.dang_hoc. "
            "Kết quả GLOBAL ghi complete=false và missing_sites nếu thiếu site."
        ),
        parameters=[OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        responses={200: OpenApiResponse(), 400: OpenApiResponse(), 403: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request):
        query = StudentReportQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        requested_site = query.validated_data.get("site_code")
        user = request.user
        if user.role == "admin_small":
            own_site = str(user.site_code or "").upper()
            if not own_site or (requested_site and requested_site != own_site):
                return Response({"detail": "Admin Small chỉ được thống kê cơ sở trong phiên đăng nhập."}, status=403)
            requested_site = own_site
        elif user.role != "admin_big":
            return Response({"detail": "Chỉ Admin Big hoặc Admin Small được xem báo cáo này."}, status=403)
        try:
            return Response(student_counts_by_site(requested_site=requested_site))
        except AcademicError as exc:
            return academic_error(exc)
