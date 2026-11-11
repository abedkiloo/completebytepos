"""
Validate and compress uploaded images before they hit storage.

Public entry points:
    - ``prepare_uploaded_image`` — reject oversize / non-images, JPEG-compress
      to ``TARGET_STORED_BYTES`` (1.5 MiB) or less
    - ``PRODUCT_MAX_INPUT_BYTES`` — hard 2 MiB cap for product photos
    - ``GENERAL_MAX_INPUT_BYTES`` — 5 MiB intake cap before compression

Side effects: none (pure transform). Callers persist the returned file.
"""

from __future__ import annotations

import io
from typing import Optional

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

# Stored photos must fit under this after compression (1.5 MiB).
TARGET_STORED_BYTES = int(1.5 * 1024 * 1024)

# Typical receipts / notes / POD / site media: accept up to 5 MiB, then compress.
GENERAL_MAX_INPUT_BYTES = 5 * 1024 * 1024

# Product catalog photos: reject above 2 MiB before compression.
PRODUCT_MAX_INPUT_BYTES = 2 * 1024 * 1024

_ALLOWED_FORMATS = frozenset({'JPEG', 'JPG', 'PNG', 'WEBP', 'GIF'})
_MAX_EDGE = 1920
_QUALITY_STEPS = (85, 75, 65, 55, 45, 35)


def _read_bytes(uploaded_file) -> bytes:
    """
    Read upload bytes and rewind the file pointer when possible.

    Args:
        uploaded_file: Django ``UploadedFile`` / file-like object.

    Returns:
        Raw file bytes (may be empty).
    """
    raw = uploaded_file.read()
    if hasattr(uploaded_file, 'seek'):
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
    return raw or b''


def _mb_label(num_bytes: int) -> str:
    """
    Human size label for error messages.

    Args:
        num_bytes: Byte count (≥ 0).

    Returns:
        String like ``1.5 MB`` or ``2 MB``.
    """
    mb = num_bytes / (1024 * 1024)
    if abs(mb - round(mb)) < 0.05:
        return f'{int(round(mb))} MB'
    return f'{mb:.1f} MB'


def compress_image_bytes(
    raw: bytes,
    *,
    target_bytes: int = TARGET_STORED_BYTES,
    max_edge: int = _MAX_EDGE,
) -> bytes:
    """
    Decode a bitmap and JPEG-compress it to ``target_bytes`` or less.

    Args:
        raw: Decoded image file bytes (JPEG/PNG/WebP/GIF), length 1 .. 20 MiB.
        target_bytes: Max output size inclusive (default 1.5 MiB).
        max_edge: Longest side in pixels after resize (default 1920).

    Returns:
        JPEG bytes with length ≤ ``target_bytes``.

    Raises:
        ValidationError: Undecodable image, disallowed format, or cannot fit
            under ``target_bytes`` after resize/quality steps.
    """
    if not raw:
        raise ValidationError('Photo is empty.')
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValidationError('Image processing is unavailable on this server.') from exc

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
        fmt = (image.format or '').upper()
    except Exception as exc:
        raise ValidationError('File is not a valid image.') from exc

    if fmt not in _ALLOWED_FORMATS:
        raise ValidationError('Use a JPEG, PNG, WebP, or GIF image.')

    if image.mode in ('RGBA', 'LA', 'P'):
        rgba = image.convert('RGBA')
        background = Image.new('RGB', rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')

    width, height = image.size
    longest = max(width, height)
    if longest > max_edge:
        scale = max_edge / float(longest)
        image = image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )

    best: Optional[bytes] = None
    working = image
    for _round in range(4):
        for quality in _QUALITY_STEPS:
            buf = io.BytesIO()
            working.save(buf, format='JPEG', quality=quality, optimize=True)
            data = buf.getvalue()
            if best is None or len(data) < len(best):
                best = data
            if len(data) <= target_bytes:
                return data
        # Still too big — shrink further and retry.
        w, h = working.size
        if max(w, h) <= 480:
            break
        working = working.resize(
            (max(1, int(w * 0.75)), max(1, int(h * 0.75))),
            Image.Resampling.LANCZOS,
        )

    if best is not None and len(best) <= target_bytes:
        return best
    raise ValidationError(
        f'Photo is still larger than {_mb_label(target_bytes)} after compressing. '
        'Crop or pick a smaller picture.'
    )


def prepare_uploaded_image(
    uploaded_file,
    *,
    field_name: str = 'image',
    max_input_bytes: int = GENERAL_MAX_INPUT_BYTES,
    target_bytes: int = TARGET_STORED_BYTES,
    label: str = 'Photo',
    preferred_name: str = 'photo.jpg',
):
    """
    Validate an upload and return a JPEG under ``target_bytes``.

    Args:
        uploaded_file: Django ``UploadedFile`` / file-like, or ``None``.
        field_name: DRF / form field key for ``ValidationError`` dicts.
        max_input_bytes: Hard reject above this size before compression
            (products use ``PRODUCT_MAX_INPUT_BYTES`` = 2 MiB).
        target_bytes: Max stored JPEG size (default 1.5 MiB).
        label: Human label in error messages (e.g. ``Product photo``).
        preferred_name: Base filename; extension forced to ``.jpg``.

    Returns:
        ``SimpleUploadedFile`` JPEG named ``*.jpg``, size 1 .. ``target_bytes``.
        Returns ``None`` when ``uploaded_file`` is ``None``.

    Raises:
        ValidationError: Missing/empty, over ``max_input_bytes``, non-image,
            or cannot compress under ``target_bytes``.
    """
    if uploaded_file is None:
        return None

    size = getattr(uploaded_file, 'size', None)
    if size is not None and size <= 0:
        raise ValidationError({field_name: f'{label} is empty.'})
    if size is not None and size > max_input_bytes:
        raise ValidationError({
            field_name: (
                f'{label} must be {_mb_label(max_input_bytes)} or smaller.'
            ),
        })

    raw = _read_bytes(uploaded_file)
    if not raw:
        raise ValidationError({field_name: f'{label} is empty.'})
    if len(raw) > max_input_bytes:
        raise ValidationError({
            field_name: (
                f'{label} must be {_mb_label(max_input_bytes)} or smaller.'
            ),
        })

    try:
        jpeg = compress_image_bytes(raw, target_bytes=target_bytes)
    except ValidationError as exc:
        message = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
        raise ValidationError({field_name: message}) from exc

    base = (preferred_name or 'photo').rsplit('.', 1)[0] or 'photo'
    base = ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in base)[:40] or 'photo'
    return SimpleUploadedFile(
        f'{base}.jpg',
        jpeg,
        content_type='image/jpeg',
    )
