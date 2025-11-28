from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Patient, User


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
