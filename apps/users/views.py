from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    DoctorRegistrationResponseSerializer,
    DoctorRegistrationSerializer,
    PatientRegistrationResponseSerializer,
    PatientRegistrationSerializer,
    UserResponseSerializer,
)


class PatientRegistrationView(APIView):
    """
    Patient Registration Endpoint

    Allows new patients to register an account. Upon successful registration:
    - User account is created with is_active=True (can login immediately)
    - User account has is_verified=False (email verification pending)
    - Patient profile is created with provided details
    """

    permission_classes = []  # Public endpoint, no authentication required

    @swagger_auto_schema(
        operation_id='register_patient',
        operation_description="""
        Register a new patient account.

        **Registration Process:**
        1. Validate all input fields
        2. Create user account with `is_active=True`, `is_verified=False`
        3. Create associated patient profile
        4. Return user data and success message

        **After Registration:**
        - Patient can login immediately
        - Email verification will be required for full access
        - Patient profile includes date of birth and phone number

        **Password Requirements:**
        - Minimum 8 characters
        - Cannot be too similar to personal information
        - Cannot be a commonly used password
        - Cannot be entirely numeric
        """,
        request_body=PatientRegistrationSerializer,
        responses={
            201: openapi.Response(
                description="Patient registered successfully",
                schema=PatientRegistrationResponseSerializer,
                examples={
                    'application/json': {
                        'message': 'Patient registered successfully. Please verify your email.',
                        'user': {
                            'id': 1,
                            'email': 'patient@example.com',
                            'first_name': 'John',
                            'last_name': 'Doe',
                            'full_name': 'John Doe',
                            'user_type': 'patient',
                            'is_active': True,
                            'is_verified': False,
                            'created_at': '2024-01-01T12:00:00Z'
                        }
                    }
                }
            ),
            400: openapi.Response(
                description="Validation error",
                examples={
                    'application/json': {
                        'email': ['A user with this email already exists.'],
                        'password': ['This password is too short.'],
                        'date_of_birth': ['Date of birth cannot be in the future.'],
                        'phone_number': ["Phone number must be entered in the format: '+999999999'."]
                    }
                }
            )
        },
        tags=['Registration']
    )
    def post(self, request):
        """Register a new patient."""
        serializer = PatientRegistrationSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            response_data = {
                'message': 'Patient registered successfully. Please verify your email.',
                'user': UserResponseSerializer(user).data
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DoctorRegistrationView(APIView):
    """
    Doctor Registration Endpoint

    Allows new doctors to register an account. Upon successful registration:
    - User account is created with is_active=False (requires admin approval)
    - User account has is_verified=False (email verification pending)
    - Doctor profile is created with provided details
    """

    permission_classes = []  # Public endpoint, no authentication required

    @swagger_auto_schema(
        operation_id='register_doctor',
        operation_description="""
        Register a new doctor account.

        **Registration Process:**
        1. Validate all input fields
        2. Create user account with `is_active=False`, `is_verified=False`
        3. Create associated doctor profile
        4. Return user data and approval notice

        **After Registration:**
        - Doctor account is inactive until admin approval
        - Admin will review and activate the account
        - Email verification will also be required

        **Password Requirements:**
        - Minimum 8 characters
        - Cannot be too similar to personal information
        - Cannot be a commonly used password
        - Cannot be entirely numeric
        """,
        request_body=DoctorRegistrationSerializer,
        responses={
            201: openapi.Response(
                description="Doctor registered successfully (pending approval)",
                schema=DoctorRegistrationResponseSerializer,
                examples={
                    'application/json': {
                        'message': 'Doctor registered successfully. Your account is pending admin approval.',
                        'user': {
                            'id': 2,
                            'email': 'doctor@example.com',
                            'first_name': 'Jane',
                            'last_name': 'Smith',
                            'full_name': 'Jane Smith',
                            'user_type': 'doctor',
                            'is_active': False,
                            'is_verified': False,
                            'created_at': '2024-01-01T12:00:00Z'
                        }
                    }
                }
            ),
            400: openapi.Response(
                description="Validation error",
                examples={
                    'application/json': {
                        'email': ['A user with this email already exists.'],
                        'password': ['This password is too short.'],
                        'phone_number': ["Phone number must be entered in the format: '+999999999'."]
                    }
                }
            )
        },
        tags=['Registration']
    )
    def post(self, request):
        """Register a new doctor."""
        serializer = DoctorRegistrationSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            response_data = {
                'message': 'Doctor registered successfully. Your account is pending admin approval.',
                'user': UserResponseSerializer(user).data
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
