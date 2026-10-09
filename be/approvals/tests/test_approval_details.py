from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from approvals.details import pending_change_details
from approvals.models import PendingChange
from approvals.registry import (
    ACTION_PRODUCT_PRICE,
    ACTION_SALE_BACKFILL,
    ACTION_SALE_REFUND,
    ACTION_STOCK_PURCHASE,
    ACTION_STORE_SETTINGS,
)
from products.models import Category, Product
from sales.models import Customer, Sale, SaleItem


def _sections(details):
    return {section['title']: section for section in details['sections']}


def _facts(section):
    return {fact['label']: fact['value'] for fact in section['facts']}


class ApprovalDetailsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maker = User.objects.create_user('details_maker', password='x', first_name='Amina')
        cls.category = Category.objects.create(name='Details Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Blue Kitenge',
            sku='DET-1',
            category=cls.category,
            price=Decimal('250.00'),
            cost=Decimal('100.00'),
            stock_quantity=10,
            is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='Mama Duka', phone='254700000111', wallet_balance=Decimal('-300'),
        )

    def _change(self, **kwargs):
        defaults = {
            'entity_repr': 'x',
            'reason': 'because',
            'made_by': self.maker,
            'original_values': {},
            'proposed_values': {},
        }
        defaults.update(kwargs)
        return PendingChange.objects.create(**defaults)

    def test_refund_shows_sale_items_and_lines_to_return(self):
        sale = Sale.objects.create(
            sale_number='DET-SALE-1',
            status='completed',
            subtotal=Decimal('750.00'),
            total=Decimal('750.00'),
            amount_paid=Decimal('500.00'),
            payment_method='mpesa',
            payment_reference='QWE123',
            customer=self.customer,
            cashier=self.maker,
        )
        item = SaleItem.objects.create(
            sale=sale, product=self.product, quantity=3,
            unit_price=Decimal('250.00'), subtotal=Decimal('750.00'),
        )
        change = self._change(
            action_type=ACTION_SALE_REFUND,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            apply_payload={'full': False, 'items': [{'sale_item_id': item.pk, 'quantity': 1}]},
        )
        sections = _sections(pending_change_details(change))
        self.assertEqual(sections['Items']['lines'][0]['name'], 'Blue Kitenge')
        self.assertEqual(sections['Items']['lines'][0]['quantity'], '3')
        money = _facts(sections['Money'])
        self.assertEqual(money['Payment method'], 'M-PESA')
        self.assertEqual(money['Payment reference'], 'QWE123')
        self.assertEqual(Decimal(money['Balance left as debt']), Decimal('250.00'))
        sale_facts = _facts(sections['Sale'])
        self.assertEqual(sale_facts['Customer'], 'Mama Duka')
        self.assertEqual(Decimal(sale_facts['Wallet debt now']), Decimal('300'))
        self.assertIn('Items to return', sections)

    def test_past_sale_resolves_product_names_and_totals(self):
        change = self._change(
            action_type=ACTION_SALE_BACKFILL,
            entity_type='sales.SaleBackfill',
            entity_id='new',
            apply_payload={
                'occurred_at': '2026-09-01T10:00:00+03:00',
                'sale_type': 'pos',
                'customer_id': self.customer.pk,
                'served_by_id': self.maker.pk,
                'payment_method': 'cash',
                'amount_paid': '300',
                'items': [{'product_id': self.product.pk, 'quantity': 2}],
                'backfill_reason': 'Power outage',
            },
        )
        sections = _sections(pending_change_details(change))
        line = sections['Items']['lines'][0]
        self.assertEqual(line['name'], 'Blue Kitenge')
        self.assertEqual(Decimal(line['subtotal']), Decimal('500.00'))
        money = _facts(sections['Money'])
        self.assertEqual(Decimal(money['Total']), Decimal('500.00'))
        self.assertEqual(Decimal(money['Balance left as debt']), Decimal('200.00'))
        header = _facts(sections['Past sale'])
        self.assertEqual(header['Sold by'], 'Amina')
        self.assertEqual(header['Reason'], 'Power outage')

    def test_product_change_shows_current_product(self):
        change = self._change(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            original_values={'price': '250.00'},
            proposed_values={'price': '300.00'},
        )
        facts = _facts(_sections(pending_change_details(change))['Product now'])
        self.assertEqual(facts['Product'], 'Blue Kitenge')
        self.assertEqual(Decimal(facts['Selling price']), Decimal('250.00'))
        self.assertEqual(facts['Stock on hand'], '10')

    def test_stock_purchase_shows_product_and_quantity(self):
        change = self._change(
            action_type=ACTION_STOCK_PURCHASE,
            entity_type='inventory.StockMovement',
            entity_id='new',
            entity_repr='Blue Kitenge',
            apply_payload={
                'product_id': self.product.pk,
                'quantity': 5,
                'unit_cost': '80.00',
                'notes': 'Restock',
                'reference': 'PO-9',
            },
        )
        facts = _facts(_sections(pending_change_details(change))['Stock movement'])
        self.assertEqual(facts['Product'], 'Blue Kitenge')
        self.assertEqual(facts['Quantity'], '5')
        self.assertEqual(Decimal(facts['Unit cost']), Decimal('80.00'))
        self.assertEqual(facts['Reference'], 'PO-9')
        self.assertEqual(facts['Type'], 'Stock purchase')

    def test_store_settings_lists_requested_fields(self):
        change = self._change(
            action_type=ACTION_STORE_SETTINGS,
            entity_type='settings.StoreSettings',
            entity_id='1',
            original_values={'maker_checker_enabled': False},
            proposed_values={'maker_checker_enabled': True},
        )
        facts = _facts(_sections(pending_change_details(change))['Settings change'])
        self.assertEqual(facts['Maker Checker Enabled (now)'], 'No')
        self.assertEqual(facts['Maker Checker Enabled (requested)'], 'Yes')
