from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count, Sum

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import Appointment, DoctorReview, DoctorService
from apps.users.models import Secretary
from apps.users.permissions import IsDoctor
from apps.dashboard.serializers.dashboard_serializers import (
    DoctorAppointmentSerializer,
    DoctorPatientSerializer,
    DoctorProfileSerializer,
    DoctorReviewSerializer,
    DoctorSecretaryCreateSerializer,
    DoctorSecretaryListSerializer,
    DoctorSecretaryUpdateSerializer,
    DoctorServiceSerializer,
)

User = get_user_model()


# ──────────────────────────────────────────────────────────────────────
# Pagination
# ──────────────────────────────────────────────────────────────────────


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ──────────────────────────────────────────────────────────────────────
# Doctor Profile
# ──────────────────────────────────────────────────────────────────────


class DoctorProfileView(APIView):
    """Get or update the authenticated doctor's own profile."""

    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = request.user.doctor_profile
        serializer = DoctorProfileSerializer(doctor)
        return Response(serializer.data)

    def patch(self, request):
        doctor = request.user.doctor_profile
        serializer = DoctorProfileSerializer(doctor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(DoctorProfileSerializer(doctor).data)


# ──────────────────────────────────────────────────────────────────────
# Doctor Appointments
# ──────────────────────────────────────────────────────────────────────


class DoctorAppointmentListView(APIView):
    """List the authenticated doctor's appointments with optional filters."""

    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = request.user.doctor_profile
        qs = (
            Appointment.objects
            .filter(doctor=doctor)
            .select_related('doctor__user', 'patient')
            .prefetch_related('services')
        )

        # Filter by status
        appt_status = request.query_params.get('status')
        if appt_status:
            qs = qs.filter(status=appt_status)

        # Filter by date range
        date_from = request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(date__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(date__lte=date_to)

        qs = qs.order_by('-date', '-created_at')

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = DoctorAppointmentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class DoctorAppointmentStatusView(APIView):
    """Update the status of an appointment belonging to this doctor."""

    permission_classes = [IsDoctor]

    VALID_TRANSITIONS = {
        'pending': ['confirmed', 'rejected'],
        'confirmed': ['completed', 'rejected'],
    }

    def patch(self, request, pk):
        doctor = request.user.doctor_profile

        try:
            appointment = (
                Appointment.objects
                .select_related('doctor__user', 'patient')
                .prefetch_related('services')
                .get(id=pk, doctor=doctor)
            )
        except Appointment.DoesNotExist:
            return Response(
                {'detail': 'Appointment not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get('status')
        if not new_status:
            return Response(
                {'detail': 'Status field is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed = self.VALID_TRANSITIONS.get(appointment.status, [])
        if new_status not in allowed:
            return Response(
                {'detail': f'Cannot change from {appointment.status} to {new_status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        appointment.status = new_status
        appointment.save(update_fields=['status', 'updated_at'])

        serializer = DoctorAppointmentSerializer(appointment)
        return Response(serializer.data)


# ──────────────────────────────────────────────────────────────────────
# Doctor Patients
# ──────────────────────────────────────────────────────────────────────


class DoctorPatientListView(APIView):
    """List unique patients who have booked with this doctor."""

    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = request.user.doctor_profile

        patients = (
            User.objects
            .filter(
                appointments_as_patient__doctor=doctor,
            )
            .annotate(
                total_appointments=Count('appointments_as_patient', distinct=True),
            )
            .order_by('-appointments_as_patient__date')
            .distinct()
        )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(patients, request)
        serializer = DoctorPatientSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ──────────────────────────────────────────────────────────────────────
# Doctor Services
# ──────────────────────────────────────────────────────────────────────


class DoctorServiceListCreateView(APIView):
    """List and create services for the authenticated doctor."""

    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = request.user.doctor_profile
        services = DoctorService.objects.filter(doctor=doctor).order_by('name')

        paginator = StandardPagination()
        page = paginator.paginate_queryset(services, request)
        serializer = DoctorServiceSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        doctor = request.user.doctor_profile
        serializer = DoctorServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(doctor=doctor)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DoctorServiceDetailView(APIView):
    """Update or delete a service belonging to this doctor."""

    permission_classes = [IsDoctor]

    def _get_service(self, request, pk):
        doctor = request.user.doctor_profile
        try:
            return DoctorService.objects.get(id=pk, doctor=doctor)
        except DoctorService.DoesNotExist:
            return None

    def patch(self, request, pk):
        service = self._get_service(request, pk)
        if service is None:
            return Response(
                {'detail': 'Service not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DoctorServiceSerializer(service, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        service = self._get_service(request, pk)
        if service is None:
            return Response(
                {'detail': 'Service not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        service.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ──────────────────────────────────────────────────────────────────────
# Doctor Secretaries
# ──────────────────────────────────────────────────────────────────────


class DoctorSecretaryListCreateView(APIView):
    """List and create secretaries for the authenticated doctor."""

    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = request.user.doctor_profile
        secretaries = (
            Secretary.objects
            .filter(doctor=doctor)
            .select_related('user')
            .order_by('-created_at')
        )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(secretaries, request)
        serializer = DoctorSecretaryListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @transaction.atomic
    def post(self, request):
        doctor = request.user.doctor_profile
        serializer = DoctorSecretaryCreateSerializer(
            data=request.data,
            context={'doctor': doctor},
        )
        serializer.is_valid(raise_exception=True)
        secretary = serializer.save()

        # Add the new user to the Secretary group
        secretary_group, _ = Group.objects.get_or_create(name='Secretary')
        secretary.user.groups.add(secretary_group)

        return Response(
            DoctorSecretaryListSerializer(secretary).data,
            status=status.HTTP_201_CREATED,
        )


class DoctorSecretaryDetailView(APIView):
    """Update or deactivate a secretary belonging to this doctor."""

    permission_classes = [IsDoctor]

    def _get_secretary(self, request, pk):
        doctor = request.user.doctor_profile
        try:
            return Secretary.objects.select_related('user').get(
                user_id=pk,
                doctor=doctor,
            )
        except Secretary.DoesNotExist:
            return None

    def patch(self, request, pk):
        secretary = self._get_secretary(request, pk)
        if secretary is None:
            return Response(
                {'detail': 'Secretary not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DoctorSecretaryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        if 'phone_number' in data:
            secretary.phone_number = data['phone_number']
        if 'is_active' in data:
            secretary.is_active = data['is_active']
        secretary.save()

        return Response(DoctorSecretaryListSerializer(secretary).data)

    def delete(self, request, pk):
        secretary = self._get_secretary(request, pk)
        if secretary is None:
            return Response(
                {'detail': 'Secretary not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Deactivate rather than hard-delete
        secretary.is_active = False
        secretary.save(update_fields=['is_active', 'updated_at'])

        secretary.user.is_active = False
        secretary.user.save(update_fields=['is_active', 'updated_at'])

        return Response(
            {'detail': 'Secretary deactivated.'},
            status=status.HTTP_200_OK,
        )


# ──────────────────────────────────────────────────────────────────────
# Doctor Reviews
# ──────────────────────────────────────────────────────────────────────


class DoctorReviewListView(APIView):
    """List all reviews for the authenticated doctor."""

    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = request.user.doctor_profile
        reviews = (
            DoctorReview.objects
            .filter(doctor=doctor)
            .select_related('user', 'appointment')
            .order_by('-created_at')
        )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(reviews, request)
        serializer = DoctorReviewSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ──────────────────────────────────────────────────────────────────────
# Doctor Analytics
# ──────────────────────────────────────────────────────────────────────


class DoctorAnalyticsView(APIView):
    """Return analytics and stats for the authenticated doctor."""

    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = request.user.doctor_profile

        appointments = Appointment.objects.filter(doctor=doctor)

        total_appointments = appointments.count()
        completed_appointments = appointments.filter(status='completed').count()
        pending_appointments = appointments.filter(status='pending').count()
        cancelled_appointments = appointments.filter(status='cancelled').count()

        total_patients = (
            appointments
            .values('patient')
            .distinct()
            .count()
        )

        revenue_total = (
            appointments
            .filter(status='completed')
            .aggregate(total=Sum('total_price'))['total']
        ) or 0

        total_reviews = doctor.total_reviews
        average_rating = float(doctor.rating)

        # This month stats
        today = date.today()
        first_of_month = today.replace(day=1)

        appointments_this_month = appointments.filter(date__gte=first_of_month).count()
        revenue_this_month = (
            appointments
            .filter(status='completed', date__gte=first_of_month)
            .aggregate(total=Sum('total_price'))['total']
        ) or 0

        data = {
            'total_appointments': total_appointments,
            'completed_appointments': completed_appointments,
            'pending_appointments': pending_appointments,
            'cancelled_appointments': cancelled_appointments,
            'total_patients': total_patients,
            'total_reviews': total_reviews,
            'average_rating': average_rating,
            'total_revenue': revenue_total,
            'appointments_this_month': appointments_this_month,
            'revenue_this_month': revenue_this_month,
        }

        return Response(data)
