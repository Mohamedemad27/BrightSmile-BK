from django.urls import path

from .views import (
    DoctorRegistrationView,
    PatientRegistrationView,
    RequestOTPView,
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
]
