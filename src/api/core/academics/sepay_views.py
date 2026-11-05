"""Student SePay checkout endpoints and the unauthenticated signed webhook."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.academics.common import (
    AcademicConflict,
    AcademicInfrastructureUnavailable,
    AcademicInvalid,
    AcademicNotFound,
)
from core.academics.sepay import create_student_payment, get_student_payment, process_sepay_webhook
from core.academics.sepay_serializers import (
    SePayWebhookAckSerializer,
    StudentSePayPaymentCreateSerializer,
    StudentSePayPaymentResponseSerializer,
)
from core.auth.authentication import AuthCookieAuthentication
from core.students.views import _student_slug_error


def _payment_error(exc):
    if isinstance(exc, AcademicNotFound):
        return Response({"detail": str(exc) or "Không tìm thấy dữ liệu."}, status=404)
    if isinstance(exc, AcademicConflict):
        return Response({"detail": str(exc)}, status=409)
    if isinstance(exc, AcademicInvalid):
        return Response({"detail": str(exc)}, status=400)
    return Response(
        {"detail": "CSDL của cơ sở chưa sẵn sàng; thanh toán chưa được xác nhận."},
        status=503,
    )


class StudentSePayPaymentCreateView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "student_portal"

    @extend_schema(
        operation_id="student_sepay_payment_create",
        tags=["Cổng học viên", "Thanh toán SePay"],
        summary="Tạo hoặc tiếp tục yêu cầu QR thanh toán cho kỳ học phí đầu tiên còn nợ",
        parameters=[
            OpenApiParameter("slug", str, OpenApiParameter.PATH),
            OpenApiParameter("tuition_id", str, OpenApiParameter.PATH),
            OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True),
        ],
        request=StudentSePayPaymentCreateSerializer,
        responses={
            200: StudentSePayPaymentResponseSerializer,
            400: OpenApiResponse(description="Yêu cầu không hợp lệ hoặc SePay chưa cấu hình."),
            403: OpenApiResponse(description="Không phải học viên."),
            404: OpenApiResponse(description="Khoản học phí không thuộc học viên."),
            409: OpenApiResponse(description="Số dư/kỳ đóng đã đổi hoặc có yêu cầu đang mở."),
            503: OpenApiResponse(description="CSDL site chưa sẵn sàng."),
        },
    )
    def post(self, request, slug: str, tuition_id: str):
        error = _student_slug_error(request, slug)
        if error:
            return error
        serializer = StudentSePayPaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = request.headers.get("Idempotency-Key", "").strip()
        try:
            key = str(uuid.UUID(key))
        except (ValueError, AttributeError):
            return Response({"detail": "Idempotency-Key phải là UUID hợp lệ."}, status=400)
        try:
            result = create_student_payment(
                user=request.user, tuition_id=tuition_id,
                installment_id=serializer.validated_data["installment_id"],
                amount=serializer.validated_data["amount"], idempotency_key=key,
            )
        except (AcademicConflict, AcademicInfrastructureUnavailable, AcademicInvalid, AcademicNotFound) as exc:
            return _payment_error(exc)
        return Response(result, status=200)


class StudentSePayPaymentStatusView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "student_portal"

    @extend_schema(
        operation_id="student_sepay_payment_status",
        tags=["Cổng học viên", "Thanh toán SePay"],
        summary="Học viên xem trạng thái yêu cầu thanh toán của chính mình",
        parameters=[
            OpenApiParameter("slug", str, OpenApiParameter.PATH),
            OpenApiParameter("attempt_id", str, OpenApiParameter.PATH),
        ],
        responses={200: StudentSePayPaymentResponseSerializer, 404: OpenApiResponse(description="Không tìm thấy yêu cầu."), 503: OpenApiResponse(description="CSDL site chưa sẵn sàng.")},
    )
    def get(self, request, slug: str, attempt_id: str):
        error = _student_slug_error(request, slug)
        if error:
            return error
        try:
            result = get_student_payment(user=request.user, attempt_id=attempt_id)
        except (AcademicConflict, AcademicInfrastructureUnavailable, AcademicInvalid, AcademicNotFound) as exc:
            return _payment_error(exc)
        return Response(result)


@method_decorator(csrf_exempt, name="dispatch")
class SePayWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    @extend_schema(
        operation_id="sepay_webhook_receive",
        tags=["Thanh toán SePay"],
        summary="Nhận webhook SePay đã ký HMAC-SHA256",
        request=OpenApiTypes.OBJECT,
        responses={200: SePayWebhookAckSerializer, 401: OpenApiResponse(description="Chữ ký không hợp lệ."), 503: OpenApiResponse(description="Site database tạm thời chưa sẵn sàng.")},
    )
    def post(self, request):
        raw_body = request.body
        if len(raw_body) > 65536:
            return Response({"detail": "Payload quá lớn."}, status=413)
        try:
            timestamp = int(request.headers.get("X-SePay-Timestamp", ""))
        except ValueError:
            return Response({"detail": "Webhook không hợp lệ."}, status=401)
        signature = request.headers.get("X-SePay-Signature", "")
        if not settings.SEPAY_ENABLED or not settings.SEPAY_WEBHOOK_SECRET:
            return Response({"detail": "Webhook chưa được cấu hình."}, status=503)
        if abs(int(time.time()) - timestamp) > 300:
            return Response({"detail": "Webhook đã hết thời gian hợp lệ."}, status=401)
        signed = str(timestamp).encode("ascii") + b"." + raw_body
        digest = hmac.new(settings.SEPAY_WEBHOOK_SECRET.encode("utf-8"), signed, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(f"sha256={digest}", signature):
            return Response({"detail": "Webhook không hợp lệ."}, status=401)
        try:
            payload = json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response({"detail": "Payload JSON không hợp lệ."}, status=400)
        if not isinstance(payload, dict):
            return Response({"detail": "Payload JSON không hợp lệ."}, status=400)
        try:
            process_sepay_webhook(payload)
        except (AcademicConflict, AcademicInfrastructureUnavailable, AcademicInvalid, AcademicNotFound):
            return Response({"detail": "Site database chưa thể ghi nhận webhook."}, status=503)
        return Response({"success": True}, status=200)
