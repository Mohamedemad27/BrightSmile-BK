import json
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone as dj_timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import redis

from django.db.models import Sum

from apps.users.models import Doctor

from apps.users.models import Patient

from .models import (
    Appointment,
    DoctorReview,
    DoctorService,
    FavoriteDoctor,
    HealthTip,
    MedicalHistory,
    Notification,
    PaymentMethod,
    PaymentPreference,
    PaymentTransaction,
    ServiceCategory,
)
from .payments import create_paymob_intention, fetch_paymob_intention_status
from .serializers import (
    AppointmentCreateSerializer,
    AppointmentListSerializer,
    AppointmentStatusUpdateSerializer,
    DoctorDetailSerializer,
    DoctorServiceSerializer,
    FavoriteDoctorSerializer,
    FeaturedReviewSerializer,
    HealthCheckSerializer,
    HealthTipSerializer,
    MedicalHistorySerializer,
    NotificationSerializer,
    PaymentMethodCreateSerializer,
    PaymentMethodSerializer,
    PaymentMethodUpdateSerializer,
    PaymentPreferenceSerializer,
    PaymentCheckoutSessionCreateSerializer,
    PaymentTransactionSerializer,
    ProfileSerializer,
    ReviewCreateSerializer,
    ServiceCategorySerializer,
    TopDoctorSerializer,
)


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
        db_status = self._check_database()['status']
        redis_status = self._check_redis()['status']

        db_connected = 'connected' if db_status == 'healthy' else 'disconnected'
        redis_connected = 'connected' if redis_status == 'healthy' else 'disconnected'
        overall = 'ok' if db_connected == 'connected' and redis_connected == 'connected' else 'degraded'

        payload = {
            'status': overall,
            'db': db_connected,
            'redis': redis_connected,
        }
        http_status = status.HTTP_200_OK if overall == 'ok' else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(payload, status=http_status)

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


class DailyTipView(APIView):
    """Returns a single health tip that rotates daily, cached in Redis."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='daily_tip',
        operation_summary='Get daily health tip',
        operation_description='Returns one health tip per day, rotating through all active tips. Cached in Redis until midnight UTC.',
        responses={
            200: openapi.Response(
                description='Daily health tip',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_STRING, format='uuid', example='a1b2c3d4-e5f6-7890-abcd-ef1234567890'),
                        'title': openapi.Schema(type=openapi.TYPE_STRING, example='Brushing Technique'),
                        'content': openapi.Schema(type=openapi.TYPE_STRING, example='Brush gently in circular motions for 2 minutes.'),
                    },
                ),
            ),
            404: 'No active tips available',
        },
        tags=['Health Tips'],
    )
    def get(self, request):
        today = date.today()
        cache_key = f'daily_tip:{today.isoformat()}'

        # Try cache first
        cached = cache.get(cache_key)
        if cached:
            return Response(json.loads(cached))

        # DB fallback: get all active tip IDs
        tip_ids = list(
            HealthTip.objects.filter(is_active=True)
            .values_list('id', flat=True)
            .order_by('created_at')
        )

        if not tip_ids:
            return Response(
                {'detail': 'No health tips available.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Deterministic rotation: day-of-year mod count
        index = today.timetuple().tm_yday % len(tip_ids)
        tip = HealthTip.objects.get(id=tip_ids[index])
        data = HealthTipSerializer(tip).data

        # Cache until midnight UTC
        now = datetime.now(timezone.utc)
        midnight = now.replace(
            hour=0, minute=0, second=0, microsecond=0,
        ) + timedelta(days=1)
        ttl = int((midnight - now).total_seconds())
        cache.set(cache_key, json.dumps(data, default=str), timeout=ttl)

        return Response(data)


class TopDoctorsView(APIView):
    """Returns top 4 rated doctors, cached for 1 hour."""

    permission_classes = []

    @swagger_auto_schema(
        operation_id='top_doctors',
        operation_summary='Get top rated doctors',
        operation_description='Returns the top 4 doctors by rating. Cached for 1 hour.',
        responses={
            200: openapi.Response(
                description='Top rated doctors',
                schema=TopDoctorSerializer(many=True),
            ),
        },
        tags=['Doctors'],
    )
    def get(self, request):
        cache_key = 'top_doctors'

        cached = cache.get(cache_key)
        if cached:
            return Response(json.loads(cached))

        doctors = (
            Doctor.objects
            .filter(user__is_active=True, rating__gt=0)
            .select_related('user')
            .order_by('-rating')[:4]
        )

        data = TopDoctorSerializer(doctors, many=True).data
        cache.set(cache_key, json.dumps(data, default=str), timeout=3600)

        return Response(data)


class FeaturedReviewsView(APIView):
    """Returns up to 10 featured reviews for the public landing page."""

    permission_classes = []

    @swagger_auto_schema(
        operation_id='featured_reviews',
        operation_summary='Get featured reviews',
        operation_description='Returns up to 10 reviews sorted by rating then recency. Public endpoint.',
        responses={200: FeaturedReviewSerializer(many=True)},
        tags=['Reviews'],
    )
    def get(self, request):
        reviews = (
            DoctorReview.objects
            .select_related('user', 'doctor__user')
            .order_by('-rating', '-created_at')[:10]
        )
        return Response(FeaturedReviewSerializer(reviews, many=True).data)


class ServiceCategoriesView(APIView):
    """Returns all active service categories, cached for 1 hour."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='service_categories',
        operation_summary='List service categories',
        operation_description='Returns all active service categories.',
        responses={200: ServiceCategorySerializer(many=True)},
        tags=['Services'],
    )
    def get(self, request):
        cache_key = 'service_categories'

        cached = cache.get(cache_key)
        if cached:
            return Response(json.loads(cached))

        categories = ServiceCategory.objects.filter(is_active=True)
        data = ServiceCategorySerializer(categories, many=True).data
        cache.set(cache_key, json.dumps(data, default=str), timeout=3600)

        return Response(data)


class DoctorsByCategoryView(APIView):
    """Returns doctors filtered by category, cached for 1 hour."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='doctors_by_category',
        operation_summary='List doctors by category',
        operation_description='Returns doctors optionally filtered by category ID. If no category specified, returns all active doctors.',
        manual_parameters=[
            openapi.Parameter(
                'category',
                openapi.IN_QUERY,
                description='Category ID to filter by',
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
        ],
        responses={200: TopDoctorSerializer(many=True)},
        tags=['Doctors'],
    )
    def get(self, request):
        category_id = request.query_params.get('category')
        limit = request.query_params.get('limit', 50)
        try:
            limit = max(1, min(int(limit), 200))
        except (TypeError, ValueError):
            limit = 50
        cache_key = f'doctors_by_cat:{category_id or "all"}:{limit}'

        cached = cache.get(cache_key)
        if cached:
            return Response(json.loads(cached))

        doctors = (
            Doctor.objects
            .filter(user__is_active=True)
            .select_related('user')
            .prefetch_related('categories')
            .order_by('-rating')
        )

        if category_id:
            doctors = doctors.filter(categories__id=category_id)

        data = TopDoctorSerializer(doctors[:limit], many=True).data
        cache.set(cache_key, json.dumps(data, default=str), timeout=3600)

        return Response(data)


class DoctorDetailView(APIView):
    """Returns full doctor profile with services and reviews."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='doctor_detail',
        operation_summary='Get doctor details',
        operation_description='Returns full doctor profile including bio, services, reviews.',
        responses={
            200: DoctorDetailSerializer,
            404: 'Doctor not found',
        },
        tags=['Doctors'],
    )
    def get(self, request, doctor_id):
        cache_key = f'doctor_detail:{doctor_id}'

        cached = cache.get(cache_key)
        if cached:
            return Response(json.loads(cached))

        try:
            doctor = (
                Doctor.objects
                .filter(user__id=doctor_id, user__is_active=True)
                .select_related('user')
                .prefetch_related('categories', 'services', 'reviews')
                .get()
            )
        except Doctor.DoesNotExist:
            return Response(
                {'detail': 'Doctor not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = DoctorDetailSerializer(doctor).data
        cache.set(cache_key, json.dumps(data, default=str), timeout=3600)

        return Response(data)


class DoctorServicesView(APIView):
    """Returns active services for a doctor."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='doctor_services',
        operation_summary='List doctor services',
        operation_description='Returns all services offered by a doctor by doctor user UUID.',
        responses={
            200: DoctorServiceSerializer(many=True),
            404: 'Doctor not found',
        },
        tags=['Doctors'],
    )
    def get(self, request, doctor_id):
        doctor_exists = Doctor.objects.filter(user__id=doctor_id, user__is_active=True).exists()
        if not doctor_exists:
            return Response(
                {'detail': 'Doctor not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        limit = request.query_params.get('limit', 100)
        try:
            limit = max(1, min(int(limit), 300))
        except (TypeError, ValueError):
            limit = 100

        services = DoctorService.objects.filter(doctor__user__id=doctor_id).order_by('name')[:limit]
        data = DoctorServiceSerializer(services, many=True).data
        return Response(data)


# ─── Appointment Views ───


class AppointmentListCreateView(APIView):
    """List and create appointments."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='list_appointments',
        operation_summary='List appointments',
        operation_description='Patients see their appointments. Doctors see appointments booked with them.',
        responses={200: AppointmentListSerializer(many=True)},
        tags=['Appointments'],
    )
    def get(self, request):
        user = request.user
        if user.user_type == 'doctor':
            qs = Appointment.objects.filter(doctor__user=user)
        else:
            qs = Appointment.objects.filter(patient=user)

        # Keep response bounded for scalability in legacy endpoint.
        limit = request.query_params.get('limit', 50)
        try:
            limit = max(1, min(int(limit), 200))
        except (TypeError, ValueError):
            limit = 50

        qs = (
            qs.select_related('doctor__user', 'patient')
            .prefetch_related('services')
            .order_by('-date', '-created_at')[:limit]
        )
        data = AppointmentListSerializer(qs, many=True).data
        return Response(data)

    @swagger_auto_schema(
        operation_id='create_appointment',
        operation_summary='Book an appointment',
        operation_description='Patient books an appointment with a doctor, selecting services, date, time, and notes.',
        request_body=AppointmentCreateSerializer,
        responses={
            201: AppointmentListSerializer,
            400: 'Validation error',
        },
        tags=['Appointments'],
    )
    def post(self, request):
        serializer = AppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doctor = Doctor.objects.get(user__id=serializer.validated_data['doctor_id'])
        services = DoctorService.objects.filter(
            id__in=serializer.validated_data['service_ids'],
        )
        total = services.aggregate(total=Sum('price'))['total'] or 0

        appointment = Appointment.objects.create(
            patient=request.user,
            doctor=doctor,
            date=serializer.validated_data['date'],
            time_slot=serializer.validated_data['time_slot'],
            notes=serializer.validated_data['notes'],
            total_price=total,
        )
        appointment.services.set(services)

        data = AppointmentListSerializer(appointment).data
        return Response(data, status=status.HTTP_201_CREATED)


class AppointmentDetailView(APIView):
    """Get appointment detail."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='appointment_detail',
        operation_summary='Get appointment detail',
        responses={200: AppointmentListSerializer, 404: 'Not found'},
        tags=['Appointments'],
    )
    def get(self, request, appointment_id):
        try:
            appt = (
                Appointment.objects
                .select_related('doctor__user', 'patient')
                .prefetch_related('services')
                .get(id=appointment_id)
            )
        except Appointment.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Check access
        user = request.user
        if user != appt.patient and not (user.user_type == 'doctor' and appt.doctor.user == user):
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = AppointmentListSerializer(appt).data
        return Response(data)


class AppointmentStatusView(APIView):
    """Update appointment status."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='update_appointment_status',
        operation_summary='Update appointment status',
        operation_description='Doctor: confirm/reject/complete. Patient: cancel.',
        request_body=AppointmentStatusUpdateSerializer,
        responses={200: AppointmentListSerializer, 400: 'Invalid transition'},
        tags=['Appointments'],
    )
    def patch(self, request, appointment_id):
        serializer = AppointmentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            appt = Appointment.objects.select_related('doctor__user', 'patient').get(id=appointment_id)
        except Appointment.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        new_status = serializer.validated_data['status']

        # Patient can only cancel their own pending/confirmed appointments
        if user == appt.patient:
            if new_status != 'cancelled':
                return Response(
                    {'detail': 'Patients can only cancel appointments.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if appt.status not in ('pending', 'confirmed'):
                return Response(
                    {'detail': 'Cannot cancel this appointment.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        # Doctor can confirm/reject/complete their own appointments
        elif user.user_type == 'doctor' and appt.doctor.user == user:
            valid_transitions = {
                'pending': ['confirmed', 'rejected'],
                'confirmed': ['completed', 'rejected'],
            }
            allowed = valid_transitions.get(appt.status, [])
            if new_status not in allowed:
                return Response(
                    {'detail': f'Cannot change from {appt.status} to {new_status}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        appt.status = new_status
        appt.save(update_fields=['status', 'updated_at'])

        data = AppointmentListSerializer(appt).data
        return Response(data)


class AppointmentReviewView(APIView):
    """Create a review for a completed appointment."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='create_appointment_review',
        operation_summary='Review a completed appointment',
        operation_description='Patient can review only after the doctor marks the appointment as completed. One review per appointment.',
        request_body=ReviewCreateSerializer,
        responses={201: 'Review created', 400: 'Validation error'},
        tags=['Appointments'],
    )
    def post(self, request, appointment_id):
        try:
            appt = Appointment.objects.select_related('doctor__user').get(id=appointment_id)
        except Appointment.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if request.user != appt.patient:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if appt.status != 'completed':
            return Response(
                {'detail': 'You can only review completed appointments.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if hasattr(appt, 'review'):
            return Response(
                {'detail': 'You have already reviewed this appointment.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        DoctorReview.objects.create(
            appointment=appt,
            doctor=appt.doctor,
            user=request.user,
            rating=serializer.validated_data['rating'],
            comment=serializer.validated_data['comment'],
        )

        # Update doctor's rating
        reviews = DoctorReview.objects.filter(doctor=appt.doctor)
        total = reviews.count()
        avg = sum(r.rating for r in reviews) / total if total else 0
        Doctor.objects.filter(user=appt.doctor.user).update(
            rating=round(avg, 1),
            total_reviews=total,
        )

        return Response({'detail': 'Review submitted.'}, status=status.HTTP_201_CREATED)


class PaymentCheckoutSessionCreateView(APIView):
    """Create a payment transaction and return checkout URL."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='create_payment_checkout_session',
        operation_summary='Create payment checkout session',
        request_body=PaymentCheckoutSessionCreateSerializer,
        responses={201: PaymentTransactionSerializer, 400: 'Validation error', 404: 'Appointment not found'},
        tags=['Payments'],
    )
    def post(self, request):
        serializer = PaymentCheckoutSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appointment_id = serializer.validated_data['appointment_id']
        provider = serializer.validated_data.get('provider', 'paymob')

        try:
            appointment = Appointment.objects.get(id=appointment_id, patient=request.user)
        except Appointment.DoesNotExist:
            return Response({'detail': 'Appointment not found.'}, status=status.HTTP_404_NOT_FOUND)

        if appointment.status in ('rejected', 'cancelled'):
            return Response({'detail': 'Cannot pay for rejected/cancelled appointment.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(appointment.total_price))
        except (InvalidOperation, TypeError, ValueError):
            return Response({'detail': 'Invalid appointment total price.'}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({'detail': 'Appointment total must be greater than zero.'}, status=status.HTTP_400_BAD_REQUEST)

        existing_paid = PaymentTransaction.objects.filter(
            appointment=appointment,
            user=request.user,
            status='paid',
        ).first()
        if existing_paid:
            return Response(PaymentTransactionSerializer(existing_paid).data, status=status.HTTP_200_OK)

        tx = PaymentTransaction.objects.create(
            appointment=appointment,
            user=request.user,
            provider=provider,
            status='pending',
            amount=amount,
            currency='EGP',
        )

        try:
            paymob_data = create_paymob_intention(
                user=request.user,
                amount=amount,
                currency='EGP',
                merchant_order_id=str(tx.id),
            )
        except Exception as exc:
            tx.status = 'failed'
            tx.provider_payload = {'error': str(exc)}
            tx.save(update_fields=['status', 'provider_payload', 'updated_at'])
            return Response(
                {'detail': f'Failed to create checkout session: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tx.provider_reference = paymob_data['provider_reference']
        tx.client_secret = paymob_data['client_secret']
        tx.checkout_url = paymob_data['checkout_url']
        tx.status = 'processing'
        tx.provider_payload = paymob_data['raw']
        tx.save(update_fields=[
            'provider_reference',
            'client_secret',
            'checkout_url',
            'status',
            'provider_payload',
            'updated_at',
        ])

        return Response(PaymentTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class PaymentTransactionStatusView(APIView):
    """Return payment status, refreshing from Paymob if possible."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='payment_transaction_status',
        operation_summary='Get payment transaction status',
        responses={200: PaymentTransactionSerializer, 404: 'Not found'},
        tags=['Payments'],
    )
    def get(self, request, transaction_id):
        try:
            tx = PaymentTransaction.objects.select_related('appointment').get(id=transaction_id, user=request.user)
        except PaymentTransaction.DoesNotExist:
            return Response({'detail': 'Payment transaction not found.'}, status=status.HTTP_404_NOT_FOUND)

        if tx.status not in ('paid', 'failed', 'cancelled') and tx.provider == 'paymob' and tx.provider_reference:
            try:
                status_data = fetch_paymob_intention_status(tx.provider_reference)
                tx.provider_payload = status_data['raw']
                if status_data['is_paid']:
                    tx.status = 'paid'
                    tx.paid_at = tx.paid_at or dj_timezone.now()
                elif status_data['status'] in {'failed', 'declined', 'cancelled'}:
                    tx.status = 'failed'
                tx.save(update_fields=['provider_payload', 'status', 'paid_at', 'updated_at'])
            except Exception:
                # Keep existing state when provider status refresh fails.
                pass

        return Response(PaymentTransactionSerializer(tx).data)


class PaymentMethodListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='list_payment_methods',
        operation_summary='List saved payment methods',
        responses={200: PaymentMethodSerializer(many=True)},
        tags=['Payments'],
    )
    def get(self, request):
        methods = PaymentMethod.objects.filter(user=request.user, is_active=True)
        return Response(PaymentMethodSerializer(methods, many=True).data)

    @swagger_auto_schema(
        operation_id='create_payment_method',
        operation_summary='Save a payment method',
        request_body=PaymentMethodCreateSerializer,
        responses={201: PaymentMethodSerializer, 400: 'Validation error'},
        tags=['Payments'],
    )
    def post(self, request):
        serializer = PaymentMethodCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        last4 = data['card_number'][-4:]

        if data.get('is_default'):
            PaymentMethod.objects.filter(user=request.user, is_default=True).update(is_default=False)

        method = PaymentMethod.objects.create(
            user=request.user,
            brand=data['brand'],
            last4=last4,
            holder_name=data['holder_name'],
            expiry=data['expiry'],
            is_default=bool(data.get('is_default')),
        )

        if not PaymentMethod.objects.filter(user=request.user, is_default=True, is_active=True).exists():
            method.is_default = True
            method.save(update_fields=['is_default', 'updated_at'])

        return Response(PaymentMethodSerializer(method).data, status=status.HTTP_201_CREATED)


class PaymentMethodDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_method(self, user, method_id):
        try:
            return PaymentMethod.objects.get(id=method_id, user=user, is_active=True)
        except PaymentMethod.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_id='update_payment_method',
        operation_summary='Update payment method',
        request_body=PaymentMethodUpdateSerializer,
        responses={200: PaymentMethodSerializer, 404: 'Not found'},
        tags=['Payments'],
    )
    def patch(self, request, method_id):
        method = self._get_method(request.user, method_id)
        if method is None:
            return Response({'detail': 'Payment method not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PaymentMethodUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_default = serializer.validated_data['is_default']
        if is_default:
            PaymentMethod.objects.filter(user=request.user, is_default=True).exclude(id=method.id).update(is_default=False)
        method.is_default = is_default
        method.save(update_fields=['is_default', 'updated_at'])

        return Response(PaymentMethodSerializer(method).data)

    @swagger_auto_schema(
        operation_id='delete_payment_method',
        operation_summary='Delete payment method',
        responses={204: 'Deleted', 404: 'Not found'},
        tags=['Payments'],
    )
    def delete(self, request, method_id):
        method = self._get_method(request.user, method_id)
        if method is None:
            return Response({'detail': 'Payment method not found.'}, status=status.HTTP_404_NOT_FOUND)

        was_default = method.is_default
        method.is_active = False
        method.is_default = False
        method.save(update_fields=['is_active', 'is_default', 'updated_at'])

        if was_default:
            fallback = PaymentMethod.objects.filter(
                user=request.user,
                is_active=True,
            ).order_by('-created_at').first()
            if fallback:
                fallback.is_default = True
                fallback.save(update_fields=['is_default', 'updated_at'])

        return Response(status=status.HTTP_204_NO_CONTENT)


class PaymentPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='get_payment_preference',
        operation_summary='Get mobile wallet and cash-on-visit preferences',
        responses={200: PaymentPreferenceSerializer},
        tags=['Payments'],
    )
    def get(self, request):
        preference, _ = PaymentPreference.objects.get_or_create(user=request.user)
        return Response(PaymentPreferenceSerializer(preference).data)

    @swagger_auto_schema(
        operation_id='update_payment_preference',
        operation_summary='Update mobile wallet and cash-on-visit preferences',
        request_body=PaymentPreferenceSerializer,
        responses={200: PaymentPreferenceSerializer},
        tags=['Payments'],
    )
    def patch(self, request):
        preference, _ = PaymentPreference.objects.get_or_create(user=request.user)
        serializer = PaymentPreferenceSerializer(preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data.get('mobile_wallet_enabled') is False:
            preference.mobile_wallet_provider = ''
        serializer.save()
        return Response(PaymentPreferenceSerializer(preference).data)


class UpcomingAppointmentView(APIView):
    """Get the next upcoming confirmed appointment for the current user."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='upcoming_appointment',
        operation_summary='Get next upcoming appointment',
        responses={200: AppointmentListSerializer, 404: 'No upcoming'},
        tags=['Appointments'],
    )
    def get(self, request):
        today = date.today()
        appt = (
            Appointment.objects
            .filter(
                patient=request.user,
                status__in=['pending', 'confirmed'],
                date__gte=today,
            )
            .select_related('doctor__user', 'patient')
            .prefetch_related('services')
            .order_by('date', 'time_slot')
            .first()
        )

        if not appt:
            return Response({'detail': 'No upcoming appointments.'}, status=status.HTTP_404_NOT_FOUND)

        data = AppointmentListSerializer(appt).data
        return Response(data)


# ─── Chatbot View ───


class ChatbotView(APIView):
    """Rule-based chatbot that answers questions using DB data."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='chatbot',
        operation_summary='Ask the chatbot',
        operation_description='Send a message and get a response based on DB data.',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['message'],
            properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING, example='Show my appointments'),
            },
        ),
        responses={200: 'Chatbot response'},
        tags=['Chatbot'],
    )
    def post(self, request):
        message = request.data.get('message', '').lower().strip()
        if not message:
            return Response({'reply': 'Please type a message.', 'data': None})

        user = request.user
        today = date.today()

        # Appointments
        if any(kw in message for kw in ['appointment', 'booking', 'booked', 'schedule']):
            appts = (
                Appointment.objects.filter(patient=user)
                .select_related('doctor__user').prefetch_related('services')
                .order_by('-date')[:5]
            )
            if not appts:
                return Response({'reply': 'You have no appointments yet.', 'data': None})
            items = []
            for a in appts:
                items.append({
                    'doctor': a.doctor.full_name, 'date': str(a.date),
                    'time': a.time_slot, 'status': a.status,
                    'services': [s.name for s in a.services.all()],
                })
            return Response({'reply': f'You have {len(items)} recent appointment(s):', 'data': {'type': 'appointments', 'items': items}})

        # Upcoming
        if any(kw in message for kw in ['upcoming', 'next', 'when']):
            appt = Appointment.objects.filter(patient=user, status__in=['pending', 'confirmed'], date__gte=today).select_related('doctor__user').order_by('date').first()
            if not appt:
                return Response({'reply': 'You have no upcoming appointments.', 'data': None})
            return Response({'reply': f'Your next appointment is with Dr. {appt.doctor.full_name} on {appt.date} at {appt.time_slot} ({appt.status}).', 'data': None})

        # Top rated / recommendations
        if any(kw in message for kw in ['recommend', 'best', 'top', 'suggestion']):
            doctors = Doctor.objects.filter(user__is_active=True, rating__gt=0).select_related('user').order_by('-rating')[:4]
            items = [{'name': d.full_name, 'rating': float(d.rating), 'id': str(d.user_id)} for d in doctors]
            return Response({'reply': 'Here are the top rated doctors:', 'data': {'type': 'doctors', 'items': items}})

        # Find doctor by name
        if any(kw in message for kw in ['doctor', 'dr.', 'find', 'search']):
            search = message
            for kw in ['find doctor', 'search doctor', 'find', 'search', 'doctor', 'dr.', 'dr']:
                search = search.replace(kw, '').strip()
            qs = Doctor.objects.filter(user__is_active=True).select_related('user')
            if search:
                qs = qs.filter(user__first_name__icontains=search) | qs.filter(user__last_name__icontains=search)
            items = [{'name': d.full_name, 'rating': float(d.rating), 'id': str(d.user_id)} for d in qs.order_by('-rating')[:5]]
            if not items:
                return Response({'reply': f'No doctors found matching "{search}".', 'data': None})
            return Response({'reply': f'Found {len(items)} doctor(s):', 'data': {'type': 'doctors', 'items': items}})

        # Available / working hours
        if any(kw in message for kw in ['available', 'availability', 'free', 'open', 'hour']):
            doctors = Doctor.objects.filter(user__is_active=True).select_related('user').order_by('-rating')
            items = [{'name': d.full_name, 'hours': d.working_hours, 'location': d.location} for d in doctors]
            return Response({'reply': 'Available doctors and their hours:', 'data': {'type': 'availability', 'items': items}})

        # Near / location
        if any(kw in message for kw in ['near', 'nearby', 'close', 'location', 'area']):
            doctors = Doctor.objects.filter(user__is_active=True).exclude(location='').select_related('user')
            items = [{'name': d.full_name, 'location': d.location, 'id': str(d.user_id)} for d in doctors]
            return Response({'reply': 'Doctors and their locations:', 'data': {'type': 'locations', 'items': items}})

        # Categories / services
        if any(kw in message for kw in ['category', 'service', 'veneer', 'whiten', 'implant']):
            cats = ServiceCategory.objects.filter(is_active=True)
            items = [{'name': c.name, 'id': str(c.id)} for c in cats]
            return Response({'reply': 'We offer these service categories:', 'data': {'type': 'categories', 'items': items}})

        # Help / greeting
        if any(kw in message for kw in ['help', 'hi', 'hello', 'hey', 'what can']):
            return Response({
                'reply': 'Hi! I can help you with:\n\u2022 Your appointments\n\u2022 Next upcoming appointment\n\u2022 Doctor recommendations\n\u2022 Find doctors by name\n\u2022 Doctor availability\n\u2022 Nearby doctors\n\u2022 Service categories',
                'data': None,
            })

        # Fallback
        return Response({
            'reply': 'I\'m not sure how to help with that. Try asking about appointments, doctors, or type "help" to see what I can do!',
            'data': None,
        })


# ─── Notification Views ───


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='list_notifications',
        operation_summary='List user notifications',
        responses={200: NotificationSerializer(many=True)},
        tags=['Notifications'],
    )
    def get(self, request):
        notifs = Notification.objects.filter(user=request.user)[:50]
        return Response(NotificationSerializer(notifs, many=True).data)


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='mark_notification_read',
        operation_summary='Mark notification as read',
        tags=['Notifications'],
    )
    def patch(self, request, notification_id):
        try:
            notif = Notification.objects.get(id=notification_id, user=request.user)
        except Notification.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notif).data)


class NotificationReadAllView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='mark_all_notifications_read',
        operation_summary='Mark all notifications as read',
        tags=['Notifications'],
    )
    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'detail': 'All notifications marked as read.'})


# ─── Medical History View ───


class MedicalHistoryView(APIView):
    """Get, create, or update the current patient's medical history."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='get_medical_history',
        operation_summary='Get medical history',
        operation_description='Returns the authenticated patient\'s medical history.',
        responses={
            200: MedicalHistorySerializer,
            404: 'No medical history found',
        },
        tags=['Medical History'],
    )
    def get(self, request):
        try:
            history = MedicalHistory.objects.get(user=request.user)
        except MedicalHistory.DoesNotExist:
            return Response(
                {'detail': 'No medical history found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(MedicalHistorySerializer(history).data)

    @swagger_auto_schema(
        operation_id='create_medical_history',
        operation_summary='Create medical history',
        operation_description='Creates a medical history record for the authenticated patient.',
        request_body=MedicalHistorySerializer,
        responses={
            201: MedicalHistorySerializer,
            400: 'Validation error or already exists',
        },
        tags=['Medical History'],
    )
    def post(self, request):
        if request.user.user_type != 'patient':
            return Response(
                {'detail': 'Only patients can create medical history.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if MedicalHistory.objects.filter(user=request.user).exists():
            return Response(
                {'detail': 'Medical history already exists. Use PATCH to update.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = MedicalHistorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_id='update_medical_history',
        operation_summary='Update medical history',
        operation_description='Partially updates the authenticated patient\'s medical history.',
        request_body=MedicalHistorySerializer,
        responses={
            200: MedicalHistorySerializer,
            404: 'No medical history found',
        },
        tags=['Medical History'],
    )
    def patch(self, request):
        try:
            history = MedicalHistory.objects.get(user=request.user)
        except MedicalHistory.DoesNotExist:
            return Response(
                {'detail': 'No medical history found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = MedicalHistorySerializer(history, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ─── Profile View ───


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='get_profile',
        operation_summary='Get current user profile',
        responses={200: ProfileSerializer},
        tags=['Profile'],
    )
    def get(self, request):
        user = request.user
        data = {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'user_type': user.user_type,
            'is_verified': user.is_verified,
            'push_notifications': user.push_notifications,
            'email_notifications': user.email_notifications,
        }
        if user.user_type == 'patient':
            try:
                patient = user.patient_profile
                data['phone_number'] = patient.phone_number
                data['date_of_birth'] = str(patient.date_of_birth) if patient.date_of_birth else None
            except Patient.DoesNotExist:
                pass
        elif user.user_type == 'doctor':
            try:
                doctor = user.doctor_profile
                data['phone_number'] = doctor.phone_number
            except Doctor.DoesNotExist:
                pass
        return Response(data)

    @swagger_auto_schema(
        operation_id='update_profile',
        operation_summary='Update current user profile',
        request_body=ProfileSerializer,
        responses={200: ProfileSerializer},
        tags=['Profile'],
    )
    def patch(self, request):
        user = request.user
        data = request.data

        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'push_notifications' in data:
            user.push_notifications = data['push_notifications']
        if 'email_notifications' in data:
            user.email_notifications = data['email_notifications']
        user.save()

        if user.user_type == 'patient':
            try:
                patient = user.patient_profile
                if 'phone_number' in data:
                    patient.phone_number = data['phone_number']
                if 'date_of_birth' in data:
                    patient.date_of_birth = data['date_of_birth']
                patient.save()
            except Patient.DoesNotExist:
                pass
        elif user.user_type == 'doctor':
            try:
                doctor = user.doctor_profile
                if 'phone_number' in data:
                    doctor.phone_number = data['phone_number']
                doctor.save()
            except Doctor.DoesNotExist:
                pass

        return self.get(request)


# ─── Favorite Doctor Views ───


class FavoriteDoctorListView(APIView):
    """List all favorite doctors for the authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        favorites = FavoriteDoctor.objects.filter(user=request.user).select_related('doctor', 'doctor__user')
        serializer = FavoriteDoctorSerializer(favorites, many=True)
        return Response(serializer.data)


class FavoriteDoctorIdsView(APIView):
    """Return list of favorited doctor IDs for the authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ids = FavoriteDoctor.objects.filter(user=request.user).values_list('doctor__user__id', flat=True)
        return Response(list(ids))


class FavoriteDoctorToggleView(APIView):
    """Toggle favorite status for a doctor."""
    permission_classes = [IsAuthenticated]

    def post(self, request, doctor_id):
        from apps.users.models import Doctor
        try:
            doctor = Doctor.objects.get(user__id=doctor_id)
        except Doctor.DoesNotExist:
            return Response({'detail': 'Doctor not found.'}, status=status.HTTP_404_NOT_FOUND)

        favorite, created = FavoriteDoctor.objects.get_or_create(
            user=request.user,
            doctor=doctor,
        )
        if not created:
            favorite.delete()

        return Response({'is_favorited': created})
