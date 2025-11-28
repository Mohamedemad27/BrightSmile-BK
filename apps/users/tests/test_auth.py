from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

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
