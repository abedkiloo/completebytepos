"""Payments config — secrets from env only (never shipped to mobile)."""

from django.conf import settings


def daraja_config():
    return {
        'consumer_key': getattr(settings, 'DARAJA_CONSUMER_KEY', '') or '',
        'consumer_secret': getattr(settings, 'DARAJA_CONSUMER_SECRET', '') or '',
        'shortcode': getattr(settings, 'DARAJA_SHORTCODE', '174379') or '174379',
        'passkey': getattr(settings, 'DARAJA_PASSKEY', '') or '',
        'callback_url': getattr(settings, 'DARAJA_CALLBACK_URL', '') or '',
        'env': getattr(settings, 'DARAJA_ENV', 'sandbox') or 'sandbox',
    }


BRAND_BLURB = getattr(
    settings,
    'SMS_BRAND_BLURB',
    'Thank you for shopping with CompleteBytePOS.',
)
PUBLIC_INVOICE_BASE_URL = getattr(
    settings,
    'PUBLIC_INVOICE_BASE_URL',
    'https://example.com/i',
)
