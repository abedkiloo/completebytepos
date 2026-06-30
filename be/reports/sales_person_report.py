"""
Sales performance by staff member (cashier) for commission / reward proof.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional, Tuple

from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from sales.models import Sale, SaleRefund

from .services import resolve_period


def resolve_sales_person_period(request) -> Tuple[Optional[datetime], Optional[datetime], str]:
    """
    Prefer ``?month=YYYY-MM`` for month-end reports; fall back to resolve_period().
    """
    params = getattr(request, 'query_params', None) or getattr(request, 'GET', {})
    month = (params.get('month') or '').strip()
    if month:
        try:
            year_str, month_str = month.split('-', 1)
            year, mon = int(year_str), int(month_str)
            if not (1 <= mon <= 12):
                raise ValueError('invalid month')
            start = timezone.make_aware(datetime(year, mon, 1))
            if mon == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, mon + 1, 1)
            end = timezone.make_aware(end_date) - timedelta(microseconds=1)
            label = month
            return start, end, label
        except (TypeError, ValueError):
            pass

    start, end, label = resolve_period(request)
    if label == 'custom' and start and end:
        label = f"{start.date().isoformat()}_{end.date().isoformat()}"
    return start, end, label


def _display_name(user: Optional[User]) -> str:
    if user is None:
        return 'Unassigned'
    full = user.get_full_name().strip()
    return full or user.username


def _decimal_float(value) -> float:
    if value is None:
        return 0.0
    return float(value)


class SalesPersonReportService:
    @staticmethod
    def build(request) -> dict[str, Any]:
        start, end, label = resolve_sales_person_period(request)
        params = getattr(request, 'query_params', None) or getattr(request, 'GET', {})
        cashier_id = params.get('cashier_id') or params.get('user_id')
        try:
            cashier_id_int = int(cashier_id) if cashier_id not in (None, '', 'all') else None
        except (TypeError, ValueError):
            cashier_id_int = None

        sales_qs = Sale.objects.filter(status='completed').select_related('cashier', 'served_by')
        if start:
            sales_qs = sales_qs.filter(occurred_at__gte=start)
        if end:
            sales_qs = sales_qs.filter(occurred_at__lte=end)
        if cashier_id_int:
            sales_qs = sales_qs.filter(
                Q(served_by_id=cashier_id_int)
                | Q(served_by__isnull=True, cashier_id=cashier_id_int)
            )

        staff_rows = list(
            sales_qs.annotate(staff_id=Coalesce('served_by_id', 'cashier_id'))
            .values('staff_id')
            .annotate(
                sales_count=Count('id', distinct=True),
                gross_sales=Sum('total'),
                items_sold=Sum('items__quantity'),
            )
            .order_by('-gross_sales')
        )

        user_ids = [row['staff_id'] for row in staff_rows if row['staff_id']]
        users_by_id = {u.id: u for u in User.objects.filter(id__in=user_ids)}

        refund_qs = SaleRefund.objects.filter(sale__status='completed').select_related(
            'sale', 'sale__cashier'
        )
        if start:
            refund_qs = refund_qs.filter(created_at__gte=start)
        if end:
            refund_qs = refund_qs.filter(created_at__lte=end)
        if cashier_id_int:
            refund_qs = refund_qs.filter(
                Q(sale__served_by_id=cashier_id_int)
                | Q(sale__served_by__isnull=True, sale__cashier_id=cashier_id_int)
            )

        refund_by_staff = {
            row['staff_id']: row
            for row in refund_qs.annotate(
                staff_id=Coalesce('sale__served_by_id', 'sale__cashier_id')
            )
            .values('staff_id')
            .annotate(
                refunds_count=Count('id'),
                refunds_total=Sum('amount'),
            )
        }

        staff = []
        totals = {
            'sales_count': 0,
            'gross_sales': 0.0,
            'refunds_count': 0,
            'refunds_total': 0.0,
            'net_sales': 0.0,
            'items_sold': 0,
        }

        for row in staff_rows:
            sid = row['staff_id']
            gross = _decimal_float(row['gross_sales'])
            count = row['sales_count'] or 0
            items = int(row['items_sold'] or 0)
            ref = refund_by_staff.get(sid, {})
            ref_count = ref.get('refunds_count') or 0
            ref_total = _decimal_float(ref.get('refunds_total'))
            net = gross - ref_total
            avg_ticket = (gross / count) if count else 0.0

            user_stub = users_by_id.get(sid) if sid else None
            name = _display_name(user_stub) if user_stub else 'Unassigned'

            staff.append({
                'user_id': sid,
                'username': user_stub.username if user_stub else '',
                'display_name': name,
                'sales_count': count,
                'gross_sales': round(gross, 2),
                'refunds_count': ref_count,
                'refunds_total': round(ref_total, 2),
                'net_sales': round(net, 2),
                'items_sold': items,
                'avg_ticket': round(avg_ticket, 2),
            })

            totals['sales_count'] += count
            totals['gross_sales'] += gross
            totals['refunds_count'] += ref_count
            totals['refunds_total'] += ref_total
            totals['net_sales'] += net
            totals['items_sold'] += items

        for key in ('gross_sales', 'refunds_total', 'net_sales'):
            totals[key] = round(totals[key], 2)

        detail = []
        if cashier_id_int or len(staff) == 1:
            target_id = cashier_id_int or (staff[0]['user_id'] if len(staff) == 1 else None)
            if target_id is not None:
                detail_qs = sales_qs.filter(
                    Q(served_by_id=target_id)
                    | Q(served_by__isnull=True, cashier_id=target_id)
                ).order_by('-occurred_at')[:200]
            elif target_id is None and staff and staff[0]['user_id'] is None:
                detail_qs = sales_qs.filter(
                    served_by__isnull=True, cashier__isnull=True
                ).order_by('-occurred_at')[:200]
            else:
                detail_qs = sales_qs.none()

            sale_ids = [s.id for s in detail_qs]
            refunded_map = {
                r['sale_id']: _decimal_float(r['total'])
                for r in SaleRefund.objects.filter(sale_id__in=sale_ids)
                .values('sale_id')
                .annotate(total=Sum('amount'))
            }

            for sale in detail_qs:
                refunded = refunded_map.get(sale.id, 0.0)
                detail.append({
                    'sale_id': sale.id,
                    'sale_number': sale.sale_number,
                    'date': sale.occurred_at.isoformat() if sale.occurred_at else None,
                    'recorded_at': sale.created_at.isoformat() if sale.created_at else None,
                    'is_late_entry': sale.is_late_entry,
                    'served_by_name': (
                        _display_name(sale.served_by) if sale.served_by else _display_name(sale.cashier)
                    ),
                    'payment_method': sale.payment_method,
                    'total': _decimal_float(sale.total),
                    'refunded': round(refunded, 2),
                    'net': round(_decimal_float(sale.total) - refunded, 2),
                    'refund_status': sale.refund_status,
                })

        period_display = label
        if len(label) == 7 and '-' in label:
            try:
                dt = datetime.strptime(label, '%Y-%m')
                period_display = dt.strftime('%B %Y')
            except ValueError:
                pass

        return {
            'period': label,
            'period_display': period_display,
            'date_from': start.date().isoformat() if start else None,
            'date_to': end.date().isoformat() if end else None,
            'cashier_id': cashier_id_int,
            'generated_at': timezone.now().isoformat(),
            'summary': totals,
            'staff': staff,
            'transactions': detail,
            'note': (
                'Net sales = completed sales total minus refunds recorded in this period. '
                'Commission is not calculated here — use this report as proof for your own reward policy.'
            ),
        }

    @staticmethod
    def to_csv(payload: dict[str, Any]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Sales staff performance report'])
        writer.writerow(['Period', payload.get('period_display') or payload.get('period', '')])
        writer.writerow(['From', payload.get('date_from') or ''])
        writer.writerow(['To', payload.get('date_to') or ''])
        writer.writerow(['Generated', payload.get('generated_at') or ''])
        writer.writerow([])

        summary = payload.get('summary') or {}
        writer.writerow(['Store totals'])
        writer.writerow(['Sales count', summary.get('sales_count', 0)])
        writer.writerow(['Gross sales', summary.get('gross_sales', 0)])
        writer.writerow(['Refunds', summary.get('refunds_total', 0)])
        writer.writerow(['Net sales', summary.get('net_sales', 0)])
        writer.writerow([])

        writer.writerow([
            'Staff name',
            'Username',
            'Sales count',
            'Gross sales',
            'Refunds count',
            'Refunds total',
            'Net sales',
            'Items sold',
            'Avg ticket',
        ])
        for row in payload.get('staff') or []:
            writer.writerow([
                row.get('display_name', ''),
                row.get('username', ''),
                row.get('sales_count', 0),
                row.get('gross_sales', 0),
                row.get('refunds_count', 0),
                row.get('refunds_total', 0),
                row.get('net_sales', 0),
                row.get('items_sold', 0),
                row.get('avg_ticket', 0),
            ])

        transactions = payload.get('transactions') or []
        if transactions:
            writer.writerow([])
            writer.writerow(['Transaction detail'])
            writer.writerow([
                'Sale #',
                'Date',
                'Payment',
                'Sale total',
                'Refunded',
                'Net',
                'Refund status',
            ])
            for tx in transactions:
                writer.writerow([
                    tx.get('sale_number', ''),
                    tx.get('date', ''),
                    tx.get('payment_method', ''),
                    tx.get('total', 0),
                    tx.get('refunded', 0),
                    tx.get('net', 0),
                    tx.get('refund_status', ''),
                ])

        return output.getvalue()
