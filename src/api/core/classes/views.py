"""HTTP endpoints for opening classes and assigning students or teachers."""

import re

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.auth.authentication import AuthCookieAuthentication
from core.classes.serializers import (
    ClassCreateSerializer,
    ClassDetailResponseSerializer,
    ClassListQuerySerializer,
    ClassListResponseSerializer,
    ClassRosterResponseSerializer,
    ClassRosterQuerySerializer,
    ClassSessionListResponseSerializer,
    ClassSiteQuerySerializer,
    ClassTeacherAssignSerializer,
    ClassTeacherAssignResponseSerializer,
    EnrollmentClassAssignResponseSerializer,
    EnrollmentClassAssignSerializer,
    EnrollmentCreateResponseSerializer,
    EnrollmentCreateSerializer,
    RoomCreateResponseSerializer,
    RoomCreateSerializer,
    RoomListQuerySerializer,
    RoomListResponseSerializer,
)
from core.classes.services import (
    ClassConflict,
    ClassInfrastructureUnavailable,
    ClassInvalid,
    ClassNotFound,
    ClassSiteUnavailable,
    assign_class_teacher,
    assign_enrollment_to_class,
    create_class,
    create_room,
    get_class,
    list_class_students,
    list_class_sessions,
    list_classes,
    list_rooms,
    register_student_to_class,
)


_MANAGEMENT_ROLES = {"admin_big", "admin_small", "le_tan"}
_SITE_RECORD_ID = re.compile(r"^[A-Za-z0-9_-]{1,24}$")


def _site_scope(user, requested_site: str | None):
    if user.role not in _MANAGEMENT_ROLES:
        return None, Response(
            {"detail": "Chỉ Admin Big, Admin Small hoặc lễ tân được xếp lớp."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if user.role == "admin_big":
        if not requested_site:
            return None, Response(
                {"detail": "Admin Big cần chọn site_code; API chỉ thao tác trong một CSDL site mỗi lần."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return requested_site, None
    own_site = str(user.site_code or "").upper()
    if not own_site or (requested_site and requested_site != own_site):
        return None, Response(
            {"detail": "Tài khoản chỉ được thao tác tại cơ sở được phân công."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return own_site, None


def _error_response(exc):
    if isinstance(exc, ClassNotFound):
        return Response({"detail": "Không tìm thấy dữ liệu trong cơ sở đã chọn."}, status=404)
    if isinstance(exc, ClassInvalid):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, ClassConflict):
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    if isinstance(exc, ClassSiteUnavailable):
        return Response(
            {"detail": "Cơ sở không ở trạng thái hoạt động."},
            status=status.HTTP_409_CONFLICT,
        )
    return Response(
        {"detail": "CSDL của cơ sở chưa sẵn sàng; thao tác chưa được xác nhận hoàn tất."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _remote_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "") or "unknown"


class _ClassApiView(APIView):
    authentication_classes = [AuthCookieAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]


class RoomCollectionView(_ClassApiView):
    throttle_scope = "class_management"

    @extend_schema(
        operation_id="room_list",
        tags=["Phòng học"],
        summary="Liệt kê phòng học tại một cơ sở",
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
            OpenApiParameter("status", str, OpenApiParameter.QUERY),
            OpenApiParameter("search", str, OpenApiParameter.QUERY),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY),
            OpenApiParameter("offset", int, OpenApiParameter.QUERY),
        ],
        responses={200: RoomListResponseSerializer, 400: OpenApiResponse(), 403: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request):
        query = RoomListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        site_code, error = _site_scope(request.user, data.get("site_code"))
        if error:
            return error
        try:
            result = list_rooms(
                site_code=site_code, status_filter=data.get("status"), search=data.get("search"),
                limit=data["limit"], offset=data["offset"],
            )
        except (ClassNotFound, ClassConflict, ClassInvalid, ClassSiteUnavailable, ClassInfrastructureUnavailable) as exc:
            return _error_response(exc)
        return Response(result)

    @extend_schema(
        operation_id="room_create",
        tags=["Phòng học"],
        summary="Tạo phòng học tại cơ sở",
        request=RoomCreateSerializer,
        responses={201: RoomCreateResponseSerializer, 400: OpenApiResponse(), 403: OpenApiResponse(), 409: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def post(self, request):
        serializer = RoomCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if request.user.role != "admin_big" and data.get("site_code"):
            if data["site_code"] != str(request.user.site_code or "").upper():
                return Response({"detail": "Không được chọn cơ sở khác."}, status=403)
        site_code, error = _site_scope(request.user, data.get("site_code"))
        if error:
            return error
        try:
            result = create_room(
                site_code=site_code, actor_id=request.user.account_id,
                remote_ip=_remote_ip(request), name=data["name"], capacity=data["capacity"],
            )
        except (ClassNotFound, ClassConflict, ClassInvalid, ClassSiteUnavailable, ClassInfrastructureUnavailable) as exc:
            return _error_response(exc)
        return Response(result, status=status.HTTP_201_CREATED)


class EnrollmentCollectionView(_ClassApiView):
    throttle_scope = "enrollment_create"

    @extend_schema(
        operation_id="enrollment_create",
        tags=["Đăng ký khóa học"],
        summary="Đăng ký học viên vào lớp và tạo khoản học phí",
        description=(
            "API chỉ tạo đăng ký tại một CSDL site. Học viên, lớp và khóa học phải cùng site; giá "
            "được đọc từ KhoaHoc.hoc_phi_chuan. DangKy, HocPhi, bộ đếm LopHoc và nhật ký cùng commit "
            "trong transaction cục bộ. Retry cùng học viên/lớp trả đăng ký hiện có; lớp đầy, lịch trùng "
            "hoặc dữ liệu sĩ số lệch sẽ không tạo dữ liệu dở dang."
        ),
        request=EnrollmentCreateSerializer,
        responses={
            201: EnrollmentCreateResponseSerializer,
            400: OpenApiResponse(description="Yêu cầu đăng ký không hợp lệ."),
            403: OpenApiResponse(description="Không có quyền hoặc yêu cầu site vượt phạm vi."),
            404: OpenApiResponse(description="Không tìm thấy học viên/lớp tại site."),
            409: OpenApiResponse(description="Lớp đầy, trùng lịch, trùng đăng ký hoặc sĩ số cần đối soát."),
            503: OpenApiResponse(description="CSDL site không sẵn sàng."),
        },
    )
    def post(self, request):
        serializer = EnrollmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if request.user.role != "admin_big" and data.get("site_code"):
            if data["site_code"] != str(request.user.site_code or "").upper():
                return Response({"detail": "Không được chọn cơ sở khác."}, status=403)
        site_code, error = _site_scope(request.user, data.get("site_code"))
        if error:
            return error
        try:
            result = register_student_to_class(
                site_code=site_code, student_id=data["student_id"], class_id=data["class_id"],
                actor_id=request.user.account_id, remote_ip=_remote_ip(request),
            )
        except (ClassNotFound, ClassConflict, ClassInvalid, ClassSiteUnavailable, ClassInfrastructureUnavailable) as exc:
            return _error_response(exc)
        response_status = status.HTTP_201_CREATED if result["created"] else status.HTTP_200_OK
        return Response(result, status=response_status)


def _validate_record_id(value: str):
    if not _SITE_RECORD_ID.fullmatch(value):
        return Response({"detail": "Mã bản ghi không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)
    return None


class ClassCollectionView(_ClassApiView):
    throttle_scope = "class_management"

    @extend_schema(
        operation_id="class_list",
        tags=["Xếp lớp"],
        summary="Liệt kê lớp và sĩ số tại một cơ sở",
        description=(
            "Đọc đúng một CSDL site. Admin Big phải chọn site_code; Admin Small/lễ tân chỉ dùng site "
            "trong phiên đăng nhập. current_count là bộ đếm LopHoc; registered_count được tính từ "
            "DangKy đang hoạt động để phát hiện lệch sĩ số. Không truy vấn xuyên site."
        ),
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
            OpenApiParameter("status", str, OpenApiParameter.QUERY),
            OpenApiParameter("search", str, OpenApiParameter.QUERY),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY),
            OpenApiParameter("offset", int, OpenApiParameter.QUERY),
        ],
        responses={
            200: ClassListResponseSerializer,
            400: OpenApiResponse(description="Tham số không hợp lệ hoặc thiếu site_code."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Vai trò không có quyền hoặc vượt phạm vi site."),
            503: OpenApiResponse(description="CSDL site không sẵn sàng."),
        },
    )
    def get(self, request):
        query = ClassListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        site_code, error = _site_scope(request.user, data.get("site_code"))
        if error:
            return error
        try:
            result = list_classes(
                site_code=site_code, status_filter=data.get("status"), search=data.get("search"),
                limit=data["limit"], offset=data["offset"],
            )
        except (ClassNotFound, ClassConflict, ClassInvalid, ClassSiteUnavailable, ClassInfrastructureUnavailable) as exc:
            return _error_response(exc)
        return Response(result)

    @extend_schema(
        operation_id="class_create",
        tags=["Xếp lớp"],
        summary="Mở lớp, phân công giáo viên/phòng và tạo lịch buổi học",
        description=(
            "Tạo LopHoc cùng các BuoiHoc theo số buổi của KhoaHoc trong một transaction cục bộ. "
            "Kiểm tra khóa học, giáo viên đang dạy, phòng hoạt động/sức chứa, ngày giờ và xung đột "
            "giáo viên/phòng. Admin Big gửi site_code; Admin Small/lễ tân dùng site phiên đăng nhập."
        ),
        request=ClassCreateSerializer,
        responses={
            201: ClassDetailResponseSerializer,
            400: OpenApiResponse(description="Thông tin lớp hoặc lịch không hợp lệ."),
            401: OpenApiResponse(description="Chưa đăng nhập hoặc phiên hết hạn."),
            403: OpenApiResponse(description="Không có quyền hoặc yêu cầu site vượt phạm vi."),
            409: OpenApiResponse(description="Trùng lịch, site chưa hoạt động hoặc dữ liệu đang xung đột."),
            503: OpenApiResponse(description="CSDL site không sẵn sàng."),
        },
    )
    def post(self, request):
        serializer = ClassCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if request.user.role != "admin_big" and data.get("site_code"):
            if data["site_code"] != str(request.user.site_code or "").upper():
                return Response({"detail": "Không được chọn cơ sở khác."}, status=403)
        site_code, error = _site_scope(request.user, data.get("site_code"))
        if error:
            return error
        try:
            result = create_class(
                site_code=site_code, actor_id=request.user.account_id,
                remote_ip=_remote_ip(request), data=data,
            )
        except (ClassNotFound, ClassConflict, ClassInvalid, ClassSiteUnavailable, ClassInfrastructureUnavailable) as exc:
            return _error_response(exc)
        return Response(result, status=status.HTTP_201_CREATED)


class ClassDetailView(_ClassApiView):
    throttle_scope = "class_management"

    @extend_schema(
        operation_id="class_detail",
        tags=["Xếp lớp"],
        summary="Xem chi tiết lớp, sĩ số và số buổi đã tạo",
        parameters=[OpenApiParameter("site_code", str, OpenApiParameter.QUERY)],
        responses={200: ClassDetailResponseSerializer, 400: OpenApiResponse(description="Thiếu site_code."), 403: OpenApiResponse(), 404: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request, class_id):
        invalid_id = _validate_record_id(class_id)
        if invalid_id:
            return invalid_id
        query = ClassSiteQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        site_code, error = _site_scope(request.user, query.validated_data.get("site_code"))
        if error:
            return error
        try:
            return Response(get_class(site_code=site_code, class_id=class_id))
        except (ClassNotFound, ClassConflict, ClassInvalid, ClassSiteUnavailable, ClassInfrastructureUnavailable) as exc:
            return _error_response(exc)


class ClassRosterView(_ClassApiView):
    throttle_scope = "class_management"

    @extend_schema(
        operation_id="class_students",
        tags=["Xếp lớp"],
        summary="Xem học viên đang đăng ký trong lớp",
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY),
            OpenApiParameter("offset", int, OpenApiParameter.QUERY),
        ],
        responses={200: ClassRosterResponseSerializer, 400: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request, class_id):
        invalid_id = _validate_record_id(class_id)
        if invalid_id:
            return invalid_id
        query_data = {
            "limit": request.query_params.get("limit", 25),
            "offset": request.query_params.get("offset", 0),
        }
        if "site_code" in request.query_params:
            query_data["site_code"] = request.query_params.get("site_code")
        query = ClassRosterQuerySerializer(data=query_data)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        site_code, error = _site_scope(request.user, data.get("site_code"))
        if error:
            return error
        try:
            return Response(list_class_students(
                site_code=site_code, class_id=class_id, limit=data["limit"], offset=data["offset"]
            ))
        except (ClassNotFound, ClassConflict, ClassInvalid, ClassSiteUnavailable, ClassInfrastructureUnavailable) as exc:
            return _error_response(exc)


class ClassSessionsView(_ClassApiView):
    throttle_scope = "class_management"

    @extend_schema(
        operation_id="class_sessions",
        tags=["Xếp lớp"],
        summary="Xem lịch từng buổi học của lớp",
        parameters=[
            OpenApiParameter("site_code", str, OpenApiParameter.QUERY),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY),
            OpenApiParameter("offset", int, OpenApiParameter.QUERY),
        ],
        responses={200: ClassSessionListResponseSerializer, 400: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def get(self, request, class_id):
        invalid_id = _validate_record_id(class_id)
        if invalid_id:
            return invalid_id
        query_data = {
            "limit": request.query_params.get("limit", 25),
            "offset": request.query_params.get("offset", 0),
        }
        if "site_code" in request.query_params:
            query_data["site_code"] = request.query_params.get("site_code")
        query = ClassRosterQuerySerializer(data=query_data)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        site_code, error = _site_scope(request.user, data.get("site_code"))
        if error:
            return error
        try:
            result = list_class_sessions(
                site_code=site_code, class_id=class_id,
                limit=data["limit"], offset=data["offset"],
            )
        except (ClassNotFound, ClassConflict, ClassInvalid, ClassSiteUnavailable, ClassInfrastructureUnavailable) as exc:
            return _error_response(exc)
        return Response(result)


class ClassTeacherAssignView(_ClassApiView):
    throttle_scope = "class_management"

    @extend_schema(
        operation_id="class_teacher_assign",
        tags=["Xếp lớp"],
        summary="Phân công hoặc đổi giáo viên cho lớp",
        description=(
            "Đổi giáo viên ở LopHoc và chỉ cập nhật các BuoiHoc tương lai chưa diễn ra; buổi lịch sử "
            "được giữ nguyên. Kiểm tra giáo viên đang dạy và lịch trùng tại cùng site."
        ),
        request=ClassTeacherAssignSerializer,
        responses={200: ClassTeacherAssignResponseSerializer, 400: OpenApiResponse(), 403: OpenApiResponse(), 404: OpenApiResponse(), 409: OpenApiResponse(), 503: OpenApiResponse()},
    )
    def put(self, request, class_id):
        invalid_id = _validate_record_id(class_id)
        if invalid_id:
            return invalid_id
        serializer = ClassTeacherAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if request.user.role != "admin_big" and data.get("site_code"):
            if data["site_code"] != str(request.user.site_code or "").upper():
                return Response({"detail": "Không được chọn cơ sở khác."}, status=403)
        site_code, error = _site_scope(request.user, data.get("site_code"))
        if error:
            return error
        try:
            result = assign_class_teacher(
                site_code=site_code, class_id=class_id, teacher_id=data["teacher_id"],
                actor_id=request.user.account_id, remote_ip=_remote_ip(request),
            )
        except (ClassNotFound, ClassConflict, ClassInvalid, ClassSiteUnavailable, ClassInfrastructureUnavailable) as exc:
            return _error_response(exc)
        return Response(result)


class EnrollmentClassAssignView(_ClassApiView):
    throttle_scope = "class_management"

    @extend_schema(
        operation_id="enrollment_class_assign",
        tags=["Xếp lớp"],
        summary="Xếp lại một đăng ký sang lớp khác cùng khóa học",
        description=(
            "Di chuyển DangKy hiện có trong cùng CSDL site. Khóa hai lớp theo thứ tự ổn định, kiểm tra "
            "sức chứa, khớp khóa học, trùng lịch và tính đúng của bộ đếm; cập nhật đăng ký, sĩ số hai "
            "lớp và nhật ký trong một transaction cục bộ. Không tạo học phí mới và không chuyển site."
        ),
        request=EnrollmentClassAssignSerializer,
        responses={
            200: EnrollmentClassAssignResponseSerializer,
            400: OpenApiResponse(description="Dữ liệu không hợp lệ."),
            403: OpenApiResponse(description="Không có quyền hoặc vượt phạm vi site."),
            404: OpenApiResponse(description="Không tìm thấy đăng ký/lớp tại site."),
            409: OpenApiResponse(description="Lớp đầy, trùng lịch hoặc dữ liệu đang xung đột."),
            503: OpenApiResponse(description="CSDL site không sẵn sàng."),
        },
    )
    def post(self, request, enrollment_id):
        invalid_id = _validate_record_id(enrollment_id)
        if invalid_id:
            return invalid_id
        serializer = EnrollmentClassAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if request.user.role != "admin_big" and data.get("site_code"):
            if data["site_code"] != str(request.user.site_code or "").upper():
                return Response({"detail": "Không được chọn cơ sở khác."}, status=403)
        site_code, error = _site_scope(request.user, data.get("site_code"))
        if error:
            return error
        try:
            result = assign_enrollment_to_class(
                site_code=site_code, enrollment_id=enrollment_id,
                target_class_id=data["target_class_id"], actor_id=request.user.account_id,
                remote_ip=_remote_ip(request),
            )
        except (ClassNotFound, ClassConflict, ClassInvalid, ClassSiteUnavailable, ClassInfrastructureUnavailable) as exc:
            return _error_response(exc)
        return Response(result)
