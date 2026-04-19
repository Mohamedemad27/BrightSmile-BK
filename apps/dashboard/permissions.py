from rest_framework.permissions import BasePermission

from apps.core.models import Appointment, DoctorService
from apps.users.models import Doctor, Secretary, User
from apps.users.permissions import HasDashboardPermission


class _RolePermission(BasePermission):
    expected_user_type = None

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == self.expected_user_type
        )

    def has_object_permission(self, request, view, obj):
        # Default: role-level auth only.
        return self.has_permission(request, view)


class AdminPermission(_RolePermission):
    expected_user_type = "admin"


class DoctorPermission(_RolePermission):
    expected_user_type = "doctor"

    @staticmethod
    def _get_doctor_profile(user):
        try:
            return user.doctor_profile
        except Doctor.DoesNotExist:
            return None
        except AttributeError:
            return None

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return self._get_doctor_profile(request.user) is not None

    def has_object_permission(self, request, view, obj):
        if not self.has_permission(request, view):
            return False

        doctor = self._get_doctor_profile(request.user)
        if doctor is None:
            return False

        if isinstance(obj, Doctor):
            return obj.user_id == request.user.id
        if isinstance(obj, Appointment):
            return obj.doctor_id == doctor.user_id
        if isinstance(obj, DoctorService):
            return obj.doctor_id == doctor.user_id
        if isinstance(obj, Secretary):
            return obj.doctor_id == doctor.user_id
        if isinstance(obj, User):
            return obj.id == request.user.id
        return False


class SecretaryPermission(_RolePermission):
    expected_user_type = "secretary"

    @staticmethod
    def _get_secretary_profile(user):
        try:
            return user.secretary_profile
        except Secretary.DoesNotExist:
            return None
        except AttributeError:
            return None

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return self._get_secretary_profile(request.user) is not None

    def has_object_permission(self, request, view, obj):
        if not self.has_permission(request, view):
            return False

        secretary = self._get_secretary_profile(request.user)
        if secretary is None:
            return False
        assigned_doctor = secretary.doctor

        if isinstance(obj, Doctor):
            return obj.user_id == assigned_doctor.user_id
        if isinstance(obj, Appointment):
            return obj.doctor_id == assigned_doctor.user_id
        if isinstance(obj, DoctorService):
            return obj.doctor_id == assigned_doctor.user_id
        if isinstance(obj, Secretary):
            return obj.user_id == request.user.id
        return False


class AdminDashboardPermission(AdminPermission):
    """
    Admin role check + codename-based permission check using `required_permission`.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return HasDashboardPermission().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)
