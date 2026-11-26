"""Admin list of course registrations, where staff then issue the student's login."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.academics.common import AcademicError, global_site_list
from core.auth.authentication import AuthCookieAuthentication
from core.students.course_registrations import list_course_registrations
from core.students.serializers import StrictInputSerializer
from core.students.services import StudentInfrastructureUnavailable, StudentSiteUnavailable
from core.students.views import _resolve_admin_site, _student_service_error

_ROLES = {"admin_big", "admin_small", "tu_van"}
_SITE_CODE = r"^[A-Za-z0-9_-]{2,10}$"


class CourseRegistrationQuerySerializer(StrictInputSerializer):
    site_code = serializers.RegexField(regex=_SITE_CODE, max_length=10, required=False)
    pending = serializers.BooleanField(required=False, default=True)
    search = serializers.CharField(max_length=100, required=False, trim_whitespace=True)
    limit = serializers.IntegerField(min_value=1, max_value=100, required=False, default=25)
    offset = serializers.IntegerField(min_value=0, max_value=100000, required=False, default=0)
    allowed_fields = {"site_code", "pending", "search", "limit", "offset"}

    def validate_site_code(self, value):
        return value.strip().upper()


class CourseRegistrationItemSerializer(serializers.Serializer):
    enrollment_id = serializers.CharField()
    enrolled_at = serializers.DateTimeField()
    enrollment_status = serializers.CharField()
    student_id = serializers.CharField()
    slug = serializers.CharField()
    site_code = serializers.CharField()
    full_name = serializers.CharField()
    email = serializers.CharField(allow_null=True)
    phone = serializers.CharField(allow_null=True)
    class_id = serializers.CharField()
    class_name = serializers.CharField()
    course_name = serializers.CharField()
    account_issued = serializers.BooleanField()
    account_issue_eligible = serializers.BooleanField()
    has_website_account = serializers.BooleanField(allow_null=True)


class CourseRegistrationListResponseSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("LOCAL", "GLOBAL"), required=False)
    complete = serializers.BooleanField(required=False)
    site_codes = serializers.ListField(child=serializers.CharField(), required=False)
    missing_sites = serializers.ListField(child=serializers.CharField(), required=False)
    site_code = serializers.CharField(required=False)
    count = serializers.IntegerField(allow_null=True)
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = CourseRegistrationItemSerializer(many=True)


class AdminCourseRegistrationListView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "student_portal"

    @extend_schema(
        operation_id="admin_course_registrations",
        tags=["Quản lý học viên"],
        summary="Danh sách người đã đăng ký khóa học và tình trạng tài khoản",
        description=(
            "Admin Big đọc toàn hệ thống (Global Query) hoặc một site; Admin Small và Tư vấn chỉ site của mình. "
            "Mặc định chỉ người chưa có tài khoản. `has_website_account` cho biết email đã có tài khoản xem web "
            "(sẽ được gắn vào hồ sơ khi cấp tài khoản). Việc cấp tài khoản dùng `POST /admin/students/{slug}/account/`."
        ),
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
            OpenApiParameter("pending", bool, OpenApiParameter.QUERY),
            OpenApiParameter("search", str, OpenApiParameter.QUERY),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY),
            OpenApiParameter("offset", int, OpenApiParameter.QUERY),
        ],
        responses={200: CourseRegistrationListResponseSerializer, 403: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request):
        query = CourseRegistrationQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        def read(site, limit, offset):
            return list_course_registrations(
                site_code=site, pending_only=data["pending"], search=data.get("search"), limit=limit, offset=offset,
            )

        if request.user.role == "admin_big" and not data.get("site_code"):
            try:
                return Response(global_site_list(
                    read, limit=data["limit"], offset=data["offset"],
                    unavailable_exceptions=(StudentInfrastructureUnavailable, StudentSiteUnavailable),
                ))
            except AcademicError as exc:
                return _student_service_error(exc)
        site_code, error = _resolve_admin_site(request.user, data.get("site_code"), allowed_roles=_ROLES)
        if error:
            return error
        try:
            return Response(read(site_code, data["limit"], data["offset"]))
        except (StudentInfrastructureUnavailable, StudentSiteUnavailable) as exc:
            return _student_service_error(exc)
