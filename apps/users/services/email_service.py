import logging
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when a transactional (OTP/password-reset) email fails to send."""


# Backwards-compatible alias: callers/tests historically imported this name.
SendGridEmailError = EmailDeliveryError


class _EmailResult:
    """Lightweight result object so callers can log a status code like before."""

    def __init__(self, sent):
        self.status_code = 202 if sent else 500
        self.body = 'sent' if sent else 'not-sent'


def _send_email_via_smtp(*, to_email, subject, text_content, html_content):
    from_email = settings.DEFAULT_FROM_EMAIL

    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[to_email],
        )
        message.attach_alternative(html_content, 'text/html')
        sent = message.send(fail_silently=False)
    except Exception as exc:
        logger.exception(
            "SMTP email send failed | to=%s from=%s host=%s",
            to_email,
            from_email,
            getattr(settings, 'EMAIL_HOST', ''),
        )
        raise EmailDeliveryError(str(exc)) from exc

    logger.info(
        "SMTP email sent | to=%s from=%s sent=%s",
        to_email,
        from_email,
        sent,
    )

    if not sent:
        raise EmailDeliveryError(
            f"Email backend reported 0 messages delivered to {to_email}"
        )

    return _EmailResult(sent)


def send_otp_email(to_email, otp, *, full_name='', expiry_minutes=None):
    context = {
        'full_name': full_name,
        'email': to_email,
        'otp': otp,
        'expiry_minutes': expiry_minutes or settings.OTP_EXPIRY_MINUTES,
        'year': datetime.now().year,
    }

    subject = 'Verify Your Email - Bright Smile'
    text_content = render_to_string('emails/verification_email.txt', context)
    html_content = render_to_string('emails/verification_email.html', context)
    return _send_email_via_smtp(
        to_email=to_email,
        subject=subject,
        text_content=text_content,
        html_content=html_content,
    )


def send_password_reset_email(to_email, otp, *, full_name='', expiry_minutes=None):
    context = {
        'full_name': full_name,
        'email': to_email,
        'otp': otp,
        'expiry_minutes': expiry_minutes or settings.PASSWORD_RESET_OTP_EXPIRY_MINUTES,
        'year': datetime.now().year,
    }

    subject = 'Reset Your Password - Bright Smile'
    text_content = render_to_string('emails/password_reset_email.txt', context)
    html_content = render_to_string('emails/password_reset_email.html', context)
    return _send_email_via_smtp(
        to_email=to_email,
        subject=subject,
        text_content=text_content,
        html_content=html_content,
    )
