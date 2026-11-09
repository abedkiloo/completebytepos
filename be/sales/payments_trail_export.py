"""Excel workbook for Payments trail money-in rows."""

from __future__ import annotations

import io
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from django.http import HttpResponse

from reports.export import (
    CONTENT_TYPES,
    UnsupportedExportFormat,
    export_filename,
    normalize_export_format,
)
from sales.payments_trail import KIND_LABELS

PAYMENT_HEADERS = [
    'When',
    'Type',
    'Customer',
    'Customer code',
    'Phone',
    'Amount',
    'Method',
    'M-Pesa via',
    'Paid by',
    'Payer phone',
    'Reference',
    'Paid towards',
    'Collected by',
    'Notes',
]

METHOD_HEADERS = ['Method', 'Payment count', 'Total']


def _as_decimal(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def _payment_rows(results: Sequence[Dict[str, Any]]) -> List[List[Any]]:
    rows: List[List[Any]] = []
    for row in results:
        kind = row.get('kind') or ''
        rows.append(
            [
                row.get('occurred_at') or '',
                KIND_LABELS.get(kind, kind),
                row.get('customer_name') or '',
                row.get('customer_code') or '',
                row.get('customer_phone') or '',
                float(_as_decimal(row.get('amount'))),
                row.get('payment_method_label') or row.get('payment_method') or '',
                row.get('mpesa_destination_label') or row.get('mpesa_destination') or '',
                row.get('payer_name') or '',
                row.get('payer_phone') or '',
                row.get('reference') or '',
                row.get('paid_towards_label') or '',
                row.get('received_by') or '',
                row.get('notes') or '',
            ]
        )
    return rows


def _method_rows(by_method: Sequence[Dict[str, Any]]) -> List[List[Any]]:
    return [
        [
            row.get('payment_method_label') or row.get('payment_method') or '',
            int(row.get('count') or 0),
            float(_as_decimal(row.get('total'))),
        ]
        for row in by_method
    ]


def render_payments_trail_xlsx(
    payload: Dict[str, Any],
    *,
    title: str = 'Payments trail',
) -> bytes:
    """
    Build an XLSX with Payments + By method sheets.

    Args:
        payload: Output of ``build_payments_trail_export``.
        title: Workbook title shown on the summary banner.

    Returns:
        XLSX file bytes.

    Raises:
        RuntimeError: When openpyxl is not installed.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError('openpyxl must be installed to export Excel files.') from exc

    results = payload.get('results') or []
    by_method = payload.get('by_method') or []
    payments = _payment_rows(results)
    methods = _method_rows(by_method)

    workbook = Workbook()
    header_fill = PatternFill('solid', fgColor='1F4E79')
    header_font = Font(bold=True, color='FFFFFF')

    sheets = [
        ('Payments', PAYMENT_HEADERS, payments, {5}),
        ('By method', METHOD_HEADERS, methods, {2}),
    ]

    for index, (name, headers, rows, money_cols) in enumerate(sheets):
        ws = workbook.active if index == 0 else workbook.create_sheet()
        ws.title = name[:31]
        if index == 0:
            ws['A1'] = title
            ws['A1'].font = Font(bold=True, size=14)
            day_from = payload.get('date_from') or ''
            day_to = payload.get('date_to') or ''
            ws['A2'] = f'From {day_from} to {day_to}'.strip()
            ws['A3'] = (
                f"Rows: {payload.get('exported_count', len(results))}"
                f" / {payload.get('count', len(results))}"
                f" · Total: {payload.get('total_amount') or '0.00'}"
            )
            if payload.get('truncated'):
                ws['A4'] = 'Export truncated to the row limit. Narrow the date range.'
            start = 6
        else:
            start = 1
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=start, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', wrap_text=True)
        for r_i, row in enumerate(rows, start=start + 1):
            for c_i, value in enumerate(row, start=1):
                cell = ws.cell(row=r_i, column=c_i, value=value)
                if (c_i - 1) in money_cols and isinstance(value, (int, float)):
                    cell.number_format = '#,##0.00'
        if rows:
            last = start + len(rows)
            ws.auto_filter.ref = f'A{start}:{get_column_letter(len(headers))}{last}'
            ws.freeze_panes = f'A{start + 1}'
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].width = 18
        if name == 'Payments':
            ws.column_dimensions['A'].width = 22
            ws.column_dimensions['C'].width = 24
            ws.column_dimensions['I'].width = 28

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def payments_trail_export_response(
    request,
    payload: Dict[str, Any],
    *,
    title: str = 'Payments trail',
    slug: str = 'payments-trail',
) -> Optional[HttpResponse]:
    """
    Return an XLSX HttpResponse for the payments trail export.

    Args:
        request: DRF request with ``format`` query param.
        payload: ``build_payments_trail_export`` result.
        title: Download title.
        slug: Filename stem.

    Returns:
        File response, or None if format is missing (caller should 400).
    """
    from rest_framework import status
    from rest_framework.response import Response

    raw = request.query_params.get('format') or request.GET.get('format')
    try:
        fmt = normalize_export_format(raw)
    except UnsupportedExportFormat as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if not fmt:
        return None
    if fmt != 'xlsx':
        return Response(
            {'error': 'Payments trail export supports format=xlsx only.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    content = render_payments_trail_xlsx(payload, title=title)
    response = HttpResponse(content, content_type=CONTENT_TYPES['xlsx'])
    response['Content-Disposition'] = (
        f'attachment; filename="{export_filename(slug, "xlsx")}"'
    )
    response['X-Report-Export'] = 'xlsx'
    if payload.get('truncated'):
        response['X-Export-Truncated'] = '1'
        response['X-Export-Total-Count'] = str(payload.get('count') or '')
    return response
