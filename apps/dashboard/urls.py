from django.urls import path

from .views import (
    # Common
    DashboardMeView,
    # Admin
    AdminUserListView,
    AdminUserDetailView,
    AdminDoctorListView,
    AdminDoctorApproveView,
    AdminAppointmentListView,
    AdminReviewListView,
    AdminReviewDeleteView,
    AdminCategoryListCreateView,
    AdminCategoryDetailView,
    AdminHealthTipListCreateView,
    AdminHealthTipDetailView,
    AdminAnalyticsView,
    AdminRoleListCreateView,
    AdminRoleDetailView,
    AdminRoleAssignView,
    AdminRolePermissionsView,
    # Doctor
    DoctorProfileView,
    DoctorAppointmentListView,
    DoctorAppointmentStatusView,
    DoctorPatientListView,
    DoctorServiceListCreateView,
    DoctorServiceDetailView,
    DoctorSecretaryListCreateView,
    DoctorSecretaryDetailView,
    DoctorReviewListView,
    DoctorAnalyticsView,
    # Secretary
    SecretaryDoctorView,
    SecretaryAppointmentListView,
    SecretaryAppointmentStatusView,
    SecretaryPatientListView,
)

app_name = 'dashboard'

urlpatterns = [
    # ── Common ──
    path('me/', DashboardMeView.as_view(), name='me'),

    # ── Admin ──
    path('admin/users/', AdminUserListView.as_view(), name='admin-users'),
    path('admin/users/<uuid:pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/doctors/', AdminDoctorListView.as_view(), name='admin-doctors'),
    path('admin/doctors/<uuid:pk>/approve/', AdminDoctorApproveView.as_view(), name='admin-doctor-approve'),
    path('admin/appointments/', AdminAppointmentListView.as_view(), name='admin-appointments'),
    path('admin/reviews/', AdminReviewListView.as_view(), name='admin-reviews'),
    path('admin/reviews/<uuid:pk>/', AdminReviewDeleteView.as_view(), name='admin-review-delete'),
    path('admin/categories/', AdminCategoryListCreateView.as_view(), name='admin-categories'),
    path('admin/categories/<uuid:pk>/', AdminCategoryDetailView.as_view(), name='admin-category-detail'),
    path('admin/health-tips/', AdminHealthTipListCreateView.as_view(), name='admin-health-tips'),
    path('admin/health-tips/<int:pk>/', AdminHealthTipDetailView.as_view(), name='admin-health-tip-detail'),
    path('admin/analytics/', AdminAnalyticsView.as_view(), name='admin-analytics'),
    path('admin/roles/', AdminRoleListCreateView.as_view(), name='admin-roles'),
    path('admin/roles/<uuid:pk>/', AdminRoleDetailView.as_view(), name='admin-role-detail'),
    path('admin/roles/<uuid:pk>/assign/', AdminRoleAssignView.as_view(), name='admin-role-assign'),
    path('admin/roles/permissions/', AdminRolePermissionsView.as_view(), name='admin-role-permissions'),

    # ── Doctor ──
    path('doctor/profile/', DoctorProfileView.as_view(), name='doctor-profile'),
    path('doctor/appointments/', DoctorAppointmentListView.as_view(), name='doctor-appointments'),
    path('doctor/appointments/<uuid:pk>/status/', DoctorAppointmentStatusView.as_view(), name='doctor-appointment-status'),
    path('doctor/patients/', DoctorPatientListView.as_view(), name='doctor-patients'),
    path('doctor/services/', DoctorServiceListCreateView.as_view(), name='doctor-services'),
    path('doctor/services/<uuid:pk>/', DoctorServiceDetailView.as_view(), name='doctor-service-detail'),
    path('doctor/secretaries/', DoctorSecretaryListCreateView.as_view(), name='doctor-secretaries'),
    path('doctor/secretaries/<uuid:pk>/', DoctorSecretaryDetailView.as_view(), name='doctor-secretary-detail'),
    path('doctor/reviews/', DoctorReviewListView.as_view(), name='doctor-reviews'),
    path('doctor/analytics/', DoctorAnalyticsView.as_view(), name='doctor-analytics'),

    # ── Secretary ──
    path('secretary/doctor/', SecretaryDoctorView.as_view(), name='secretary-doctor'),
    path('secretary/appointments/', SecretaryAppointmentListView.as_view(), name='secretary-appointments'),
    path('secretary/appointments/<uuid:pk>/status/', SecretaryAppointmentStatusView.as_view(), name='secretary-appointment-status'),
    path('secretary/patients/', SecretaryPatientListView.as_view(), name='secretary-patients'),
]
