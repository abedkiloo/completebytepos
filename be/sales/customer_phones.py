"""Normalize and enforce unique customer phones (same duka must not register twice)."""

from __future__ import annotations

from django.db.models import Count, Q

from sales.models import Customer
from utils.phone import PhoneNumberError, normalize_phone_number


def normalized_customer_phone(raw) -> str:
    """Return stored MSISDN or '' when blank/invalid."""
    try:
        return normalize_phone_number(raw or '')
    except PhoneNumberError:
        return ''


def customers_with_phone(phone: str, *, exclude_id=None):
    """
    Active customers that share this phone (any common Kenya formatting).

    Matches 07…, 2547…, and +2547… forms against normalized digits.
    """
    key = normalized_customer_phone(phone)
    if not key:
        return Customer.objects.none()

    national = key[3:] if key.startswith('254') and len(key) == 12 else key
    forms = {
        key,
        national,
        f'0{national}' if national else '',
        f'+{key}',
        f'+0{national}' if national else '',
    }
    forms.discard('')
    qs = Customer.objects.filter(is_active=True, phone__in=forms)
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    # Also catch spaced/odd stored values that still normalize to the same key.
    extras = (
        Customer.objects.filter(is_active=True)
        .exclude(phone='')
        .exclude(pk__in=qs.values_list('pk', flat=True))
        .filter(phone__icontains=national[-9:] if len(national) >= 9 else national)
        .only('id', 'phone')
    )
    if exclude_id is not None:
        extras = extras.exclude(pk=exclude_id)
    extra_ids = [
        c.id for c in extras.iterator(chunk_size=200)
        if normalized_customer_phone(c.phone) == key
    ]
    if not extra_ids:
        return qs
    return Customer.objects.filter(pk__in=list(qs.values_list('pk', flat=True)) + extra_ids)


def duplicate_phone_error(phone: str, *, exclude_id=None) -> str | None:
    """Human message when another active duka already uses this phone."""
    others = customers_with_phone(phone, exclude_id=exclude_id)
    other = others.select_related().first()
    if other is None:
        return None
    label = (other.name or other.customer_code or f'#{other.pk}').strip()
    return (
        f'This phone is already used by {label}. '
        'Open that duka instead of registering again.'
    )


def find_duplicate_phone_groups(*, include_inactive: bool = False) -> list[dict]:
    """
    Groups of customers sharing the same normalized phone.

    Each group: {phone, customer_ids, keep_id, deactivate_ids}.
    keep_id prefers most sales, then oldest, then lowest id.
    """
    qs = Customer.objects.exclude(phone='').exclude(phone__isnull=True)
    if not include_inactive:
        qs = qs.filter(is_active=True)

    by_phone: dict[str, list[Customer]] = {}
    for customer in qs.annotate(sale_count=Count('sales')).order_by('id'):
        key = normalized_customer_phone(customer.phone)
        if not key:
            continue
        by_phone.setdefault(key, []).append(customer)

    groups = []
    for phone, members in sorted(by_phone.items()):
        if len(members) < 2:
            continue
        ranked = sorted(
            members,
            key=lambda c: (
                -int(getattr(c, 'sale_count', 0) or 0),
                c.created_at or c.id,
                c.id,
            ),
        )
        keep = ranked[0]
        deactivate = ranked[1:]
        groups.append({
            'phone': phone,
            'customer_ids': [c.id for c in ranked],
            'keep_id': keep.id,
            'keep_name': keep.name,
            'deactivate_ids': [c.id for c in deactivate],
            'deactivate_names': [c.name for c in deactivate],
        })
    return groups
