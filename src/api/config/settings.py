"""Settings for the distributed language-center API."""

import json
import os
import re
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_csv(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("Thiếu DJANGO_SECRET_KEY trong biến môi trường hoặc file src/api/.env.")

DEBUG = env_bool("DJANGO_DEBUG", False)
API_DOCS_ENABLED = env_bool("API_DOCS_ENABLED", DEBUG)
ALLOWED_HOSTS = env_csv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "core.apps.CoreConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# The default alias intentionally cannot store application data. All application
# database access must resolve an explicit site code to a separate SQL Server DB.
DATABASES = {"default": {"ENGINE": "django.db.backends.dummy"}}
SITE_DATABASE_ALIASES: dict[str, str] = {}

_site_database_json = os.getenv("SITE_DATABASES_JSON", "{}").strip() or "{}"
try:
    _site_database_configs = json.loads(_site_database_json)
except json.JSONDecodeError as exc:
    raise ImproperlyConfigured("SITE_DATABASES_JSON phải là JSON hợp lệ.") from exc

if not isinstance(_site_database_configs, dict):
    raise ImproperlyConfigured("SITE_DATABASES_JSON phải là object ánh xạ mã cơ sở tới cấu hình.")

for _site_code, _site_config in _site_database_configs.items():
    if not isinstance(_site_code, str) or not re.fullmatch(r"[A-Z0-9_-]{2,12}", _site_code):
        raise ImproperlyConfigured(f"Mã cơ sở không hợp lệ trong SITE_DATABASES_JSON: {_site_code!r}.")
    if not isinstance(_site_config, dict):
        raise ImproperlyConfigured(f"Cấu hình của site {_site_code} phải là JSON object.")

    _trusted_connection = _site_config.get("trusted_connection", False) is True
    _required_keys = ("name", "host") if _trusted_connection else ("name", "host", "user", "password")
    _missing = [key for key in _required_keys if not str(_site_config.get(key, "")).strip()]
    if _missing:
        raise ImproperlyConfigured(
            f"Site {_site_code} thiếu cấu hình bắt buộc: {', '.join(_missing)}."
        )

    _alias = f"site_{_site_code.lower()}"
    if _alias in DATABASES:
        raise ImproperlyConfigured(f"Database alias bị trùng: {_alias}.")

    _encrypt = "yes" if env_bool("SQL_SERVER_ENCRYPT", True) else "no"
    _trust_certificate = "yes" if env_bool("SQL_SERVER_TRUST_SERVER_CERTIFICATE", False) else "no"
    _extra_params = (
        ("Trusted_Connection=yes;" if _trusted_connection else "")
        + f"Encrypt={_encrypt};TrustServerCertificate={_trust_certificate};"
        + "Connection Timeout=5;"
    )
    DATABASES[_alias] = {
        "ENGINE": "mssql",
        "NAME": str(_site_config["name"]),
        "HOST": str(_site_config["host"]),
        "PORT": str(_site_config.get("port", 1433)),
        "USER": "" if _trusted_connection else str(_site_config["user"]),
        "PASSWORD": "" if _trusted_connection else str(_site_config["password"]),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "driver": os.getenv("SQL_SERVER_DRIVER", "ODBC Driver 18 for SQL Server"),
            "extra_params": _extra_params,
        },
    }
    SITE_DATABASE_ALIASES[_site_code] = _alias

AUTH_SESSION_SITE_CODE = os.getenv("AUTH_SESSION_SITE_CODE", "").strip().upper()
if AUTH_SESSION_SITE_CODE and AUTH_SESSION_SITE_CODE not in SITE_DATABASE_ALIASES:
    raise ImproperlyConfigured(
        "AUTH_SESSION_SITE_CODE phải trỏ tới một site đã khai báo trong SITE_DATABASES_JSON."
    )

DATABASE_ROUTERS: list[str] = []

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Password creation/verification must use Django's maintained bcrypt hasher.
# This configures the approved algorithm; it does not add an auth endpoint or
# create a central Django user table.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.BCryptSHA256PasswordHasher"]
AUTH_DUMMY_PASSWORD_HASH = make_password("qlttnn-invalid-login-timing-sentinel")
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["core.auth.authentication.AuthCookieAuthentication"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min",
        "user": "600/min",
        "admin_account_create": "10/hour",
        "admin_small_self_profile": "30/hour",
        "admin_big_self_profile": "20/hour",
        "admin_small_delete": "10/hour",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "API Quản lý Trung tâm Ngoại ngữ",
    "DESCRIPTION": (
        "API và Coordinator cho hệ thống CSDL phân tán. Mỗi site dùng một CSDL SQL Server riêng; "
        "Global Query tổng hợp kết quả tại tầng API. Các nghiệp vụ còn lại sẽ được công bố "
        "trong OpenAPI khi được triển khai và kiểm thử."
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_DIST": "SIDECAR",
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "Hệ thống", "description": "Kiểm tra tiến trình API."},
        {"name": "Xác thực", "description": "Đăng nhập và quản lý phiên theo vai trò được cấp."},
    ],
}

CORS_ALLOWED_ORIGINS = env_csv("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env_csv("CSRF_TRUSTED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# Email delivery for account activation and password recovery. Keep credentials
# in src/api/.env or a deployment secret store; never expose them to the web app.
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
).strip()
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com").strip()
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "").strip()
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER).strip()
ADMIN_SMALL_TEMP_PASSWORD = os.getenv("ADMIN_SMALL_TEMP_PASSWORD", "").strip()
WEB_APP_BASE_URL = os.getenv("WEB_APP_BASE_URL", "http://localhost:3000").rstrip("/")
PASSWORD_RESET_TIMEOUT = int(os.getenv("PASSWORD_RESET_TIMEOUT", "120"))
ACCOUNT_ACTIVATION_TIMEOUT = int(os.getenv("ACCOUNT_ACTIVATION_TIMEOUT", "86400"))
AUTH_PASSWORD_RESET_IP_LIMIT_PER_HOUR = 10
AUTH_PASSWORD_RESET_IDENTITY_LIMIT_PER_HOUR = 3
AUTH_PASSWORD_RESET_COOLDOWN_SECONDS = 60
AUTH_PASSWORD_RESET_VERIFY_IP_LIMIT_PER_HOUR = 20
AUTH_PASSWORD_RESET_VERIFY_IDENTITY_LIMIT_PER_HOUR = 10
AUTH_PASSWORD_RESET_OTP_ATTEMPT_LIMIT = 5

if not 1 <= EMAIL_PORT <= 65535:
    raise ImproperlyConfigured("EMAIL_PORT phải nằm trong khoảng 1–65535.")
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured("Chỉ bật một trong EMAIL_USE_TLS hoặc EMAIL_USE_SSL.")
if EMAIL_TIMEOUT <= 0 or ACCOUNT_ACTIVATION_TIMEOUT <= 0:
    raise ImproperlyConfigured("Timeout email và kích hoạt tài khoản phải lớn hơn 0.")
if PASSWORD_RESET_TIMEOUT != 120:
    raise ImproperlyConfigured("OTP quên mật khẩu quản trị cố định hết hạn sau 120 giây.")

# Cloudinary credentials are optional until a signed upload endpoint is
# implemented. Never expose CLOUDINARY_API_SECRET to the web frontend or logs.
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "").strip()
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "").strip()
CLOUDINARY_ROOT_FOLDER = (
    os.getenv("CLOUDINARY_ROOT_FOLDER", "language-center-management").strip("/ ")
    or "language-center-management"
)

# OAuth settings are placeholders for the future authorization-code callbacks.
# No OAuth route is enabled until provider verification, distributed account
# resolution, revocable app sessions, and the schema migration are implemented.
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
GOOGLE_OAUTH_REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
FACEBOOK_OAUTH_APP_ID = os.getenv("FACEBOOK_OAUTH_APP_ID", "").strip()
FACEBOOK_OAUTH_APP_SECRET = os.getenv("FACEBOOK_OAUTH_APP_SECRET", "").strip()
FACEBOOK_OAUTH_REDIRECT_URI = os.getenv("FACEBOOK_OAUTH_REDIRECT_URI", "").strip()
OAUTH_WEB_RETURN_URL = os.getenv("OAUTH_WEB_RETURN_URL", "").strip()

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
AUTH_COOKIE_NAME = "qlttnn_auth"
AUTH_IDLE_TIMEOUT_SECONDS = 3600
AUTH_LOGIN_IP_LIMIT_PER_MINUTE = 10
AUTH_LOGIN_IDENTITY_FAILURE_LIMIT = 5
AUTH_LOGIN_IDENTITY_WINDOW_SECONDS = 900
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
