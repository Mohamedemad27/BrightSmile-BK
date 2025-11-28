from django.contrib.auth import get_user_model
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import EmailVerificationOTP
from .serializers import (
    DoctorRegistrationResponseSerializer,
    DoctorRegistrationSerializer,
    OTPResponseSerializer,
    PatientRegistrationResponseSerializer,
    PatientRegistrationSerializer,
    RequestOTPSerializer,
    UserResponseSerializer,
    VerifyOTPSerializer,
)
from .tasks import send_verification_email_task

User = get_user_model()


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


class RequestOTPView(APIView):
    """
    Request OTP Endpoint

    Allows users to request a new email verification OTP.
    Users cannot request a new OTP until the previous one expires.
    """

    permission_classes = []  # Public endpoint

    @swagger_auto_schema(
        operation_id='request_otp',
        operation_description="""
        Request a new email verification OTP.

        **Process:**
        1. Validate email exists and user is not verified
        2. Check if there's an existing valid OTP (cooldown period)
        3. Generate new 6-digit OTP
        4. Send OTP via email (background task)
        5. Return success message

        **Cooldown:**
        - Users cannot request a new OTP until the previous one expires
        - Default expiry time is 5 minutes (configurable via OTP_EXPIRY_MINUTES)

        **Note:**
        - OTP is automatically sent on registration
        - Use this endpoint only if the original OTP expired
        """,
        request_body=RequestOTPSerializer,
        responses={
            200: openapi.Response(
                description="OTP sent successfully",
                schema=OTPResponseSerializer,
                examples={
                    'application/json': {
                        'message': 'Verification code sent to your email.',
                        'email': 'user@example.com'
                    }
                }
            ),
            400: openapi.Response(
                description="Validation error",
                examples={
                    'application/json': {
                        'email': ['No account found with this email address.']
                    }
                }
            ),
            429: openapi.Response(
                description="Rate limited - OTP already sent",
                examples={
                    'application/json': {
                        'email': ['An OTP was recently sent. Please wait 4m 30s before requesting a new one.']
                    }
                }
            )
        },
        tags=['Email Verification']
    )
    def post(self, request):
        """Request a new verification OTP."""
        serializer = RequestOTPSerializer(data=request.data)

        if serializer.is_valid():
            email = serializer.validated_data['email']
            user = User.objects.get(email__iexact=email)

            # Create OTP and send email
            otp_instance, otp_plain = EmailVerificationOTP.create_for_user(user)
            send_verification_email_task.delay(user.id, otp_plain)

            return Response({
                'message': 'Verification code sent to your email.',
                'email': user.email
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(APIView):
    """
    Verify OTP Endpoint

    Allows users to verify their email using the OTP code.
    """

    permission_classes = []  # Public endpoint

    @swagger_auto_schema(
        operation_id='verify_otp',
        operation_description="""
        Verify email using OTP code.

        **Process:**
        1. Validate email and OTP format
        2. Check if user exists and is not already verified
        3. Find valid (non-expired, non-used) OTP for user
        4. Verify OTP against stored hash
        5. Mark OTP as used and user as verified
        6. Return success message

        **OTP Validation:**
        - OTP must be exactly 6 digits
        - OTP must not be expired
        - OTP must not have been used before
        - OTP must match the stored hash
        """,
        request_body=VerifyOTPSerializer,
        responses={
            200: openapi.Response(
                description="Email verified successfully",
                schema=OTPResponseSerializer,
                examples={
                    'application/json': {
                        'message': 'Email verified successfully.',
                        'email': 'user@example.com'
                    }
                }
            ),
            400: openapi.Response(
                description="Validation error",
                examples={
                    'application/json': {
                        'otp': ['Invalid OTP code.']
                    }
                }
            )
        },
        tags=['Email Verification']
    )
    def post(self, request):
        """Verify email with OTP."""
        serializer = VerifyOTPSerializer(data=request.data)

        if serializer.is_valid():
            otp_instance = serializer.validated_data['otp_instance']
            user = serializer.validated_data['user']

            # Mark OTP as used
            otp_instance.is_used = True
            otp_instance.save(update_fields=['is_used'])

            # Mark user as verified
            user.is_verified = True
            user.save(update_fields=['is_verified'])

            return Response({
                'message': 'Email verified successfully.',
                'email': user.email
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
