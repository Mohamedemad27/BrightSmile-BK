from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.users.models import Admin

User = get_user_model()


class AdminModelTestCase(TestCase):
    """Test cases for the Admin model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='admin@example.com',
            password='testpass123',
            first_name='John',
            last_name='Admin',
            user_type='admin'
        )
        self.admin_data = {
            'user': self.user,
        }

    def test_create_admin_with_valid_data(self):
        """Test creating an admin with valid data is successful."""
        admin = Admin.objects.create(**self.admin_data)

        self.assertEqual(admin.user, self.user)
        self.assertIsNotNone(admin.created_at)
        self.assertIsNotNone(admin.updated_at)

    def test_admin_str_method(self):
        """Test the string representation of admin."""
        admin = Admin.objects.create(**self.admin_data)
        expected_str = f"Admin: {self.user.get_full_name()}"
        self.assertEqual(str(admin), expected_str)

    def test_admin_email_property(self):
        """Test email convenience property."""
        admin = Admin.objects.create(**self.admin_data)
        self.assertEqual(admin.email, self.user.email)

    def test_admin_full_name_property(self):
        """Test full_name convenience property."""
        admin = Admin.objects.create(**self.admin_data)
        self.assertEqual(admin.full_name, self.user.get_full_name())

    def test_admin_timestamps_auto_generated(self):
        """Test that created_at and updated_at are automatically set."""
        admin = Admin.objects.create(**self.admin_data)

        self.assertIsNotNone(admin.created_at)
        self.assertIsNotNone(admin.updated_at)

    def test_admin_updated_at_changes_on_update(self):
        """Test that updated_at changes when admin is updated."""
        admin = Admin.objects.create(**self.admin_data)
        original_updated_at = admin.updated_at

        # Update the admin (save triggers updated_at change)
        admin.save()

        self.assertGreaterEqual(admin.updated_at, original_updated_at)

    def test_admin_one_to_one_relationship(self):
        """Test OneToOne relationship between Admin and User."""
        admin = Admin.objects.create(**self.admin_data)

        # Test forward relationship
        self.assertEqual(admin.user.email, 'admin@example.com')

        # Test reverse relationship
        self.assertEqual(self.user.admin_profile, admin)

    def test_admin_cascade_delete(self):
        """Test that deleting user deletes associated admin."""
        admin = Admin.objects.create(**self.admin_data)
        admin_pk = admin.pk

        # Delete the user
        self.user.delete()

        # Admin should be deleted too
        self.assertFalse(Admin.objects.filter(pk=admin_pk).exists())

    def test_admin_primary_key_is_user_id(self):
        """Test that admin uses user's primary key."""
        admin = Admin.objects.create(**self.admin_data)
        self.assertEqual(admin.pk, self.user.pk)

    def test_admin_ordering(self):
        """Test that admins are ordered by created_at descending."""
        user2 = User.objects.create_user(
            email='admin2@example.com',
            password='testpass123',
            first_name='Jane',
            last_name='Admin',
            user_type='admin'
        )
        admin1 = Admin.objects.create(**self.admin_data)
        admin2 = Admin.objects.create(user=user2)

        admins = list(Admin.objects.all())
        # Most recently created should be first
        self.assertEqual(admins[0], admin2)
        self.assertEqual(admins[1], admin1)

    def test_admin_verbose_name(self):
        """Test Admin model verbose names."""
        self.assertEqual(Admin._meta.verbose_name, 'Admin')
        self.assertEqual(Admin._meta.verbose_name_plural, 'Admins')

    def test_only_one_admin_profile_per_user(self):
        """Test that a user can only have one admin profile."""
        Admin.objects.create(**self.admin_data)

        # Attempting to create another admin profile for the same user should fail
        with self.assertRaises(Exception):
            Admin.objects.create(user=self.user)


class AdminSignalTestCase(TestCase):
    """Test cases for Admin model signals."""

    def test_user_type_set_on_admin_creation(self):
        """Test that user_type is automatically set to 'admin' when Admin is created."""
        # Create user without admin type
        user = User.objects.create_user(
            email='signal_test@example.com',
            password='testpass123',
            first_name='Signal',
            last_name='Test',
            user_type='patient'  # Intentionally set to patient
        )

        # Create admin profile
        Admin.objects.create(user=user)

        # Refresh user from database
        user.refresh_from_db()

        # User type should now be 'admin'
        self.assertEqual(user.user_type, 'admin')

    def test_is_staff_set_on_admin_creation(self):
        """Test that is_staff is automatically set to True when Admin is created."""
        # Create user without is_staff
        user = User.objects.create_user(
            email='staff_test@example.com',
            password='testpass123',
            first_name='Staff',
            last_name='Test',
            user_type='patient',
            is_staff=False  # Explicitly set to False
        )

        # Create admin profile
        Admin.objects.create(user=user)

        # Refresh user from database
        user.refresh_from_db()

        # is_staff should now be True
        self.assertTrue(user.is_staff)

    def test_user_type_and_is_staff_both_set(self):
        """Test that both user_type and is_staff are set on admin creation."""
        user = User.objects.create_user(
            email='both_test@example.com',
            password='testpass123',
            first_name='Both',
            last_name='Test',
            user_type='doctor',
            is_staff=False
        )

        Admin.objects.create(user=user)
        user.refresh_from_db()

        self.assertEqual(user.user_type, 'admin')
        self.assertTrue(user.is_staff)

    def test_no_save_if_already_admin_and_staff(self):
        """Test that signal doesn't trigger unnecessary save if user_type is already 'admin' and is_staff is True."""
        user = User.objects.create_user(
            email='already_admin@example.com',
            password='testpass123',
            first_name='Already',
            last_name='Admin',
            user_type='admin',
            is_staff=True
        )

        with patch.object(User, 'save') as mock_save:
            Admin.objects.create(user=user)
            # User.save should not be called since user_type is already 'admin' and is_staff is True
            mock_save.assert_not_called()

    def test_signal_only_on_creation(self):
        """Test that signal only fires on creation, not on update."""
        user = User.objects.create_user(
            email='update_test@example.com',
            password='testpass123',
            first_name='Update',
            last_name='Test',
            user_type='patient',
            is_staff=False
        )

        # Create admin
        admin = Admin.objects.create(user=user)

        # Change user_type back to patient and is_staff to False manually
        user.user_type = 'patient'
        user.is_staff = False
        user.save()

        # Update admin (not create)
        admin.save()

        # User type should still be 'patient' and is_staff False since signal only fires on creation
        user.refresh_from_db()
        self.assertEqual(user.user_type, 'patient')
        self.assertFalse(user.is_staff)


class SuperuserAdminProfileTestCase(TestCase):
    """Test cases for automatic Admin profile creation for superusers."""

    def test_admin_profile_created_for_superuser(self):
        """Test that an Admin profile is automatically created when a superuser is created."""
        superuser = User.objects.create_superuser(
            email='superuser@example.com',
            password='testpass123',
            first_name='Super',
            last_name='User',
            user_type='admin'
        )

        # Admin profile should be created automatically
        self.assertTrue(hasattr(superuser, 'admin_profile'))
        self.assertIsNotNone(superuser.admin_profile)
        self.assertIsInstance(superuser.admin_profile, Admin)

    def test_superuser_has_correct_attributes(self):
        """Test that superuser with auto-created Admin profile has correct attributes."""
        superuser = User.objects.create_superuser(
            email='superuser2@example.com',
            password='testpass123',
            first_name='Super',
            last_name='Admin',
            user_type='admin'
        )

        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_staff)
        self.assertEqual(superuser.user_type, 'admin')

    def test_admin_profile_not_created_for_regular_user(self):
        """Test that Admin profile is NOT created for regular users."""
        regular_user = User.objects.create_user(
            email='regular@example.com',
            password='testpass123',
            first_name='Regular',
            last_name='User',
            user_type='patient'
        )

        # Admin profile should NOT exist
        self.assertFalse(hasattr(regular_user, 'admin_profile') and regular_user.admin_profile is not None)

    def test_admin_profile_not_duplicated(self):
        """Test that creating a superuser doesn't create duplicate Admin profiles."""
        superuser = User.objects.create_superuser(
            email='nodupe@example.com',
            password='testpass123',
            first_name='No',
            last_name='Dupe',
            user_type='admin'
        )

        # Count admin profiles for this user
        admin_count = Admin.objects.filter(user=superuser).count()
        self.assertEqual(admin_count, 1)
