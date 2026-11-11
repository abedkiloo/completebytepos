"""Attach pending backfill receipt photos saved before maker-checker approval."""

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


def save_pending_backfill_receipt_photo(uploaded_file) -> str:
    """
    Store a backfill receipt after validating and compressing to ≤ 1.5 MiB.

    Rejects SVG/HTML and other non-image payloads that would become stored XSS
    when served from same-origin ``/media/``. Extension is always ``.jpg``.

    Args:
        uploaded_file: Django ``UploadedFile`` (size 1 byte .. 5 MiB intake).

    Returns:
        Storage path under ``sale_backfill/pending/`` (uuid + ``.jpg``).

    Raises:
        ValidationError: Empty file, oversize, undecodable, or compress failure.
    """
    prepared = prepare_uploaded_image(
        uploaded_file,
        field_name='backfill_receipt_photo',
        max_input_bytes=GENERAL_MAX_INPUT_BYTES,
        target_bytes=TARGET_STORED_BYTES,
        label='Image',
        preferred_name='backfill_receipt.jpg',
    )
    if prepared is None:
        raise ValidationError({'backfill_receipt_photo': 'No file uploaded.'})

    path = f'sale_backfill/pending/{uuid.uuid4().hex}.jpg'
    return default_storage.save(path, ContentFile(prepared.read()))


def attach_pending_backfill_receipt_photo(sale, storage_path: str | None) -> None:
    """
    Move a pending receipt photo onto the sale and delete the pending file.

    Args:
        sale: ``Sale`` instance to attach ``backfill_receipt_photo`` on.
        storage_path: Path previously returned by
            ``save_pending_backfill_receipt_photo``, or None/blank to no-op.

    Returns:
        None.

    Side effects:
        Writes the sale image field and deletes the pending storage object.
    """
    if not storage_path or not default_storage.exists(storage_path):
        return
    with default_storage.open(storage_path, 'rb') as pending:
        sale.backfill_receipt_photo.save(
            storage_path.rsplit('/', 1)[-1],
            ContentFile(pending.read()),
            save=True,
        )
    default_storage.delete(storage_path)
