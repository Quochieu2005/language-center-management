from django.conf import settings
from django.db import DatabaseError, connections
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.auth.authentication import AuthenticationUnavailable
from core.auth.registration import RegistrationConflict, register_student
from core.auth.serializers import AuthRegisterSerializer, AuthRegisterResponseSerializer, RegistrationSitesSerializer
from core.auth.service_common import AuthInfrastructureUnavailable, auth_session_alias
from core.students.services import StudentConflict, StudentInfrastructureUnavailable


@method_decorator(csrf_protect, name="dispatch")
class AuthRegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def get_throttles(self):
        return super().get_throttles() if self.request.method == "POST" else []

    @extend_schema(responses=RegistrationSitesSerializer, tags=["Xác thực"], summary="Danh sách cơ sở để đăng ký tài khoản")
    def get(self, request):
        try:
            with connections[auth_session_alias()].cursor() as cursor:
                cursor.execute("SELECT ma_co_so, ten_co_so FROM dbo.CoSo WHERE trang_thai = 'hoat_dong' ORDER BY ma_co_so")
                sites = [{"site_code": str(code), "name": str(name)} for code, name in cursor.fetchall()]
                cursor.execute("SELECT san_sang FROM dbo.TrangThaiKhoEmail WHERE id = 1")
                ready = cursor.fetchone()
        except DatabaseError as exc:
            raise AuthenticationUnavailable from exc
        return Response({"sites": sites, "registration_ready": bool(ready and ready[0])})

    @extend_schema(request=AuthRegisterSerializer, responses={201: AuthRegisterResponseSerializer},
                   tags=["Xác thực"], summary="Tạo tài khoản học viên miễn phí trước khi đăng ký lớp")
    def post(self, request):
        serializer = AuthRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            data = dict(serializer.validated_data)
            data.setdefault("site_code", settings.AUTH_SESSION_SITE_CODE)
            result = register_student(**data, remote_ip=request.META.get("REMOTE_ADDR", "unknown"))
        except (RegistrationConflict, StudentConflict):
            return Response({"detail": "Không thể tạo tài khoản bằng thông tin này. Hãy đăng nhập hoặc liên hệ trung tâm."}, status=409)
        except ValueError:
            return Response({"detail": "Cơ sở không hợp lệ hoặc không hoạt động."}, status=400)
        except (AuthInfrastructureUnavailable, StudentInfrastructureUnavailable, DatabaseError) as exc:
            raise AuthenticationUnavailable from exc
        return Response({
            "detail": "Đã tạo tài khoản miễn phí. Bạn có thể đăng nhập và chọn khóa học.",
            "replication_complete": not result.replication_pending_sites,
            "replication_pending_sites": list(result.replication_pending_sites),
        }, status=201)
