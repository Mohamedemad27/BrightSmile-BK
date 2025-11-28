from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from utils.validators import phone_number_validator, validate_date_of_birth
from .models import Doctor, EmailVerificationOTP, Patient

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
