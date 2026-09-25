"""Branded invoice and financial PDFs."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from utils.pdf_generator import (
    create_balance_sheet_pdf,
    create_income_statement_pdf,
    create_invoice_pdf,
    create_trial_balance_pdf,
    format_currency,
)


def _invoice(**overrides):
    invoice = MagicMock()
    invoice.invoice_number = 'INV-1'
    invoice.issued_date = date(2026, 9, 1)
    invoice.created_at = datetime(2026, 9, 1, 10, 0)
    invoice.due_date = date(2026, 9, 15)
    invoice.status = 'partial'
    invoice.customer_name = 'Martha'
    invoice.customer_email = 'm@x.com'
    invoice.customer_phone = '0718'
    invoice.customer_address = 'Nairobi'
    invoice.subtotal = Decimal('100')
    invoice.tax_amount = Decimal('0')
    invoice.discount_amount = Decimal('0')
    invoice.total = Decimal('100')
    invoice.amount_paid = Decimal('40')
    invoice.balance = Decimal('60')
    invoice.notes = ''
    invoice.items.select_related.return_value.all.return_value = []
    invoice.payments.exists.return_value = False
    for key, value in overrides.items():
        setattr(invoice, key, value)
    return invoice


class PdfGeneratorTests(SimpleTestCase):
    def test_format_currency(self):
        self.assertIn('1,000.50', format_currency(Decimal('1000.50')))
        self.assertIn('10.00', format_currency(10))

    def test_invoice_pdf_empty_lines_and_notes(self):
        invoice = _invoice(
            issued_date=None,
            due_date=None,
            customer_name='',
            notes='Pay by Friday',
        )
        pdf = create_invoice_pdf(invoice).read()
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_invoice_pdf_variant_and_payments(self):
        sized = MagicMock()
        sized.name = 'Large'
        coloured = MagicMock()
        coloured.name = 'White'
        product = MagicMock()
        product.name = 'Sofa'
        item = MagicMock(
            variant=object(),
            size=sized,
            color=coloured,
            product=product,
            description='Custom stitch',
            quantity=1,
            unit_price=Decimal('100'),
            subtotal=Decimal('100'),
        )
        orphan = MagicMock(
            variant=None,
            product=None,
            description='Misc',
            quantity=2,
            unit_price=Decimal('10'),
            subtotal=Decimal('20'),
        )
        invoice = _invoice()
        invoice.items.select_related.return_value.all.return_value = [item, orphan]
        payment = MagicMock(
            payment_method='cash',
            payment_date=date(2026, 9, 1),
            reference=None,
            amount=Decimal('40'),
        )
        unknown = MagicMock(
            payment_method='voucher',
            payment_date=date(2026, 9, 2),
            reference='V-1',
            amount=Decimal('10'),
        )
        invoice.payments.exists.return_value = True
        invoice.payments.all.return_value = [payment, unknown]
        pdf = create_invoice_pdf(invoice).read()
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_financial_pdfs_include_brand_header(self):
        balance = create_balance_sheet_pdf(
            {
                'date': '2026-09-01',
                'assets': {'Cash': {'account_code': '1000', 'balance': 100}},
                'total_assets': 100,
                'liabilities': {'AP': {'account_code': '2000', 'balance': 40}},
                'total_liabilities': 40,
                'equity': {'Capital': {'account_code': '3000', 'balance': 60}},
                'total_equity': 60,
            }
        ).read()
        income = create_income_statement_pdf(
            {
                'period_start': '2026-09-01',
                'period_end': '2026-09-30',
                'revenue': {'Sales': {'account_code': '4000', 'amount': 200}},
                'total_revenue': 200,
                'expenses': {'Rent': {'account_code': '5000', 'amount': 50}},
                'total_expenses': 50,
                'net_income': 150,
            }
        ).read()
        trial = create_trial_balance_pdf(
            {
                'date': '2026-09-30',
                'accounts': [
                    {
                        'account_code': '1000',
                        'account_name': 'Cash',
                        'account_type': 'asset',
                        'debit': 100,
                        'credit': 0,
                    },
                    {
                        'account_code': '2000',
                        'account_name': 'AP',
                        'account_type': 'liability',
                        'debit': 0,
                        'credit': 100,
                    },
                ],
                'total_debits': 100,
                'total_credits': 100,
            }
        ).read()
        for pdf in (balance, income, trial):
            self.assertTrue(pdf.startswith(b'%PDF'))
            self.assertGreater(len(pdf), 400)
