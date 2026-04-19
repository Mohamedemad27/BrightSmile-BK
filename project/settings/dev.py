"""
Development settings for Bright Smile project.
"""
from .common import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# Add development-specific apps
INSTALLED_APPS += [
    'debug_toolbar',
    # 'silk',  # Disabled due to Django 5.1 compatibility issues
]

# Add development middleware
MIDDLEWARE += [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    # 'silk.middleware.SilkyMiddleware',  # Disabled due to Django 5.1 compatibility issues
]

# Debug Toolbar configuration
INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]

# REST Framework - Add Browsable API for development
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
    'rest_framework.renderers.JSONRenderer',
    'rest_framework.renderers.BrowsableAPIRenderer',
]

# Email backend for development:
# Read from environment and default to SMTP so dev matches production delivery.
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend'
)

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
