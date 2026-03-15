from django.db.models import Count

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import Appointment
from apps.users.permissions import IsSecretary
from apps.dashboard.serializers.dashboard_serializers import (
    DoctorAppointmentSerializer,
    DoctorPatientSerializer,
    SecretaryDoctorSerializer,
)

from django.contrib.auth import get_user_model

User = get_user_model()


# ──────────────────────────────────────────────────────────────────────
# Pagination
# ──────────────────────────────────────────────────────────────────────


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ──────────────────────────────────────────────────────────────────────
# Secretary – Assigned Doctor
# ──────────────────────────────────────────────────────────────────────


class SecretaryDoctorView(APIView):
    """Get the assigned doctor's profile (read-only)."""

    permission_classes = [IsSecretary]

    def get(self, request):
        doctor = request.user.secretary_profile.doctor
        serializer = SecretaryDoctorSerializer(doctor)
        return Response(serializer.data)


# ──────────────────────────────────────────────────────────────────────
# Secretary – Appointments
# ──────────────────────────────────────────────────────────────────────


class SecretaryAppointmentListView(APIView):
    """List appointments for the secretary's assigned doctor."""

    permission_classes = [IsSecretary]

    def get(self, request):
        doctor = request.user.secretary_profile.doctor
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


class SecretaryAppointmentStatusView(APIView):
    """Update appointment status on behalf of the assigned doctor."""

    permission_classes = [IsSecretary]

    VALID_TRANSITIONS = {
        'pending': ['confirmed', 'rejected'],
        'confirmed': ['completed', 'rejected'],
    }

    def patch(self, request, pk):
        doctor = request.user.secretary_profile.doctor

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
# Secretary – Patients
# ──────────────────────────────────────────────────────────────────────


class SecretaryPatientListView(APIView):
    """List unique patients for the secretary's assigned doctor."""

    permission_classes = [IsSecretary]

    def get(self, request):
        doctor = request.user.secretary_profile.doctor

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
