import logging
from datetime import datetime

from django.conf import settings
from django.template.loader import render_to_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

logger = logging.getLogger(__name__)


class SendGridEmailError(Exception):
    """Raised when SendGrid email delivery fails."""


def _send_email_via_sendgrid(*, to_email, subject, text_content, html_content):
    if not settings.SENDGRID_API_KEY:
        raise SendGridEmailError('SENDGRID_API_KEY is not configured.')

    message = Mail(
        from_email=settings.DEFAULT_FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        plain_text_content=text_content,
        html_content=html_content,
    )

    try:
        response = SendGridAPIClient(settings.SENDGRID_API_KEY).send(message)
    except Exception as exc:
        logger.exception(
            "SendGrid API request failed | to=%s from=%s",
            to_email,
            settings.DEFAULT_FROM_EMAIL,
        )
        raise SendGridEmailError(str(exc)) from exc

    body = response.body
    if isinstance(body, bytes):
        body = body.decode('utf-8', errors='replace')

    logger.info(
        "SendGrid email response | to=%s from=%s status=%s body=%s",
        to_email,
        settings.DEFAULT_FROM_EMAIL,
        response.status_code,
        body,
    )

    if response.status_code >= 400:
        raise SendGridEmailError(
            f"SendGrid returned status {response.status_code}: {body}"
        )

    return response


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
    return _send_email_via_sendgrid(
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
    return _send_email_via_sendgrid(
        to_email=to_email,
        subject=subject,
        text_content=text_content,
        html_content=html_content,
    )
