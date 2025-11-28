from django.urls import path

from .views import (
    BackupCodesView,
    ChangePasswordView,
    DoctorRegistrationView,
    LoginView,
    LogoutView,
    PatientRegistrationView,
    RequestOTPView,
    TokenRefreshView,
    TwoFactorDisableView,
    TwoFactorLoginView,
    TwoFactorSetupView,
    TwoFactorStatusView,
    TwoFactorVerifySetupView,
    VerifyOTPView,
)

app_name = 'users'

urlpatterns = [
    # Registration endpoints
    path('register/patient/', PatientRegistrationView.as_view(), name='register-patient'),
    path('register/doctor/', DoctorRegistrationView.as_view(), name='register-doctor'),

    # Email verification endpoints
    path('verify/request-otp/', RequestOTPView.as_view(), name='request-otp'),
    path('verify/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),

    # Authentication endpoints
    path('login/', LoginView.as_view(), name='login'),
    path('login/2fa/', TwoFactorLoginView.as_view(), name='login-2fa'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('password/change/', ChangePasswordView.as_view(), name='change-password'),

    # Two-Factor Authentication endpoints
    path('2fa/setup/', TwoFactorSetupView.as_view(), name='2fa-setup'),
    path('2fa/verify-setup/', TwoFactorVerifySetupView.as_view(), name='2fa-verify-setup'),
    path('2fa/disable/', TwoFactorDisableView.as_view(), name='2fa-disable'),
    path('2fa/status/', TwoFactorStatusView.as_view(), name='2fa-status'),
    path('2fa/backup-codes/', BackupCodesView.as_view(), name='2fa-backup-codes'),
]
