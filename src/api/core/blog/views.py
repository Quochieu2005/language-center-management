from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.auth.authentication import AuthCookieAuthentication
from core.blog.serializers import (
    AdminBlogArticleDetailResponseSerializer,
    AdminBlogCategoryDetailResponseSerializer,
    AdminBlogListResponseSerializer,
    BlogArticleCreateSerializer,
    BlogArticlePatchSerializer,
    BlogCategoryCreateSerializer,
    BlogCategoryPatchSerializer,
    BlogWriteResponseSerializer,
    BlogImageCompleteRequestSerializer,
    BlogImageCompleteResponseSerializer,
    BlogImageIntentRequestSerializer,
    PublicBlogArticlesResponseSerializer,
    PublicBlogCategoriesResponseSerializer,
    PublicBlogDetailResponseSerializer,
)
from core.blog.images import complete_blog_image, create_blog_image_intent
from core.media.avatars import AvatarInvalidIntent, AvatarInvalidUpload, AvatarUnavailable
from core.media.serializers import AdminAvatarUploadIntentResponseSerializer
from core.blog.services import (
    PublicBlogConflict,
    PublicBlogNotFound,
    PublicBlogUnavailable,
    get_admin_blog_article,
    get_admin_blog_category,
    get_public_blog_article,
    list_admin_blog_articles,
    list_admin_blog_categories,
    list_public_blog_articles,
    list_public_blog_categories,
)
from core.blog.write_services import (
    create_blog_article,
    create_blog_category,
    delete_blog_article,
    delete_blog_category,
    update_blog_article,
    update_blog_category,
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


def _admin_blog_error(exc, *, scope="REPLICATED-WRITE"):
    payload = {
        "detail": str(exc), "scope": scope, "complete": False,
        "site_codes": list(exc.site_codes),
    }
    if isinstance(exc, PublicBlogNotFound):
        payload["complete"] = bool(exc.site_codes)
    if exc.missing_sites:
        payload["missing_sites"] = list(exc.missing_sites)
    if exc.inconsistent_sites:
        payload["inconsistent_sites"] = list(exc.inconsistent_sites)
    code = (
        status.HTTP_404_NOT_FOUND if isinstance(exc, PublicBlogNotFound)
        else status.HTTP_409_CONFLICT if isinstance(exc, PublicBlogConflict)
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return Response(payload, status=code)


def _blog_idempotency_key(request):
    key = str(request.headers.get("Idempotency-Key", "")).strip()
    if len(key) < 8 or len(key) > 128 or not all(character.isalnum() or character in "._:-" for character in key):
        return None
    return key


def _blog_roles_only(request, roles=("admin_big",)):
    if request.user.role not in roles:
        return Response({"detail": "Bạn không có quyền thao tác CMS Blog này."}, status=status.HTTP_403_FORBIDDEN)
    return None


def _admin_big_only(request):
    return _blog_roles_only(request)


def _write_blog_response(request, serializer_class, operation, *, slug=None, created=False, roles=("admin_big",)):
    denied = _blog_roles_only(request, roles)
    if denied:
        return denied
    key = _blog_idempotency_key(request)
    if not key:
        return Response({"detail": "Header Idempotency-Key phải dài 8–128 ký tự hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)
    serializer = serializer_class(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        arguments = {"idempotency_key": key, "actor_id": request.user.account_id}
        if slug is not None:
            arguments["slug"] = slug
        result = operation(payload=serializer.validated_data, **arguments)
    except (PublicBlogConflict, PublicBlogNotFound, PublicBlogUnavailable) as exc:
        return _admin_blog_error(exc)
    return Response(result, status=status.HTTP_201_CREATED if created and result["complete"] and not result["idempotent_replay"]
                    else status.HTTP_202_ACCEPTED if not result["complete"] else status.HTTP_200_OK)


def _read_admin_blog(request, reader, *, roles=("admin_big",)):
    denied = _blog_roles_only(request, roles)
    if denied:
        return denied
    try:
        return Response(reader())
    except (PublicBlogConflict, PublicBlogNotFound, PublicBlogUnavailable) as exc:
        return _admin_blog_error(exc, scope="GLOBAL")


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


class PublicBlogArticlesView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="public_blog_articles",
        tags=["Blog"],
        summary="Liệt kê bài Blog đã xuất bản",
        description="Global Query chỉ đọc; trả bài đã xuất bản mới nhất trước, từ các site đang kết nối được.",
        responses={200: PublicBlogArticlesResponseSerializer, 503: OpenApiResponse(description="Không site nào đọc được.")},
    )
    def get(self, request):
        try:
            return Response(list_public_blog_articles())
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


class _AdminBlogView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "shared_catalog_write"


class AdminBlogCategoryCollectionView(_AdminBlogView):
    @extend_schema(operation_id="admin_blog_categories_list", tags=["Blog"], summary="Liệt kê danh mục Blog cho Admin Big và Tư vấn & xếp lớp", responses={200: AdminBlogListResponseSerializer})
    def get(self, request):
        return _read_admin_blog(request, list_admin_blog_categories, roles=("admin_big", "tu_van"))

    @extend_schema(operation_id="admin_blog_category_create", tags=["Blog"], summary="Tạo danh mục Blog trên mọi site hoạt động", request=BlogCategoryCreateSerializer, responses={201: BlogWriteResponseSerializer, 202: BlogWriteResponseSerializer})
    def post(self, request):
        return _write_blog_response(
            request, BlogCategoryCreateSerializer,
            lambda *, payload, **kwargs: create_blog_category(category=payload, **kwargs), created=True,
        )


class AdminBlogCategoryDetailView(_AdminBlogView):
    @extend_schema(operation_id="admin_blog_category_detail", tags=["Blog"], summary="Đọc danh mục Blog cho Admin Big", responses={200: AdminBlogCategoryDetailResponseSerializer, 404: OpenApiResponse(description="Không tìm thấy danh mục."), 409: OpenApiResponse(description="Bản sao danh mục lệch."), 503: OpenApiResponse(description="Thiếu site hoạt động.")})
    def get(self, request, slug):
        denied = _admin_big_only(request)
        if denied:
            return denied
        try:
            return Response(get_admin_blog_category(slug))
        except (PublicBlogConflict, PublicBlogNotFound, PublicBlogUnavailable) as exc:
            return _admin_blog_error(exc, scope="GLOBAL")

    @extend_schema(operation_id="admin_blog_category_update", tags=["Blog"], summary="Sửa danh mục Blog trên mọi site hoạt động", request=BlogCategoryPatchSerializer, responses={200: BlogWriteResponseSerializer, 202: BlogWriteResponseSerializer})
    def patch(self, request, slug):
        return _write_blog_response(
            request, BlogCategoryPatchSerializer,
            lambda *, payload, **kwargs: update_blog_category(patch=payload, **kwargs), slug=slug,
        )

    @extend_schema(operation_id="admin_blog_category_delete", tags=["Blog"], summary="Xóa danh mục không có bài viết", responses={200: BlogWriteResponseSerializer, 202: BlogWriteResponseSerializer})
    def delete(self, request, slug):
        denied = _admin_big_only(request)
        if denied:
            return denied
        key = _blog_idempotency_key(request)
        if not key:
            return Response({"detail": "Header Idempotency-Key phải dài 8–128 ký tự hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = delete_blog_category(slug=slug, idempotency_key=key, actor_id=request.user.account_id)
        except (PublicBlogConflict, PublicBlogNotFound, PublicBlogUnavailable) as exc:
            return _admin_blog_error(exc)
        return Response(result, status=status.HTTP_200_OK if result["complete"] else status.HTTP_202_ACCEPTED)


class AdminBlogArticleCollectionView(_AdminBlogView):
    @extend_schema(operation_id="admin_blog_articles_list", tags=["Blog"], summary="Liệt kê bài Blog mọi trạng thái cho Admin Big và Tư vấn & xếp lớp", responses={200: AdminBlogListResponseSerializer})
    def get(self, request):
        return _read_admin_blog(request, list_admin_blog_articles, roles=("admin_big", "tu_van"))

    @extend_schema(operation_id="admin_blog_article_create", tags=["Blog"], summary="Admin Big hoặc Tư vấn & xếp lớp tạo bài Blog trên mọi site hoạt động", request=BlogArticleCreateSerializer, responses={201: BlogWriteResponseSerializer, 202: BlogWriteResponseSerializer})
    def post(self, request):
        return _write_blog_response(
            request, BlogArticleCreateSerializer,
            lambda *, payload, **kwargs: create_blog_article(article=payload, **kwargs), created=True,
            roles=("admin_big", "tu_van"),
        )


class AdminBlogArticleDetailView(_AdminBlogView):
    @extend_schema(operation_id="admin_blog_article_detail", tags=["Blog"], summary="Đọc bài Blog mọi trạng thái cho Admin Big và Tư vấn & xếp lớp", responses={200: AdminBlogArticleDetailResponseSerializer, 404: OpenApiResponse(description="Không tìm thấy bài viết."), 409: OpenApiResponse(description="Bản sao bài viết lệch."), 503: OpenApiResponse(description="Thiếu site hoạt động.")})
    def get(self, request, slug):
        denied = _blog_roles_only(request, ("admin_big", "tu_van"))
        if denied:
            return denied
        try:
            return Response(get_admin_blog_article(slug))
        except (PublicBlogConflict, PublicBlogNotFound, PublicBlogUnavailable) as exc:
            return _admin_blog_error(exc, scope="GLOBAL")

    @extend_schema(operation_id="admin_blog_article_update", tags=["Blog"], summary="Admin Big hoặc Tư vấn & xếp lớp sửa bài Blog trên mọi site hoạt động", request=BlogArticlePatchSerializer, responses={200: BlogWriteResponseSerializer, 202: BlogWriteResponseSerializer})
    def patch(self, request, slug):
        return _write_blog_response(
            request, BlogArticlePatchSerializer,
            lambda *, payload, **kwargs: update_blog_article(patch=payload, **kwargs), slug=slug,
            roles=("admin_big", "tu_van"),
        )

    @extend_schema(operation_id="admin_blog_article_delete", tags=["Blog"], summary="Xóa bài Blog trên mọi site hoạt động", responses={200: BlogWriteResponseSerializer, 202: BlogWriteResponseSerializer})
    def delete(self, request, slug):
        denied = _admin_big_only(request)
        if denied:
            return denied
        key = _blog_idempotency_key(request)
        if not key:
            return Response({"detail": "Header Idempotency-Key phải dài 8–128 ký tự hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = delete_blog_article(slug=slug, idempotency_key=key, actor_id=request.user.account_id)
        except (PublicBlogConflict, PublicBlogNotFound, PublicBlogUnavailable) as exc:
            return _admin_blog_error(exc)
        return Response(result, status=status.HTTP_200_OK if result["complete"] else status.HTTP_202_ACCEPTED)


def _image_error(exc):
    code = status.HTTP_503_SERVICE_UNAVAILABLE if isinstance(exc, AvatarUnavailable) else status.HTTP_400_BAD_REQUEST
    return Response({"detail": str(exc)}, status=code)


class _BlogImageView(_AdminBlogView):
    throttle_scope = "profile_avatar"

    def _guard(self, request):
        return _blog_roles_only(request, ("admin_big", "tu_van"))


class AdminBlogImageIntentView(_BlogImageView):
    @extend_schema(
        operation_id="admin_blog_image_intent", tags=["Blog"],
        summary="Xin chữ ký tải ảnh bìa hoặc ảnh trong bài Blog lên Cloudinary",
        request=BlogImageIntentRequestSerializer,
        responses={200: AdminAvatarUploadIntentResponseSerializer, 400: OpenApiResponse(), 403: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def post(self, request):
        denied = self._guard(request)
        if denied:
            return denied
        serializer = BlogImageIntentRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(create_blog_image_intent(request.user, **serializer.validated_data))
        except (AvatarInvalidIntent, AvatarInvalidUpload, AvatarUnavailable) as exc:
            return _image_error(exc)


class AdminBlogImageCompleteView(_BlogImageView):
    @extend_schema(
        operation_id="admin_blog_image_complete", tags=["Blog"],
        summary="Xác minh ảnh Blog đã tải lên Cloudinary và trả URL",
        request=BlogImageCompleteRequestSerializer,
        responses={200: BlogImageCompleteResponseSerializer, 400: OpenApiResponse(), 403: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def post(self, request):
        denied = self._guard(request)
        if denied:
            return denied
        serializer = BlogImageCompleteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(complete_blog_image(request.user, **serializer.validated_data))
        except (AvatarInvalidIntent, AvatarInvalidUpload, AvatarUnavailable) as exc:
            return _image_error(exc)
