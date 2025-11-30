# Users App

Custom user authentication and management system for the Bright Smile application.

## Overview

This app implements a custom user model that extends Django's `AbstractBaseUser` and `PermissionsMixin`. It uses email as the primary authentication field and provides a foundation for three user types: patients, doctors, and admins.

## User Model

### Fields

| Field | Type | Description | Indexed |
|-------|------|-------------|---------|
| `email` | EmailField | Primary authentication field (unique) | Yes (unique) |
| `first_name` | CharField | User's first name (max 150 chars) | No |
| `last_name` | CharField | User's last name (max 150 chars) | No |
| `user_type` | CharField | Type of user (patient/doctor/admin) | Yes |
| `google_id` | CharField | Google OAuth user ID (unique, nullable) | Yes |
| `auth_provider` | CharField | Authentication provider (email/google) | Yes |
| `is_active` | BooleanField | Account active status (default: True) | Yes |
| `is_staff` | BooleanField | Staff status for admin access (default: False) | No |
| `is_verified` | BooleanField | Email verification status (default: False) | Yes |
| `is_2fa_enabled` | BooleanField | Two-factor authentication status (default: False) | Yes |
| `last_login` | DateTimeField | Last login timestamp (nullable) | No |
| `created_at` | DateTimeField | Account creation timestamp | Yes |
| `updated_at` | DateTimeField | Last update timestamp | No |

### Database Indexes

**Single Field Indexes**:
- `email` (via unique constraint)
- `user_type`
- `is_active`
- `is_verified`
- `created_at`

**Composite Indexes**:
- `(user_type, is_active)` - For filtering users by type and status
- `(is_verified, is_active)` - For filtering verified active users
- `email` - Additional index for email lookups
- `google_id` - For Google OAuth lookups
- `auth_provider` - For filtering by authentication provider

### User Types

```python
USER_TYPE_CHOICES = [
    ('patient', 'Patient'),
    ('doctor', 'Doctor'),
    ('admin', 'Admin'),
]
```

### Auth Providers

```python
AUTH_PROVIDER_CHOICES = [
    ('email', 'Email'),
    ('google', 'Google'),
]
```

### Methods

#### `get_full_name()`
Returns the user's full name in the format: `first_name last_name`

```python
user.get_full_name()  # "John Doe"
```

#### `get_short_name()`
Returns the user's first name

```python
user.get_short_name()  # "John"
```

#### `__str__()`
Returns the user's email address

```python
str(user)  # "user@example.com"
```

## UserManager

Custom manager for creating users with proper validation and password hashing.

### Methods

#### `create_user(email, password=None, **extra_fields)`

Creates and saves a regular user.

**Parameters**:
- `email` (required): User's email address
- `password` (optional): User's password (will be hashed)
- `**extra_fields`: Additional user fields (first_name, last_name, user_type, etc.)

**Raises**:
- `ValueError`: If email is not provided

**Example**:
```python
from django.contrib.auth import get_user_model

User = get_user_model()

user = User.objects.create_user(
    email='patient@example.com',
    password='securepass123',
    first_name='Jane',
    last_name='Smith',
    user_type='patient'
)
```

#### `create_superuser(email, password=None, **extra_fields)`

Creates and saves a superuser with staff and superuser permissions.

**Parameters**:
- `email` (required): User's email address
- `password` (optional): User's password (will be hashed)
- `**extra_fields`: Additional user fields

**Raises**:
- `ValueError`: If `is_staff` or `is_superuser` is not True

**Auto-set Fields**:
- `is_staff=True`
- `is_superuser=True`
- `is_active=True`

**Example**:
```python
superuser = User.objects.create_superuser(
    email='admin@example.com',
    password='adminpass123',
    first_name='Admin',
    last_name='User',
    user_type='admin'
)
```

## Usage Examples

### Creating a Patient User

```python
from django.contrib.auth import get_user_model

User = get_user_model()

patient = User.objects.create_user(
    email='patient@example.com',
    password='securepass123',
    first_name='John',
    last_name='Doe',
    user_type='patient'
)
```

### Creating a Doctor User

```python
doctor = User.objects.create_user(
    email='doctor@example.com',
    password='securepass123',
    first_name='Jane',
    last_name='Smith',
    user_type='doctor'
)
```

### Creating an Admin User

```python
admin = User.objects.create_superuser(
    email='admin@example.com',
    password='adminpass123',
    first_name='Admin',
    last_name='User',
    user_type='admin'
)
```

### Querying Users

```python
# Get all patients
patients = User.objects.filter(user_type='patient')

# Get all active verified doctors
doctors = User.objects.filter(
    user_type='doctor',
    is_active=True,
    is_verified=True
)

# Get user by email
user = User.objects.get(email='user@example.com')

# Check password
if user.check_password('password'):
    print("Password is correct")
```

### Updating User Information

```python
user = User.objects.get(email='user@example.com')
user.first_name = 'Updated'
user.is_verified = True
user.save()
```

## Authentication Configuration

The user model is configured as the authentication backend in `project/settings/common.py`:

```python
AUTH_USER_MODEL = 'users.User'
```

### Required Fields

When creating a user through Django's management command or admin:
- `email` - USERNAME_FIELD
- `first_name` - REQUIRED_FIELDS
- `last_name` - REQUIRED_FIELDS
- `user_type` - REQUIRED_FIELDS

## Testing

The app includes comprehensive unit tests covering:

### Model Tests (`test_models.py`)
- User creation with email
- Email validation and normalization
- Unique email constraint
- String representations (str, get_full_name, get_short_name)
- User type choices
- Timestamp auto-generation
- Last login initialization

### Manager Tests (`test_mangers.py`)
- create_user() method
- create_superuser() method
- Email validation
- Password handling
- Field validation for superusers
- Email normalization

### Running Tests

```bash
# Run all user tests
docker-compose run --rm web python manage.py test apps.users

# Run specific test file
docker-compose run --rm web python manage.py test apps.users.tests.test_models

# Run specific test case
docker-compose run --rm web python manage.py test apps.users.tests.test_models.UserModelTestCase.test_create_user_with_email
```

**Test Coverage**: 18 tests, all passing ✓

## Future Extensions

This base user model is designed to be extended through OneToOne relationships:

### Patient Model (Future)
```python
class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    medical_history = models.TextField()
    date_of_birth = models.DateField()
    # Additional patient-specific fields
```

### Doctor Model (Future)
```python
class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    specialization = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50)
    # Additional doctor-specific fields
```

### Admin Model (Future)
```python
class Admin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.CharField(max_length=100)
    # Additional admin-specific fields
```

## Migration Notes

**CRITICAL**: The initial migration (`0001_initial.py`) must be applied before any other app migrations that depend on the User model (such as admin, auth, etc.).

The migration includes:
- User model creation
- Custom UserManager
- All field definitions with constraints
- Database indexes (single and composite)

## Admin Integration

To register the User model in Django admin, add to `admin.py`:

```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'user_type', 'is_active', 'is_verified']
    list_filter = ['user_type', 'is_active', 'is_verified', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['-created_at']
```

## Security Considerations

1. **Password Hashing**: All passwords are automatically hashed using Django's password hashers
2. **Email Normalization**: Email addresses are normalized (domain lowercased) before storage
3. **Unique Constraint**: Email uniqueness is enforced at the database level
4. **Index Security**: Sensitive queries are optimized with proper indexing
5. **Field Validation**: All fields have appropriate max_length and type constraints

## Performance Optimization

The model includes strategic database indexes to optimize common queries:

**Optimized Query Patterns**:
- Filtering by user_type and is_active
- Filtering by is_verified and is_active
- Email lookups
- Ordering by created_at (default ordering)

These indexes significantly improve query performance for user listing, filtering, and authentication operations.
