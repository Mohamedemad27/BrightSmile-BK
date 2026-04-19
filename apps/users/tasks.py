import logging
from datetime import datetime

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _get_email_context(user, otp, expiry_minutes):
    """
    Build common email context for OTP emails.

    Args:
        user: User instance
        otp: Plain text OTP code
        expiry_minutes: OTP expiry time in minutes

    Returns:
        dict: Context dictionary for email templates
    """
    return {
        'full_name': user.get_full_name(),
        'email': user.email,
        'otp': otp,
        'expiry_minutes': expiry_minutes,
        'year': datetime.now().year,
    }


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

        context = _get_email_context(user, otp, settings.OTP_EXPIRY_MINUTES)

        subject = 'Verify Your Email - Bright Smile'
        message = render_to_string('emails/verification_email.txt', context)
        html_message = render_to_string('emails/verification_email.html', context)

        logger.info(
            "Sending verification OTP email | task_id=%s user_id=%s to=%s backend=%s host=%s port=%s tls=%s from=%s",
            getattr(self.request, 'id', None),
            user_id,
            user.email,
            settings.EMAIL_BACKEND,
            settings.EMAIL_HOST,
            settings.EMAIL_PORT,
            settings.EMAIL_USE_TLS,
            settings.DEFAULT_FROM_EMAIL,
        )
        sent_count = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(
            "Verification OTP email send_mail completed | task_id=%s user_id=%s to=%s sent_count=%s",
            getattr(self.request, 'id', None),
            user_id,
            user.email,
            sent_count,
        )
        return True

    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return False

    except Exception as e:
        logger.exception("Failed to send verification OTP email | task_id=%s user_id=%s", getattr(self.request, 'id', None), user_id)
        # Retry the task
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

        context = _get_email_context(user, otp, settings.PASSWORD_RESET_OTP_EXPIRY_MINUTES)

        subject = 'Reset Your Password - Bright Smile'
        message = render_to_string('emails/password_reset_email.txt', context)
        html_message = render_to_string('emails/password_reset_email.html', context)

        logger.info(
            "Sending password reset OTP email | task_id=%s user_id=%s to=%s backend=%s host=%s port=%s tls=%s from=%s",
            getattr(self.request, 'id', None),
            user_id,
            user.email,
            settings.EMAIL_BACKEND,
            settings.EMAIL_HOST,
            settings.EMAIL_PORT,
            settings.EMAIL_USE_TLS,
            settings.DEFAULT_FROM_EMAIL,
        )
        sent_count = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(
            "Password reset OTP email send_mail completed | task_id=%s user_id=%s to=%s sent_count=%s",
            getattr(self.request, 'id', None),
            user_id,
            user.email,
            sent_count,
        )
        return True

    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return False

    except Exception as e:
        logger.exception("Failed to send password reset OTP email | task_id=%s user_id=%s", getattr(self.request, 'id', None), user_id)
        # Retry the task
        raise self.retry(exc=e)
