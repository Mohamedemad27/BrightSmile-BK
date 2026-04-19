"""
Common settings for Bright Smile project.
"""
import os
from datetime import timedelta
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-in-production')

# Application definition
USE_GIS = config('USE_GIS', default=False, cast=bool)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_yasg',
    'drf_spectacular',

    # Local apps
    'apps.core',
    'apps.users',
    'apps.dashboard',
    'apps.ai',
    'apps.reports',
]

if USE_GIS:
    INSTALLED_APPS.append('django.contrib.gis')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'utils.middleware.request_logging.RequestLoggingMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'project.wsgi.application'

# Database
DB_ENGINE = config('DB_ENGINE', default='django.db.backends.sqlite3')
if DB_ENGINE == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': config('DB_NAME', default=str(BASE_DIR / 'db.sqlite3')),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': config('DB_NAME', default='bright_smile_db'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default='postgres'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'utils.pagination.StandardizedPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'auth_login': '10/min',
        'admin_sync': '5/min',
    },
    'DEFAULT_RENDERER_CLASSES': [
        'utils.renderers.EnvelopeJSONRenderer',
    ],
    'EXCEPTION_HANDLER': 'utils.exception_handler.custom_exception_handler',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Bright Smile API',
    'DESCRIPTION': 'Bright Smile public and dashboard API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'DISABLE_ERRORS_AND_WARNINGS': True,
}

# CORS settings
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000,http://localhost:5174,http://127.0.0.1:5174',
    cast=lambda v: [s.strip() for s in v.split(',')]
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000,http://localhost:5174,http://127.0.0.1:5174',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# GDAL Library Path (for GeoDjango)
if os.name == 'nt':  # Windows
    GDAL_LIBRARY_PATH = config('GDAL_LIBRARY_PATH', default=None)
    GEOS_LIBRARY_PATH = config('GEOS_LIBRARY_PATH', default=None)

# Cache Configuration (Redis)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': config('CELERY_BROKER_URL', default='redis://localhost:6379/0'),
    }
}

# Application Version and Environment
APP_VERSION = '1.0.0'
ENVIRONMENT = config('ENVIRONMENT', default='dev')

# OTP Configuration
OTP_EXPIRY_MINUTES = config('OTP_EXPIRY_MINUTES', default=5, cast=int)
PASSWORD_RESET_OTP_EXPIRY_MINUTES = config('PASSWORD_RESET_OTP_EXPIRY_MINUTES', default=5, cast=int)
PASSWORD_RESET_TOKEN_EXPIRY_MINUTES = config('PASSWORD_RESET_TOKEN_EXPIRY_MINUTES', default=10, cast=int)

# Email Configuration
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.sendgrid.net')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='apikey')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@brightsmile.com')

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=60, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# Two-Factor Authentication Configuration
TWO_FACTOR_ISSUER_NAME = config('TWO_FACTOR_ISSUER_NAME', default='Bright Smile')
TWO_FACTOR_TOKEN_EXPIRY_MINUTES = config('TWO_FACTOR_TOKEN_EXPIRY_MINUTES', default=5, cast=int)

# Google OAuth Configuration
GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID', default='')

# Feature Flags
FEATURE_FLAGS = {
    'enable_syndicate_sync': config('FEATURE_ENABLE_SYNDICATE_SYNC', default=True, cast=bool),
    'enable_audit_logging': config('FEATURE_ENABLE_AUDIT_LOGGING', default=True, cast=bool),
}

# External integrations
SYNDICATE_SOURCE_URL = config('SYNDICATE_SOURCE_URL', default='')
SYNDICATE_TIMEOUT_SECONDS = config('SYNDICATE_TIMEOUT_SECONDS', default=5, cast=int)
IDEMPOTENCY_CACHE_TTL_SECONDS = config('IDEMPOTENCY_CACHE_TTL_SECONDS', default=3600, cast=int)

# Reports storage (MinIO / S3 compatible)
REPORTS_STORAGE_ENDPOINT = config('REPORTS_STORAGE_ENDPOINT', default='')
REPORTS_STORAGE_REGION = config('REPORTS_STORAGE_REGION', default='us-east-1')
REPORTS_STORAGE_BUCKET = config('REPORTS_STORAGE_BUCKET', default='bright-smile-reports')
REPORTS_STORAGE_ACCESS_KEY = config('REPORTS_STORAGE_ACCESS_KEY', default='')
REPORTS_STORAGE_SECRET_KEY = config('REPORTS_STORAGE_SECRET_KEY', default='')
REPORTS_PUBLIC_BASE_URL = config('REPORTS_PUBLIC_BASE_URL', default='')
REPORTS_DOWNLOAD_URL_EXPIRY_SECONDS = config('REPORTS_DOWNLOAD_URL_EXPIRY_SECONDS', default=86400, cast=int)

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'loggers': {
        'request': {
            'handlers': ['console'],
            'level': config('REQUEST_LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'apps.dashboard': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
