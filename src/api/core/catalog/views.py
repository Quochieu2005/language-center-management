from django.db import DatabaseError
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.auth.authentication import AuthCookieAuthentication
from core.catalog.serializers import SharedSubjectPatchSerializer, SharedSubjectUpdateResponseSerializer
from core.catalog.services import (
    SharedCatalogConflict,
    SharedCatalogNotFound,
    SharedCatalogUnavailable,
    update_shared_subject,
)


class SharedSubjectDetailView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "shared_catalog_write"

    @extend_schema(
        operation_id="admin_shared_subject_update",
        tags=["Danh mục dùng chung"],
        summary="Cập nhật môn học và nhân bản tới các site hoạt động",
        description=(
            "Chỉ Admin Big được ghi. Coordinator kiểm tra tất cả site hoạt động, khóa thao tác "
            "cùng slug, rồi cập nhật MonHoc và ghi ACK append-only vào dbo.Logs trong cùng "
            "transaction cục bộ tại từng CSDL. Bắt buộc gửi Idempotency-Key; nếu thiếu site "
            "tạm thời ở giữa quá trình, API trả 202 complete=false và yêu cầu retry cùng key/body. "
            "Đây là replication tầng ứng dụng, không phải SQL Server Publication/2PC."
        ),
        parameters=[
            OpenApiParameter("slug", str, OpenApiParameter.PATH),
            OpenApiParameter(
                "Idempotency-Key", str, OpenApiParameter.HEADER, required=True,
                description="8–128 ký tự; dùng lại chính xác key và body khi retry.",
            ),
        ],
        request=SharedSubjectPatchSerializer,
        responses={
            200: SharedSubjectUpdateResponseSerializer,
            202: SharedSubjectUpdateResponseSerializer,
            400: OpenApiResponse(description="Slug, body hoặc Idempotency-Key không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big được cập nhật danh mục dùng chung."),
            404: OpenApiResponse(description="Không tìm thấy môn học ở một hoặc nhiều site."),
            409: OpenApiResponse(description="Idempotency-Key bị dùng lại với body khác hoặc bản sao đang lệch."),
            503: OpenApiResponse(description="Site bắt buộc chưa sẵn sàng hoặc thao tác cần đối soát."),
        },
    )
    def patch(self, request, slug):
        if request.user.role != "admin_big":
            return Response(
                {"detail": "Chỉ Admin Big được cập nhật danh mục dùng chung."},
                status=status.HTTP_403_FORBIDDEN,
            )
        normalized_slug = str(slug or "").strip().lower()
        if (
            len(normalized_slug) > 120
            or not normalized_slug
            or any(not (character.islower() or character.isdigit() or character == "-") for character in normalized_slug)
            or normalized_slug.startswith("-")
            or normalized_slug.endswith("-")
            or "--" in normalized_slug
        ):
            return Response({"detail": "Slug môn học không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)

        key = str(request.headers.get("Idempotency-Key", "")).strip()
        if len(key) < 8 or len(key) > 128 or not all(character.isalnum() or character in "._:-" for character in key):
            return Response(
                {"detail": "Idempotency-Key phải có 8–128 ký tự chữ, số hoặc . _ : -."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = SharedSubjectPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = update_shared_subject(
                slug=normalized_slug,
                patch=serializer.validated_data,
                idempotency_key=key,
                actor_id=str(request.user.account_id),
            )
        except SharedCatalogNotFound:
            return Response({"detail": "Không tìm thấy môn học ở mọi site hoạt động."}, status=404)
        except SharedCatalogConflict as exc:
            return Response({"detail": str(exc)}, status=409)
        except SharedCatalogUnavailable as exc:
            payload = {"detail": str(exc) or "CSDL site chưa sẵn sàng; chưa xác nhận hoàn tất."}
            missing = getattr(exc, "missing_sites", ())
            if missing:
                payload["missing_sites"] = list(missing)
            return Response(payload, status=503)
        except DatabaseError:
            return Response(
                {"detail": "Không xác nhận được kết quả ghi; kiểm tra trạng thái rồi retry cùng Idempotency-Key."},
                status=503,
            )
        return Response(result, status=status.HTTP_200_OK if result["complete"] else status.HTTP_202_ACCEPTED)
