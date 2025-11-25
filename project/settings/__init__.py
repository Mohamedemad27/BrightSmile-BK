"""
Settings initialization for Bright Smile project.
"""
import os
from decouple import config

ENVIRONMENT = config('ENVIRONMENT', default='dev')

if ENVIRONMENT == 'prod':
    from .prod import *
else:
    from .dev import *
