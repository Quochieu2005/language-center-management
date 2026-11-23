from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.academics.common import AcademicInfrastructureUnavailable, AcademicSiteUnavailable
from core.auth.authentication import AuthCookieAuthentication
from core.catalog.class_sessions import list_course_class_sessions
from core.catalog.serializers import (
    CourseClassSessionSummarySerializer,
    SharedCourseCreateSerializer,
    SharedCourseDeleteResponseSerializer,
    SharedCoursePatchSerializer,
    SharedCourseSyncRequestSerializer,
    SharedCourseSyncStatusSerializer,
    SharedCourseWriteResponseSerializer,
    PublicCourseListSerializer,
    SharedSubjectCreateSerializer,
    SharedSubjectDeleteResponseSerializer,
    SharedSubjectListSerializer,
    SharedSubjectPatchSerializer,
    SharedSubjectUpdateResponseSerializer,
)
from core.catalog.services import (
    SharedCatalogConflict,
    SharedCatalogNotFound,
    SharedCatalogUnavailable,
    update_shared_subject,
)
from core.catalog.subject_write_services import create_shared_subject, delete_shared_subject
from core.catalog.public_courses import list_public_courses, list_shared_subjects
from core.catalog.course_services import (
    create_shared_course,
    delete_shared_course,
    reconcile_pending_course_writes,
    update_shared_course,
)
from core.sites.connections import UnknownSiteError


_COURSE_MANAGEMENT_ROLES = {"admin_big", "tu_van", "ke_toan"}


def _catalog_idempotency_key(request):
    key = str(request.headers.get("Idempotency-Key", "")).strip()
    if len(key) < 8 or len(key) > 128 or not all(character.isalnum() or character in "._:-" for character in key):
        return None
    return key


def _catalog_write_error(exc):
    payload = {"detail": str(exc) or "Một site chưa sẵn sàng; chưa thể xác nhận ghi hoàn tất."}
    missing = getattr(exc, "missing_sites", ())
    if missing:
        payload["missing_sites"] = list(missing)
    return Response(payload, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class SharedCourseSyncView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "shared_catalog_write"

    @extend_schema(
        operation_id="admin_shared_course_reconcile",
        tags=["Danh mục dùng chung"],
        summary="Đối soát và tiếp tục đồng bộ khóa học đang chờ",
        description=(
            "Admin Big, Tư vấn & xếp lớp hoặc Kế toán & Lễ tân. Đọc ý định đồng bộ trong Logs "
            "tại site cấu hình AUTH_SESSION_SITE_CODE, "
            "thử áp dụng các site còn thiếu theo ACK idempotent. Mỗi CSDL ghi trong transaction cục bộ; "
            "không báo hoàn tất khi còn site chưa xác nhận. Giao diện gọi khi mở trang/định kỳ; management command "
            "sync_courses cũng retry nền mỗi 5 giây khi được chạy cùng API. "
            "Có thể truyền operation_id để yêu cầu đối soát lại một thao tác đang ở trạng thái cần đối soát."
        ),
        request=SharedCourseSyncRequestSerializer,
        responses={
            200: SharedCourseSyncStatusSerializer,
            400: OpenApiResponse(description="operation_id không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Vai trò hiện tại không được quản lý khóa học."),
            404: OpenApiResponse(description="Không tìm thấy thao tác cần đối soát."),
            503: OpenApiResponse(description="Site điều phối chưa sẵn sàng."),
        },
    )
    def post(self, request):
        if request.user.role not in _COURSE_MANAGEMENT_ROLES:
            return Response({"detail": "Vai trò hiện tại không được quản lý khóa học."}, status=403)
        serializer = SharedCourseSyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        operation_id = serializer.validated_data.get("operation_id")
        try:
            return Response(reconcile_pending_course_writes(operation_id=operation_id or None))
        except SharedCatalogNotFound as exc:
            return Response({"detail": str(exc)}, status=404)
        except SharedCatalogUnavailable as exc:
            return _catalog_write_error(exc)
        except DatabaseError:
            return Response(
                {"detail": "Không đọc được hàng đợi đồng bộ khóa học; yêu cầu vẫn được giữ để thử lại."},
                status=503,
            )


def _shared_subject_slug(value):
    slug = str(value or "").strip().lower()
    if (
        not slug
        or len(slug) > 120
        or any(not character.isascii() or not (character.islower() or character.isdigit() or character == "-") for character in slug)
        or slug.startswith("-")
        or slug.endswith("-")
        or "--" in slug
    ):
        return None
    return slug


class PublicCourseListView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="public_course_list",
        tags=["Khóa học"],
        summary="Danh sách khóa học và cơ sở đang mở lớp",
        description=(
            "Global Query chỉ đọc từng CSDL site riêng, kiểm tra bản sao danh mục dùng chung, "
            "rồi tổng hợp kết quả trong API. Cơ sở chỉ xuất hiện khi có lớp còn chỗ ở trạng thái "
            "sắp mở hoặc đang học. Trả complete=false nếu thiếu site hoặc bản sao không thống nhất."
        ),
        responses={
            200: PublicCourseListSerializer,
            503: OpenApiResponse(description="Không đọc được danh sách site hoặc CSDL site nào."),
        },
    )
    def get(self, request):
        try:
            return Response(list_public_courses())
        except SharedCatalogUnavailable as exc:
            return Response(
                {"detail": str(exc), "complete": False,
                 "missing_sites": list(getattr(exc, "missing_sites", ()))},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class SharedSubjectCollectionView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "shared_catalog_write"

    @extend_schema(
        operation_id="admin_shared_subject_list",
        tags=["Danh mục dùng chung"],
        summary="Liệt kê môn học dùng chung đã đối chiếu các site",
        description=(
            "Admin Big, Tư vấn & xếp lớp và Kế toán & Lễ tân được xem. Global Query đọc MonHoc riêng tại từng site đang hoạt động, "
            "đối chiếu các bản sao và tổng hợp danh sách ở tầng API. Trả complete=false "
            "kèm site thiếu hoặc lệch; không ghi dữ liệu."
        ),
        responses={
            200: SharedSubjectListSerializer,
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Vai trò hiện tại không được xem danh mục môn học."),
            503: OpenApiResponse(description="Không đọc được danh sách site hoặc CSDL site nào."),
        },
    )
    def get(self, request):
        if request.user.role not in _COURSE_MANAGEMENT_ROLES:
            return Response(
                {"detail": "Vai trò hiện tại không được xem danh mục môn học."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            return Response(list_shared_subjects())
        except SharedCatalogUnavailable as exc:
            return Response(
                {
                    "detail": str(exc),
                    "complete": False,
                    "missing_sites": list(getattr(exc, "missing_sites", ())),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    @extend_schema(
        operation_id="admin_shared_subject_create",
        tags=["Danh mục dùng chung"],
        summary="Tạo môn học dùng chung và nhân bản tới các site hoạt động",
        description=(
            "Chỉ Admin Big. API ghi MonHoc và biên nhận Logs tại Publisher cấu hình; SQL Server "
            "Publication truyền tới Subscriber. Sau commit, đọc từng site hoạt động để xác nhận. "
            "Trả 202 nếu chưa nhận đủ; retry cùng key/body chỉ kiểm tra lại, không ghi lại. "
            "Biên nhận tại Publisher không chứng minh Subscriber đã nhận. Không phải ACID xuyên site."
        ),
        parameters=[OpenApiParameter(
            "Idempotency-Key", str, OpenApiParameter.HEADER, required=True,
            description="8–128 ký tự; giữ nguyên key và body khi retry.",
        )],
        request=SharedSubjectCreateSerializer,
        responses={
            201: SharedSubjectUpdateResponseSerializer,
            202: SharedSubjectUpdateResponseSerializer,
            400: OpenApiResponse(description="Dữ liệu môn học hoặc Idempotency-Key không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big được quản lý danh mục dùng chung."),
            409: OpenApiResponse(description="Mã/slug trùng hoặc các bản sao đang lệch."),
            503: OpenApiResponse(description="Một site chưa sẵn sàng hoặc cần retry/đối soát."),
        },
    )
    def post(self, request):
        if request.user.role != "admin_big":
            return Response({"detail": "Chỉ Admin Big được quản lý danh mục dùng chung."}, status=403)
        key = _catalog_idempotency_key(request)
        if not key:
            return Response({"detail": "Idempotency-Key phải có 8–128 ký tự chữ, số hoặc . _ : -."}, status=400)
        serializer = SharedSubjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = create_shared_subject(
                subject=serializer.validated_data,
                idempotency_key=key,
                actor_id=str(request.user.account_id),
            )
        except SharedCatalogConflict as exc:
            return Response({"detail": str(exc)}, status=409)
        except SharedCatalogUnavailable as exc:
            return _catalog_write_error(exc)
        except DatabaseError:
            return Response(
                {"detail": "Không xác nhận được kết quả ghi; retry đúng nội dung với cùng Idempotency-Key."},
                status=503,
            )
        return Response(result, status=201 if result["complete"] else 202)


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
            "Chỉ Admin Big. API chỉ cập nhật MonHoc và biên nhận Logs tại Publisher; SQL Server "
            "Publication chuyển bản sao. Kiểm tra mã, slug, nội dung và phiên bản từng site sau commit. "
            "Trả 202 complete=false khi chưa nhận đủ. Retry cùng key/body chỉ đối soát, không tăng "
            "phiên bản lần nữa. Không dùng AUTH_SESSION_SITE_CODE để chọn Publisher."
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
        normalized_slug = _shared_subject_slug(slug)
        if not normalized_slug:
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

    @extend_schema(
        operation_id="admin_shared_subject_delete",
        tags=["Danh mục dùng chung"],
        summary="Xóa môn học dùng chung khỏi các site hoạt động",
        description=(
            "Chỉ Admin Big. Chỉ xóa khi không có khóa học nào tham chiếu môn tại bất kỳ site nào. "
            "Chỉ xóa MonHoc và ghi biên nhận Logs tại Publisher trong transaction cục bộ; "
            "SQL Server Publication truyền lệnh xóa. Bắt buộc Idempotency-Key. Trả 202 nếu còn bản sao "
            "chưa mất; retry cùng key chỉ đối soát. Không tuyên bố ACID nguyên tử xuyên CSDL."
        ),
        parameters=[
            OpenApiParameter("slug", str, OpenApiParameter.PATH),
            OpenApiParameter(
                "Idempotency-Key", str, OpenApiParameter.HEADER, required=True,
                description="8–128 ký tự; dùng lại cùng key nếu cần retry.",
            ),
        ],
        responses={
            200: SharedSubjectDeleteResponseSerializer,
            202: SharedSubjectDeleteResponseSerializer,
            400: OpenApiResponse(description="Slug hoặc Idempotency-Key không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Chỉ Admin Big được xóa danh mục dùng chung."),
            404: OpenApiResponse(description="Không tìm thấy môn học."),
            409: OpenApiResponse(description="Môn học đang được khóa học dùng hoặc bản sao bị lệch."),
            503: OpenApiResponse(description="Một site chưa sẵn sàng hoặc cần retry/đối soát."),
        },
    )
    def delete(self, request, slug):
        if request.user.role != "admin_big":
            return Response({"detail": "Chỉ Admin Big được xóa danh mục dùng chung."}, status=403)
        normalized_slug = _shared_subject_slug(slug)
        if not normalized_slug:
            return Response({"detail": "Slug môn học không hợp lệ."}, status=400)
        key = _catalog_idempotency_key(request)
        if not key:
            return Response({"detail": "Idempotency-Key phải có 8–128 ký tự chữ, số hoặc . _ : -."}, status=400)
        try:
            result = delete_shared_subject(
                slug=normalized_slug,
                idempotency_key=key,
                actor_id=str(request.user.account_id),
            )
        except SharedCatalogNotFound as exc:
            return Response({"detail": str(exc)}, status=404)
        except SharedCatalogConflict as exc:
            return Response({"detail": str(exc)}, status=409)
        except SharedCatalogUnavailable as exc:
            return _catalog_write_error(exc)
        except DatabaseError:
            return Response(
                {"detail": "Không xác nhận được kết quả xóa; retry đúng yêu cầu với cùng Idempotency-Key."},
                status=503,
            )
        return Response(result, status=200 if result["complete"] else 202)


class SharedCourseCollectionView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "shared_catalog_write"

    @extend_schema(
        operation_id="admin_shared_course_create",
        tags=["Danh mục dùng chung"],
        summary="Tạo khóa học và đồng bộ tới các site hoạt động",
        description=(
            "Admin Big, Tư vấn & xếp lớp hoặc Kế toán & Lễ tân. Ghi KhoaHoc và ACK Logs trong transaction cục bộ "
            "ở từng site đang kết nối; mã môn phải tồn tại và nhất quán trên các site đang kết nối. Trước khi ghi, "
            "API lưu ý định vào Logs append-only tại site cấu hình AUTH_SESSION_SITE_CODE. Nếu một site khác "
            "đang mất kết nối, API vẫn ghi các site hiện có và trả 202; endpoint POST /admin/courses/sync/ thử lại "
            "khi kết nối phục hồi. Nếu site điều phối mất kết nối hoặc các bản sao đang lệch, không nhận yêu cầu mới. "
            "Bắt buộc Idempotency-Key. Đây là fan-out có log ý định và transaction cục bộ, không phải ACID xuyên CSDL."
        ),
        parameters=[OpenApiParameter(
            "Idempotency-Key", str, OpenApiParameter.HEADER, required=True,
            description="8–128 ký tự; giữ nguyên key và body khi retry.",
        )],
        request=SharedCourseCreateSerializer,
        responses={
            201: SharedCourseWriteResponseSerializer,
            202: SharedCourseWriteResponseSerializer,
            400: OpenApiResponse(description="Dữ liệu khóa học hoặc Idempotency-Key không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Vai trò hiện tại không được quản lý khóa học."),
            404: OpenApiResponse(description="Môn học không tồn tại ở mọi site hoạt động."),
            409: OpenApiResponse(description="Mã/slug trùng, bản sao lệch hoặc key/body xung đột."),
            503: OpenApiResponse(description="Site điều phối/Logs chưa sẵn sàng hoặc dữ liệu hiện có cần đối soát."),
        },
    )
    def post(self, request):
        if request.user.role not in _COURSE_MANAGEMENT_ROLES:
            return Response({"detail": "Vai trò hiện tại không được quản lý khóa học."}, status=403)
        key = _catalog_idempotency_key(request)
        if not key:
            return Response({"detail": "Idempotency-Key phải có 8–128 ký tự chữ, số hoặc . _ : -."}, status=400)
        serializer = SharedCourseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = create_shared_course(
                course=serializer.validated_data,
                idempotency_key=key,
                actor_id=str(request.user.account_id),
            )
        except SharedCatalogNotFound as exc:
            return Response({"detail": str(exc)}, status=404)
        except SharedCatalogConflict as exc:
            return Response({"detail": str(exc)}, status=409)
        except SharedCatalogUnavailable as exc:
            return _catalog_write_error(exc)
        except DatabaseError:
            return Response(
                {"detail": "Không xác nhận được kết quả ghi; kiểm tra trạng thái rồi retry cùng Idempotency-Key."},
                status=503,
            )
        return Response(result, status=status.HTTP_201_CREATED if result["complete"] else status.HTTP_202_ACCEPTED)


class SharedCourseDetailView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "shared_catalog_write"

    @extend_schema(
        operation_id="admin_shared_course_update",
        tags=["Danh mục dùng chung"],
        summary="Cập nhật khóa học và đồng bộ tới các site hoạt động",
        description=(
            "Admin Big, Tư vấn & xếp lớp hoặc Kế toán & Lễ tân được sửa thông tin khóa học, bao gồm mã khóa học. Khi đổi mã, "
            "các lớp đang tham chiếu được cập nhật trong cùng transaction tại từng site. API lưu ý định vào "
            "Logs trên site AUTH_SESSION_SITE_CODE, rồi ghi KhoaHoc cùng ACK Logs tại các site đang kết nối. "
            "Nếu thiếu site khác, trả 202 và endpoint POST /admin/courses/sync/ sẽ thử lại khi site hoạt động. "
            "Site điều phối không sẵn sàng hoặc các bản sao đang lệch thì không nhận yêu cầu mới. Giữ nguyên "
            "Idempotency-Key và body khi retry; đây không phải transaction ACID xuyên CSDL."
        ),
        parameters=[
            OpenApiParameter("slug", str, OpenApiParameter.PATH),
            OpenApiParameter(
                "Idempotency-Key", str, OpenApiParameter.HEADER, required=True,
                description="8–128 ký tự; giữ nguyên key và body khi retry.",
            ),
        ],
        request=SharedCoursePatchSerializer,
        responses={
            200: SharedCourseWriteResponseSerializer,
            202: SharedCourseWriteResponseSerializer,
            400: OpenApiResponse(description="Slug, body hoặc Idempotency-Key không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Vai trò hiện tại không được quản lý khóa học."),
            404: OpenApiResponse(description="Không tìm thấy khóa học hoặc môn học."),
            409: OpenApiResponse(description="Bản sao lệch hoặc Idempotency-Key/body xung đột."),
            503: OpenApiResponse(description="Site điều phối/Logs chưa sẵn sàng hoặc dữ liệu hiện có cần đối soát."),
        },
    )
    def patch(self, request, slug):
        if request.user.role not in _COURSE_MANAGEMENT_ROLES:
            return Response({"detail": "Vai trò hiện tại không được quản lý khóa học."}, status=403)
        slug = str(slug or "").strip().lower()
        if (
            len(slug) > 160 or not slug
            or any(not (character.islower() or character.isdigit() or character == "-") for character in slug)
            or slug.startswith("-") or slug.endswith("-") or "--" in slug
        ):
            return Response({"detail": "Slug khóa học không hợp lệ."}, status=400)
        key = _catalog_idempotency_key(request)
        if not key:
            return Response({"detail": "Idempotency-Key phải có 8–128 ký tự chữ, số hoặc . _ : -."}, status=400)
        serializer = SharedCoursePatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = update_shared_course(
                slug=slug,
                patch=serializer.validated_data,
                idempotency_key=key,
                actor_id=str(request.user.account_id),
            )
        except SharedCatalogNotFound as exc:
            return Response({"detail": str(exc)}, status=404)
        except SharedCatalogConflict as exc:
            return Response({"detail": str(exc)}, status=409)
        except SharedCatalogUnavailable as exc:
            return _catalog_write_error(exc)
        except DatabaseError:
            return Response(
                {"detail": "Không xác nhận được kết quả ghi; kiểm tra trạng thái rồi retry cùng Idempotency-Key."},
                status=503,
            )
        return Response(result, status=200 if result["complete"] else 202)

    @extend_schema(
        operation_id="admin_shared_course_delete",
        tags=["Danh mục dùng chung"],
        summary="Xóa khóa học và đồng bộ tới các site hoạt động",
        description=(
            "Admin Big, Tư vấn & xếp lớp hoặc Kế toán & Lễ tân. API lưu ý định xóa vào hàng đợi điều phối. Nếu thiếu site, "
            "trả 202 và chưa xóa ở bất kỳ site nào; khi đủ kết nối, hệ thống kiểm tra LopHoc tham chiếu tại mọi site rồi mới xóa. "
            "Nếu lớp đang dùng khóa học, yêu cầu cần đối soát và không xóa. Mỗi site ghi ACK append-only vào Logs cùng KhoaHoc "
            "trong transaction cục bộ. Dùng Idempotency-Key khi retry; đây không phải ACID xuyên CSDL."
        ),
        parameters=[
            OpenApiParameter("slug", str, OpenApiParameter.PATH),
            OpenApiParameter(
                "Idempotency-Key", str, OpenApiParameter.HEADER, required=True,
                description="8–128 ký tự; giữ nguyên key khi retry.",
            ),
        ],
        responses={
            200: SharedCourseDeleteResponseSerializer,
            202: SharedCourseDeleteResponseSerializer,
            400: OpenApiResponse(description="Slug hoặc Idempotency-Key không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Vai trò hiện tại không được quản lý khóa học."),
            404: OpenApiResponse(description="Không tìm thấy khóa học."),
            409: OpenApiResponse(description="Khóa học đang được lớp sử dụng hoặc các bản sao không thống nhất."),
            503: OpenApiResponse(description="Site điều phối/Logs chưa sẵn sàng hoặc dữ liệu hiện có cần đối soát."),
        },
    )
    def delete(self, request, slug):
        if request.user.role not in _COURSE_MANAGEMENT_ROLES:
            return Response({"detail": "Vai trò hiện tại không được quản lý khóa học."}, status=403)
        slug = str(slug or "").strip().lower()
        if (
            len(slug) > 160 or not slug
            or any(not (character.islower() or character.isdigit() or character == "-") for character in slug)
            or slug.startswith("-") or slug.endswith("-") or "--" in slug
        ):
            return Response({"detail": "Slug khóa học không hợp lệ."}, status=400)
        key = _catalog_idempotency_key(request)
        if not key:
            return Response({"detail": "Idempotency-Key phải có 8–128 ký tự chữ, số hoặc . _ : -."}, status=400)
        try:
            result = delete_shared_course(
                slug=slug,
                idempotency_key=key,
                actor_id=str(request.user.account_id),
            )
        except SharedCatalogNotFound as exc:
            return Response({"detail": str(exc)}, status=404)
        except SharedCatalogConflict as exc:
            return Response({"detail": str(exc)}, status=409)
        except SharedCatalogUnavailable as exc:
            return _catalog_write_error(exc)
        except DatabaseError:
            return Response(
                {"detail": "Không xác nhận được kết quả xóa; kiểm tra trạng thái rồi retry cùng Idempotency-Key."},
                status=503,
            )
        return Response(result, status=status.HTTP_200_OK if result["complete"] else status.HTTP_202_ACCEPTED)


class CourseClassSessionSummaryView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "report_read"

    @extend_schema(
        operation_id="admin_course_class_session_summary",
        tags=["Khóa học"],
        summary="Đếm buổi học đã tạo theo từng lớp",
        description=(
            "Admin Big đọc GLOBAL từ LopHoc và BuoiHoc ở từng CSDL site hoạt động rồi tổng hợp trong API; "
            "Tư vấn & xếp lớp và Kế toán & Lễ tân chỉ đọc LOCAL tại site gắn với phiên. "
            "Số buổi là số dòng BuoiHoc đã tạo cho từng lớp, không cập nhật KhoaHoc.so_buoi. "
            "Nếu thiếu site, trả complete=false và missing_sites."
        ),
        responses={
            200: CourseClassSessionSummarySerializer,
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Không có quyền xem lịch lớp."),
            404: OpenApiResponse(description="Cơ sở được phân công không còn hoạt động."),
            503: OpenApiResponse(description="Không đọc được CSDL của cơ sở được phân công."),
        },
    )
    def get(self, request):
        try:
            result = list_course_class_sessions(
                role=request.user.role,
                user_site_code=request.user.site_code,
            )
        except PermissionError:
            return Response({"detail": "Vai trò hiện tại không được xem số buổi theo lớp."}, status=403)
        except AcademicSiteUnavailable:
            if request.user.role == "admin_big":
                return Response({"detail": "Không xác định được danh sách cơ sở hoạt động."}, status=503)
            return Response({"detail": "Cơ sở được phân công không còn hoạt động."}, status=404)
        except (AcademicInfrastructureUnavailable, DatabaseError, ImproperlyConfigured, KeyError, UnknownSiteError):
            return Response(
                {"detail": "Không đọc được lịch lớp tại cơ sở; số buổi theo lớp chưa tải được."},
                status=503,
            )
        return Response(result)
