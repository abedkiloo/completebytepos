"""Attach pending backfill receipt photos saved before maker-checker approval."""

from __future__ import annotations

import os
import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def save_pending_backfill_receipt_photo(uploaded_file) -> str:
    """Store an uploaded receipt image; return the storage path."""
    ext = os.path.splitext(getattr(uploaded_file, 'name', '') or '')[1] or '.jpg'
    token = uuid.uuid4().hex
    path = f'sale_backfill/pending/{token}{ext}'
    return default_storage.save(path, uploaded_file)


def attach_pending_backfill_receipt_photo(sale, storage_path: str | None) -> None:
    """Move a pending receipt photo onto the sale and delete the pending file."""
    if not storage_path or not default_storage.exists(storage_path):
        return
    with default_storage.open(storage_path, 'rb') as pending:
        sale.backfill_receipt_photo.save(
            os.path.basename(storage_path),
            ContentFile(pending.read()),
            save=True,
        )
    default_storage.delete(storage_path)
