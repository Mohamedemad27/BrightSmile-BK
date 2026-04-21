from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import EmailVerificationOTP, Patient

User = get_user_model()


class EmailVerificationOTPModelTestCase(TestCase):
    """Test cases for EmailVerificationOTP model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            user_type='patient'
        )

    def test_generate_otp_returns_6_digits(self):
        """Test that generate_otp returns a 6-digit string."""
        otp = EmailVerificationOTP.generate_otp()

        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

    def test_generate_otp_is_random(self):
        """Test that generate_otp returns different values."""
        otps = [EmailVerificationOTP.generate_otp() for _ in range(100)]
        # Should have at least some variety
        self.assertGreater(len(set(otps)), 50)

    def test_create_for_user_returns_instance_and_plain_otp(self):
        """Test that create_for_user returns both instance and plain OTP."""
        otp_instance, otp_plain = EmailVerificationOTP.create_for_user(self.user)

        self.assertIsInstance(otp_instance, EmailVerificationOTP)
        self.assertEqual(len(otp_plain), 6)
        self.assertTrue(otp_plain.isdigit())

    def test_create_for_user_stores_plain_otp(self):
        """Test that plain OTP is stored for admin visibility."""
        otp_instance, otp_plain = EmailVerificationOTP.create_for_user(self.user)

        self.assertEqual(otp_instance.otp_plain, otp_plain)

    def test_create_for_user_hashes_otp(self):
        """Test that OTP is hashed."""
        otp_instance, otp_plain = EmailVerificationOTP.create_for_user(self.user)

        self.assertNotEqual(otp_instance.otp_hash, otp_plain)
        self.assertGreater(len(otp_instance.otp_hash), 6)

    def test_verify_correct_otp(self):
        """Test that verify returns True for correct OTP."""
        otp_instance, otp_plain = EmailVerificationOTP.create_for_user(self.user)

        self.assertTrue(otp_instance.verify(otp_plain))

    def test_verify_incorrect_otp(self):
        """Test that verify returns False for incorrect OTP."""
        otp_instance, _ = EmailVerificationOTP.create_for_user(self.user)

        self.assertFalse(otp_instance.verify('000000'))

    def test_verify_used_otp(self):
        """Test that verify returns False for used OTP."""
        otp_instance, otp_plain = EmailVerificationOTP.create_for_user(self.user)
        otp_instance.is_used = True
        otp_instance.save()

        self.assertFalse(otp_instance.verify(otp_plain))

    def test_verify_expired_otp(self):
        """Test that verify returns False for expired OTP."""
        otp_instance, otp_plain = EmailVerificationOTP.create_for_user(self.user)
        otp_instance.expires_at = timezone.now() - timedelta(minutes=1)
        otp_instance.save()

        self.assertFalse(otp_instance.verify(otp_plain))

    def test_is_expired_property_false_when_not_expired(self):
        """Test is_expired returns False when OTP is not expired."""
        otp_instance, _ = EmailVerificationOTP.create_for_user(self.user)

        self.assertFalse(otp_instance.is_expired)

    def test_is_expired_property_true_when_expired(self):
        """Test is_expired returns True when OTP is expired."""
        otp_instance, _ = EmailVerificationOTP.create_for_user(self.user)
        otp_instance.expires_at = timezone.now() - timedelta(minutes=1)
        otp_instance.save()

        self.assertTrue(otp_instance.is_expired)

    def test_is_valid_property(self):
        """Test is_valid returns True when not used and not expired."""
        otp_instance, _ = EmailVerificationOTP.create_for_user(self.user)

        self.assertTrue(otp_instance.is_valid)

    def test_is_valid_false_when_used(self):
        """Test is_valid returns False when used."""
        otp_instance, _ = EmailVerificationOTP.create_for_user(self.user)
        otp_instance.is_used = True
        otp_instance.save()

        self.assertFalse(otp_instance.is_valid)

    def test_is_valid_false_when_expired(self):
        """Test is_valid returns False when expired."""
        otp_instance, _ = EmailVerificationOTP.create_for_user(self.user)
        otp_instance.expires_at = timezone.now() - timedelta(minutes=1)
        otp_instance.save()

        self.assertFalse(otp_instance.is_valid)

    @override_settings(OTP_EXPIRY_MINUTES=10)
    def test_expiry_time_configurable(self):
        """Test that OTP expiry time is configurable via settings."""
        otp_instance, _ = EmailVerificationOTP.create_for_user(self.user)

        # Should expire in approximately 10 minutes
        expected_expiry = timezone.now() + timedelta(minutes=10)
        # Allow 5 second tolerance
        self.assertAlmostEqual(
            otp_instance.expires_at.timestamp(),
            expected_expiry.timestamp(),
            delta=5
        )

    def test_str_representation(self):
        """Test string representation of OTP."""
        otp_instance, _ = EmailVerificationOTP.create_for_user(self.user)

        self.assertIn(self.user.email, str(otp_instance))


@override_settings(OTP_EMAILS_SYNC=False)
class RequestOTPViewTestCase(APITestCase):
    """Test cases for request OTP endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:request-otp')
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_verified=False
        )

    @patch('apps.users.views.send_verification_email_task.delay')
    def test_request_otp_success(self, mock_task):
        """Test successful OTP request."""
        response = self.client.post(self.url, {'email': self.user.email}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('email', response.data)

    @patch('apps.users.views.send_verification_email_task.delay')
    def test_request_otp_creates_otp_record(self, mock_task):
        """Test that OTP record is created in database."""
        response = self.client.post(self.url, {'email': self.user.email}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(EmailVerificationOTP.objects.filter(user=self.user).exists())

    @patch('apps.users.views.send_verification_email_task.delay')
    def test_request_otp_triggers_email_task(self, mock_task):
        """Test that Celery task is called to send email."""
        response = self.client.post(self.url, {'email': self.user.email}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_task.assert_called_once()

    def test_request_otp_nonexistent_email(self):
        """Test request OTP with nonexistent email."""
        response = self.client.post(self.url, {'email': 'nonexistent@example.com'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_request_otp_already_verified_user(self):
        """Test request OTP for already verified user."""
        self.user.is_verified = True
        self.user.save()

        response = self.client.post(self.url, {'email': self.user.email}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    @patch('apps.users.views.send_verification_email_task.delay')
    def test_request_otp_cooldown(self, mock_task):
        """Test that user cannot request new OTP until previous expires."""
        # First request
        response = self.client.post(self.url, {'email': self.user.email}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Second request immediately after
        response = self.client.post(self.url, {'email': self.user.email}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    @patch('apps.users.views.send_verification_email_task.delay')
    def test_request_otp_after_expiry(self, mock_task):
        """Test that user can request new OTP after previous expires."""
        # First request
        response = self.client.post(self.url, {'email': self.user.email}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Expire the OTP
        otp = EmailVerificationOTP.objects.get(user=self.user)
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save()

        # Second request after expiry
        response = self.client.post(self.url, {'email': self.user.email}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_request_otp_case_insensitive_email(self):
        """Test that email lookup is case insensitive."""
        with patch('apps.users.views.send_verification_email_task.delay'):
            response = self.client.post(self.url, {'email': 'TEST@EXAMPLE.COM'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_request_otp_invalid_email_format(self):
        """Test request OTP with invalid email format."""
        response = self.client.post(self.url, {'email': 'invalid-email'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_request_otp_no_authentication_required(self):
        """Test that endpoint is publicly accessible."""
        with patch('apps.users.views.send_verification_email_task.delay'):
            response = self.client.post(self.url, {'email': self.user.email}, format='json')

        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class VerifyOTPViewTestCase(APITestCase):
    """Test cases for verify OTP endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:verify-otp')
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_verified=False
        )
        self.otp_instance, self.otp_plain = EmailVerificationOTP.create_for_user(self.user)

    def test_verify_otp_success(self):
        """Test successful OTP verification returns auto-login tokens."""
        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': self.otp_plain
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        # Active user should get tokens
        self.assertIsNotNone(response.data['access'])
        self.assertIsNotNone(response.data['refresh'])

    def test_verify_otp_returns_user_data(self):
        """Test that successful verification returns user data."""
        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': self.otp_plain
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['email'], self.user.email)
        self.assertTrue(response.data['user']['is_verified'])

    def test_verify_otp_marks_user_verified(self):
        """Test that successful verification marks user as verified."""
        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': self.otp_plain
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)

    def test_verify_otp_marks_otp_used(self):
        """Test that successful verification marks OTP as used."""
        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': self.otp_plain
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.otp_instance.refresh_from_db()
        self.assertTrue(self.otp_instance.is_used)

    def test_verify_otp_invalid_otp(self):
        """Test verification with invalid OTP."""
        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': '000000'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('otp', response.data)

    def test_verify_otp_expired(self):
        """Test verification with expired OTP."""
        self.otp_instance.expires_at = timezone.now() - timedelta(minutes=1)
        self.otp_instance.save()

        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': self.otp_plain
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('otp', response.data)

    def test_verify_otp_already_used(self):
        """Test verification with already used OTP."""
        self.otp_instance.is_used = True
        self.otp_instance.save()

        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': self.otp_plain
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('otp', response.data)

    def test_verify_otp_nonexistent_email(self):
        """Test verification with nonexistent email."""
        response = self.client.post(self.url, {
            'email': 'nonexistent@example.com',
            'otp': self.otp_plain
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_verify_otp_already_verified_user(self):
        """Test verification for already verified user."""
        self.user.is_verified = True
        self.user.save()

        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': self.otp_plain
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_otp_non_numeric(self):
        """Test verification with non-numeric OTP."""
        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': 'abcdef'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('otp', response.data)

    def test_verify_otp_wrong_length(self):
        """Test verification with wrong length OTP."""
        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': '123'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_otp_case_insensitive_email(self):
        """Test that email lookup is case insensitive."""
        response = self.client.post(self.url, {
            'email': 'TEST@EXAMPLE.COM',
            'otp': self.otp_plain
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_verify_otp_inactive_user_no_tokens(self):
        """Test that inactive users get verified but don't receive tokens."""
        # Create inactive user (like a doctor pending approval)
        inactive_user = User.objects.create_user(
            email='doctor@example.com',
            password='SecurePass123!',
            first_name='Doctor',
            last_name='Test',
            user_type='doctor',
            is_active=False,
            is_verified=False
        )
        otp_instance, otp_plain = EmailVerificationOTP.create_for_user(inactive_user)

        response = self.client.post(self.url, {
            'email': inactive_user.email,
            'otp': otp_plain
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # User should be verified
        inactive_user.refresh_from_db()
        self.assertTrue(inactive_user.is_verified)
        # But should not receive tokens
        self.assertIsNone(response.data['access'])
        self.assertIsNone(response.data['refresh'])
        self.assertIn('pending approval', response.data['message'])

    def test_verify_otp_uses_latest_otp(self):
        """Test that verification uses the latest OTP."""
        # Create another OTP
        _, new_otp_plain = EmailVerificationOTP.create_for_user(self.user)

        # Old OTP should not work
        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': self.otp_plain
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # New OTP should work
        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': new_otp_plain
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_verify_otp_no_authentication_required(self):
        """Test that endpoint is publicly accessible."""
        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': self.otp_plain
        }, format='json')

        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(OTP_EMAILS_SYNC=False)
class OTPSignalTestCase(APITestCase):
    """Test cases for OTP signals on registration."""

    @patch('apps.users.tasks.send_verification_email_task.delay')
    def test_otp_sent_on_patient_registration(self, mock_task):
        """Test that OTP is sent when patient registers."""
        url = reverse('users:register-patient')
        data = {
            'email': 'newpatient@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'first_name': 'New',
            'last_name': 'Patient',
            'date_of_birth': '1990-05-15',
            'phone_number': '+1234567890',
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_task.assert_called_once()

    @patch('apps.users.tasks.send_verification_email_task.delay')
    def test_otp_created_on_patient_registration(self, mock_task):
        """Test that OTP record is created when patient registers."""
        url = reverse('users:register-patient')
        data = {
            'email': 'newpatient@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'first_name': 'New',
            'last_name': 'Patient',
            'date_of_birth': '1990-05-15',
            'phone_number': '+1234567890',
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email=data['email'])
        self.assertTrue(EmailVerificationOTP.objects.filter(user=user).exists())

    @patch('apps.users.tasks.send_verification_email_task.delay')
    def test_otp_sent_on_doctor_registration(self, mock_task):
        """Test that OTP is sent when doctor registers."""
        url = reverse('users:register-doctor')
        data = {
            'email': 'newdoctor@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'first_name': 'New',
            'last_name': 'Doctor',
            'phone_number': '+1234567890',
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_task.assert_called_once()

    @patch('apps.users.tasks.send_verification_email_task.delay')
    def test_otp_created_on_doctor_registration(self, mock_task):
        """Test that OTP record is created when doctor registers."""
        url = reverse('users:register-doctor')
        data = {
            'email': 'newdoctor@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'first_name': 'New',
            'last_name': 'Doctor',
            'phone_number': '+1234567890',
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email=data['email'])
        self.assertTrue(EmailVerificationOTP.objects.filter(user=user).exists())


class CeleryTaskTestCase(TestCase):
    """Test cases for Celery email task."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            user_type='patient'
        )

    @patch('apps.users.tasks.send_otp_email')
    def test_send_verification_email_task_success(self, mock_send_otp_email):
        """Test that email task sends email successfully."""
        from apps.users.tasks import send_verification_email_task
        mock_send_otp_email.return_value.status_code = 202

        result = send_verification_email_task(self.user.id, '123456')

        self.assertTrue(result)
        mock_send_otp_email.assert_called_once()

    @patch('apps.users.tasks.send_otp_email')
    def test_send_verification_email_task_user_not_found(self, mock_send_otp_email):
        """Test that email task handles nonexistent user."""
        from apps.users.tasks import send_verification_email_task

        result = send_verification_email_task(99999, '123456')

        self.assertFalse(result)
        mock_send_otp_email.assert_not_called()

    @patch('apps.users.tasks.send_otp_email')
    def test_send_verification_email_contains_otp(self, mock_send_otp_email):
        """Test that email contains the OTP code."""
        from apps.users.tasks import send_verification_email_task
        mock_send_otp_email.return_value.status_code = 202

        otp = '123456'
        send_verification_email_task(self.user.id, otp)

        call_args = mock_send_otp_email.call_args
        self.assertEqual(call_args.args[1], otp)

    @patch('apps.users.tasks.send_otp_email')
    def test_send_verification_email_to_correct_recipient(self, mock_send_otp_email):
        """Test that email is sent to correct recipient."""
        from apps.users.tasks import send_verification_email_task
        mock_send_otp_email.return_value.status_code = 202

        send_verification_email_task(self.user.id, '123456')

        call_args = mock_send_otp_email.call_args
        self.assertEqual(call_args.args[0], self.user.email)
