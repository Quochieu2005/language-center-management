"""Settings for the distributed language-center API."""

import json
import os
import re
from pathlib import Path

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

    _required_keys = ("name", "host", "user", "password")
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
    DATABASES[_alias] = {
        "ENGINE": "mssql",
        "NAME": str(_site_config["name"]),
        "HOST": str(_site_config["host"]),
        "PORT": str(_site_config.get("port", 1433)),
        "USER": str(_site_config["user"]),
        "PASSWORD": str(_site_config["password"]),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "driver": os.getenv("SQL_SERVER_DRIVER", "ODBC Driver 18 for SQL Server"),
            "extra_params": (
                f"Encrypt={_encrypt};TrustServerCertificate={_trust_certificate};"
                "Connection Timeout=5;"
            ),
        },
    }
    SITE_DATABASE_ALIASES[_site_code] = _alias

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

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "120/min", "user": "600/min"},
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
    "TAGS": [{"name": "Hệ thống", "description": "Kiểm tra tiến trình API."}],
}

CORS_ALLOWED_ORIGINS = env_csv("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env_csv("CSRF_TRUSTED_ORIGINS")

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
