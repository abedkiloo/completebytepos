"""
Default / editable sales-agent commission template (daily bands).

Matches Omuwenga Sales Agent Commission Structure:
daily fixed commission by sales band + transport incentive.
Admins can change the stored template; this module supplies the defaults
and pure calculation helpers (no ORM).
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any

from payroll.adapters.bonus import money

# Omuwenga Suppliers — Sales Agent Commission Structure (starting default).
DEFAULT_COMMISSION_TEMPLATE: dict[str, Any] = {
    'scheme': 'daily_bands',
    'bands': [
        {'min': '0', 'max': '12499.99', 'commission': '0'},
        {'min': '12500', 'max': '19999.99', 'commission': '500'},
        {'min': '20000', 'max': '31999.99', 'commission': '1000'},
        {'min': '32000', 'max': '39999.99', 'commission': '2000'},
        {'min': '40000', 'max': '49999.99', 'commission': '3500'},
        {'min': '50000', 'max': None, 'commission': '4000'},
    ],
    'transport': {
        'min_sales': '5000',
        'amount': '200',
    },
    # Commission-only: matching product lines stay on sales screens; they just
    # do not count toward the daily award base. Empty keywords or
    # ``exclude_products_from_commission: false`` turns this off.
    'exclude_products_from_commission': True,
    'exclude_product_keywords': ['zip', 'sofa cup holder'],
    'field_only': True,
    'require_full_payment_same_day': True,
}


def _dec(value, default: str = '0') -> Decimal:
    try:
        if value is None or value == '':
            return Decimal(default)
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def normalize_commission_template(raw) -> dict[str, Any]:
    """
    Normalize a stored or posted commission template.

    Args:
        raw: Mapping or None; missing keys fall back to DEFAULT.

    Returns:
        Deep-copied template with Decimal-friendly string amounts and
        ``scheme`` of ``daily_bands`` or ``percent`` (legacy).
    """
    base = deepcopy(DEFAULT_COMMISSION_TEMPLATE)
    if not isinstance(raw, dict):
        return base

    scheme = str(raw.get('scheme') or base['scheme']).strip().lower()
    if scheme not in ('daily_bands', 'percent'):
        scheme = 'daily_bands'
    base['scheme'] = scheme

    bands_in = raw.get('bands')
    if isinstance(bands_in, list) and bands_in:
        bands = []
        for row in bands_in:
            if not isinstance(row, dict):
                continue
            bands.append(
                {
                    'min': str(_dec(row.get('min'))),
                    'max': None
                    if row.get('max') in (None, '', 'null')
                    else str(_dec(row.get('max'))),
                    'commission': str(money(_dec(row.get('commission')))),
                }
            )
        if bands:
            bands.sort(key=lambda b: _dec(b['min']))
            base['bands'] = bands

    transport_in = raw.get('transport')
    if isinstance(transport_in, dict):
        base['transport'] = {
            'min_sales': str(_dec(transport_in.get('min_sales'), '5000')),
            'amount': str(money(_dec(transport_in.get('amount'), '200'))),
        }

    if 'exclude_products_from_commission' in raw:
        base['exclude_products_from_commission'] = bool(
            raw.get('exclude_products_from_commission')
        )

    if 'exclude_product_keywords' in raw:
        keywords = raw.get('exclude_product_keywords')
        if isinstance(keywords, str):
            keywords = [part.strip() for part in keywords.split(',')]
        if isinstance(keywords, list):
            cleaned = [str(k).strip().lower() for k in keywords if str(k).strip()]
            base['exclude_product_keywords'] = cleaned
        elif keywords in (None, ''):
            base['exclude_product_keywords'] = []

    if 'field_only' in raw:
        base['field_only'] = bool(raw.get('field_only'))
    if 'require_full_payment_same_day' in raw:
        base['require_full_payment_same_day'] = bool(
            raw.get('require_full_payment_same_day')
        )
    if scheme == 'percent' and raw.get('percent_rate') is not None:
        base['percent_rate'] = str(_dec(raw.get('percent_rate'), '0.03'))
    return base


def commission_for_qualifying_sales(
    qualifying_sales: Decimal,
    template: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Pick the daily commission band for a day's qualifying sales.

    Args:
        qualifying_sales: Non-negative day total (KES).
        template: Normalized template (defaults to PDF starter).

    Returns:
        Dict with ``commission``, ``band_min``, ``band_max``, ``band_index``,
        and ``next_band`` (or None at top).
    """
    tpl = normalize_commission_template(template)
    sales = money(qualifying_sales)
    if sales < 0:
        sales = Decimal('0.00')

    bands = tpl['bands']
    chosen_idx = 0
    chosen = bands[0]
    for idx, band in enumerate(bands):
        lo = _dec(band['min'])
        hi = band['max']
        if sales < lo:
            break
        if hi is None or sales <= _dec(hi):
            chosen_idx = idx
            chosen = band
            break
        chosen_idx = idx
        chosen = band

    commission = money(_dec(chosen['commission']))
    next_band = None
    if chosen_idx + 1 < len(bands):
        nxt = bands[chosen_idx + 1]
        next_min = _dec(nxt['min'])
        gap = money(max(Decimal('0.00'), next_min - sales))
        next_band = {
            'min': str(next_min),
            'commission': str(money(_dec(nxt['commission']))),
            'sales_to_go': str(gap),
        }

    return {
        'commission': commission,
        'band_min': str(_dec(chosen['min'])),
        'band_max': None if chosen['max'] is None else str(_dec(chosen['max'])),
        'band_index': chosen_idx,
        'next_band': next_band,
    }


def transport_for_qualifying_sales(
    qualifying_sales: Decimal,
    template: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Transport incentive for a working day (≥ min sales → fixed amount).

    Args:
        qualifying_sales: Day qualifying sales (KES).
        template: Normalized template.

    Returns:
        Dict with ``qualified`` (bool), ``amount`` (Decimal), ``min_sales``.
    """
    tpl = normalize_commission_template(template)
    transport = tpl['transport']
    min_sales = money(_dec(transport['min_sales'], '5000'))
    amount = money(_dec(transport['amount'], '200'))
    sales = money(qualifying_sales)
    qualified = sales >= min_sales
    return {
        'qualified': qualified,
        'amount': amount if qualified else Decimal('0.00'),
        'min_sales': min_sales,
    }


def product_name_excluded(name: str, template: dict[str, Any] | None = None) -> bool:
    """
    True when a product line must not count toward commission qualifying sales.

    This never removes the product from POS, sales history, or agent dashboards —
    it only skips the line when building the award base. Off when
    ``exclude_products_from_commission`` is false or the keyword list is empty.

    Args:
        name: Product display name (any case; empty → not excluded).
        template: Normalized template with keywords and the exclude toggle.

    Returns:
        bool.
    """
    # Hot path: month scoring calls this per line — skip deepcopy when already
    # normalized (has the toggle key from DEFAULT / normalize_commission_template).
    if isinstance(template, dict) and 'exclude_products_from_commission' in template:
        tpl = template
    else:
        tpl = normalize_commission_template(template)
    if not tpl.get('exclude_products_from_commission', True):
        return False
    hay = (name or '').strip().lower()
    if not hay:
        return False
    for keyword in tpl.get('exclude_product_keywords') or []:
        if keyword and keyword in hay:
            return True
    return False
