from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


def validate_date_of_birth(value):
    """
    Validate that date of birth is not in the future and meets minimum age requirement.

    Args:
        value: The date of birth to validate

    Raises:
        ValidationError: If date is in the future or user is too young
    """
    today = date.today()
    if value > today:
        raise ValidationError('Date of birth cannot be in the future.')

    # Calculate age
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age < 0:
        raise ValidationError('Invalid date of birth.')


# Phone number validator for international format
phone_number_validator = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be entered in the format: '+999999999'. "
            "Up to 15 digits allowed."
)
