"""Helpers for wallet repayment receipt images and backdated payment dates."""

from __future__ import annotations

from django.utils import timezone


def receipt_image_url(txn, *, request=None) -> str | None:
    """
    Absolute media URL for a wallet transaction receipt image.

    Args:
        txn: CustomerWalletTransaction (or any object with ``receipt_image``).
        request: Optional HTTP request for absolute URL building.

    Returns:
        Absolute URL string, or None when no image is stored / URL unavailable.
    """
    image = getattr(txn, 'receipt_image', None)
    if not image:
        return None
    try:
        relative = image.url
    except (ValueError, AttributeError, OSError):
        return None
    from config.media_urls import absolute_media_url

    return absolute_media_url(request, relative)


def is_backdated_wallet_txn(txn) -> bool:
    """
    True when the payment's business local day differs from when it was recorded.

    Args:
        txn: CustomerWalletTransaction with ``occurred_at`` / ``created_at``.

    Returns:
        bool. False when ``occurred_at`` is null (legacy / same-day default).
    """
    occurred = getattr(txn, 'occurred_at', None)
    created = getattr(txn, 'created_at', None)
    if occurred is None or created is None:
        return False
    return timezone.localtime(occurred).date() != timezone.localtime(created).date()
