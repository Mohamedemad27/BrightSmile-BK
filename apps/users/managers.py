from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    """
    Custom user manager for the User model.
    Handles user creation with email as the primary identifier.
    """

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a regular user with the given email and password.

        Args:
            email: User's email address (required)
            password: User's password (optional)
            **extra_fields: Additional fields for the user model

        Returns:
            User: Created user instance

        Raises:
            ValueError: If email is not provided
        """
        if not email:
            raise ValueError('The Email field must be set')

        # Normalize the email address by lowercasing the domain part
        email = self.normalize_email(email)

        # Create user instance
        user = self.model(email=email, **extra_fields)

        # Set password with proper hashing
        user.set_password(password)

        # Save to database
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a superuser with the given email and password.

        Args:
            email: User's email address (required)
            password: User's password (optional)
            **extra_fields: Additional fields for the user model

        Returns:
            User: Created superuser instance

        Raises:
            ValueError: If is_staff or is_superuser is not True
        """
        # Set required superuser fields
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        # Validate superuser fields
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        # Create superuser using create_user method
        return self.create_user(email, password, **extra_fields)
