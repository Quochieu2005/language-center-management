"""Role-aware login, session inspection, inactivity refresh, and logout."""

from datetime import timezone as datetime_timezone
from django.conf import settings
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.auth.authentication import AuthCookieAuthentication, AuthenticationUnavailable
from core.auth.admin_small_accounts import list_admin_small_accounts
from core.auth.account_status import (
    AccountStatusConflict,
    AccountStatusTargetNotFound,
    change_account_status,
)
from core.auth.admin_big_profile import (
    AdminBigProfileConflict,
    AdminBigProfileNotFound,
    AdminBigProfilePasswordInvalid,
    get_admin_big_self_profile,
    update_admin_big_self_profile,
)
from core.auth.serializers import (
    AdminForgotPasswordSerializer,
    AdminBigSelfProfileResponseSerializer,
    AdminBigSelfProfileUpdateSerializer,
    AccountStatusResponseSerializer,
    AccountStatusUpdateSerializer,
    AdminSmallListQuerySerializer,
    AdminSmallListResponseSerializer,
    AdminSmallCreateResponseSerializer,
    AdminSmallCreateSerializer,
    AdminSmallDeleteResponseSerializer,
    AdminSmallSelfProfileResponseSerializer,
    AdminSmallSelfProfileUpdateSerializer,
    AuthChangePasswordSerializer,
    AuthPasswordChangeResponseSerializer,
    AdminResetPasswordSerializer,
    AuthLoginResponseSerializer,
    AuthLoginSerializer,
    AuthProfileResponseSerializer,
    CsrfTokenResponseSerializer,
    EmptyRequestSerializer,
    GenericPasswordResetResponseSerializer,
    PasswordResetCompleteResponseSerializer,
)
from core.auth.services import (
    AuthInfrastructureUnavailable,
    AdminSmallAccountConflict,
    AdminSmallDeleteConflict,
    AdminSmallProfileNotFound,
    AdminSmallSiteUnavailable,
    AdminSmallTargetNotFound,
    LoginRateLimitExceeded,
    PasswordResetRateLimitExceeded,
    change_authenticated_password,
    create_admin_small,
    delete_admin_small,
    extend_user_session,
    login_user,
    request_admin_password_reset,
    reset_admin_password,
    revoke_user_session,
    session_token_digest,
    get_admin_small_self_profile,
    update_admin_small_self_profile,
)


def _serialized_user(user):
    return {
        "account_id": user.account_id,
        "slug": user.slug,
        "email": user.email,
        "username": user.username,
        "role": user.role,
        "site_code": user.site_code,
        "profile_id": user.profile_id,
        "must_change_password": user.must_change_password,
    }


def _utc_datetime(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime_timezone.utc)
    return value.astimezone(datetime_timezone.utc)


def _set_auth_cookie(response, token):
    response.set_cookie(
        settings.AUTH_COOKIE_NAME,
        token,
        max_age=settings.AUTH_IDLE_TIMEOUT_SECONDS,
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfTokenView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="auth_csrf_token",
        tags=["Xác thực"],
        summary="Lấy CSRF token trước khi đăng nhập hoặc gửi yêu cầu thay đổi dữ liệu",
        responses={200: CsrfTokenResponseSerializer},
    )
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class AuthLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="auth_login",
        tags=["Xác thực"],
        summary="Đăng nhập theo vai trò đã cấp",
        description=(
            "Xác minh tài khoản đã được cấp trong TaiKhoan và tự xác định vai trò từ hồ sơ "
            "NhanVien hoặc GiaoVien tại cơ sở tương ứng. Hỗ trợ Admin Big, Admin Small, lễ tân, "
            "kế toán và giáo viên; không nhận vai trò hoặc cơ sở từ client. "
            "Phiên được lưu tại site cấu hình AUTH_SESSION_SITE_CODE, gửi qua cookie HttpOnly "
            "và hết hạn sau 3600 giây không có hoạt động. Gọi GET /auth/csrf/ trước và gửi "
            "csrf_token trong header X-CSRFToken."
        ),
        request=AuthLoginSerializer,
        responses={
            200: AuthLoginResponseSerializer,
            400: OpenApiResponse(description="Dữ liệu đăng nhập không hợp lệ."),
            401: OpenApiResponse(description="Thông tin đăng nhập không hợp lệ hoặc hồ sơ không hoạt động."),
            429: OpenApiResponse(description="Đã vượt giới hạn đăng nhập; phản hồi có Retry-After."),
            503: OpenApiResponse(description="Không xác minh được site hoặc kho phiên đăng nhập."),
        },
    )
    def post(self, request):
        serializer = AuthLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        remote_ip = request.META.get("REMOTE_ADDR", "")
        try:
            result = login_user(
                serializer.validated_data["identifier"],
                serializer.validated_data["password"],
                remote_ip or "unknown",
            )
        except LoginRateLimitExceeded as exc:
            response = Response(
                {"detail": "Đã vượt số lần đăng nhập cho phép. Vui lòng thử lại sau."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            response["Retry-After"] = str(exc.retry_after)
            return response
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc

        if result is None:
            return Response(
                {"detail": "Thông tin đăng nhập không hợp lệ hoặc hồ sơ không hoạt động."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user, token, _expires_at = result
        response = Response(
            {
                "user": _serialized_user(user),
                "idle_timeout_seconds": settings.AUTH_IDLE_TIMEOUT_SECONDS,
            },
            status=status.HTTP_200_OK,
        )
        _set_auth_cookie(response, token)
        return response


@method_decorator(csrf_protect, name="dispatch")
class AuthChangePasswordView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="auth_password_change",
        tags=["Xác thực"],
        summary="Đổi mật khẩu hiện tại hoặc mật khẩu tạm được cấp",
        description=(
            "Yêu cầu mật khẩu hiện tại và mật khẩu mới tối thiểu 12 ký tự. "
            "Mật khẩu mới được băm BCrypt và đồng bộ tới mọi site đang hoạt động; "
            "các phiên cũ bị thu hồi. Tài khoản có cờ bắt buộc đổi mật khẩu chỉ được "
            "xem hồ sơ qua /auth/profile/{slug}/, đổi mật khẩu hoặc đăng xuất."
        ),
        request=AuthChangePasswordSerializer,
        responses={
            200: AuthPasswordChangeResponseSerializer,
            400: OpenApiResponse(description="Mật khẩu hiện tại sai hoặc mật khẩu mới không hợp lệ."),
            401: OpenApiResponse(description="Phiên không hợp lệ hoặc đã hết hạn."),
            503: OpenApiResponse(description="Không thể cập nhật mật khẩu đầy đủ trên các site."),
        },
    )
    def post(self, request):
        serializer = AuthChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            changed = change_authenticated_password(
                request.user,
                serializer.validated_data["current_password"],
                serializer.validated_data["new_password"],
            )
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc

        if not changed:
            return Response(
                {"detail": "Mật khẩu hiện tại không đúng hoặc tài khoản đã thay đổi."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = Response(
            {"detail": "Đã đổi mật khẩu. Vui lòng đăng nhập lại bằng mật khẩu mới."},
            status=status.HTTP_200_OK,
        )
        response.delete_cookie(
            settings.AUTH_COOKIE_NAME,
            path="/",
            samesite=settings.SESSION_COOKIE_SAMESITE,
        )
        return response


class AdminSmallCreateView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "admin_account_create"

    def get_throttles(self):
        self.throttle_scope = "admin_account_read" if self.request.method == "GET" else "admin_account_create"
        return super().get_throttles()

    @extend_schema(
        operation_id="admin_small_list",
        tags=["Quản lý tài khoản"],
        summary="Admin Big xem Admin Small theo cơ sở",
        description=(
            "Chỉ Admin Big. Mặc định truy vấn Global Query trên tất cả site đang hoạt động; dữ liệu "
            "NhanVien được đọc tại từng CSDL site rồi gộp ở API, không JOIN xuyên site. Nếu site bắt "
            "buộc lỗi thì API trả 503, không trả danh sách thiếu như thể đầy đủ. Danh sách gồm slug và "
            "trạng thái để Admin Big có thể bật/tắt đúng tài khoản."
        ),
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY),
            OpenApiParameter("offset", int, OpenApiParameter.QUERY),
        ],
        responses={
            200: AdminSmallListResponseSerializer,
            400: OpenApiResponse(description="Tham số phân trang hoặc site không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập."),
            403: OpenApiResponse(description="Chỉ Admin Big được xem danh sách Admin Small."),
            503: OpenApiResponse(description="Site/CSDL chưa sẵn sàng; danh sách chưa đầy đủ."),
        },
    )
    def get(self, request):
        if request.user.role != "admin_big":
            return Response(
                {"detail": "Chỉ Admin Big được xem danh sách Admin Small."},
                status=status.HTTP_403_FORBIDDEN,
            )
        query = AdminSmallListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            result = list_admin_small_accounts(**query.validated_data)
        except ValueError:
            return Response({"detail": "Cơ sở được chọn không hoạt động."}, status=status.HTTP_400_BAD_REQUEST)
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc
        return Response(result, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="admin_small_create",
        tags=["Quản lý tài khoản"],
        summary="Admin Big tạo Admin Small cho một cơ sở",
        description=(
            "Chỉ Admin Big được gọi. API tạo tài khoản nhan_vien với hồ sơ NhanVien có "
            "chuc_vu=quan_ly_co_so tại cơ sở được chọn; vai trò hiệu lực là admin_small. "
            "TaiKhoan được nhân bản tới mọi site đang hoạt động; hồ sơ nhân viên chỉ nằm "
            "ở site được giao. API gửi mật khẩu tạm từ ADMIN_SMALL_TEMP_PASSWORD qua SMTP, "
            "bắt buộc đổi mật khẩu sau đăng nhập đầu tiên và không trả mật khẩu trong response. "
            "Giới hạn 10 yêu cầu mỗi giờ cho một tài khoản Admin Big."
        ),
        request=AdminSmallCreateSerializer,
        responses={
            201: AdminSmallCreateResponseSerializer,
            400: OpenApiResponse(description="Dữ liệu không hợp lệ hoặc site không hoạt động."),
            401: OpenApiResponse(description="Chưa đăng nhập."),
            403: OpenApiResponse(description="Chỉ Admin Big được tạo Admin Small."),
            409: OpenApiResponse(description="Email hoặc tên đăng nhập đã được sử dụng."),
            429: OpenApiResponse(description="Đã vượt giới hạn tạo tài khoản."),
            503: OpenApiResponse(description="Site, SQL Server hoặc SMTP chưa sẵn sàng."),
        },
    )
    def post(self, request):
        if request.user.role != "admin_big":
            return Response(
                {"detail": "Chỉ Admin Big được tạo Admin Small."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = AdminSmallCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result, email_sent = create_admin_small(
                email=serializer.validated_data["email"],
                full_name=serializer.validated_data["full_name"],
                site_code=serializer.validated_data["site_code"],
                username=serializer.validated_data.get("username"),
                admin_big_id=request.user.account_id,
                remote_ip=request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except AdminSmallAccountConflict:
            return Response(
                {"detail": "Email hoặc tên đăng nhập đã được sử dụng."},
                status=status.HTTP_409_CONFLICT,
            )
        except AdminSmallSiteUnavailable:
            return Response(
                {"detail": "Cơ sở không tồn tại hoặc đang không hoạt động."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc

        return Response(
            {
                "account_id": result.account_id,
                "employee_id": result.employee_id,
                "username": result.username,
                "email": result.email,
                "site_code": result.site_code,
                "slug": result.slug,
                "role": "admin_small",
                "account_status": "active",
                "must_change_password": result.must_change_password,
                "email_sent": email_sent,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name="dispatch")
class AdminSmallSelfProfileView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "admin_small_self_profile"

    @extend_schema(
        operation_id="admin_small_profile_read",
        tags=["Quản lý tài khoản"],
        summary="Admin Small xem hồ sơ qua slug của chính mình",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        responses={
            200: AdminSmallSelfProfileResponseSerializer,
            401: OpenApiResponse(description="Chưa đăng nhập."),
            403: OpenApiResponse(description="Chỉ Admin Small được truy cập hồ sơ này."),
            503: OpenApiResponse(description="Cơ sở chưa sẵn sàng."),
        },
    )
    def get(self, request, slug: str):
        if request.user.role != "admin_small":
            return Response(
                {"detail": "Chỉ Admin Small được truy cập hồ sơ cá nhân này."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if slug != request.user.slug:
            return Response({"detail": "Không tìm thấy hồ sơ Admin Small."}, status=404)
        try:
            profile = get_admin_small_self_profile(request.user, slug)
        except AdminSmallProfileNotFound:
            return Response({"detail": "Không tìm thấy hồ sơ Admin Small đang hoạt động."}, status=404)
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc
        return Response(profile, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="admin_small_profile_update",
        tags=["Quản lý tài khoản"],
        summary="Admin Small chỉnh sửa hồ sơ qua slug của chính mình",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        description=(
            "Chỉ cho phép sửa họ tên và số điện thoại của hồ sơ NhanVien gắn với phiên đăng nhập. "
            "Không nhận mã tài khoản/hồ sơ, vai trò, cơ sở, email hoặc tên đăng nhập từ client. "
            "Admin Big và các vai trò khác không được dùng endpoint này để sửa Admin Small."
        ),
        request=AdminSmallSelfProfileUpdateSerializer,
        responses={
            200: AdminSmallSelfProfileResponseSerializer,
            400: OpenApiResponse(description="Dữ liệu hồ sơ không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập."),
            403: OpenApiResponse(description="Chỉ Admin Small được tự sửa hồ sơ."),
            404: OpenApiResponse(description="Không tìm thấy hồ sơ Admin Small."),
            429: OpenApiResponse(description="Vượt giới hạn yêu cầu."),
            503: OpenApiResponse(description="Cơ sở chưa sẵn sàng."),
        },
    )
    def patch(self, request, slug: str):
        if request.user.role != "admin_small":
            return Response(
                {"detail": "Chỉ Admin Small được tự sửa hồ sơ."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if slug != request.user.slug:
            return Response({"detail": "Không tìm thấy hồ sơ Admin Small."}, status=404)
        serializer = AdminSmallSelfProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            profile = update_admin_small_self_profile(
                request.user,
                slug,
                serializer.validated_data,
                request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except AdminSmallProfileNotFound:
            return Response({"detail": "Không tìm thấy hồ sơ Admin Small đang hoạt động."}, status=404)
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc
        return Response(profile, status=status.HTTP_200_OK)


@method_decorator(csrf_protect, name="dispatch")
class AdminBigSelfProfileView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "admin_big_self_profile"

    @extend_schema(
        operation_id="admin_big_profile_read",
        tags=["Quản lý tài khoản"],
        summary="Admin Big xem tài khoản qua slug của chính mình",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        responses={
            200: AdminBigSelfProfileResponseSerializer,
            401: OpenApiResponse(description="Chưa đăng nhập."),
            403: OpenApiResponse(description="Chỉ Admin Big được xem thông tin này."),
            503: OpenApiResponse(description="Một hoặc nhiều cơ sở chưa sẵn sàng."),
        },
    )
    def get(self, request, slug: str):
        if request.user.role != "admin_big":
            return Response(
                {"detail": "Chỉ Admin Big được xem tài khoản cá nhân này."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if slug != request.user.slug:
            return Response({"detail": "Không tìm thấy tài khoản Admin Big."}, status=404)
        try:
            profile = get_admin_big_self_profile(request.user, slug)
        except AdminBigProfileNotFound:
            return Response({"detail": "Không tìm thấy tài khoản Admin Big đang hoạt động."}, status=404)
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc
        return Response(profile, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="admin_big_profile_update",
        tags=["Quản lý tài khoản"],
        summary="Admin Big cập nhật tài khoản qua slug của chính mình",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        description=(
            "Chỉ cho phép cập nhật username, email và slug của tài khoản gắn với phiên hiện tại; "
            "bắt buộc xác nhận mật khẩu hiện tại. Không nhận account_id, role hoặc site từ client, "
            "nên không thể dùng API này để sửa Admin Small. Các trường TaiKhoan được đồng bộ tới "
            "mọi site đang hoạt động; nếu một site lỗi, tiến trình được lưu để lần gọi sau tiếp tục."
        ),
        request=AdminBigSelfProfileUpdateSerializer,
        responses={
            200: AdminBigSelfProfileResponseSerializer,
            400: OpenApiResponse(description="Dữ liệu cập nhật không hợp lệ hoặc mật khẩu hiện tại sai."),
            401: OpenApiResponse(description="Phiên đăng nhập không hợp lệ hoặc đã hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big được cập nhật tài khoản này."),
            404: OpenApiResponse(description="Không tìm thấy tài khoản Admin Big."),
            409: OpenApiResponse(description="Username, email hoặc slug đã được sử dụng; hoặc có xung đột cần đối soát."),
            429: OpenApiResponse(description="Vượt giới hạn yêu cầu cập nhật."),
            503: OpenApiResponse(description="Đồng bộ một hoặc nhiều CSDL site chưa hoàn tất; có thể gọi lại để tiếp tục."),
        },
    )
    def patch(self, request, slug: str):
        if request.user.role != "admin_big":
            return Response(
                {"detail": "Chỉ Admin Big được cập nhật tài khoản cá nhân này."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if slug != request.user.slug:
            return Response({"detail": "Không tìm thấy tài khoản Admin Big."}, status=404)
        serializer = AdminBigSelfProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = dict(serializer.validated_data)
        current_password = payload.pop("current_password")
        try:
            profile = update_admin_big_self_profile(
                request.user,
                slug,
                payload,
                current_password,
                request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except AdminBigProfilePasswordInvalid:
            return Response(
                {"detail": "Mật khẩu hiện tại không đúng."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except AdminBigProfileConflict:
            return Response(
                {"detail": "Username, email hoặc slug đã được sử dụng hoặc đang có thay đổi cần đối soát."},
                status=status.HTTP_409_CONFLICT,
            )
        except AdminBigProfileNotFound:
            return Response({"detail": "Không tìm thấy tài khoản Admin Big đang hoạt động."}, status=404)
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc
        return Response(profile, status=status.HTTP_200_OK)


@method_decorator(csrf_protect, name="dispatch")
class AdminSmallDeleteView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "admin_small_delete"

    @extend_schema(
        operation_id="admin_small_deactivate",
        tags=["Quản lý tài khoản"],
        summary="Admin Big vô hiệu hóa Admin Small",
        description=(
            "Chỉ Admin Big được gọi. Đây là xóa mềm: TaiKhoan được chuyển sang vo_hieu và tăng phien_ban "
            "trên các site đã ghi nhận; hồ sơ NhanVien ở site của tài khoản chuyển sang nghi_viec. Phiên cũ bị thu hồi, "
            "nhật ký và dữ liệu lịch sử được giữ. Coordinator lưu tiến trình và retry tiến về phía trước nếu site lỗi; "
            "không tuyên bố giao dịch ACID nguyên tử xuyên CSDL. Admin Small không thể xóa ai, kể cả chính mình."
        ),
        responses={
            200: AdminSmallDeleteResponseSerializer,
            401: OpenApiResponse(description="Chưa đăng nhập."),
            403: OpenApiResponse(description="Chỉ Admin Big được vô hiệu hóa Admin Small."),
            404: OpenApiResponse(description="Không tìm thấy tài khoản Admin Small."),
            409: OpenApiResponse(description="Tài khoản có trạng thái không thể vô hiệu hóa."),
            429: OpenApiResponse(description="Vượt giới hạn yêu cầu."),
            503: OpenApiResponse(description="Site/Coordinator chưa sẵn sàng; lần gọi sau sẽ tiếp tục phục hồi."),
        },
    )
    def delete(self, request, account_id: str):
        if request.user.role != "admin_big":
            return Response(
                {"detail": "Chỉ Admin Big được vô hiệu hóa Admin Small."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            result = delete_admin_small(
                account_id,
                request.user.account_id,
                request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except AdminSmallTargetNotFound:
            return Response({"detail": "Không tìm thấy tài khoản Admin Small."}, status=404)
        except AdminSmallDeleteConflict:
            return Response(
                {"detail": "Tài khoản Admin Small đang ở trạng thái xung đột; cần kiểm tra hoặc tiếp tục phục hồi."},
                status=status.HTTP_409_CONFLICT,
            )
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc
        return Response(
            {
                "account_id": result.account_id,
                "site_code": result.site_code,
                "role": "admin_small",
                "status": result.status,
                "detail": "Tài khoản đã được vô hiệu hóa; hồ sơ và lịch sử vẫn được lưu giữ.",
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_protect, name="dispatch")
class AdminSmallStatusView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "admin_small_delete"

    @extend_schema(
        operation_id="admin_small_account_status_update",
        tags=["Quản lý tài khoản"],
        summary="Admin Big bật hoặc tắt tài khoản Admin Small theo slug",
        description=(
            "Chỉ Admin Big được đổi trạng thái. TaiKhoan được cập nhật tới tất cả site đang hoạt động qua "
            "Coordinator; phiên bản tăng để thu hồi phiên cũ. Tiến trình có thể retry nếu site tạm lỗi. "
            "Đây là bật/tắt quyền đăng nhập, không sửa hồ sơ Admin Small."
        ),
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        request=AccountStatusUpdateSerializer,
        responses={
            200: AccountStatusResponseSerializer,
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big được bật/tắt Admin Small."),
            404: OpenApiResponse(description="Không tìm thấy Admin Small."),
            409: OpenApiResponse(description="Hồ sơ đã nghỉ việc hoặc trạng thái thay đổi đồng thời."),
            429: OpenApiResponse(description="Vượt giới hạn yêu cầu."),
            503: OpenApiResponse(description="Đồng bộ site chưa hoàn tất; có thể gọi lại để tiếp tục."),
        },
    )
    def patch(self, request, slug: str):
        if request.user.role != "admin_big":
            return Response(
                {"detail": "Chỉ Admin Big được bật/tắt tài khoản Admin Small."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = AccountStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = change_account_status(
                slug=slug,
                expected_role="admin_small",
                desired_status=serializer.validated_data["status"],
                actor_id=request.user.account_id,
                remote_ip=request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except AccountStatusTargetNotFound:
            return Response({"detail": "Không tìm thấy Admin Small."}, status=status.HTTP_404_NOT_FOUND)
        except AccountStatusConflict:
            return Response(
                {"detail": "Hồ sơ Admin Small đã nghỉ việc hoặc trạng thái đang được thay đổi."},
                status=status.HTTP_409_CONFLICT,
            )
        except AuthInfrastructureUnavailable:
            return Response(
                {"detail": "Đồng bộ site chưa hoàn tất; thao tác có thể gọi lại để tiếp tục."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {
                "account_id": result.account_id,
                "slug": result.slug,
                "role": result.role,
                "site_code": result.site_code,
                "status": result.status,
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_protect, name="dispatch")
class AdminForgotPasswordView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="admin_password_reset_request",
        tags=["Xác thực"],
        summary="Gửi OTP đặt lại mật khẩu quản trị",
        description=(
            "Chỉ gửi mã tới email đã đăng ký của Admin Big hoặc Admin Small. OTP 6 chữ số "
            "được lưu dưới dạng HMAC, hết hạn sau 120 giây, chỉ dùng một lần; endpoint luôn "
            "trả cùng nội dung để không tiết lộ email có tồn tại hay không. Giới hạn tối đa "
            "10 yêu cầu/IP/giờ, 3 yêu cầu/email/giờ và 1 lần mỗi 60 giây cho cùng email/IP."
        ),
        request=AdminForgotPasswordSerializer,
        responses={
            202: GenericPasswordResetResponseSerializer,
            400: OpenApiResponse(description="Email không hợp lệ."),
            503: OpenApiResponse(description="Kho xác thực hoặc một site đang hoạt động không sẵn sàng."),
        },
    )
    def post(self, request):
        serializer = AdminForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            request_admin_password_reset(
                serializer.validated_data["email"],
                request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc
        return Response(
            {
                "detail": (
                    "Nếu email thuộc tài khoản quản trị hợp lệ, mã OTP sẽ được gửi. "
                    "Mã có hiệu lực trong 2 phút."
                )
            },
            status=status.HTTP_202_ACCEPTED,
        )


@method_decorator(csrf_protect, name="dispatch")
class AdminResetPasswordView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="admin_password_reset_confirm",
        tags=["Xác thực"],
        summary="Xác nhận OTP và đặt mật khẩu quản trị mới",
        description=(
            "Yêu cầu OTP còn hạn, chưa dùng và chưa vượt 5 lần nhập sai. Mật khẩu mới tối thiểu "
            "12 ký tự, được băm BCrypt-SHA256. Sau khi xác nhận, phiên cũ bị vô hiệu hóa và "
            "Coordinator cập nhật các bản sao TaiKhoan ở mọi site đang hoạt động theo cơ chế "
            "retry tiến về phía trước; không tuyên bố ACID nguyên tử xuyên CSDL."
        ),
        request=AdminResetPasswordSerializer,
        responses={
            200: PasswordResetCompleteResponseSerializer,
            400: OpenApiResponse(description="OTP không đúng, hết hạn, đã dùng hoặc dữ liệu mật khẩu không hợp lệ."),
            429: OpenApiResponse(description="Đã vượt giới hạn thử OTP; phản hồi có Retry-After."),
            503: OpenApiResponse(description="Chưa xác nhận được việc cập nhật mật khẩu trên các site."),
        },
    )
    def post(self, request):
        serializer = AdminResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reset = reset_admin_password(
                serializer.validated_data["email"],
                serializer.validated_data["otp"],
                serializer.validated_data["new_password"],
                request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except PasswordResetRateLimitExceeded as exc:
            response = Response(
                {"detail": "Đã vượt số lần thử mã OTP. Vui lòng thử lại sau."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            response["Retry-After"] = str(exc.retry_after)
            return response
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc

        if not reset:
            return Response(
                {"detail": "OTP không hợp lệ, đã hết hạn hoặc không thể sử dụng."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"detail": "Đã cập nhật mật khẩu. Vui lòng đăng nhập lại bằng mật khẩu mới."},
            status=status.HTTP_200_OK,
        )


class AuthProfileView(APIView):
    authentication_classes = [AuthCookieAuthentication]

    @extend_schema(
        operation_id="auth_profile_read",
        tags=["Xác thực"],
        summary="Lấy tài khoản và vai trò phiên hiện tại theo slug",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        responses={
            200: AuthProfileResponseSerializer,
            404: OpenApiResponse(description="Slug không thuộc tài khoản đang đăng nhập."),
        },
    )
    def get(self, request, slug: str):
        if slug != request.user.slug:
            return Response({"detail": "Không tìm thấy hồ sơ tài khoản."}, status=status.HTTP_404_NOT_FOUND)
        session = request.auth
        return Response(
            {
                "user": _serialized_user(request.user),
                "expires_at": _utc_datetime(session.expires_at),
            }
        )


class AuthActivityView(APIView):
    authentication_classes = [AuthCookieAuthentication]

    @extend_schema(
        operation_id="auth_session_activity",
        tags=["Xác thực"],
        summary="Gia hạn phiên sau thao tác thật của người dùng",
        description=(
            "Frontend chỉ gọi endpoint này sau thao tác bàn phím, chuột hoặc chạm của người dùng; "
            "không gọi bằng polling nền. Mỗi lần gia hạn đặt hạn phiên thành 3600 giây kể từ hiện tại."
        ),
        request=EmptyRequestSerializer,
        responses={200: AuthProfileResponseSerializer},
    )
    def post(self, request):
        try:
            expires_at = extend_user_session(request.auth.token_digest)
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc
        if expires_at is None:
            return Response(
                {"detail": "Phiên đăng nhập không hợp lệ hoặc đã hết hạn."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        response = Response(
            {
                "user": _serialized_user(request.user),
                "expires_at": _utc_datetime(expires_at),
            }
        )
        token = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
        if token:
            _set_auth_cookie(response, token)
        return response


class AuthLogoutView(APIView):
    authentication_classes = [AuthCookieAuthentication]

    @extend_schema(
        operation_id="auth_logout",
        tags=["Xác thực"],
        summary="Thu hồi phiên hiện tại",
        request=EmptyRequestSerializer,
        responses={204: OpenApiResponse(description="Đã thu hồi phiên đăng nhập.")},
    )
    def post(self, request):
        try:
            revoke_user_session(request.auth.token_digest)
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(
            settings.AUTH_COOKIE_NAME,
            path="/",
            samesite=settings.SESSION_COOKIE_SAMESITE,
        )
        return response
