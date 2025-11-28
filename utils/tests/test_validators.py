from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase

from utils.validators import phone_number_validator, validate_date_of_birth


class DateOfBirthValidatorTestCase(TestCase):
    """Test cases for validate_date_of_birth validator."""

    def test_valid_date_of_birth(self):
        """Test that valid dates do not raise errors."""
        valid_dates = [
            date(1990, 5, 15),
            date(2000, 1, 1),
            date.today() - timedelta(days=365),
            date.today(),  # Newborn
        ]
        for dob in valid_dates:
            # Should not raise
            validate_date_of_birth(dob)

    def test_future_date_raises_error(self):
        """Test that future dates raise ValidationError."""
        future_date = date.today() + timedelta(days=1)
        with self.assertRaises(ValidationError) as context:
            validate_date_of_birth(future_date)
        self.assertIn('Date of birth cannot be in the future', str(context.exception))

    def test_far_future_date_raises_error(self):
        """Test that dates far in the future raise ValidationError."""
        far_future = date.today() + timedelta(days=365)
        with self.assertRaises(ValidationError) as context:
            validate_date_of_birth(far_future)
        self.assertIn('Date of birth cannot be in the future', str(context.exception))


class PhoneNumberValidatorTestCase(TestCase):
    """Test cases for phone_number_validator."""

    def test_valid_phone_numbers(self):
        """Test that valid phone numbers do not raise errors."""
        valid_numbers = [
            '+1234567890',
            '+12345678901234',
            '1234567890',
            '+11234567890',
            '123456789',  # 9 digits - minimum
            '123456789012345',  # 15 digits - maximum
        ]
        for phone in valid_numbers:
            # Should not raise
            phone_number_validator(phone)

    def test_phone_with_letters_raises_error(self):
        """Test that phone numbers with letters raise ValidationError."""
        with self.assertRaises(ValidationError):
            phone_number_validator('abc1234567')

    def test_phone_too_short_raises_error(self):
        """Test that phone numbers with fewer than 9 digits raise ValidationError."""
        with self.assertRaises(ValidationError):
            phone_number_validator('+1234')

    def test_phone_too_long_raises_error(self):
        """Test that phone numbers with more than 15 digits raise ValidationError."""
        with self.assertRaises(ValidationError):
            phone_number_validator('12345678901234567')  # 17 digits

    def test_phone_with_special_characters_raises_error(self):
        """Test that phone numbers with special characters (except +) raise ValidationError."""
        invalid_numbers = [
            '123-456-7890',
            '(123) 456-7890',
            '123.456.7890',
        ]
        for phone in invalid_numbers:
            with self.assertRaises(ValidationError):
                phone_number_validator(phone)

    def test_phone_with_plus_at_start_valid(self):
        """Test that + at the start is valid."""
        phone_number_validator('+1234567890')

    def test_phone_with_plus_in_middle_invalid(self):
        """Test that + in the middle is invalid."""
        with self.assertRaises(ValidationError):
            phone_number_validator('123+4567890')
