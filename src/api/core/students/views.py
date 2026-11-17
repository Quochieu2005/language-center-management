"""Admin student-account issuance and self-only student portal endpoints."""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.academics.common import AcademicError, global_site_list
from core.auth.authentication import AuthCookieAuthentication
from core.auth.serializers import EmptyRequestSerializer
from core.media.avatars import (
    AvatarConflict,
    AvatarInvalidIntent,
    AvatarInvalidUpload,
    AvatarUnavailable,
)
from core.media.serializers import (
    AdminAvatarFinalizeRequestSerializer,
    AdminAvatarUploadIntentResponseSerializer,
)
from core.students.serializers import (
    StudentAccountProvisionResponseSerializer,
    StudentAdminProfileSerializer,
    StudentAvatarResponseSerializer,
    StudentCreateSerializer,
    StudentDeleteResponseSerializer,
    StudentEnrollmentListResponseSerializer,
    StudentGradesResponseSerializer,
    StudentListQuerySerializer,
    StudentListResponseSerializer,
    StudentProfileSerializer,
    StudentProfileUpdateSerializer,
    StudentSiteQuerySerializer,
    StudentScheduleResponseSerializer,
    StudentTuitionResponseSerializer,
    StudentUpdateSerializer,
)
from core.students.services import (
    StudentConflict,
    StudentInfrastructureUnavailable,
    StudentNotEligible,
    StudentNotFound,
    StudentSiteUnavailable,
    create_student_profile,
    delete_student_profile,
    get_admin_student_profile,
    get_student_enrollments,
    get_student_grades,
    get_student_profile,
    get_student_schedule,
    get_student_tuition,
    issue_student_account,
    list_students,
    update_student_profile,
    update_student_contact,
)
from core.students.avatars import (
    complete_student_avatar_upload,
    create_student_avatar_upload_intent,
)


_ADMIN_ROLES = {"admin_big", "admin_small"}


def _resolve_admin_site(user, requested_site: str | None):
    if user.role not in _ADMIN_ROLES:
        return None, Response(
            {"detail": "Chỉ Admin Big hoặc Admin Small được quản lý hồ sơ học viên."},
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
    allowed_roles = {"admin_big", "admin_small", "tu_van", "ke_toan"}
    if user.role not in allowed_roles:
        return None, Response(
            {"detail": "Tài khoản không được phép tra cứu học viên tại cơ sở."},
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


def _resolve_request_admin_site(request):
    query = StudentSiteQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    return _resolve_admin_site(request.user, query.validated_data.get("site_code"))


def _student_service_error(exc):
    if isinstance(exc, StudentNotFound):
        return Response({"detail": "Không tìm thấy học viên trong cơ sở được chọn."}, status=404)
    if isinstance(exc, StudentNotEligible):
        return Response(
            {"detail": "Chỉ cấp tài khoản cho hồ sơ đang học có email hợp lệ."},
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, StudentConflict):
        return Response(
            {"detail": "Dữ liệu hồ sơ hoặc tài khoản đang được nghiệp vụ khác sử dụng; không thể hoàn tất thao tác."},
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
    if isinstance(exc, StudentNotFound):
        return Response({"detail": "Không tìm thấy học viên trong cơ sở được chọn."}, status=404)
    if isinstance(exc, StudentConflict):
        return Response(
            {"detail": "Hồ sơ đã có tài khoản, đăng ký hoặc lịch sử chuyển cơ sở; giữ dữ liệu và không thể xóa cứng."},
            status=409,
        )
    if isinstance(exc, StudentSiteUnavailable):
        return Response({"detail": "Cơ sở không hoạt động hoặc chưa có cấu hình kết nối."}, status=400)
    return Response(
        {"detail": "Site, Coordinator hoặc SQL Server chưa sẵn sàng; thao tác chưa được xác nhận."},
        status=503,
    )


def _student_avatar_error(exc):
    if isinstance(exc, StudentNotFound):
        return Response({"detail": "Không tìm thấy học viên trong cơ sở được chọn."}, status=404)
    if isinstance(exc, StudentSiteUnavailable):
        return Response({"detail": "Cơ sở không hoạt động hoặc chưa có cấu hình kết nối."}, status=400)
    if isinstance(exc, (AvatarInvalidIntent, AvatarInvalidUpload)):
        return Response({"detail": str(exc)}, status=400)
    if isinstance(exc, (AvatarConflict, StudentConflict)):
        return Response({"detail": str(exc)}, status=409)
    return Response(
        {"detail": str(exc) or "Site, SQL Server hoặc Cloudinary chưa sẵn sàng.", "complete": False},
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


@method_decorator(csrf_protect, name="dispatch")
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
            "Đọc LOCAL từ đúng CSDL site. Admin Big phải chọn site_code; Admin Small, tư vấn và kế toán dùng site trong "
            "phiên đăng nhập và không được chọn site khác. Tư vấn chỉ tra cứu; kế toán chỉ dùng danh sách để chọn học viên khi đăng ký lớp. "
            "Các vai trò này không cấp tài khoản hay xóa học viên. "
            "Trả slug, trạng thái, cờ đã cấp tài khoản và điều kiện hiện tại để cấp tài khoản; "
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
        if request.user.role == "admin_big" and not data.get("site_code"):
            try:
                result = global_site_list(
                    lambda site, limit, offset: list_students(
                        site_code=site, status_filter=data.get("status"), search=data.get("search"),
                        account_issued=data.get("account_issued"), limit=limit, offset=offset,
                    ),
                    limit=data["limit"], offset=data["offset"],
                    unavailable_exceptions=(StudentInfrastructureUnavailable, StudentSiteUnavailable),
                )
            except AcademicError as exc:
                return _student_service_error(exc)
            return Response(result)
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

    @extend_schema(
        operation_id="admin_student_create",
        tags=["Quản lý học viên"],
        summary="Tạo hồ sơ học viên tại một cơ sở",
        description=(
            "Ghi LOCAL vào HocVien tại site đã được xác thực qua Site Router. Admin Big chọn site_code; "
            "Admin Small chỉ dùng site trong phiên. Sinh mã học viên theo sequence của site, ghi nhật ký "
            "cùng transaction. Không tạo TaiKhoan hoặc gửi mật khẩu; tài khoản chỉ được cấp bằng thao tác riêng "
            "khi hồ sơ có email hợp lệ."
        ),
        parameters=[OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        request=StudentCreateSerializer,
        responses={
            201: StudentAdminProfileSerializer,
            400: OpenApiResponse(description="Site hoặc dữ liệu hồ sơ không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên đã hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big/Admin Small đúng phạm vi được tạo hồ sơ."),
            503: OpenApiResponse(description="Site/CSDL chưa sẵn sàng."),
        },
    )
    def post(self, request):
        site_code, error = _resolve_request_admin_site(request)
        if error:
            return error
        serializer = StudentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            profile = create_student_profile(
                site_code=site_code,
                fields=serializer.validated_data,
                actor_id=request.user.account_id,
                remote_ip=_remote_ip(request),
            )
        except (StudentConflict, StudentInfrastructureUnavailable, StudentSiteUnavailable) as exc:
            return _student_service_error(exc)
        return Response(profile, status=status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name="dispatch")
class StudentAccountProvisionView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "student_account_create"

    @extend_schema(
        operation_id="admin_student_account_issue",
        tags=["Quản lý học viên"],
        summary="Cấp tài khoản cho học viên đang học",
        request=EmptyRequestSerializer,
        description=(
            "Admin Big chọn site_code; Admin Small chỉ cấp tại site được phân công. Học viên phải đang "
            "học và có email hợp lệ trong HocVien. Không yêu cầu đã có DangKy. TaiKhoan được ghi có kiểm "
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
class StudentAdminDetailView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "student_management"

    @extend_schema(
        operation_id="admin_student_detail",
        tags=["Quản lý học viên"],
        summary="Xem và cập nhật hồ sơ học viên tại một cơ sở",
        description=(
            "Đọc/sửa LOCAL trong HocVien của site được xác thực. Chỉ Admin Big hoặc Admin Small được phép; "
            "Admin Big chọn site_code, Admin Small dùng site trong phiên. Không sửa hồ sơ đã chuyển đi, "
            "đang được giao dịch chuyển xử lý, hoặc email đã gắn với tài khoản. Tư vấn chỉ đọc danh sách."
        ),
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH),
                    OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        responses={
            200: StudentAdminProfileSerializer,
            400: OpenApiResponse(description="Admin Big chưa chọn site_code hoặc site không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên đã hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big/Admin Small đúng phạm vi được xem hồ sơ."),
            404: OpenApiResponse(description="Không tìm thấy hồ sơ học viên."),
            409: OpenApiResponse(description="Hồ sơ đang bị khóa bởi giao dịch chuyển hoặc tài khoản."),
            503: OpenApiResponse(description="Site/CSDL chưa sẵn sàng."),
        },
    )
    def get(self, request, slug: str):
        site_code, error = _resolve_request_admin_site(request)
        if error:
            return error
        try:
            profile = get_admin_student_profile(site_code=site_code, student_slug=slug)
        except (StudentInfrastructureUnavailable, StudentNotFound, StudentSiteUnavailable) as exc:
            return _student_service_error(exc)
        return Response(profile)

    @extend_schema(
        operation_id="admin_student_update",
        tags=["Quản lý học viên"],
        summary="Cập nhật hồ sơ học viên tại một cơ sở",
        description=(
            "Cập nhật danh tính/liên hệ LOCAL trong một transaction và ghi Logs append-only. "
            "Không cho sửa site, trạng thái, slug hoặc mã học viên; khi đã cấp tài khoản thì không đổi email."
        ),
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH),
                    OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        request=StudentUpdateSerializer,
        responses={
            200: StudentAdminProfileSerializer,
            400: OpenApiResponse(description="Site hoặc dữ liệu hồ sơ không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên đã hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big/Admin Small đúng phạm vi được sửa hồ sơ."),
            404: OpenApiResponse(description="Không tìm thấy hồ sơ học viên."),
            409: OpenApiResponse(description="Hồ sơ đang bị khóa bởi giao dịch chuyển hoặc tài khoản."),
            503: OpenApiResponse(description="Site/CSDL chưa sẵn sàng."),
        },
    )
    def patch(self, request, slug: str):
        site_code, error = _resolve_request_admin_site(request)
        if error:
            return error
        serializer = StudentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            profile = update_student_profile(
                site_code=site_code,
                student_slug=slug,
                fields=serializer.validated_data,
                actor_id=request.user.account_id,
                remote_ip=_remote_ip(request),
            )
        except (StudentConflict, StudentInfrastructureUnavailable, StudentNotFound, StudentSiteUnavailable) as exc:
            return _student_service_error(exc)
        return Response(profile)

    @extend_schema(
        operation_id="admin_student_delete",
        tags=["Quản lý học viên"],
        summary="Xóa hồ sơ học viên chưa phát sinh dữ liệu nghiệp vụ",
        description=(
            "Xóa LOCAL trong một transaction chỉ khi hồ sơ chưa có tài khoản, đăng ký hoặc lịch sử chuyển cơ sở. "
            "Nếu đã phát sinh nghiệp vụ, trả 409 và giữ toàn bộ lịch sử; không xóa phiếu thu, điểm, điểm danh, "
            "giao dịch hoặc Logs. Admin Big chọn site_code; Admin Small dùng site trong phiên."
        ),
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH),
                    OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        request=EmptyRequestSerializer,
        responses={
            200: StudentDeleteResponseSerializer,
            400: OpenApiResponse(description="Admin Big chưa chọn site_code hoặc site không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên đã hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big/Admin Small đúng phạm vi được xóa hồ sơ."),
            404: OpenApiResponse(description="Không tìm thấy hồ sơ học viên."),
            409: OpenApiResponse(description="Hồ sơ có tài khoản, đăng ký hoặc lịch sử cần được giữ."),
            429: OpenApiResponse(description="Vượt giới hạn thao tác quản lý học viên."),
            503: OpenApiResponse(description="Site/CSDL chưa sẵn sàng."),
        },
    )
    def delete(self, request, slug: str):
        site_code, error = _resolve_request_admin_site(request)
        if error:
            return error
        try:
            result = delete_student_profile(
                site_code=site_code,
                student_slug=slug,
                actor_id=request.user.account_id,
                remote_ip=_remote_ip(request),
            )
        except (StudentConflict, StudentInfrastructureUnavailable, StudentNotFound, StudentSiteUnavailable) as exc:
            return _student_delete_error(exc)
        return Response(result)


@method_decorator(csrf_protect, name="dispatch")
class StudentAvatarUploadIntentView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "profile_avatar"

    @extend_schema(
        operation_id="admin_student_avatar_upload_intent",
        tags=["Quản lý học viên"],
        summary="Cấp chữ ký tải ảnh hồ sơ học viên lên Cloudinary",
        description=(
            "Chỉ Admin Big/Admin Small đúng site. API tạo upload intent gắn với actor, site, slug và hồ sơ hiện tại; "
            "ảnh được tải thẳng lên Cloudinary. Không nhận URL tùy ý hoặc để trình duyệt gửi API secret. "
            "Bước hoàn tất chỉ cập nhật metadata tại HocVien của site này (`LOCAL`)."
        ),
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH),
                    OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        request=EmptyRequestSerializer,
        responses={
            200: AdminAvatarUploadIntentResponseSerializer,
            400: OpenApiResponse(description="Site chưa chọn hoặc không hoạt động."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên đã hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big/Admin Small đúng site được tải ảnh."),
            404: OpenApiResponse(description="Không tìm thấy hồ sơ học viên."),
            409: OpenApiResponse(description="Hồ sơ đã chuyển hoặc metadata ảnh chưa nhất quán."),
            429: OpenApiResponse(description="Vượt giới hạn cấp chữ ký."),
            503: OpenApiResponse(description="Site, Cloudinary hoặc SQL Server chưa sẵn sàng."),
        },
    )
    def post(self, request, slug: str):
        site_code, error = _resolve_request_admin_site(request)
        if error:
            return error
        serializer = EmptyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            intent = create_student_avatar_upload_intent(request.user, site_code, slug)
        except (AvatarConflict, AvatarUnavailable, StudentConflict, StudentInfrastructureUnavailable,
                StudentNotFound, StudentSiteUnavailable) as exc:
            return _student_avatar_error(exc)
        return Response(intent)


@method_decorator(csrf_protect, name="dispatch")
class StudentAvatarCompleteView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "profile_avatar"

    @extend_schema(
        operation_id="admin_student_avatar_complete",
        tags=["Quản lý học viên"],
        summary="Xác minh ảnh Cloudinary và lưu metadata hồ sơ học viên",
        description=(
            "Xác minh intent, chữ ký tài nguyên, loại ảnh, dung lượng và kích thước qua Cloudinary. "
            "Ghi avatar_public_id/avatar_secure_url và Logs append-only trong transaction tại site hồ sơ (`LOCAL`); "
            "không tạo TaiKhoan hoặc nhân bản dữ liệu học viên."
        ),
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH),
                    OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        request=AdminAvatarFinalizeRequestSerializer,
        responses={
            200: StudentAvatarResponseSerializer,
            400: OpenApiResponse(description="Ảnh hoặc upload intent không hợp lệ/hết hạn."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên đã hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big/Admin Small đúng site được lưu ảnh."),
            404: OpenApiResponse(description="Không tìm thấy hồ sơ học viên."),
            409: OpenApiResponse(description="Hồ sơ đã chuyển hoặc metadata ảnh bị xung đột."),
            429: OpenApiResponse(description="Vượt giới hạn hoàn tất upload."),
            503: OpenApiResponse(description="Cloudinary/site chưa sẵn sàng; có thể gửi lại cùng yêu cầu."),
        },
    )
    def post(self, request, slug: str):
        site_code, error = _resolve_request_admin_site(request)
        if error:
            return error
        serializer = AdminAvatarFinalizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = complete_student_avatar_upload(
                request.user,
                site_code,
                slug,
                serializer.validated_data["intent_token"],
                serializer.validated_data["public_id"],
                _remote_ip(request),
            )
        except (AvatarConflict, AvatarInvalidIntent, AvatarInvalidUpload, AvatarUnavailable,
                StudentConflict, StudentInfrastructureUnavailable, StudentNotFound,
                StudentSiteUnavailable) as exc:
            return _student_avatar_error(exc)
        return Response(result)


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
