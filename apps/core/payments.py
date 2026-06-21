import logging
from decimal import Decimal

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

PAYMOB_INTENTION_URL = 'https://accept.paymob.com/v1/intention/'
PAYMOB_INTENTION_STATUS_URL = 'https://accept.paymob.com/v1/intention/{intention_id}/'
PAYMOB_UNIFIED_CHECKOUT_URL = 'https://accept.paymob.com/unifiedcheckout/'


def _paymob_headers(secret_key: str) -> dict[str, str]:
    return {
        'Authorization': f'Token {secret_key}',
        'Content-Type': 'application/json',
    }


def build_paymob_checkout_url(public_key: str, client_secret: str) -> str:
    return f'{PAYMOB_UNIFIED_CHECKOUT_URL}?publicKey={public_key}&clientSecret={client_secret}'


def create_paymob_intention(*, user, amount: Decimal, currency: str, merchant_order_id: str) -> dict:
    secret_key = getattr(settings, 'PAYMOB_SECRET_KEY', '')
    public_key = getattr(settings, 'PAYMOB_PUBLIC_KEY', '')
    integration_id = getattr(settings, 'PAYMOB_INTEGRATION_ID', 0)

    if not secret_key or not public_key or not integration_id:
        raise ValueError('Paymob keys are not configured.')

    first_name = (user.first_name or 'Patient').strip() or 'Patient'
    last_name = (user.last_name or 'User').strip() or 'User'
    amount_cents = int((amount * Decimal('100')).quantize(Decimal('1')))

    payload = {
        'amount': amount_cents,
        'currency': currency,
        'payment_methods': [int(integration_id)],
        'merchant_order_id': merchant_order_id,
        'billing_data': {
            'first_name': first_name,
            'last_name': last_name,
            'email': user.email,
            'phone_number': '',
            'country': 'EG',
            'city': 'Cairo',
            'street': 'NA',
            'building': 'NA',
            'floor': 'NA',
            'apartment': 'NA',
            'state': 'NA',
            'postal_code': 'NA',
        },
        'items': [],
    }

    response = requests.post(
        PAYMOB_INTENTION_URL,
        json=payload,
        headers=_paymob_headers(secret_key),
        timeout=20,
    )
    response.raise_for_status()
    body = response.json()
    client_secret = body.get('client_secret', '')
    intention_id = body.get('id')

    if not client_secret or not intention_id:
        logger.error('Unexpected Paymob intention response: %s', body)
        raise ValueError('Invalid Paymob response: missing client_secret or id.')

    checkout_url = build_paymob_checkout_url(public_key, client_secret)
    return {
        'provider_reference': str(intention_id),
        'client_secret': client_secret,
        'checkout_url': checkout_url,
        'raw': body,
    }


def fetch_paymob_intention_status(intention_id: str) -> dict:
    secret_key = getattr(settings, 'PAYMOB_SECRET_KEY', '')
    if not secret_key:
        raise ValueError('Paymob secret key is missing.')

    response = requests.get(
        PAYMOB_INTENTION_STATUS_URL.format(intention_id=intention_id),
        headers=_paymob_headers(secret_key),
        timeout=20,
    )
    response.raise_for_status()
    body = response.json()

    status_value = str(body.get('status', '')).lower()
    transaction_status = str(body.get('transaction_status', '')).lower()

    is_paid = status_value in {'succeeded', 'success', 'paid', 'completed'}
    if transaction_status in {'success', 'paid', 'captured', 'authorized'}:
        is_paid = True

    return {
        'is_paid': is_paid,
        'status': status_value or transaction_status or 'pending',
        'raw': body,
    }
