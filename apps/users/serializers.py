from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from utils.validators import phone_number_validator, validate_date_of_birth
from .models import BackupCode, Doctor, EmailVerificationOTP, Patient, TwoFactorAuth, TwoFactorToken

User = get_user_model()


class UserResponseSerializer(serializers.ModelSerializer):
    """Serializer for user data in registration responses."""

    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'user_type',
            'is_active',
            'is_verified',
            'is_2fa_enabled',
            'created_at',
        ]
        read_only_fields = fields


class PatientRegistrationSerializer(serializers.Serializer):
    """
    Serializer for patient registration.

    Creates a User with is_active=True, is_verified=False and an associated Patient profile.
    """

    # User fields
    email = serializers.EmailField(
        help_text="Patient's email address (used for login)"
    )
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="Password (min 8 characters, must include letters and numbers)"
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="Confirm password"
    )
    first_name = serializers.CharField(
        max_length=150,
        help_text="Patient's first name"
    )
    last_name = serializers.CharField(
        max_length=150,
        help_text="Patient's last name"
    )

    # Patient fields
    date_of_birth = serializers.DateField(
        help_text="Date of birth (YYYY-MM-DD format)"
    )
    phone_number = serializers.CharField(
        max_length=20,
        help_text="Phone number in international format (e.g., +1234567890)"
    )

    def validate_email(self, value):
        """Check that email is unique."""
        email = value.lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate_password(self, value):
        """Validate password using Django's password validators."""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate_date_of_birth(self, value):
        """Validate date of birth."""
        try:
            validate_date_of_birth(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(str(e.message))
        return value

    def validate_phone_number(self, value):
        """Validate phone number format."""
        try:
            phone_number_validator(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(str(e.message))
        return value

    def validate(self, attrs):
        """Validate that passwords match."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': "Passwords do not match."
            })
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create user and patient profile."""
        # Remove password_confirm from data
        validated_data.pop('password_confirm')

        # Extract patient-specific fields
        date_of_birth = validated_data.pop('date_of_birth')
        phone_number = validated_data.pop('phone_number')

        # Create user
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            user_type='patient',
            is_active=True,
            is_verified=False,
        )

        # Create patient profile
        Patient.objects.create(
            user=user,
            date_of_birth=date_of_birth,
            phone_number=phone_number,
        )

        return user


class DoctorRegistrationSerializer(serializers.Serializer):
    """
    Serializer for doctor registration.

    Creates a User with is_active=False, is_verified=False (requires admin approval)
    and an associated Doctor profile.
    """

    # User fields
    email = serializers.EmailField(
        help_text="Doctor's email address (used for login)"
    )
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="Password (min 8 characters, must include letters and numbers)"
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="Confirm password"
    )
    first_name = serializers.CharField(
        max_length=150,
        help_text="Doctor's first name"
    )
    last_name = serializers.CharField(
        max_length=150,
        help_text="Doctor's last name"
    )

    # Doctor fields
    phone_number = serializers.CharField(
        max_length=20,
        help_text="Phone number in international format (e.g., +1234567890)"
    )

    def validate_email(self, value):
        """Check that email is unique."""
        email = value.lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate_password(self, value):
        """Validate password using Django's password validators."""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate_phone_number(self, value):
        """Validate phone number format."""
        try:
            phone_number_validator(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(str(e.message))
        return value

    def validate(self, attrs):
        """Validate that passwords match."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': "Passwords do not match."
            })
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create user and doctor profile."""
        # Remove password_confirm from data
        validated_data.pop('password_confirm')

        # Extract doctor-specific fields
        phone_number = validated_data.pop('phone_number')

        # Create user (inactive until admin approval)
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            user_type='doctor',
            is_active=False,
            is_verified=False,
        )

        # Create doctor profile
        Doctor.objects.create(
            user=user,
            phone_number=phone_number,
        )

        return user


class PatientRegistrationResponseSerializer(serializers.Serializer):
    """Serializer for patient registration response."""

    message = serializers.CharField(help_text="Success message")
    user = UserResponseSerializer(help_text="Created user data")


class DoctorRegistrationResponseSerializer(serializers.Serializer):
    """Serializer for doctor registration response."""

    message = serializers.CharField(help_text="Success message with approval notice")
    user = UserResponseSerializer(help_text="Created user data")


class RequestOTPSerializer(serializers.Serializer):
    """Serializer for requesting a new OTP."""

    email = serializers.EmailField(
        help_text="Email address to send OTP to"
    )

    def validate_email(self, value):
        """Validate email exists and user is not already verified."""
        email = value.lower()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("No account found with this email address.")

        if user.is_verified:
            raise serializers.ValidationError("This email is already verified.")

        # Check for existing valid OTP (cooldown)
        existing_otp = EmailVerificationOTP.objects.filter(
            user=user,
            is_used=False,
            expires_at__gt=timezone.now()
        ).first()

        if existing_otp:
            remaining_seconds = (existing_otp.expires_at - timezone.now()).total_seconds()
            remaining_minutes = int(remaining_seconds // 60)
            remaining_secs = int(remaining_seconds % 60)
            raise serializers.ValidationError(
                f"An OTP was recently sent. Please wait {remaining_minutes}m {remaining_secs}s before requesting a new one."
            )

        return email


class VerifyOTPSerializer(serializers.Serializer):
    """Serializer for verifying an OTP."""

    email = serializers.EmailField(
        help_text="Email address to verify"
    )
    otp = serializers.CharField(
        min_length=6,
        max_length=6,
        help_text="6-digit OTP code"
    )

    def validate_email(self, value):
        """Validate email exists."""
        email = value.lower()
        try:
            User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("No account found with this email address.")
        return email

    def validate_otp(self, value):
        """Validate OTP is numeric."""
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits.")
        return value

    def validate(self, attrs):
        """Validate OTP against stored hash."""
        email = attrs['email']
        otp = attrs['otp']

        user = User.objects.get(email__iexact=email)

        if user.is_verified:
            raise serializers.ValidationError({
                'email': "This email is already verified."
            })

        # Find valid OTP for user
        otp_instance = EmailVerificationOTP.objects.filter(
            user=user,
            is_used=False,
            expires_at__gt=timezone.now()
        ).order_by('-created_at').first()

        if not otp_instance:
            raise serializers.ValidationError({
                'otp': "No valid OTP found. Please request a new one."
            })

        if not otp_instance.verify(otp):
            raise serializers.ValidationError({
                'otp': "Invalid OTP code."
            })

        # Store verified OTP instance for use in view
        attrs['otp_instance'] = otp_instance
        attrs['user'] = user

        return attrs


class OTPResponseSerializer(serializers.Serializer):
    """Serializer for OTP request/verify responses."""

    message = serializers.CharField(help_text="Response message")
    email = serializers.EmailField(help_text="Email address")


class VerifyOTPResponseSerializer(serializers.Serializer):
    """Serializer for successful OTP verification response with auto-login tokens."""

    message = serializers.CharField(help_text="Success message")
    access = serializers.CharField(help_text="JWT access token for auto-login")
    refresh = serializers.CharField(help_text="JWT refresh token")
    user = UserResponseSerializer(help_text="Verified user data")


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""

    email = serializers.EmailField(
        help_text="User's email address"
    )
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="User's password"
    )

    def validate(self, attrs):
        """Validate credentials and check user status."""
        email = attrs.get('email', '').lower()
        password = attrs.get('password', '')

        # Check if user exists
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({
                'detail': "Invalid email or password."
            })

        # Check password
        if not user.check_password(password):
            raise serializers.ValidationError({
                'detail': "Invalid email or password."
            })

        # Check if user is active
        if not user.is_active:
            raise serializers.ValidationError({
                'detail': "Your account is not active. Please contact support."
            })

        attrs['user'] = user
        return attrs


class LoginResponseSerializer(serializers.Serializer):
    """Serializer for login response."""

    access = serializers.CharField(help_text="JWT access token")
    refresh = serializers.CharField(help_text="JWT refresh token")
    user = UserResponseSerializer(help_text="User data")


class TokenRefreshResponseSerializer(serializers.Serializer):
    """Serializer for token refresh response."""

    access = serializers.CharField(help_text="New JWT access token")
    refresh = serializers.CharField(help_text="New JWT refresh token (if rotation enabled)")


class LogoutSerializer(serializers.Serializer):
    """Serializer for logout request."""

    refresh = serializers.CharField(
        help_text="Refresh token to blacklist"
    )

    def validate_refresh(self, value):
        """Validate refresh token."""
        try:
            RefreshToken(value)
        except Exception:
            raise serializers.ValidationError("Invalid or expired refresh token.")
        return value


class LogoutResponseSerializer(serializers.Serializer):
    """Serializer for logout response."""

    message = serializers.CharField(help_text="Success message")


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing user password."""

    current_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="Current password"
    )
    new_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="New password (min 8 characters)"
    )
    new_password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="Confirm new password"
    )

    def validate_current_password(self, value):
        """Validate current password is correct."""
        user = self.context.get('request').user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        """Validate new password using Django's password validators."""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, attrs):
        """Validate new passwords match."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': "New passwords do not match."
            })

        # Check new password is different from current
        if attrs['current_password'] == attrs['new_password']:
            raise serializers.ValidationError({
                'new_password': "New password must be different from current password."
            })

        return attrs


class ChangePasswordResponseSerializer(serializers.Serializer):
    """Serializer for change password response."""

    message = serializers.CharField(help_text="Success message")


# ============================================================================
# Two-Factor Authentication Serializers
# ============================================================================

class TwoFactorSetupSerializer(serializers.Serializer):
    """Serializer for 2FA setup response."""

    secret = serializers.CharField(help_text="TOTP secret key for manual entry")
    qr_code = serializers.CharField(help_text="Base64 encoded QR code image")
    provisioning_uri = serializers.CharField(help_text="otpauth:// URI for authenticator apps")


class TwoFactorVerifySetupSerializer(serializers.Serializer):
    """Serializer for verifying 2FA setup."""

    code = serializers.CharField(
        min_length=6,
        max_length=6,
        help_text="6-digit code from authenticator app"
    )

    def validate_code(self, value):
        """Validate code is numeric."""
        if not value.isdigit():
            raise serializers.ValidationError("Code must contain only digits.")
        return value

    def validate(self, attrs):
        """Validate TOTP code against stored secret."""
        user = self.context.get('request').user
        code = attrs['code']

        # Check if user has 2FA setup pending
        try:
            two_factor_auth = user.two_factor_auth
        except TwoFactorAuth.DoesNotExist:
            raise serializers.ValidationError({
                'detail': "2FA setup not initiated. Please start setup first."
            })

        if two_factor_auth.is_verified:
            raise serializers.ValidationError({
                'detail': "2FA is already enabled for this account."
            })

        # Verify the code
        if not two_factor_auth.verify_code(code):
            raise serializers.ValidationError({
                'code': "Invalid code. Please try again."
            })

        attrs['two_factor_auth'] = two_factor_auth
        return attrs


class TwoFactorVerifySetupResponseSerializer(serializers.Serializer):
    """Serializer for 2FA verify setup response."""

    message = serializers.CharField(help_text="Success message")
    backup_codes = serializers.ListField(
        child=serializers.CharField(),
        help_text="List of backup codes (save these securely!)"
    )


class TwoFactorDisableSerializer(serializers.Serializer):
    """Serializer for disabling 2FA."""

    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="Current account password"
    )
    code = serializers.CharField(
        min_length=6,
        max_length=6,
        help_text="6-digit code from authenticator app"
    )

    def validate_password(self, value):
        """Validate current password."""
        user = self.context.get('request').user
        if not user.check_password(value):
            raise serializers.ValidationError("Incorrect password.")
        return value

    def validate_code(self, value):
        """Validate code is numeric."""
        if not value.isdigit():
            raise serializers.ValidationError("Code must contain only digits.")
        return value

    def validate(self, attrs):
        """Validate user has 2FA enabled and code is valid."""
        user = self.context.get('request').user
        code = attrs['code']

        # Check if 2FA is enabled
        if not user.is_2fa_enabled:
            raise serializers.ValidationError({
                'detail': "2FA is not enabled for this account."
            })

        try:
            two_factor_auth = user.two_factor_auth
        except TwoFactorAuth.DoesNotExist:
            raise serializers.ValidationError({
                'detail': "2FA configuration not found."
            })

        # Verify the code
        if not two_factor_auth.verify_code(code):
            raise serializers.ValidationError({
                'code': "Invalid code. Please try again."
            })

        attrs['two_factor_auth'] = two_factor_auth
        return attrs


class TwoFactorDisableResponseSerializer(serializers.Serializer):
    """Serializer for 2FA disable response."""

    message = serializers.CharField(help_text="Success message")


class BackupCodesResponseSerializer(serializers.Serializer):
    """Serializer for backup codes response."""

    backup_codes = serializers.ListField(
        child=serializers.CharField(),
        help_text="List of unused backup codes"
    )
    unused_count = serializers.IntegerField(help_text="Number of unused backup codes")


class RegenerateBackupCodesSerializer(serializers.Serializer):
    """Serializer for regenerating backup codes."""

    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="Current account password"
    )

    def validate_password(self, value):
        """Validate current password."""
        user = self.context.get('request').user
        if not user.check_password(value):
            raise serializers.ValidationError("Incorrect password.")
        return value

    def validate(self, attrs):
        """Validate user has 2FA enabled."""
        user = self.context.get('request').user

        if not user.is_2fa_enabled:
            raise serializers.ValidationError({
                'detail': "2FA must be enabled to regenerate backup codes."
            })

        return attrs


class TwoFactorLoginSerializer(serializers.Serializer):
    """Serializer for 2FA login verification."""

    temp_token = serializers.CharField(
        help_text="Temporary token from login response"
    )
    code = serializers.CharField(
        min_length=6,
        max_length=8,  # Allow 8 chars for backup codes
        help_text="6-digit TOTP code or 8-character backup code"
    )

    def validate(self, attrs):
        """Validate temp token and 2FA code."""
        temp_token = attrs.get('temp_token', '').strip()
        code = attrs.get('code', '').strip()

        # Verify temp token and get user
        user = TwoFactorToken.verify_token(temp_token)
        if not user:
            raise serializers.ValidationError({
                'temp_token': "Invalid or expired token. Please login again."
            })

        # Verify user has 2FA enabled
        if not user.is_2fa_enabled:
            raise serializers.ValidationError({
                'detail': "2FA is not enabled for this account."
            })

        # Check if user is active
        if not user.is_active:
            raise serializers.ValidationError({
                'detail': "Your account is not active."
            })

        # Try TOTP code first (6 digits)
        verified = False
        if len(code) == 6 and code.isdigit():
            try:
                two_factor_auth = user.two_factor_auth
                if two_factor_auth.verify_code(code):
                    verified = True
            except TwoFactorAuth.DoesNotExist:
                pass

        # Try backup code (8 characters)
        if not verified and len(code) == 8:
            if BackupCode.verify_code_for_user(user, code):
                verified = True

        if not verified:
            raise serializers.ValidationError({
                'code': "Invalid code. Please try again."
            })

        # Store temp_token for invalidation in view
        attrs['temp_token_str'] = temp_token
        attrs['user'] = user
        return attrs


class TwoFactorLoginResponseSerializer(serializers.Serializer):
    """Serializer for 2FA login response."""

    access = serializers.CharField(help_text="JWT access token")
    refresh = serializers.CharField(help_text="JWT refresh token")
    user = UserResponseSerializer(help_text="User data")


class TwoFactorRequiredResponseSerializer(serializers.Serializer):
    """Serializer for login response when 2FA is required."""

    requires_2fa = serializers.BooleanField(help_text="Indicates 2FA verification is required")
    temp_token = serializers.CharField(help_text="Temporary token for 2FA verification (expires in 5 minutes)")
    message = serializers.CharField(help_text="Message indicating 2FA is required")


class TwoFactorStatusSerializer(serializers.Serializer):
    """Serializer for 2FA status response."""

    is_enabled = serializers.BooleanField(help_text="Whether 2FA is currently enabled")
    is_setup_pending = serializers.BooleanField(help_text="Whether 2FA setup is pending verification")
    backup_codes_remaining = serializers.IntegerField(help_text="Number of unused backup codes")


# ============================================================================
# Google OAuth Serializers
# ============================================================================

class GooglePatientAuthSerializer(serializers.Serializer):
    """
    Serializer for Google OAuth patient authentication.

    Handles both registration (new user) and login (existing user) flows.
    For new users, date_of_birth and phone_number are required.
    For existing users, only id_token is needed.
    """

    id_token = serializers.CharField(
        help_text="Google ID token from frontend OAuth flow"
    )
    date_of_birth = serializers.DateField(
        required=False,
        help_text="Date of birth (YYYY-MM-DD format) - required for new users"
    )
    phone_number = serializers.CharField(
        max_length=20,
        required=False,
        help_text="Phone number in international format (e.g., +1234567890) - required for new users"
    )

    def validate_date_of_birth(self, value):
        """Validate date of birth if provided."""
        if value:
            try:
                validate_date_of_birth(value)
            except DjangoValidationError as e:
                raise serializers.ValidationError(str(e.message))
        return value

    def validate_phone_number(self, value):
        """Validate phone number format if provided."""
        if value:
            try:
                phone_number_validator(value)
            except DjangoValidationError as e:
                raise serializers.ValidationError(str(e.message))
        return value

    def validate(self, attrs):
        """Validate Google token and determine if registration or login."""
        from .services import GoogleAuthService
        from .services.google_auth import GoogleAuthError

        id_token = attrs.get('id_token')

        # Verify Google token
        try:
            google_data = GoogleAuthService.verify_token(id_token)
        except GoogleAuthError as e:
            raise serializers.ValidationError({'id_token': str(e)})

        attrs['google_data'] = google_data

        # Check if user exists by Google ID
        existing_user_by_google_id = User.objects.filter(
            google_id=google_data['google_id']
        ).first()

        # Check if user exists by email
        existing_user_by_email = User.objects.filter(
            email__iexact=google_data['email']
        ).first()

        if existing_user_by_google_id:
            # Existing Google user - login flow
            if existing_user_by_google_id.user_type != 'patient':
                raise serializers.ValidationError({
                    'id_token': f"This Google account is registered as a {existing_user_by_google_id.user_type}, not a patient."
                })
            attrs['existing_user'] = existing_user_by_google_id
            attrs['is_new_user'] = False
        elif existing_user_by_email:
            # Email exists but not linked to Google
            if existing_user_by_email.auth_provider != 'google':
                raise serializers.ValidationError({
                    'id_token': "An account with this email already exists. Please login with your email and password."
                })
            # Edge case: email registered with Google but google_id doesn't match (shouldn't happen)
            raise serializers.ValidationError({
                'id_token': "This Google account is already linked to another user."
            })
        else:
            # New user - registration flow
            attrs['is_new_user'] = True

            # Validate required fields for new users
            if not attrs.get('date_of_birth'):
                raise serializers.ValidationError({
                    'date_of_birth': "This field is required for new users."
                })
            if not attrs.get('phone_number'):
                raise serializers.ValidationError({
                    'phone_number': "This field is required for new users."
                })

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create new patient user or return existing user."""
        google_data = validated_data['google_data']
        is_new_user = validated_data['is_new_user']

        if not is_new_user:
            return validated_data['existing_user']

        # Create new user
        user = User.objects.create_user(
            email=google_data['email'],
            password=None,  # No password for Google users
            first_name=google_data['first_name'] or 'User',
            last_name=google_data['last_name'] or '',
            user_type='patient',
            is_active=True,
            is_verified=True,  # Google verifies email
            google_id=google_data['google_id'],
            auth_provider='google',
        )

        # Create patient profile
        Patient.objects.create(
            user=user,
            date_of_birth=validated_data['date_of_birth'],
            phone_number=validated_data['phone_number'],
        )

        return user


class GoogleDoctorAuthSerializer(serializers.Serializer):
    """
    Serializer for Google OAuth doctor authentication.

    Handles both registration (new user) and login (existing user) flows.
    For new users, phone_number is required.
    For existing users, only id_token is needed.
    """

    id_token = serializers.CharField(
        help_text="Google ID token from frontend OAuth flow"
    )
    phone_number = serializers.CharField(
        max_length=20,
        required=False,
        help_text="Phone number in international format (e.g., +1234567890) - required for new users"
    )

    def validate_phone_number(self, value):
        """Validate phone number format if provided."""
        if value:
            try:
                phone_number_validator(value)
            except DjangoValidationError as e:
                raise serializers.ValidationError(str(e.message))
        return value

    def validate(self, attrs):
        """Validate Google token and determine if registration or login."""
        from .services import GoogleAuthService
        from .services.google_auth import GoogleAuthError

        id_token = attrs.get('id_token')

        # Verify Google token
        try:
            google_data = GoogleAuthService.verify_token(id_token)
        except GoogleAuthError as e:
            raise serializers.ValidationError({'id_token': str(e)})

        attrs['google_data'] = google_data

        # Check if user exists by Google ID
        existing_user_by_google_id = User.objects.filter(
            google_id=google_data['google_id']
        ).first()

        # Check if user exists by email
        existing_user_by_email = User.objects.filter(
            email__iexact=google_data['email']
        ).first()

        if existing_user_by_google_id:
            # Existing Google user - login flow
            if existing_user_by_google_id.user_type != 'doctor':
                raise serializers.ValidationError({
                    'id_token': f"This Google account is registered as a {existing_user_by_google_id.user_type}, not a doctor."
                })
            attrs['existing_user'] = existing_user_by_google_id
            attrs['is_new_user'] = False
        elif existing_user_by_email:
            # Email exists but not linked to Google
            if existing_user_by_email.auth_provider != 'google':
                raise serializers.ValidationError({
                    'id_token': "An account with this email already exists. Please login with your email and password."
                })
            # Edge case: email registered with Google but google_id doesn't match
            raise serializers.ValidationError({
                'id_token': "This Google account is already linked to another user."
            })
        else:
            # New user - registration flow
            attrs['is_new_user'] = True

            # Validate required fields for new users
            if not attrs.get('phone_number'):
                raise serializers.ValidationError({
                    'phone_number': "This field is required for new users."
                })

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create new doctor user or return existing user."""
        google_data = validated_data['google_data']
        is_new_user = validated_data['is_new_user']

        if not is_new_user:
            return validated_data['existing_user']

        # Create new user (inactive until admin approval)
        user = User.objects.create_user(
            email=google_data['email'],
            password=None,  # No password for Google users
            first_name=google_data['first_name'] or 'User',
            last_name=google_data['last_name'] or '',
            user_type='doctor',
            is_active=False,  # Requires admin approval
            is_verified=True,  # Google verifies email
            google_id=google_data['google_id'],
            auth_provider='google',
        )

        # Create doctor profile
        Doctor.objects.create(
            user=user,
            phone_number=validated_data['phone_number'],
        )

        return user


class GoogleLinkAccountSerializer(serializers.Serializer):
    """
    Serializer for linking a Google account to an existing user.

    Allows users who registered with email/password to link their Google account.
    """

    id_token = serializers.CharField(
        help_text="Google ID token from frontend OAuth flow"
    )

    def validate(self, attrs):
        """Validate Google token and check if linkable."""
        from .services import GoogleAuthService
        from .services.google_auth import GoogleAuthError

        id_token = attrs.get('id_token')
        user = self.context.get('request').user

        # Verify Google token
        try:
            google_data = GoogleAuthService.verify_token(id_token)
        except GoogleAuthError as e:
            raise serializers.ValidationError({'id_token': str(e)})

        attrs['google_data'] = google_data

        # Check if user already has Google linked
        if user.google_id:
            raise serializers.ValidationError({
                'id_token': "Your account already has a Google account linked."
            })

        # Check if this Google account is already linked to another user
        existing_google_user = User.objects.filter(
            google_id=google_data['google_id']
        ).first()

        if existing_google_user:
            raise serializers.ValidationError({
                'id_token': "This Google account is already linked to another user."
            })

        # Check if email matches (optional security check)
        if google_data['email'].lower() != user.email.lower():
            raise serializers.ValidationError({
                'id_token': "The Google account email does not match your account email."
            })

        return attrs

    def update(self, instance, validated_data):
        """Link Google account to user."""
        google_data = validated_data['google_data']

        instance.google_id = google_data['google_id']
        instance.save(update_fields=['google_id'])

        return instance


class GoogleAuthResponseSerializer(serializers.Serializer):
    """Serializer for Google auth login response."""

    message = serializers.CharField(help_text="Success message")
    user = UserResponseSerializer(help_text="User data")
    tokens = serializers.DictField(
        child=serializers.CharField(),
        help_text="JWT tokens (access and refresh)"
    )


class GoogleAuthRegistrationResponseSerializer(serializers.Serializer):
    """Serializer for Google auth registration response (patient)."""

    message = serializers.CharField(help_text="Success message")
    user = UserResponseSerializer(help_text="Created user data")
    tokens = serializers.DictField(
        child=serializers.CharField(),
        help_text="JWT tokens (access and refresh)"
    )


class GoogleDoctorRegistrationResponseSerializer(serializers.Serializer):
    """Serializer for Google auth registration response (doctor - no tokens, needs approval)."""

    message = serializers.CharField(help_text="Success message with approval notice")
    user = UserResponseSerializer(help_text="Created user data")


class GoogleLinkAccountResponseSerializer(serializers.Serializer):
    """Serializer for Google account link response."""

    message = serializers.CharField(help_text="Success message")
