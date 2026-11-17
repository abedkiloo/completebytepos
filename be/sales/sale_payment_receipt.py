"""Checkout M-Pesa payment screenshot attach helpers."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from utils.image_upload import (
    GENERAL_MAX_INPUT_BYTES,
    TARGET_STORED_BYTES,
    prepare_uploaded_image,
)


def actor_is_sales_personnel(user) -> bool:
    """
    Whether this person is Sales Personnel.

    Args:
        user: Authenticated user or None. The custom role name is read when
            a profile exists. Length of that name is 0–150.

    Returns:
        bool: True only for the Sales Personnel role. Missing profile is False.

    Raises:
        None.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    custom = getattr(profile, 'custom_role', None)
    name = (getattr(custom, 'name', '') or '') if custom is not None else ''
    if name == 'Sales Personnel':
        return True
    return (getattr(profile, 'role', '') or '') == 'sales'


def terminal_mpesa_screenshot_optional(request) -> bool:
    """
    Terminal POS may skip the M-Pesa screenshot. A sales person may not.

    Args:
        request: DRF request or None. ``pos_surface`` must be the string
            ``terminal`` (max 16 characters). Any other value stays required.

    Returns:
        bool: True only for a terminal checkout by someone who is not
        Sales Personnel. No writes.

    Raises:
        None.
    """
    if request is None:
        return False
    data = getattr(request, 'data', None) or {}
    surface = str(data.get('pos_surface') or '').strip().lower()[:16]
    if surface != 'terminal':
        return False
    return not actor_is_sales_personnel(getattr(request, 'user', None))


def require_sale_payment_receipt_image(
    uploaded_file,
    *,
    payment_method: str,
    amount_paid,
    optional: bool = False,
) -> None:
    """
    Require a payment screenshot when collecting M-Pesa now.

    Args:
        uploaded_file: UploadedFile or None.
        payment_method: Sale tender code.
        amount_paid: Amount collected (0 → pay later, no receipt).
        optional: When True, a missing file is allowed. A file that is sent
            is still stored by ``attach_sale_payment_receipt``. Default False
            keeps every other checkout mandatory.

    Raises:
        ValidationError: When M-Pesa is collected without a screenshot and
            ``optional`` is False.
    """
    from sales.sale_payment_method import as_decimal

    method = (payment_method or '').strip().lower()
    paid = as_decimal(amount_paid)
    if method != 'mpesa' or paid <= 0:
        return
    if uploaded_file is None:
        if optional:
            return
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
