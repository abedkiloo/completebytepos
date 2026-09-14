from rest_framework.exceptions import ValidationError

from .config import MIN_SITE_MEDIA
from .models import CustomerSite


class SiteFinalizeError(ValidationError):
    """Raised when a site cannot leave draft."""


def assert_can_finalize(site: CustomerSite, *, min_media: int = MIN_SITE_MEDIA) -> None:
    """
    Hard rule: finalized sites need confirmed pin + ≥ min_media photos + customer.
    """
    errors = {}
    if site.latitude is None or site.longitude is None:
        errors['location'] = 'Map pin (latitude and longitude) is required.'
    if site.customer_id is None:
        errors['customer'] = 'Customer is required before finalize.'
    media_count = site.media.count()
    if media_count < min_media:
        errors['media'] = (
            f'At least {min_media} site photo(s) required '
            f'(have {media_count}).'
        )
    if errors:
        raise SiteFinalizeError(errors)


def finalize_site(site: CustomerSite, *, min_media: int = MIN_SITE_MEDIA) -> CustomerSite:
    assert_can_finalize(site, min_media=min_media)
    site.status = CustomerSite.STATUS_FINALIZED
    site.save(update_fields=['status', 'updated_at'])
    return site
