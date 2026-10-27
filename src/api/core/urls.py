from django.urls import path

from core.auth.views import (
    AuthActivityView,
    AuthChangePasswordView,
    AuthLoginView,
    AuthLogoutView,
    AuthMeView,
    AdminBigSelfProfileView,
    AdminForgotPasswordView,
    AdminResetPasswordView,
    AdminSmallCreateView,
    AdminSmallDeleteView,
    AdminSmallSelfProfileView,
    CsrfTokenView,
)
from core.views import health_check


app_name = "core"

urlpatterns = [
    path("health/", health_check, name="health"),
    path("auth/csrf/", CsrfTokenView.as_view(), name="auth-csrf"),
    path("auth/login/", AuthLoginView.as_view(), name="auth-login"),
    path("auth/password/change/", AuthChangePasswordView.as_view(), name="auth-password-change"),
    path("auth/password/forgot/", AdminForgotPasswordView.as_view(), name="auth-password-forgot"),
    path("auth/password/reset/", AdminResetPasswordView.as_view(), name="auth-password-reset"),
    path("auth/me/", AuthMeView.as_view(), name="auth-me"),
    path("auth/activity/", AuthActivityView.as_view(), name="auth-activity"),
    path("auth/logout/", AuthLogoutView.as_view(), name="auth-logout"),
    path("admin/admin-smalls/", AdminSmallCreateView.as_view(), name="admin-small-create"),
    path("admin/admin-smalls/me/", AdminSmallSelfProfileView.as_view(), name="admin-small-self-profile"),
    path("admin/admin-smalls/<str:account_id>/", AdminSmallDeleteView.as_view(), name="admin-small-delete"),
    path("admin/admin-bigs/me/", AdminBigSelfProfileView.as_view(), name="admin-big-self-profile"),
]
