"""Site-scoped consultant transfer requests and admin decisions."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.academics.common import AcademicError
from core.academics.http import academic_error, validate_record_id
from core.academics.serializers import (
    TransferDecisionSerializer,
    TransferListQuerySerializer,
    TransferRequestSerializer,
)
from core.academics.transfers import (
    create_transfer_request,
    decide_transfer,
    execute_approved_transfer,
    list_transfer_requests,
    retry_transfer,
)
from core.auth.authentication import AuthCookieAuthentication


class _TransferApiView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "transfer_management"


class TransferCollectionView(_TransferApiView):
    @extend_schema(
        operation_id="transfer_request_list",
        tags=["Chuyển cơ sở"],
        summary="Liệt kê đề nghị chuyển cơ sở",
        description=(
            "Admin Big đọc hộp thư GLOBAL qua từng site; response có complete/missing_sites. "
            "Admin Small xem đề nghị phát sinh tại site mình và đề nghị gửi tới site mình để duyệt. "
            "Chỉ Tư vấn & xếp lớp được tạo đề nghị và xem danh sách tại site trong phiên; "
            "Kế toán & Lễ tân chỉ đọc tại site trong phiên. "
            "Mỗi dòng kèm tổng phải thu/đã thu/còn nợ được tính riêng từ DangKy/HocPhi tại site nguồn; "
            "Admin Big hoặc Admin Small tại site nhận được duyệt/từ chối; retry vẫn chỉ thuộc Admin Big."
        ),
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
            OpenApiParameter("status", str, OpenApiParameter.QUERY),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY),
            OpenApiParameter("offset", int, OpenApiParameter.QUERY),
        ],
        request=None,
        responses={200: OpenApiResponse(), 400: OpenApiResponse(), 403: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request):
        query = TransferListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        try:
            result = list_transfer_requests(
                role=request.user.role, user_site=request.user.site_code,
                requested_site=data.get("site_code"), status_filter=data.get("status"),
                limit=data["limit"], offset=data["offset"],
            )
            return Response(result)
        except AcademicError as exc:
            return academic_error(exc)

    @extend_schema(
        operation_id="transfer_request_create",
        tags=["Chuyển cơ sở"],
        summary="Tư vấn & xếp lớp đề nghị chuyển học viên sang cơ sở khác",
        description=(
            "LOCAL tại nguồn. Nguồn lấy từ phiên Tư vấn & xếp lớp; kiểm tra học viên đang học, không còn công nợ, "
            "site đích đang hoạt động và không có giao dịch mở. Chưa ghi hồ sơ đích hoặc đổi trạng thái nguồn."
        ),
        request=TransferRequestSerializer,
        responses={201: OpenApiResponse(), 400: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 409: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def post(self, request):
        serializer = TransferRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if request.user.role != "tu_van" or not request.user.site_code:
            return Response({"detail": "Chỉ Tư vấn & xếp lớp được tạo đề nghị tại cơ sở được phân công."}, status=403)
        try:
            result = create_transfer_request(
                source_site=request.user.site_code,
                student_slug=serializer.validated_data["student_slug"],
                target_site=serializer.validated_data["target_site"],
                actor_id=request.user.account_id, remote_ip=str(request.META.get("REMOTE_ADDR", "")),
                reason=serializer.validated_data["reason"],
            )
            return Response(result, status=status.HTTP_201_CREATED)
        except AcademicError as exc:
            return academic_error(exc)


class TransferDecisionView(_TransferApiView):
    @extend_schema(
        operation_id="transfer_request_decide",
        tags=["Chuyển cơ sở"],
        summary="Admin Big hoặc Admin Small cơ sở nhận duyệt/từ chối đề nghị",
        description=(
            "Quyết định ghi LOCAL vào CSDL nguồn. Duyệt chỉ chấp nhận đề nghị đang chờ; sau commit, "
            "Admin Small chỉ được quyết định đề nghị có cơ sở đích đúng cơ sở trong phiên. Coordinator "
            "thực hiện tiến trình giữa nguồn và đích; sau hoàn tất, hệ thống gửi thông báo LOCAL cho nhân sự site nhận. "
            "Nếu một site lỗi, trạng thái được giữ để Admin Big retry."
        ),
        parameters=[OpenApiParameter("source_site", str, OpenApiParameter.PATH), OpenApiParameter("transfer_id", str, OpenApiParameter.PATH)],
        request=TransferDecisionSerializer,
        responses={200: OpenApiResponse(), 202: OpenApiResponse(description="Đã duyệt, tiến trình cần retry."), 400: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 409: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def post(self, request, source_site, transfer_id):
        invalid = validate_record_id(transfer_id)
        if invalid:
            return invalid
        serializer = TransferDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if request.user.role not in {"admin_big", "admin_small"} or (
            request.user.role == "admin_small" and not request.user.site_code
        ):
            return Response({"detail": "Chỉ Admin Big hoặc Admin Small tại cơ sở nhận được quyết định đề nghị chuyển."}, status=403)
        try:
            decision = serializer.validated_data
            result = decide_transfer(
                source_site=source_site, transfer_id=transfer_id,
                actor_id=request.user.account_id, actor_role=request.user.role,
                actor_site=request.user.site_code, decision=decision["decision"],
                reason=decision.get("reason"),
            )
            if decision["decision"] == "reject":
                return Response(result)
            try:
                progressed = execute_approved_transfer(
                    source_site=source_site, transfer_id=transfer_id, actor_id=request.user.account_id,
                )
                return Response(progressed, status=200 if progressed["complete"] else 202)
            except AcademicError as exc:
                if exc.__class__.__name__ == "AcademicInfrastructureUnavailable":
                    return Response(
                        {"transfer_id": transfer_id, "status": "dang_xu_ly", "complete": False,
                         "detail": "Đề nghị đã được duyệt nhưng một bước điều phối chưa xong; có thể gọi lại API retry."},
                        status=202,
                    )
                return academic_error(exc)
        except AcademicError as exc:
            return academic_error(exc)


class TransferRetryView(_TransferApiView):
    @extend_schema(
        operation_id="transfer_retry",
        tags=["Chuyển cơ sở"],
        summary="Admin Big tiếp tục một giao dịch chuyển đã duyệt",
        parameters=[OpenApiParameter("source_site", str, OpenApiParameter.PATH), OpenApiParameter("transfer_id", str, OpenApiParameter.PATH)],
        request=None,
        responses={200: OpenApiResponse(), 202: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 409: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def post(self, request, source_site, transfer_id):
        invalid = validate_record_id(transfer_id)
        if invalid:
            return invalid
        if request.user.role != "admin_big":
            return Response({"detail": "Chỉ Admin Big được retry giao dịch chuyển."}, status=403)
        try:
            result = retry_transfer(
                source_site=source_site, transfer_id=transfer_id,
                actor_id=request.user.account_id,
            )
            return Response(result, status=200 if result["complete"] else 202)
        except AcademicError as exc:
            return academic_error(exc)
