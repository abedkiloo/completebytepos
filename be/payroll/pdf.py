"""Payslip PDF generation with store brand / letterhead.

PDFs are not stored on disk — each download builds bytes from the locked
payslip rows + current store/payroll branding (same pattern as receipts).
Layout is compact (A5, small logo/type) so files stay light like receipts.
"""

from __future__ import annotations

import calendar
import re
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from payroll.models import PayrollSettings, Payslip
from utils.document_branding import brand_header_elements, branded_document_title

# Compact slip page — roughly receipt-scale, not full A4.
_PAGE = A5
_CONTENT_W = _PAGE[0] - (2 * 8 * mm)


def payslip_download_filename(payslip: Payslip) -> str:
    """
    Download name: PersonName_Month_Year_EmployeeID.pdf

    Employee ID is omitted when blank. Unsafe path characters are stripped.
    """
    name = (getattr(payslip, 'employee_name_snapshot', None) or 'Employee').strip()
    emp_id = (getattr(payslip, 'employee_id_snapshot', None) or '').strip()
    run = getattr(payslip, 'run', None)
    month = getattr(run, 'month', None) or 0
    year = getattr(run, 'year', None) or 0
    month_name = calendar.month_name[month] if 1 <= month <= 12 else 'Month'
    year_label = str(year) if year else 'Year'
    parts = [name, month_name, year_label]
    if emp_id:
        parts.append(emp_id)
    raw = '_'.join(parts)
    safe = re.sub(r'[^\w.\-]+', '_', raw, flags=re.UNICODE)
    safe = re.sub(r'_+', '_', safe).strip('._')
    return f'{safe or "payslip"}.pdf'


def _period_display(payslip: Payslip) -> str:
    run = getattr(payslip, 'run', None)
    month = getattr(run, 'month', None) or 0
    year = getattr(run, 'year', None) or 0
    if 1 <= month <= 12 and year:
        return f'{calendar.month_name[month]} {year}'
    return getattr(run, 'period_label', '') or '—'


def _payslip_letterhead(settings: PayrollSettings, tenant) -> str:
    """Combine payroll letterhead with tenant registration/tax when configured."""
    parts = []
    if settings.letterhead_line:
        parts.append(settings.letterhead_line.strip())
    if tenant is not None:
        if getattr(tenant, 'registration_number', None):
            parts.append(f'Reg. No: {tenant.registration_number.strip()}')
        if getattr(tenant, 'tax_id', None):
            parts.append(f'Tax ID: {tenant.tax_id.strip()}')
    return ' · '.join(p for p in parts if p)


def build_payslip_pdf(payslip: Payslip) -> bytes:
    tenant = getattr(payslip.run, 'tenant', None)
    settings = PayrollSettings.load(tenant)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=_PAGE,
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=6 * mm,
        bottomMargin=6 * mm,
        title=branded_document_title(
            f'Payslip {payslip.employee_id_snapshot} {_period_display(payslip)}'
        ),
    )
    styles = getSampleStyleSheet()
    section = ParagraphStyle(
        'PayslipSection',
        parent=styles['Heading3'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1a4d7a'),
        spaceBefore=6,
        spaceAfter=2,
    )

    story = []
    # Small logo + tight brand block (receipt-like footprint).
    story.extend(
        brand_header_elements(
            'Payslip',
            logo_size=0.55 * inch,
            extra_letterhead=_payslip_letterhead(settings, tenant),
            respect_logo_flag=True,
            compact=True,
        )
    )
    story.append(Spacer(1, 4))

    label_w = 0.7 * inch
    value_w = (_CONTENT_W / 2) - label_w
    info = [
        [
            'Employee',
            payslip.employee_name_snapshot,
            'Period',
            _period_display(payslip),
        ],
        ['ID', payslip.employee_id_snapshot, 'Currency', payslip.currency],
        [
            'Position',
            payslip.position_snapshot or '—',
            'Dept',
            payslip.department_snapshot or '—',
        ],
    ]
    if payslip.bank_name_snapshot or payslip.bank_account_snapshot:
        info.append(
            [
                'Bank',
                payslip.bank_name_snapshot or '—',
                'Account',
                payslip.bank_account_snapshot or '—',
            ]
        )
    info_table = Table(info, colWidths=[label_w, value_w, label_w, value_w])
    info_table.setStyle(
        TableStyle(
            [
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('LEADING', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
                ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#333333')),
            ]
        )
    )
    story.append(info_table)
    story.append(Spacer(1, 6))

    earnings = [ln for ln in payslip.lines.all() if ln.kind == 'earning']
    deductions = [ln for ln in payslip.lines.all() if ln.kind == 'deduction']

    desc_w = _CONTENT_W * 0.72
    amt_w = _CONTENT_W * 0.28

    story.append(Paragraph('Earnings', section))
    earn_rows = [['Description', 'Amount']]
    for ln in earnings:
        earn_rows.append([ln.name, f'{ln.amount:,.2f}'])
    earn_rows.append(['Gross pay', f'{payslip.gross_pay:,.2f}'])
    earn_table = Table(earn_rows, colWidths=[desc_w, amt_w])
    earn_table.setStyle(_amount_table_style(len(earn_rows)))
    story.append(earn_table)

    story.append(Paragraph('Deductions', section))
    ded_rows = [['Description', 'Amount']]
    if deductions:
        for ln in deductions:
            ded_rows.append([ln.name, f'{ln.amount:,.2f}'])
    else:
        ded_rows.append(['—', '0.00'])
    ded_rows.append(['Total deductions', f'{payslip.total_deductions:,.2f}'])
    ded_table = Table(ded_rows, colWidths=[desc_w, amt_w])
    ded_table.setStyle(_amount_table_style(len(ded_rows)))
    story.append(ded_table)

    story.append(Spacer(1, 6))
    net_table = Table(
        [['Net pay', f'{payslip.currency} {payslip.net_pay:,.2f}']],
        colWidths=[desc_w, amt_w],
    )
    net_table.setStyle(
        TableStyle(
            [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e8f0f7')),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#1a4d7a')),
            ]
        )
    )
    story.append(net_table)

    doc.build(story)
    return buffer.getvalue()


def _amount_table_style(nrows: int) -> TableStyle:
    cmds = [
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('LEADING', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEBELOW', (0, 0), (-1, 0), 0.4, colors.HexColor('#cccccc')),
        ('LINEABOVE', (0, -1), (-1, -1), 0.6, colors.HexColor('#1a4d7a')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]
    return TableStyle(cmds)
