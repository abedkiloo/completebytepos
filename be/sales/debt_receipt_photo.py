"""Pending M-Pesa repayment receipt photos (maker-checker before wallet credit)."""

from __future__ import annotations

import io
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

_MAX_BYTES = 5 * 1024 * 1024
_ALLOWED = {
    'JPEG': '.jpg',
    'JPG': '.jpg',
    'PNG': '.png',
    'WEBP': '.webp',
    'GIF': '.gif',
}


def save_pending_debt_receipt_photo(uploaded_file) -> str:
    """
    Validate and store a repayment receipt image pending approval.

    Args:
        uploaded_file: Django UploadedFile (1 byte .. 5 MiB, real bitmap).

    Returns:
        Storage path under ``debt_receipts/pending/``.

    Raises:
        ValidationError: Empty, oversize, or non-image payload.
    """
    if uploaded_file is None:
        raise ValidationError({'receipt_image': 'Attach the M-Pesa repayment screenshot.'})

    size = getattr(uploaded_file, 'size', None)
    if size is not None and size <= 0:
        raise ValidationError({'receipt_image': 'Receipt photo is empty.'})
    if size is not None and size > _MAX_BYTES:
        raise ValidationError({
            'receipt_image': 'Receipt photo must be 5 MB or smaller.',
        })

    raw = uploaded_file.read()
    if hasattr(uploaded_file, 'seek'):
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
    if not raw:
        raise ValidationError({'receipt_image': 'Receipt photo is empty.'})
    if len(raw) > _MAX_BYTES:
        raise ValidationError({
            'receipt_image': 'Receipt photo must be 5 MB or smaller.',
        })

    try:
        from PIL import Image
    except ImportError as exc:
        raise ValidationError({
            'receipt_image': 'Image validation is unavailable on this server.',
        }) from exc

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
        fmt = (image.format or '').upper()
    except Exception as exc:
        raise ValidationError({
            'receipt_image': 'File is not a valid image.',
        }) from exc

    ext = _ALLOWED.get(fmt)
    if not ext:
        raise ValidationError({
            'receipt_image': 'Use a JPEG, PNG, WebP, or GIF screenshot.',
        })

    path = f'debt_receipts/pending/{uuid.uuid4().hex}{ext}'
    return default_storage.save(path, ContentFile(raw))


def attach_pending_debt_receipt_photo(txn, storage_path: str | None) -> None:
    """
    Move a pending receipt onto the wallet transaction and delete the temp file.

    Args:
        txn: CustomerWalletTransaction to attach ``receipt_image`` on.
        storage_path: Path from ``save_pending_debt_receipt_photo``, or blank.

    Returns:
        None.
    """
    if not storage_path or not default_storage.exists(storage_path):
        return
    with default_storage.open(storage_path, 'rb') as pending:
        txn.receipt_image.save(
            storage_path.rsplit('/', 1)[-1],
            ContentFile(pending.read()),
            save=True,
        )
    default_storage.delete(storage_path)


def require_mpesa_receipt_image(uploaded_file, *, payment_method: str) -> None:
    """
    Require a receipt file when payment method is M-Pesa.

    Args:
        uploaded_file: UploadedFile or None.
        payment_method: ``cash`` / ``mpesa``.

    Raises:
        ValidationError: When M-Pesa and no file was attached.
    """
    if (payment_method or '').strip().lower() != 'mpesa':
        return
    if uploaded_file is None:
        raise ValidationError({
            'receipt_image': 'Attach a screenshot of the M-Pesa repayment receipt.',
        })
