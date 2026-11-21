"""HTTP endpoints for Admin Big/Admin Small to manage employee accounts."""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.academics.common import AcademicError, AcademicForbidden, AcademicInvalid, global_site_list, site_scope
from core.auth.account_status import (
    AccountStatusConflict,
    AccountStatusTargetNotFound,
    change_account_status,
)
from core.auth.authentication import AuthCookieAuthentication
from core.auth.serializers import EmptyRequestSerializer
from core.auth.admin_small_email import send_employee_credentials
from core.auth.service_common import (
    AdminSmallCredentialEmailConflict,
    AdminSmallCredentialEmailDeliveryFailed,
    AdminSmallCredentialEmailUncertain,
    AdminSmallTargetNotFound,
    AuthInfrastructureUnavailable,
)
from core.media.avatars import create_employee_avatar_setup_token
from core.employees.serializers import (
    EmployeeCreateSerializer,
    EmployeeCreateResponseSerializer,
    EmployeeListQuerySerializer,
    EmployeeResponseSerializer,
    EmployeeSiteQuerySerializer,
    EmployeeCredentialEmailResponseSerializer,
    EmployeeStatusUpdateSerializer,
    EmployeeUpdateSerializer,
)
from core.employees.services import (
    EmployeeConflict,
    EmployeeInfrastructureUnavailable,
    EmployeeNotFound,
    create_employee,
    delete_employee,
    get_employee,
    list_employees,
    update_employee,
)


def _site_error(exc):
    if isinstance(exc, AcademicForbidden):
        return Response({"detail": "Bạn không có quyền truy cập cơ sở này."}, status=403)
    if isinstance(exc, AcademicInvalid):
        return Response({"detail": str(exc)}, status=400)
    if isinstance(exc, ValueError):
        return Response({"detail": str(exc)}, status=400)
    return Response(
        {"detail": "CSDL cơ sở hoặc dịch vụ cần thiết chưa sẵn sàng; kiểm tra trạng thái trước khi gọi lại."},
        status=503,
    )


@method_decorator(csrf_protect, name="dispatch")
class EmployeeCollectionView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "employee_management"

    def get_throttles(self):
        self.throttle_scope = "employee_read" if self.request.method == "GET" else "employee_management"
        return super().get_throttles()

    @extend_schema(
        operation_id="employee_list",
        tags=["Quản lý nhân viên"],
        summary="Liệt kê nhân viên theo cơ sở và chức vụ",
        description=(
            "Admin Big bỏ site_code để đọc GLOBAL: Coordinator truy vấn riêng từng CSDL site đang hoạt động rồi phân trang/tổng hợp trong API; "
            "có site lỗi thì trả complete=false và missing_sites. Admin Big truyền site_code để đọc LOCAL. Admin Small chỉ đọc site trong phiên. "
            "Hồ sơ lấy từ dbo.NhanVien tại các CSDL site; TaiKhoan được đọc theo bản tại cùng site."
        ),
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
            OpenApiParameter("job_title", str, OpenApiParameter.QUERY),
            OpenApiParameter("status", str, OpenApiParameter.QUERY),
            OpenApiParameter("search", str, OpenApiParameter.QUERY),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY),
            OpenApiParameter("offset", int, OpenApiParameter.QUERY),
        ],
        responses={200: OpenApiResponse(), 400: OpenApiResponse(), 401: OpenApiResponse(), 403: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request):
        query = EmployeeListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        try:
            if request.user.role == "admin_big" and not data.get("site_code"):
                return Response(global_site_list(
                    lambda site, limit, offset: list_employees(
                        site_code=site, job_title=data.get("job_title"), status=data.get("status"),
                        search=data.get("search"), limit=limit, offset=offset,
                    ),
                    limit=data["limit"], offset=data["offset"],
                    unavailable_exceptions=(AcademicError, EmployeeInfrastructureUnavailable),
                ))
            site = site_scope(request.user, data.get("site_code"), roles={"admin_big", "admin_small"})
            return Response(list_employees(
                site_code=site, job_title=data.get("job_title"), status=data.get("status"),
                search=data.get("search"), limit=data["limit"], offset=data["offset"],
            ))
        except (AcademicError, EmployeeInfrastructureUnavailable, KeyError) as exc:
            return _site_error(exc)

    @extend_schema(
        operation_id="employee_create",
        tags=["Quản lý nhân viên"],
        summary="Tạo nhân viên Kế toán & Lễ tân hoặc Tư vấn & xếp lớp",
        description=(
            "LOCAL cho hồ sơ dbo.NhanVien tại site đã chọn; bản ghi TaiKhoan nhan_vien được nhân bản "
            "đến các site hoạt động theo chính sách tài khoản hiện có. Admin Big chọn site; Admin Small "
            "chỉ tạo ở site của mình. Mật khẩu tạm lấy từ ADMIN_SMALL_TEMP_PASSWORD, lưu dạng hash và "
            "bắt buộc đổi ở lần đăng nhập đầu; tạo nhân viên không gửi email. API ghi trạng thái chờ gửi "
            "vào Logs; Admin Big/Admin Small phải bấm gửi qua endpoint credential-email. Nếu avatar_requested=true, API trả "
            "setup_token ngắn hạn để tải ảnh lên Cloudinary; bytes ảnh không đi qua Django/SQL Server."
        ),
        request=EmployeeCreateSerializer,
        responses={201: EmployeeCreateResponseSerializer, 400: OpenApiResponse(), 401: OpenApiResponse(), 403: OpenApiResponse(), 409: OpenApiResponse(), 429: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def post(self, request):
        serializer = EmployeeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            site = site_scope(request.user, data.get("site_code"), roles={"admin_big", "admin_small"})
            result = create_employee(
                site_code=site, full_name=data["full_name"], email=data["email"],
                username=data.get("username"), phone=data.get("phone"),
                job_title=data["job_title"], actor_id=request.user.account_id,
                remote_ip=request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except EmployeeConflict:
            return Response({"detail": "Email, tên đăng nhập hoặc hồ sơ nhân viên đã tồn tại."}, status=409)
        except (AcademicError, EmployeeInfrastructureUnavailable, ValueError, KeyError) as exc:
            return _site_error(exc)
        avatar_setup_token = create_employee_avatar_setup_token(request.user, result) if data["avatar_requested"] else None
        return Response(
            {
                "employee_id": result.employee_id,
                "account_id": result.account_id,
                "slug": result.slug,
                "username": result.username,
                "email": result.email,
                "site_code": result.site_code,
                "job_title": result.job_title,
                "full_name": result.full_name,
                "phone": result.phone,
                "account_status": "active",
                "employee_status": "dang_lam",
                "replication_complete": not result.replication_pending_sites,
                "replication_pending_sites": list(result.replication_pending_sites),
                "avatar_secure_url": None,
                "avatar_setup_token": avatar_setup_token,
                "must_change_password": result.must_change_password,
                "credential_email_status": result.credential_email_status,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name="dispatch")
class EmployeeCredentialEmailView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "admin_credential_email"

    @extend_schema(
        operation_id="employee_send_credentials_once",
        tags=["Quản lý nhân viên"],
        summary="Admin Big/Admin Small gửi mật khẩu tạm cho nhân viên một lần",
        request=EmptyRequestSerializer,
        description=(
            "Chỉ gửi khi Logs tại site ghi nhận trạng thái chờ gửi hoặc lần gửi trước được SMTP xác nhận thất bại. "
            "Gửi thành công, đổi mật khẩu, hoặc kết quả SMTP chưa rõ sẽ khóa gửi lại. Khóa SQL Server ngăn gửi đồng thời. "
            "Admin Big phải chọn site; Admin Small chỉ dùng site trong phiên."
        ),
        parameters=[OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        responses={
            200: EmployeeCredentialEmailResponseSerializer,
            400: OpenApiResponse(description="Thiếu hoặc sai site."),
            401: OpenApiResponse(description="Chưa đăng nhập."),
            403: OpenApiResponse(description="Không đủ quyền hoặc Admin Small chọn site khác."),
            404: OpenApiResponse(description="Không tìm thấy nhân viên đang hoạt động."),
            409: OpenApiResponse(description="Email đã gửi, đang xử lý, kết quả chưa rõ hoặc mật khẩu tạm đã đổi."),
            429: OpenApiResponse(description="Đã vượt giới hạn gửi email."),
            502: OpenApiResponse(description="SMTP xác nhận chưa nhận email; có thể thử lại."),
            503: OpenApiResponse(description="CSDL hoặc SMTP chưa sẵn sàng; trạng thái chưa rõ sẽ khóa gửi lại."),
        },
    )
    def post(self, request, account_id: str):
        query = EmployeeSiteQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            site = site_scope(
                request.user, query.validated_data.get("site_code"),
                roles={"admin_big", "admin_small"},
            )
            result = send_employee_credentials(
                account_id=account_id,
                site_code=site,
                remote_ip=request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except AdminSmallTargetNotFound:
            return Response({"detail": "Không tìm thấy nhân viên đang hoạt động tại cơ sở được chọn."}, status=404)
        except AdminSmallCredentialEmailConflict:
            return Response(
                {"detail": "Không thể gửi lại: email đã được gửi, đang xử lý, chưa xác định kết quả hoặc mật khẩu tạm đã đổi."},
                status=409,
            )
        except AdminSmallCredentialEmailDeliveryFailed:
            return Response({"detail": "SMTP xác nhận chưa nhận email. Có thể thử gửi lại."}, status=502)
        except AdminSmallCredentialEmailUncertain:
            return Response(
                {"detail": "Chưa xác định email đã tới hay chưa; hệ thống đã khóa gửi lại để tránh gửi trùng."},
                status=503,
            )
        except (AcademicError, AuthInfrastructureUnavailable, KeyError) as exc:
            return _site_error(exc)
        return Response(
            {"detail": "Đã gửi mật khẩu tạm đến email nhân viên.", **result},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_protect, name="dispatch")
class EmployeeDetailView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "employee_management"

    def get_throttles(self):
        self.throttle_scope = "employee_read" if self.request.method == "GET" else "employee_management"
        return super().get_throttles()

    @extend_schema(
        operation_id="employee_detail_by_slug",
        tags=["Quản lý nhân viên"],
        summary="Xem chi tiết nhân viên theo slug",
        description=(
            "LOCAL: đọc NhanVien và bản TaiKhoan tại CSDL site được chọn. Admin Big gửi site_code; "
            "Admin Small chỉ đọc site gắn với phiên. Email và tên đăng nhập là danh tính TaiKhoan, "
            "không phải trường hồ sơ có thể sửa ở endpoint này."
        ),
        parameters=[OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        responses={200: EmployeeResponseSerializer, 400: OpenApiResponse(), 401: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 409: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request, slug: str):
        query = EmployeeSiteQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            site = site_scope(
                request.user, query.validated_data.get("site_code"),
                roles={"admin_big", "admin_small"},
            )
            return Response(get_employee(slug=slug, site_code=site))
        except EmployeeNotFound:
            return Response({"detail": "Không tìm thấy nhân viên trong cơ sở được chọn."}, status=404)
        except EmployeeConflict:
            return Response({"detail": "Dữ liệu tài khoản hoặc hồ sơ nhân viên đang xung đột."}, status=409)
        except (AcademicError, EmployeeInfrastructureUnavailable, KeyError) as exc:
            return _site_error(exc)

    @extend_schema(
        operation_id="employee_update_by_slug",
        tags=["Quản lý nhân viên"],
        summary="Cập nhật hồ sơ nhân viên theo slug",
        description=(
            "LOCAL: cập nhật NhanVien.ho_ten, sdt hoặc chuc_vu và ghi Logs trong cùng transaction tại site. "
            "Chỉ hồ sơ/tài khoản đang hoạt động được sửa. Không nhận email, username hoặc site_code trong body: "
            "danh tính đăng nhập được nhân bản, còn đổi cơ sở cần nghiệp vụ riêng."
        ),
        parameters=[OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        request=EmployeeUpdateSerializer,
        responses={200: EmployeeResponseSerializer, 400: OpenApiResponse(), 401: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 409: OpenApiResponse(), 429: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def patch(self, request, slug: str):
        serializer = EmployeeUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query = EmployeeSiteQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            site = site_scope(
                request.user, query.validated_data.get("site_code"),
                roles={"admin_big", "admin_small"},
            )
            result = update_employee(
                slug=slug, site_code=site, fields=serializer.validated_data,
                actor_id=request.user.account_id,
                remote_ip=request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except EmployeeNotFound:
            return Response({"detail": "Không tìm thấy nhân viên trong cơ sở được chọn."}, status=404)
        except EmployeeConflict:
            return Response(
                {"detail": "Nhân viên đã nghỉ việc hoặc dữ liệu tài khoản đang xung đột; hãy tải lại."},
                status=409,
            )
        except (AcademicError, EmployeeInfrastructureUnavailable, ValueError, KeyError) as exc:
            return _site_error(exc)
        return Response(result, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="employee_delete_by_slug",
        tags=["Quản lý nhân viên"],
        summary="Xóa vĩnh viễn tài khoản nhân viên theo slug",
        description=(
            "Chỉ Admin Big hoặc Admin Small được gọi. Admin Big phải chỉ định site_code; Admin Small "
            "chỉ thao tác tại site trong phiên. DELETE xóa vật lý TaiKhoan, phiên/token và ảnh đại diện "
            "ở các bản sao; không đổi trạng thái sang inactive. Nếu NhanVien được PhieuThu tham chiếu, "
            "giữ hồ sơ tại site, gỡ liên kết tài khoản và đánh dấu nghỉ việc; nếu không, xóa hồ sơ. "
            "Giữ Logs/chứng từ. Có thể gọi lại cùng slug sau lỗi để tiếp tục; không tuyên bố hoàn tất "
            "trước khi đồng bộ đủ các site được cấu hình. Kiểu: REPLICATED-WRITE cho TaiKhoan và "
            "LOCAL cho NhanVien/PhienDangNhap/TokenDatLaiMatKhau/Logs."
        ),
        parameters=[OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        responses={
            200: OpenApiResponse(description="Tài khoản đăng nhập đã bị xóa vĩnh viễn."),
            400: OpenApiResponse(description="Site không hợp lệ hoặc Admin Big chưa chọn site."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Không đủ quyền hoặc Admin Small chọn site khác."),
            404: OpenApiResponse(description="Không tìm thấy nhân viên tại site được chọn."),
            409: OpenApiResponse(description="Còn dữ liệu nghiệp vụ cần giữ hoặc bản sao tài khoản xung đột."),
            503: OpenApiResponse(description="Site hoặc bản sao tài khoản chưa sẵn sàng; gọi lại để tiếp tục."),
        },
    )
    def delete(self, request, slug: str):
        query = EmployeeSiteQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            site = site_scope(
                request.user, query.validated_data.get("site_code"),
                roles={"admin_big", "admin_small"},
            )
            result = delete_employee(
                slug=slug, site_code=site, actor_id=request.user.account_id,
                remote_ip=request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except EmployeeNotFound:
            return Response({"detail": "Không tìm thấy nhân viên trong cơ sở được chọn."}, status=404)
        except EmployeeConflict:
            return Response(
                {"detail": "Không thể xóa: tài khoản còn dữ liệu nghiệp vụ cần giữ hoặc bản sao đang xung đột."},
                status=409,
            )
        except (AcademicError, EmployeeInfrastructureUnavailable, KeyError) as exc:
            return _site_error(exc)
        return Response(
            {
                "employee_id": result.employee_id,
                "account_id": result.account_id,
                "slug": result.slug,
                "site_code": result.site_code,
                "deleted": True,
                "profile_retained": result.profile_retained,
                "detail": (
                    "Tài khoản đã bị xóa vĩnh viễn; hồ sơ được giữ để bảo toàn phiếu thu."
                    if result.profile_retained else "Tài khoản và hồ sơ nhân viên đã bị xóa vĩnh viễn."
                ),
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_protect, name="dispatch")
class EmployeeStatusView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "employee_management"

    @extend_schema(
        operation_id="employee_account_status_update",
        tags=["Quản lý nhân viên"],
        summary="Admin Big/Admin Small ngưng tài khoản nhân viên",
        description=(
            "Chỉ hỗ trợ active → inactive; không có thao tác kích hoạt lại. TaiKhoan được đồng bộ tới mọi "
            "site đang hoạt động và các phiên hiện có bị thu hồi. Không thay đổi NhanVien.trang_thai "
            "(tình trạng làm việc). Admin Big phải chọn site; Admin Small chỉ dùng site của mình."
        ),
        parameters=[OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        request=EmployeeStatusUpdateSerializer,
        responses={
            200: OpenApiResponse(description="Trạng thái tài khoản đã được cập nhật."),
            400: OpenApiResponse(description="Site hoặc trạng thái không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Không đủ quyền hoặc vượt phạm vi site."),
            404: OpenApiResponse(description="Không tìm thấy nhân viên tại site được chọn."),
            409: OpenApiResponse(description="Nhân viên đã nghỉ việc hoặc dữ liệu đang xung đột."),
            503: OpenApiResponse(description="Đồng bộ site chưa hoàn tất; có thể gọi lại."),
        },
    )
    def patch(self, request, slug: str):
        query = EmployeeSiteQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        serializer = EmployeeStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            site = site_scope(
                request.user, query.validated_data.get("site_code"),
                roles={"admin_big", "admin_small"},
            )
            result = change_account_status(
                slug=slug,
                expected_role="employee",
                desired_status=serializer.validated_data["status"],
                actor_id=request.user.account_id,
                remote_ip=request.META.get("REMOTE_ADDR", "") or "unknown",
                site_code=site,
            )
        except AccountStatusTargetNotFound:
            return Response({"detail": "Không tìm thấy nhân viên trong cơ sở được chọn."}, status=404)
        except AccountStatusConflict:
            return Response({"detail": "Nhân viên đã nghỉ việc hoặc trạng thái đang được thay đổi."}, status=409)
        except (AcademicError, AuthInfrastructureUnavailable, KeyError) as exc:
            return _site_error(exc)
        return Response({
            "account_id": result.account_id,
            "slug": result.slug,
            "role": result.role,
            "site_code": result.site_code,
            "status": result.status,
        })
