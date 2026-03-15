from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Admin as AdminModel, AdminRole, AdminRoleAssignment, Doctor, EmailVerificationOTP, Patient, Secretary, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for the User model."""

    list_display = [
        'email',
        'first_name',
        'last_name',
        'user_type',
        'is_active',
        'is_verified',
        'is_staff',
        'created_at',
    ]
    list_filter = ['user_type', 'is_active', 'is_verified', 'is_staff', 'is_superuser']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'last_login']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'user_type')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'user_type', 'password1', 'password2'),
        }),
    )


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    """Admin configuration for the Patient model."""

    list_display = [
        'get_email',
        'get_full_name',
        'date_of_birth',
        'age',
        'phone_number',
        'created_at',
    ]
    list_filter = ['created_at', 'date_of_birth']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'phone_number']
    ordering = ['-created_at']
    readonly_fields = ['age', 'created_at', 'updated_at']
    raw_id_fields = ['user']

    fieldsets = (
        ('User Information', {'fields': ('user',)}),
        ('Patient Details', {'fields': ('date_of_birth', 'age', 'phone_number')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    @admin.display(description='Email', ordering='user__email')
    def get_email(self, obj):
        """Return the patient's email."""
        return obj.user.email

    @admin.display(description='Full Name', ordering='user__first_name')
    def get_full_name(self, obj):
        """Return the patient's full name."""
        return obj.user.get_full_name()


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    """Admin configuration for the Doctor model."""

    list_display = [
        'get_email',
        'get_full_name',
        'phone_number',
        'created_at',
    ]
    list_filter = ['created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'phone_number']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user']

    fieldsets = (
        ('User Information', {'fields': ('user',)}),
        ('Doctor Details', {'fields': ('phone_number',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    @admin.display(description='Email', ordering='user__email')
    def get_email(self, obj):
        """Return the doctor's email."""
        return obj.user.email

    @admin.display(description='Full Name', ordering='user__first_name')
    def get_full_name(self, obj):
        """Return the doctor's full name."""
        return obj.user.get_full_name()


@admin.register(AdminModel)
class AdminProfileAdmin(admin.ModelAdmin):
    """Admin configuration for the Admin model."""

    list_display = [
        'get_email',
        'get_full_name',
        'get_is_staff',
        'created_at',
    ]
    list_filter = ['created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user']

    fieldsets = (
        ('User Information', {'fields': ('user',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    @admin.display(description='Email', ordering='user__email')
    def get_email(self, obj):
        """Return the admin's email."""
        return obj.user.email

    @admin.display(description='Full Name', ordering='user__first_name')
    def get_full_name(self, obj):
        """Return the admin's full name."""
        return obj.user.get_full_name()

    @admin.display(description='Staff Status', boolean=True)
    def get_is_staff(self, obj):
        """Return the admin's staff status."""
        return obj.user.is_staff


@admin.register(Secretary)
class SecretaryAdmin(admin.ModelAdmin):
    list_display = ['get_email', 'get_full_name', 'get_doctor_name', 'phone_number', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'doctor__user__first_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user', 'doctor']

    @admin.display(description='Email', ordering='user__email')
    def get_email(self, obj):
        return obj.user.email

    @admin.display(description='Full Name', ordering='user__first_name')
    def get_full_name(self, obj):
        return obj.user.get_full_name()

    @admin.display(description='Doctor')
    def get_doctor_name(self, obj):
        return obj.doctor.full_name


@admin.register(AdminRole)
class AdminRoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_system', 'get_assignment_count', 'created_at']
    list_filter = ['is_system']
    search_fields = ['name']
    filter_horizontal = ['permissions']

    @admin.display(description='Assigned Users')
    def get_assignment_count(self, obj):
        return obj.assignments.count()


@admin.register(AdminRoleAssignment)
class AdminRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ['get_user_email', 'role', 'assigned_at']
    list_filter = ['role']
    raw_id_fields = ['user']

    @admin.display(description='User', ordering='user__email')
    def get_user_email(self, obj):
        return obj.user.email


@admin.register(EmailVerificationOTP)
class EmailVerificationOTPAdmin(admin.ModelAdmin):
    """Admin configuration for the EmailVerificationOTP model."""

    list_display = [
        'get_email',
        'otp_plain',
        'is_used',
        'is_expired_display',
        'created_at',
        'expires_at',
    ]
    list_filter = ['is_used', 'created_at', 'expires_at']
    search_fields = ['user__email', 'otp_plain']
    ordering = ['-created_at']
    readonly_fields = ['otp_hash', 'otp_plain', 'created_at', 'is_expired_display', 'is_valid_display']
    raw_id_fields = ['user']

    fieldsets = (
        ('User Information', {'fields': ('user',)}),
        ('OTP Details', {'fields': ('otp_plain', 'otp_hash', 'is_used')}),
        ('Validity', {'fields': ('expires_at', 'is_expired_display', 'is_valid_display')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )

    @admin.display(description='Email', ordering='user__email')
    def get_email(self, obj):
        """Return the user's email."""
        return obj.user.email

    @admin.display(description='Expired', boolean=True)
    def is_expired_display(self, obj):
        """Return whether the OTP is expired."""
        return obj.is_expired

    @admin.display(description='Valid', boolean=True)
    def is_valid_display(self, obj):
        """Return whether the OTP is valid (not used and not expired)."""
        return obj.is_valid
