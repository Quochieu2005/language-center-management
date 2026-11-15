"""HTTP endpoints for Admin Big/Admin Small to manage employee accounts."""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.academics.common import AcademicError, AcademicForbidden, AcademicInvalid, site_scope
from core.auth.authentication import AuthCookieAuthentication
from core.employees.serializers import (
    EmployeeCreateSerializer,
    EmployeeCreateResponseSerializer,
    EmployeeListQuerySerializer,
    EmployeeResponseSerializer,
    EmployeeSiteQuerySerializer,
    EmployeeUpdateSerializer,
)
from core.employees.services import (
    EmployeeConflict,
    EmployeeInfrastructureUnavailable,
    EmployeeNotFound,
    create_employee,
    deactivate_employee,
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

    @extend_schema(
        operation_id="employee_list",
        tags=["Quản lý nhân viên"],
        summary="Liệt kê nhân viên theo cơ sở và chức vụ",
        description=(
            "LOCAL: Admin Big phải chỉ định một site; Admin Small chỉ đọc site trong phiên. "
            "Kết quả chỉ lấy hồ sơ từ dbo.NhanVien tại CSDL site được phép."
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
        summary="Tạo tài khoản nhân viên tư vấn, kế toán hoặc xếp lớp",
        description=(
            "LOCAL cho hồ sơ dbo.NhanVien tại site đã chọn; bản ghi TaiKhoan nhan_vien được nhân bản "
            "đến các site hoạt động theo chính sách tài khoản hiện có. Admin Big chọn site; Admin Small "
            "chỉ tạo ở site của mình. Mật khẩu tạm từ ADMIN_SMALL_TEMP_PASSWORD được gửi qua SMTP, "
            "bắt buộc đổi ở lần đăng nhập đầu; API không trả mật khẩu. Không tạo bảng hoặc CSDL mới."
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
                "must_change_password": result.must_change_password,
                "email_sent": result.email_sent,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name="dispatch")
class EmployeeDetailView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "employee_management"

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
        summary="Xóa nhân viên theo slug",
        description=(
            "Chỉ Admin Big hoặc Admin Small được gọi. Admin Big phải chỉ định site_code; Admin Small "
            "chỉ thao tác tại site trong phiên. DELETE khóa TaiKhoan trên mọi bản sao, thu hồi phiên "
            "đăng nhập và chuyển NhanVien.trang_thai sang nghi_viec tại site sở hữu. Hồ sơ, PhieuThu "
            "và Logs được giữ để bảo toàn chứng từ và lịch sử. Nếu một bản sao lỗi, gọi lại cùng slug "
            "để tiếp tục đồng bộ; không tuyên bố thành công khi chưa hoàn tất mọi site. Kiểu: "
            "REPLICATED-WRITE cho TaiKhoan và LOCAL cho NhanVien/PhienDangNhap/Logs."
        ),
        parameters=[OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        responses={
            200: OpenApiResponse(description="Tài khoản đã bị khóa, hồ sơ được chuyển sang nghỉ việc."),
            400: OpenApiResponse(description="Site không hợp lệ hoặc Admin Big chưa chọn site."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Không đủ quyền hoặc Admin Small chọn site khác."),
            404: OpenApiResponse(description="Không tìm thấy nhân viên tại site được chọn."),
            409: OpenApiResponse(description="Trạng thái nhân viên/tài khoản xung đột."),
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
            result = deactivate_employee(
                slug=slug, site_code=site, actor_id=request.user.account_id,
                remote_ip=request.META.get("REMOTE_ADDR", "") or "unknown",
            )
        except EmployeeNotFound:
            return Response({"detail": "Không tìm thấy nhân viên trong cơ sở được chọn."}, status=404)
        except EmployeeConflict:
            return Response(
                {"detail": "Trạng thái nhân viên hoặc tài khoản đang xung đột; hãy tải lại dữ liệu."},
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
                "status": result.status,
                "employee_status": result.employee_status,
                "detail": "Tài khoản đã bị khóa; hồ sơ, phiếu thu và nhật ký được giữ lại.",
            },
            status=status.HTTP_200_OK,
        )
