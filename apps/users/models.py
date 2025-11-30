import base64
import secrets
from datetime import date, timedelta
from io import BytesIO

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
import pyotp
import qrcode

from utils.validators import phone_number_validator, validate_date_of_birth
from .managers import UserManager


def get_encryption_key():
    """
    Get or derive the encryption key for TOTP secrets.
    Uses Django's SECRET_KEY to derive a Fernet-compatible key.
    """
    secret_key = settings.SECRET_KEY.encode()
    # Pad or truncate to 32 bytes, then base64 encode for Fernet
    key = secret_key[:32].ljust(32, b'0')
    return base64.urlsafe_b64encode(key)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model that uses email as the primary authentication field.
    This serves as the base for all user types in the Bright Smile system.

    Patient, Doctor, and Admin models will extend this through OneToOne relationships.
    """

    USER_TYPE_CHOICES = [
        ('patient', 'Patient'),
        ('doctor', 'Doctor'),
        ('admin', 'Admin'),
    ]

    AUTH_PROVIDER_CHOICES = [
        ('email', 'Email'),
        ('google', 'Google'),
    ]

    # Authentication & Identification
    email = models.EmailField(unique=True, max_length=255)  # unique=True creates an index
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, db_index=True)

    # OAuth fields
    google_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Google OAuth user ID"
    )
    auth_provider = models.CharField(
        max_length=20,
        choices=AUTH_PROVIDER_CHOICES,
        default='email',
        db_index=True,
        help_text="Authentication provider used for registration"
    )

    # Status & Permissions
    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False, db_index=True)
    is_2fa_enabled = models.BooleanField(default=False, db_index=True)

    # Timestamps
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Custom manager
    objects = UserManager()

    # Authentication configuration
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'user_type']

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            # Composite index for common query pattern: filtering by user_type and status
            models.Index(fields=['user_type', 'is_active'], name='user_type_active_idx'),
            # Index for filtering verified active users
            models.Index(fields=['is_verified', 'is_active'], name='user_verified_active_idx'),
            # Index for email lookups with case-insensitive search support
            models.Index(fields=['email'], name='user_email_idx'),
            # Index for Google OAuth lookups
            models.Index(fields=['google_id'], name='user_google_id_idx'),
            # Index for auth provider filtering
            models.Index(fields=['auth_provider'], name='user_auth_provider_idx'),
        ]

    def __str__(self):
        """Return email as string representation."""
        return self.email

    def get_full_name(self):
        """
        Return the user's full name.

        Returns:
            str: Full name in format 'first_name last_name'
        """
        return f"{self.first_name} {self.last_name}"

    def get_short_name(self):
        """
        Return the user's short name.

        Returns:
            str: User's first name
        """
        return self.first_name


class Patient(models.Model):
    """
    Patient profile model that extends User through a OneToOne relationship.

    Stores patient-specific information including date of birth and phone number.
    This is one of the three user type models in the Bright Smile system.
    """

    # OneToOne relationship with User - uses user's pk as primary key
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='patient_profile',
        primary_key=True
    )

    # Patient-specific fields
    date_of_birth = models.DateField(
        validators=[validate_date_of_birth],
        db_index=True
    )
    phone_number = models.CharField(
        max_length=20,
        validators=[phone_number_validator],
        db_index=True
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Patient'
        verbose_name_plural = 'Patients'
        indexes = [
            models.Index(
                fields=['date_of_birth', 'phone_number'],
                name='patient_dob_phone_idx'
            ),
        ]

    def __str__(self):
        """Return patient's full name and email for identification."""
        return f"Patient: {self.user.get_full_name()} ({self.user.email})"

    @property
    def age(self):
        """
        Calculate the patient's current age from date of birth.

        Returns:
            int: Patient's age in years
        """
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def email(self):
        """Convenience property to access user's email."""
        return self.user.email

    @property
    def full_name(self):
        """Convenience property to access user's full name."""
        return self.user.get_full_name()


class Doctor(models.Model):
    """
    Doctor profile model that extends User through a OneToOne relationship.

    Stores doctor-specific information including phone number.
    This is one of the three user type models in the Bright Smile system.
    """

    # OneToOne relationship with User - uses user's pk as primary key
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='doctor_profile',
        primary_key=True
    )

    # Doctor-specific fields
    phone_number = models.CharField(
        max_length=20,
        validators=[phone_number_validator],
        db_index=True
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Doctor'
        verbose_name_plural = 'Doctors'
        indexes = [
            models.Index(fields=['phone_number'], name='doctor_phone_idx'),
        ]

    def __str__(self):
        """Return doctor's full name for identification."""
        return f"Doctor: {self.user.get_full_name()}"

    @property
    def email(self):
        """Convenience property to access user's email."""
        return self.user.email

    @property
    def full_name(self):
        """Convenience property to access user's full name."""
        return self.user.get_full_name()


class Admin(models.Model):
    """
    Admin profile model that extends User through a OneToOne relationship.

    This is a minimal implementation to establish the Admin model structure.
    This is one of the three user type models in the Bright Smile system.
    """

    # OneToOne relationship with User - uses user's pk as primary key
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='admin_profile',
        primary_key=True
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Admin'
        verbose_name_plural = 'Admins'

    def __str__(self):
        """Return admin's full name for identification."""
        return f"Admin: {self.user.get_full_name()}"

    @property
    def email(self):
        """Convenience property to access user's email."""
        return self.user.email

    @property
    def full_name(self):
        """Convenience property to access user's full name."""
        return self.user.get_full_name()


class EmailVerificationOTP(models.Model):
    """
    Model to store email verification OTPs.

    Stores both hashed OTP for verification and plain OTP for admin visibility.
    OTPs are also cached in Redis for fast lookups with configurable expiration.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='verification_otps'
    )
    otp_hash = models.CharField(
        max_length=128,
        help_text="Hashed OTP for secure verification"
    )
    otp_plain = models.CharField(
        max_length=6,
        help_text="Plain OTP for admin display only"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Email Verification OTP'
        verbose_name_plural = 'Email Verification OTPs'
        indexes = [
            models.Index(fields=['user', 'is_used'], name='otp_user_used_idx'),
            models.Index(fields=['expires_at'], name='otp_expires_idx'),
        ]

    def __str__(self):
        return f"OTP for {self.user.email} - {'Used' if self.is_used else 'Active'}"

    def save(self, *args, **kwargs):
        """Set expires_at if not already set."""
        if not self.expires_at:
            expiry_minutes = getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
            self.expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if OTP has expired."""
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        """Check if OTP is still valid (not used and not expired)."""
        return not self.is_used and not self.is_expired

    def verify(self, otp):
        """
        Verify the provided OTP against the stored hash.

        Args:
            otp: The plain text OTP to verify

        Returns:
            bool: True if OTP is valid and matches, False otherwise
        """
        if not self.is_valid:
            return False
        return check_password(otp, self.otp_hash)

    @classmethod
    def generate_otp(cls):
        """
        Generate a cryptographically secure 6-digit OTP.

        Returns:
            str: 6-digit OTP string
        """
        return ''.join(str(secrets.randbelow(10)) for _ in range(6))

    @classmethod
    def create_for_user(cls, user):
        """
        Create a new OTP for a user.

        Args:
            user: The user to create OTP for

        Returns:
            tuple: (EmailVerificationOTP instance, plain OTP string)
        """
        otp_plain = cls.generate_otp()
        otp_hash = make_password(otp_plain)

        otp_instance = cls.objects.create(
            user=user,
            otp_hash=otp_hash,
            otp_plain=otp_plain,
        )

        return otp_instance, otp_plain


class TwoFactorAuth(models.Model):
    """
    Model to store TOTP (Time-based One-Time Password) configuration for 2FA.

    The TOTP secret is stored encrypted using Fernet symmetric encryption.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='two_factor_auth',
        primary_key=True
    )
    encrypted_secret = models.TextField(
        help_text="Encrypted TOTP secret key"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether the 2FA setup has been verified with a valid code"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Two-Factor Authentication'
        verbose_name_plural = 'Two-Factor Authentications'

    def __str__(self):
        status = 'Verified' if self.is_verified else 'Pending'
        return f"2FA for {self.user.email} - {status}"

    @staticmethod
    def encrypt_secret(secret):
        """
        Encrypt a TOTP secret using Fernet encryption.

        Args:
            secret: Plain text TOTP secret

        Returns:
            str: Encrypted secret (base64 encoded)
        """
        fernet = Fernet(get_encryption_key())
        return fernet.encrypt(secret.encode()).decode()

    @staticmethod
    def decrypt_secret(encrypted_secret):
        """
        Decrypt an encrypted TOTP secret.

        Args:
            encrypted_secret: Encrypted secret string

        Returns:
            str: Plain text TOTP secret
        """
        fernet = Fernet(get_encryption_key())
        return fernet.decrypt(encrypted_secret.encode()).decode()

    @property
    def secret(self):
        """Get the decrypted TOTP secret."""
        return self.decrypt_secret(self.encrypted_secret)

    def get_totp(self):
        """
        Get a TOTP instance for this user.

        Returns:
            pyotp.TOTP: TOTP instance for generating/verifying codes
        """
        return pyotp.TOTP(self.secret)

    def verify_code(self, code):
        """
        Verify a TOTP code.

        Args:
            code: 6-digit TOTP code to verify

        Returns:
            bool: True if code is valid, False otherwise
        """
        totp = self.get_totp()
        return totp.verify(code)

    def get_provisioning_uri(self):
        """
        Get the provisioning URI for authenticator apps.

        Returns:
            str: otpauth:// URI for QR code generation
        """
        totp = self.get_totp()
        return totp.provisioning_uri(
            name=self.user.email,
            issuer_name=getattr(settings, 'TWO_FACTOR_ISSUER_NAME', 'Bright Smile')
        )

    def generate_qr_code_base64(self):
        """
        Generate a QR code for the provisioning URI as base64.

        Returns:
            str: Base64 encoded PNG image of the QR code
        """
        uri = self.get_provisioning_uri()
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        return base64.b64encode(buffer.getvalue()).decode()

    @classmethod
    def create_for_user(cls, user):
        """
        Create or update 2FA configuration for a user.

        Args:
            user: User instance

        Returns:
            TwoFactorAuth: The created or updated instance
        """
        # Generate a new random secret
        secret = pyotp.random_base32()
        encrypted_secret = cls.encrypt_secret(secret)

        # Create or update (in case user is re-setting up 2FA)
        instance, created = cls.objects.update_or_create(
            user=user,
            defaults={
                'encrypted_secret': encrypted_secret,
                'is_verified': False,
                'verified_at': None,
            }
        )

        return instance


class BackupCode(models.Model):
    """
    Model to store backup/recovery codes for 2FA.

    Backup codes are hashed before storage for security.
    Each code can only be used once.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='backup_codes'
    )
    code_hash = models.CharField(
        max_length=128,
        help_text="Hashed backup code"
    )
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Backup Code'
        verbose_name_plural = 'Backup Codes'
        indexes = [
            models.Index(fields=['user', 'is_used'], name='backup_code_user_used_idx'),
        ]

    def __str__(self):
        status = 'Used' if self.is_used else 'Active'
        return f"Backup code for {self.user.email} - {status}"

    def verify(self, code):
        """
        Verify a backup code against the stored hash.

        Args:
            code: Plain text backup code to verify

        Returns:
            bool: True if code matches and is not used, False otherwise
        """
        if self.is_used:
            return False
        return check_password(code, self.code_hash)

    def mark_used(self):
        """Mark this backup code as used."""
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=['is_used', 'used_at'])

    @staticmethod
    def generate_code():
        """
        Generate a cryptographically secure backup code.

        Returns:
            str: 8-character alphanumeric backup code
        """
        # Generate 8 character code using alphanumeric characters
        alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # Exclude similar chars (0, O, I, 1)
        return ''.join(secrets.choice(alphabet) for _ in range(8))

    @classmethod
    def generate_codes_for_user(cls, user, count=10):
        """
        Generate new backup codes for a user.

        Deletes any existing backup codes and generates new ones.

        Args:
            user: User instance
            count: Number of codes to generate (default 10)

        Returns:
            list: List of plain text backup codes (only returned once!)
        """
        # Delete existing backup codes
        cls.objects.filter(user=user).delete()

        plain_codes = []
        for _ in range(count):
            code = cls.generate_code()
            plain_codes.append(code)

            cls.objects.create(
                user=user,
                code_hash=make_password(code)
            )

        return plain_codes

    @classmethod
    def verify_code_for_user(cls, user, code):
        """
        Verify a backup code for a user.

        Args:
            user: User instance
            code: Plain text backup code to verify

        Returns:
            bool: True if code is valid and was marked as used, False otherwise
        """
        # Normalize code (uppercase, remove spaces/dashes)
        code = code.upper().replace(' ', '').replace('-', '')

        unused_codes = cls.objects.filter(user=user, is_used=False)
        for backup_code in unused_codes:
            if backup_code.verify(code):
                backup_code.mark_used()
                return True
        return False

    @classmethod
    def get_unused_count(cls, user):
        """
        Get the count of unused backup codes for a user.

        Args:
            user: User instance

        Returns:
            int: Number of unused backup codes
        """
        return cls.objects.filter(user=user, is_used=False).count()


class TwoFactorToken(models.Model):
    """
    Temporary token for 2FA verification during login.

    This token is issued after successful password authentication
    and can only be used to complete 2FA verification.
    Token expires after a short time (default 5 minutes).
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='two_factor_tokens'
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Temporary token for 2FA verification"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Two-Factor Token'
        verbose_name_plural = 'Two-Factor Tokens'
        indexes = [
            models.Index(fields=['token', 'is_used'], name='tfa_token_used_idx'),
            models.Index(fields=['expires_at'], name='tfa_token_expires_idx'),
        ]

    def __str__(self):
        status = 'Used' if self.is_used else 'Active'
        return f"2FA Token for {self.user.email} - {status}"

    def save(self, *args, **kwargs):
        """Set expires_at if not already set."""
        if not self.expires_at:
            expiry_minutes = getattr(settings, 'TWO_FACTOR_TOKEN_EXPIRY_MINUTES', 5)
            self.expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if token has expired."""
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        """Check if token is still valid (not used and not expired)."""
        return not self.is_used and not self.is_expired

    def mark_used(self):
        """Mark this token as used."""
        self.is_used = True
        self.save(update_fields=['is_used'])

    @classmethod
    def generate_token(cls):
        """
        Generate a cryptographically secure token.

        Returns:
            str: 64-character hex token
        """
        return secrets.token_hex(32)

    @classmethod
    def create_for_user(cls, user):
        """
        Create a new temporary 2FA token for a user.

        Invalidates any existing tokens for the user.

        Args:
            user: User instance

        Returns:
            TwoFactorToken: The created token instance
        """
        # Invalidate existing tokens
        cls.objects.filter(user=user, is_used=False).update(is_used=True)

        token = cls.generate_token()
        return cls.objects.create(
            user=user,
            token=token
        )

    @classmethod
    def verify_token(cls, token):
        """
        Verify a temporary 2FA token.

        Args:
            token: The token string to verify

        Returns:
            User or None: The user if token is valid, None otherwise
        """
        try:
            token_obj = cls.objects.get(token=token, is_used=False)
            if token_obj.is_valid:
                return token_obj.user
        except cls.DoesNotExist:
            pass
        return None

    @classmethod
    def get_and_invalidate(cls, token):
        """
        Get user from token and mark it as used.

        Args:
            token: The token string

        Returns:
            User or None: The user if token was valid, None otherwise
        """
        try:
            token_obj = cls.objects.get(token=token, is_used=False)
            if token_obj.is_valid:
                token_obj.mark_used()
                return token_obj.user
        except cls.DoesNotExist:
            pass
        return None
