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
