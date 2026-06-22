from django.contrib.auth import get_user_model

from apps.users.models import Doctor

User = get_user_model()


class AdminUserService:
    @staticmethod
    def get_user_or_none(pk):
        try:
            return User.objects.get(id=pk)
        except User.DoesNotExist:
            return None

    @staticmethod
    def get_doctor_or_none(pk):
        try:
            return Doctor.objects.select_related("user").get(user_id=pk)
        except Doctor.DoesNotExist:
            return None

    @staticmethod
    def approve_doctor(doctor):
        user = doctor.user
        if user.is_active:
            return False
        user.is_active = True
        user.save(update_fields=["is_active", "updated_at"])
        return True

    @staticmethod
    def decline_doctor(doctor):
        """
        Decline (reject) a pending doctor registration.

        Only pending (inactive) doctors may be declined. On success the user
        account is deleted (cascading to the Doctor profile) and a snapshot of
        the removed account is returned for audit logging. Returns None if the
        doctor is already active and therefore cannot be declined.
        """
        user = doctor.user
        if user.is_active:
            return None
        snapshot = {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.get_full_name(),
            "syndicate_number": doctor.syndicate_number,
        }
        user.delete()
        return snapshot
