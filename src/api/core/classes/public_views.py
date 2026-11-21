"""Anonymous public course registration endpoints."""

import hashlib

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from core.auth.authentication import AuthCookieAuthentication
from core.classes.services import register_student_to_class

from core.classes.public_enrollment import create_public_enrollment, list_public_course_classes
from core.classes.serializers import (
    PublicCourseClassListSerializer,
    PublicCourseClassQuerySerializer,
    PublicEnrollmentCreateSerializer,
    PublicEnrollmentResponseSerializer,
)
from core.classes.services import (
    ClassConflict,
    ClassInfrastructureUnavailable,
    ClassInvalid,
    ClassNotFound,
    ClassSiteUnavailable,
)


def _public_error(exc):
    if isinstance(exc, ClassConflict):
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    if isinstance(exc, ClassNotFound):
        return Response({"detail": "Không tìm thấy lớp đang nhận đăng ký."}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, (ClassInvalid, ClassSiteUnavailable)):
        return Response({"detail": "Cơ sở hoặc yêu cầu đăng ký không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {"detail": "Dịch vụ đăng ký tạm thời không sẵn sàng. Vui lòng thử lại sau."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _remote_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "") or "unknown"


class PublicEnrollmentEmailThrottle(SimpleRateThrottle):
    scope = "public_enrollment_email"

    def get_cache_key(self, request, view):
        email = str(request.data.get("email", "")).strip().casefold()
        if not email:
            return None
        identity = hashlib.sha256(f"{self.get_ident(request)}:{email}".encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": identity}


class PublicCourseClassListView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="public_course_classes",
        tags=["Khóa học"],
        summary="Xem lớp còn chỗ của khóa học tại một cơ sở",
        description=(
            "Đọc LOCAL từ CSDL cơ sở được chọn. Chỉ trả lớp đang nhận đăng ký, còn chỗ và có sĩ số "
            "khớp với số đăng ký đang hiệu lực. Không trả thông tin học viên hoặc nhân sự."
        ),
        parameters=[
            OpenApiParameter("course_slug", str, OpenApiParameter.PATH),
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY, required=True),
        ],
        responses={
            200: PublicCourseClassListSerializer,
            400: OpenApiResponse(description="Site không hợp lệ hoặc không hoạt động."),
            503: OpenApiResponse(description="CSDL site hoặc danh sách site không sẵn sàng."),
        },
    )
    def get(self, request, course_slug):
        query = PublicCourseClassQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            return Response(list_public_course_classes(
                site_code=query.validated_data["site_code"], course_slug=course_slug,
            ))
        except (ClassInfrastructureUnavailable, ClassNotFound, ClassSiteUnavailable) as exc:
            return _public_error(exc)


@method_decorator(csrf_protect, name="dispatch")
class PublicEnrollmentCreateView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle, PublicEnrollmentEmailThrottle]
    throttle_scope = "public_enrollment"

    @extend_schema(
        operation_id="public_course_enrollment_create",
        tags=["Đăng ký khóa học"],
        summary="Đăng ký học viên mới vào một lớp còn chỗ",
        description=(
            "Khách chọn một lớp tại đúng site. API giữ email trong directory đã bootstrap để tránh tạo "
            "hồ sơ lặp; nếu chưa có hồ sơ, tạo HocVien, DangKy, HocPhi và Logs tại CSDL site đã chọn "
            "trong cùng transaction cục bộ. Lớp, học phí và số chỗ được kiểm tra lại trong transaction. "
            "Khách ẩn danh chưa được tạo tài khoản; Admin cấp sau hoặc dùng signup riêng. "
            "Với phiên học viên, ghi danh vào chính hồ sơ/site từ phiên. CSRF bắt buộc. "
            "Directory kỹ thuật + LOCAL write, không phải transaction nguyên tử xuyên site."
        ),
        request=PublicEnrollmentCreateSerializer,
        responses={
            201: PublicEnrollmentResponseSerializer,
            400: OpenApiResponse(description="Dữ liệu đăng ký không hợp lệ."),
            409: OpenApiResponse(description="Lớp hết chỗ hoặc thông tin đã có hồ sơ."),
            429: OpenApiResponse(description="Đã vượt giới hạn gửi đăng ký."),
            503: OpenApiResponse(description="Một site hoặc dịch vụ cần thiết chưa sẵn sàng."),
        },
    )
    def post(self, request):
        serializer = PublicEnrollmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            data = serializer.validated_data
            data.setdefault("phone", None)
            if request.user.is_authenticated:
                user = request.user
                if user.role != "hoc_vien" or user.site_code != data["site_code"] or not user.profile_id:
                    raise ClassConflict("Hãy chọn lớp tại cơ sở tài khoản của bạn; liên hệ trung tâm nếu cần chuyển cơ sở.")
                enrolled = register_student_to_class(
                    site_code=user.site_code, student_id=user.profile_id, class_id=data["class_id"],
                    actor_id=user.account_id, remote_ip=_remote_ip(request),
                )
                result = {"site_code": user.site_code, "class_id": data["class_id"],
                          "accepted": True, "already_registered": not enrolled["created"]}
            else:
                result = create_public_enrollment(**data, remote_ip=_remote_ip(request))
        except (ClassConflict, ClassInfrastructureUnavailable, ClassInvalid, ClassNotFound, ClassSiteUnavailable) as exc:
            return _public_error(exc)
        result["message"] = ("Đã ghi nhận đăng ký. Xem học phí trong cổng học viên."
                             if request.user.is_authenticated else
                             "Yêu cầu đã được ghi nhận. Cơ sở sẽ liên hệ để xác nhận thông tin và cấp tài khoản sau.")
        return Response(result, status=status.HTTP_201_CREATED)
