import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


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

        subject = 'Verify Your Email - Bright Smile'
        message = f"""
Hello {user.get_full_name()},

Your verification code is: {otp}

This code will expire in {settings.OTP_EXPIRY_MINUTES} minutes.

If you did not request this verification code, please ignore this email.

Best regards,
Bright Smile Team
"""
        html_message = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .otp-code {{ font-size: 32px; font-weight: bold; color: #2563eb; letter-spacing: 8px; text-align: center; padding: 20px; background: #f3f4f6; border-radius: 8px; margin: 20px 0; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Email Verification</h2>
        <p>Hello {user.get_full_name()},</p>
        <p>Your verification code is:</p>
        <div class="otp-code">{otp}</div>
        <p>This code will expire in <strong>{settings.OTP_EXPIRY_MINUTES} minutes</strong>.</p>
        <p>If you did not request this verification code, please ignore this email.</p>
        <div class="footer">
            <p>Best regards,<br>Bright Smile Team</p>
        </div>
    </div>
</body>
</html>
"""

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Verification email sent successfully to {user.email}")
        return True

    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return False

    except Exception as e:
        logger.error(f"Failed to send verification email to user {user_id}: {str(e)}")
        # Retry the task
        raise self.retry(exc=e)
