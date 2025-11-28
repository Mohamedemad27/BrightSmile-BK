from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.users.models import Patient

User = get_user_model()


class PatientModelTestCase(TestCase):
    """Test cases for the Patient model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='patient@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe',
            user_type='patient'
        )
        self.patient_data = {
            'user': self.user,
            'date_of_birth': date(1990, 5, 15),
            'phone_number': '+1234567890'
        }

    def test_create_patient_with_valid_data(self):
        """Test creating a patient with valid data is successful."""
        patient = Patient.objects.create(**self.patient_data)

        self.assertEqual(patient.user, self.user)
        self.assertEqual(patient.date_of_birth, self.patient_data['date_of_birth'])
        self.assertEqual(patient.phone_number, self.patient_data['phone_number'])
        self.assertIsNotNone(patient.created_at)
        self.assertIsNotNone(patient.updated_at)

    def test_patient_str_method(self):
        """Test the string representation of patient."""
        patient = Patient.objects.create(**self.patient_data)
        expected_str = f"Patient: {self.user.get_full_name()} ({self.user.email})"
        self.assertEqual(str(patient), expected_str)

    def test_patient_age_property(self):
        """Test age calculation from date of birth."""
        patient = Patient.objects.create(**self.patient_data)

        # Calculate expected age
        today = date.today()
        expected_age = today.year - 1990 - (
            (today.month, today.day) < (5, 15)
        )
        self.assertEqual(patient.age, expected_age)

    def test_patient_age_birthday_not_yet(self):
        """Test age calculation when birthday hasn't occurred this year."""
        # Set date of birth to later this year (or next if we're in December)
        future_month = (date.today().month % 12) + 1
        future_day = min(15, 28)  # Safe day for all months
        birth_year = date.today().year - 30

        user = User.objects.create_user(
            email='patient2@example.com',
            password='testpass123',
            first_name='Jane',
            last_name='Doe',
            user_type='patient'
        )
        patient = Patient.objects.create(
            user=user,
            date_of_birth=date(birth_year, future_month, future_day),
            phone_number='+1987654321'
        )

        # If birthday is in a future month this year, age should be 29
        today = date.today()
        if (future_month, future_day) > (today.month, today.day):
            self.assertEqual(patient.age, 29)
        else:
            self.assertEqual(patient.age, 30)

    def test_patient_email_property(self):
        """Test email convenience property."""
        patient = Patient.objects.create(**self.patient_data)
        self.assertEqual(patient.email, self.user.email)

    def test_patient_full_name_property(self):
        """Test full_name convenience property."""
        patient = Patient.objects.create(**self.patient_data)
        self.assertEqual(patient.full_name, self.user.get_full_name())

    def test_patient_timestamps_auto_generated(self):
        """Test that created_at and updated_at are automatically set."""
        patient = Patient.objects.create(**self.patient_data)

        self.assertIsNotNone(patient.created_at)
        self.assertIsNotNone(patient.updated_at)

    def test_patient_updated_at_changes_on_update(self):
        """Test that updated_at changes when patient is updated."""
        patient = Patient.objects.create(**self.patient_data)
        original_updated_at = patient.updated_at

        # Update the patient
        patient.phone_number = '+9876543210'
        patient.save()

        self.assertGreaterEqual(patient.updated_at, original_updated_at)

    def test_patient_one_to_one_relationship(self):
        """Test OneToOne relationship between Patient and User."""
        patient = Patient.objects.create(**self.patient_data)

        # Test forward relationship
        self.assertEqual(patient.user.email, 'patient@example.com')

        # Test reverse relationship
        self.assertEqual(self.user.patient_profile, patient)

    def test_patient_cascade_delete(self):
        """Test that deleting user deletes associated patient."""
        patient = Patient.objects.create(**self.patient_data)
        patient_pk = patient.pk

        # Delete the user
        self.user.delete()

        # Patient should be deleted too
        self.assertFalse(Patient.objects.filter(pk=patient_pk).exists())

    def test_patient_primary_key_is_user_id(self):
        """Test that patient uses user's primary key."""
        patient = Patient.objects.create(**self.patient_data)
        self.assertEqual(patient.pk, self.user.pk)

    def test_patient_ordering(self):
        """Test that patients are ordered by created_at descending."""
        user2 = User.objects.create_user(
            email='patient2@example.com',
            password='testpass123',
            first_name='Jane',
            last_name='Smith',
            user_type='patient'
        )
        patient1 = Patient.objects.create(**self.patient_data)
        patient2 = Patient.objects.create(
            user=user2,
            date_of_birth=date(1985, 3, 20),
            phone_number='+1122334455'
        )

        patients = list(Patient.objects.all())
        # Most recently created should be first
        self.assertEqual(patients[0], patient2)
        self.assertEqual(patients[1], patient1)

    def test_patient_verbose_name(self):
        """Test Patient model verbose names."""
        self.assertEqual(Patient._meta.verbose_name, 'Patient')
        self.assertEqual(Patient._meta.verbose_name_plural, 'Patients')


class PatientValidationTestCase(TestCase):
    """Test cases for Patient model validation."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='validation@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            user_type='patient'
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
            patient = Patient(
                user=self.user,
                date_of_birth=date(1990, 1, 1),
                phone_number=phone
            )
            # Should not raise validation error
            patient.full_clean()
            # Clean up for next iteration
            self.user = User.objects.create_user(
                email=f'{phone}@example.com',
                password='testpass123',
                first_name='Test',
                last_name='User',
                user_type='patient'
            )

    def test_invalid_phone_number_format(self):
        """Test that invalid phone numbers raise ValidationError."""
        invalid_numbers = [
            'abc1234567',       # Contains letters
            '+1234',            # Too short
            '12345678901234567', # Too long (more than 15 digits)
        ]

        for phone in invalid_numbers:
            patient = Patient(
                user=self.user,
                date_of_birth=date(1990, 1, 1),
                phone_number=phone
            )
            with self.assertRaises(ValidationError):
                patient.full_clean()

    def test_date_of_birth_in_future_raises_error(self):
        """Test that date of birth in future raises ValidationError."""
        future_date = date.today() + timedelta(days=1)
        patient = Patient(
            user=self.user,
            date_of_birth=future_date,
            phone_number='+1234567890'
        )
        with self.assertRaises(ValidationError) as context:
            patient.full_clean()

        self.assertIn('Date of birth cannot be in the future', str(context.exception))

    def test_date_of_birth_today_is_valid(self):
        """Test that date of birth today is valid (for newborns)."""
        patient = Patient(
            user=self.user,
            date_of_birth=date.today(),
            phone_number='+1234567890'
        )
        # Should not raise validation error
        patient.full_clean()


class PatientSignalTestCase(TestCase):
    """Test cases for Patient model signals."""

    def test_user_type_set_on_patient_creation(self):
        """Test that user_type is automatically set to 'patient' when Patient is created."""
        # Create user without patient type
        user = User.objects.create_user(
            email='signal_test@example.com',
            password='testpass123',
            first_name='Signal',
            last_name='Test',
            user_type='doctor'  # Intentionally set to doctor
        )

        # Create patient profile
        Patient.objects.create(
            user=user,
            date_of_birth=date(1990, 1, 1),
            phone_number='+1234567890'
        )

        # Refresh user from database
        user.refresh_from_db()

        # User type should now be 'patient'
        self.assertEqual(user.user_type, 'patient')

    def test_user_type_not_changed_if_already_patient(self):
        """Test that signal doesn't trigger unnecessary save if user_type is already 'patient'."""
        user = User.objects.create_user(
            email='already_patient@example.com',
            password='testpass123',
            first_name='Already',
            last_name='Patient',
            user_type='patient'
        )

        with patch.object(User, 'save') as mock_save:
            Patient.objects.create(
                user=user,
                date_of_birth=date(1990, 1, 1),
                phone_number='+1234567890'
            )
            # User.save should not be called since user_type is already 'patient'
            mock_save.assert_not_called()

    def test_signal_only_on_creation(self):
        """Test that signal only fires on creation, not on update."""
        user = User.objects.create_user(
            email='update_test@example.com',
            password='testpass123',
            first_name='Update',
            last_name='Test',
            user_type='doctor'
        )

        # Create patient
        patient = Patient.objects.create(
            user=user,
            date_of_birth=date(1990, 1, 1),
            phone_number='+1234567890'
        )

        # Change user_type back to doctor manually
        user.user_type = 'doctor'
        user.save()

        # Update patient (not create)
        patient.phone_number = '+9876543210'
        patient.save()

        # User type should still be 'doctor' since signal only fires on creation
        user.refresh_from_db()
        self.assertEqual(user.user_type, 'doctor')
