"""
Google OAuth authentication service.

This module provides functionality to verify Google ID tokens
and extract user information for authentication.
"""

from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests


class GoogleAuthError(Exception):
    """Custom exception for Google authentication errors."""
    pass


class GoogleAuthService:
    """
    Service class for Google OAuth authentication.

    Handles verification of Google ID tokens and extraction of user data.
    """

    @staticmethod
    def verify_token(token: str) -> dict:
        """
        Verify a Google ID token and extract user information.

        Args:
            token: The Google ID token to verify

        Returns:
            dict: User information containing:
                - google_id: Google's unique user identifier
                - email: User's email address
                - first_name: User's given name
                - last_name: User's family name
                - email_verified: Whether Google has verified the email

        Raises:
            GoogleAuthError: If the token is invalid or verification fails
        """
        try:
            # Get the Google Client ID from settings
            client_id = getattr(settings, 'GOOGLE_CLIENT_ID', None)
            if not client_id:
                raise GoogleAuthError('Google Client ID not configured')

            # Verify the token with Google
            idinfo = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                client_id
            )

            # Verify the token issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise GoogleAuthError('Invalid token issuer')

            # Verify email is present and verified
            if not idinfo.get('email'):
                raise GoogleAuthError('Email not provided in token')

            if not idinfo.get('email_verified', False):
                raise GoogleAuthError('Email not verified by Google')

            return {
                'google_id': idinfo['sub'],
                'email': idinfo['email'].lower(),
                'first_name': idinfo.get('given_name', ''),
                'last_name': idinfo.get('family_name', ''),
                'email_verified': idinfo.get('email_verified', False),
            }

        except ValueError as e:
            raise GoogleAuthError(f'Invalid Google token: {str(e)}')
        except Exception as e:
            if isinstance(e, GoogleAuthError):
                raise
            raise GoogleAuthError(f'Google authentication failed: {str(e)}')
