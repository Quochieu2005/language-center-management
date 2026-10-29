"""REST endpoints for grade entry and grade audit history."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.academics.common import AcademicError
from core.academics.grades import GRADE_TYPES, list_enrollment_grades, list_grade_history, upsert_enrollment_grade
from core.academics.http import academic_error, remote_ip, user_profile, user_site, validate_record_id
from core.academics.serializers import GradeWriteSerializer
from core.auth.authentication import AuthCookieAuthentication


class TeacherEnrollmentGradesView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "grade_management"

    @extend_schema(
        operation_id="teacher_enrollment_grades",
        tags=["Giáo viên - Điểm"],
        summary="Xem điểm của đăng ký trong lớp được phân công",
        parameters=[OpenApiParameter("enrollment_id", str, OpenApiParameter.PATH)],
        responses={200: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request, enrollment_id):
        invalid = validate_record_id(enrollment_id)
        if invalid:
            return invalid
        if request.user.role != "giao_vien" or not user_site(request.user) or not user_profile(request.user):
            return Response({"detail": "Chỉ giáo viên được xem điểm lớp được phân công."}, status=403)
        try:
            return Response(list_enrollment_grades(
                site_code=user_site(request.user), teacher_id=user_profile(request.user),
                enrollment_id=enrollment_id,
            ))
        except AcademicError as exc:
            return academic_error(exc)


class TeacherEnrollmentGradeHistoryView(TeacherEnrollmentGradesView):
    @extend_schema(
        operation_id="teacher_enrollment_grade_history",
        tags=["Giáo viên - Điểm"],
        summary="Xem lịch sử thay đổi điểm dạng chỉ đọc",
        parameters=[OpenApiParameter("enrollment_id", str, OpenApiParameter.PATH)],
        responses={200: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request, enrollment_id):
        invalid = validate_record_id(enrollment_id)
        if invalid:
            return invalid
        if request.user.role != "giao_vien" or not user_site(request.user) or not user_profile(request.user):
            return Response({"detail": "Chỉ giáo viên được phân công mới được xem lịch sử điểm."}, status=403)
        try:
            result = list_grade_history(
                site_code=user_site(request.user), teacher_id=user_profile(request.user),
                enrollment_id=enrollment_id,
            )
            result["count"] = len(result["results"])
            return Response(result)
        except AcademicError as exc:
            return academic_error(exc)


class TeacherEnrollmentGradeItemView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "grade_management"

    @extend_schema(
        operation_id="teacher_grade_upsert",
        tags=["Giáo viên - Điểm"],
        summary="Nhập hoặc sửa một loại điểm",
        description=(
            "LOCAL tại site của giáo viên. API tự lấy mã giáo viên từ phiên, kiểm tra lớp được phân công, "
            "loại điểm 0–10 và unique (ma_dang_ky, loai_diem). Ghi Logs append-only với giá trị trước/sau."
        ),
        parameters=[
            OpenApiParameter("enrollment_id", str, OpenApiParameter.PATH),
            OpenApiParameter("grade_type", str, OpenApiParameter.PATH, enum=list(GRADE_TYPES)),
        ],
        request=GradeWriteSerializer,
        responses={200: OpenApiResponse(), 400: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 409: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def put(self, request, enrollment_id, grade_type):
        invalid = validate_record_id(enrollment_id)
        if invalid:
            return invalid
        if grade_type not in GRADE_TYPES:
            return Response({"detail": "Loại điểm không hợp lệ."}, status=400)
        serializer = GradeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if request.user.role != "giao_vien" or not user_site(request.user) or not user_profile(request.user):
            return Response({"detail": "Chỉ giáo viên được phân công mới được nhập điểm."}, status=403)
        try:
            result = upsert_enrollment_grade(
                site_code=user_site(request.user), teacher_id=user_profile(request.user),
                actor_id=request.user.account_id, enrollment_id=enrollment_id,
                grade_type=grade_type, score=serializer.validated_data["score"],
                remote_ip=remote_ip(request),
            )
            return Response(result, status=status.HTTP_200_OK)
        except AcademicError as exc:
            return academic_error(exc)
