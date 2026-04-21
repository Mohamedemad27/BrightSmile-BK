import logging

from celery import shared_task
from django.conf import settings

from .services.email_service import (
    SendGridEmailError,
    send_otp_email,
    send_password_reset_email,
)

logger = logging.getLogger(__name__)


def dispatch_verification_email(user_id, otp):
    """
    Send verification email immediately when debugging SMTP issues, otherwise
    enqueue it through Celery.
    """
    if settings.OTP_EMAILS_SYNC:
        logger.info(
            "OTP_EMAILS_SYNC enabled; sending verification email synchronously | user_id=%s",
            user_id,
        )
        send_verification_email_task(user_id, otp)
        return None
    return send_verification_email_task.delay(user_id, otp)


def dispatch_password_reset_email(user_id, otp):
    """
    Send password-reset email immediately when debugging SMTP issues, otherwise
    enqueue it through Celery.
    """
    if settings.OTP_EMAILS_SYNC:
        logger.info(
            "OTP_EMAILS_SYNC enabled; sending password reset email synchronously | user_id=%s",
            user_id,
        )
        send_password_reset_email_task(user_id, otp)
        return None
    return send_password_reset_email_task.delay(user_id, otp)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email_task(self, user_id, otp):
    """
    Celery task to send verification email with OTP code.

    Args:
        user_id: The ID of the user to send email to
        otp: The plain text OTP code to include in email

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    from apps.users.models import User

    try:
        user = User.objects.get(id=user_id)

        logger.info(
            "Sending verification OTP email via SendGrid API | task_id=%s user_id=%s to=%s from=%s",
            getattr(self.request, 'id', None),
            user_id,
            user.email,
            settings.DEFAULT_FROM_EMAIL,
        )
        response = send_otp_email(
            user.email,
            otp,
            full_name=user.get_full_name(),
            expiry_minutes=settings.OTP_EXPIRY_MINUTES,
        )

        logger.info(
            "Verification OTP email SendGrid API completed | task_id=%s user_id=%s to=%s status=%s",
            getattr(self.request, 'id', None),
            user_id,
            user.email,
            response.status_code,
        )
        return True

    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return False

    except SendGridEmailError as e:
        logger.exception("Failed to send verification OTP email | task_id=%s user_id=%s", getattr(self.request, 'id', None), user_id)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email_task(self, user_id, otp):
    """
    Celery task to send password reset email with OTP code.

    Args:
        user_id: The ID of the user to send email to
        otp: The plain text OTP code to include in email

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    from apps.users.models import User

    try:
        user = User.objects.get(id=user_id)

        logger.info(
            "Sending password reset OTP email via SendGrid API | task_id=%s user_id=%s to=%s from=%s",
            getattr(self.request, 'id', None),
            user_id,
            user.email,
            settings.DEFAULT_FROM_EMAIL,
        )
        response = send_password_reset_email(
            user.email,
            otp,
            full_name=user.get_full_name(),
            expiry_minutes=settings.PASSWORD_RESET_OTP_EXPIRY_MINUTES,
        )

        logger.info(
            "Password reset OTP email SendGrid API completed | task_id=%s user_id=%s to=%s status=%s",
            getattr(self.request, 'id', None),
            user_id,
            user.email,
            response.status_code,
        )
        return True

    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return False

    except SendGridEmailError as e:
        logger.exception("Failed to send password reset OTP email | task_id=%s user_id=%s", getattr(self.request, 'id', None), user_id)
        raise self.retry(exc=e)
