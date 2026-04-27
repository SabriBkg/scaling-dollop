from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from core.views.auth import SafeNetTokenObtainPairView
from core.views.optout import optout_view
from core.views.password_reset import password_reset_confirm, password_reset_request

# CRITICAL: Disable default /admin/ — operator console is at /ops-console/ only
admin.autodiscover()

urlpatterns = [
    # Operator console — is_staff only, isolated from client API
    path("ops-console/", admin.site.urls),

    # JWT auth endpoints
    path("api/v1/auth/token/", SafeNetTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Password reset (Story 4.5) — anonymous, JSON, throttled.
    path("api/v1/auth/password-reset/", password_reset_request, name="password_reset_request"),
    path("api/v1/auth/password-reset/confirm/", password_reset_confirm, name="password_reset_confirm"),

    # Core endpoints (health check, account)
    path("api/", include("core.urls")),

    # OpenAPI schema (internal — not exposed to clients)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    # Public, unauthenticated subscriber opt-out (Story 4.4).
    # Sits OUTSIDE /api/v1/ — no JWT, no DRF, returns HTML. The signed token
    # in the URL is the proof-of-intent (architecture.md line 921-923).
    path("optout/<str:token>/", optout_view, name="notification_optout"),
]

# DO NOT add path("admin/", admin.site.urls) — /admin/ must be disabled, not redirected.
