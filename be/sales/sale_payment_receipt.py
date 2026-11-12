"""Checkout M-Pesa payment screenshot attach helpers."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from utils.image_upload import (
    GENERAL_MAX_INPUT_BYTES,
    TARGET_STORED_BYTES,
    prepare_uploaded_image,
)


def require_sale_payment_receipt_image(uploaded_file, *, payment_method: str, amount_paid) -> None:
    """
    Require a payment screenshot when collecting M-Pesa now.

    Args:
        uploaded_file: UploadedFile or None.
        payment_method: Sale tender code.
        amount_paid: Amount collected (0 → pay later, no receipt).

    Raises:
        ValidationError: When M-Pesa is collected without a screenshot.
    """
    from sales.sale_payment_method import as_decimal

    method = (payment_method or '').strip().lower()
    paid = as_decimal(amount_paid)
    if method != 'mpesa' or paid <= 0:
        return
    if uploaded_file is None:
        raise ValidationError({
            'payment_receipt_image': (
                'Attach a screenshot of the M-Pesa payment (till or bank).'
            ),
        })


def attach_sale_payment_receipt(sale, uploaded_file) -> None:
    """
    Compress and save a checkout payment screenshot onto [sale].

    Args:
        sale: Sale instance.
        uploaded_file: UploadedFile or None (no-op when blank).

    Raises:
        ValidationError: Invalid / oversize image.
    """
    if uploaded_file is None:
        return
    prepared = prepare_uploaded_image(
        uploaded_file,
        field_name='payment_receipt_image',
        max_input_bytes=GENERAL_MAX_INPUT_BYTES,
        target_bytes=TARGET_STORED_BYTES,
        label='Payment screenshot',
        preferred_name='payment_receipt.jpg',
    )
    if prepared is None:
        raise ValidationError({
            'payment_receipt_image': 'Attach a screenshot of the payment confirmation.',
        })
    sale.payment_receipt_image.save(
        'payment_receipt.jpg',
        ContentFile(prepared.read()),
        save=True,
    )


def sale_payment_receipt_url(sale, *, request=None) -> str | None:
    """Absolute or relative media URL for the sale payment screenshot."""
    image = getattr(sale, 'payment_receipt_image', None)
    if not image:
        return None
    try:
        url = image.url
    except Exception:
        return None
    if request is not None:
        try:
            return request.build_absolute_uri(url)
        except Exception:
            return url
    return url
