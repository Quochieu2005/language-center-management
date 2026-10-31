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
    AvatarUnavailable,
    complete_admin_avatar_upload,
    create_admin_avatar_upload_intent,
)
from core.media.serializers import (
    AdminAvatarFinalizeRequestSerializer,
    AdminAvatarResponseSerializer,
    AdminAvatarUploadIntentResponseSerializer,
)


@method_decorator(csrf_protect, name="dispatch")
class AdminAvatarUploadIntentView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "profile_avatar"

    @extend_schema(
        operation_id="admin_profile_avatar_upload_intent",
        tags=["Quản lý tài khoản"],
        summary="Cấp chữ ký Cloudinary tải ảnh cho hồ sơ admin hiện tại",
        description=(
            "Chỉ Admin Big hoặc Admin Small được tạo chữ ký cho tài khoản của chính mình. "
            "API không nhận account_id/site từ client; ảnh tải thẳng lên Cloudinary, khóa API secret "
            "không rời máy chủ. Metadata TaiKhoan được đồng bộ tại bước hoàn tất."
        ),
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        request=EmptyRequestSerializer,
        responses={
            200: AdminAvatarUploadIntentResponseSerializer,
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big và Admin Small được tải ảnh."),
            404: OpenApiResponse(description="Slug không thuộc tài khoản hiện tại."),
            409: OpenApiResponse(description="Tài khoản hoặc ảnh ở các site chưa đồng nhất."),
            429: OpenApiResponse(description="Vượt giới hạn cấp chữ ký."),
            503: OpenApiResponse(description="Cloudinary, migration hoặc một site chưa sẵn sàng."),
        },
    )
    def post(self, request, slug: str):
        if request.user.role not in {"admin_big", "admin_small"}:
            return Response({"detail": "Chỉ Admin Big và Admin Small được tải ảnh."}, status=403)
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
        operation_id="admin_profile_avatar_complete",
        tags=["Quản lý tài khoản"],
        summary="Xác minh ảnh Cloudinary và đồng bộ hồ sơ admin qua các site",
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
            403: OpenApiResponse(description="Chỉ Admin Big và Admin Small được đổi ảnh."),
            404: OpenApiResponse(description="Slug không thuộc tài khoản hiện tại."),
            409: OpenApiResponse(description="Ảnh hoặc metadata giữa các site bị xung đột."),
            429: OpenApiResponse(description="Vượt giới hạn hoàn tất tải ảnh."),
            503: OpenApiResponse(description="Cloudinary hoặc một site chưa sẵn sàng; có thể thử lại."),
        },
    )
    def post(self, request, slug: str):
        if request.user.role not in {"admin_big", "admin_small"}:
            return Response({"detail": "Chỉ Admin Big và Admin Small được đổi ảnh."}, status=403)
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
