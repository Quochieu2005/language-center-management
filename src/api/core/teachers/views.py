from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.auth.authentication import AuthCookieAuthentication
from core.auth.account_status import (
    AccountStatusConflict,
    AccountStatusTargetNotFound,
    change_account_status,
)
from core.auth.serializers import AccountStatusResponseSerializer, AccountStatusUpdateSerializer
from core.auth.service_common import AuthInfrastructureUnavailable
from core.media.avatars import create_teacher_avatar_setup_token
from core.teachers.serializers import (
    TeacherCreateResponseSerializer,
    TeacherCreateSerializer,
    TeacherCredentialEmailResponseSerializer,
    TeacherDeleteResponseSerializer,
    TeacherListQuerySerializer,
    TeacherListResponseSerializer,
    TeacherProfileUpdateSerializer,
    TeacherResponseSerializer,
    TeacherSiteQuerySerializer,
)
from core.teachers.services import (
    TeacherConflict,
    TeacherInfrastructureUnavailable,
    TeacherNotFound,
    TeacherSiteUnavailable,
    create_teacher,
    deactivate_teacher,
    get_teacher,
    list_teachers,
    update_teacher,
)
from core.teachers.credential_email import (
    TeacherCredentialEmailConflict,
    TeacherCredentialEmailDeliveryFailed,
    TeacherCredentialEmailNotFound,
    TeacherCredentialEmailUncertain,
    send_teacher_credentials,
)


_ADMIN_ROLES = {"admin_big", "admin_small"}


def _site_scope(user, requested_site: str | None):
    if user.role not in _ADMIN_ROLES:
        return None, Response(
            {"detail": "Chỉ Admin Big hoặc Admin Small được quản lý giáo viên."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if user.role == "admin_small":
        own_site = str(user.site_code or "").upper()
        if not own_site or (requested_site and requested_site != own_site):
            return None, Response(
                {"detail": "Admin Small chỉ được truy cập cơ sở được phân công."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return own_site, None
    if not requested_site:
        return None, Response(
            {"detail": "Admin Big cần chọn site_code để quản lý giáo viên."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return requested_site, None


def _service_error(exc):
    if isinstance(exc, TeacherNotFound):
        return Response({"detail": "Không tìm thấy giáo viên trong cơ sở được chọn."}, status=404)
    if isinstance(exc, TeacherConflict):
        return Response(
            {"detail": "Thao tác xung đột với dữ liệu hiện tại; kiểm tra email, trạng thái giáo viên hoặc lớp đang mở."},
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, TeacherSiteUnavailable):
        return Response(
            {"detail": "Cơ sở không hoạt động hoặc không nằm trong cấu hình hiện tại."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {"detail": "CSDL site hoặc tiến trình đồng bộ chưa sẵn sàng; thao tác chưa được xác nhận hoàn tất."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _remote_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "") or "unknown"


@method_decorator(csrf_protect, name="dispatch")
class TeacherCollectionView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "teacher_management"

    def get_throttles(self):
        self.throttle_scope = "teacher_create" if self.request.method == "POST" else "teacher_management"
        return super().get_throttles()

    @extend_schema(
        operation_id="teacher_list",
        tags=["Quản lý giáo viên"],
        summary="Liệt kê giáo viên trong một cơ sở",
        description=(
            "Admin Big phải truyền site_code; Admin Small dùng site từ phiên đăng nhập và không được "
            "chọn site khác. Chỉ đọc CSDL riêng của site, không JOIN xuyên site. Hỗ trợ lọc status/search "
            "và phân trang limit/offset."
        ),
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
            OpenApiParameter("status", str, OpenApiParameter.QUERY),
            OpenApiParameter("search", str, OpenApiParameter.QUERY),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY),
            OpenApiParameter("offset", int, OpenApiParameter.QUERY),
        ],
        responses={
            200: TeacherListResponseSerializer,
            400: OpenApiResponse(description="Tham số lọc không hợp lệ hoặc Admin Big chưa chọn cơ sở."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Vai trò không được quản lý giáo viên hoặc vượt phạm vi site."),
            503: OpenApiResponse(description="Site/CSDL không sẵn sàng."),
        },
    )
    def get(self, request):
        query = TeacherListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        site_code, error = _site_scope(request.user, data.get("site_code"))
        if error:
            return error
        try:
            result = list_teachers(
                site_code=site_code,
                status_filter=data.get("status"),
                search=data.get("search"),
                limit=data["limit"],
                offset=data["offset"],
            )
        except (TeacherInfrastructureUnavailable, TeacherSiteUnavailable) as exc:
            return _service_error(exc)
        return Response(result)

    @extend_schema(
        operation_id="teacher_create",
        tags=["Quản lý giáo viên"],
        summary="Tạo giáo viên và tài khoản đăng nhập",
        description=(
            "Admin Big truyền site_code; Admin Small chỉ tạo tại site được xác thực. Hồ sơ GiaoVien "
            "nằm riêng ở site đó; TaiKhoan được ghi tại các site đang hoạt động và đồng bộ qua Logs (loai_log='sync'). "
            "Mật khẩu cấp ban đầu lấy từ cấu hình backend, được băm và không trả trong response. "
            "Không bắt buộc đổi ở lần đăng nhập đầu. Gửi thông tin đăng nhập qua endpoint riêng "
            "theo thao tác chủ động của quản trị viên; chỉ gửi một lần. Ảnh hồ sơ tải lên Cloudinary."
        ),
        request=TeacherCreateSerializer,
        responses={
            201: TeacherCreateResponseSerializer,
            400: OpenApiResponse(description="Thông tin hồ sơ hoặc site không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Vai trò không được tạo giáo viên hoặc Admin Small gửi site khác."),
            409: OpenApiResponse(description="Email/tên đăng nhập đã được sử dụng hoặc dữ liệu đang xung đột."),
            429: OpenApiResponse(description="Vượt giới hạn tạo giáo viên."),
            503: OpenApiResponse(description="Thiếu cấu hình mật khẩu tạm hoặc một site SQL Server chưa sẵn sàng."),
        },
    )
    def post(self, request):
        if request.user.role not in _ADMIN_ROLES:
            return Response(
                {"detail": "Chỉ Admin Big hoặc Admin Small được tạo giáo viên."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = TeacherCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if request.user.role == "admin_small" and data.get("site_code"):
            return Response(
                {"detail": "Admin Small không được chọn cơ sở trong request."},
                status=status.HTTP_403_FORBIDDEN,
            )
        site_code = data.get("site_code") if request.user.role == "admin_big" else request.user.site_code
        if not site_code:
            return Response({"detail": "Cần chọn cơ sở."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = create_teacher(
                full_name=data["full_name"],
                email=data["email"],
                username=data.get("username"),
                phone=data.get("phone"),
                slug=data["slug"],
                site_code=site_code,
                actor_id=request.user.account_id,
                remote_ip=_remote_ip(request),
            )
        except (TeacherInfrastructureUnavailable, TeacherSiteUnavailable, TeacherConflict) as exc:
            return _service_error(exc)
        avatar_setup_token = (
            create_teacher_avatar_setup_token(request.user, result)
            if data.get("avatar_requested") else None
        )
        return Response(
            {
                "teacher_id": result.teacher_id,
                "account_id": result.account_id,
                "site_code": result.site_code,
                "account_status": "active",
                "full_name": result.full_name,
                "phone": result.phone,
                "email": result.email,
                "username": result.username,
                "slug": result.slug,
                "specialty": result.specialty,
                "avatar_secure_url": None,
                "status": result.status,
                "must_change_password": result.must_change_password,
                "credential_email_status": result.credential_email_status,
                "avatar_setup_token": avatar_setup_token,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name="dispatch")
class TeacherCredentialEmailView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "admin_credential_email"

    @extend_schema(
        operation_id="teacher_credentials_send_email",
        tags=["Quản lý giáo viên"],
        summary="Gửi thông tin tài khoản giáo viên qua email một lần",
        description=(
            "Chỉ Admin Big/Admin Small trong phạm vi site. Chỉ gửi khi trạng thái còn sẵn sàng "
            "hoặc lần gửi trước thất bại rõ ràng; trạng thái đã gửi hoặc không xác định không thể gửi lại. "
            "Mật khẩu không xuất hiện trong request/response; kết quả email không chắc chắn cần xử lý thủ công."
        ),
        parameters=[OpenApiParameter("site_code", str, OpenApiParameter.QUERY, required=True)],
        responses={
            200: TeacherCredentialEmailResponseSerializer,
            400: OpenApiResponse(description="Thiếu hoặc sai site_code."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Không đủ quyền hoặc vượt phạm vi site."),
            404: OpenApiResponse(description="Không tìm thấy giáo viên."),
            409: OpenApiResponse(description="Đã gửi, đang gửi, kết quả gửi chưa rõ hoặc mật khẩu cấp đã thay đổi."),
            429: OpenApiResponse(description="Vượt giới hạn gửi email."),
            502: OpenApiResponse(description="Máy chủ email xác nhận không nhận thư."),
            503: OpenApiResponse(description="Cơ sở dữ liệu hoặc cấu hình email chưa sẵn sàng."),
        },
    )
    def post(self, request, slug: str):
        query = TeacherSiteQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        site_code, error = _site_scope(request.user, query.validated_data.get("site_code"))
        if error:
            return error
        try:
            result = send_teacher_credentials(
                slug=slug, site_code=site_code, remote_ip=_remote_ip(request)
            )
        except TeacherCredentialEmailNotFound:
            return Response({"detail": "Không tìm thấy giáo viên trong cơ sở được chọn."}, status=404)
        except TeacherCredentialEmailConflict:
            return Response(
                {"detail": "Không thể gửi lại: thông tin đã gửi, đang xử lý, chưa rõ kết quả hoặc mật khẩu đã thay đổi."},
                status=status.HTTP_409_CONFLICT,
            )
        except TeacherCredentialEmailDeliveryFailed:
            return Response(
                {"detail": "Máy chủ email xác nhận chưa nhận thư; có thể thử gửi lại."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except TeacherCredentialEmailUncertain:
            return Response(
                {"detail": "Chưa xác định được kết quả gửi email; hệ thống đã khóa gửi lại để tránh gửi trùng."},
                status=status.HTTP_409_CONFLICT,
            )
        except AuthInfrastructureUnavailable:
            return Response(
                {"detail": "Cơ sở dữ liệu hoặc cấu hình email chưa sẵn sàng."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({**result, "detail": "Đã gửi thông tin tài khoản đến email giáo viên."})


@method_decorator(csrf_protect, name="dispatch")
class TeacherDetailView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "teacher_management"

    def _target_site(self, request):
        query = TeacherSiteQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        return _site_scope(request.user, query.validated_data.get("site_code"))

    @extend_schema(
        operation_id="teacher_get_by_slug",
        tags=["Quản lý giáo viên"],
        summary="Xem hồ sơ giáo viên theo slug",
        parameters=[OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        responses={
            200: TeacherResponseSerializer,
            400: OpenApiResponse(description="Admin Big chưa chọn cơ sở."),
            401: OpenApiResponse(description="Chưa đăng nhập."),
            403: OpenApiResponse(description="Không đủ quyền hoặc vượt phạm vi site."),
            404: OpenApiResponse(description="Không tìm thấy giáo viên."),
            503: OpenApiResponse(description="Site/CSDL không sẵn sàng."),
        },
    )
    def get(self, request, slug: str):
        site_code, error = self._target_site(request)
        if error:
            return error
        try:
            result = get_teacher(slug=slug, site_code=site_code)
        except (TeacherInfrastructureUnavailable, TeacherSiteUnavailable, TeacherNotFound) as exc:
            return _service_error(exc)
        return Response(result)

    @extend_schema(
        operation_id="teacher_delete_by_slug",
        tags=["Quản lý giáo viên"],
        summary="Vô hiệu hóa tài khoản và xóa mềm hồ sơ giáo viên theo slug",
        description=(
            "Admin Big/Admin Small theo phạm vi site. DELETE không xóa vật lý: chuyển TaiKhoan thành "
            "0 (inactive) trên các site hoạt động, tăng phiên bản để vô hiệu phiên, đặt GiaoVien thành nghi_viec "
            "tại site sở hữu và giữ lịch sử. Từ chối khi giáo viên còn lớp sap_mo/dang_hoc. Trạng thái "
            "được cập nhật trực tiếp trên TaiKhoan và GiaoVien; thao tác nhiều site không được tuyên bố "
            "là ACID nguyên tử xuyên CSDL."
        ),
        parameters=[OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        responses={
            200: TeacherDeleteResponseSerializer,
            400: OpenApiResponse(description="Site không hợp lệ hoặc Admin Big chưa chọn site."),
            401: OpenApiResponse(description="Chưa đăng nhập."),
            403: OpenApiResponse(description="Không đủ quyền hoặc vượt phạm vi site."),
            404: OpenApiResponse(description="Không tìm thấy giáo viên."),
            409: OpenApiResponse(description="Còn lớp đang mở hoặc trạng thái tài khoản xung đột."),
            503: OpenApiResponse(description="Một site SQL Server chưa sẵn sàng; kiểm tra trạng thái các bản sao trước khi gọi lại."),
        },
    )
    def delete(self, request, slug: str):
        site_code, error = self._target_site(request)
        if error:
            return error
        try:
            result = deactivate_teacher(
                slug=slug,
                site_code=site_code,
                actor_id=request.user.account_id,
                remote_ip=_remote_ip(request),
            )
        except (TeacherInfrastructureUnavailable, TeacherSiteUnavailable, TeacherNotFound, TeacherConflict) as exc:
            return _service_error(exc)
        return Response(
            {
                "teacher_id": result.teacher_id,
                "account_id": result.account_id,
                "site_code": result.site_code,
                "status": result.status,
                "teacher_status": result.teacher_status,
                "detail": "Tài khoản đã bị vô hiệu hóa; hồ sơ và lịch sử được giữ lại.",
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class TeacherStatusView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "teacher_management"

    @extend_schema(
        operation_id="teacher_account_status_update",
        tags=["Quản lý giáo viên"],
        summary="Admin Big/Admin Small bật hoặc tắt tài khoản giáo viên",
        description=(
            "Ghi trạng thái TaiKhoan tới mọi site đang hoạt động, tăng phiên bản để thu hồi phiên cũ "
            "và cập nhật trạng thái GiaoVien tại site hồ sơ. Admin Big phải chọn site_code; Admin Small chỉ dùng site của mình. "
            "Giáo viên và các vai trò khác không được gọi endpoint này."
        ),
        parameters=[OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        request=AccountStatusUpdateSerializer,
        responses={
            200: AccountStatusResponseSerializer,
            400: OpenApiResponse(description="Trạng thái hoặc site không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Không đủ quyền hoặc vượt phạm vi site."),
            404: OpenApiResponse(description="Không tìm thấy giáo viên trong site được chọn."),
            409: OpenApiResponse(description="Hồ sơ đã nghỉ việc hoặc trạng thái thay đổi đồng thời."),
            503: OpenApiResponse(description="Một site SQL Server chưa sẵn sàng; kiểm tra trạng thái các bản sao trước khi gọi lại."),
        },
    )
    def patch(self, request, slug: str):
        query = TeacherSiteQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        site_code, error = _site_scope(request.user, query.validated_data.get("site_code"))
        if error:
            return error
        serializer = AccountStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = change_account_status(
                slug=slug,
                expected_role="giao_vien",
                desired_status=serializer.validated_data["status"],
                actor_id=request.user.account_id,
                remote_ip=_remote_ip(request),
                site_code=site_code,
            )
        except AccountStatusTargetNotFound:
            return Response({"detail": "Không tìm thấy giáo viên trong cơ sở được chọn."}, status=404)
        except AccountStatusConflict:
            return Response({"detail": "Giáo viên đã nghỉ việc hoặc trạng thái đang được thay đổi."}, status=409)
        except AuthInfrastructureUnavailable:
            return Response(
                {"detail": "Đồng bộ site chưa hoàn tất; thao tác có thể gọi lại để tiếp tục."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {
                "account_id": result.account_id,
                "slug": result.slug,
                "role": result.role,
                "site_code": result.site_code,
                "status": result.status,
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class TeacherProfileView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "teacher_management"

    def _self_profile(self, request, slug: str):
        if request.user.role != "giao_vien":
            return Response({"detail": "Chỉ giáo viên được truy cập hồ sơ giáo viên."}, status=403)
        if slug != request.user.slug:
            return Response({"detail": "Không tìm thấy hồ sơ giáo viên."}, status=404)
        if not request.user.site_code:
            return Response({"detail": "Tài khoản chưa được gán cơ sở."}, status=403)
        return None

    @extend_schema(
        operation_id="teacher_profile_read",
        tags=["Hồ sơ giáo viên"],
        summary="Giáo viên xem hồ sơ của mình theo slug",
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        responses={
            200: TeacherResponseSerializer,
            403: OpenApiResponse(description="Chỉ giáo viên được xem hồ sơ cá nhân."),
            404: OpenApiResponse(description="Slug không thuộc giáo viên đang đăng nhập."),
            503: OpenApiResponse(description="Site/CSDL không sẵn sàng."),
        },
    )
    def get(self, request, slug: str):
        error = self._self_profile(request, slug)
        if error:
            return error
        try:
            result = get_teacher(slug=slug, site_code=request.user.site_code)
        except (TeacherInfrastructureUnavailable, TeacherSiteUnavailable, TeacherNotFound) as exc:
            return _service_error(exc)
        return Response(result)

    @extend_schema(
        operation_id="teacher_profile_update",
        tags=["Hồ sơ giáo viên"],
        summary="Giáo viên tự cập nhật hồ sơ theo slug",
        description=(
            "Chỉ sửa họ tên và số điện thoại của tài khoản đang đăng nhập. Email, username, "
            "slug, vai trò, cơ sở và trạng thái tài khoản không thể sửa qua endpoint này."
        ),
        parameters=[OpenApiParameter("slug", str, OpenApiParameter.PATH)],
        request=TeacherProfileUpdateSerializer,
        responses={
            200: TeacherResponseSerializer,
            400: OpenApiResponse(description="Dữ liệu hồ sơ không hợp lệ."),
            403: OpenApiResponse(description="Chỉ giáo viên được sửa hồ sơ cá nhân."),
            404: OpenApiResponse(description="Slug không thuộc giáo viên đang đăng nhập."),
            409: OpenApiResponse(description="Hồ sơ giáo viên không còn ở trạng thái có thể sửa."),
            503: OpenApiResponse(description="Site/CSDL không sẵn sàng."),
        },
    )
    def patch(self, request, slug: str):
        error = self._self_profile(request, slug)
        if error:
            return error
        serializer = TeacherProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = update_teacher(
                slug=slug,
                site_code=request.user.site_code,
                actor_id=request.user.account_id,
                updates=serializer.validated_data,
                remote_ip=_remote_ip(request),
            )
        except (TeacherInfrastructureUnavailable, TeacherSiteUnavailable, TeacherNotFound, TeacherConflict) as exc:
            return _service_error(exc)
        return Response(result)
