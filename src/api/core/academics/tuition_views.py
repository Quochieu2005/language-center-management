"""Admin/cashier tuition queries and cashier-only receipt creation."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.academics.common import AcademicError, site_scope
from core.academics.http import academic_error, remote_ip, validate_record_id
from core.academics.serializers import TuitionQuerySerializer, TuitionReceiptSerializer
from core.academics.tuition import collect_tuition, list_tuition
from core.auth.authentication import AuthCookieAuthentication


class _TuitionApiView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "tuition_management"


def _tuition_site(request, requested_site):
    return site_scope(
        request.user, requested_site,
        roles={"admin_big", "admin_small", "ke_toan"},
    )


class AdminTuitionListView(_TuitionApiView):
    @extend_schema(
        operation_id="admin_tuition_list",
        tags=["Học phí"],
        summary="Tra cứu học phí tại một cơ sở",
        description="LOCAL: Admin Big chọn site; Admin Small và kế toán chỉ truy cập site trong phiên. Không gộp dữ liệu học phí giữa các CSDL.",
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
            OpenApiParameter("status", str, OpenApiParameter.QUERY),
            OpenApiParameter("student_slug", str, OpenApiParameter.QUERY),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY),
            OpenApiParameter("offset", int, OpenApiParameter.QUERY),
        ],
        responses={200: OpenApiResponse(), 400: OpenApiResponse(), 403: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request):
        query = TuitionQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        try:
            site = _tuition_site(request, data.get("site_code"))
            return Response(list_tuition(
                site_code=site, status_filter=data.get("status"),
                student_slug=data.get("student_slug"), limit=data["limit"], offset=data["offset"],
            ))
        except AcademicError as exc:
            return academic_error(exc)


class TuitionReceiptCreateView(_TuitionApiView):
    @extend_schema(
        operation_id="tuition_receipt_create",
        tags=["Học phí"],
        summary="Thu học phí tại cơ sở bằng phiếu thu nội bộ",
        description=(
            "Chỉ kế toán có hồ sơ NhanVien đang làm tại site mới được ghi nhận thu. Số dư được đọc và khóa "
            "trong transaction LOCAL; `idempotency_key` tạo mã phiếu site-prefixed để retry sau timeout. "
            "API này ghi nhận thu tại quầy, chưa kết nối cổng thanh toán trực tuyến."
        ),
        parameters=[OpenApiParameter("tuition_id", str, OpenApiParameter.PATH), OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        request=TuitionReceiptSerializer,
        responses={200: OpenApiResponse(description="Retry đã khớp phiếu cũ."), 201: OpenApiResponse(description="Đã ghi phiếu thu."), 400: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 409: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def post(self, request, tuition_id):
        invalid = validate_record_id(tuition_id)
        if invalid:
            return invalid
        serializer = TuitionReceiptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            site = _tuition_site(request, request.query_params.get("site_code"))
            if request.user.role != "ke_toan":
                return Response({"detail": "Chỉ tài khoản kế toán gắn với hồ sơ nhân viên được phép ghi phiếu thu."}, status=403)
            result = collect_tuition(
                site_code=site, tuition_id=tuition_id, actor_id=request.user.account_id,
                employee_id=str(request.user.profile_id or ""), role=request.user.role,
                idempotency_key=serializer.validated_data["idempotency_key"],
                amount=serializer.validated_data["amount"],
                payment_method=serializer.validated_data["payment_method"],
                note=serializer.validated_data.get("note"), remote_ip=remote_ip(request),
            )
            response_status = status.HTTP_200_OK if result["replayed"] else status.HTTP_201_CREATED
            return Response(result, status=response_status)
        except AcademicError as exc:
            return academic_error(exc)
