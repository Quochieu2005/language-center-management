from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.auth.authentication import AuthCookieAuthentication
from core.auth.serializers import EmptyRequestSerializer
from core.media.avatars import (
    AvatarConflict,
    AvatarInvalidIntent,
    AvatarInvalidUpload,
    AvatarTargetNotFound,
    AvatarUnavailable,
    complete_admin_avatar_upload,
    complete_admin_small_avatar_upload,
    complete_teacher_avatar_upload,
    create_admin_avatar_upload_intent,
    create_admin_small_avatar_upload_intent,
    create_teacher_avatar_upload_intent,
)
from core.media.serializers import (
    AdminAvatarFinalizeRequestSerializer,
    AdminAvatarResponseSerializer,
    AdminAvatarUploadIntentResponseSerializer,
    AdminSmallAvatarFinalizeRequestSerializer,
    AdminSmallAvatarUploadIntentRequestSerializer,
    TeacherAvatarFinalizeRequestSerializer,
    TeacherAvatarUploadIntentRequestSerializer,
)


@method_decorator(csrf_protect, name="dispatch")
class AdminAvatarUploadIntentView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "profile_avatar"

    @extend_schema(
        operation_id="profile_avatar_upload_intent",
        tags=["Hồ sơ tài khoản"],
        summary="Cấp chữ ký Cloudinary tải ảnh cho hồ sơ hiện tại",
        description=(
            "Tài khoản đã xác thực chỉ được tạo chữ ký cho hồ sơ của chính mình. "
            "API không nhận account_id/site từ client; ảnh tải thẳng lên Cloudinary, khóa API secret "
            "không rời máy chủ. Metadata TaiKhoan được đồng bộ tại bước hoàn tất."
        ),
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        request=EmptyRequestSerializer,
        responses={
            200: AdminAvatarUploadIntentResponseSerializer,
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Vai trò không được phép tải ảnh."),
            404: OpenApiResponse(description="Slug không thuộc tài khoản hiện tại."),
            409: OpenApiResponse(description="Tài khoản hoặc ảnh ở các site chưa đồng nhất."),
            429: OpenApiResponse(description="Vượt giới hạn cấp chữ ký."),
            503: OpenApiResponse(description="Cloudinary, migration hoặc một site chưa sẵn sàng."),
        },
    )
    def post(self, request, slug: str):
        if slug != request.user.slug:
            return Response({"detail": "Không tìm thấy hồ sơ tài khoản."}, status=404)
        try:
            intent = create_admin_avatar_upload_intent(request.user)
        except AvatarConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except AvatarUnavailable as exc:
            return Response(
                {"detail": str(exc), "complete": False, "missing_sites": list(exc.missing_sites)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(intent, status=status.HTTP_200_OK)


@method_decorator(csrf_protect, name="dispatch")
class AdminAvatarCompleteView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "profile_avatar"

    @extend_schema(
        operation_id="profile_avatar_complete",
        tags=["Hồ sơ tài khoản"],
        summary="Xác minh ảnh Cloudinary và đồng bộ hồ sơ hiện tại qua các site",
        description=(
            "API xác minh public_id, thư mục, loại ảnh, kích thước và URL qua Cloudinary Admin API. "
            "Sau đó ghi hai cột metadata trên dbo.TaiKhoan tại mọi site đang hoạt động; mỗi site "
            "có transaction cục bộ và ACK append-only trong dbo.Logs. Khi site lỗi, gửi lại cùng "
            "intent_token/public_id để tiếp tục; thao tác không phải ACID nguyên tử xuyên CSDL."
        ),
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        request=AdminAvatarFinalizeRequestSerializer,
        responses={
            200: AdminAvatarResponseSerializer,
            400: OpenApiResponse(description="Intent hết hạn hoặc ảnh không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Vai trò không được phép đổi ảnh."),
            404: OpenApiResponse(description="Slug không thuộc tài khoản hiện tại."),
            409: OpenApiResponse(description="Ảnh hoặc metadata giữa các site bị xung đột."),
            429: OpenApiResponse(description="Vượt giới hạn hoàn tất tải ảnh."),
            503: OpenApiResponse(description="Cloudinary hoặc một site chưa sẵn sàng; có thể thử lại."),
        },
    )
    def post(self, request, slug: str):
        if slug != request.user.slug:
            return Response({"detail": "Không tìm thấy hồ sơ tài khoản."}, status=404)
        serializer = AdminAvatarFinalizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = complete_admin_avatar_upload(
                request.user,
                serializer.validated_data["intent_token"],
                serializer.validated_data["public_id"],
                request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except AvatarInvalidIntent as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except AvatarInvalidUpload as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except AvatarConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except AvatarUnavailable as exc:
            return Response(
                {"detail": str(exc), "complete": False, "missing_sites": list(exc.missing_sites)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(result, status=status.HTTP_200_OK)


@method_decorator(csrf_protect, name="dispatch")
class AdminSmallAvatarUploadIntentView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "profile_avatar"

    @extend_schema(
        operation_id="admin_small_initial_avatar_upload_intent",
        tags=["Quản lý tài khoản"],
        summary="Cấp quyền tải ảnh ban đầu cho Admin Small vừa được Admin Big tạo",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        request=AdminSmallAvatarUploadIntentRequestSerializer,
        responses={
            200: AdminAvatarUploadIntentResponseSerializer,
            400: OpenApiResponse(description="Quyền tải ảnh không hợp lệ hoặc đã hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big được cấp ảnh ban đầu."),
            404: OpenApiResponse(description="Không tìm thấy tài khoản Admin Small."),
            409: OpenApiResponse(description="Tài khoản hoặc bản sao ảnh đã tồn tại/xung đột."),
            429: OpenApiResponse(description="Vượt giới hạn tải ảnh."),
            503: OpenApiResponse(description="Cloudinary hoặc một site chưa sẵn sàng."),
        },
    )
    def post(self, request, slug: str):
        if request.user.role != "admin_big":
            return Response({"detail": "Chỉ Admin Big được cấp ảnh ban đầu."}, status=403)
        serializer = AdminSmallAvatarUploadIntentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            intent = create_admin_small_avatar_upload_intent(
                request.user, slug, serializer.validated_data["setup_token"]
            )
        except AvatarInvalidIntent as exc:
            return Response({"detail": str(exc)}, status=400)
        except AvatarTargetNotFound:
            return Response({"detail": "Không tìm thấy tài khoản Admin Small."}, status=404)
        except AvatarConflict as exc:
            return Response({"detail": str(exc)}, status=409)
        except AvatarUnavailable as exc:
            return Response(
                {"detail": str(exc), "complete": False, "missing_sites": list(exc.missing_sites)},
                status=503,
            )
        return Response(intent, status=200)


@method_decorator(csrf_protect, name="dispatch")
class AdminSmallAvatarCompleteView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "profile_avatar"

    @extend_schema(
        operation_id="admin_small_initial_avatar_complete",
        tags=["Quản lý tài khoản"],
        summary="Xác minh và lưu ảnh ban đầu cho Admin Small vừa được tạo",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        request=AdminSmallAvatarFinalizeRequestSerializer,
        responses={
            200: AdminAvatarResponseSerializer,
            400: OpenApiResponse(description="Ảnh hoặc quyền tải ảnh không hợp lệ."),
            403: OpenApiResponse(description="Chỉ Admin Big được cấp ảnh ban đầu."),
            404: OpenApiResponse(description="Không tìm thấy tài khoản Admin Small."),
            409: OpenApiResponse(description="Ảnh hoặc metadata giữa các site bị xung đột."),
            429: OpenApiResponse(description="Vượt giới hạn hoàn tất tải ảnh."),
            503: OpenApiResponse(description="Cloudinary hoặc một site chưa sẵn sàng; có thể gửi lại cùng yêu cầu."),
        },
    )
    def post(self, request, slug: str):
        if request.user.role != "admin_big":
            return Response({"detail": "Chỉ Admin Big được cấp ảnh ban đầu."}, status=403)
        serializer = AdminSmallAvatarFinalizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = complete_admin_small_avatar_upload(
                request.user,
                slug,
                serializer.validated_data["setup_token"],
                serializer.validated_data["intent_token"],
                serializer.validated_data["public_id"],
                request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except AvatarInvalidIntent as exc:
            return Response({"detail": str(exc)}, status=400)
        except AvatarInvalidUpload as exc:
            return Response({"detail": str(exc)}, status=400)
        except AvatarTargetNotFound:
            return Response({"detail": "Không tìm thấy tài khoản Admin Small."}, status=404)
        except AvatarConflict as exc:
            return Response({"detail": str(exc)}, status=409)
        except AvatarUnavailable as exc:
            return Response(
                {"detail": str(exc), "complete": False, "missing_sites": list(exc.missing_sites)},
                status=503,
            )
        return Response(result, status=200)


@method_decorator(csrf_protect, name="dispatch")
class TeacherAvatarUploadIntentView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "profile_avatar"

    @extend_schema(
        operation_id="teacher_initial_avatar_upload_intent",
        tags=["Quản lý giáo viên"],
        summary="Cấp quyền tải ảnh hồ sơ ban đầu cho giáo viên vừa được tạo",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        request=TeacherAvatarUploadIntentRequestSerializer,
        responses={
            200: AdminAvatarUploadIntentResponseSerializer,
            400: OpenApiResponse(description="Quyền tải ảnh không hợp lệ hoặc đã hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big/Admin Small được cấp ảnh trong phạm vi site."),
            404: OpenApiResponse(description="Không tìm thấy giáo viên."),
            409: OpenApiResponse(description="Tài khoản hoặc bản sao ảnh chưa đồng nhất."),
            429: OpenApiResponse(description="Vượt giới hạn tải ảnh."),
            503: OpenApiResponse(description="Cloudinary hoặc một site chưa sẵn sàng."),
        },
    )
    def post(self, request, slug: str):
        if request.user.role not in {"admin_big", "admin_small"}:
            return Response({"detail": "Chỉ Admin Big hoặc Admin Small được cấp ảnh giáo viên."}, status=403)
        serializer = TeacherAvatarUploadIntentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            intent = create_teacher_avatar_upload_intent(
                request.user, slug, serializer.validated_data["setup_token"]
            )
        except AvatarInvalidIntent as exc:
            return Response({"detail": str(exc)}, status=400)
        except AvatarTargetNotFound:
            return Response({"detail": "Không tìm thấy giáo viên."}, status=404)
        except AvatarConflict as exc:
            return Response({"detail": str(exc)}, status=409)
        except AvatarUnavailable as exc:
            return Response(
                {"detail": str(exc), "complete": False, "missing_sites": list(exc.missing_sites)},
                status=503,
            )
        return Response(intent, status=200)


@method_decorator(csrf_protect, name="dispatch")
class TeacherAvatarCompleteView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "profile_avatar"

    @extend_schema(
        operation_id="teacher_initial_avatar_complete",
        tags=["Quản lý giáo viên"],
        summary="Xác minh và lưu ảnh hồ sơ giáo viên vào các bản sao TaiKhoan",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        request=TeacherAvatarFinalizeRequestSerializer,
        responses={
            200: AdminAvatarResponseSerializer,
            400: OpenApiResponse(description="Ảnh hoặc quyền tải ảnh không hợp lệ."),
            403: OpenApiResponse(description="Chỉ Admin Big/Admin Small được cấp ảnh trong phạm vi site."),
            404: OpenApiResponse(description="Không tìm thấy giáo viên."),
            409: OpenApiResponse(description="Ảnh hoặc metadata giữa các site bị xung đột."),
            429: OpenApiResponse(description="Vượt giới hạn hoàn tất tải ảnh."),
            503: OpenApiResponse(description="Cloudinary hoặc một site chưa sẵn sàng; có thể gửi lại cùng yêu cầu."),
        },
    )
    def post(self, request, slug: str):
        if request.user.role not in {"admin_big", "admin_small"}:
            return Response({"detail": "Chỉ Admin Big hoặc Admin Small được cấp ảnh giáo viên."}, status=403)
        serializer = TeacherAvatarFinalizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = complete_teacher_avatar_upload(
                request.user,
                slug,
                serializer.validated_data["setup_token"],
                serializer.validated_data["intent_token"],
                serializer.validated_data["public_id"],
                request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except AvatarInvalidIntent as exc:
            return Response({"detail": str(exc)}, status=400)
        except AvatarInvalidUpload as exc:
            return Response({"detail": str(exc)}, status=400)
        except AvatarTargetNotFound:
            return Response({"detail": "Không tìm thấy giáo viên."}, status=404)
        except AvatarConflict as exc:
            return Response({"detail": str(exc)}, status=409)
        except AvatarUnavailable as exc:
            return Response(
                {"detail": str(exc), "complete": False, "missing_sites": list(exc.missing_sites)},
                status=503,
            )
        return Response(result, status=200)
