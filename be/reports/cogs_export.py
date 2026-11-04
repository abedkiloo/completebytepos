"""
Analyst-grade COGS workbook / CSV export for trading profit.

Produces numeric columns (not locale-formatted strings) so Excel pivots,
SUMIF, and margin checks work without re-typing. Sheets are designed for
tie-out: Goods Sold line totals must reconcile to Summary COGS sold.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from django.http import HttpResponse

from reports.export import (
    CONTENT_TYPES,
    UnsupportedExportFormat,
    export_filename,
    normalize_export_format,
)
from utils.document_branding import brand_contact_line, brand_name_line


SOURCE_LABELS = {
    'unit_cost': 'FIFO stamp (sale line)',
    'layer_allocation': 'FIFO layer slices',
    'stock_movement': 'Stock movement',
    'catalog': 'Product catalog cost',
    'legacy_pending': 'Unresolved (zero)',
    'legacy_movement': 'Legacy stock movements',
}


def _d(value: Any) -> Decimal:
    """
    Coerce money/qty values to Decimal.

    Args:
        value: Number, string, or None.

    Returns:
        Decimal value, or Decimal('0') when empty/invalid.
    """
    if value is None or value == '':
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def _num(value: Any) -> Optional[float]:
    """
    Excel-friendly float, or None for blank cells.

    Args:
        value: Scalar money/qty; None stays blank (not zero) for optional fields.

    Returns:
        float rounded to 4 dp, or None when value is None/''.
    """
    if value is None or value == '':
        return None
    return float(_d(value).quantize(Decimal('0.0001')))


def _money_num(value: Any) -> Optional[float]:
    """
    Money cell as float with 2 decimal places.

    Args:
        value: Amount; None stays blank.

    Returns:
        float or None.
    """
    if value is None or value == '':
        return None
    return float(_d(value).quantize(Decimal('0.01')))


def extract_cogs_payload(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Pull the nested or top-level COGS breakdown from a report response.

    Args:
        payload: Breakdown or ``/trading_profit/cogs/`` JSON body.

    Returns:
        COGS dict with ``sales`` / ``cogs_sold`` keys, or None if not COGS.
    """
    if not isinstance(payload, dict):
        return None
    nested = payload.get('cogs')
    if isinstance(nested, dict) and (
        'sales' in nested or 'cogs_sold' in nested or 'cogs' in nested
    ):
        merged = dict(nested)
        for key in ('period', 'date_from', 'date_to', 'title', 'formula', 'explanation'):
            if key not in merged and payload.get(key) is not None:
                merged[key] = payload.get(key)
        if 'explanation' not in merged and payload.get('explanation'):
            merged['explanation'] = payload['explanation']
        return merged
    if 'cogs_sold' in payload and isinstance(payload.get('sales'), list):
        return payload
    return None


def _goods_sold_rows(cogs: dict[str, Any]) -> list[list[Any]]:
    """
    Flatten every sale line into one analyst row.

    Args:
        cogs: COGS breakdown payload.

    Returns:
        List of row lists matching GOODS_HEADERS (0–N rows).
    """
    rows: list[list[Any]] = []
    for sale in cogs.get('sales') or []:
        if not isinstance(sale, dict):
            continue
        sale_number = sale.get('sale_number') or ''
        occurred = sale.get('occurred_at') or ''
        if isinstance(occurred, str) and 'T' in occurred:
            occurred = occurred.replace('T', ' ')[:19]
        sale_total = _money_num(sale.get('sale_total'))
        sale_cogs = _money_num(sale.get('cogs'))
        sale_gp = _money_num(sale.get('gross_profit'))
        payment = sale.get('payment_method') or ''
        cashier = sale.get('cashier') or ''
        for line in sale.get('lines') or []:
            if not isinstance(line, dict):
                continue
            source = line.get('source') or ''
            rows.append(
                [
                    sale_number,
                    occurred,
                    line.get('product_name') or '',
                    line.get('sku') or '',
                    _num(line.get('quantity')),
                    _money_num(line.get('unit_price')),
                    _money_num(line.get('line_sale')),
                    _money_num(line.get('unit_cost')),
                    _money_num(line.get('line_cogs')),
                    _money_num(line.get('line_gross_profit')),
                    _num(line.get('margin_pct')),
                    SOURCE_LABELS.get(source, source),
                    'Yes' if line.get('cost_missing') else 'No',
                    sale_total,
                    sale_cogs,
                    sale_gp,
                    payment,
                    cashier,
                ]
            )
    return rows


GOODS_HEADERS = [
    'Sale number',
    'Sale date/time',
    'Goods sold',
    'SKU',
    'Quantity',
    'Unit selling price',
    'Line sale (revenue)',
    'Unit cost (FIFO)',
    'Line COGS',
    'Line gross profit',
    'Margin %',
    'Cost source',
    'Cost missing',
    'Sale total (header)',
    'Sale COGS',
    'Sale gross profit',
    'Payment method',
    'Cashier',
]


def _sale_total_rows(cogs: dict[str, Any]) -> list[list[Any]]:
    """One row per sale for header-level tie-out."""
    rows = []
    for sale in cogs.get('sales') or []:
        if not isinstance(sale, dict):
            continue
        occurred = sale.get('occurred_at') or ''
        if isinstance(occurred, str) and 'T' in occurred:
            occurred = occurred.replace('T', ' ')[:19]
        concerns = sale.get('concerns') or []
        rows.append(
            [
                sale.get('sale_number') or '',
                occurred,
                _money_num(sale.get('sale_total')),
                _money_num(sale.get('line_revenue')),
                _money_num(sale.get('revenue_gap')),
                _money_num(sale.get('cogs')),
                _money_num(sale.get('gross_profit')),
                _num(sale.get('margin_pct')),
                len(sale.get('lines') or []),
                sale.get('payment_method') or '',
                sale.get('cashier') or '',
                ' | '.join(str(c) for c in concerns) if concerns else '',
            ]
        )
    return rows


SALE_HEADERS = [
    'Sale number',
    'Sale date/time',
    'Sale total (header)',
    'Line revenue (goods)',
    'Revenue gap (tax/fees/other)',
    'Sale COGS',
    'Gross profit',
    'Margin %',
    'Line count',
    'Payment method',
    'Cashier',
    'Cost concerns',
]


def _by_product_rows(cogs: dict[str, Any]) -> list[list[Any]]:
    """Aggregate quantity, revenue, and COGS by product name + SKU."""
    buckets: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(
        lambda: {
            'qty': Decimal('0'),
            'revenue': Decimal('0'),
            'cogs': Decimal('0'),
        }
    )
    for sale in cogs.get('sales') or []:
        if not isinstance(sale, dict):
            continue
        for line in sale.get('lines') or []:
            if not isinstance(line, dict):
                continue
            if line.get('source') == 'legacy_movement':
                continue
            key = (line.get('product_name') or 'Item', line.get('sku') or '')
            buckets[key]['qty'] += _d(line.get('quantity'))
            buckets[key]['revenue'] += _d(line.get('line_sale'))
            buckets[key]['cogs'] += _d(line.get('line_cogs'))
    rows = []
    for (name, sku), vals in sorted(buckets.items(), key=lambda x: (-x[1]['cogs'], x[0][0])):
        rev = vals['revenue']
        cog = vals['cogs']
        gp = rev - cog
        margin = (
            float((gp / rev * Decimal('100')).quantize(Decimal('0.01')))
            if rev > 0
            else None
        )
        avg_cost = (
            float((cog / vals['qty']).quantize(Decimal('0.01')))
            if vals['qty'] > 0
            else None
        )
        rows.append(
            [
                name,
                sku,
                float(vals['qty']),
                float(rev.quantize(Decimal('0.01'))),
                float(cog.quantize(Decimal('0.01'))),
                float(gp.quantize(Decimal('0.01'))),
                margin,
                avg_cost,
            ]
        )
    return rows


PRODUCT_HEADERS = [
    'Goods sold',
    'SKU',
    'Quantity sold',
    'Revenue',
    'COGS',
    'Gross profit',
    'Margin %',
    'Avg unit cost',
]


def _concern_rows(cogs: dict[str, Any]) -> list[list[Any]]:
    """Lines still at zero cost — must be fixed for absolute costing."""
    rows = []
    for sale in cogs.get('sales') or []:
        if not isinstance(sale, dict):
            continue
        for line in sale.get('lines') or []:
            if not isinstance(line, dict) or not line.get('cost_missing'):
                continue
            rows.append(
                [
                    sale.get('sale_number') or '',
                    line.get('product_name') or '',
                    line.get('sku') or '',
                    _num(line.get('quantity')),
                    _money_num(line.get('line_sale')),
                    SOURCE_LABELS.get(line.get('source') or '', line.get('source')),
                    ' | '.join(sale.get('concerns') or []),
                ]
            )
    return rows


CONCERN_HEADERS = [
    'Sale number',
    'Goods sold',
    'SKU',
    'Quantity',
    'Line sale',
    'Cost source',
    'Notes',
]


def _refund_rows(cogs: dict[str, Any]) -> list[list[Any]]:
    rows = []
    for refund in cogs.get('refunds') or []:
        if not isinstance(refund, dict):
            continue
        created = refund.get('created_at') or ''
        if isinstance(created, str) and 'T' in created:
            created = created.replace('T', ' ')[:19]
        lines = refund.get('lines') or []
        if not lines:
            rows.append(
                [
                    refund.get('sale_number') or '',
                    created,
                    '',
                    None,
                    None,
                    _money_num(refund.get('refund_amount')),
                    _money_num(refund.get('cogs_restored')),
                ]
            )
            continue
        for line in lines:
            if not isinstance(line, dict):
                continue
            rows.append(
                [
                    refund.get('sale_number') or '',
                    created,
                    line.get('product_name') or '',
                    _num(line.get('quantity')),
                    _money_num(line.get('unit_cost')),
                    _money_num(refund.get('refund_amount')),
                    _money_num(line.get('line_cogs')),
                ]
            )
    return rows


REFUND_HEADERS = [
    'Original sale',
    'Refund date/time',
    'Goods restored',
    'Quantity',
    'Unit cost',
    'Refund amount',
    'COGS restored',
]


def _summary_rows(cogs: dict[str, Any], goods_rows: list[list[Any]]) -> list[list[Any]]:
    """
    Control totals and methodology for senior analyst review.

    Args:
        cogs: COGS payload.
        goods_rows: Flattened goods rows (Quantity at index 4, Line COGS at 8).

    Returns:
        Label/value pairs for the Summary sheet.
    """
    line_cogs_sum = sum((_d(r[8]) for r in goods_rows), Decimal('0'))
    line_qty_sum = sum((_d(r[4]) for r in goods_rows if r[4] is not None), Decimal('0'))
    line_rev_sum = sum((_d(r[6]) for r in goods_rows if r[6] is not None), Decimal('0'))
    cogs_sold = _d(cogs.get('cogs_sold'))
    cogs_refunded = _d(cogs.get('cogs_refunded'))
    net = _d(cogs.get('cogs'))
    tie_out = line_cogs_sum - cogs_sold
    missing = sum(
        1
        for sale in cogs.get('sales') or []
        if isinstance(sale, dict)
        for line in sale.get('lines') or []
        if isinstance(line, dict) and line.get('cost_missing')
    )
    return [
        ['Brand', brand_name_line()],
        ['Contact', brand_contact_line()],
        ['Report', cogs.get('title') or 'COGS (cost of goods sold)'],
        ['Period', cogs.get('period') or ''],
        ['Date from', cogs.get('date_from') or ''],
        ['Date to', cogs.get('date_to') or ''],
        ['Formula', cogs.get('formula') or 'COGS sold − cost restored on refunds'],
        ['Methodology', cogs.get('explanation') or ''],
        [],
        ['COGS sold (period)', float(cogs_sold.quantize(Decimal('0.01')))],
        ['Refunded cost (restored)', float(cogs_refunded.quantize(Decimal('0.01')))],
        ['Net COGS', float(net.quantize(Decimal('0.01')))],
        [],
        ['Sales in period', cogs.get('sale_count') or 0],
        ['Sales in this workbook', cogs.get('sales_shown') or len(cogs.get('sales') or [])],
        ['Truncated', 'Yes' if cogs.get('truncated') else 'No'],
        ['Sales with cost concerns', cogs.get('cost_missing_sale_count') or 0],
        ['Lines with cost missing', missing],
        [],
        ['Goods sold lines (rows)', len(goods_rows)],
        ['Total quantity sold (lines)', float(line_qty_sum)],
        ['Sum of line sale revenue', float(line_rev_sum.quantize(Decimal('0.01')))],
        ['Sum of line COGS', float(line_cogs_sum.quantize(Decimal('0.01')))],
        [
            'Tie-out: line COGS − COGS sold (must be 0 if not truncated)',
            float(tie_out.quantize(Decimal('0.01'))),
        ],
        [
            'Gross profit on goods (line revenue − line COGS)',
            float((line_rev_sum - line_cogs_sum).quantize(Decimal('0.01'))),
        ],
        [],
        [
            'Accounting notes',
            (
                'Unit cost uses FIFO stamp on the sale line; fallbacks are layer '
                'slices → stock movements → catalog cost. Sale total (header) may '
                'include tax or non-line amounts — use Revenue gap on Sale Totals. '
                'Every tracked product must have a cost; fix Cost Concerns before '
                'signing off the period.'
            ),
        ],
    ]


def render_cogs_xlsx(cogs: dict[str, Any], *, title: str = 'COGS') -> bytes:
    """
    Build a multi-sheet COGS workbook.

    Args:
        cogs: COGS breakdown dict (sales, refunds, totals).
        title: Workbook title (≤ 120 chars).

    Returns:
        XLSX file bytes (empty sheets still include headers).

    Raises:
        RuntimeError: When openpyxl is not installed.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError('openpyxl must be installed to export Excel files.') from exc

    goods = _goods_sold_rows(cogs)
    sheets: list[tuple[str, list[str], list[list[Any]]]] = [
        ('Summary', ['Field', 'Value'], _summary_rows(cogs, goods)),
        ('Goods Sold', GOODS_HEADERS, goods),
        ('Sale Totals', SALE_HEADERS, _sale_total_rows(cogs)),
        ('By Product', PRODUCT_HEADERS, _by_product_rows(cogs)),
        ('Cost Concerns', CONCERN_HEADERS, _concern_rows(cogs)),
        ('Refunds', REFUND_HEADERS, _refund_rows(cogs)),
    ]

    workbook = Workbook()
    header_fill = PatternFill('solid', fgColor='1F4E79')
    header_font = Font(bold=True, color='FFFFFF')
    money_cols = {
        'Goods Sold': {5, 6, 7, 8, 9, 13, 14, 15},
        'Sale Totals': {2, 3, 4, 5, 6},
        'By Product': {3, 4, 5, 7},
        'Cost Concerns': {4},
        'Refunds': {4, 5, 6},
    }

    for index, (name, headers, rows) in enumerate(sheets):
        ws = workbook.active if index == 0 else workbook.create_sheet()
        ws.title = name[:31]
        if name == 'Summary':
            ws['A1'] = brand_name_line()
            ws['A1'].font = Font(bold=True, size=14)
            ws['A2'] = title
            ws['A2'].font = Font(bold=True, size=12)
            start_row = 4
            for col, header in enumerate(headers, start=1):
                cell = ws.cell(row=start_row, column=col, value=header)
                cell.fill = header_fill
                cell.font = header_font
            for r_i, row in enumerate(rows, start=start_row + 1):
                for c_i, value in enumerate(row, start=1):
                    ws.cell(row=r_i, column=c_i, value=value)
        else:
            for col, header in enumerate(headers, start=1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center', wrap_text=True)
            money_set = money_cols.get(name, set())
            for r_i, row in enumerate(rows, start=2):
                for c_i, value in enumerate(row, start=1):
                    cell = ws.cell(row=r_i, column=c_i, value=value)
                    if c_i - 1 in money_set and isinstance(value, (int, float)):
                        cell.number_format = '#,##0.00'
                    elif isinstance(value, float) and headers[c_i - 1].endswith('%'):
                        cell.number_format = '0.00'
            ws.auto_filter.ref = f'A1:{get_column_letter(len(headers))}{max(len(rows) + 1, 1)}'
            ws.freeze_panes = 'A2'
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].width = 18
        if name == 'Goods Sold':
            ws.column_dimensions['C'].width = 28
            ws.column_dimensions['L'].width = 22

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def render_cogs_csv(cogs: dict[str, Any]) -> bytes:
    """
    Flat Goods Sold CSV for pivot/import tools.

    Args:
        cogs: COGS breakdown dict.

    Returns:
        UTF-8-SIG CSV bytes with GOODS_HEADERS.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(GOODS_HEADERS)
    for row in _goods_sold_rows(cogs):
        writer.writerow(row)
    return output.getvalue().encode('utf-8-sig')


def maybe_export_cogs_workbook(
    request,
    payload: Any,
    *,
    title: str = 'COGS (cost of goods sold)',
    slug: str = 'trading_profit_cogs',
) -> Optional[HttpResponse]:
    """
    If ``format=xlsx|csv`` and payload is COGS, return a dedicated file response.

    Args:
        request: Request with optional ``format`` query param.
        payload: Report JSON (breakdown or cogs endpoint).
        title: Filename/title label (≤ 120 chars).
        slug: Safe filename stem.

    Returns:
        HttpResponse file download, Response 400 for bad format, or None to
        fall through to the generic exporter (e.g. PDF / non-COGS metrics).
    """
    if request is None or not isinstance(payload, dict):
        return None
    raw = request.query_params.get('format') or request.GET.get('format')
    try:
        fmt = normalize_export_format(raw)
    except UnsupportedExportFormat as exc:
        from rest_framework import status
        from rest_framework.response import Response

        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if not fmt:
        return None
    cogs = extract_cogs_payload(payload)
    if cogs is None:
        return None
    if fmt == 'pdf':
        # Keep PDF on the generic flattener.
        return None
    if fmt == 'csv':
        content = render_cogs_csv(cogs)
        response = HttpResponse(content, content_type=CONTENT_TYPES['csv'])
        response['Content-Disposition'] = (
            f'attachment; filename="{export_filename(slug, "csv")}"'
        )
        response['X-Report-Export'] = 'csv'
        if cogs.get('truncated'):
            response['X-Export-Truncated'] = '1'
            response['X-Export-Total-Count'] = str(cogs.get('sale_count') or '')
        return response
    content = render_cogs_xlsx(cogs, title=title)
    response = HttpResponse(content, content_type=CONTENT_TYPES['xlsx'])
    response['Content-Disposition'] = (
        f'attachment; filename="{export_filename(slug, "xlsx")}"'
    )
    response['X-Report-Export'] = 'xlsx'
    if cogs.get('truncated'):
        response['X-Export-Truncated'] = '1'
        response['X-Export-Total-Count'] = str(cogs.get('sale_count') or '')
    return response
