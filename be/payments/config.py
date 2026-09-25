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


def get_brand_blurb():
    """SMS / public invoice thank-you line; uses the admin-editable store name."""
    from settings.store_settings_helpers import resolved_store_name

    template = getattr(settings, 'SMS_BRAND_BLURB', '') or (
        'Thank you for shopping with {store_name}.'
    )
    if template == 'Thank you for shopping with CompleteBytePOS.':
        template = 'Thank you for shopping with {store_name}.'
    try:
        return template.format(store_name=resolved_store_name())
    except (KeyError, IndexError, ValueError):
        return template.replace('{store_name}', resolved_store_name())


BRAND_BLURB = 'Thank you for shopping with Omuwenga Suppliers.'
PUBLIC_INVOICE_BASE_URL = getattr(
    settings,
    'PUBLIC_INVOICE_BASE_URL',
    'https://example.com/i',
)
