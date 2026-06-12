"""
Sale checkout connects product stock, accounting journals, audit trail, and reports.
"""

from decimal import Decimal

from django.contrib.auth.models import User

from accounting.models import JournalEntry, Transaction
from accounts.models import AuditLog
from products.models import Category, Product
from sales.models import Sale
from settings.test_utils import disable_maker_checker
from utils.tests.api_test_base import ManagerAPITestCase


class SaleAccountingAuditIntegrationTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        disable_maker_checker()
        cls.category = Category.objects.create(name='Retail', is_active=True)
        cls.product = Product.objects.create(
            name='Audit Sale Item',
            sku='SALE-AUD-1',
            category=cls.category,
            price=Decimal('250.00'),
            cost=Decimal('100.00'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        cls.tenant, cls.branch, _ = cls.create_tenant_with_branches(cls.manager_user)

    def setUp(self):
        super().setUp()
        self.set_session_branch(self.tenant, self.branch)
        AuditLog.objects.all().delete()

    def test_checkout_updates_stock_creates_journal_and_audit(self):
        stock_before = self.product.stock_quantity
        hold = self.client.post(
            '/api/sales/holding/',
            {
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 2,
                        'unit_price': '250.00',
                    }
                ],
                'tax_amount': '0',
                'discount_amount': '0',
                'branch_id': self.branch.id,
            },
            format='json',
        )
        self.assertEqual(hold.status_code, 200, hold.data)

        checkout = self.client.post(
            f'/api/sales/{hold.data["id"]}/checkout/',
            {
                'payment_method': 'cash',
                'amount_paid': '500.00',
                'allow_partial_payment': False,
            },
            format='json',
        )
        self.assertEqual(checkout.status_code, 200, checkout.data)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, stock_before - 2)

        sale = Sale.objects.get(pk=hold.data['id'])
        self.assertEqual(sale.status, 'completed')
        self.assertTrue(
            Transaction.objects.filter(reference_type='sale', reference_id=sale.id).exists()
        )
        self.assertTrue(
            JournalEntry.objects.filter(reference=sale.sale_number).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(module='sales', action='checkout').exists()
        )

        income = self.client.get('/api/accounting/reports/income_statement/')
        self.assertEqual(income.status_code, 200, income.data)
        self.assertGreaterEqual(float(income.data.get('total_revenue', 0)), 500.0)
