"""
PDF Generation utilities for financial documents
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from decimal import Decimal
from datetime import datetime
from sales.models import Payment


def format_currency(amount):
    """Format amount as currency"""
    if isinstance(amount, Decimal):
        amount = float(amount)
    return f"KES {amount:,.2f}"


def create_invoice_pdf(invoice):
    """Generate PDF for an invoice"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#333333'),
        spaceAfter=12
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 9
    
    # Company Header
    elements.append(Paragraph("CompleteByte POS", title_style))
    elements.append(Paragraph("Invoice", heading_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Invoice Details
    invoice_data = [
        ['Invoice Number:', invoice.invoice_number],
        ['Date:', invoice.issued_date.strftime('%B %d, %Y') if invoice.issued_date else invoice.created_at.strftime('%B %d, %Y')],
        ['Due Date:', invoice.due_date.strftime('%B %d, %Y') if invoice.due_date else 'N/A'],
        ['Status:', invoice.status.upper()],
    ]
    
    invoice_table = Table(invoice_data, colWidths=[2*inch, 3*inch])
    invoice_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(invoice_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Customer Details
    elements.append(Paragraph("Bill To:", heading_style))
    customer_data = [
        [invoice.customer_name or 'N/A'],
        [invoice.customer_email or ''],
        [invoice.customer_phone or ''],
        [invoice.customer_address or ''],
    ]
    
    customer_table = Table(customer_data, colWidths=[5*inch])
    customer_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(customer_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Invoice Items
    elements.append(Paragraph("Items:", heading_style))
    
    items_data = [['Description', 'Qty', 'Unit Price', 'Total']]
    for item in invoice.items.all():
        variant_info = ""
        if item.variant:
            variant_parts = []
            if item.size:
                variant_parts.append(f"Size: {item.size.name}")
            if item.color:
                variant_parts.append(f"Color: {item.color.name}")
            if variant_parts:
                variant_info = f" ({', '.join(variant_parts)})"
        
        description = f"{item.product.name}{variant_info}"
        if item.description:
            description += f" - {item.description}"
        
        items_data.append([
            description,
            str(item.quantity),
            format_currency(item.unit_price),
            format_currency(item.subtotal)
        ])
    
    items_table = Table(items_data, colWidths=[3*inch, 0.8*inch, 1.2*inch, 1*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Totals
    totals_data = [
        ['Subtotal:', format_currency(invoice.subtotal)],
        ['Tax:', format_currency(invoice.tax_amount)],
        ['Discount:', format_currency(invoice.discount_amount)],
        ['Total:', format_currency(invoice.total)],
        ['Amount Paid:', format_currency(invoice.amount_paid)],
        ['Balance:', format_currency(invoice.balance)],
    ]
    
    totals_table = Table(totals_data, colWidths=[2*inch, 2*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (0, -2), (1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTSIZE', (0, -2), (1, -1), 12),
        ('TEXTCOLOR', (0, -2), (1, -1), colors.HexColor('#1a1a1a')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEABOVE', (0, -2), (1, -2), 1, colors.black),
    ]))
    elements.append(totals_table)
    
    # Payments
    if invoice.payments.exists():
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("Payments:", heading_style))
        
        payments_data = [['Date', 'Method', 'Reference', 'Amount']]
        for payment in invoice.payments.all():
            # Get payment method display name
            payment_methods_dict = dict(Payment.PAYMENT_METHODS)
            payment_method_display = payment_methods_dict.get(payment.payment_method, payment.payment_method.title())
            payments_data.append([
                payment.payment_date.strftime('%Y-%m-%d'),
                payment_method_display,
                payment.reference or '-',
                format_currency(payment.amount)
            ])
        
        payments_table = Table(payments_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1*inch])
        payments_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(payments_table)
    
    # Notes
    if invoice.notes:
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("Notes:", heading_style))
        elements.append(Paragraph(invoice.notes, normal_style))
    
    # Footer
    elements.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", footer_style))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


def create_balance_sheet_pdf(data):
    """Generate PDF for balance sheet"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a1a1a'),
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    # Title
    elements.append(Paragraph("BALANCE SHEET", title_style))
    elements.append(Paragraph(f"As of {datetime.strptime(data['date'], '%Y-%m-%d').strftime('%B %d, %Y')}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Assets
    assets_data = [['Account', 'Code', 'Amount']]
    for account_name, account_info in data['assets'].items():
        assets_data.append([
            account_name,
            account_info['account_code'],
            format_currency(account_info['balance'])
        ])
    assets_data.append(['TOTAL ASSETS', '', format_currency(data['total_assets'])])
    
    # Liabilities
    liabilities_data = [['Account', 'Code', 'Amount']]
    for account_name, account_info in data['liabilities'].items():
        liabilities_data.append([
            account_name,
            account_info['account_code'],
            format_currency(account_info['balance'])
        ])
    liabilities_data.append(['TOTAL LIABILITIES', '', format_currency(data['total_liabilities'])])
    
    # Equity
    equity_data = [['Account', 'Code', 'Amount']]
    for account_name, account_info in data['equity'].items():
        equity_data.append([
            account_name,
            account_info['account_code'],
            format_currency(account_info['balance'])
        ])
    equity_data.append(['TOTAL EQUITY', '', format_currency(data['total_equity'])])
    
    # Create tables
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])
    
    elements.append(Paragraph("ASSETS", styles['Heading2']))
    assets_table = Table(assets_data, colWidths=[3*inch, 1*inch, 1.5*inch])
    assets_table.setStyle(table_style)
    elements.append(assets_table)
    elements.append(Spacer(1, 0.3*inch))
    
    elements.append(Paragraph("LIABILITIES", styles['Heading2']))
    liabilities_table = Table(liabilities_data, colWidths=[3*inch, 1*inch, 1.5*inch])
    liabilities_table.setStyle(table_style)
    elements.append(liabilities_table)
    elements.append(Spacer(1, 0.3*inch))
    
    elements.append(Paragraph("EQUITY", styles['Heading2']))
    equity_table = Table(equity_data, colWidths=[3*inch, 1*inch, 1.5*inch])
    equity_table.setStyle(table_style)
    elements.append(equity_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer


def create_income_statement_pdf(data):
    """Generate PDF for income statement"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a1a1a'),
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    # Title
    date_from = datetime.strptime(data['period_start'], '%Y-%m-%d').strftime('%B %d, %Y')
    date_to = datetime.strptime(data['period_end'], '%Y-%m-%d').strftime('%B %d, %Y')
    elements.append(Paragraph("INCOME STATEMENT", title_style))
    elements.append(Paragraph(f"Period: {date_from} to {date_to}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Revenue
    revenue_data = [['Account', 'Code', 'Amount']]
    for account_name, account_info in data['revenue'].items():
        revenue_data.append([
            account_name,
            account_info['account_code'],
            format_currency(account_info['amount'])
        ])
    revenue_data.append(['TOTAL REVENUE', '', format_currency(data['total_revenue'])])
    
    # Expenses
    expenses_data = [['Account', 'Code', 'Amount']]
    for account_name, account_info in data['expenses'].items():
        expenses_data.append([
            account_name,
            account_info['account_code'],
            format_currency(account_info['amount'])
        ])
    expenses_data.append(['TOTAL EXPENSES', '', format_currency(data['total_expenses'])])
    
    # Net Income
    net_income_data = [
        ['NET INCOME', format_currency(data['net_income'])]
    ]
    
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])
    
    elements.append(Paragraph("REVENUE", styles['Heading2']))
    revenue_table = Table(revenue_data, colWidths=[3*inch, 1*inch, 1.5*inch])
    revenue_table.setStyle(table_style)
    elements.append(revenue_table)
    elements.append(Spacer(1, 0.3*inch))
    
    elements.append(Paragraph("EXPENSES", styles['Heading2']))
    expenses_table = Table(expenses_data, colWidths=[3*inch, 1*inch, 1.5*inch])
    expenses_table.setStyle(table_style)
    elements.append(expenses_table)
    elements.append(Spacer(1, 0.3*inch))
    
    net_income_table = Table(net_income_data, colWidths=[3*inch, 2.5*inch])
    net_income_style = TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a1a1a')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('LINEABOVE', (0, 0), (1, 0), 2, colors.black),
    ])
    net_income_table.setStyle(net_income_style)
    elements.append(net_income_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer


def create_trial_balance_pdf(data):
    """Generate PDF for trial balance"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, landscape=True)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a1a1a'),
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    # Title
    elements.append(Paragraph("TRIAL BALANCE", title_style))
    elements.append(Paragraph(f"As of {datetime.strptime(data['date'], '%Y-%m-%d').strftime('%B %d, %Y')}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Accounts
    accounts_data = [['Account Code', 'Account Name', 'Type', 'Debit', 'Credit']]
    for account in data['accounts']:
        accounts_data.append([
            account['account_code'],
            account['account_name'],
            account['account_type'].title(),
            format_currency(account['debit']) if account['debit'] > 0 else '',
            format_currency(account['credit']) if account['credit'] > 0 else '',
        ])
    
    accounts_data.append(['', '', 'TOTAL', format_currency(data['total_debits']), format_currency(data['total_credits'])])
    
    accounts_table = Table(accounts_data, colWidths=[1*inch, 3*inch, 1*inch, 1.5*inch, 1.5*inch])
    accounts_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (3, 0), (4, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(accounts_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

