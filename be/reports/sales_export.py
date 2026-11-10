"""
Analyst-grade Sales Excel: goods + quantity first, then payment/day summaries.

The legacy flatten of ``by_payment_method`` / ``daily_breakdown`` only shows
sale *counts* — this workbook puts product qty and revenue on sheet 1.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Optional

from django.http import HttpResponse

from reports.export import (
    CONTENT_TYPES,
    UnsupportedExportFormat,
    export_filename,
    normalize_export_format,
    sales_export_filename,
)
from utils.document_branding import brand_contact_line, brand_name_line


def is_sales_export_payload(payload: Any) -> bool:
    """
    Detect sales / sales-overview JSON shapes.

    Args:
        payload: Report response dict.

    Returns:
        True when payment breakdown plus goods or daily data is present.
    """
    if not isinstance(payload, dict):
        return False
    if 'by_payment_method' not in payload:
        return False
    return (
        'by_product' in payload
        or 'goods_sold' in payload
        or 'daily_breakdown' in payload
        or 'trend' in payload
    )


PRODUCT_HEADERS = [
    'Goods sold (product)',
    'SKU',
    'Category',
    'Quantity sold',
    'Revenue',
    'COGS',
    'Gross profit',
    'Margin %',
    'Sale line count',
]

PRODUCT_HEADERS_NO_COST = [
    'Goods sold (product)',
    'SKU',
    'Category',
    'Quantity sold',
    'Revenue',
    'Sale line count',
]

LINE_HEADERS = [
    'Sale number',
    'Sale date/time',
    'Goods sold',
    'SKU',
    'Quantity',
    'Unit price',
    'Line sale',
    'Unit cost',
    'Line COGS',
    'Line gross profit',
]

LINE_HEADERS_NO_COST = [
    'Sale number',
    'Sale date/time',
    'Goods sold',
    'SKU',
    'Quantity',
    'Unit price',
    'Line sale',
]


def _product_rows(payload: dict[str, Any], *, include_cost: bool = True) -> list[list[Any]]:
    """
    Goods-sold product roll-up rows.

    Args:
        payload: Sales payload with ``by_product`` / ``goods_sold``.
        include_cost: When False, omit COGS / margin columns (non-admin Excel).

    Returns:
        List of PRODUCT_HEADERS or PRODUCT_HEADERS_NO_COST-aligned rows.
    """
    rows = payload.get('by_product') or payload.get('goods_sold') or []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        base = [
            row.get('product') or row.get('product_name') or '',
            row.get('sku') or '',
            row.get('category') or '',
            row.get('quantity_sold'),
            row.get('revenue'),
        ]
        if include_cost:
            base.extend(
                [
                    row.get('cogs'),
                    row.get('gross_profit'),
                    row.get('margin_pct'),
                    row.get('sale_line_count'),
                ]
            )
        else:
            base.append(row.get('sale_line_count'))
        out.append(base)
    return out


def _line_rows(payload: dict[str, Any], *, include_cost: bool = True) -> list[list[Any]]:
    """
    Sale-line detail rows.

    Args:
        payload: Sales payload with ``sale_lines``.
        include_cost: When False, omit unit cost / line COGS columns.

    Returns:
        List of LINE_HEADERS or LINE_HEADERS_NO_COST-aligned rows.
    """
    out = []
    for row in payload.get('sale_lines') or []:
        if not isinstance(row, dict):
            continue
        occurred = row.get('sale_date') or ''
        if isinstance(occurred, str) and 'T' in occurred:
            occurred = occurred.replace('T', ' ')[:19]
        base = [
            row.get('sale_number') or '',
            occurred,
            row.get('product') or '',
            row.get('sku') or '',
            row.get('quantity'),
            row.get('unit_price'),
            row.get('line_sale'),
        ]
        if include_cost:
            base.extend(
                [
                    row.get('unit_cost'),
                    row.get('line_cogs'),
                    row.get('line_gross_profit'),
                ]
            )
        out.append(base)
    return out


def _payment_rows(payload: dict[str, Any]) -> list[list[Any]]:
    out = []
    for row in payload.get('by_payment_method') or []:
        if not isinstance(row, dict):
            continue
        method = row.get('payment_method') or row.get('method') or ''
        out.append([method, row.get('count'), row.get('total')])
    return out


def _daily_rows(payload: dict[str, Any]) -> list[list[Any]]:
    daily = payload.get('daily_breakdown') or payload.get('trend') or []
    out = []
    for row in daily:
        if not isinstance(row, dict):
            continue
        day = row.get('day') or row.get('date') or ''
        count = row.get('count') if 'count' in row else row.get('sales_count')
        total = row.get('total') if 'total' in row else row.get('revenue')
        out.append([day, count, total])
    return out


def _ticket_rows(payload: dict[str, Any]) -> list[list[Any]]:
    """Slim sale tickets — products text, no customer column."""
    out = []
    for row in payload.get('sales') or []:
        if not isinstance(row, dict):
            continue
        when = row.get('date') or ''
        if hasattr(when, 'isoformat'):
            when = when.isoformat().replace('T', ' ')[:19]
        elif isinstance(when, str) and 'T' in when:
            when = when.replace('T', ' ')[:19]
        out.append(
            [
                row.get('sale_number') or '',
                when,
                row.get('cashier') or '',
                row.get('products') or '',
                row.get('quantity') if 'quantity' in row else row.get('items'),
                row.get('total'),
                row.get('payment') or '',
                row.get('status') or '',
            ]
        )
    return out


TICKET_HEADERS = [
    'Sale number',
    'Date',
    'Cashier',
    'Products',
    'Quantity',
    'Total',
    'Payment',
    'Status',
]


def _summary_rows(payload: dict[str, Any], product_rows: list) -> list[list[Any]]:
    summary = payload.get('summary') if isinstance(payload.get('summary'), dict) else {}
    qty = sum(float(r[3] or 0) for r in product_rows)
    rev = sum(float(r[4] or 0) for r in product_rows)
    return [
        ['Brand', brand_name_line()],
        ['Contact', brand_contact_line()],
        ['Report', 'Sales — goods sold'],
        ['Period', payload.get('period') or ''],
        [],
        ['Sale count (tickets)', summary.get('total_sales') or summary.get('sales_count')],
        ['Gross revenue', summary.get('total_revenue') or summary.get('gross_revenue')],
        ['Items sold (units)', summary.get('total_items') or summary.get('items_sold')],
        ['Tax', summary.get('total_tax') or summary.get('tax')],
        ['Discount', summary.get('total_discount') or summary.get('discount')],
        [],
        ['Distinct products', len(product_rows)],
        ['Sum quantity (by product)', qty],
        ['Sum revenue (by product)', round(rev, 2)],
        ['Sale lines in workbook', len(payload.get('sale_lines') or [])],
        ['Sale lines truncated', 'Yes' if payload.get('lines_truncated') else 'No'],
        [],
        [
            'Note',
            (
                '“Count” on Payment Method / Daily sheets is number of *sales* '
                '(tickets), not product quantity. Use Goods Sold for units per product.'
            ),
        ],
    ]


def render_sales_xlsx(
    payload: dict[str, Any],
    *,
    title: str = 'Sales',
    include_cost: bool = True,
) -> bytes:
    """
    Build a multi-sheet sales workbook with Goods Sold first.

    Args:
        payload: Sales or sales-overview response including ``by_product``.
        title: Workbook title (≤ 120 chars).
        include_cost: When True (admin), include COGS columns on product sheets.

    Returns:
        XLSX bytes.

    Raises:
        RuntimeError: When openpyxl is missing.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError('openpyxl must be installed to export Excel files.') from exc

    products = _product_rows(payload, include_cost=include_cost)
    lines = _line_rows(payload, include_cost=include_cost)
    product_headers = PRODUCT_HEADERS if include_cost else PRODUCT_HEADERS_NO_COST
    line_headers = LINE_HEADERS if include_cost else LINE_HEADERS_NO_COST
    tickets = _ticket_rows(payload)
    sheets = [
        ('Goods Sold', product_headers, products),
        ('Sale Lines', line_headers, lines),
    ]
    if tickets:
        sheets.append(('Sales', TICKET_HEADERS, tickets))
    sheets.extend(
        [
            (
                'Payment Method',
                ['Payment method', 'Sale count', 'Total'],
                _payment_rows(payload),
            ),
            ('Daily Breakdown', ['Day', 'Sale count', 'Total'], _daily_rows(payload)),
            ('Summary', ['Field', 'Value'], _summary_rows(payload, products)),
        ]
    )

    workbook = Workbook()
    header_fill = PatternFill('solid', fgColor='1F4E79')
    header_font = Font(bold=True, color='FFFFFF')
    money_idx = {
        'Goods Sold': {4, 5, 6} if include_cost else {4},
        'Sale Lines': {5, 6, 7, 8, 9} if include_cost else {5, 6},
        'Sales': {5},
        'Payment Method': {2},
        'Daily Breakdown': {2},
    }

    for index, (name, headers, rows) in enumerate(sheets):
        ws = workbook.active if index == 0 else workbook.create_sheet()
        ws.title = name[:31]
        if name == 'Summary':
            ws['A1'] = brand_name_line()
            ws['A1'].font = Font(bold=True, size=14)
            ws['A2'] = title
            ws['A2'].font = Font(bold=True, size=12)
            start = 4
        else:
            start = 1
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=start, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', wrap_text=True)
        money_set = money_idx.get(name, set())
        for r_i, row in enumerate(rows, start=start + 1):
            for c_i, value in enumerate(row, start=1):
                cell = ws.cell(row=r_i, column=c_i, value=value)
                if c_i - 1 in money_set and isinstance(value, (int, float)):
                    cell.number_format = '#,##0.00'
                elif isinstance(value, float) and headers[c_i - 1].endswith('%'):
                    cell.number_format = '0.00'
        if name != 'Summary' and rows:
            last = start + len(rows)
            ws.auto_filter.ref = f'A{start}:{get_column_letter(len(headers))}{last}'
            ws.freeze_panes = f'A{start + 1}'
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].width = 18
        if name == 'Goods Sold':
            ws.column_dimensions['A'].width = 32

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def render_sales_csv(
    payload: dict[str, Any],
    *,
    include_cost: bool = True,
) -> bytes:
    """
    Flat Goods Sold CSV (product + quantity).

    Args:
        payload: Sales payload with ``by_product``.
        include_cost: When True (admin), include COGS columns.

    Returns:
        UTF-8-SIG CSV bytes.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    headers = PRODUCT_HEADERS if include_cost else PRODUCT_HEADERS_NO_COST
    writer.writerow(headers)
    for row in _product_rows(payload, include_cost=include_cost):
        writer.writerow(row)
    return output.getvalue().encode('utf-8-sig')


def maybe_export_sales_workbook(
    request,
    payload: Any,
    *,
    title: str = 'Sales',
    slug: str = 'sales',
) -> Optional[HttpResponse]:
    """
    Return a dedicated sales XLSX/CSV when ``format`` is set and payload matches.

    Args:
        request: Request with optional ``format`` query param.
        payload: Sales or sales-overview JSON.
        title: Download title.
        slug: Filename stem.

    Returns:
        File HttpResponse, 400 Response for bad format, or None (e.g. PDF /
        non-sales payload — fall through to generic exporter).
    """
    if request is None or not is_sales_export_payload(payload):
        return None
    raw = request.query_params.get('format') or request.GET.get('format')
    try:
        fmt = normalize_export_format(raw)
    except UnsupportedExportFormat as exc:
        from rest_framework import status
        from rest_framework.response import Response

        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if not fmt or fmt == 'pdf':
        return None
    from reports.export_product_cost import user_may_export_product_cost

    include_cost = user_may_export_product_cost(getattr(request, 'user', None))
    date_from = request.query_params.get('date_from') or request.GET.get('date_from')
    date_to = request.query_params.get('date_to') or request.GET.get('date_to')
    if slug in ('sales-history', 'sales', 'sale'):
        file_name = sales_export_filename(fmt, date_from=date_from, date_to=date_to)
    else:
        file_name = export_filename(slug, fmt)
    if fmt == 'csv':
        content = render_sales_csv(payload, include_cost=include_cost)
        response = HttpResponse(content, content_type=CONTENT_TYPES['csv'])
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        response['X-Report-Export'] = 'csv'
        return response
    content = render_sales_xlsx(payload, title=title, include_cost=include_cost)
    response = HttpResponse(content, content_type=CONTENT_TYPES['xlsx'])
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'
    response['X-Report-Export'] = 'xlsx'
    if payload.get('lines_truncated'):
        response['X-Export-Truncated'] = '1'
        response['X-Export-Total-Count'] = str(payload.get('line_count') or '')
    return response
