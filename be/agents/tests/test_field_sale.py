"""A packed field order is the agent's sale: stock, books, debt, daily sales, reports."""

import io
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounting.models import Transaction
from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    ROLE_DISPATCHER,
    ROLE_FIELD_AGENT,
    ROLE_SUPER_ADMIN,
    ensure_permissions,
    sync_default_roles,
)
from agents.models import CustomerSite, FieldOrder, FieldOrderLine, SiteMedia
from agents.order_services import FieldOrderTransitionError, pack_order
from products.models import Product
from sales.models import Customer, CustomerWalletTransaction, Sale
from utils.tests.api_test_base import _enable_modules


def _png():
    buf = io.BytesIO()
    Image.new('RGB', (8, 8), color=(1, 2, 3)).save(buf, format='PNG')
    return SimpleUploadedFile('s.png', buf.getvalue(), content_type='image/png')


class _FieldSaleSetup(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        _enable_modules('sales', 'reports', 'products', 'inventory', 'pos')
        cls.agent = User.objects.create_user('fs_agent', password='x', first_name='Wanjiku')
        UserProfile.objects.create(
            user=cls.agent, role='cashier',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT), is_active=True,
        )
        cls.dispatch = User.objects.create_user('fs_disp', password='x')
        UserProfile.objects.create(
            user=cls.dispatch, role='manager',
            custom_role=Role.objects.get(name=ROLE_DISPATCHER), is_active=True,
        )
        cls.admin = User.objects.create_superuser('fs_admin', 'a@x.com', 'x')
        UserProfile.objects.create(
            user=cls.admin, role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN), is_active=True,
        )
        cls.customer = Customer.objects.create(name='Hardware Mart', phone='0711000000')
        cls.site = CustomerSite.objects.create(
            customer=cls.customer, latitude='-1.1', longitude='36.7',
            created_by=cls.agent, status=CustomerSite.STATUS_FINALIZED,
        )
        SiteMedia.objects.create(site=cls.site, image=_png(), created_by=cls.agent)

    def setUp(self):
        self.cement = Product.objects.create(
            name='Cement 50kg', sku='CEM-FS', price=Decimal('800'), cost=Decimal('600'),
            stock_quantity=20, track_stock=True,
        )

    def _order(self, quantity=3, unit_price='750'):
        order = FieldOrder.objects.create(
            site=self.site, customer=self.customer,
            status=FieldOrder.STATUS_SUBMITTED, created_by=self.agent,
        )
        FieldOrderLine.objects.create(
            order=order, product=self.cement, quantity=quantity,
            unit_price=Decimal(unit_price), product_name='Cement 50kg',
        )
        return order

    def _client(self, user):
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')


class FieldSaleTests(_FieldSaleSetup):
    def test_packing_records_the_agents_field_sale(self):
        order = pack_order(self._order(), user=self.dispatch)
        sale = order.sale

        self.assertEqual(sale.entry_source, 'field')
        self.assertTrue(sale.is_field_sale)
        self.assertEqual(sale.status, 'completed')
        self.assertEqual(sale.cashier, self.agent)
        self.assertEqual(sale.served_by, self.agent)
        self.assertEqual(sale.customer, self.customer)
        self.assertEqual(sale.total, Decimal('2250.00'))
        self.assertEqual(sale.amount_paid, Decimal('0'))
        self.assertEqual(sale.occurred_at, order.packed_at)
        self.assertEqual(sale.items.get().unit_price, Decimal('750.00'))

        self.cement.refresh_from_db()
        self.assertEqual(self.cement.stock_quantity, 17)
        self.assertTrue(
            Transaction.objects.filter(reference_type='sale', reference_id=sale.id).exists()
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('-2250.00'))
        self.assertEqual(
            CustomerWalletTransaction.objects.get(sale=sale, source_type='debt').amount,
            Decimal('2250.00'),
        )

    def test_not_enough_stock_stops_packing(self):
        order = self._order(quantity=25)
        with self.assertRaises(FieldOrderTransitionError):
            pack_order(order, user=self.dispatch)
        order.refresh_from_db()
        self.assertEqual(order.status, FieldOrder.STATUS_PACKING)
        self.assertFalse(order.stock_allocated)
        self.assertIsNone(order.sale_id)
        self.assertFalse(Sale.objects.filter(entry_source='field').exists())

    def test_fractional_quantities_are_rejected(self):
        order = self._order(quantity=Decimal('1.5'))
        with self.assertRaises(FieldOrderTransitionError) as ctx:
            pack_order(order, user=self.dispatch)
        self.assertIn('whole number', str(ctx.exception.detail))

    def test_packing_twice_does_not_create_a_second_sale(self):
        order = pack_order(self._order(), user=self.dispatch)
        self.assertEqual(Sale.objects.filter(entry_source='field').count(), 1)
        self.assertEqual(
            CustomerWalletTransaction.objects.filter(
                customer=self.customer, source_type='debt',
            ).count(),
            1,
        )
        self.assertFalse(
            CustomerWalletTransaction.objects.filter(reference=f'FO-{order.pk}').exists()
        )

        with self.assertRaises(FieldOrderTransitionError):
            pack_order(order, user=self.dispatch)
        self.assertEqual(Sale.objects.filter(entry_source='field').count(), 1)
        self.assertEqual(
            CustomerWalletTransaction.objects.filter(
                customer=self.customer, source_type='debt',
            ).count(),
            1,
        )

    def test_field_sale_counts_in_the_agents_daily_sales_and_is_labelled(self):
        pack_order(self._order(), user=self.dispatch)
        self._client(self.agent)
        response = self.client.get('/api/sales/daily/', {'date': timezone.localdate().isoformat()})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        summary = response.data['summary']
        self.assertEqual(summary['orders_count'], 1)
        self.assertEqual(summary['total_sales'], '2250.00')
        self.assertEqual(summary['field_orders_count'], 1)
        self.assertEqual(summary['field_sales_total'], '2250.00')
        self.assertEqual(summary['shop_orders_count'], 0)
        order_row = response.data['orders'][0]
        self.assertTrue(order_row['is_field_sale'])
        self.assertEqual(order_row['sale_origin'], 'field')
        self.assertEqual(order_row['payment_status'], 'debt')

    def test_sales_list_labels_and_filters_field_sales(self):
        pack_order(self._order(), user=self.dispatch)
        self._client(self.agent)
        listed = self.client.get('/api/sales/')
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        rows = listed.data.get('results', listed.data)
        self.assertEqual(rows[0]['sale_origin'], 'field')

        self._client(self.admin)
        field_only = self.client.get('/api/sales/', {'sale_origin': 'field'})
        shop_only = self.client.get('/api/sales/', {'sale_origin': 'shop'})
        self.assertEqual(len(field_only.data.get('results', field_only.data)), 1)
        self.assertEqual(len(shop_only.data.get('results', shop_only.data)), 0)

    def test_sales_by_person_report_credits_the_agent_and_splits_field_sales(self):
        pack_order(self._order(), user=self.dispatch)
        self._client(self.admin)
        response = self.client.get('/api/reports/sales_by_person/', {'period': 'today'})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        row = next(r for r in response.data['staff'] if r['user_id'] == self.agent.id)
        self.assertEqual(row['sales_count'], 1)
        self.assertEqual(row['field_sales_count'], 1)
        self.assertEqual(row['field_sales'], 2250.0)
        self.assertEqual(row['shop_sales_count'], 0)
        self.assertEqual(response.data['summary']['field_sales'], 2250.0)


class BackfillFieldSalesTests(_FieldSaleSetup):
    def _legacy_packed_order(self):
        order = self._order(quantity=2, unit_price='800')
        order.status = FieldOrder.STATUS_READY
        order.stock_allocated = True
        order.packed_at = timezone.now()
        order.save()
        self.customer.wallet_balance = Decimal('-1600.00')
        self.customer.save(update_fields=['wallet_balance'])
        CustomerWalletTransaction.objects.create(
            customer=self.customer, transaction_type='debit', source_type='debt',
            amount=Decimal('1600.00'), balance_after=Decimal('-1600.00'),
            reference=f'FO-{order.pk}', created_by=self.dispatch,
        )
        return order

    def test_dry_run_changes_nothing(self):
        order = self._legacy_packed_order()
        call_command('backfill_field_sales', stdout=io.StringIO())
        order.refresh_from_db()
        self.assertIsNone(order.sale_id)

    def test_apply_records_sale_and_reuses_existing_debt(self):
        order = self._legacy_packed_order()
        call_command('backfill_field_sales', '--apply', stdout=io.StringIO())
        order.refresh_from_db()
        self.assertTrue(order.sale.is_field_sale)
        self.assertEqual(order.sale.cashier, self.agent)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('-1600.00'))
        debt = CustomerWalletTransaction.objects.get(customer=self.customer, source_type='debt')
        self.assertEqual(debt.sale, order.sale)
        self.cement.refresh_from_db()
        self.assertEqual(self.cement.stock_quantity, 18)

        call_command('backfill_field_sales', '--apply', stdout=io.StringIO())
        self.assertEqual(Sale.objects.filter(entry_source='field').count(), 1)

    def test_skip_stock_leaves_shelves_alone(self):
        order = self._legacy_packed_order()
        call_command('backfill_field_sales', '--apply', '--skip-stock', stdout=io.StringIO())
        order.refresh_from_db()
        self.assertEqual(order.sale.status, 'completed')
        self.cement.refresh_from_db()
        self.assertEqual(self.cement.stock_quantity, 20)
