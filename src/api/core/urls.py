from django.urls import path

from core.auth.views import (
    AuthActivityView,
    AuthChangePasswordView,
    AuthLoginView,
    AuthLogoutView,
    AuthProfileView,
    AdminBigSelfProfileView,
    AdminForgotPasswordView,
    AdminResetPasswordView,
    AdminSmallCreateView,
    AdminSmallDeleteView,
    AdminSmallStatusView,
    AdminSmallSelfProfileView,
    CsrfTokenView,
)
from core.views import health_check
from core.teachers.views import TeacherCollectionView, TeacherDetailView, TeacherProfileView, TeacherStatusView
from core.notifications.views import (
    AdminNotificationListView,
    AdminNotificationReadAllView,
    AdminNotificationReadView,
    AdminNotificationUnreadCountView,
)


app_name = "core"

urlpatterns = [
    path("health/", health_check, name="health"),
    path("auth/csrf/", CsrfTokenView.as_view(), name="auth-csrf"),
    path("auth/login/", AuthLoginView.as_view(), name="auth-login"),
    path("auth/password/change/", AuthChangePasswordView.as_view(), name="auth-password-change"),
    path("auth/password/forgot/", AdminForgotPasswordView.as_view(), name="auth-password-forgot"),
    path("auth/password/reset/", AdminResetPasswordView.as_view(), name="auth-password-reset"),
    path("auth/profile/<str:slug>/", AuthProfileView.as_view(), name="auth-profile"),
    path("auth/activity/", AuthActivityView.as_view(), name="auth-activity"),
    path("auth/logout/", AuthLogoutView.as_view(), name="auth-logout"),
    path("admin/admin-smalls/", AdminSmallCreateView.as_view(), name="admin-small-create"),
    path("admin/admin-smalls/profile/<str:slug>/", AdminSmallSelfProfileView.as_view(), name="admin-small-profile"),
    path("admin/admin-smalls/<str:slug>/status/", AdminSmallStatusView.as_view(), name="admin-small-status"),
    path("admin/admin-smalls/<str:account_id>/", AdminSmallDeleteView.as_view(), name="admin-small-delete"),
    path("admin/admin-bigs/profile/<str:slug>/", AdminBigSelfProfileView.as_view(), name="admin-big-profile"),
    path("teachers/profile/<str:slug>/", TeacherProfileView.as_view(), name="teacher-profile"),
    path("admin/teachers/", TeacherCollectionView.as_view(), name="teacher-list-create"),
    path("admin/teachers/<str:slug>/status/", TeacherStatusView.as_view(), name="teacher-status"),
    path("admin/teachers/<str:slug>/", TeacherDetailView.as_view(), name="teacher-detail"),
    path("admin/notifications/", AdminNotificationListView.as_view(), name="admin-notification-list"),
    path("admin/notifications/unread-count/", AdminNotificationUnreadCountView.as_view(), name="admin-notification-unread-count"),
    path("admin/notifications/read-all/", AdminNotificationReadAllView.as_view(), name="admin-notification-read-all"),
    path("admin/notifications/<str:site_code>/<str:slug>/read/", AdminNotificationReadView.as_view(), name="admin-notification-read"),
]
