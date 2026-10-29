"""Admin student-account issuance and self-only student portal endpoints."""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.auth.authentication import AuthCookieAuthentication
from core.auth.serializers import EmptyRequestSerializer
from core.students.deletion import (
    StudentDeletionPending,
    StudentPermissionDenied,
    delete_student,
)
from core.students.serializers import (
    StudentAccountProvisionResponseSerializer,
    StudentDeleteResponseSerializer,
    StudentEnrollmentListResponseSerializer,
    StudentGradesResponseSerializer,
    StudentListQuerySerializer,
    StudentListResponseSerializer,
    StudentProfileSerializer,
    StudentProfileUpdateSerializer,
    StudentScheduleResponseSerializer,
    StudentTuitionResponseSerializer,
)
from core.students.services import (
    StudentConflict,
    StudentInfrastructureUnavailable,
    StudentNotEligible,
    StudentNotFound,
    StudentSiteUnavailable,
    get_student_enrollments,
    get_student_grades,
    get_student_profile,
    get_student_schedule,
    get_student_tuition,
    issue_student_account,
    list_students,
    update_student_contact,
)


_ADMIN_ROLES = {"admin_big", "admin_small"}


def _resolve_admin_site(user, requested_site: str | None):
    if user.role not in _ADMIN_ROLES:
        return None, Response(
            {"detail": "Chỉ Admin Big hoặc Admin Small được quản lý tài khoản học viên."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if user.role == "admin_small":
        own_site = str(user.site_code or "").upper()
        if not own_site or requested_site:
            return None, Response(
                {"detail": "Admin Small chỉ được thao tác tại cơ sở trong phiên đăng nhập."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return own_site, None
    if not requested_site:
        return None, Response(
            {"detail": "Admin Big cần chọn site_code."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return requested_site, None


def _resolve_student_list_site(user, requested_site: str | None):
    """Allow consultants to search local student profiles without provisioning or deleting."""
    allowed_roles = {"admin_big", "admin_small", "tu_van"}
    if user.role not in allowed_roles:
        return None, Response(
            {"detail": "Chỉ Admin Big, Admin Small hoặc nhân viên tư vấn được tra cứu học viên."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if user.role == "admin_big":
        if not requested_site:
            return None, Response(
                {"detail": "Admin Big cần chọn site_code."}, status=status.HTTP_400_BAD_REQUEST,
            )
        return requested_site, None
    own_site = str(user.site_code or "").upper()
    if not own_site or requested_site:
        return None, Response(
            {"detail": "Tài khoản chỉ được tra cứu tại cơ sở trong phiên đăng nhập."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return own_site, None


def _student_service_error(exc):
    if isinstance(exc, StudentPermissionDenied):
        return Response(
            {"detail": "Bạn không có quyền quản lý học viên này trong phạm vi được giao."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if isinstance(exc, StudentNotFound):
        return Response({"detail": "Không tìm thấy học viên trong cơ sở được chọn."}, status=404)
    if isinstance(exc, StudentNotEligible):
        return Response(
            {"detail": "Chỉ cấp tài khoản cho học viên đang học, có đăng ký còn hiệu lực và email hợp lệ."},
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, StudentConflict):
        return Response(
            {"detail": "Học viên đã có tài khoản hoặc dữ liệu tài khoản đang xung đột."},
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, StudentSiteUnavailable):
        return Response(
            {"detail": "Cơ sở không hoạt động hoặc chưa có cấu hình kết nối."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {"detail": "Site, Coordinator, SQL Server hoặc email chưa sẵn sàng; thao tác chưa được xác nhận."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _student_delete_error(exc):
    if isinstance(exc, StudentPermissionDenied):
        return Response({"detail": "Bạn không có quyền xóa học viên này."}, status=403)
    if isinstance(exc, StudentDeletionPending):
        return Response(
            {"detail": "Đang xóa dữ liệu trên nhiều cơ sở; một số site có thể đã hoàn tất. Gửi lại cùng yêu cầu để tiếp tục, API chỉ xác nhận khi tất cả site hoàn tất."},
            status=503,
        )
    if isinstance(exc, StudentNotFound):
        return Response({"detail": "Không tìm thấy học viên trong cơ sở được chọn."}, status=404)
    if isinstance(exc, StudentConflict):
        return Response(
            {"detail": "Tài khoản học viên đang được tham chiếu bởi dữ liệu khác không thuộc hồ sơ học viên; cần đối soát trước khi xóa."},
            status=409,
        )
    if isinstance(exc, StudentSiteUnavailable):
        return Response({"detail": "Cơ sở không hoạt động hoặc chưa có cấu hình kết nối."}, status=400)
    return Response(
        {"detail": "Site, Coordinator hoặc SQL Server chưa sẵn sàng; thao tác chưa được xác nhận."},
        status=503,
    )


def _student_slug_error(request, slug: str):
    if request.user.role != "hoc_vien":
        return Response({"detail": "Chức năng này chỉ dành cho tài khoản học viên."}, status=403)
    if slug != request.user.slug:
        return Response({"detail": "Không tìm thấy hồ sơ học viên."}, status=404)
    return None


def _remote_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "") or "unknown"


class StudentAdminCollectionView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "student_management"

    @extend_schema(
        operation_id="admin_students_list",
        tags=["Quản lý học viên"],
        summary="Liệt kê hồ sơ học viên tại một cơ sở",
        description=(
            "Đọc LOCAL từ đúng CSDL site. Admin Big phải chọn site_code; Admin Small và tư vấn dùng site trong "
            "phiên đăng nhập và không được chọn site khác. Tư vấn chỉ tra cứu, không cấp tài khoản hay xóa học viên. "
            "Trả slug, trạng thái và cờ đã cấp tài khoản; "
            "không đọc hoặc nối dữ liệu giữa các CSDL site."
        ),
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
            OpenApiParameter("status", str, OpenApiParameter.QUERY),
            OpenApiParameter("search", str, OpenApiParameter.QUERY),
            OpenApiParameter("account_issued", bool, OpenApiParameter.QUERY),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY),
            OpenApiParameter("offset", int, OpenApiParameter.QUERY),
        ],
        responses={
            200: StudentListResponseSerializer,
            400: OpenApiResponse(description="Site hoặc bộ lọc không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên đã hết hạn."),
            403: OpenApiResponse(description="Vai trò không được quản lý học viên hoặc vượt phạm vi site."),
            503: OpenApiResponse(description="Site/CSDL chưa sẵn sàng."),
        },
    )
    def get(self, request):
        query = StudentListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        site_code, error = _resolve_student_list_site(request.user, data.get("site_code"))
        if error:
            return error
        try:
            result = list_students(
                site_code=site_code,
                status_filter=data.get("status"),
                search=data.get("search"),
                account_issued=data.get("account_issued"),
                limit=data["limit"],
                offset=data["offset"],
            )
        except (StudentInfrastructureUnavailable, StudentSiteUnavailable) as exc:
            return _student_service_error(exc)
        return Response(result)


class StudentAccountProvisionView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "student_account_create"

    @extend_schema(
        operation_id="admin_student_account_issue",
        tags=["Quản lý học viên"],
        summary="Cấp tài khoản cho học viên đã đăng ký học",
        request=EmptyRequestSerializer,
        description=(
            "Admin Big chọn site_code; Admin Small chỉ cấp tại site được phân công. Học viên phải đang "
            "học, có ít nhất một DangKy còn hiệu lực và có email trong HocVien. TaiKhoan được ghi có kiểm "
            "soát tới các site đang hoạt động; liên kết HocVien.ma_tai_khoan chỉ ghi tại site hồ sơ. API "
            "gửi mật khẩu tạm đã cấu hình qua email, BCrypt hash là giá trị duy nhất lưu trong CSDL và "
            "buộc đổi mật khẩu ở lần đăng nhập đầu. Yêu cầu lặp dùng lại tài khoản đã liên kết và kiểm tra các bản sao; "
            "không trả mật khẩu trong response."
        ),
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH),
                    OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        responses={
            201: StudentAccountProvisionResponseSerializer,
            400: OpenApiResponse(description="Site chưa được chọn hoặc không hoạt động."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên đã hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big/Admin Small trong đúng phạm vi được phép."),
            404: OpenApiResponse(description="Không tìm thấy hồ sơ học viên."),
            409: OpenApiResponse(description="Học viên chưa đủ điều kiện hoặc tài khoản đã/xung đột."),
            429: OpenApiResponse(description="Vượt giới hạn cấp tài khoản."),
            503: OpenApiResponse(description="SQL Server tại một site hoặc SMTP chưa sẵn sàng."),
        },
    )
    def post(self, request, slug: str):
        requested_site = request.query_params.get("site_code")
        if requested_site:
            requested_site = requested_site.strip().upper()
        site_code, error = _resolve_admin_site(request.user, requested_site)
        if error:
            return error
        try:
            result = issue_student_account(
                site_code=site_code,
                student_slug=slug,
                actor_id=request.user.account_id,
                remote_ip=_remote_ip(request),
            )
        except (
            StudentConflict,
            StudentInfrastructureUnavailable,
            StudentNotEligible,
            StudentNotFound,
            StudentSiteUnavailable,
        ) as exc:
            return _student_service_error(exc)
        return Response(
            {
                "account_id": result.account_id,
                "student_id": result.student_id,
                "slug": result.slug,
                "site_code": result.site_code,
                "username": result.username,
                "email": result.email,
                "role": "hoc_vien",
                "account_status": "active",
                "must_change_password": result.must_change_password,
                "email_sent": result.email_sent,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name="dispatch")
class StudentDeleteView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "student_management"

    @extend_schema(
        operation_id="admin_student_permanent_delete",
        tags=["Quản lý học viên"],
        summary="Xóa vĩnh viễn học viên và dữ liệu liên quan ở các cơ sở",
        description=(
            "Xóa vĩnh viễn bản HocVien tại các site đã cấu hình cùng DangKy, HocPhi, PhieuThu, Diem, "
            "DiemDanh, lịch sử/giao dịch chuyển cơ sở, tài khoản học viên đã nhân bản, phiên, OAuth, "
            "OTP, trạng thái đã đọc thông báo, thông báo gắn với tài khoản và nhật ký/sự kiện chỉ liên "
            "quan tới học viên đó. Admin Big phải chọn site_code; Admin Small dùng site trong phiên. "
            "Giáo viên chỉ được xóa khi mọi đăng ký còn hiệu lực tại site của mình thuộc lớp do giáo viên "
            "đó phụ trách. Mỗi site được xóa trong transaction cục bộ; Coordinator lưu tiến trình để retry "
            "và phục hồi tiến về phía trước. Đây không phải ACID nguyên tử xuyên site. API chỉ báo thành "
            "công khi tất cả site đã xác nhận; nếu lỗi giữa chừng, gọi lại cùng DELETE để tiếp tục. "
            "Cần cài migration 22 trên Coordinator và migration 23 trên từng site trước khi bật endpoint."
        ),
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH),
                    OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        request=EmptyRequestSerializer,
        responses={
            200: StudentDeleteResponseSerializer,
            400: OpenApiResponse(description="Admin Big chưa chọn site_code hoặc site không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên đã hết hạn."),
            403: OpenApiResponse(description="Vai trò hoặc phạm vi lớp/cơ sở không được phép."),
            404: OpenApiResponse(description="Không tìm thấy hồ sơ học viên."),
            409: OpenApiResponse(description="Tài khoản học viên còn được dữ liệu không thuộc hồ sơ này tham chiếu."),
            429: OpenApiResponse(description="Vượt giới hạn thao tác quản lý học viên."),
            503: OpenApiResponse(description="Site/Coordinator chưa sẵn sàng hoặc đang cần retry; API chưa xác nhận xóa toàn phần."),
        },
    )
    def delete(self, request, slug: str):
        requested_site = request.query_params.get("site_code")
        if requested_site:
            requested_site = requested_site.strip().upper()

        if request.user.role in _ADMIN_ROLES:
            site_code, error = _resolve_admin_site(request.user, requested_site)
            if error:
                return error
        elif request.user.role == "giao_vien":
            if requested_site or not request.user.site_code or not request.user.profile_id:
                return Response(
                    {"detail": "Giáo viên chỉ được thao tác tại cơ sở và lớp trong phiên đăng nhập."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            site_code = request.user.site_code
        else:
            return Response(
                {"detail": "Chỉ Admin Big, Admin Small hoặc giáo viên được xóa vĩnh viễn học viên."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            result = delete_student(
                site_code=site_code,
                student_slug=slug,
                actor_id=request.user.account_id,
                actor_role=request.user.role,
                teacher_id=request.user.profile_id if request.user.role == "giao_vien" else None,
            )
        except (
            StudentDeletionPending,
            StudentConflict,
            StudentInfrastructureUnavailable,
            StudentNotFound,
            StudentPermissionDenied,
            StudentSiteUnavailable,
        ) as exc:
            return _student_delete_error(exc)
        return Response(
            {
                "slug": result.slug,
                "site_code": result.site_code,
                "deleted": True,
                "deleted_site_count": result.deleted_site_count,
                "account_deleted": result.account_deleted,
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class StudentProfileView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "student_portal"

    @extend_schema(
        operation_id="student_profile_read",
        tags=["Cổng học viên"],
        summary="Học viên xem hồ sơ của chính mình theo slug",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        responses={200: StudentProfileSerializer, 403: OpenApiResponse(description="Không phải học viên."),
                   404: OpenApiResponse(description="Slug không thuộc học viên đang đăng nhập.")},
    )
    def get(self, request, slug: str):
        error = _student_slug_error(request, slug)
        if error:
            return error
        try:
            profile = get_student_profile(
                account_id=request.user.account_id,
                student_id=request.user.profile_id,
                site_code=request.user.site_code,
            )
        except (StudentInfrastructureUnavailable, StudentNotFound) as exc:
            return _student_service_error(exc)
        return Response(profile)

    @extend_schema(
        operation_id="student_profile_update_contact",
        tags=["Cổng học viên"],
        summary="Học viên cập nhật số điện thoại/địa chỉ của chính mình",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        request=StudentProfileUpdateSerializer,
        responses={200: StudentProfileSerializer, 400: OpenApiResponse(description="Thông tin liên hệ không hợp lệ."),
                   403: OpenApiResponse(description="Không phải học viên."),
                   404: OpenApiResponse(description="Slug không thuộc học viên đang đăng nhập."),
                   503: OpenApiResponse(description="CSDL site chưa sẵn sàng.")},
    )
    def patch(self, request, slug: str):
        error = _student_slug_error(request, slug)
        if error:
            return error
        serializer = StudentProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            profile = update_student_contact(
                user=request.user,
                changes=serializer.validated_data,
                remote_ip=_remote_ip(request),
            )
        except (StudentInfrastructureUnavailable, StudentNotFound, StudentConflict) as exc:
            return _student_service_error(exc)
        return Response(profile)


class _StudentPortalReadView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "student_portal"
    service = None
    response_schema = None
    operation_id = ""
    summary = ""

    @extend_schema(
        tags=["Cổng học viên"],
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        responses={200: StudentEnrollmentListResponseSerializer,
                   403: OpenApiResponse(description="Không phải học viên."),
                   404: OpenApiResponse(description="Slug không thuộc học viên đang đăng nhập."),
                   503: OpenApiResponse(description="CSDL site chưa sẵn sàng.")},
    )
    def get(self, request, slug: str):
        error = _student_slug_error(request, slug)
        if error:
            return error
        try:
            result = self.service(request.user)
        except (StudentInfrastructureUnavailable, StudentNotFound) as exc:
            return _student_service_error(exc)
        return Response(result)


class StudentEnrollmentListView(_StudentPortalReadView):
    service = staticmethod(get_student_enrollments)

    @extend_schema(operation_id="student_enrollments_read", tags=["Cổng học viên"],
                   summary="Học viên xem các khóa/lớp đã đăng ký", responses={200: StudentEnrollmentListResponseSerializer})
    def get(self, request, slug: str):
        return super().get(request, slug)


class StudentScheduleView(_StudentPortalReadView):
    service = staticmethod(get_student_schedule)

    @extend_schema(operation_id="student_schedule_read", tags=["Cổng học viên"],
                   summary="Học viên xem lịch học", responses={200: StudentScheduleResponseSerializer})
    def get(self, request, slug: str):
        return super().get(request, slug)


class StudentTuitionView(_StudentPortalReadView):
    service = staticmethod(get_student_tuition)

    @extend_schema(operation_id="student_tuition_read", tags=["Cổng học viên"],
                   summary="Học viên xem học phí và phiếu thu chỉ đọc", responses={200: StudentTuitionResponseSerializer})
    def get(self, request, slug: str):
        return super().get(request, slug)


class StudentGradesView(_StudentPortalReadView):
    service = staticmethod(get_student_grades)

    @extend_schema(operation_id="student_grades_read", tags=["Cổng học viên"],
                   summary="Học viên xem điểm của chính mình", responses={200: StudentGradesResponseSerializer})
    def get(self, request, slug: str):
        return super().get(request, slug)
