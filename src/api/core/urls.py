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
)
from core.students.views import (
    StudentAccountProvisionView,
    StudentAdminCollectionView,
    StudentDeleteView,
    StudentEnrollmentListView,
    StudentGradesView,
    StudentProfileView,
    StudentScheduleView,
    StudentTuitionView,
)
from core.classes.views import (
    ClassCollectionView,
    ClassDetailView,
    ClassRosterView,
    ClassSessionsView,
    ClassTeacherAssignView,
    EnrollmentCollectionView,
    EnrollmentClassAssignView,
    RoomCollectionView,
)
from core.academics.attendance_views import (
    TeacherClassListView,
    TeacherSessionAttendanceView,
    TeacherSessionListView,
)
from core.academics.grade_views import (
    TeacherEnrollmentGradeHistoryView,
    TeacherEnrollmentGradeItemView,
    TeacherEnrollmentGradesView,
)
from core.academics.report_views import StudentCountsBySiteView
from core.academics.transfer_views import TransferCollectionView, TransferDecisionView, TransferRetryView
from core.academics.installment_views import TuitionInstallmentPlanView
from core.academics.tuition_views import (
    AdminTuitionListView,
    TuitionInvoiceView,
    TuitionReceiptCreateView,
)
from core.academics.reminder_views import ClassTuitionReminderView
from core.employees.views import EmployeeCollectionView, EmployeeDetailView
from core.catalog.views import SharedSubjectDetailView


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
    path("admin/employees/", EmployeeCollectionView.as_view(), name="employee-list-create"),
    path("admin/employees/<str:slug>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path("admin/shared/subjects/<str:slug>/", SharedSubjectDetailView.as_view(), name="shared-subject-detail"),
    path("admin/students/", StudentAdminCollectionView.as_view(), name="student-admin-list"),
    path("admin/students/<str:slug>/", StudentDeleteView.as_view(), name="student-admin-delete"),
    path("admin/students/<str:slug>/account/", StudentAccountProvisionView.as_view(), name="student-account-issue"),
    path("admin/classes/", ClassCollectionView.as_view(), name="class-list-create"),
    path("admin/rooms/", RoomCollectionView.as_view(), name="room-list-create"),
    path("admin/classes/<str:class_id>/", ClassDetailView.as_view(), name="class-detail"),
    path("admin/classes/<str:class_id>/students/", ClassRosterView.as_view(), name="class-students"),
    path("admin/classes/<str:class_id>/sessions/", ClassSessionsView.as_view(), name="class-sessions"),
    path("admin/classes/<str:class_id>/teacher/", ClassTeacherAssignView.as_view(), name="class-assign-teacher"),
    path("admin/enrollments/<str:enrollment_id>/class/", EnrollmentClassAssignView.as_view(), name="enrollment-assign-class"),
    path("admin/enrollments/", EnrollmentCollectionView.as_view(), name="enrollment-create"),
    path("admin/tuition/", AdminTuitionListView.as_view(), name="tuition-list"),
    path("admin/tuition/<str:tuition_id>/installments/", TuitionInstallmentPlanView.as_view(), name="tuition-installments"),
    path("admin/tuition/<str:tuition_id>/receipts/", TuitionReceiptCreateView.as_view(), name="tuition-receipt-create"),
    path("admin/tuition/<str:tuition_id>/receipts/<str:receipt_id>/invoice/", TuitionInvoiceView.as_view(), name="tuition-invoice"),
    path("admin/classes/<str:class_id>/tuition-reminders/", ClassTuitionReminderView.as_view(), name="class-tuition-reminders"),
    path("admin/transfers/", TransferCollectionView.as_view(), name="transfer-request-list-create"),
    path("admin/transfers/<str:source_site>/<str:transfer_id>/decision/", TransferDecisionView.as_view(), name="transfer-request-decision"),
    path("admin/transfers/<str:source_site>/<str:transfer_id>/retry/", TransferRetryView.as_view(), name="transfer-retry"),
    path("admin/reports/students-by-site/", StudentCountsBySiteView.as_view(), name="student-counts-by-site"),
    path("teacher/classes/", TeacherClassListView.as_view(), name="teacher-classes"),
    path("teacher/classes/<str:class_id>/sessions/", TeacherSessionListView.as_view(), name="teacher-class-sessions"),
    path("teacher/sessions/<str:session_id>/attendance/", TeacherSessionAttendanceView.as_view(), name="teacher-session-attendance"),
    path("teacher/enrollments/<str:enrollment_id>/grades/history/", TeacherEnrollmentGradeHistoryView.as_view(), name="teacher-grade-history"),
    path("teacher/enrollments/<str:enrollment_id>/grades/", TeacherEnrollmentGradesView.as_view(), name="teacher-enrollment-grades"),
    path("teacher/enrollments/<str:enrollment_id>/grades/<str:grade_type>/", TeacherEnrollmentGradeItemView.as_view(), name="teacher-grade-upsert"),
    path("students/profile/<str:slug>/", StudentProfileView.as_view(), name="student-profile"),
    path("students/profile/<str:slug>/enrollments/", StudentEnrollmentListView.as_view(), name="student-enrollments"),
    path("students/profile/<str:slug>/schedule/", StudentScheduleView.as_view(), name="student-schedule"),
    path("students/profile/<str:slug>/tuition/", StudentTuitionView.as_view(), name="student-tuition"),
    path("students/profile/<str:slug>/grades/", StudentGradesView.as_view(), name="student-grades"),
    path("admin/notifications/", AdminNotificationListView.as_view(), name="admin-notification-list"),
]
