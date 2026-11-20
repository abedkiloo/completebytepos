"""
Product views: one featured photo and up to three more.

Each upload must be 2 MiB or smaller and is stored as a JPEG of at most
1.5 MiB. A product has slots 1–4. ``Product.featured_slot`` chooses the
featured photo, which is also copied onto ``Product.image``.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from products.models import ProductPhoto

MAX_PHOTOS = 4
SLOT_MIN = 1
SLOT_MAX = 4


def _url(request, field):
    """
    Absolute URL for an image field.

    Args:
        request: DRF request or None.
        field: ImageField file or empty.

    Returns:
        str or None. No writes.
    """
    if not field:
        return None
    try:
        from config.media_urls import absolute_media_url

        return absolute_media_url(request, field.url)
    except (ValueError, AttributeError, OSError):
        return None


def photo_rows(product, request=None) -> list:
    """
    Views saved on a product, featured first in the flag only.

    Args:
        product: Product instance. May have a legacy ``image`` and no rows.
        request: Optional request for absolute URLs.

    Returns:
        list[dict]: 0–4 rows of ``slot`` (1–4), ``url``, and ``is_featured``.
        A product that only has the old single image is returned as slot 1.
        No writes.
    """
    photos = list(product.photos.all()) if product.pk else []
    featured = int(getattr(product, 'featured_slot', None) or 1)
    if not photos and getattr(product, 'image', None):
        url = _url(request, product.image)
        if not url:
            return []
        return [{'slot': 1, 'url': url, 'is_featured': True}]
    rows = []
    for photo in photos:
        url = _url(request, photo.image)
        if not url:
            continue
        rows.append({
            'slot': int(photo.slot),
            'url': url,
            'is_featured': int(photo.slot) == featured,
        })
    if rows and not any(row['is_featured'] for row in rows):
        rows[0]['is_featured'] = True
    return rows


def featured_image_url(product, request=None):
    """
    URL of the featured view.

    Args:
        product: Product.
        request: Optional request.

    Returns:
        str or None. Falls back to ``Product.image``. No writes.
    """
    rows = photo_rows(product, request)
    for row in rows:
        if row['is_featured']:
            return row['url']
    return rows[0]['url'] if rows else _url(request, getattr(product, 'image', None))


def _parse_slot(value) -> int:
    """
    Parse a slot number.

    Args:
        value: Raw form value.

    Returns:
        int: 1–4.

    Raises:
        ValidationError: Outside 1–4 or not a whole number.
    """
    try:
        slot = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError({'featured_slot': 'Choose a view from 1 to 4.'})
    if slot < SLOT_MIN or slot > SLOT_MAX:
        raise ValidationError({'featured_slot': 'Choose a view from 1 to 4.'})
    return slot


def _clear_slots(raw) -> list:
    """
    Slots to remove.

    Args:
        raw: Blank, or comma-separated slots. At most 4 numbers.

    Returns:
        list[int]: Unique slots 1–4. Empty when blank.

    Raises:
        ValidationError: A token is not a slot.
    """
    text = str(raw or '').strip()
    if not text:
        return []
    slots = []
    for part in text.split(',')[:MAX_PHOTOS]:
        part = part.strip()
        if not part:
            continue
        slots.append(_parse_slot(part))
    return list(dict.fromkeys(slots))


def _prepare(uploaded, slot: int):
    """
    Compress one product view.

    Args:
        uploaded: Uploaded file.
        slot: 1–4, used as the error field name.

    Returns:
        JPEG upload of at most 1.5 MiB.

    Raises:
        ValidationError: Over 2 MiB, empty, or not a real image.
    """
    from utils.image_upload import (
        PRODUCT_MAX_INPUT_BYTES,
        TARGET_STORED_BYTES,
        prepare_uploaded_image,
    )

    return prepare_uploaded_image(
        uploaded,
        field_name=f'photo_{slot}',
        max_input_bytes=PRODUCT_MAX_INPUT_BYTES,
        target_bytes=TARGET_STORED_BYTES,
        label=f'View {slot}',
        preferred_name=getattr(uploaded, 'name', f'view-{slot}.jpg') or f'view-{slot}.jpg',
    )


def request_changes_photos(request) -> bool:
    """
    Whether this save includes a new view or a removed view.

    Args:
        request: DRF request. May have no files.

    Returns:
        True when ``image`` or ``photo_1``–``photo_4`` is uploaded, or
        ``clear_photos`` names a slot. A text-only edit returns False.

    Raises:
        None.
    """
    if request is None:
        return False
    files = getattr(request, 'FILES', None) or {}
    if any(files.get(name) for name in ('image', 'photo_1', 'photo_2', 'photo_3', 'photo_4')):
        return True
    data = getattr(request, 'data', None) or {}
    return bool(str(data.get('clear_photos') or '').strip())


def validate_product_photo_uploads(request) -> None:
    """
    Check view uploads before the product row is saved.

    Args:
        request: DRF request or None.

    Returns:
        None. No writes.

    Raises:
        ValidationError: More than 4 views, a slot outside 1–4, a file over
            2 MiB, or a file that is not an image.
    """
    if request is None:
        return
    files = getattr(request, 'FILES', None) or {}
    data = getattr(request, 'data', None) or {}
    if files.get('photo_5'):
        raise ValidationError({'photo_5': 'A product can have 4 views.'})
    for slot in range(SLOT_MIN, SLOT_MAX + 1):
        upload = files.get(f'photo_{slot}')
        if upload:
            _prepare(upload, slot)
    _clear_slots(data.get('clear_photos'))
    featured = data.get('featured_slot', None)
    if featured not in (None, ''):
        _parse_slot(featured)


def apply_product_photos(product, request) -> None:
    """
    Save uploaded views, clear chosen slots, and set the featured photo.

    The legacy ``image`` file, when present in this request, is view 1.
    Existing products that only have ``image`` gain a slot-1 row the first
    time another view is added.

    Args:
        product: Saved product.
        request: DRF request or None. Reads ``photo_1``–``photo_4``,
            ``featured_slot``, and ``clear_photos``.

    Returns:
        None.

    Raises:
        ValidationError: A file is over 2 MiB, broken, or the slot is
            outside 1–4. Nothing is saved when a file fails.

    Side effects:
        Writes ``ProductPhoto`` rows and copies the featured file onto
        ``Product.image``.
    """
    if request is None or product is None or not getattr(product, 'pk', None):
        return
    files = getattr(request, 'FILES', None) or {}
    data = getattr(request, 'data', None) or {}
    incoming = {}
    for slot in range(SLOT_MIN, SLOT_MAX + 1):
        upload = files.get(f'photo_{slot}')
        if upload:
            incoming[slot] = _prepare(upload, slot)
    if files.get('image') and 1 not in incoming and getattr(product, 'image', None):
        incoming[1] = None  # already stored on product.image by the serializer
    clears = _clear_slots(data.get('clear_photos'))
    featured_raw = data.get('featured_slot', None)
    featured = _parse_slot(featured_raw) if featured_raw not in (None, '') else None
    if not incoming and not clears and featured is None:
        return

    with transaction.atomic():
        if (
            product.image
            and 1 not in incoming
            and not ProductPhoto.objects.filter(product=product, slot=1).exists()
        ):
            ProductPhoto.objects.create(product=product, slot=1, image=product.image)
        if incoming.get(1) is None and 1 in incoming and product.image:
            photo, _created = ProductPhoto.objects.get_or_create(
                product=product,
                slot=1,
                defaults={'image': product.image},
            )
            if not _created:
                photo.image = product.image
                photo.save(update_fields=['image'])
        for slot, prepared in incoming.items():
            if prepared is None:
                continue
            photo, _created = ProductPhoto.objects.get_or_create(
                product=product,
                slot=slot,
                defaults={'image': prepared},
            )
            if not _created:
                photo.image = prepared
                photo.save(update_fields=['image'])
        if clears:
            ProductPhoto.objects.filter(product=product, slot__in=clears).delete()
        if not ProductPhoto.objects.filter(product=product).exists() and product.image and not clears:
            ProductPhoto.objects.get_or_create(
                product=product,
                slot=1,
                defaults={'image': product.image},
            )
        _sync_featured(product, featured)


def _sync_featured(product, featured: int | None) -> None:
    """
    Point the product at the chosen view.

    Args:
        product: Product with photos loaded from the database.
        featured: Requested slot 1–4, or None to keep the current slot.

    Returns:
        None. Writes ``featured_slot`` and ``image``.
    """
    photos = list(ProductPhoto.objects.filter(product=product).order_by('slot'))
    if not photos:
        if featured:
            product.featured_slot = featured
            product.image = None
            product.save(update_fields=['featured_slot', 'image'])
        return
    slot = featured or int(product.featured_slot or 1)
    chosen = next((photo for photo in photos if photo.slot == slot), None)
    if chosen is None:
        chosen = photos[0]
    product.featured_slot = chosen.slot
    product.image = chosen.image
    product.save(update_fields=['featured_slot', 'image'])
