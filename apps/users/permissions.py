from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'admin'


class IsSuperAdmin(BasePermission):
    """Check if admin has the Super Admin system role."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated or request.user.user_type != 'admin':
            return False
        assignment = getattr(request.user, 'admin_role_assignment', None)
        if assignment is None:
            return False
        return assignment.role.is_system


class IsDoctor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'doctor'


class IsSecretary(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'secretary'


class IsDoctorOrSecretary(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type in ('doctor', 'secretary')
        )


class HasDashboardPermission(BasePermission):
    """
    Generic permission check that verifies the user has a specific
    permission codename via their AdminRole.

    Usage in views:
        permission_classes = [IsAdmin, HasDashboardPermission]
        required_permission = 'view_all_users'
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        required = getattr(view, 'required_permission', None)
        if required is None:
            return True

        # Super admins (system role) always have all permissions
        assignment = getattr(request.user, 'admin_role_assignment', None)
        if assignment is None:
            return False
        if assignment.role.is_system:
            return True

        return assignment.role.permissions.filter(codename=required).exists()


# All admin permissions that can be assigned to custom roles
ADMIN_PERMISSION_CODENAMES = [
    'view_all_users',
    'manage_users',
    'deactivate_users',
    'approve_doctors',
    'manage_doctor_profiles',
    'view_all_appointments',
    'manage_all_appointments',
    'view_all_reviews',
    'moderate_reviews',
    'manage_categories',
    'manage_health_tips',
    'manage_settings',
    'view_analytics',
    'manage_roles',
    'view_all_secretaries',
]
