from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


@extend_schema(
    operation_id="system_health",
    tags=["Hệ thống"],
    summary="Kiểm tra API đang hoạt động",
    description=(
        "Liveness check của tiến trình Django. Endpoint này không kết nối SQL Server, "
        "vì vậy phản hồi thành công không xác nhận các site database đang sẵn sàng."
    ),
    responses={
        200: OpenApiResponse(
            response={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "example": "ok"},
                    "service": {"type": "string", "example": "qlttnn-api"},
                },
            },
            description="Tiến trình API đang nhận request.",
        )
    },
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle, UserRateThrottle])
def health_check(_request):
    return Response({"status": "ok", "service": "qlttnn-api"})
