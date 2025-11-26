from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class UserManagerTestCase(TestCase):
    """Test cases for the UserManager."""

    def test_create_user(self):
        """Test creating a user with the manager."""
        email = 'user@example.com'
        password = 'testpass123'
        first_name = 'John'
        last_name = 'Doe'
        user_type = 'patient'

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            user_type=user_type
        )

        self.assertEqual(user.email, email)
        self.assertEqual(user.first_name, first_name)
        self.assertEqual(user.last_name, last_name)
        self.assertEqual(user.user_type, user_type)
        self.assertTrue(user.check_password(password))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_without_email(self):
        """Test creating a user without email raises ValueError."""
        with self.assertRaises(ValueError) as context:
            User.objects.create_user(
                email='',
                password='testpass123',
                first_name='John',
                last_name='Doe',
                user_type='patient'
            )
        self.assertIn('The Email field must be set', str(context.exception))

    def test_create_user_without_password(self):
        """Test creating a user without password."""
        user = User.objects.create_user(
            email='user@example.com',
            password=None,
            first_name='John',
            last_name='Doe',
            user_type='patient'
        )

        self.assertFalse(user.has_usable_password())

    def test_create_superuser(self):
        """Test creating a superuser with the manager."""
        email = 'admin@example.com'
        password = 'adminpass123'
        first_name = 'Admin'
        last_name = 'User'
        user_type = 'admin'

        superuser = User.objects.create_superuser(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            user_type=user_type
        )

        self.assertEqual(superuser.email, email)
        self.assertTrue(superuser.check_password(password))
        self.assertTrue(superuser.is_active)
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)

    def test_create_superuser_without_is_staff_raises_error(self):
        """Test creating a superuser with is_staff=False raises ValueError."""
        with self.assertRaises(ValueError) as context:
            User.objects.create_superuser(
                email='admin@example.com',
                password='adminpass123',
                first_name='Admin',
                last_name='User',
                user_type='admin',
                is_staff=False
            )
        self.assertIn('Superuser must have is_staff=True', str(context.exception))

    def test_create_superuser_without_is_superuser_raises_error(self):
        """Test creating a superuser with is_superuser=False raises ValueError."""
        with self.assertRaises(ValueError) as context:
            User.objects.create_superuser(
                email='admin@example.com',
                password='adminpass123',
                first_name='Admin',
                last_name='User',
                user_type='admin',
                is_superuser=False
            )
        self.assertIn('Superuser must have is_superuser=True', str(context.exception))

    def test_create_superuser_sets_required_fields(self):
        """Test creating a superuser automatically sets required fields."""
        superuser = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123',
            first_name='Admin',
            last_name='User',
            user_type='admin'
        )

        # Verify all required superuser fields are set correctly
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_active)

    def test_email_normalization(self):
        """Test that email is normalized when creating users."""
        email = 'Test@EXAMPLE.COM'
        user = User.objects.create_user(
            email=email,
            password='testpass123',
            first_name='Test',
            last_name='User',
            user_type='patient'
        )

        # The domain part should be lowercased
        self.assertEqual(user.email, 'Test@example.com')
