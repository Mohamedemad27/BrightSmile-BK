from celery.result import AsyncResult
from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dashboard.permissions import AdminDashboardPermission, DoctorPermission

from .serializers import ReportExportRequestSerializer, ReportQuerySerializer
from .services.report_data_service import ReportDataService
from .tasks import generate_report_export_task


def _filters_from_request(request):
    ser = ReportQuerySerializer(data=request.query_params)
    ser.is_valid(raise_exception=True)
    return ser.validated_data


class _AdminReportBase(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = "view_analytics"
    report_type = ""

    def get(self, request):
        data = ReportDataService.generate(
            report_type=self.report_type,
            user=request.user,
            filters=_filters_from_request(request),
        )
        return Response(data)


class AdminAppointmentsReportView(_AdminReportBase):
    report_type = "admin_appointments"


class AdminPatientsReportView(_AdminReportBase):
    report_type = "admin_patients"


class AdminAuditReportView(_AdminReportBase):
    report_type = "admin_audit"


class AdminDoctorsReportView(_AdminReportBase):
    report_type = "admin_doctors"


class DoctorAppointmentsReportView(APIView):
    permission_classes = [DoctorPermission]

    def get(self, request):
        data = ReportDataService.generate(
            report_type="doctor_appointments",
            user=request.user,
            filters=_filters_from_request(request),
        )
        return Response(data)


class DoctorPatientsReportView(APIView):
    permission_classes = [DoctorPermission]

    def get(self, request):
        data = ReportDataService.generate(
            report_type="doctor_patients",
            user=request.user,
            filters=_filters_from_request(request),
        )
        return Response(data)


class PatientReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.user_type != "patient":
            return Response({"detail": "Only patients can access this report."}, status=status.HTTP_403_FORBIDDEN)
        data = ReportDataService.generate(
            report_type="patient_report",
            user=request.user,
            filters=_filters_from_request(request),
        )
        return Response(data)


class ReportExportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReportExportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        report_type = payload["report_type"]

        if report_type.startswith("admin_") and request.user.user_type != "admin":
            return Response({"detail": "Admin reports require admin account."}, status=status.HTTP_403_FORBIDDEN)
        if report_type.startswith("doctor_") and request.user.user_type != "doctor":
            return Response({"detail": "Doctor reports require doctor account."}, status=status.HTTP_403_FORBIDDEN)
        if report_type == "patient_report" and request.user.user_type != "patient":
            return Response({"detail": "Patient report requires patient account."}, status=status.HTTP_403_FORBIDDEN)

        task = generate_report_export_task.delay(
            report_type=report_type,
            user_id=str(request.user.id),
            filters=payload.get("filters") or {},
            file_format=payload["file_format"],
        )
        cache.set(f"report_task_owner:{task.id}", str(request.user.id), timeout=86400)
        return Response({"task_id": task.id, "status": "queued"}, status=status.HTTP_202_ACCEPTED)


class ReportTaskStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        owner_id = cache.get(f"report_task_owner:{task_id}")
        if owner_id and owner_id != str(request.user.id) and request.user.user_type != "admin":
            return Response({"detail": "Not allowed to access this task."}, status=status.HTTP_403_FORBIDDEN)

        result = AsyncResult(task_id)
        data = {
            "task_id": task_id,
            "status": result.status.lower(),
            "download_url": None,
            "error": None,
        }
        if result.successful():
            payload = result.result or {}
            data["download_url"] = payload.get("download_url")
        elif result.failed():
            data["error"] = str(result.result)
        return Response(data)
