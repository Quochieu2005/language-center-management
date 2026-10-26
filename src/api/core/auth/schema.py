from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class AuthCookieAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "core.auth.authentication.AuthCookieAuthentication"
    name = "SessionCookie"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.AUTH_COOKIE_NAME,
        }
