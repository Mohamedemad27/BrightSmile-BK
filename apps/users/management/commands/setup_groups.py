from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from apps.users.models import User, AdminRole
from apps.users.permissions import ADMIN_PERMISSION_CODENAMES


# Permissions defined on the User model proxy
DOCTOR_PERMISSION_CODENAMES = [
    'view_own_appointments',
    'manage_own_appointments',
    'view_own_patients',
    'view_own_profile',
    'manage_own_profile',
    'view_own_services',
    'manage_own_services',
    'view_own_reviews',
    'view_own_secretaries',
    'manage_own_secretaries',
    'view_own_analytics',
]

SECRETARY_PERMISSION_CODENAMES = [
    'view_doctor_appointments',
    'manage_doctor_appointments',
    'view_doctor_patients',
    'view_doctor_profile',
    'view_doctor_services',
]

ALL_CODENAMES = ADMIN_PERMISSION_CODENAMES + DOCTOR_PERMISSION_CODENAMES + SECRETARY_PERMISSION_CODENAMES


class Command(BaseCommand):
    help = 'Create default groups, permissions, and the Super Admin role'

    def handle(self, *args, **options):
        ct = ContentType.objects.get_for_model(User)

        # Create all custom permissions
        for codename in ALL_CODENAMES:
            name = codename.replace('_', ' ').title()
            Permission.objects.get_or_create(
                codename=codename,
                content_type=ct,
                defaults={'name': name},
            )

        self.stdout.write(self.style.SUCCESS(
            f'Created {len(ALL_CODENAMES)} custom permissions'
        ))

        # --- Groups ---
        admin_group, _ = Group.objects.get_or_create(name='Admin')
        doctor_group, _ = Group.objects.get_or_create(name='Doctor')
        secretary_group, _ = Group.objects.get_or_create(name='Secretary')

        admin_perms = Permission.objects.filter(codename__in=ADMIN_PERMISSION_CODENAMES, content_type=ct)
        admin_group.permissions.set(admin_perms)

        doctor_perms = Permission.objects.filter(codename__in=DOCTOR_PERMISSION_CODENAMES, content_type=ct)
        doctor_group.permissions.set(doctor_perms)

        secretary_perms = Permission.objects.filter(codename__in=SECRETARY_PERMISSION_CODENAMES, content_type=ct)
        secretary_group.permissions.set(secretary_perms)

        self.stdout.write(self.style.SUCCESS(
            f'Groups created: Admin ({admin_perms.count()} perms), '
            f'Doctor ({doctor_perms.count()} perms), '
            f'Secretary ({secretary_perms.count()} perms)'
        ))

        # --- Super Admin Role ---
        super_role, created = AdminRole.objects.get_or_create(
            name='Super Admin',
            defaults={
                'description': 'Full platform access with role management capabilities.',
                'is_system': True,
            },
        )
        super_role.permissions.set(admin_perms)
        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'{action} Super Admin role with all admin permissions'
        ))

        self.stdout.write(self.style.SUCCESS('Setup complete!'))
