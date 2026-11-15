from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.blog.serializers import (
    PublicBlogCategoriesResponseSerializer,
    PublicBlogDetailResponseSerializer,
)
from core.blog.services import (
    PublicBlogConflict,
    PublicBlogNotFound,
    PublicBlogUnavailable,
    get_public_blog_article,
    list_public_blog_categories,
)


def _blog_error(exc):
    payload = {
        "detail": str(exc),
        "scope": "GLOBAL",
        "complete": isinstance(exc, PublicBlogNotFound) and bool(exc.site_codes),
        "site_codes": list(exc.site_codes),
    }
    if exc.missing_sites:
        payload["missing_sites"] = list(exc.missing_sites)
    if exc.inconsistent_sites:
        payload["inconsistent_sites"] = list(exc.inconsistent_sites)
    return payload


class PublicBlogCategoriesView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="public_blog_categories",
        tags=["Blog"],
        summary="Liệt kê danh mục Blog",
        description=(
            "Global Query chỉ đọc từng CSDL site riêng và đối chiếu danh mục cùng số bài đã "
            "xuất bản. Trả complete=false nếu thiếu site hoặc dữ liệu không thống nhất; "
            "không đọc database trung tâm."
        ),
        responses={
            200: PublicBlogCategoriesResponseSerializer,
            503: OpenApiResponse(description="Không đọc được danh sách site hoặc Blog ở site nào."),
        },
    )
    def get(self, request):
        try:
            return Response(list_public_blog_categories())
        except PublicBlogUnavailable as exc:
            return Response(_blog_error(exc), status=status.HTTP_503_SERVICE_UNAVAILABLE)


class PublicBlogDetailView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="public_blog_detail",
        tags=["Blog"],
        summary="Lấy bài Blog đã xuất bản theo slug",
        description=(
            "Global Query đọc slug tại từng CSDL site riêng. Chỉ trả bài khi các bản sao "
            "khớp; slug không tồn tại trả 404, dữ liệu lệch giữa site trả 409, thiếu site trả 503."
        ),
        responses={
            200: PublicBlogDetailResponseSerializer,
            404: OpenApiResponse(description="Không tìm thấy bài đã xuất bản theo slug."),
            409: OpenApiResponse(description="Các bản Blog theo slug không nhất quán giữa site."),
            503: OpenApiResponse(description="Không đọc đủ site để xác nhận kết quả toàn cục."),
        },
    )
    def get(self, request, slug):
        try:
            return Response(get_public_blog_article(slug))
        except PublicBlogNotFound as exc:
            return Response(_blog_error(exc), status=status.HTTP_404_NOT_FOUND)
        except PublicBlogConflict as exc:
            return Response(_blog_error(exc), status=status.HTTP_409_CONFLICT)
        except PublicBlogUnavailable as exc:
            return Response(_blog_error(exc), status=status.HTTP_503_SERVICE_UNAVAILABLE)
