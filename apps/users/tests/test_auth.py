from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
import pyotp

from apps.users.models import BackupCode, TwoFactorAuth, TwoFactorToken

User = get_user_model()


class LoginTestCase(APITestCase):
    """Test cases for login endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:login')
        self.password = 'SecurePass123!'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password=self.password,
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True,
            is_verified=True
        )

    def test_login_success(self):
        """Test successful login returns tokens."""
        response = self.client.post(self.url, {
            'email': self.user.email,
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)

    def test_login_returns_user_data(self):
        """Test login returns correct user data."""
        response = self.client.post(self.url, {
            'email': self.user.email,
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['email'], self.user.email)
        self.assertEqual(response.data['user']['first_name'], self.user.first_name)
        self.assertEqual(response.data['user']['user_type'], 'patient')

    def test_login_updates_last_login(self):
        """Test login updates last_login timestamp."""
        self.assertIsNone(self.user.last_login)

        response = self.client.post(self.url, {
            'email': self.user.email,
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)

    def test_login_invalid_email(self):
        """Test login with non-existent email."""
        response = self.client.post(self.url, {
            'email': 'nonexistent@example.com',
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)

    def test_login_invalid_password(self):
        """Test login with wrong password."""
        response = self.client.post(self.url, {
            'email': self.user.email,
            'password': 'wrongpassword'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)

    def test_login_inactive_user(self):
        """Test login with inactive user account."""
        self.user.is_active = False
        self.user.save()

        response = self.client.post(self.url, {
            'email': self.user.email,
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        detail = response.data['detail']
        if isinstance(detail, list):
            detail = detail[0]
        self.assertIn('not active', detail.lower())

    def test_login_case_insensitive_email(self):
        """Test login with different email case."""
        response = self.client.post(self.url, {
            'email': 'TESTUSER@EXAMPLE.COM',
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_login_missing_email(self):
        """Test login without email."""
        response = self.client.post(self.url, {
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_login_missing_password(self):
        """Test login without password."""
        response = self.client.post(self.url, {
            'email': self.user.email
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_login_empty_body(self):
        """Test login with empty request body."""
        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_doctor_inactive(self):
        """Test that inactive doctor cannot login."""
        doctor = User.objects.create_user(
            email='doctor@example.com',
            password=self.password,
            first_name='Test',
            last_name='Doctor',
            user_type='doctor',
            is_active=False,  # Pending admin approval
            is_verified=False
        )

        response = self.client.post(self.url, {
            'email': doctor.email,
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        detail = response.data['detail']
        if isinstance(detail, list):
            detail = detail[0]
        self.assertIn('not active', detail.lower())

    def test_login_no_authentication_required(self):
        """Test that login endpoint is publicly accessible."""
        response = self.client.post(self.url, {
            'email': self.user.email,
            'password': self.password
        }, format='json')

        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TokenRefreshTestCase(APITestCase):
    """Test cases for token refresh endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:token-refresh')
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password='SecurePass123!',
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True
        )
        self.refresh_token = RefreshToken.for_user(self.user)

    def test_token_refresh_success(self):
        """Test successful token refresh."""
        response = self.client.post(self.url, {
            'refresh': str(self.refresh_token)
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_token_refresh_returns_new_refresh(self):
        """Test that refresh returns new refresh token (rotation)."""
        response = self.client.post(self.url, {
            'refresh': str(self.refresh_token)
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('refresh', response.data)

    def test_token_refresh_invalid_token(self):
        """Test refresh with invalid token."""
        response = self.client.post(self.url, {
            'refresh': 'invalid-token'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_missing_token(self):
        """Test refresh without token."""
        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('refresh', response.data)

    def test_token_refresh_no_authentication_required(self):
        """Test that refresh endpoint is publicly accessible."""
        response = self.client.post(self.url, {
            'refresh': str(self.refresh_token)
        }, format='json')

        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class LogoutTestCase(APITestCase):
    """Test cases for logout endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:logout')
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password='SecurePass123!',
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True
        )
        self.refresh_token = RefreshToken.for_user(self.user)
        self.access_token = self.refresh_token.access_token

    def test_logout_success(self):
        """Test successful logout."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'refresh': str(self.refresh_token)
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

    def test_logout_blacklists_token(self):
        """Test that logout blacklists the refresh token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'refresh': str(self.refresh_token)
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Try to use the blacklisted token for refresh
        refresh_url = reverse('users:token-refresh')
        response = self.client.post(refresh_url, {
            'refresh': str(self.refresh_token)
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_authentication(self):
        """Test that logout requires authentication."""
        response = self.client.post(self.url, {
            'refresh': str(self.refresh_token)
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_invalid_token(self):
        """Test logout with invalid refresh token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'refresh': 'invalid-token'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_missing_token(self):
        """Test logout without refresh token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('refresh', response.data)


class JWTAuthenticationTestCase(APITestCase):
    """Test cases for JWT authentication on protected endpoints."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password='SecurePass123!',
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True
        )
        self.refresh_token = RefreshToken.for_user(self.user)
        self.access_token = self.refresh_token.access_token

    def test_access_protected_endpoint_with_token(self):
        """Test accessing protected endpoint with valid token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        # Logout is a protected endpoint
        url = reverse('users:logout')
        response = self.client.post(url, {
            'refresh': str(self.refresh_token)
        }, format='json')

        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_protected_endpoint_without_token(self):
        """Test accessing protected endpoint without token."""
        url = reverse('users:logout')
        response = self.client.post(url, {
            'refresh': str(self.refresh_token)
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_protected_endpoint_invalid_token(self):
        """Test accessing protected endpoint with invalid token."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')

        url = reverse('users:logout')
        response = self.client.post(url, {
            'refresh': str(self.refresh_token)
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_protected_endpoint_wrong_auth_type(self):
        """Test accessing protected endpoint with wrong auth type."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.access_token}')

        url = reverse('users:logout')
        response = self.client.post(url, {
            'refresh': str(self.refresh_token)
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LoginSerializerTestCase(APITestCase):
    """Test cases for login serializer validation."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:login')
        self.password = 'SecurePass123!'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password=self.password,
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True
        )

    def test_login_normalizes_email(self):
        """Test that email is normalized to lowercase."""
        response = self.client.post(self.url, {
            'email': '  TESTUSER@EXAMPLE.COM  ',
            'password': self.password
        }, format='json')

        # Should still work with extra spaces and uppercase
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_error_message_not_reveal_user_existence(self):
        """Test that error message doesn't reveal whether user exists."""
        # Wrong email
        response1 = self.client.post(self.url, {
            'email': 'wrong@example.com',
            'password': self.password
        }, format='json')

        # Wrong password
        response2 = self.client.post(self.url, {
            'email': self.user.email,
            'password': 'wrongpassword'
        }, format='json')

        # Both should return the same generic error
        self.assertEqual(response1.data['detail'], response2.data['detail'])


class FullAuthFlowTestCase(APITestCase):
    """Test cases for complete authentication flow."""

    def setUp(self):
        """Set up test data."""
        self.password = 'SecurePass123!'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password=self.password,
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True
        )

    def test_full_auth_flow(self):
        """Test complete flow: login -> use token -> refresh -> logout."""
        # Step 1: Login
        login_url = reverse('users:login')
        login_response = self.client.post(login_url, {
            'email': self.user.email,
            'password': self.password
        }, format='json')

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        access_token = login_response.data['access']
        refresh_token = login_response.data['refresh']

        # Step 2: Use access token on protected endpoint
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_url = reverse('users:logout')

        # Step 3: Refresh token
        refresh_url = reverse('users:token-refresh')
        self.client.credentials()  # Clear credentials
        refresh_response = self.client.post(refresh_url, {
            'refresh': refresh_token
        }, format='json')

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        new_access_token = refresh_response.data['access']
        new_refresh_token = refresh_response.data['refresh']

        # Step 4: Logout with new tokens
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_access_token}')
        logout_response = self.client.post(logout_url, {
            'refresh': new_refresh_token
        }, format='json')

        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        # Step 5: Verify refresh token is blacklisted
        self.client.credentials()
        refresh_response = self.client.post(refresh_url, {
            'refresh': new_refresh_token
        }, format='json')

        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unverified_user_can_login(self):
        """Test that unverified users can still login."""
        self.user.is_verified = False
        self.user.save()

        login_url = reverse('users:login')
        response = self.client.post(login_url, {
            'email': self.user.email,
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['user']['is_verified'])


class ChangePasswordTestCase(APITestCase):
    """Test cases for change password endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:change-password')
        self.current_password = 'CurrentPass123!'
        self.new_password = 'NewSecurePass456!'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password=self.current_password,
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True
        )
        self.refresh_token = RefreshToken.for_user(self.user)
        self.access_token = self.refresh_token.access_token

    def test_change_password_success(self):
        """Test successful password change."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'current_password': self.current_password,
            'new_password': self.new_password,
            'new_password_confirm': self.new_password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

    def test_change_password_updates_password(self):
        """Test that password is actually updated."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'current_password': self.current_password,
            'new_password': self.new_password,
            'new_password_confirm': self.new_password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify old password no longer works
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password(self.current_password))

        # Verify new password works
        self.assertTrue(self.user.check_password(self.new_password))

    def test_change_password_wrong_current_password(self):
        """Test change password with wrong current password."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'current_password': 'WrongPassword123!',
            'new_password': self.new_password,
            'new_password_confirm': self.new_password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('current_password', response.data)

    def test_change_password_weak_new_password(self):
        """Test change password with weak new password."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'current_password': self.current_password,
            'new_password': '123',
            'new_password_confirm': '123'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)

    def test_change_password_common_password(self):
        """Test change password with common password."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'current_password': self.current_password,
            'new_password': 'password123',
            'new_password_confirm': 'password123'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)

    def test_change_password_mismatch(self):
        """Test change password with mismatched new passwords."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'current_password': self.current_password,
            'new_password': self.new_password,
            'new_password_confirm': 'DifferentPassword456!'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password_confirm', response.data)

    def test_change_password_same_as_current(self):
        """Test change password with new password same as current."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'current_password': self.current_password,
            'new_password': self.current_password,
            'new_password_confirm': self.current_password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)

    def test_change_password_requires_authentication(self):
        """Test that change password requires authentication."""
        response = self.client.post(self.url, {
            'current_password': self.current_password,
            'new_password': self.new_password,
            'new_password_confirm': self.new_password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_missing_current_password(self):
        """Test change password without current password."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'new_password': self.new_password,
            'new_password_confirm': self.new_password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('current_password', response.data)

    def test_change_password_missing_new_password(self):
        """Test change password without new password."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'current_password': self.current_password,
            'new_password_confirm': self.new_password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)

    def test_change_password_missing_confirm(self):
        """Test change password without confirmation."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'current_password': self.current_password,
            'new_password': self.new_password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password_confirm', response.data)

    def test_change_password_empty_body(self):
        """Test change password with empty request body."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_can_login_with_new_password_after_change(self):
        """Test that user can login with new password after change."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        # Change password
        response = self.client.post(self.url, {
            'current_password': self.current_password,
            'new_password': self.new_password,
            'new_password_confirm': self.new_password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Clear credentials and try to login with new password
        self.client.credentials()
        login_url = reverse('users:login')
        login_response = self.client.post(login_url, {
            'email': self.user.email,
            'password': self.new_password
        }, format='json')

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', login_response.data)


# ============================================================================
# Two-Factor Authentication Tests
# ============================================================================

class TwoFactorSetupTestCase(APITestCase):
    """Test cases for 2FA setup endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:2fa-setup')
        self.password = 'SecurePass123!'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password=self.password,
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True
        )
        self.refresh_token = RefreshToken.for_user(self.user)
        self.access_token = self.refresh_token.access_token

    def test_setup_2fa_success(self):
        """Test successful 2FA setup initiation."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('secret', response.data)
        self.assertIn('qr_code', response.data)
        self.assertIn('provisioning_uri', response.data)

    def test_setup_2fa_creates_record(self):
        """Test that 2FA setup creates a TwoFactorAuth record."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(TwoFactorAuth.objects.filter(user=self.user).exists())
        two_factor = TwoFactorAuth.objects.get(user=self.user)
        self.assertFalse(two_factor.is_verified)

    def test_setup_2fa_requires_authentication(self):
        """Test that 2FA setup requires authentication."""
        response = self.client.post(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_setup_2fa_already_enabled(self):
        """Test that 2FA setup fails if already enabled."""
        self.user.is_2fa_enabled = True
        self.user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)

    def test_setup_2fa_returns_valid_secret(self):
        """Test that returned secret is valid TOTP secret."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Try to create TOTP with the secret
        totp = pyotp.TOTP(response.data['secret'])
        code = totp.now()
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())


class TwoFactorVerifySetupTestCase(APITestCase):
    """Test cases for 2FA verify setup endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:2fa-verify-setup')
        self.password = 'SecurePass123!'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password=self.password,
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True
        )
        self.refresh_token = RefreshToken.for_user(self.user)
        self.access_token = self.refresh_token.access_token
        # Create 2FA setup
        self.two_factor = TwoFactorAuth.create_for_user(self.user)

    def test_verify_setup_success(self):
        """Test successful 2FA verification."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        totp = pyotp.TOTP(self.two_factor.secret)

        response = self.client.post(self.url, {
            'code': totp.now()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('backup_codes', response.data)
        self.assertEqual(len(response.data['backup_codes']), 10)

    def test_verify_setup_enables_2fa(self):
        """Test that verification enables 2FA on user."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        totp = pyotp.TOTP(self.two_factor.secret)

        response = self.client.post(self.url, {
            'code': totp.now()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_2fa_enabled)
        self.two_factor.refresh_from_db()
        self.assertTrue(self.two_factor.is_verified)

    def test_verify_setup_invalid_code(self):
        """Test verification with invalid code."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'code': '000000'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data)

    def test_verify_setup_no_setup(self):
        """Test verification without prior setup."""
        self.two_factor.delete()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'code': '123456'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)

    def test_verify_setup_already_verified(self):
        """Test verification when already verified."""
        self.two_factor.is_verified = True
        self.two_factor.save()
        self.user.is_2fa_enabled = True
        self.user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        totp = pyotp.TOTP(self.two_factor.secret)

        response = self.client.post(self.url, {
            'code': totp.now()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)

    def test_verify_setup_requires_authentication(self):
        """Test that verification requires authentication."""
        response = self.client.post(self.url, {
            'code': '123456'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TwoFactorDisableTestCase(APITestCase):
    """Test cases for 2FA disable endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:2fa-disable')
        self.password = 'SecurePass123!'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password=self.password,
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True,
            is_2fa_enabled=True
        )
        self.refresh_token = RefreshToken.for_user(self.user)
        self.access_token = self.refresh_token.access_token
        # Create verified 2FA
        self.two_factor = TwoFactorAuth.create_for_user(self.user)
        self.two_factor.is_verified = True
        self.two_factor.save()
        # Create backup codes
        BackupCode.generate_codes_for_user(self.user)

    def test_disable_2fa_success(self):
        """Test successful 2FA disable."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        totp = pyotp.TOTP(self.two_factor.secret)

        response = self.client.post(self.url, {
            'password': self.password,
            'code': totp.now()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

    def test_disable_2fa_removes_records(self):
        """Test that disabling 2FA removes all records."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        totp = pyotp.TOTP(self.two_factor.secret)

        response = self.client.post(self.url, {
            'password': self.password,
            'code': totp.now()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_2fa_enabled)
        self.assertFalse(TwoFactorAuth.objects.filter(user=self.user).exists())
        self.assertFalse(BackupCode.objects.filter(user=self.user).exists())

    def test_disable_2fa_wrong_password(self):
        """Test disable with wrong password."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        totp = pyotp.TOTP(self.two_factor.secret)

        response = self.client.post(self.url, {
            'password': 'WrongPassword123!',
            'code': totp.now()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_disable_2fa_wrong_code(self):
        """Test disable with wrong TOTP code."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'password': self.password,
            'code': '000000'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data)

    def test_disable_2fa_not_enabled(self):
        """Test disable when 2FA is not enabled."""
        self.user.is_2fa_enabled = False
        self.user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'password': self.password,
            'code': '123456'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)

    def test_disable_2fa_requires_authentication(self):
        """Test that disable requires authentication."""
        response = self.client.post(self.url, {
            'password': self.password,
            'code': '123456'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TwoFactorStatusTestCase(APITestCase):
    """Test cases for 2FA status endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:2fa-status')
        self.password = 'SecurePass123!'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password=self.password,
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True
        )
        self.refresh_token = RefreshToken.for_user(self.user)
        self.access_token = self.refresh_token.access_token

    def test_status_2fa_disabled(self):
        """Test status when 2FA is disabled."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.get(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_enabled'])
        self.assertFalse(response.data['is_setup_pending'])
        self.assertEqual(response.data['backup_codes_remaining'], 0)

    def test_status_2fa_setup_pending(self):
        """Test status when 2FA setup is pending."""
        TwoFactorAuth.create_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.get(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_enabled'])
        self.assertTrue(response.data['is_setup_pending'])

    def test_status_2fa_enabled(self):
        """Test status when 2FA is enabled."""
        self.user.is_2fa_enabled = True
        self.user.save()
        two_factor = TwoFactorAuth.create_for_user(self.user)
        two_factor.is_verified = True
        two_factor.save()
        BackupCode.generate_codes_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.get(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_enabled'])
        self.assertFalse(response.data['is_setup_pending'])
        self.assertEqual(response.data['backup_codes_remaining'], 10)

    def test_status_requires_authentication(self):
        """Test that status requires authentication."""
        response = self.client.get(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class BackupCodesTestCase(APITestCase):
    """Test cases for backup codes endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:2fa-backup-codes')
        self.password = 'SecurePass123!'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password=self.password,
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True,
            is_2fa_enabled=True
        )
        self.refresh_token = RefreshToken.for_user(self.user)
        self.access_token = self.refresh_token.access_token
        # Create 2FA and backup codes
        two_factor = TwoFactorAuth.create_for_user(self.user)
        two_factor.is_verified = True
        two_factor.save()
        BackupCode.generate_codes_for_user(self.user)

    def test_get_backup_codes_count(self):
        """Test getting backup codes count."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.get(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unused_count'], 10)
        self.assertEqual(response.data['backup_codes'], [])  # Codes not exposed

    def test_regenerate_backup_codes(self):
        """Test regenerating backup codes."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['backup_codes']), 10)
        self.assertEqual(response.data['unused_count'], 10)

    def test_regenerate_backup_codes_wrong_password(self):
        """Test regenerating backup codes with wrong password."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.url, {
            'password': 'WrongPassword123!'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_backup_codes_requires_2fa_enabled(self):
        """Test that backup codes require 2FA enabled."""
        self.user.is_2fa_enabled = False
        self.user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.get(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_backup_codes_requires_authentication(self):
        """Test that backup codes require authentication."""
        response = self.client.get(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TwoFactorLoginTestCase(APITestCase):
    """Test cases for 2FA login endpoint."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse('users:login-2fa')
        self.login_url = reverse('users:login')
        self.password = 'SecurePass123!'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password=self.password,
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True,
            is_2fa_enabled=True
        )
        # Create verified 2FA
        self.two_factor = TwoFactorAuth.create_for_user(self.user)
        self.two_factor.is_verified = True
        self.two_factor.save()
        # Generate backup codes
        self.backup_codes = BackupCode.generate_codes_for_user(self.user)

    def test_login_with_2fa_requires_totp(self):
        """Test that login with 2FA enabled requires TOTP verification."""
        response = self.client.post(self.login_url, {
            'email': self.user.email,
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(response.data['requires_2fa'])
        self.assertIn('temp_token', response.data)
        self.assertNotIn('email', response.data)

    def test_2fa_login_success_with_totp(self):
        """Test successful 2FA login with TOTP code."""
        # First get temp token
        temp_token = TwoFactorToken.create_for_user(self.user)
        totp = pyotp.TOTP(self.two_factor.secret)

        response = self.client.post(self.url, {
            'temp_token': temp_token.token,
            'code': totp.now()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)

    def test_2fa_login_success_with_backup_code(self):
        """Test successful 2FA login with backup code."""
        temp_token = TwoFactorToken.create_for_user(self.user)
        backup_code = self.backup_codes[0]

        response = self.client.post(self.url, {
            'temp_token': temp_token.token,
            'code': backup_code
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_2fa_login_backup_code_marked_used(self):
        """Test that backup code is marked as used after login."""
        temp_token = TwoFactorToken.create_for_user(self.user)
        backup_code = self.backup_codes[0]
        initial_count = BackupCode.get_unused_count(self.user)

        response = self.client.post(self.url, {
            'temp_token': temp_token.token,
            'code': backup_code
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(BackupCode.get_unused_count(self.user), initial_count - 1)

    def test_2fa_login_invalid_totp(self):
        """Test 2FA login with invalid TOTP code."""
        temp_token = TwoFactorToken.create_for_user(self.user)

        response = self.client.post(self.url, {
            'temp_token': temp_token.token,
            'code': '000000'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data)

    def test_2fa_login_invalid_backup_code(self):
        """Test 2FA login with invalid backup code."""
        temp_token = TwoFactorToken.create_for_user(self.user)

        response = self.client.post(self.url, {
            'temp_token': temp_token.token,
            'code': 'XXXXXXXX'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data)

    def test_2fa_login_invalid_temp_token(self):
        """Test 2FA login with invalid temp token."""
        totp = pyotp.TOTP(self.two_factor.secret)

        response = self.client.post(self.url, {
            'temp_token': 'invalid-token',
            'code': totp.now()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('temp_token', response.data)

    def test_2fa_login_expired_temp_token(self):
        """Test 2FA login with expired temp token."""
        from django.utils import timezone
        from datetime import timedelta

        temp_token = TwoFactorToken.create_for_user(self.user)
        # Manually expire the token
        temp_token.expires_at = timezone.now() - timedelta(minutes=1)
        temp_token.save()

        totp = pyotp.TOTP(self.two_factor.secret)

        response = self.client.post(self.url, {
            'temp_token': temp_token.token,
            'code': totp.now()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('temp_token', response.data)

    def test_2fa_login_used_temp_token(self):
        """Test 2FA login with already used temp token."""
        temp_token = TwoFactorToken.create_for_user(self.user)
        temp_token.is_used = True
        temp_token.save()

        totp = pyotp.TOTP(self.two_factor.secret)

        response = self.client.post(self.url, {
            'temp_token': temp_token.token,
            'code': totp.now()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('temp_token', response.data)

    def test_2fa_login_invalidates_temp_token(self):
        """Test that successful 2FA login invalidates the temp token."""
        temp_token = TwoFactorToken.create_for_user(self.user)
        totp = pyotp.TOTP(self.two_factor.secret)

        response = self.client.post(self.url, {
            'temp_token': temp_token.token,
            'code': totp.now()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Try to use the same token again
        response = self.client.post(self.url, {
            'temp_token': temp_token.token,
            'code': totp.now()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('temp_token', response.data)

    def test_2fa_login_updates_last_login(self):
        """Test that 2FA login updates last_login."""
        self.assertIsNone(self.user.last_login)
        temp_token = TwoFactorToken.create_for_user(self.user)
        totp = pyotp.TOTP(self.two_factor.secret)

        response = self.client.post(self.url, {
            'temp_token': temp_token.token,
            'code': totp.now()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)


class TwoFactorFullFlowTestCase(APITestCase):
    """Test cases for complete 2FA flow."""

    def setUp(self):
        """Set up test data."""
        self.password = 'SecurePass123!'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password=self.password,
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True
        )
        self.refresh_token = RefreshToken.for_user(self.user)
        self.access_token = self.refresh_token.access_token

    def test_complete_2fa_setup_and_login_flow(self):
        """Test complete flow: setup -> verify -> login with 2FA."""
        # Step 1: Setup 2FA
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        setup_url = reverse('users:2fa-setup')
        setup_response = self.client.post(setup_url, format='json')

        self.assertEqual(setup_response.status_code, status.HTTP_200_OK)
        secret = setup_response.data['secret']

        # Step 2: Verify setup
        verify_url = reverse('users:2fa-verify-setup')
        totp = pyotp.TOTP(secret)
        verify_response = self.client.post(verify_url, {
            'code': totp.now()
        }, format='json')

        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(verify_response.data['backup_codes']), 10)

        # Step 3: Login requires 2FA - returns temp_token
        self.client.credentials()
        login_url = reverse('users:login')
        login_response = self.client.post(login_url, {
            'email': self.user.email,
            'password': self.password
        }, format='json')

        self.assertEqual(login_response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(login_response.data['requires_2fa'])
        self.assertIn('temp_token', login_response.data)
        temp_token = login_response.data['temp_token']

        # Step 4: Complete login with temp_token and TOTP
        login_2fa_url = reverse('users:login-2fa')
        login_2fa_response = self.client.post(login_2fa_url, {
            'temp_token': temp_token,
            'code': totp.now()
        }, format='json')

        self.assertEqual(login_2fa_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', login_2fa_response.data)

    def test_disable_2fa_and_normal_login(self):
        """Test disabling 2FA allows normal login."""
        # Setup and enable 2FA
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        setup_url = reverse('users:2fa-setup')
        setup_response = self.client.post(setup_url, format='json')
        secret = setup_response.data['secret']

        verify_url = reverse('users:2fa-verify-setup')
        totp = pyotp.TOTP(secret)
        self.client.post(verify_url, {
            'code': totp.now()
        }, format='json')

        # Disable 2FA
        disable_url = reverse('users:2fa-disable')
        disable_response = self.client.post(disable_url, {
            'password': self.password,
            'code': totp.now()
        }, format='json')

        self.assertEqual(disable_response.status_code, status.HTTP_200_OK)

        # Normal login should work now
        self.client.credentials()
        login_url = reverse('users:login')
        login_response = self.client.post(login_url, {
            'email': self.user.email,
            'password': self.password
        }, format='json')

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', login_response.data)
        self.assertNotIn('requires_2fa', login_response.data)
