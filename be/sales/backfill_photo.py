"""Attach pending backfill receipt photos saved before maker-checker approval."""

from __future__ import annotations

import io
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

# Keep uploads small enough for receipts; reject multi-megabyte dumps.
_MAX_BACKFILL_PHOTO_BYTES = 5 * 1024 * 1024
_ALLOWED_FORMATS = {
    'JPEG': '.jpg',
    'JPG': '.jpg',
    'PNG': '.png',
    'WEBP': '.webp',
    'GIF': '.gif',
}


def save_pending_backfill_receipt_photo(uploaded_file) -> str:
    """
    Store an uploaded receipt image after verifying it is a real bitmap.

    Rejects SVG/HTML and other non-image payloads that would become stored XSS
    when served from same-origin ``/media/``. Extension is chosen server-side
    from the decoded image format (client filename is ignored).

    Args:
        uploaded_file: Django ``UploadedFile`` (size 1 byte .. 5 MiB).

    Returns:
        Storage path under ``sale_backfill/pending/`` (uuid + safe extension).

    Raises:
        ValidationError: Empty file, oversize, undecodable, or disallowed format.
    """
    if uploaded_file is None:
        raise ValidationError({'backfill_receipt_photo': 'No file uploaded.'})

    size = getattr(uploaded_file, 'size', None)
    if size is not None and size <= 0:
        raise ValidationError({'backfill_receipt_photo': 'Empty file.'})
    if size is not None and size > _MAX_BACKFILL_PHOTO_BYTES:
        raise ValidationError({
            'backfill_receipt_photo': (
                f'Image must be {_MAX_BACKFILL_PHOTO_BYTES // (1024 * 1024)} MB or smaller.'
            ),
        })

    raw = uploaded_file.read()
    if hasattr(uploaded_file, 'seek'):
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
    if not raw:
        raise ValidationError({'backfill_receipt_photo': 'Empty file.'})
    if len(raw) > _MAX_BACKFILL_PHOTO_BYTES:
        raise ValidationError({
            'backfill_receipt_photo': (
                f'Image must be {_MAX_BACKFILL_PHOTO_BYTES // (1024 * 1024)} MB or smaller.'
            ),
        })

    try:
        from PIL import Image
    except ImportError as exc:
        raise ValidationError({
            'backfill_receipt_photo': 'Image validation is unavailable on this server.',
        }) from exc

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
        fmt = (image.format or '').upper()
    except Exception as exc:
        raise ValidationError({
            'backfill_receipt_photo': 'File is not a valid image.',
        }) from exc

    ext = _ALLOWED_FORMATS.get(fmt)
    if not ext:
        raise ValidationError({
            'backfill_receipt_photo': 'Use a JPEG, PNG, WebP, or GIF image.',
        })

    token = uuid.uuid4().hex
    path = f'sale_backfill/pending/{token}{ext}'
    return default_storage.save(path, ContentFile(raw))


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
