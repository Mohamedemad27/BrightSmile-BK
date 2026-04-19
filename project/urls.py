from django.contrib import admin
from django.urls import path, re_path, include
from django.views.generic import RedirectView
from rest_framework import permissions
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.conf import settings

schema_view = get_schema_view(
   openapi.Info(
      title="Bright Smile API",
      default_version='v1',
      description="""
      ## Bright Smile Backend API

      A comprehensive Django REST API with PostGIS support for geographic data,
      Celery for background tasks, and Docker for easy deployment.

      ### Key Features:
      - **GeoDjango**: Full PostGIS support for spatial data
      - **Health Monitoring**: Comprehensive health check endpoint
      - **Background Tasks**: Celery integration for async processing
      - **Auto Documentation**: Swagger UI and ReDoc

      ### Health Check
      Use `/api/health/` to monitor system status and service availability.
      """,
      terms_of_service="https://www.example.com/terms/",
      contact=openapi.Contact(email="contact@brightsmile.com"),
      license=openapi.License(name="MIT License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Root: redirect to API docs instead of returning 404
    path('', RedirectView.as_view(url='/api/schema/swagger/', permanent=False)),

    # Admin
    path('admin/', admin.site.urls),

    # API v1
    path('api/v1/', include(('apps.core.urls', 'core'), namespace='v1-core')),
    path('api/v1/users/', include(('apps.users.urls', 'users'), namespace='v1-users')),
    path('api/v1/dashboard/', include(('apps.dashboard.urls', 'dashboard'), namespace='v1-dashboard')),
    path('api/v1/ai/', include(('apps.ai.urls', 'ai'), namespace='v1-ai')),
    path('api/v1/reports/', include(('apps.reports.urls', 'reports'), namespace='v1-reports')),

    # Legacy API (backward compatibility during migration)
    path('api/', include(('apps.core.urls', 'core'), namespace='legacy-core')),
    path('api/users/', include(('apps.users.urls', 'users'), namespace='legacy-users')),
    path('api/dashboard/', include(('apps.dashboard.urls', 'dashboard'), namespace='legacy-dashboard')),
    path('api/ai/', include(('apps.ai.urls', 'ai'), namespace='legacy-ai')),
    path('api/reports/', include(('apps.reports.urls', 'reports'), namespace='legacy-reports')),

    # OpenAPI (spectacular)
    path('api/schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('api/schema/swagger/', SpectacularSwaggerView.as_view(url_name='api-schema'), name='api-schema-swagger-ui'),

    # Docs
    re_path(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        # path('silk/', include('silk.urls', namespace='silk')),  # Disabled due to Django 5.1 compatibility
        path('__debug__/', include(debug_toolbar.urls)),
    ]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
