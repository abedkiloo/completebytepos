"""
Customer purchase intelligence — lightweight, denormalized tiers for lists & ML later.

Design (ML-engineer constraints):
- Hot path is O(1) indexed fields on Customer — never aggregate sales on list/read.
- Refresh only when a sale completes (or via backfill command).
- Two primary engagement tiers the business asked for:
    * prospect — in the system, never bought from Omuwenga
    * buyer    — at least one completed sale
- Buyers get a deterministic RFM-lite segment (new / active / at_risk / dormant /
  champion) so we can later swap rule thresholds for a scored model without
  changing API shapes.

Performance: one aggregate query per customer refresh; list filters use indexes.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from django.db import transaction
from django.db.models import Count, Max, Min, Sum
from django.utils import timezone

ENGAGEMENT_PROSPECT = 'prospect'
ENGAGEMENT_BUYER = 'buyer'
ENGAGEMENT_TIERS = (ENGAGEMENT_PROSPECT, ENGAGEMENT_BUYER)

SEGMENT_NONE = 'none'
SEGMENT_NEW = 'new'
SEGMENT_ACTIVE = 'active'
SEGMENT_AT_RISK = 'at_risk'
SEGMENT_DORMANT = 'dormant'
SEGMENT_CHAMPION = 'champion'
BUYER_SEGMENTS = (
    SEGMENT_NONE,
    SEGMENT_NEW,
    SEGMENT_ACTIVE,
    SEGMENT_AT_RISK,
    SEGMENT_DORMANT,
    SEGMENT_CHAMPION,
)

# Tunable rule thresholds — swap for model scores later without schema churn.
ACTIVE_WITHIN_DAYS = 30
AT_RISK_WITHIN_DAYS = 90
CHAMPION_MIN_PURCHASES = 5
CHAMPION_MIN_LTV = Decimal('10000.00')


def classify_buyer_segment(
    *,
    purchase_count: int,
    lifetime_sales_value: Decimal,
    last_purchased_at,
    now=None,
) -> str:
    """Deterministic RFM-lite label for a buyer (or none for prospects)."""
    if purchase_count <= 0 or last_purchased_at is None:
        return SEGMENT_NONE

    now = now or timezone.now()
    last = last_purchased_at
    if timezone.is_naive(last):
        last = timezone.make_aware(last, timezone.get_current_timezone())
    age_days = (now - last).days
    ltv = Decimal(str(lifetime_sales_value or 0))

    if (
        purchase_count >= CHAMPION_MIN_PURCHASES
        and ltv >= CHAMPION_MIN_LTV
        and age_days <= ACTIVE_WITHIN_DAYS
    ):
        return SEGMENT_CHAMPION
    if purchase_count == 1 and age_days <= ACTIVE_WITHIN_DAYS:
        return SEGMENT_NEW
    if age_days <= ACTIVE_WITHIN_DAYS:
        return SEGMENT_ACTIVE
    if age_days <= AT_RISK_WITHIN_DAYS:
        return SEGMENT_AT_RISK
    return SEGMENT_DORMANT


def engagement_tier_for_count(purchase_count: int) -> str:
    return ENGAGEMENT_BUYER if purchase_count > 0 else ENGAGEMENT_PROSPECT


def compute_purchase_stats(customer_id: int) -> dict[str, Any]:
    """Aggregate completed sales for one customer (used only on refresh/backfill)."""
    from sales.models import Sale

    row = Sale.objects.filter(
        customer_id=customer_id,
        status='completed',
    ).exclude(refund_status='refunded').aggregate(
        purchase_count=Count('id'),
        lifetime_sales_value=Sum('total'),
        first_purchased_at=Min('occurred_at'),
        last_purchased_at=Max('occurred_at'),
    )
    count = int(row['purchase_count'] or 0)
    ltv = Decimal(str(row['lifetime_sales_value'] or 0)).quantize(Decimal('0.01'))
    return {
        'purchase_count': count,
        'lifetime_sales_value': ltv,
        'first_purchased_at': row['first_purchased_at'],
        'last_purchased_at': row['last_purchased_at'],
        'engagement_tier': engagement_tier_for_count(count),
        'buyer_segment': classify_buyer_segment(
            purchase_count=count,
            lifetime_sales_value=ltv,
            last_purchased_at=row['last_purchased_at'],
        ),
    }


@transaction.atomic
def refresh_customer_purchase_intelligence(customer_id: Optional[int]) -> Optional[dict]:
    """
    Recompute denormalized tier + RFM-lite features for one customer.

    Safe no-op when customer_id is missing. Call after a sale completes.
    """
    if not customer_id:
        return None

    from sales.models import Customer

    stats = compute_purchase_stats(customer_id)
    updated = Customer.objects.filter(pk=customer_id).update(
        engagement_tier=stats['engagement_tier'],
        buyer_segment=stats['buyer_segment'],
        purchase_count=stats['purchase_count'],
        lifetime_sales_value=stats['lifetime_sales_value'],
        first_purchased_at=stats['first_purchased_at'],
        last_purchased_at=stats['last_purchased_at'],
        intelligence_updated_at=timezone.now(),
    )
    if not updated:
        return None
    return stats


def on_sale_completed(sale) -> None:
    """Hook for sale completion paths — keeps list filters accurate without cron."""
    customer_id = getattr(sale, 'customer_id', None)
    if not customer_id:
        return
    if getattr(sale, 'status', None) != 'completed':
        return
    refresh_customer_purchase_intelligence(customer_id)


def backfill_customer_intelligence(*, batch_size: int = 500) -> dict[str, int]:
    """Full recompute for all customers (ops / migration heal)."""
    from sales.models import Customer

    processed = 0
    buyers = 0
    qs = Customer.objects.order_by('id').only('id')
    batch: list[int] = []
    for cid in qs.values_list('id', flat=True).iterator(chunk_size=batch_size):
        batch.append(cid)
        if len(batch) >= batch_size:
            for customer_id in batch:
                stats = refresh_customer_purchase_intelligence(customer_id)
                processed += 1
                if stats and stats['engagement_tier'] == ENGAGEMENT_BUYER:
                    buyers += 1
            batch = []
    for customer_id in batch:
        stats = refresh_customer_purchase_intelligence(customer_id)
        processed += 1
        if stats and stats['engagement_tier'] == ENGAGEMENT_BUYER:
            buyers += 1
    return {
        'processed': processed,
        'buyers': buyers,
        'prospects': processed - buyers,
    }


def segment_label(segment: str) -> str:
    return {
        SEGMENT_NONE: 'No purchases',
        SEGMENT_NEW: 'New buyer',
        SEGMENT_ACTIVE: 'Active',
        SEGMENT_AT_RISK: 'At risk',
        SEGMENT_DORMANT: 'Dormant',
        SEGMENT_CHAMPION: 'Champion',
    }.get(segment, segment)


def tier_label(tier: str) -> str:
    return {
        ENGAGEMENT_BUYER: 'Has bought from Omuwenga',
        ENGAGEMENT_PROSPECT: 'Registered only',
    }.get(tier, tier)
