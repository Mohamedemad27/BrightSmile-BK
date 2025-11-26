from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()


class UserModelTestCase(TestCase):
    """Test cases for the User model."""

    def setUp(self):
        """Set up test data."""
        self.user_data = {
            'email': 'test@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'user_type': 'patient',
            'password': 'testpass123'
        }

    def test_create_user_with_email(self):
        """Test creating a user with email is successful."""
        user = User.objects.create_user(**self.user_data)

        self.assertEqual(user.email, self.user_data['email'])
        self.assertEqual(user.first_name, self.user_data['first_name'])
        self.assertEqual(user.last_name, self.user_data['last_name'])
        self.assertEqual(user.user_type, self.user_data['user_type'])
        self.assertTrue(user.check_password(self.user_data['password']))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_verified)

    def test_create_user_without_email_raises_error(self):
        """Test creating a user without email raises ValueError."""
        with self.assertRaises(ValueError) as context:
            User.objects.create_user(
                email='',
                password='testpass123',
                first_name='John',
                last_name='Doe',
                user_type='patient'
            )
        self.assertEqual(str(context.exception), 'The Email field must be set')

    def test_create_user_with_normalized_email(self):
        """Test email is normalized for new users."""
        email = 'test@EXAMPLE.COM'
        user = User.objects.create_user(
            email=email,
            password='testpass123',
            first_name='John',
            last_name='Doe',
            user_type='patient'
        )
        self.assertEqual(user.email, email.lower())

    def test_unique_email_constraint(self):
        """Test that email must be unique."""
        User.objects.create_user(**self.user_data)

        with self.assertRaises(IntegrityError):
            User.objects.create_user(**self.user_data)

    def test_user_str_method(self):
        """Test the string representation of user."""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(str(user), self.user_data['email'])

    def test_get_full_name(self):
        """Test get_full_name method returns full name."""
        user = User.objects.create_user(**self.user_data)
        expected_name = f"{self.user_data['first_name']} {self.user_data['last_name']}"
        self.assertEqual(user.get_full_name(), expected_name)

    def test_get_short_name(self):
        """Test get_short_name method returns first name."""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.get_short_name(), self.user_data['first_name'])

    def test_user_type_choices(self):
        """Test user can be created with each user type."""
        user_types = ['patient', 'doctor', 'admin']

        for user_type in user_types:
            user = User.objects.create_user(
                email=f'{user_type}@example.com',
                password='testpass123',
                first_name='Test',
                last_name='User',
                user_type=user_type
            )
            self.assertEqual(user.user_type, user_type)

    def test_user_timestamps(self):
        """Test that created_at and updated_at are set automatically."""
        user = User.objects.create_user(**self.user_data)

        self.assertIsNotNone(user.created_at)
        self.assertIsNotNone(user.updated_at)

    def test_user_last_login_initially_none(self):
        """Test that last_login is initially None."""
        user = User.objects.create_user(**self.user_data)
        self.assertIsNone(user.last_login)
