from datetime import date

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from utils.validators import phone_number_validator, validate_date_of_birth
from .managers import UserManager


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

    # Authentication & Identification
    email = models.EmailField(unique=True, max_length=255)  # unique=True creates an index
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, db_index=True)

    # Status & Permissions
    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False, db_index=True)

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
