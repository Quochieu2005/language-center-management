"""Role-aware login, session inspection, inactivity refresh, and logout."""

from datetime import timezone as datetime_timezone
from django.conf import settings
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth.authentication import AuthCookieAuthentication, AuthenticationUnavailable
from core.auth.serializers import (
    AdminForgotPasswordSerializer,
    AdminResetPasswordSerializer,
    AuthLoginResponseSerializer,
    AuthLoginSerializer,
    AuthMeResponseSerializer,
    CsrfTokenResponseSerializer,
    EmptyRequestSerializer,
    GenericPasswordResetResponseSerializer,
    PasswordResetCompleteResponseSerializer,
)
from core.auth.services import (
    AuthInfrastructureUnavailable,
    LoginRateLimitExceeded,
    PasswordResetRateLimitExceeded,
    extend_user_session,
    login_user,
    request_admin_password_reset,
    reset_admin_password,
    revoke_user_session,
    session_token_digest,
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


class AuthMeView(APIView):
    authentication_classes = [AuthCookieAuthentication]

    @extend_schema(
        operation_id="auth_me",
        tags=["Xác thực"],
        summary="Lấy tài khoản và vai trò của phiên hiện tại",
        responses={200: AuthMeResponseSerializer},
    )
    def get(self, request):
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
        responses={200: AuthMeResponseSerializer},
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
