import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def send_verification_otp(user):
    """
    Helper function to create OTP and send verification email.

    Args:
        user: The User instance to send OTP to
    """
    from apps.users.models import EmailVerificationOTP
    from apps.users.tasks import send_verification_email_task

    # Create OTP for user
    otp_instance, otp_plain = EmailVerificationOTP.create_for_user(user)

    # Send email via Celery background task
    send_verification_email_task.delay(user.id, otp_plain)

    logger.info(f"Verification OTP sent to {user.email}")


@receiver(post_save, sender='users.Patient')
def set_patient_user_type(sender, instance, created, **kwargs):
    """
    Signal handler to automatically set user.user_type='patient' when a Patient is created.
    Also sends verification OTP email.

    Args:
        sender: The model class (Patient)
        instance: The Patient instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    if created:
        if instance.user.user_type != 'patient':
            instance.user.user_type = 'patient'
            instance.user.save(update_fields=['user_type'])

        # Send verification OTP email
        send_verification_otp(instance.user)


@receiver(post_save, sender='users.Doctor')
def set_doctor_user_type(sender, instance, created, **kwargs):
    """
    Signal handler to automatically set user.user_type='doctor' when a Doctor is created.
    Also sends verification OTP email.

    Args:
        sender: The model class (Doctor)
        instance: The Doctor instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    if created:
        if instance.user.user_type != 'doctor':
            instance.user.user_type = 'doctor'
            instance.user.save(update_fields=['user_type'])

        # Send verification OTP email
        send_verification_otp(instance.user)


@receiver(post_save, sender='users.Admin')
def set_admin_user_type(sender, instance, created, **kwargs):
    """
    Signal handler to automatically set user.user_type='admin' and is_staff=True when an Admin is created.

    Args:
        sender: The model class (Admin)
        instance: The Admin instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    if created:
        update_fields = []
        if instance.user.user_type != 'admin':
            instance.user.user_type = 'admin'
            update_fields.append('user_type')
        if not instance.user.is_staff:
            instance.user.is_staff = True
            update_fields.append('is_staff')
        if update_fields:
            instance.user.save(update_fields=update_fields)


@receiver(post_save, sender='users.User')
def create_admin_profile_for_superuser(sender, instance, created, **kwargs):
    """
    Signal handler to automatically create an Admin profile when a superuser is created.

    Args:
        sender: The model class (User)
        instance: The User instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    # Import here to avoid circular imports
    from apps.users.models import Admin

    if created and instance.is_superuser:
        # Check if admin profile doesn't already exist
        if not hasattr(instance, 'admin_profile'):
            Admin.objects.create(user=instance)
