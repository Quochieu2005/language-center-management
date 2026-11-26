"""Student self-service profile photo: the same LOCAL flow as the admin photo endpoints."""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.auth.authentication import AuthCookieAuthentication
from core.auth.serializers import EmptyRequestSerializer
from core.media.avatars import AvatarConflict, AvatarInvalidIntent, AvatarInvalidUpload, AvatarUnavailable
from core.media.serializers import AdminAvatarFinalizeRequestSerializer, AdminAvatarUploadIntentResponseSerializer
from core.students.avatars import complete_student_avatar_upload, create_student_avatar_upload_intent
from core.students.serializers import StudentAvatarResponseSerializer
from core.students.services import (
    StudentConflict,
    StudentInfrastructureUnavailable,
    StudentNotFound,
    StudentSiteUnavailable,
)
from core.students.views import _remote_ip, _student_avatar_error, _student_slug_error

_ERRORS = (
    AvatarConflict, AvatarInvalidIntent, AvatarInvalidUpload, AvatarUnavailable, StudentConflict,
    StudentInfrastructureUnavailable, StudentNotFound, StudentSiteUnavailable,
)


class _StudentSelfAvatarView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "profile_avatar"


@method_decorator(csrf_protect, name="dispatch")
class StudentSelfAvatarUploadIntentView(_StudentSelfAvatarView):
    @extend_schema(
        operation_id="student_self_avatar_upload_intent",
        tags=["Cổng học viên"],
        summary="Học viên xin chữ ký tải ảnh hồ sơ của chính mình lên Cloudinary",
        description="Site và hồ sơ lấy từ phiên học viên, không nhận từ client. LOCAL tại site hồ sơ.",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        request=EmptyRequestSerializer,
        responses={
            200: AdminAvatarUploadIntentResponseSerializer, 403: OpenApiResponse(), 404: OpenApiResponse(),
            409: OpenApiResponse(), 503: OpenApiResponse(),
        },
    )
    def post(self, request, slug: str):
        error = _student_slug_error(request, slug)
        if error:
            return error
        serializer = EmptyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(create_student_avatar_upload_intent(request.user, request.user.site_code, slug))
        except _ERRORS as exc:
            return _student_avatar_error(exc)


@method_decorator(csrf_protect, name="dispatch")
class StudentSelfAvatarCompleteView(_StudentSelfAvatarView):
    @extend_schema(
        operation_id="student_self_avatar_complete",
        tags=["Cổng học viên"],
        summary="Học viên xác nhận ảnh đã tải và lưu vào hồ sơ của chính mình",
        description="Xác minh ảnh qua Cloudinary rồi ghi metadata `HocVien` cùng audit trong transaction tại site hồ sơ.",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        request=AdminAvatarFinalizeRequestSerializer,
        responses={
            200: StudentAvatarResponseSerializer, 400: OpenApiResponse(), 403: OpenApiResponse(),
            404: OpenApiResponse(), 409: OpenApiResponse(), 503: OpenApiResponse(),
        },
    )
    def post(self, request, slug: str):
        error = _student_slug_error(request, slug)
        if error:
            return error
        serializer = AdminAvatarFinalizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(complete_student_avatar_upload(
                request.user, request.user.site_code, slug,
                serializer.validated_data["intent_token"], serializer.validated_data["public_id"],
                _remote_ip(request),
            ))
        except _ERRORS as exc:
            return _student_avatar_error(exc)
