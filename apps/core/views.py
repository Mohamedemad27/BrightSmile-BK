import time
from datetime import datetime
from django.conf import settings
from django.db import connection
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .serializers import HealthCheckSerializer
import redis


class HealthCheckView(APIView):
    """
    Health Check Endpoint

    Performs comprehensive health checks on all critical system components including:
    - Database (PostgreSQL with PostGIS)
    - Redis (Celery broker)
    - Overall system status

    Returns detailed status information for monitoring and alerting purposes.
    """

    permission_classes = []  # Public endpoint, no authentication required

    @swagger_auto_schema(
        operation_id='health_check',
        operation_description="""
        Comprehensive health check endpoint that monitors all critical services.

        **Checks performed:**
        - **Database (PostgreSQL/PostGIS)**: Tests database connectivity and query execution
        - **Redis**: Tests Redis connectivity for Celery task queue
        - **Application**: Verifies Django application is running

        **Response Status:**
        - `healthy`: All services are operational
        - `degraded`: Some non-critical services are down
        - `unhealthy`: Critical services are down

        **Use Cases:**
        - Kubernetes/Docker health probes
        - Load balancer health checks
        - Monitoring and alerting systems
        - CI/CD pipeline validation
        """,
        responses={
            200: openapi.Response(
                description="System is healthy or degraded",
                schema=HealthCheckSerializer,
                examples={
                    'application/json': {
                        'status': 'healthy',
                        'timestamp': '2024-01-01T12:00:00Z',
                        'version': '1.0.0',
                        'environment': 'dev',
                        'services': [
                            {
                                'service': 'database',
                                'status': 'healthy',
                                'response_time': 12.5,
                                'details': 'PostgreSQL 17 with PostGIS 3.5'
                            },
                            {
                                'service': 'redis',
                                'status': 'healthy',
                                'response_time': 3.2,
                                'details': 'Redis 7.0'
                            },
                            {
                                'service': 'application',
                                'status': 'healthy',
                                'response_time': 0.5,
                                'details': 'Django 5.2.8'
                            }
                        ]
                    }
                }
            ),
            503: openapi.Response(
                description="System is unhealthy - critical services are down",
                schema=HealthCheckSerializer,
                examples={
                    'application/json': {
                        'status': 'unhealthy',
                        'timestamp': '2024-01-01T12:00:00Z',
                        'version': '1.0.0',
                        'environment': 'dev',
                        'services': [
                            {
                                'service': 'database',
                                'status': 'unhealthy',
                                'response_time': None,
                                'details': 'Connection refused'
                            }
                        ]
                    }
                }
            )
        },
        tags=['Health Check']
    )
    def get(self, request):
        """
        Perform health check on all services.
        """
        services_status = []
        overall_status = 'healthy'

        # Check Database
        db_status = self._check_database()
        services_status.append(db_status)
        if db_status['status'] == 'unhealthy':
            overall_status = 'unhealthy'

        # Check Redis
        redis_status = self._check_redis()
        services_status.append(redis_status)
        if redis_status['status'] == 'unhealthy' and overall_status != 'unhealthy':
            overall_status = 'degraded'

        # Application status
        app_status = {
            'service': 'application',
            'status': 'healthy',
            'response_time': 0.5,
            'details': f'Django {self._get_django_version()}'
        }
        services_status.append(app_status)

        # Prepare response
        response_data = {
            'status': overall_status,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'version': getattr(settings, 'APP_VERSION', '1.0.0'),
            'environment': getattr(settings, 'ENVIRONMENT', 'dev'),
            'services': services_status
        }

        # Return appropriate HTTP status code
        http_status = status.HTTP_200_OK if overall_status != 'unhealthy' else status.HTTP_503_SERVICE_UNAVAILABLE

        return Response(response_data, status=http_status)

    def _check_database(self):
        """
        Check database connectivity and query execution.
        """
        start_time = time.time()
        try:
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

                # Check PostGIS version
                try:
                    cursor.execute("SELECT PostGIS_version()")
                    postgis_version = cursor.fetchone()[0]
                    details = f'PostgreSQL with PostGIS {postgis_version.split()[0]}'
                except Exception:
                    details = 'PostgreSQL (PostGIS not available)'

            response_time = (time.time() - start_time) * 1000  # Convert to ms

            return {
                'service': 'database',
                'status': 'healthy',
                'response_time': round(response_time, 2),
                'details': details
            }
        except Exception as e:
            return {
                'service': 'database',
                'status': 'unhealthy',
                'response_time': None,
                'details': f'Error: {str(e)}'
            }

    def _check_redis(self):
        """
        Check Redis connectivity.
        """
        start_time = time.time()
        try:
            # Try to connect to Redis using Django cache
            cache.set('health_check', 'ok', 10)
            result = cache.get('health_check')

            if result == 'ok':
                response_time = (time.time() - start_time) * 1000

                # Try to get Redis version
                try:
                    redis_url = getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0')
                    r = redis.from_url(redis_url)
                    info = r.info()
                    redis_version = info.get('redis_version', 'Unknown')
                    details = f'Redis {redis_version}'
                except Exception:
                    details = 'Redis (version unknown)'

                return {
                    'service': 'redis',
                    'status': 'healthy',
                    'response_time': round(response_time, 2),
                    'details': details
                }
            else:
                return {
                    'service': 'redis',
                    'status': 'unhealthy',
                    'response_time': None,
                    'details': 'Cache test failed'
                }
        except Exception as e:
            return {
                'service': 'redis',
                'status': 'unhealthy',
                'response_time': None,
                'details': f'Error: {str(e)}'
            }

    def _get_django_version(self):
        """
        Get Django version.
        """
        import django
        return django.get_version()
