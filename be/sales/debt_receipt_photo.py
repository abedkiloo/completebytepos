"""Pending M-Pesa repayment receipt photos (maker-checker before wallet credit)."""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from utils.image_upload import (
    GENERAL_MAX_INPUT_BYTES,
    TARGET_STORED_BYTES,
    prepare_uploaded_image,
)


def save_pending_debt_receipt_photo(uploaded_file) -> str:
    """
    Validate, compress (≤ 1.5 MiB), and store a repayment receipt pending approval.

    Args:
        uploaded_file: Django UploadedFile (1 byte .. 5 MiB intake, real bitmap).

    Returns:
        Storage path under ``debt_receipts/pending/`` ending in ``.jpg``.

    Raises:
        ValidationError: Empty, oversize intake, non-image, or compress failure.
    """
    prepared = prepare_uploaded_image(
        uploaded_file,
        field_name='receipt_image',
        max_input_bytes=GENERAL_MAX_INPUT_BYTES,
        target_bytes=TARGET_STORED_BYTES,
        label='Receipt photo',
        preferred_name='mpesa_receipt.jpg',
    )
    if prepared is None:
        raise ValidationError({'receipt_image': 'Attach the M-Pesa repayment screenshot.'})

    path = f'debt_receipts/pending/{uuid.uuid4().hex}.jpg'
    return default_storage.save(path, ContentFile(prepared.read()))


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
