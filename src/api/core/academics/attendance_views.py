"""REST endpoints for assigned-teacher rosters, sessions, and attendance."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.academics.attendance import (
    get_attendance_roster,
    list_teacher_classes,
    list_teacher_sessions,
    save_attendance_batch,
)
from core.academics.common import AcademicError
from core.academics.http import academic_error, remote_ip, user_profile, user_site, validate_record_id
from core.academics.serializers import AttendanceBatchSerializer
from core.auth.authentication import AuthCookieAuthentication


class _TeacherApiView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "attendance_management"

    def _teacher(self, request):
        if request.user.role != "giao_vien" or not user_site(request.user) or not user_profile(request.user):
            return None, Response({"detail": "Chức năng này chỉ dành cho giáo viên có hồ sơ đang dạy."}, status=403)
        return (user_site(request.user), user_profile(request.user)), None


class TeacherClassListView(_TeacherApiView):
    @extend_schema(
        operation_id="teacher_class_list",
        tags=["Giáo viên - Điểm danh"],
        summary="Liệt kê lớp đang được phân công cho giáo viên",
        responses={200: OpenApiResponse(description="Danh sách lớp tại CSDL site của giáo viên."), 403: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request):
        scope, error = self._teacher(request)
        if error:
            return error
        try:
            return Response({"site_code": scope[0], "results": list_teacher_classes(site_code=scope[0], teacher_id=scope[1])})
        except AcademicError as exc:
            return academic_error(exc)


class TeacherSessionListView(_TeacherApiView):
    @extend_schema(
        operation_id="teacher_session_list",
        tags=["Giáo viên - Điểm danh"],
        summary="Liệt kê buổi học của lớp được phân công",
        parameters=[OpenApiParameter("class_id", str, OpenApiParameter.PATH)],
        responses={200: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request, class_id):
        invalid = validate_record_id(class_id)
        if invalid:
            return invalid
        scope, error = self._teacher(request)
        if error:
            return error
        try:
            results = list_teacher_sessions(site_code=scope[0], teacher_id=scope[1], class_id=class_id)
            if not results:
                # An assigned class may have no sessions yet; distinguish it from a foreign class.
                classes = list_teacher_classes(site_code=scope[0], teacher_id=scope[1])
                if not any(row["class_id"] == class_id for row in classes):
                    return Response({"detail": "Không tìm thấy lớp được phân công."}, status=404)
            return Response({"site_code": scope[0], "class_id": class_id, "results": results})
        except AcademicError as exc:
            return academic_error(exc)


class TeacherSessionAttendanceView(_TeacherApiView):
    @extend_schema(
        operation_id="teacher_attendance_roster",
        tags=["Giáo viên - Điểm danh"],
        summary="Xem danh sách học viên và điểm danh của buổi học",
        parameters=[OpenApiParameter("session_id", str, OpenApiParameter.PATH)],
        responses={200: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request, session_id):
        invalid = validate_record_id(session_id)
        if invalid:
            return invalid
        scope, error = self._teacher(request)
        if error:
            return error
        try:
            return Response(get_attendance_roster(site_code=scope[0], teacher_id=scope[1], session_id=session_id))
        except AcademicError as exc:
            return academic_error(exc)

    @extend_schema(
        operation_id="teacher_attendance_upsert",
        tags=["Giáo viên - Điểm danh"],
        summary="Ghi hoặc cập nhật điểm danh theo lô",
        description=(
            "LOCAL tại CSDL của giáo viên. Chỉ thao tác buổi thuộc lớp được phân công; kiểm tra từng đăng ký "
            "thuộc đúng lớp, khóa buổi trong transaction, upsert theo cặp buổi/đăng ký và ghi Logs. "
            "Toàn bộ danh sách commit hoặc rollback cùng nhau."
        ),
        request=AttendanceBatchSerializer,
        responses={200: OpenApiResponse(), 400: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 409: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def put(self, request, session_id):
        invalid = validate_record_id(session_id)
        if invalid:
            return invalid
        serializer = AttendanceBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scope, error = self._teacher(request)
        if error:
            return error
        try:
            result = save_attendance_batch(
                site_code=scope[0], teacher_id=scope[1], actor_id=request.user.account_id,
                session_id=session_id, items=serializer.validated_data["items"],
                remote_ip=remote_ip(request),
            )
            return Response(result, status=status.HTTP_200_OK)
        except AcademicError as exc:
            return academic_error(exc)
