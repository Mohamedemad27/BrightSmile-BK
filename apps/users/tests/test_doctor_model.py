from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.users.models import Doctor

User = get_user_model()


class DoctorModelTestCase(TestCase):
    """Test cases for the Doctor model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='doctor@example.com',
            password='testpass123',
            first_name='John',
            last_name='Smith',
            user_type='doctor'
        )
        self.doctor_data = {
            'user': self.user,
            'phone_number': '+1234567890'
        }

    def test_create_doctor_with_valid_data(self):
        """Test creating a doctor with valid data is successful."""
        doctor = Doctor.objects.create(**self.doctor_data)

        self.assertEqual(doctor.user, self.user)
        self.assertEqual(doctor.phone_number, self.doctor_data['phone_number'])
        self.assertIsNotNone(doctor.created_at)
        self.assertIsNotNone(doctor.updated_at)

    def test_doctor_str_method(self):
        """Test the string representation of doctor."""
        doctor = Doctor.objects.create(**self.doctor_data)
        expected_str = f"Doctor: {self.user.get_full_name()}"
        self.assertEqual(str(doctor), expected_str)

    def test_doctor_email_property(self):
        """Test email convenience property."""
        doctor = Doctor.objects.create(**self.doctor_data)
        self.assertEqual(doctor.email, self.user.email)

    def test_doctor_full_name_property(self):
        """Test full_name convenience property."""
        doctor = Doctor.objects.create(**self.doctor_data)
        self.assertEqual(doctor.full_name, self.user.get_full_name())

    def test_doctor_timestamps_auto_generated(self):
        """Test that created_at and updated_at are automatically set."""
        doctor = Doctor.objects.create(**self.doctor_data)

        self.assertIsNotNone(doctor.created_at)
        self.assertIsNotNone(doctor.updated_at)

    def test_doctor_updated_at_changes_on_update(self):
        """Test that updated_at changes when doctor is updated."""
        doctor = Doctor.objects.create(**self.doctor_data)
        original_updated_at = doctor.updated_at

        # Update the doctor
        doctor.phone_number = '+9876543210'
        doctor.save()

        self.assertGreaterEqual(doctor.updated_at, original_updated_at)

    def test_doctor_one_to_one_relationship(self):
        """Test OneToOne relationship between Doctor and User."""
        doctor = Doctor.objects.create(**self.doctor_data)

        # Test forward relationship
        self.assertEqual(doctor.user.email, 'doctor@example.com')

        # Test reverse relationship
        self.assertEqual(self.user.doctor_profile, doctor)

    def test_doctor_cascade_delete(self):
        """Test that deleting user deletes associated doctor."""
        doctor = Doctor.objects.create(**self.doctor_data)
        doctor_pk = doctor.pk

        # Delete the user
        self.user.delete()

        # Doctor should be deleted too
        self.assertFalse(Doctor.objects.filter(pk=doctor_pk).exists())

    def test_doctor_primary_key_is_user_id(self):
        """Test that doctor uses user's primary key."""
        doctor = Doctor.objects.create(**self.doctor_data)
        self.assertEqual(doctor.pk, self.user.pk)

    def test_doctor_ordering(self):
        """Test that doctors are ordered by created_at descending."""
        user2 = User.objects.create_user(
            email='doctor2@example.com',
            password='testpass123',
            first_name='Jane',
            last_name='Doe',
            user_type='doctor'
        )
        doctor1 = Doctor.objects.create(**self.doctor_data)
        doctor2 = Doctor.objects.create(
            user=user2,
            phone_number='+1122334455'
        )

        doctors = list(Doctor.objects.all())
        # Most recently created should be first
        self.assertEqual(doctors[0], doctor2)
        self.assertEqual(doctors[1], doctor1)

    def test_doctor_verbose_name(self):
        """Test Doctor model verbose names."""
        self.assertEqual(Doctor._meta.verbose_name, 'Doctor')
        self.assertEqual(Doctor._meta.verbose_name_plural, 'Doctors')

    def test_only_one_doctor_profile_per_user(self):
        """Test that a user can only have one doctor profile."""
        Doctor.objects.create(**self.doctor_data)

        # Attempting to create another doctor profile for the same user should fail
        with self.assertRaises(Exception):
            Doctor.objects.create(
                user=self.user,
                phone_number='+9999999999'
            )


class DoctorValidationTestCase(TestCase):
    """Test cases for Doctor model validation."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='validation@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            user_type='doctor'
        )

    def test_valid_phone_number_formats(self):
        """Test various valid phone number formats."""
        valid_numbers = [
            '+1234567890',
            '+12345678901234',
            '1234567890',
            '+11234567890',
        ]

        for phone in valid_numbers:
            doctor = Doctor(
                user=self.user,
                phone_number=phone
            )
            # Should not raise validation error
            doctor.full_clean()
            # Clean up for next iteration
            self.user = User.objects.create_user(
                email=f'{phone}@example.com',
                password='testpass123',
                first_name='Test',
                last_name='User',
                user_type='doctor'
            )

    def test_invalid_phone_number_format(self):
        """Test that invalid phone numbers raise ValidationError."""
        invalid_numbers = [
            'abc1234567',       # Contains letters
            '+1234',            # Too short
            '12345678901234567', # Too long (more than 15 digits)
        ]

        for phone in invalid_numbers:
            doctor = Doctor(
                user=self.user,
                phone_number=phone
            )
            with self.assertRaises(ValidationError):
                doctor.full_clean()


class DoctorSignalTestCase(TestCase):
    """Test cases for Doctor model signals."""

    def test_user_type_set_on_doctor_creation(self):
        """Test that user_type is automatically set to 'doctor' when Doctor is created."""
        # Create user without doctor type
        user = User.objects.create_user(
            email='signal_test@example.com',
            password='testpass123',
            first_name='Signal',
            last_name='Test',
            user_type='patient'  # Intentionally set to patient
        )

        # Create doctor profile
        Doctor.objects.create(
            user=user,
            phone_number='+1234567890'
        )

        # Refresh user from database
        user.refresh_from_db()

        # User type should now be 'doctor'
        self.assertEqual(user.user_type, 'doctor')

    def test_user_type_not_changed_if_already_doctor(self):
        """Test that signal doesn't trigger unnecessary save if user_type is already 'doctor'."""
        user = User.objects.create_user(
            email='already_doctor@example.com',
            password='testpass123',
            first_name='Already',
            last_name='Doctor',
            user_type='doctor'
        )

        with patch.object(User, 'save') as mock_save:
            Doctor.objects.create(
                user=user,
                phone_number='+1234567890'
            )
            # User.save should not be called since user_type is already 'doctor'
            mock_save.assert_not_called()

    def test_signal_only_on_creation(self):
        """Test that signal only fires on creation, not on update."""
        user = User.objects.create_user(
            email='update_test@example.com',
            password='testpass123',
            first_name='Update',
            last_name='Test',
            user_type='patient'
        )

        # Create doctor
        doctor = Doctor.objects.create(
            user=user,
            phone_number='+1234567890'
        )

        # Change user_type back to patient manually
        user.user_type = 'patient'
        user.save()

        # Update doctor (not create)
        doctor.phone_number = '+9876543210'
        doctor.save()

        # User type should still be 'patient' since signal only fires on creation
        user.refresh_from_db()
        self.assertEqual(user.user_type, 'patient')
