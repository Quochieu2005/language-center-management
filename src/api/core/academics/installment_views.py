"""Admin API for configuring and reading site-local tuition schedules."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.academics.common import AcademicError, site_scope
from core.academics.http import academic_error, remote_ip, validate_record_id
from core.academics.installment_serializers import (
    TuitionInstallmentPlanResponseSerializer,
    TuitionInstallmentPlanWriteSerializer,
)
from core.academics.tuition_installments import (
    get_tuition_installment_plan,
    set_tuition_installment_plan,
)
from core.auth.authentication import AuthCookieAuthentication
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView


_PLAN_ROLES = {"admin_big", "admin_small", "le_tan", "ke_toan"}


def _plan_site(request, requested_site):
    return site_scope(request.user, requested_site, roles=_PLAN_ROLES)


class TuitionInstallmentPlanView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "tuition_management"

    @extend_schema(
        operation_id="tuition_installment_plan_read",
        tags=["Học phí"],
        summary="Xem lịch đóng các kỳ học phí",
        description="LOCAL: Đọc lịch tại đúng site đang giữ HocPhi; kỳ quá hạn được tính theo ngày Việt Nam.",
        parameters=[
            OpenApiParameter("tuition_id", str, OpenApiParameter.PATH),
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
        ],
        responses={
            200: TuitionInstallmentPlanResponseSerializer,
            400: OpenApiResponse(), 403: OpenApiResponse(),
            404: OpenApiResponse(), 409: OpenApiResponse(), 503: OpenApiResponse(),
        },
    )
    def get(self, request, tuition_id: str):
        invalid = validate_record_id(tuition_id)
        if invalid:
            return invalid
        try:
            site = _plan_site(request, request.query_params.get("site_code"))
            return Response(get_tuition_installment_plan(site_code=site, tuition_id=tuition_id))
        except AcademicError as exc:
            return academic_error(exc)

    @extend_schema(
        operation_id="tuition_installment_plan_set",
        tags=["Học phí"],
        summary="Chọn đóng một lần hoặc chia học phí theo tháng",
        description=(
            "LOCAL: Chỉ được đổi kế hoạch trước lần thu đầu tiên. Kỳ chia đều, phần dư được cộng vào kỳ cuối. "
            "Các lần thu sau được phân bổ vào kỳ chưa đóng có hạn sớm nhất; kế toán vẫn ghi phiếu thu qua endpoint receipts."
        ),
        parameters=[
            OpenApiParameter("tuition_id", str, OpenApiParameter.PATH),
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
        ],
        request=TuitionInstallmentPlanWriteSerializer,
        responses={
            200: TuitionInstallmentPlanResponseSerializer,
            400: OpenApiResponse(), 403: OpenApiResponse(),
            404: OpenApiResponse(), 409: OpenApiResponse(), 503: OpenApiResponse(),
        },
    )
    def put(self, request, tuition_id: str):
        invalid = validate_record_id(tuition_id)
        if invalid:
            return invalid
        serializer = TuitionInstallmentPlanWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            site = _plan_site(request, request.query_params.get("site_code"))
            result = set_tuition_installment_plan(
                site_code=site,
                tuition_id=tuition_id,
                payment_mode=data["payment_mode"],
                installment_count=data.get("installment_count"),
                first_due_date=data["first_due_date"],
                actor_id=request.user.account_id,
                remote_ip=remote_ip(request),
            )
            return Response(result, status=status.HTTP_200_OK)
        except AcademicError as exc:
            return academic_error(exc)
