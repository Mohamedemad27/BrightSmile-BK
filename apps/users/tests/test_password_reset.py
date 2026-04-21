"""
Tests for password reset functionality.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import PasswordResetOTP, PasswordResetToken

User = get_user_model()


class PasswordResetOTPModelTestCase(TestCase):
    """Test cases for PasswordResetOTP model."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            user_type='patient'
        )

    def test_create_otp_for_user(self):
        """Test creating OTP for a user."""
        otp_instance, otp_plain = PasswordResetOTP.create_for_user(self.user)

        self.assertEqual(otp_instance.user, self.user)
        self.assertEqual(len(otp_plain), 6)
        self.assertTrue(otp_plain.isdigit())
        self.assertFalse(otp_instance.is_used)
        self.assertIsNotNone(otp_instance.expires_at)

    def test_otp_verify_correct(self):
        """Test OTP verification with correct code."""
        otp_instance, otp_plain = PasswordResetOTP.create_for_user(self.user)

        self.assertTrue(otp_instance.verify(otp_plain))

    def test_otp_verify_incorrect(self):
        """Test OTP verification with incorrect code."""
        otp_instance, otp_plain = PasswordResetOTP.create_for_user(self.user)

        self.assertFalse(otp_instance.verify('000000'))

    def test_otp_is_valid_when_fresh(self):
        """Test OTP is valid when fresh."""
        otp_instance, _ = PasswordResetOTP.create_for_user(self.user)

        self.assertTrue(otp_instance.is_valid)

    def test_otp_is_invalid_when_used(self):
        """Test OTP is invalid when used."""
        otp_instance, _ = PasswordResetOTP.create_for_user(self.user)
        otp_instance.is_used = True
        otp_instance.save()

        self.assertFalse(otp_instance.is_valid)

    def test_otp_is_invalid_when_expired(self):
        """Test OTP is invalid when expired."""
        otp_instance, _ = PasswordResetOTP.create_for_user(self.user)
        otp_instance.expires_at = timezone.now() - timedelta(minutes=1)
        otp_instance.save()

        self.assertTrue(otp_instance.is_expired)
        self.assertFalse(otp_instance.is_valid)

    def test_otp_string_representation(self):
        """Test OTP string representation."""
        otp_instance, _ = PasswordResetOTP.create_for_user(self.user)

        self.assertIn(self.user.email, str(otp_instance))
        self.assertIn('Active', str(otp_instance))


class PasswordResetTokenModelTestCase(TestCase):
    """Test cases for PasswordResetToken model."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            user_type='patient'
        )

    def test_create_token_for_user(self):
        """Test creating token for a user."""
        token = PasswordResetToken.create_for_user(self.user)

        self.assertEqual(token.user, self.user)
        self.assertEqual(len(token.token), 64)
        self.assertFalse(token.is_used)
        self.assertIsNotNone(token.expires_at)

    def test_token_is_valid_when_fresh(self):
        """Test token is valid when fresh."""
        token = PasswordResetToken.create_for_user(self.user)

        self.assertTrue(token.is_valid)

    def test_token_is_invalid_when_used(self):
        """Test token is invalid when used."""
        token = PasswordResetToken.create_for_user(self.user)
        token.mark_used()

        self.assertFalse(token.is_valid)

    def test_token_is_invalid_when_expired(self):
        """Test token is invalid when expired."""
        token = PasswordResetToken.create_for_user(self.user)
        token.expires_at = timezone.now() - timedelta(minutes=1)
        token.save()

        self.assertTrue(token.is_expired)
        self.assertFalse(token.is_valid)

    def test_verify_token(self):
        """Test verifying a valid token."""
        token = PasswordResetToken.create_for_user(self.user)

        user = PasswordResetToken.verify_token(token.token)
        self.assertEqual(user, self.user)

    def test_verify_invalid_token(self):
        """Test verifying an invalid token."""
        user = PasswordResetToken.verify_token('invalid_token')
        self.assertIsNone(user)

    def test_get_and_invalidate(self):
        """Test getting user and invalidating token."""
        token = PasswordResetToken.create_for_user(self.user)
        token_str = token.token

        user = PasswordResetToken.get_and_invalidate(token_str)
        self.assertEqual(user, self.user)

        # Token should now be invalid
        token.refresh_from_db()
        self.assertTrue(token.is_used)

    def test_create_token_invalidates_existing(self):
        """Test creating new token invalidates existing tokens."""
        old_token = PasswordResetToken.create_for_user(self.user)
        new_token = PasswordResetToken.create_for_user(self.user)

        old_token.refresh_from_db()
        self.assertTrue(old_token.is_used)
        self.assertFalse(new_token.is_used)

    def test_token_string_representation(self):
        """Test token string representation."""
        token = PasswordResetToken.create_for_user(self.user)

        self.assertIn(self.user.email, str(token))
        self.assertIn('Active', str(token))


@override_settings(OTP_EMAILS_SYNC=False)
class PasswordResetRequestViewTestCase(APITestCase):
    """Test cases for password reset request endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_verified=True
        )
        self.url = reverse('users:password-reset-request')

    @patch('apps.users.views.send_password_reset_email_task.delay')
    def test_request_password_reset_success(self, mock_task):
        """Test successful password reset request."""
        response = self.client.post(self.url, {'email': self.user.email})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('email', response.data)
        mock_task.assert_called_once()

    def test_request_password_reset_invalid_email(self):
        """Test password reset request with non-existent email."""
        response = self.client.post(self.url, {'email': 'nonexistent@example.com'})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    @patch('apps.users.views.send_password_reset_email_task.delay')
    def test_request_password_reset_cooldown(self, mock_task):
        """Test password reset request respects cooldown."""
        # First request
        response = self.client.post(self.url, {'email': self.user.email})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Second request should be rate limited
        response = self.client.post(self.url, {'email': self.user.email})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('recently sent', str(response.data))

    def test_request_password_reset_missing_email(self):
        """Test password reset request with missing email."""
        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.users.views.send_password_reset_email_task.delay')
    def test_request_password_reset_case_insensitive(self, mock_task):
        """Test password reset request is case insensitive."""
        response = self.client.post(self.url, {'email': self.user.email.upper()})

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PasswordResetVerifyViewTestCase(APITestCase):
    """Test cases for password reset OTP verification endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_verified=True
        )
        self.url = reverse('users:password-reset-verify')

    def test_verify_otp_success(self):
        """Test successful OTP verification."""
        otp_instance, otp_plain = PasswordResetOTP.create_for_user(self.user)

        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': otp_plain
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('reset_token', response.data)
        self.assertEqual(len(response.data['reset_token']), 64)

        # OTP should be marked as used
        otp_instance.refresh_from_db()
        self.assertTrue(otp_instance.is_used)

    def test_verify_otp_invalid_code(self):
        """Test OTP verification with invalid code."""
        PasswordResetOTP.create_for_user(self.user)

        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': '000000'
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('otp', response.data)

    def test_verify_otp_expired(self):
        """Test OTP verification with expired code."""
        otp_instance, otp_plain = PasswordResetOTP.create_for_user(self.user)
        otp_instance.expires_at = timezone.now() - timedelta(minutes=1)
        otp_instance.save()

        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': otp_plain
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_otp_already_used(self):
        """Test OTP verification with already used code."""
        otp_instance, otp_plain = PasswordResetOTP.create_for_user(self.user)
        otp_instance.is_used = True
        otp_instance.save()

        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': otp_plain
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_otp_no_otp_found(self):
        """Test OTP verification when no OTP exists."""
        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': '123456'
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_otp_invalid_email(self):
        """Test OTP verification with non-existent email."""
        response = self.client.post(self.url, {
            'email': 'nonexistent@example.com',
            'otp': '123456'
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_otp_invalid_format(self):
        """Test OTP verification with invalid format."""
        response = self.client.post(self.url, {
            'email': self.user.email,
            'otp': 'abcdef'
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmViewTestCase(APITestCase):
    """Test cases for password reset confirmation endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_verified=True
        )
        self.url = reverse('users:password-reset-confirm')

    def _create_token(self):
        """Create a fresh password reset token."""
        return PasswordResetToken.create_for_user(self.user)

    def test_reset_password_success(self):
        """Test successful password reset."""
        token = self._create_token()
        new_password = 'NewSecurePass123!'
        response = self.client.post(
            self.url,
            {
                'new_password': new_password,
                'new_password_confirm': new_password
            },
            HTTP_AUTHORIZATION=f'Bearer {token.token}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    def test_reset_password_without_token(self):
        """Test password reset without token."""
        response = self.client.post(self.url, {
            'new_password': 'NewSecurePass123!',
            'new_password_confirm': 'NewSecurePass123!'
        })

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reset_password_invalid_token(self):
        """Test password reset with invalid token."""
        response = self.client.post(
            self.url,
            {
                'new_password': 'NewSecurePass123!',
                'new_password_confirm': 'NewSecurePass123!'
            },
            HTTP_AUTHORIZATION='Bearer invalid_token'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reset_password_expired_token(self):
        """Test password reset with expired token."""
        token = self._create_token()
        token.expires_at = timezone.now() - timedelta(minutes=1)
        token.save()

        response = self.client.post(
            self.url,
            {
                'new_password': 'NewSecurePass123!',
                'new_password_confirm': 'NewSecurePass123!'
            },
            HTTP_AUTHORIZATION=f'Bearer {token.token}'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reset_password_used_token(self):
        """Test password reset with already used token."""
        token = self._create_token()
        token.is_used = True
        token.save()

        response = self.client.post(
            self.url,
            {
                'new_password': 'NewSecurePass123!',
                'new_password_confirm': 'NewSecurePass123!'
            },
            HTTP_AUTHORIZATION=f'Bearer {token.token}'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reset_password_mismatch(self):
        """Test password reset with mismatched passwords."""
        token = self._create_token()
        response = self.client.post(
            self.url,
            {
                'new_password': 'NewSecurePass123!',
                'new_password_confirm': 'DifferentPass123!'
            },
            HTTP_AUTHORIZATION=f'Bearer {token.token}'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password_confirm', response.data)

    def test_reset_password_weak_password(self):
        """Test password reset with weak password."""
        token = self._create_token()
        response = self.client.post(
            self.url,
            {
                'new_password': '12345',
                'new_password_confirm': '12345'
            },
            HTTP_AUTHORIZATION=f'Bearer {token.token}'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)

    def test_reset_password_token_invalidated_after_use(self):
        """Test that token is invalidated after successful password reset."""
        token = self._create_token()
        token_str = token.token
        new_password = 'NewSecurePass123!'
        response = self.client.post(
            self.url,
            {
                'new_password': new_password,
                'new_password_confirm': new_password
            },
            HTTP_AUTHORIZATION=f'Bearer {token_str}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Try to use the same token again
        response = self.client.post(
            self.url,
            {
                'new_password': 'AnotherPass123!',
                'new_password_confirm': 'AnotherPass123!'
            },
            HTTP_AUTHORIZATION=f'Bearer {token_str}'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(OTP_EMAILS_SYNC=False)
class PasswordResetIntegrationTestCase(APITestCase):
    """Integration tests for the complete password reset flow."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='oldpassword123',
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_verified=True
        )
        self.request_url = reverse('users:password-reset-request')
        self.verify_url = reverse('users:password-reset-verify')
        self.confirm_url = reverse('users:password-reset-confirm')

    @patch('apps.users.views.send_password_reset_email_task.delay')
    def test_complete_password_reset_flow(self, mock_task):
        """Test the complete password reset flow."""
        # Step 1: Request password reset
        response = self.client.post(self.request_url, {'email': self.user.email})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get the OTP from the database (in real scenario, user gets this via email)
        otp = PasswordResetOTP.objects.filter(user=self.user, is_used=False).first()
        self.assertIsNotNone(otp)

        # Step 2: Verify OTP
        response = self.client.post(self.verify_url, {
            'email': self.user.email,
            'otp': otp.otp_plain
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        reset_token = response.data['reset_token']

        # Step 3: Reset password
        new_password = 'NewSecurePassword123!'
        response = self.client.post(
            self.confirm_url,
            {
                'new_password': new_password,
                'new_password_confirm': new_password
            },
            HTTP_AUTHORIZATION=f'Bearer {reset_token}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify user can login with new password
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(self.user.check_password('oldpassword123'))

    @patch('apps.users.views.send_password_reset_email_task.delay')
    def test_password_reset_flow_with_multiple_otps(self, mock_task):
        """Test that only the latest OTP works."""
        # Request first OTP
        self.client.post(self.request_url, {'email': self.user.email})
        first_otp = PasswordResetOTP.objects.filter(user=self.user).first()

        # Manually expire the first OTP to allow requesting new one
        first_otp.expires_at = timezone.now() - timedelta(minutes=1)
        first_otp.save()

        # Request second OTP
        self.client.post(self.request_url, {'email': self.user.email})
        second_otp = PasswordResetOTP.objects.filter(
            user=self.user,
            is_used=False
        ).exclude(pk=first_otp.pk).first()

        # Verify only the second (latest valid) OTP works
        response = self.client.post(self.verify_url, {
            'email': self.user.email,
            'otp': second_otp.otp_plain
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
