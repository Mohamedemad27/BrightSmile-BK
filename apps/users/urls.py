from django.urls import path

from .views import DoctorRegistrationView, PatientRegistrationView

app_name = 'users'

urlpatterns = [
    # Registration endpoints
    path('register/patient/', PatientRegistrationView.as_view(), name='register-patient'),
    path('register/doctor/', DoctorRegistrationView.as_view(), name='register-doctor'),
]
