"""
Unit tests for Google OAuth authentication.

Tests cover:
- Patient registration/login via Google
- Doctor registration/login via Google
- Google account linking
- Error handling for various scenarios
"""

from datetime import date
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import Doctor, Patient, TwoFactorAuth
from apps.users.services.google_auth import GoogleAuthService, GoogleAuthError

User = get_user_model()


class GoogleAuthTestMixin:
    """Mixin providing common Google auth test utilities."""

    def get_mock_google_data(self, **kwargs):
        """Return mock Google user data."""
        return {
            'google_id': kwargs.get('google_id', '123456789'),
            'email': kwargs.get('email', 'testuser@gmail.com'),
            'first_name': kwargs.get('first_name', 'John'),
            'last_name': kwargs.get('last_name', 'Doe'),
            'email_verified': kwargs.get('email_verified', True),
        }


class GooglePatientAuthTestCase(GoogleAuthTestMixin, APITestCase):
    """Test cases for Google patient authentication endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:google-patient-auth')
        self.valid_token = 'valid_google_id_token'
        self.patient_data = {
            'id_token': self.valid_token,
            'date_of_birth': '1990-05-15',
            'phone_number': '+1234567890'
        }

    @patch.object(GoogleAuthService, 'verify_token')
    def test_patient_registration_success(self, mock_verify):
        """Test successful patient registration via Google."""
        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, self.patient_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
        self.assertEqual(response.data['user']['email'], 'testuser@gmail.com')
        self.assertEqual(response.data['user']['user_type'], 'patient')
        self.assertTrue(response.data['user']['is_active'])
        self.assertTrue(response.data['user']['is_verified'])

    @patch.object(GoogleAuthService, 'verify_token')
    def test_patient_registration_creates_profile(self, mock_verify):
        """Test patient registration creates Patient profile."""
        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, self.patient_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='testuser@gmail.com')
        self.assertTrue(hasattr(user, 'patient_profile'))
        self.assertEqual(user.patient_profile.date_of_birth, date(1990, 5, 15))
        self.assertEqual(user.patient_profile.phone_number, '+1234567890')

    @patch.object(GoogleAuthService, 'verify_token')
    def test_patient_registration_sets_google_fields(self, mock_verify):
        """Test patient registration sets Google OAuth fields."""
        mock_verify.return_value = self.get_mock_google_data(google_id='google_123')

        response = self.client.post(self.url, self.patient_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='testuser@gmail.com')
        self.assertEqual(user.google_id, 'google_123')
        self.assertEqual(user.auth_provider, 'google')

    @patch.object(GoogleAuthService, 'verify_token')
    def test_patient_login_success(self, mock_verify):
        """Test successful patient login via Google."""
        # Create existing Google user
        user = User.objects.create_user(
            email='testuser@gmail.com',
            password=None,
            first_name='John',
            last_name='Doe',
            user_type='patient',
            is_active=True,
            is_verified=True,
            google_id='123456789',
            auth_provider='google'
        )
        Patient.objects.create(
            user=user,
            date_of_birth='1990-05-15',
            phone_number='+1234567890'
        )

        mock_verify.return_value = self.get_mock_google_data()

        # Login only requires id_token
        response = self.client.post(self.url, {'id_token': self.valid_token}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)
        self.assertEqual(response.data['message'], 'Login successful')

    @patch.object(GoogleAuthService, 'verify_token')
    def test_patient_login_with_2fa_returns_temp_token(self, mock_verify):
        """Test patient login with 2FA enabled returns temp token."""
        # Create existing Google user with 2FA
        user = User.objects.create_user(
            email='testuser@gmail.com',
            password=None,
            first_name='John',
            last_name='Doe',
            user_type='patient',
            is_active=True,
            is_verified=True,
            is_2fa_enabled=True,
            google_id='123456789',
            auth_provider='google'
        )
        Patient.objects.create(
            user=user,
            date_of_birth='1990-05-15',
            phone_number='+1234567890'
        )
        TwoFactorAuth.create_for_user(user)
        user.two_factor_auth.is_verified = True
        user.two_factor_auth.save()

        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, {'id_token': self.valid_token}, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(response.data['requires_2fa'])
        self.assertIn('temp_token', response.data)

    @patch.object(GoogleAuthService, 'verify_token')
    def test_patient_registration_missing_date_of_birth(self, mock_verify):
        """Test registration fails without date_of_birth for new user."""
        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, {
            'id_token': self.valid_token,
            'phone_number': '+1234567890'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('date_of_birth', response.data)

    @patch.object(GoogleAuthService, 'verify_token')
    def test_patient_registration_missing_phone_number(self, mock_verify):
        """Test registration fails without phone_number for new user."""
        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, {
            'id_token': self.valid_token,
            'date_of_birth': '1990-05-15'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone_number', response.data)

    @patch.object(GoogleAuthService, 'verify_token')
    def test_patient_registration_invalid_phone_number(self, mock_verify):
        """Test registration fails with invalid phone number."""
        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, {
            'id_token': self.valid_token,
            'date_of_birth': '1990-05-15',
            'phone_number': 'invalid'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone_number', response.data)

    @patch.object(GoogleAuthService, 'verify_token')
    def test_existing_email_user_cannot_register_with_google(self, mock_verify):
        """Test user with existing email/password cannot register with Google."""
        # Create existing email/password user
        User.objects.create_user(
            email='testuser@gmail.com',
            password='SecurePass123!',
            first_name='John',
            last_name='Doe',
            user_type='patient',
            is_active=True,
            auth_provider='email'
        )

        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, self.patient_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('id_token', response.data)
        self.assertIn('email already exists', response.data['id_token'][0].lower())

    @patch.object(GoogleAuthService, 'verify_token')
    def test_wrong_user_type_cannot_login_as_patient(self, mock_verify):
        """Test doctor cannot login through patient endpoint."""
        # Create existing Google doctor
        user = User.objects.create_user(
            email='testuser@gmail.com',
            password=None,
            first_name='John',
            last_name='Doe',
            user_type='doctor',
            is_active=True,
            is_verified=True,
            google_id='123456789',
            auth_provider='google'
        )
        Doctor.objects.create(user=user, phone_number='+1234567890')

        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, {'id_token': self.valid_token}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('id_token', response.data)

    @patch.object(GoogleAuthService, 'verify_token')
    def test_invalid_google_token(self, mock_verify):
        """Test invalid Google token returns error."""
        mock_verify.side_effect = GoogleAuthError('Invalid token')

        response = self.client.post(self.url, self.patient_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('id_token', response.data)


class GoogleDoctorAuthTestCase(GoogleAuthTestMixin, APITestCase):
    """Test cases for Google doctor authentication endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:google-doctor-auth')
        self.valid_token = 'valid_google_id_token'
        self.doctor_data = {
            'id_token': self.valid_token,
            'phone_number': '+1234567890'
        }

    @patch.object(GoogleAuthService, 'verify_token')
    def test_doctor_registration_success(self, mock_verify):
        """Test successful doctor registration via Google."""
        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, self.doctor_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('user', response.data)
        self.assertNotIn('tokens', response.data)  # No tokens for new doctors
        self.assertEqual(response.data['user']['user_type'], 'doctor')
        self.assertFalse(response.data['user']['is_active'])  # Pending approval
        self.assertTrue(response.data['user']['is_verified'])

    @patch.object(GoogleAuthService, 'verify_token')
    def test_doctor_registration_creates_profile(self, mock_verify):
        """Test doctor registration creates Doctor profile."""
        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, self.doctor_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='testuser@gmail.com')
        self.assertTrue(hasattr(user, 'doctor_profile'))
        self.assertEqual(user.doctor_profile.phone_number, '+1234567890')

    @patch.object(GoogleAuthService, 'verify_token')
    def test_doctor_login_success(self, mock_verify):
        """Test successful doctor login via Google (approved doctor)."""
        # Create existing approved Google doctor
        user = User.objects.create_user(
            email='testuser@gmail.com',
            password=None,
            first_name='Jane',
            last_name='Smith',
            user_type='doctor',
            is_active=True,  # Approved
            is_verified=True,
            google_id='123456789',
            auth_provider='google'
        )
        Doctor.objects.create(user=user, phone_number='+1234567890')

        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, {'id_token': self.valid_token}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)
        self.assertEqual(response.data['message'], 'Login successful')

    @patch.object(GoogleAuthService, 'verify_token')
    def test_doctor_login_pending_approval(self, mock_verify):
        """Test doctor login fails when pending approval."""
        # Create existing Google doctor pending approval
        user = User.objects.create_user(
            email='testuser@gmail.com',
            password=None,
            first_name='Jane',
            last_name='Smith',
            user_type='doctor',
            is_active=False,  # Pending approval
            is_verified=True,
            google_id='123456789',
            auth_provider='google'
        )
        Doctor.objects.create(user=user, phone_number='+1234567890')

        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, {'id_token': self.valid_token}, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('detail', response.data)
        self.assertIn('pending', response.data['detail'].lower())

    @patch.object(GoogleAuthService, 'verify_token')
    def test_doctor_registration_missing_phone_number(self, mock_verify):
        """Test registration fails without phone_number for new doctor."""
        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, {'id_token': self.valid_token}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone_number', response.data)

    @patch.object(GoogleAuthService, 'verify_token')
    def test_wrong_user_type_cannot_login_as_doctor(self, mock_verify):
        """Test patient cannot login through doctor endpoint."""
        # Create existing Google patient
        user = User.objects.create_user(
            email='testuser@gmail.com',
            password=None,
            first_name='John',
            last_name='Doe',
            user_type='patient',
            is_active=True,
            is_verified=True,
            google_id='123456789',
            auth_provider='google'
        )
        Patient.objects.create(
            user=user,
            date_of_birth='1990-05-15',
            phone_number='+1234567890'
        )

        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, {'id_token': self.valid_token}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('id_token', response.data)


class GoogleLinkAccountTestCase(GoogleAuthTestMixin, APITestCase):
    """Test cases for Google account linking endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:google-link-account')
        self.valid_token = 'valid_google_id_token'
        self.password = 'SecurePass123!'
        self.user = User.objects.create_user(
            email='testuser@gmail.com',
            password=self.password,
            first_name='John',
            last_name='Doe',
            user_type='patient',
            is_active=True,
            is_verified=True,
            auth_provider='email'
        )
        Patient.objects.create(
            user=self.user,
            date_of_birth='1990-05-15',
            phone_number='+1234567890'
        )

    def authenticate_user(self):
        """Helper to authenticate the test user."""
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    @patch.object(GoogleAuthService, 'verify_token')
    def test_link_google_account_success(self, mock_verify):
        """Test successful Google account linking."""
        self.authenticate_user()
        mock_verify.return_value = self.get_mock_google_data(
            email='testuser@gmail.com',
            google_id='google_123'
        )

        response = self.client.post(self.url, {'id_token': self.valid_token}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.google_id, 'google_123')

    @patch.object(GoogleAuthService, 'verify_token')
    def test_link_google_account_requires_auth(self, mock_verify):
        """Test linking requires authentication."""
        mock_verify.return_value = self.get_mock_google_data()

        response = self.client.post(self.url, {'id_token': self.valid_token}, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch.object(GoogleAuthService, 'verify_token')
    def test_cannot_link_already_linked_google_account(self, mock_verify):
        """Test cannot link Google account that's already linked to another user."""
        # Create another user with the Google ID already linked
        other_user = User.objects.create_user(
            email='other@gmail.com',
            password=self.password,
            first_name='Other',
            last_name='User',
            user_type='patient',
            is_active=True,
            google_id='google_123',
            auth_provider='google'
        )

        self.authenticate_user()
        mock_verify.return_value = self.get_mock_google_data(
            email='testuser@gmail.com',
            google_id='google_123'
        )

        response = self.client.post(self.url, {'id_token': self.valid_token}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('id_token', response.data)
        self.assertIn('already linked', response.data['id_token'][0].lower())

    @patch.object(GoogleAuthService, 'verify_token')
    def test_cannot_link_if_already_has_google(self, mock_verify):
        """Test cannot link if user already has a Google account linked."""
        self.user.google_id = 'existing_google_id'
        self.user.save()

        self.authenticate_user()
        mock_verify.return_value = self.get_mock_google_data(
            email='testuser@gmail.com',
            google_id='new_google_123'
        )

        response = self.client.post(self.url, {'id_token': self.valid_token}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('id_token', response.data)

    @patch.object(GoogleAuthService, 'verify_token')
    def test_cannot_link_mismatched_email(self, mock_verify):
        """Test cannot link Google account with different email."""
        self.authenticate_user()
        mock_verify.return_value = self.get_mock_google_data(
            email='different@gmail.com',  # Different email
            google_id='google_123'
        )

        response = self.client.post(self.url, {'id_token': self.valid_token}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('id_token', response.data)
        self.assertIn('does not match', response.data['id_token'][0].lower())


class GoogleAuthServiceTestCase(APITestCase):
    """Test cases for Google auth service."""

    @patch('apps.users.services.google_auth.id_token.verify_oauth2_token')
    @patch('apps.users.services.google_auth.settings')
    def test_verify_token_success(self, mock_settings, mock_verify):
        """Test successful token verification."""
        mock_settings.GOOGLE_CLIENT_ID = 'test_client_id'
        mock_verify.return_value = {
            'iss': 'accounts.google.com',
            'sub': 'google_user_id',
            'email': 'test@gmail.com',
            'given_name': 'John',
            'family_name': 'Doe',
            'email_verified': True,
        }

        result = GoogleAuthService.verify_token('valid_token')

        self.assertEqual(result['google_id'], 'google_user_id')
        self.assertEqual(result['email'], 'test@gmail.com')
        self.assertEqual(result['first_name'], 'John')
        self.assertEqual(result['last_name'], 'Doe')
        self.assertTrue(result['email_verified'])

    @patch('apps.users.services.google_auth.id_token.verify_oauth2_token')
    @patch('apps.users.services.google_auth.settings')
    def test_verify_token_invalid_issuer(self, mock_settings, mock_verify):
        """Test token verification fails with invalid issuer."""
        mock_settings.GOOGLE_CLIENT_ID = 'test_client_id'
        mock_verify.return_value = {
            'iss': 'invalid.issuer.com',
            'sub': 'google_user_id',
            'email': 'test@gmail.com',
            'email_verified': True,
        }

        with self.assertRaises(GoogleAuthError):
            GoogleAuthService.verify_token('valid_token')

    @patch('apps.users.services.google_auth.id_token.verify_oauth2_token')
    @patch('apps.users.services.google_auth.settings')
    def test_verify_token_unverified_email(self, mock_settings, mock_verify):
        """Test token verification fails with unverified email."""
        mock_settings.GOOGLE_CLIENT_ID = 'test_client_id'
        mock_verify.return_value = {
            'iss': 'accounts.google.com',
            'sub': 'google_user_id',
            'email': 'test@gmail.com',
            'email_verified': False,
        }

        with self.assertRaises(GoogleAuthError):
            GoogleAuthService.verify_token('valid_token')

    @patch('apps.users.services.google_auth.settings')
    def test_verify_token_missing_client_id(self, mock_settings):
        """Test token verification fails when client ID not configured."""
        mock_settings.GOOGLE_CLIENT_ID = None

        with self.assertRaises(GoogleAuthError) as context:
            GoogleAuthService.verify_token('valid_token')

        self.assertIn('not configured', str(context.exception).lower())
