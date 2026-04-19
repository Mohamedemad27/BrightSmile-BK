from apps.core.models import Appointment


class DoctorServiceLayer:
    DOCTOR_VALID_TRANSITIONS = {
        "pending": ["confirmed", "rejected"],
        "confirmed": ["completed", "rejected"],
    }

    @staticmethod
    def get_appointment_for_doctor(*, appointment_id, doctor):
        try:
            return (
                Appointment.objects.select_related("doctor__user", "patient")
                .prefetch_related("services")
                .get(id=appointment_id, doctor=doctor)
            )
        except Appointment.DoesNotExist:
            return None

    @classmethod
    def update_appointment_status(cls, *, appointment, new_status):
        allowed = cls.DOCTOR_VALID_TRANSITIONS.get(appointment.status, [])
        if new_status not in allowed:
            return False, f"Cannot change from {appointment.status} to {new_status}."

        appointment.status = new_status
        appointment.save(update_fields=["status", "updated_at"])
        return True, ""
