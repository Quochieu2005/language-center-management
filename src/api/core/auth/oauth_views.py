"""Student-only Google/Facebook login and account linking endpoints."""

from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseRedirect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.auth.authentication import AuthCookieAuthentication, AuthenticationUnavailable
from core.auth.oauth_services import (
    OAUTH_STATE_COOKIE_AGE,
    PROVIDER_COLUMNS,
    OAuthAccountConflict,
    OAuthNotConfigured,
    OAuthProviderError,
    OAuthStateInvalid,
    consume_oauth_state_once,
    create_oauth_flow,
    exchange_oauth_code,
    get_oauth_connections,
    link_oauth_provider,
    login_with_oauth_provider,
    oauth_state_cookie_name,
    read_oauth_flow,
)
from core.auth.service_common import AuthInfrastructureUnavailable, LoginRateLimitExceeded
from core.auth.views import _serialized_user


def _frontend_origin() -> str:
    raw = settings.OAUTH_WEB_RETURN_URL or settings.WEB_APP_BASE_URL
    parsed = urlsplit(raw)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.netloc
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
        or (not settings.DEBUG and parsed.scheme != "https")
    ):
        raise ImproperlyConfigured("OAUTH_WEB_RETURN_URL phải là một origin frontend hợp lệ.")
    return f"{parsed.scheme}://{parsed.netloc}"


def _return_response(result: str, intent: str, provider: str):
    page = "student" if intent == "link" and result != "session_expired" else "login"
    response = HttpResponseRedirect(f"{_frontend_origin()}/{page}?oauth={result}&provider={provider}")
    response.delete_cookie(
        oauth_state_cookie_name(provider),
        path="/api/v1/auth/oauth/",
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


def _set_oauth_state_cookie(response, provider: str, value: str):
    response.set_cookie(
        oauth_state_cookie_name(provider),
        value,
        max_age=OAUTH_STATE_COOKIE_AGE,
        path="/api/v1/auth/oauth/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )


def _set_auth_cookie(response, token: str):
    response.set_cookie(
        settings.AUTH_COOKIE_NAME,
        token,
        max_age=settings.AUTH_IDLE_TIMEOUT_SECONDS,
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )


class OAuthStartView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]

    def get_throttles(self):
        self.throttle_scope = "oauth_start"
        return super().get_throttles()

    def get_authenticators(self):
        if self.request.method == "GET":
            return []
        return super().get_authenticators()

    @extend_schema(
        operation_id="auth_student_oauth_login_start",
        tags=["Xác thực"],
        summary="Bắt đầu đăng nhập học viên bằng Google hoặc Facebook",
        description=(
            "Chỉ đăng nhập học viên đã liên kết danh tính xã hội trước đó. Tài khoản nhân viên, "
            "Admin và học viên chưa liên kết không được tự tạo hoặc tự ghép tài khoản."
        ),
        parameters=[OpenApiParameter("provider", str, OpenApiParameter.PATH)],
        responses={302: OpenApiResponse(description="Chuyển hướng tới nhà cung cấp OAuth.")},
    )
    def get(self, request, provider: str):
        if provider not in PROVIDER_COLUMNS:
            return Response({"detail": "Nhà cung cấp OAuth không hợp lệ."}, status=status.HTTP_404_NOT_FOUND)
        try:
            authorization_url, flow = create_oauth_flow(provider, "login")
            response = HttpResponseRedirect(authorization_url)
            _set_oauth_state_cookie(response, provider, flow["cookie"])
            return response
        except OAuthNotConfigured:
            return _return_response("not_configured", "login", provider)
        except ImproperlyConfigured as exc:
            raise AuthenticationUnavailable from exc

    @extend_schema(
        operation_id="auth_student_oauth_link_start",
        tags=["Xác thực"],
        summary="Bắt đầu liên kết Google hoặc Facebook với tài khoản học viên hiện tại",
        description=(
            "Chỉ học viên đã đăng nhập và đã đổi mật khẩu cấp lần đầu được liên kết. "
            "Liên kết được ghi tới các bản TaiKhoan tại mọi site đang hoạt động."
        ),
        parameters=[OpenApiParameter("provider", str, OpenApiParameter.PATH)],
        responses={200: OpenApiResponse(description="URL ủy quyền và cookie state HttpOnly."), 403: OpenApiResponse(description="Không đúng vai trò hoặc phải đổi mật khẩu trước.")},
    )
    def post(self, request, provider: str):
        if provider not in PROVIDER_COLUMNS:
            return Response({"detail": "Nhà cung cấp OAuth không hợp lệ."}, status=status.HTTP_404_NOT_FOUND)
        if (
            not getattr(request.user, "is_authenticated", False)
            or request.user.role != "hoc_vien"
            or request.user.must_change_password
        ):
            return Response({"detail": "Chỉ học viên đã đổi mật khẩu cấp lần đầu mới được liên kết."}, status=403)
        try:
            authorization_url, flow = create_oauth_flow(provider, "link", request.user.account_id)
        except OAuthNotConfigured:
            return Response({"detail": "Nhà cung cấp OAuth chưa được cấu hình."}, status=503)
        response = Response({"authorization_url": authorization_url})
        _set_oauth_state_cookie(response, provider, flow["cookie"])
        return response


class OAuthCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]

    def get_throttles(self):
        self.throttle_scope = "oauth_callback"
        return super().get_throttles()

    @extend_schema(
        operation_id="auth_student_oauth_callback",
        tags=["Xác thực"],
        summary="Nhận callback OAuth và xác minh tài khoản học viên",
        parameters=[OpenApiParameter("provider", str, OpenApiParameter.PATH)],
        responses={302: OpenApiResponse(description="Trả về trang đăng nhập hoặc cổng học viên với mã kết quả an toàn.")},
    )
    def get(self, request, provider: str):
        if provider not in PROVIDER_COLUMNS:
            return Response({"detail": "Nhà cung cấp OAuth không hợp lệ."}, status=status.HTTP_404_NOT_FOUND)
        cookie_name = oauth_state_cookie_name(provider)
        flow_cookie = request.COOKIES.get(cookie_name, "")
        try:
            flow = read_oauth_flow(provider, flow_cookie, request.GET.get("state", ""))
        except (OAuthNotConfigured, OAuthStateInvalid):
            return _return_response("invalid", "login", provider)

        intent = flow["intent"]
        remote_ip = request.META.get("REMOTE_ADDR", "") or "unknown"
        oauth_user = None
        if intent == "link":
            try:
                authenticated = AuthCookieAuthentication().authenticate(request)
            except AuthenticationFailed:
                return _return_response("session_expired", "link", provider)
            except AuthenticationUnavailable as exc:
                raise AuthenticationUnavailable from exc
            if authenticated is None:
                return _return_response("session_expired", "link", provider)
            oauth_user = authenticated[0]
        try:
            consume_oauth_state_once(flow["state"], remote_ip)
        except OAuthStateInvalid:
            return _return_response("invalid", intent, provider)
        except (AuthInfrastructureUnavailable, ImproperlyConfigured) as exc:
            raise AuthenticationUnavailable from exc
        if request.GET.get("error"):
            return _return_response("cancelled", intent, provider)
        try:
            subject = exchange_oauth_code(provider, request.GET.get("code", ""), flow)
            if intent == "link":
                if (
                    oauth_user is None
                    or oauth_user.role != "hoc_vien"
                    or oauth_user.must_change_password
                    or oauth_user.account_id != flow.get("account_id")
                ):
                    return _return_response("session_expired", "link", provider)
                link_oauth_provider(oauth_user, provider, subject, remote_ip)
                return _return_response("linked", "link", provider)

            result = login_with_oauth_provider(provider, subject, remote_ip)
            if result is None:
                return _return_response("not_linked", "login", provider)
            user, token, _expires_at = result
            response = _return_response("success", "login", provider)
            _set_auth_cookie(response, token)
            response["Cache-Control"] = "no-store"
            response["Referrer-Policy"] = "no-referrer"
            return response
        except OAuthStateInvalid:
            return _return_response("invalid", intent, provider)
        except LoginRateLimitExceeded:
            return _return_response("rate_limited", intent, provider)
        except OAuthAccountConflict:
            return _return_response("link_conflict", intent, provider)
        except OAuthNotConfigured:
            return _return_response("not_configured", intent, provider)
        except (AuthInfrastructureUnavailable, ImproperlyConfigured) as exc:
            raise AuthenticationUnavailable from exc
        except OAuthProviderError:
            return _return_response("provider_error", intent, provider)


class StudentOAuthConnectionsView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "oauth_connections"

    @extend_schema(
        operation_id="auth_student_oauth_connections",
        tags=["Xác thực"],
        summary="Xem trạng thái liên kết Google và Facebook của học viên hiện tại",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        responses={200: OpenApiResponse(description="Chỉ trả trạng thái đã liên kết, không trả subject hoặc token."), 503: OpenApiResponse(description="Các bản sao TaiKhoan chưa đồng nhất hoặc site không sẵn sàng.")},
    )
    def get(self, request, slug: str):
        try:
            connections = get_oauth_connections(request.user, slug)
        except OAuthAccountConflict:
            return Response({"detail": "Không tìm thấy quyền hồ sơ học viên."}, status=status.HTTP_404_NOT_FOUND)
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc
        return Response({"connections": connections})


class AuthSessionView(APIView):
    """Return the authenticated principal without putting a slug in a callback URL."""

    authentication_classes = [AuthCookieAuthentication]

    @extend_schema(
        operation_id="auth_session_read",
        tags=["Xác thực"],
        summary="Lấy thông tin tài khoản của phiên đăng nhập hiện tại",
        responses={200: OpenApiResponse(description="Tài khoản và vai trò đã xác thực."), 401: OpenApiResponse(description="Phiên không hợp lệ hoặc hết hạn.")},
    )
    def get(self, request):
        return Response({"user": _serialized_user(request.user)})
