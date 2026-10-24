"""Payslip PDF generation with store brand / letterhead."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from payroll.models import PayrollSettings, Payslip
from utils.document_branding import brand_header_elements, branded_document_title


def build_payslip_pdf(payslip: Payslip) -> bytes:
    settings = PayrollSettings.load(payslip.run.tenant)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        title=branded_document_title(
            f'Payslip {payslip.employee_id_snapshot} {payslip.run.period_label}'
        ),
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        'PayslipBody',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
    )
    right = ParagraphStyle(
        'PayslipRight',
        parent=body,
        alignment=TA_RIGHT,
    )
    section = ParagraphStyle(
        'PayslipSection',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=colors.HexColor('#1a4d7a'),
        spaceBefore=10,
        spaceAfter=4,
    )

    story = []
    story.extend(brand_header_elements('Payslip'))
    if settings.letterhead_line:
        story.append(
            Paragraph(
                settings.letterhead_line,
                ParagraphStyle(
                    'Letterhead',
                    parent=body,
                    alignment=TA_LEFT,
                    textColor=colors.HexColor('#555555'),
                    spaceAfter=6,
                ),
            )
        )
    story.append(Spacer(1, 8))

    info = [
        ['Employee', payslip.employee_name_snapshot, 'Period', payslip.run.period_label],
        ['ID', payslip.employee_id_snapshot, 'Currency', payslip.currency],
        [
            'Position',
            payslip.position_snapshot or '—',
            'Department',
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
    info_table = Table(info, colWidths=[1.1 * inch, 2.4 * inch, 1.1 * inch, 2.0 * inch])
    info_table.setStyle(
        TableStyle(
            [
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
                ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#333333')),
            ]
        )
    )
    story.append(info_table)
    story.append(Spacer(1, 12))

    earnings = [ln for ln in payslip.lines.all() if ln.kind == 'earning']
    deductions = [ln for ln in payslip.lines.all() if ln.kind == 'deduction']

    story.append(Paragraph('Earnings', section))
    earn_rows = [['Description', 'Amount']]
    for ln in earnings:
        earn_rows.append([ln.name, f'{ln.amount:,.2f}'])
    earn_rows.append(['Gross pay', f'{payslip.gross_pay:,.2f}'])
    earn_table = Table(earn_rows, colWidths=[4.6 * inch, 2.0 * inch])
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
    ded_table = Table(ded_rows, colWidths=[4.6 * inch, 2.0 * inch])
    ded_table.setStyle(_amount_table_style(len(ded_rows)))
    story.append(ded_table)

    story.append(Spacer(1, 14))
    net_table = Table(
        [['Net pay', f'{payslip.currency} {payslip.net_pay:,.2f}']],
        colWidths=[4.6 * inch, 2.0 * inch],
    )
    net_table.setStyle(
        TableStyle(
            [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e8f0f7')),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#1a4d7a')),
            ]
        )
    )
    story.append(net_table)

    if payslip.run.status == 'locked' and payslip.run.locked_at:
        story.append(Spacer(1, 16))
        story.append(
            Paragraph(
                f'Locked {payslip.run.locked_at.strftime("%Y-%m-%d %H:%M")} — this payslip is final.',
                ParagraphStyle('LockedNote', parent=body, textColor=colors.HexColor('#666666')),
            )
        )

    doc.build(story)
    return buffer.getvalue()


def _amount_table_style(nrows: int) -> TableStyle:
    cmds = [
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.HexColor('#cccccc')),
        ('LINEABOVE', (0, -1), (-1, -1), 0.8, colors.HexColor('#1a4d7a')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]
    return TableStyle(cmds)
