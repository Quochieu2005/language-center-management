from django.urls import path

from core.auth.views import (
    AuthActivityView,
    AuthLoginView,
    AuthLogoutView,
    AuthMeView,
    AdminForgotPasswordView,
    AdminResetPasswordView,
    CsrfTokenView,
)
from core.views import health_check


app_name = "core"

urlpatterns = [
    path("health/", health_check, name="health"),
    path("auth/csrf/", CsrfTokenView.as_view(), name="auth-csrf"),
    path("auth/login/", AuthLoginView.as_view(), name="auth-login"),
    path("auth/password/forgot/", AdminForgotPasswordView.as_view(), name="auth-password-forgot"),
    path("auth/password/reset/", AdminResetPasswordView.as_view(), name="auth-password-reset"),
    path("auth/me/", AuthMeView.as_view(), name="auth-me"),
    path("auth/activity/", AuthActivityView.as_view(), name="auth-activity"),
    path("auth/logout/", AuthLogoutView.as_view(), name="auth-logout"),
]
