"""HttpOnly cookie authentication for authenticated API requests."""

import re

from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework.exceptions import APIException, AuthenticationFailed

from core.auth.services import AuthInfrastructureUnavailable, load_user_session


_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{64}$")


class AuthenticationUnavailable(APIException):
    status_code = 503
    default_detail = "Dịch vụ xác thực tạm thời không sẵn sàng."
    default_code = "authentication_unavailable"


class AuthCookieAuthentication(BaseAuthentication):
    """Validate a revocable DB session and enforce CSRF for unsafe methods."""

    def authenticate(self, request):
        from django.conf import settings

        token = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
        if not token:
            return None
        if not _TOKEN_RE.fullmatch(token):
            raise AuthenticationFailed("Phiên đăng nhập không hợp lệ hoặc đã hết hạn.")

        try:
            loaded = load_user_session(token)
        except AuthInfrastructureUnavailable as exc:
            raise AuthenticationUnavailable from exc
        if loaded is None:
            raise AuthenticationFailed("Phiên đăng nhập không hợp lệ hoặc đã hết hạn.")

        user, session = loaded
        if user.must_change_password:
            allowed_url_names = {"auth-profile", "auth-password-change", "auth-logout"}
            match = getattr(request, "resolver_match", None)
            if match is None or match.url_name not in allowed_url_names:
                raise AuthenticationFailed(
                    "Bạn phải đổi mật khẩu trước khi sử dụng chức năng khác.",
                    code="password_change_required",
                )

        if request.method not in ("GET", "HEAD", "OPTIONS", "TRACE"):
            SessionAuthentication().enforce_csrf(request)
        return user, session

    def authenticate_header(self, _request):
        return "Session"
