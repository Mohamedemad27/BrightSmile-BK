from django.contrib.auth import get_user_model
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import BackupCode, EmailVerificationOTP, TwoFactorAuth, TwoFactorToken
from .serializers import (
    BackupCodesResponseSerializer,
    ChangePasswordResponseSerializer,
    ChangePasswordSerializer,
    DoctorRegistrationResponseSerializer,
    DoctorRegistrationSerializer,
    LoginResponseSerializer,
    LoginSerializer,
    LogoutResponseSerializer,
    LogoutSerializer,
    OTPResponseSerializer,
    PatientRegistrationResponseSerializer,
    PatientRegistrationSerializer,
    RegenerateBackupCodesSerializer,
    RequestOTPSerializer,
    TokenRefreshResponseSerializer,
    TwoFactorDisableResponseSerializer,
    TwoFactorDisableSerializer,
    TwoFactorLoginResponseSerializer,
    TwoFactorLoginSerializer,
    TwoFactorRequiredResponseSerializer,
    TwoFactorSetupSerializer,
    TwoFactorStatusSerializer,
    TwoFactorVerifySetupResponseSerializer,
    TwoFactorVerifySetupSerializer,
    UserResponseSerializer,
    VerifyOTPResponseSerializer,
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
    Returns JWT tokens for auto-login after successful verification.
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
        6. Generate JWT tokens for auto-login
        7. Return tokens and user data

        **OTP Validation:**
        - OTP must be exactly 6 digits
        - OTP must not be expired
        - OTP must not have been used before
        - OTP must match the stored hash

        **Auto-Login:**
        - On successful verification, JWT tokens are returned
        - User can use these tokens immediately without logging in separately
        - Access token can be used in Authorization header: `Bearer <access_token>`
        """,
        request_body=VerifyOTPSerializer,
        responses={
            200: openapi.Response(
                description="Email verified successfully with auto-login tokens",
                schema=VerifyOTPResponseSerializer,
                examples={
                    'application/json': {
                        'message': 'Email verified successfully.',
                        'access': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                        'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                        'user': {
                            'id': 1,
                            'email': 'user@example.com',
                            'first_name': 'John',
                            'last_name': 'Doe',
                            'full_name': 'John Doe',
                            'user_type': 'patient',
                            'is_active': True,
                            'is_verified': True,
                            'is_2fa_enabled': False,
                            'created_at': '2024-01-01T12:00:00Z'
                        }
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
        """Verify email with OTP and return auto-login tokens."""
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

            # Generate JWT tokens for auto-login (only for active users)
            if user.is_active:
                refresh = RefreshToken.for_user(user)
                user.last_login = timezone.now()
                user.save(update_fields=['last_login'])

                return Response({
                    'message': 'Email verified successfully.',
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': UserResponseSerializer(user).data
                }, status=status.HTTP_200_OK)
            else:
                # For inactive users (e.g., doctors pending approval), just verify without tokens
                return Response({
                    'message': 'Email verified successfully. Your account is pending approval.',
                    'access': None,
                    'refresh': None,
                    'user': UserResponseSerializer(user).data
                }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    User Login Endpoint

    Authenticates users with email/password and returns JWT tokens.
    If 2FA is enabled, returns a flag indicating 2FA verification is required.
    """

    permission_classes = []  # Public endpoint

    @swagger_auto_schema(
        operation_id='login',
        operation_description="""
        Authenticate user and obtain JWT tokens.

        **Process:**
        1. Validate email and password
        2. Check user exists and password is correct
        3. Check user account is active
        4. If 2FA is enabled, return requires_2fa flag (use /login/2fa/ endpoint)
        5. If 2FA is not enabled, generate access and refresh tokens
        6. Update last_login timestamp
        7. Return tokens and user data

        **Two-Factor Authentication:**
        - If user has 2FA enabled, response will include `requires_2fa: true`
        - User must then call `/api/users/login/2fa/` with email and TOTP code
        - Backup codes can also be used for 2FA verification

        **Token Usage:**
        - Include access token in Authorization header: `Bearer <access_token>`
        - Access token expires in 60 minutes (configurable)
        - Use refresh token to obtain new access token

        **Account Status:**
        - Only active users (is_active=True) can login
        - Doctors must be approved by admin before login
        """,
        request_body=LoginSerializer,
        responses={
            200: openapi.Response(
                description="Login successful (or 2FA required)",
                schema=LoginResponseSerializer,
                examples={
                    'application/json': {
                        'access': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                        'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                        'user': {
                            'id': 1,
                            'email': 'user@example.com',
                            'first_name': 'John',
                            'last_name': 'Doe',
                            'full_name': 'John Doe',
                            'user_type': 'patient',
                            'is_active': True,
                            'is_verified': True,
                            'is_2fa_enabled': False,
                            'created_at': '2024-01-01T12:00:00Z'
                        }
                    }
                }
            ),
            202: openapi.Response(
                description="2FA verification required",
                schema=TwoFactorRequiredResponseSerializer,
                examples={
                    'application/json': {
                        'requires_2fa': True,
                        'temp_token': 'a1b2c3d4e5f6...',
                        'message': 'Two-factor authentication required. Please provide your TOTP code.'
                    }
                }
            ),
            400: openapi.Response(
                description="Invalid credentials or inactive account",
                examples={
                    'application/json': {
                        'detail': 'Invalid email or password.'
                    }
                }
            )
        },
        tags=['Authentication']
    )
    def post(self, request):
        """Login and obtain JWT tokens."""
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data['user']

            # Check if 2FA is enabled
            if user.is_2fa_enabled:
                # Generate temporary token for 2FA verification
                temp_token = TwoFactorToken.create_for_user(user)
                return Response({
                    'requires_2fa': True,
                    'temp_token': temp_token.token,
                    'message': 'Two-factor authentication required. Please provide your TOTP code.'
                }, status=status.HTTP_202_ACCEPTED)

            # Generate tokens
            refresh = RefreshToken.for_user(user)

            # Update last_login
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserResponseSerializer(user).data
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TokenRefreshView(APIView):
    """
    Token Refresh Endpoint

    Obtain a new access token using a refresh token.
    """

    permission_classes = []  # Public endpoint

    @swagger_auto_schema(
        operation_id='token_refresh',
        operation_description="""
        Obtain new access token using refresh token.

        **Process:**
        1. Validate refresh token
        2. Generate new access token
        3. If token rotation is enabled, generate new refresh token and blacklist old one
        4. Return new tokens

        **Token Rotation:**
        - Enabled by default for security
        - Old refresh token is blacklisted after use
        - New refresh token is provided with each refresh

        **Refresh Token Lifetime:**
        - Default: 7 days (configurable via JWT_REFRESH_TOKEN_LIFETIME_DAYS)
        """,
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['refresh'],
            properties={
                'refresh': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Refresh token'
                ),
            }
        ),
        responses={
            200: openapi.Response(
                description="Token refreshed successfully",
                schema=TokenRefreshResponseSerializer,
                examples={
                    'application/json': {
                        'access': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                        'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
                    }
                }
            ),
            401: openapi.Response(
                description="Invalid or expired refresh token",
                examples={
                    'application/json': {
                        'detail': 'Token is invalid or expired',
                        'code': 'token_not_valid'
                    }
                }
            )
        },
        tags=['Authentication']
    )
    def post(self, request):
        """Refresh access token."""
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response({
                'refresh': ['This field is required.']
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            refresh = RefreshToken(refresh_token)

            response_data = {
                'access': str(refresh.access_token),
            }

            # If rotation is enabled, include new refresh token
            # The old token is automatically blacklisted by simplejwt
            response_data['refresh'] = str(refresh)

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'detail': 'Token is invalid or expired',
                'code': 'token_not_valid'
            }, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    """
    User Logout Endpoint

    Blacklists the refresh token to invalidate the session.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='logout',
        operation_description="""
        Logout user by blacklisting the refresh token.

        **Process:**
        1. Validate refresh token
        2. Add refresh token to blacklist
        3. Return success message

        **Important:**
        - Access token will remain valid until it expires
        - Client should discard both tokens after logout
        - Requires authentication (Bearer token in header)

        **Security:**
        - Blacklisted tokens cannot be used for refresh
        - Recommended to logout from all devices by blacklisting all tokens
        """,
        request_body=LogoutSerializer,
        responses={
            200: openapi.Response(
                description="Logout successful",
                schema=LogoutResponseSerializer,
                examples={
                    'application/json': {
                        'message': 'Successfully logged out.'
                    }
                }
            ),
            400: openapi.Response(
                description="Invalid refresh token",
                examples={
                    'application/json': {
                        'refresh': ['Invalid or expired refresh token.']
                    }
                }
            ),
            401: openapi.Response(
                description="Authentication required",
                examples={
                    'application/json': {
                        'detail': 'Authentication credentials were not provided.'
                    }
                }
            )
        },
        tags=['Authentication'],
        security=[{'Bearer': []}]
    )
    def post(self, request):
        """Logout and blacklist refresh token."""
        serializer = LogoutSerializer(data=request.data)

        if serializer.is_valid():
            try:
                refresh_token = serializer.validated_data['refresh']
                token = RefreshToken(refresh_token)
                token.blacklist()

                return Response({
                    'message': 'Successfully logged out.'
                }, status=status.HTTP_200_OK)

            except Exception:
                return Response({
                    'refresh': ['Invalid or expired refresh token.']
                }, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """
    Change Password Endpoint

    Allows authenticated users to change their password.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='change_password',
        operation_description="""
        Change the authenticated user's password.

        **Process:**
        1. Verify current password is correct
        2. Validate new password meets security requirements
        3. Validate new password confirmation matches
        4. Update user's password
        5. Return success message

        **Password Requirements:**
        - Minimum 8 characters
        - Cannot be too similar to personal information
        - Cannot be a commonly used password
        - Cannot be entirely numeric
        - Must be different from current password

        **Note:**
        - Requires authentication (Bearer token in header)
        - After changing password, existing tokens remain valid
        - User should logout and login again for best security
        """,
        request_body=ChangePasswordSerializer,
        responses={
            200: openapi.Response(
                description="Password changed successfully",
                schema=ChangePasswordResponseSerializer,
                examples={
                    'application/json': {
                        'message': 'Password changed successfully.'
                    }
                }
            ),
            400: openapi.Response(
                description="Validation error",
                examples={
                    'application/json': {
                        'current_password': ['Current password is incorrect.'],
                        'new_password': ['This password is too short.'],
                        'new_password_confirm': ['New passwords do not match.']
                    }
                }
            ),
            401: openapi.Response(
                description="Authentication required",
                examples={
                    'application/json': {
                        'detail': 'Authentication credentials were not provided.'
                    }
                }
            )
        },
        tags=['Authentication'],
        security=[{'Bearer': []}]
    )
    def post(self, request):
        """Change user password."""
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save(update_fields=['password'])

            return Response({
                'message': 'Password changed successfully.'
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# Two-Factor Authentication Views
# ============================================================================

class TwoFactorSetupView(APIView):
    """
    2FA Setup Endpoint

    Initiates 2FA setup by generating a TOTP secret and QR code.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='2fa_setup',
        operation_description="""
        Initiate Two-Factor Authentication setup.

        **Process:**
        1. Generate a new TOTP secret for the user
        2. Create QR code for authenticator app scanning
        3. Return secret, QR code, and provisioning URI
        4. User must verify setup with /2fa/verify-setup/ endpoint

        **Setup Flow:**
        1. Call this endpoint to get secret and QR code
        2. Scan QR code with authenticator app (Google Authenticator, Authy, etc.)
        3. Enter the 6-digit code from the app at /2fa/verify-setup/
        4. Save the backup codes securely

        **Note:**
        - If user already has 2FA enabled, they must disable it first
        - The secret is stored encrypted but marked as unverified
        - 2FA is only active after verification
        """,
        responses={
            200: openapi.Response(
                description="2FA setup initiated",
                schema=TwoFactorSetupSerializer,
                examples={
                    'application/json': {
                        'secret': 'JBSWY3DPEHPK3PXP',
                        'qr_code': 'iVBORw0KGgoAAAANSUhEUgAA...',
                        'provisioning_uri': 'otpauth://totp/Bright%20Smile:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=Bright%20Smile'
                    }
                }
            ),
            400: openapi.Response(
                description="2FA already enabled",
                examples={
                    'application/json': {
                        'detail': '2FA is already enabled. Disable it first to set up again.'
                    }
                }
            ),
            401: openapi.Response(
                description="Authentication required"
            )
        },
        tags=['Two-Factor Authentication'],
        security=[{'Bearer': []}]
    )
    def post(self, request):
        """Initiate 2FA setup."""
        user = request.user

        # Check if 2FA is already enabled
        if user.is_2fa_enabled:
            return Response({
                'detail': '2FA is already enabled. Disable it first to set up again.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create or update 2FA configuration
        two_factor_auth = TwoFactorAuth.create_for_user(user)

        return Response({
            'secret': two_factor_auth.secret,
            'qr_code': two_factor_auth.generate_qr_code_base64(),
            'provisioning_uri': two_factor_auth.get_provisioning_uri()
        }, status=status.HTTP_200_OK)


class TwoFactorVerifySetupView(APIView):
    """
    2FA Verify Setup Endpoint

    Verifies 2FA setup and enables 2FA for the user.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='2fa_verify_setup',
        operation_description="""
        Verify and complete Two-Factor Authentication setup.

        **Process:**
        1. Validate the TOTP code from authenticator app
        2. Mark 2FA as verified and enabled
        3. Generate backup codes for recovery
        4. Return backup codes (save these securely!)

        **Important:**
        - Backup codes are shown only once
        - Store backup codes in a safe place
        - Each backup code can only be used once
        - You will receive 10 backup codes
        """,
        request_body=TwoFactorVerifySetupSerializer,
        responses={
            200: openapi.Response(
                description="2FA enabled successfully",
                schema=TwoFactorVerifySetupResponseSerializer,
                examples={
                    'application/json': {
                        'message': '2FA has been enabled successfully.',
                        'backup_codes': [
                            'ABCD1234', 'EFGH5678', 'IJKL9012',
                            'MNOP3456', 'QRST7890', 'UVWX1234',
                            'YZAB5678', 'CDEF9012', 'GHIJ3456',
                            'KLMN7890'
                        ]
                    }
                }
            ),
            400: openapi.Response(
                description="Invalid code or setup not initiated",
                examples={
                    'application/json': {
                        'code': ['Invalid code. Please try again.']
                    }
                }
            ),
            401: openapi.Response(
                description="Authentication required"
            )
        },
        tags=['Two-Factor Authentication'],
        security=[{'Bearer': []}]
    )
    def post(self, request):
        """Verify 2FA setup and enable 2FA."""
        serializer = TwoFactorVerifySetupSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            user = request.user
            two_factor_auth = serializer.validated_data['two_factor_auth']

            # Mark 2FA as verified
            two_factor_auth.is_verified = True
            two_factor_auth.verified_at = timezone.now()
            two_factor_auth.save(update_fields=['is_verified', 'verified_at'])

            # Enable 2FA on user
            user.is_2fa_enabled = True
            user.save(update_fields=['is_2fa_enabled'])

            # Generate backup codes
            backup_codes = BackupCode.generate_codes_for_user(user)

            return Response({
                'message': '2FA has been enabled successfully.',
                'backup_codes': backup_codes
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TwoFactorDisableView(APIView):
    """
    2FA Disable Endpoint

    Disables 2FA for the user (requires password and TOTP code).
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='2fa_disable',
        operation_description="""
        Disable Two-Factor Authentication.

        **Process:**
        1. Verify password
        2. Verify TOTP code
        3. Disable 2FA and remove configuration
        4. Delete all backup codes

        **Security:**
        - Requires both password and valid TOTP code
        - This action cannot be undone
        - User will need to set up 2FA again if desired
        """,
        request_body=TwoFactorDisableSerializer,
        responses={
            200: openapi.Response(
                description="2FA disabled successfully",
                schema=TwoFactorDisableResponseSerializer,
                examples={
                    'application/json': {
                        'message': '2FA has been disabled successfully.'
                    }
                }
            ),
            400: openapi.Response(
                description="Invalid password or code",
                examples={
                    'application/json': {
                        'password': ['Incorrect password.'],
                        'code': ['Invalid code. Please try again.']
                    }
                }
            ),
            401: openapi.Response(
                description="Authentication required"
            )
        },
        tags=['Two-Factor Authentication'],
        security=[{'Bearer': []}]
    )
    def post(self, request):
        """Disable 2FA."""
        serializer = TwoFactorDisableSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            user = request.user
            two_factor_auth = serializer.validated_data['two_factor_auth']

            # Delete 2FA configuration
            two_factor_auth.delete()

            # Delete backup codes
            BackupCode.objects.filter(user=user).delete()

            # Disable 2FA on user
            user.is_2fa_enabled = False
            user.save(update_fields=['is_2fa_enabled'])

            return Response({
                'message': '2FA has been disabled successfully.'
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TwoFactorStatusView(APIView):
    """
    2FA Status Endpoint

    Returns the current 2FA status for the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='2fa_status',
        operation_description="""
        Get the current Two-Factor Authentication status.

        Returns:
        - Whether 2FA is enabled
        - Whether setup is pending verification
        - Number of remaining backup codes
        """,
        responses={
            200: openapi.Response(
                description="2FA status",
                schema=TwoFactorStatusSerializer,
                examples={
                    'application/json': {
                        'is_enabled': True,
                        'is_setup_pending': False,
                        'backup_codes_remaining': 8
                    }
                }
            ),
            401: openapi.Response(
                description="Authentication required"
            )
        },
        tags=['Two-Factor Authentication'],
        security=[{'Bearer': []}]
    )
    def get(self, request):
        """Get 2FA status."""
        user = request.user

        is_setup_pending = False
        try:
            two_factor_auth = user.two_factor_auth
            is_setup_pending = not two_factor_auth.is_verified
        except TwoFactorAuth.DoesNotExist:
            pass

        return Response({
            'is_enabled': user.is_2fa_enabled,
            'is_setup_pending': is_setup_pending,
            'backup_codes_remaining': BackupCode.get_unused_count(user)
        }, status=status.HTTP_200_OK)


class BackupCodesView(APIView):
    """
    Backup Codes Endpoint

    Returns unused backup codes count or regenerates backup codes.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='get_backup_codes',
        operation_description="""
        Get backup codes information.

        **Note:**
        - For security, this endpoint only returns the count of unused codes
        - To see the actual codes, regenerate them using POST
        - Each code can only be used once
        """,
        responses={
            200: openapi.Response(
                description="Backup codes info",
                schema=BackupCodesResponseSerializer,
                examples={
                    'application/json': {
                        'backup_codes': [],
                        'unused_count': 8
                    }
                }
            ),
            400: openapi.Response(
                description="2FA not enabled",
                examples={
                    'application/json': {
                        'detail': '2FA is not enabled for this account.'
                    }
                }
            ),
            401: openapi.Response(
                description="Authentication required"
            )
        },
        tags=['Two-Factor Authentication'],
        security=[{'Bearer': []}]
    )
    def get(self, request):
        """Get backup codes count."""
        user = request.user

        if not user.is_2fa_enabled:
            return Response({
                'detail': '2FA is not enabled for this account.'
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'backup_codes': [],  # Don't expose codes for security
            'unused_count': BackupCode.get_unused_count(user)
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_id='regenerate_backup_codes',
        operation_description="""
        Regenerate backup codes.

        **Process:**
        1. Verify password
        2. Delete all existing backup codes
        3. Generate 10 new backup codes
        4. Return new codes (save these securely!)

        **Important:**
        - This invalidates all previous backup codes
        - New codes are shown only once
        - Store codes in a safe place
        """,
        request_body=RegenerateBackupCodesSerializer,
        responses={
            200: openapi.Response(
                description="Backup codes regenerated",
                schema=BackupCodesResponseSerializer,
                examples={
                    'application/json': {
                        'backup_codes': [
                            'ABCD1234', 'EFGH5678', 'IJKL9012',
                            'MNOP3456', 'QRST7890', 'UVWX1234',
                            'YZAB5678', 'CDEF9012', 'GHIJ3456',
                            'KLMN7890'
                        ],
                        'unused_count': 10
                    }
                }
            ),
            400: openapi.Response(
                description="Invalid password or 2FA not enabled",
                examples={
                    'application/json': {
                        'password': ['Incorrect password.']
                    }
                }
            ),
            401: openapi.Response(
                description="Authentication required"
            )
        },
        tags=['Two-Factor Authentication'],
        security=[{'Bearer': []}]
    )
    def post(self, request):
        """Regenerate backup codes."""
        serializer = RegenerateBackupCodesSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            user = request.user

            # Generate new backup codes
            backup_codes = BackupCode.generate_codes_for_user(user)

            return Response({
                'backup_codes': backup_codes,
                'unused_count': len(backup_codes)
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TwoFactorLoginView(APIView):
    """
    2FA Login Verification Endpoint

    Completes login for users with 2FA enabled using temporary token.
    """

    permission_classes = []  # Public endpoint

    @swagger_auto_schema(
        operation_id='2fa_login',
        operation_description="""
        Complete login with Two-Factor Authentication.

        **Process:**
        1. User first calls /login/ with email and password
        2. If 2FA is enabled, /login/ returns `requires_2fa: true` and a `temp_token`
        3. User calls this endpoint with temp_token and TOTP code
        4. On success, returns JWT tokens

        **Temporary Token:**
        - Valid for 5 minutes only
        - Can only be used once
        - Must be obtained from /login/ endpoint

        **Code Types:**
        - 6-digit TOTP code from authenticator app
        - 8-character backup code (for recovery)

        **Note:**
        - Backup codes can only be used once
        - After using a backup code, it's marked as used
        """,
        request_body=TwoFactorLoginSerializer,
        responses={
            200: openapi.Response(
                description="Login successful",
                schema=TwoFactorLoginResponseSerializer,
                examples={
                    'application/json': {
                        'access': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                        'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                        'user': {
                            'id': 1,
                            'email': 'user@example.com',
                            'first_name': 'John',
                            'last_name': 'Doe',
                            'full_name': 'John Doe',
                            'user_type': 'patient',
                            'is_active': True,
                            'is_verified': True,
                            'is_2fa_enabled': True,
                            'created_at': '2024-01-01T12:00:00Z'
                        }
                    }
                }
            ),
            400: openapi.Response(
                description="Invalid token or code",
                examples={
                    'application/json': {
                        'temp_token': ['Invalid or expired token. Please login again.'],
                        'code': ['Invalid code. Please try again.']
                    }
                }
            )
        },
        tags=['Authentication']
    )
    def post(self, request):
        """Complete 2FA login."""
        serializer = TwoFactorLoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data['user']
            temp_token_str = serializer.validated_data['temp_token_str']

            # Invalidate the temp token
            TwoFactorToken.get_and_invalidate(temp_token_str)

            # Generate tokens
            refresh = RefreshToken.for_user(user)

            # Update last_login
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserResponseSerializer(user).data
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
