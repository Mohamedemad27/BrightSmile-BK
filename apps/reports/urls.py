from django.urls import path

from .views import (
    AdminAppointmentsReportView,
    AdminAuditReportView,
    AdminDoctorsReportView,
    AdminPatientsReportView,
    DoctorAppointmentsReportHtmlView,
    DoctorAppointmentsReportView,
    DoctorPatientsReportHtmlView,
    DoctorPatientsReportView,
    PatientReportView,
    ReportExportView,
    ReportTaskStatusView,
)

app_name = "reports"

urlpatterns = [
    path("admin/appointments/", AdminAppointmentsReportView.as_view(), name="admin-appointments-report"),
    path("admin/patients/", AdminPatientsReportView.as_view(), name="admin-patients-report"),
    path("admin/audit/", AdminAuditReportView.as_view(), name="admin-audit-report"),
    path("admin/doctors/", AdminDoctorsReportView.as_view(), name="admin-doctors-report"),
    path("doctor/appointments/html/", DoctorAppointmentsReportHtmlView.as_view(), name="doctor-appointments-report-html"),
    path("doctor/appointments/", DoctorAppointmentsReportView.as_view(), name="doctor-appointments-report"),
    path("doctor/patients/html/", DoctorPatientsReportHtmlView.as_view(), name="doctor-patients-report-html"),
    path("doctor/patients/", DoctorPatientsReportView.as_view(), name="doctor-patients-report"),
    path("patient/me/", PatientReportView.as_view(), name="patient-report"),
    path("export/", ReportExportView.as_view(), name="report-export"),
    path("<str:task_id>/", ReportTaskStatusView.as_view(), name="report-status"),
]
