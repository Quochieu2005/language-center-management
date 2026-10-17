from django.conf import settings
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


urlpatterns = [path("api/v1/", include("core.urls"))]

# Swagger/ReDoc are the generated documentation UIs from drf-spectacular.
# Enable explicitly in development; it stays independent of Django's test-mode
# DEBUG override and can be disabled in production with API_DOCS_ENABLED=false.
if settings.API_DOCS_ENABLED:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/docs/swagger/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path(
            "api/docs/redoc/",
            SpectacularRedocView.as_view(url_name="schema"),
            name="redoc",
        ),
    ]
