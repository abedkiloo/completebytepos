"""
Customer site finalize rules for field visits.

Public entry points:
    - ``assert_can_finalize`` / ``finalize_site`` — draft → finalized transition

Side effects: ``finalize_site`` updates ``CustomerSite.status`` only; no orders or stock.
"""

from rest_framework.exceptions import ValidationError

from .config import MIN_SITE_MEDIA
from .models import CustomerSite


class SiteFinalizeError(ValidationError):
    """Validation failure when a site cannot leave ``STATUS_DRAFT``."""


def assert_can_finalize(site: CustomerSite, *, min_media: int = MIN_SITE_MEDIA) -> None:
    """
    Verify a site meets finalize preconditions.

    Args:
        site: Site to check; must have map pin and linked customer.
        min_media: Minimum ``SiteMedia`` count when > 0; default from
            ``MIN_SITE_MEDIA`` (0 = photos optional).

    Returns:
        None.

    Raises:
        SiteFinalizeError: Missing pin, customer, or insufficient photos.
    """
    errors = {}
    if site.latitude is None or site.longitude is None:
        errors['location'] = 'Map pin (latitude and longitude) is required.'
    if site.customer_id is None:
        errors['customer'] = 'Customer is required before finalize.'
    if min_media > 0:
        media_count = site.media.count()
        if media_count < min_media:
            errors['media'] = (
                f'At least {min_media} site photo(s) required '
                f'(have {media_count}).'
            )
    if errors:
        raise SiteFinalizeError(errors)


def finalize_site(site: CustomerSite, *, min_media: int = MIN_SITE_MEDIA) -> CustomerSite:
    """
    Mark a customer site finalized after validation.

    Args:
        site: Site in ``STATUS_DRAFT`` (or re-finalize is a no-op on status value).
        min_media: Passed to ``assert_can_finalize``.

    Returns:
        The same ``CustomerSite`` with ``status=STATUS_FINALIZED``.

    Raises:
        SiteFinalizeError: Preconditions fail.

    Side effects:
        Persists ``status`` and ``updated_at`` only.
    """
    assert_can_finalize(site, min_media=min_media)
    site.status = CustomerSite.STATUS_FINALIZED
    site.save(update_fields=['status', 'updated_at'])
    return site
