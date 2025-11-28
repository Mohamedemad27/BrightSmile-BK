from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import Doctor, Patient

User = get_user_model()


class PatientRegistrationTestCase(APITestCase):
    """Test cases for patient registration endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:register-patient')
        self.valid_data = {
            'email': 'newpatient@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'first_name': 'John',
            'last_name': 'Doe',
            'date_of_birth': '1990-05-15',
            'phone_number': '+1234567890',
        }

    def test_patient_registration_success(self):
        """Test successful patient registration."""
        response = self.client.post(self.url, self.valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['email'], self.valid_data['email'])
        self.assertEqual(response.data['user']['user_type'], 'patient')

    def test_patient_is_active_after_registration(self):
        """Test that patient is active after registration."""
        response = self.client.post(self.url, self.valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['user']['is_active'])

    def test_patient_is_not_verified_after_registration(self):
        """Test that patient is not verified after registration."""
        response = self.client.post(self.url, self.valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['user']['is_verified'])

    def test_patient_profile_created(self):
        """Test that patient profile is created with registration."""
        response = self.client.post(self.url, self.valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email=self.valid_data['email'])
        self.assertTrue(hasattr(user, 'patient_profile'))
        self.assertEqual(user.patient_profile.phone_number, self.valid_data['phone_number'])
        self.assertEqual(str(user.patient_profile.date_of_birth), self.valid_data['date_of_birth'])

    def test_patient_registration_duplicate_email(self):
        """Test that duplicate email returns error."""
        # Create existing user
        User.objects.create_user(
            email=self.valid_data['email'],
            password='existingpass123',
            first_name='Existing',
            last_name='User',
            user_type='patient'
        )

        response = self.client.post(self.url, self.valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_patient_registration_duplicate_email_case_insensitive(self):
        """Test that email uniqueness check is case insensitive."""
        # Create existing user with lowercase email
        User.objects.create_user(
            email='newpatient@example.com',
            password='existingpass123',
            first_name='Existing',
            last_name='User',
            user_type='patient'
        )

        # Try to register with uppercase email
        data = self.valid_data.copy()
        data['email'] = 'NEWPATIENT@EXAMPLE.COM'

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_patient_registration_password_mismatch(self):
        """Test that mismatched passwords return error."""
        data = self.valid_data.copy()
        data['password_confirm'] = 'DifferentPass123!'

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_confirm', response.data)

    def test_patient_registration_weak_password(self):
        """Test that weak password returns error."""
        data = self.valid_data.copy()
        data['password'] = '123'
        data['password_confirm'] = '123'

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_patient_registration_common_password(self):
        """Test that common password returns error."""
        data = self.valid_data.copy()
        data['password'] = 'password123'
        data['password_confirm'] = 'password123'

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_patient_registration_invalid_phone_number(self):
        """Test that invalid phone number returns error."""
        data = self.valid_data.copy()
        data['phone_number'] = 'invalid-phone'

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone_number', response.data)

    def test_patient_registration_future_date_of_birth(self):
        """Test that future date of birth returns error."""
        data = self.valid_data.copy()
        future_date = date.today() + timedelta(days=1)
        data['date_of_birth'] = future_date.isoformat()

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('date_of_birth', response.data)

    def test_patient_registration_missing_required_fields(self):
        """Test that missing required fields return errors."""
        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)
        self.assertIn('password', response.data)
        self.assertIn('first_name', response.data)
        self.assertIn('last_name', response.data)
        self.assertIn('date_of_birth', response.data)
        self.assertIn('phone_number', response.data)

    def test_patient_registration_invalid_email_format(self):
        """Test that invalid email format returns error."""
        data = self.valid_data.copy()
        data['email'] = 'not-an-email'

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_patient_registration_no_authentication_required(self):
        """Test that registration endpoint is publicly accessible."""
        # No authentication headers set
        response = self.client.post(self.url, self.valid_data, format='json')

        # Should not return 401 or 403
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DoctorRegistrationTestCase(APITestCase):
    """Test cases for doctor registration endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:register-doctor')
        self.valid_data = {
            'email': 'newdoctor@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'phone_number': '+1987654321',
        }

    def test_doctor_registration_success(self):
        """Test successful doctor registration."""
        response = self.client.post(self.url, self.valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['email'], self.valid_data['email'])
        self.assertEqual(response.data['user']['user_type'], 'doctor')

    def test_doctor_is_not_active_after_registration(self):
        """Test that doctor is NOT active after registration (requires admin approval)."""
        response = self.client.post(self.url, self.valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['user']['is_active'])

    def test_doctor_is_not_verified_after_registration(self):
        """Test that doctor is not verified after registration."""
        response = self.client.post(self.url, self.valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['user']['is_verified'])

    def test_doctor_profile_created(self):
        """Test that doctor profile is created with registration."""
        response = self.client.post(self.url, self.valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email=self.valid_data['email'])
        self.assertTrue(hasattr(user, 'doctor_profile'))
        self.assertEqual(user.doctor_profile.phone_number, self.valid_data['phone_number'])

    def test_doctor_registration_duplicate_email(self):
        """Test that duplicate email returns error."""
        # Create existing user
        User.objects.create_user(
            email=self.valid_data['email'],
            password='existingpass123',
            first_name='Existing',
            last_name='User',
            user_type='doctor'
        )

        response = self.client.post(self.url, self.valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_doctor_registration_password_mismatch(self):
        """Test that mismatched passwords return error."""
        data = self.valid_data.copy()
        data['password_confirm'] = 'DifferentPass123!'

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_confirm', response.data)

    def test_doctor_registration_weak_password(self):
        """Test that weak password returns error."""
        data = self.valid_data.copy()
        data['password'] = '123'
        data['password_confirm'] = '123'

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_doctor_registration_invalid_phone_number(self):
        """Test that invalid phone number returns error."""
        data = self.valid_data.copy()
        data['phone_number'] = 'invalid-phone'

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone_number', response.data)

    def test_doctor_registration_missing_required_fields(self):
        """Test that missing required fields return errors."""
        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)
        self.assertIn('password', response.data)
        self.assertIn('first_name', response.data)
        self.assertIn('last_name', response.data)
        self.assertIn('phone_number', response.data)

    def test_doctor_registration_no_authentication_required(self):
        """Test that registration endpoint is publicly accessible."""
        # No authentication headers set
        response = self.client.post(self.url, self.valid_data, format='json')

        # Should not return 401 or 403
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_approval_message_in_response(self):
        """Test that response includes message about pending approval."""
        response = self.client.post(self.url, self.valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('pending', response.data['message'].lower())


class RegistrationEdgeCasesTestCase(APITestCase):
    """Test edge cases for registration endpoints."""

    def test_patient_and_doctor_cannot_share_email(self):
        """Test that patient and doctor cannot register with same email."""
        patient_url = reverse('users:register-patient')
        doctor_url = reverse('users:register-doctor')

        # Register patient first
        patient_data = {
            'email': 'shared@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'first_name': 'Patient',
            'last_name': 'User',
            'date_of_birth': '1990-01-01',
            'phone_number': '+1234567890',
        }
        response = self.client.post(patient_url, patient_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Try to register doctor with same email
        doctor_data = {
            'email': 'shared@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'first_name': 'Doctor',
            'last_name': 'User',
            'phone_number': '+1987654321',
        }
        response = self.client.post(doctor_url, doctor_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_email_is_normalized_lowercase(self):
        """Test that email is stored in lowercase."""
        url = reverse('users:register-patient')
        data = {
            'email': 'UPPERCASE@EXAMPLE.COM',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'first_name': 'Test',
            'last_name': 'User',
            'date_of_birth': '1990-01-01',
            'phone_number': '+1234567890',
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(id=response.data['user']['id'])
        self.assertEqual(user.email, 'uppercase@example.com')

    def test_user_type_is_set_correctly_for_patient(self):
        """Test that user_type is correctly set to 'patient' for patient registration."""
        url = reverse('users:register-patient')
        data = {
            'email': 'patient@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'first_name': 'Test',
            'last_name': 'Patient',
            'date_of_birth': '1990-01-01',
            'phone_number': '+1234567890',
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(id=response.data['user']['id'])
        self.assertEqual(user.user_type, 'patient')

    def test_user_type_is_set_correctly_for_doctor(self):
        """Test that user_type is correctly set to 'doctor' for doctor registration."""
        url = reverse('users:register-doctor')
        data = {
            'email': 'doctor@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'first_name': 'Test',
            'last_name': 'Doctor',
            'phone_number': '+1234567890',
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(id=response.data['user']['id'])
        self.assertEqual(user.user_type, 'doctor')

    def test_password_is_hashed(self):
        """Test that password is properly hashed and not stored in plain text."""
        url = reverse('users:register-patient')
        password = 'SecurePass123!'
        data = {
            'email': 'hashtest@example.com',
            'password': password,
            'password_confirm': password,
            'first_name': 'Test',
            'last_name': 'User',
            'date_of_birth': '1990-01-01',
            'phone_number': '+1234567890',
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(id=response.data['user']['id'])
        # Password should not be stored as plain text
        self.assertNotEqual(user.password, password)
        # But should validate correctly
        self.assertTrue(user.check_password(password))
