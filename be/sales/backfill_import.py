"""Bulk CSV import for past sales."""

from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from products.models import Product
from sales.backfill_policy import (
    backfill_requires_approval,
    validate_backfill_occurred_at,
    validate_backfill_reason,
    validate_backfill_stock_warnings,
)


CSV_TEMPLATE_HEADER = [
    'sale_reference',
    'occurred_at',
    'backfill_reason',
    'product_sku',
    'quantity',
    'unit_price',
    'payment_method',
    'amount_paid',
    'sale_type',
    'payment_reference',
    'customer_id',
    'served_by_id',
]


def backfill_import_template_csv() -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_TEMPLATE_HEADER)
    writer.writerow(
        [
            'SALE-001',
            '2026-06-20T10:00:00',
            'Sold offline during power outage',
            'SKU-001',
            '2',
            '100.00',
            'cash',
            '200.00',
            'pos',
            '',
            '',
            '',
        ]
    )
    writer.writerow(
        [
            'SALE-001',
            '2026-06-20T10:00:00',
            'Sold offline during power outage',
            'SKU-002',
            '1',
            '50.00',
            'cash',
            '200.00',
            'pos',
            '',
            '',
            '',
        ]
    )
    return output.getvalue()


def _decode_csv_file(csv_file) -> str:
    try:
        return csv_file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        csv_file.seek(0)
        return csv_file.read().decode('latin-1')


def _parse_decimal(raw, field: str, row_num: int) -> Decimal:
    text = str(raw or '').strip()
    if not text:
        raise ValueError(f'Row {row_num}: {field} is required')
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'Row {row_num}: invalid {field}') from exc


def _parse_row_groups(reader) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    groups: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    for row_num, row in enumerate(reader, start=2):
        try:
            sku = (row.get('product_sku') or row.get('sku') or '').strip()
            product_id_raw = (row.get('product_id') or '').strip()
            if not sku and not product_id_raw:
                errors.append(f'Row {row_num}: product_sku or product_id is required')
                continue

            occurred_raw = (row.get('occurred_at') or '').strip()
            if not occurred_raw:
                errors.append(f'Row {row_num}: occurred_at is required')
                continue
            occurred_at = parse_datetime(occurred_raw)
            if occurred_at is None:
                errors.append(f'Row {row_num}: invalid occurred_at')
                continue
            if timezone.is_naive(occurred_at):
                occurred_at = timezone.make_aware(occurred_at)

            reason = (row.get('backfill_reason') or '').strip()
            if len(reason) < 10:
                errors.append(f'Row {row_num}: backfill_reason must be at least 10 characters')
                continue

            qty = int(str(row.get('quantity') or '0').strip() or '0')
            if qty <= 0:
                errors.append(f'Row {row_num}: quantity must be positive')
                continue

            unit_price = _parse_decimal(row.get('unit_price'), 'unit_price', row_num)
            amount_paid = _parse_decimal(row.get('amount_paid'), 'amount_paid', row_num)

            product = None
            if product_id_raw:
                product = Product.objects.filter(pk=int(product_id_raw)).first()
            elif sku:
                product = Product.objects.filter(sku=sku).first()
            if not product:
                errors.append(f'Row {row_num}: product not found ({sku or product_id_raw})')
                continue

            sale_ref = (row.get('sale_reference') or '').strip() or f'__row_{row_num}'
            group = groups.setdefault(
                sale_ref,
                {
                    'occurred_at': occurred_at,
                    'backfill_reason': reason,
                    'sale_type': (row.get('sale_type') or 'pos').strip() or 'pos',
                    'payment_method': (row.get('payment_method') or 'cash').strip() or 'cash',
                    'payment_reference': (row.get('payment_reference') or '').strip(),
                    'amount_paid': amount_paid,
                    'customer_id': (row.get('customer_id') or '').strip() or None,
                    'served_by_id': (row.get('served_by_id') or '').strip() or None,
                    'items': [],
                    '_row_nums': [],
                },
            )

            if group['occurred_at'] != occurred_at:
                errors.append(f'Row {row_num}: occurred_at must match other rows in {sale_ref}')
                continue
            if group['backfill_reason'] != reason:
                errors.append(f'Row {row_num}: backfill_reason must match other rows in {sale_ref}')
                continue

            group['items'].append(
                {
                    'product_id': product.id,
                    'quantity': qty,
                    'unit_price': unit_price,
                }
            )
            group['_row_nums'].append(row_num)
        except ValueError as exc:
            errors.append(str(exc))
        except Exception as exc:
            errors.append(f'Row {row_num}: {exc}')

    return groups, errors


@transaction.atomic
def import_backfill_sales_from_csv(
    csv_file,
    *,
    user,
    request=None,
    acknowledge_stock_warnings: bool = False,
) -> Dict[str, Any]:
    from approvals.backfill_integration import queue_sale_backfill
    from sales.services import SaleService

    decoded = _decode_csv_file(csv_file)
    lines = [line for line in decoded.splitlines() if line.strip() and not line.strip().startswith('#')]
    if not lines:
        return {
            'created': 0,
            'pending': 0,
            'errors': ['CSV file is empty or contains only comments'],
            'sales': [],
        }

    reader = csv.DictReader(lines)
    groups, errors = _parse_row_groups(reader)
    if not groups and errors:
        return {'created': 0, 'pending': 0, 'errors': errors, 'sales': []}

    service = SaleService()
    created = 0
    pending = 0
    sales_out: List[Dict[str, Any]] = []

    for sale_ref, group in groups.items():
        row_label = sale_ref if not sale_ref.startswith('__row_') else f'row {group["_row_nums"][0]}'
        try:
            validate_backfill_occurred_at(group['occurred_at'])
            validate_backfill_reason(group['backfill_reason'])
            validate_backfill_stock_warnings(
                group['occurred_at'],
                group['items'],
                acknowledged=acknowledge_stock_warnings,
            )

            payload = {
                'occurred_at': group['occurred_at'],
                'backfill_reason': group['backfill_reason'],
                'sale_type': group['sale_type'],
                'payment_method': group['payment_method'],
                'payment_reference': group['payment_reference'],
                'amount_paid': group['amount_paid'],
                'items': group['items'],
                '_backfill': True,
            }
            if group['customer_id']:
                payload['customer_id'] = int(group['customer_id'])
            if group['served_by_id']:
                payload['served_by_id'] = int(group['served_by_id'])
            elif user is not None:
                payload['served_by_id'] = user.pk
            if group['sale_type'] == 'normal':
                payload['create_invoice'] = True

            validated_items = service.validate_sale_items(
                payload['items'],
                check_stock=False,
                user=user,
            )
            subtotal = sum(item['subtotal'] for item in validated_items)
            payload['_preview_total'] = subtotal

            if backfill_requires_approval():
                if request is None:
                    raise ValidationError('Maker-checker import requires an HTTP request context.')
                queue_sale_backfill(request, payload)
                pending += 1
                sales_out.append({'sale_reference': row_label, 'status': 'pending'})
                continue

            result = service.create_sale_from_validated_data(payload, user, request)
            sale = result['sale']
            created += 1
            sales_out.append(
                {
                    'sale_reference': row_label,
                    'status': 'created',
                    'sale_id': sale.id,
                    'sale_number': sale.sale_number,
                }
            )
        except ValidationError as exc:
            if hasattr(exc, 'message_dict'):
                detail = exc.message_dict
                if 'stock_warnings' in detail:
                    errors.append(f'{row_label}: stock adjusted after sale date — confirm to continue')
                else:
                    flat = []
                    for val in detail.values():
                        if isinstance(val, list):
                            flat.extend(str(v) for v in val)
                        else:
                            flat.append(str(val))
                    errors.append(f'{row_label}: {"; ".join(flat)}')
            else:
                errors.append(f'{row_label}: {exc}')
        except Exception as exc:
            errors.append(f'{row_label}: {exc}')

    return {
        'created': created,
        'pending': pending,
        'errors': errors,
        'sales': sales_out,
    }
