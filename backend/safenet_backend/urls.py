from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from core.views.auth import SafeNetTokenObtainPairView

# CRITICAL: Disable default /admin/ — operator console is at /ops-console/ only
admin.autodiscover()

urlpatterns = [
    # Operator console — is_staff only, isolated from client API
    path("ops-console/", admin.site.urls),

    # JWT auth endpoints
    path("api/v1/auth/token/", SafeNetTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Core endpoints (health check, account)
    path("api/", include("core.urls")),

    # OpenAPI schema (internal — not exposed to clients)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

# DO NOT add path("admin/", admin.site.urls) — /admin/ must be disabled, not redirected.
