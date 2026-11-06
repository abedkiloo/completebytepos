"""
Gross sales Excel / CSV for Trading profit drill-down.

Sheets are built for tie-out: Sum of sale totals must equal the Summary
TOTAL (and Trading profit gross_sales) when the workbook is not truncated.
"""

from __future__ import annotations

import csv
import io
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


SALE_HEADERS = [
    'Sale number',
    'Business date',
    'Payment method',
    'Amount paid',
    'Sale total',
    'Unpaid',
]

LINE_HEADERS = [
    'Sale number',
    'Business date',
    'Product',
    'Quantity',
    'Unit price',
    'Line total',
]


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


def _money_num(value: Any) -> float:
    """
    Money cell as float with 2 decimal places.

    Args:
        value: Amount; None/blank becomes 0.00.

    Returns:
        float rounded to 2 dp (always a number for SUM in Excel).
    """
    return float(_d(value).quantize(Decimal('0.01')))


def _qty_num(value: Any) -> float:
    """
    Quantity cell as float.

    Args:
        value: Quantity; None/blank becomes 0.

    Returns:
        float rounded to 4 dp.
    """
    return float(_d(value).quantize(Decimal('0.0001')))


def _business_date(row: dict[str, Any]) -> str:
    """
    Business date string for a sale row.

    Args:
        row: Breakdown sale row with ``occurred_at`` and/or ``sublabel``.

    Returns:
        YYYY-MM-DD when known, else empty string (≤ 32 chars).
    """
    occurred = row.get('occurred_at') or ''
    if isinstance(occurred, str) and len(occurred) >= 10:
        return occurred[:10]
    sub = str(row.get('sublabel') or '')
    if len(sub) >= 10 and sub[4] == '-' and sub[7] == '-':
        return sub[:10]
    return ''


def _payment_method(row: dict[str, Any]) -> str:
    """
    Payment method from structured fields or the sublabel middle segment.

    Args:
        row: Breakdown sale row.

    Returns:
        Method label (≤ 40 chars), or empty string.
    """
    method = row.get('payment_method')
    if method:
        return str(method)[:40]
    sub = str(row.get('sublabel') or '')
    parts = [p.strip() for p in sub.split('·')]
    if len(parts) >= 2:
        return parts[1][:40]
    return ''


def is_gross_sales_export_payload(payload: Any) -> bool:
    """
    Detect Trading profit gross_sales breakdown JSON.

    Args:
        payload: Report response dict.

    Returns:
        True when metric is gross_sales and rows list is present.
    """
    if not isinstance(payload, dict):
        return False
    if (payload.get('metric') or '').strip().lower() != 'gross_sales':
        return False
    return isinstance(payload.get('rows'), list)


def sale_export_rows(payload: dict[str, Any]) -> list[list[Any]]:
    """
    Flat sale header rows for Excel/CSV.

    Args:
        payload: Gross sales breakdown with ``rows``.

    Returns:
        List of SALE_HEADERS-aligned rows (0–COGS_EXPORT_SALE_LIMIT).
    """
    out: list[list[Any]] = []
    for row in payload.get('rows') or []:
        if not isinstance(row, dict):
            continue
        out.append(
            [
                row.get('label') or '',
                _business_date(row),
                _payment_method(row),
                _money_num(row.get('amount_paid')),
                _money_num(row.get('amount') if row.get('amount') is not None else row.get('sale_total')),
                _money_num(row.get('unpaid')),
            ]
        )
    return out


def line_export_rows(payload: dict[str, Any]) -> list[list[Any]]:
    """
    Flat line-item rows for Excel/CSV.

    Args:
        payload: Gross sales breakdown with nested ``lines`` on each sale.

    Returns:
        List of LINE_HEADERS-aligned rows.
    """
    out: list[list[Any]] = []
    for row in payload.get('rows') or []:
        if not isinstance(row, dict):
            continue
        sale_number = row.get('label') or ''
        day = _business_date(row)
        for line in row.get('lines') or []:
            if not isinstance(line, dict):
                continue
            out.append(
                [
                    sale_number,
                    day,
                    line.get('product_name') or 'Item',
                    _qty_num(line.get('quantity')),
                    _money_num(line.get('unit_price')),
                    _money_num(line.get('line_total')),
                ]
            )
    return out


def summary_rows(payload: dict[str, Any], *, sales_rows: list[list[Any]]) -> list[list[Any]]:
    """
    Tie-out summary rows for the workbook.

    Args:
        payload: Gross sales breakdown.
        sales_rows: Output of ``sale_export_rows`` (same workbook).

    Returns:
        Label/value pairs including TOTAL and sum-of-rows check.
    """
    total = _d(payload.get('total'))
    rows_sum = sum((_d(r[4]) for r in sales_rows), Decimal('0'))
    tie_out = rows_sum - total
    return [
        ['Brand', brand_name_line()],
        ['Contact', brand_contact_line()],
        ['Report', payload.get('title') or 'Gross sales'],
        ['Period', payload.get('period') or ''],
        ['Date from', payload.get('date_from') or ''],
        ['Date to', payload.get('date_to') or ''],
        ['Formula', payload.get('formula') or 'Sum of sale totals'],
        ['Methodology', payload.get('explanation') or ''],
        [],
        ['TOTAL (gross sales)', _money_num(total)],
        ['Sales in period', payload.get('row_count') or 0],
        ['Sales in this workbook', payload.get('rows_shown') or len(sales_rows)],
        ['Truncated', 'Yes' if payload.get('truncated') else 'No'],
        [],
        ['Sum of sale totals (this workbook)', _money_num(rows_sum)],
        [
            'Tie-out: workbook sum − TOTAL (must be 0 if not truncated)',
            _money_num(tie_out),
        ],
    ]


def render_gross_sales_xlsx(
    payload: dict[str, Any],
    *,
    title: str = 'Gross sales',
) -> bytes:
    """
    Build a multi-sheet Gross sales workbook.

    Args:
        payload: Gross sales breakdown dict.
        title: Workbook title (≤ 120 chars).

    Returns:
        XLSX bytes.

    Raises:
        RuntimeError: When openpyxl is not installed.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError('openpyxl must be installed to export Excel files.') from exc

    sales = sale_export_rows(payload)
    lines = line_export_rows(payload)
    summary = summary_rows(payload, sales_rows=sales)

    workbook = Workbook()
    summary_ws = workbook.active
    summary_ws.title = 'Summary'
    for r_idx, row in enumerate(summary, start=1):
        for c_idx, value in enumerate(row, start=1):
            summary_ws.cell(row=r_idx, column=c_idx, value=value)
    summary_ws['A1'].font = Font(bold=True, size=14)

    def write_table(ws, headers, rows):
        header_fill = PatternFill('solid', fgColor='1F4E79')
        header_font = Font(bold=True, color='FFFFFF')
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
        for r_idx, row in enumerate(rows, start=2):
            for c_idx, value in enumerate(row, start=1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                if isinstance(value, float) and c_idx > 1:
                    cell.number_format = '#,##0.00'
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].width = 18

    sales_ws = workbook.create_sheet('Sales')
    write_table(sales_ws, SALE_HEADERS, sales)
    lines_ws = workbook.create_sheet('Line items')
    write_table(lines_ws, LINE_HEADERS, lines)

    summary_ws['A3'] = title[:120]
    summary_ws['A3'].font = Font(bold=True, size=12)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def render_gross_sales_csv(payload: dict[str, Any]) -> bytes:
    """
    Flat Gross sales CSV (sales first, then line items).

    Args:
        payload: Gross sales breakdown dict.

    Returns:
        UTF-8-SIG CSV bytes.
    """
    sales = sale_export_rows(payload)
    lines = line_export_rows(payload)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([brand_name_line()])
    writer.writerow([payload.get('title') or 'Gross sales'])
    writer.writerow(['TOTAL', _money_num(payload.get('total'))])
    writer.writerow([])
    writer.writerow(['Sales'])
    writer.writerow(SALE_HEADERS)
    for row in sales:
        writer.writerow(row)
    writer.writerow([])
    writer.writerow(['Line items'])
    writer.writerow(LINE_HEADERS)
    for row in lines:
        writer.writerow(row)
    return output.getvalue().encode('utf-8-sig')


def maybe_export_gross_sales_workbook(
    request,
    payload: Any,
    *,
    title: str = 'Gross sales',
    slug: str = 'trading_profit_gross_sales',
) -> Optional[HttpResponse]:
    """
    If ``format=xlsx|csv`` and payload is gross_sales, return a file response.

    Args:
        request: Request with optional ``format`` query param.
        payload: Report JSON (breakdown endpoint).
        title: Filename/title label (≤ 120 chars).
        slug: Safe filename stem.

    Returns:
        HttpResponse file download, Response 400 for bad format, or None to
        fall through to the generic exporter.
    """
    if request is None or not is_gross_sales_export_payload(payload):
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
    if fmt == 'pdf':
        return None
    if fmt == 'csv':
        content = render_gross_sales_csv(payload)
        response = HttpResponse(content, content_type=CONTENT_TYPES['csv'])
        response['Content-Disposition'] = (
            f'attachment; filename="{export_filename(slug, "csv")}"'
        )
        response['X-Report-Export'] = 'csv'
    else:
        content = render_gross_sales_xlsx(payload, title=title)
        response = HttpResponse(content, content_type=CONTENT_TYPES['xlsx'])
        response['Content-Disposition'] = (
            f'attachment; filename="{export_filename(slug, "xlsx")}"'
        )
        response['X-Report-Export'] = 'xlsx'
    if payload.get('truncated'):
        response['X-Export-Truncated'] = '1'
        response['X-Export-Total-Count'] = str(payload.get('row_count') or '')
    return response
