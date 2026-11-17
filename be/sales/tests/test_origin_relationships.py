"""Shop, field-order, and field-load sales stay separate in reports and payroll.

A field-load sale is paid to the agent and listed on its own total. It is not
a shop sale and it is not a packed field order.
"""

from datetime import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_FIELD_AGENT
from payroll.adapters.commission import net_field_sales_for_user
from payroll.daily_commission import agent_day_commission
from products.models import Category, Product
from sales.daily_sales import get_daily_sales_report
from sales.models import Customer, Sale, SaleItem
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase


def _sale(user, source, total, phone_customer=None):
    """
    Save one completed sale credited to ``user``.

    Args:
        user: Cashier and served-by user.
        source: ``pos``, ``field``, or ``field_load``. Length 3–10.
        total: Sale total, 0.01 through 1000000, two decimal places.
        phone_customer: Optional customer. The phone must not appear in reports.

    Returns:
        Sale: Completed row for today.

    Raises:
        None.
    """
    amount = Decimal(total)
    return Sale.objects.create(
        sale_number=f'REL-{source}-{user.id}-{Sale.objects.count() + 1}',
        status='completed',
        sale_type='pos',
        entry_source=source,
        subtotal=amount,
        total=amount,
        amount_paid=amount,
        payment_method='cash',
        cashier=user,
        served_by=user,
        customer=phone_customer,
        occurred_at=timezone.now(),
    )


class OriginRelationshipTests(ManagerAPITestCase):
    """Reports, the day book, and commission keep the three sale origins apart."""

    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user('origin_staff', password='x', first_name='Ada', last_name='Lane')
        self.customer = Customer.objects.create(name='Origin Duka', phone='0718555001')
        self.shop = _sale(self.staff, 'pos', '100.00', self.customer)
        self.field = _sale(self.staff, 'field', '200.00', self.customer)
        self.load = _sale(self.staff, 'field_load', '300.00', self.customer)

    def test_the_person_report_keeps_shop_field_and_load_apart(self):
        month = timezone.localdate().strftime('%Y-%m')
        response = self.client.get(
            '/api/reports/sales_by_person/',
            {'month': month, 'cashier_id': self.staff.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        row = response.data['staff'][0]
        self.assertEqual(row['sales_count'], 3)
        self.assertEqual(row['field_sales_count'], 1)
        self.assertEqual(row['field_sales'], 200.0)
        self.assertEqual(row['field_load_sales_count'], 1)
        self.assertEqual(row['field_load_sales'], 300.0)
        self.assertEqual(row['shop_sales_count'], 1)
        self.assertEqual(row['shop_sales'], 100.0)
        origins = {item['sale_origin'] for item in response.data['transactions']}
        self.assertEqual(origins, {'shop', 'field', 'field_load'})
        self.assertNotIn('0718555001', response.content.decode())

    def test_the_day_book_subtracts_both_field_origins_from_the_shop(self):
        report = get_daily_sales_report(
            date_str=timezone.localdate().isoformat(),
            cashier_id=self.staff.id,
        )
        summary = report['summary']
        self.assertEqual(summary['orders_count'], 3)
        self.assertEqual(summary['field_orders_count'], 1)
        self.assertEqual(summary['field_sales_total'], '200.00')
        self.assertEqual(summary['field_load_orders_count'], 1)
        self.assertEqual(summary['field_load_sales_total'], '300.00')
        self.assertEqual(summary['shop_orders_count'], 1)
        self.assertEqual(summary['shop_sales_total'], '100.00')

    def test_commission_pays_the_field_order_and_the_load_and_skips_the_shop(self):
        category = Category.objects.create(name='Origin timber', is_active=True)
        product = Product.objects.create(
            name='Plain timber',
            sku=f'OT-{self.staff.id}',
            category=category,
            price=Decimal('100'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )
        for sale in (self.field, self.load):
            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=1,
                unit_price=sale.total,
                subtotal=sale.total,
            )
        today = timezone.localdate()
        net = net_field_sales_for_user(self.staff.id, year=today.year, month=today.month)
        self.assertEqual(net, Decimal('500.00'))
        day = agent_day_commission(self.staff.id, today)
        self.assertEqual(day['qualifying_sales'], '500.00')
        self.assertEqual(day['sale_count'], 2)


class OriginSecurityTests(ManagerAPITestCase):
    """A stranger, the wrong role, and a hidden report cannot see these totals."""

    def test_a_stranger_cannot_open_the_report_or_the_payroll(self):
        client = APIClient()
        report = client.get('/api/reports/sales_by_person/')
        payroll = client.get('/api/payroll/settings/')
        self.assertEqual(report.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(payroll.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('0718', report.content.decode())

    def test_writing_to_the_report_is_refused(self):
        response = self.client.post('/api/reports/sales_by_person/', {}, format='json')
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED))

    def test_a_field_agent_sees_their_field_and_load_sales_only(self):
        role = Role.objects.get(name=ROLE_FIELD_AGENT)
        agent = User.objects.create_user('origin_agent', password='x')
        UserProfile.objects.create(user=agent, role='cashier', custom_role=role, is_active=True)
        other = User.objects.create_user('origin_other', password='x')
        own_field = _sale(agent, 'field', '40.00')
        own_load = _sale(agent, 'field_load', '50.00')
        _sale(agent, 'pos', '60.00')
        _sale(other, 'field', '70.00')
        token_client = APIClient()
        from rest_framework_simplejwt.tokens import RefreshToken
        token_client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(agent).access_token}')
        listed = token_client.get('/api/sales/')
        self.assertEqual(listed.status_code, status.HTTP_200_OK, listed.content)
        rows = listed.data.get('results', listed.data)
        origins = {row['sale_origin'] for row in rows}
        self.assertEqual(origins, {'field', 'field_load'})
        numbers = {row['sale_number'] for row in rows}
        self.assertEqual(numbers, {own_field.sale_number, own_load.sale_number})
        self.assertNotIn('0718', listed.content.decode())

    def test_the_person_report_stays_closed_when_sales_reports_are_off(self):
        SettingsService.set('reports', 'enable_sales_reports', False)
        try:
            closed = self.client.get('/api/reports/sales_by_person/')
            self.assertEqual(closed.status_code, status.HTTP_403_FORBIDDEN)
            self.assertNotIn('phone', closed.content.decode())
        finally:
            SettingsService.set('reports', 'enable_sales_reports', True)


class OriginStressTests(ManagerAPITestCase):
    """A few hundred mixed sales still add up on the right lines."""

    def test_one_hundred_and_twenty_sales_keep_their_origin(self):
        staff = User.objects.create_user('origin_bulk', password='x')
        for index in range(40):
            for source, total in (('pos', '10.00'), ('field', '20.00'), ('field_load', '30.00')):
                Sale.objects.create(
                    sale_number=f'BULK-{source}-{index}',
                    status='completed',
                    sale_type='pos',
                    entry_source=source,
                    subtotal=Decimal(total),
                    total=Decimal(total),
                    amount_paid=Decimal(total),
                    payment_method='cash',
                    cashier=staff,
                    served_by=staff,
                    occurred_at=timezone.make_aware(datetime(2026, 4, 2, 10, index % 60, 0)),
                )
        response = self.client.get(
            '/api/reports/sales_by_person/',
            {'month': '2026-04', 'cashier_id': staff.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        row = response.data['staff'][0]
        self.assertEqual(row['sales_count'], 120)
        self.assertEqual(row['shop_sales_count'], 40)
        self.assertEqual(row['shop_sales'], 400.0)
        self.assertEqual(row['field_sales_count'], 40)
        self.assertEqual(row['field_sales'], 800.0)
        self.assertEqual(row['field_load_sales_count'], 40)
        self.assertEqual(row['field_load_sales'], 1200.0)
        self.assertEqual(response.data['summary']['sales_count'], 120)

    def test_a_sale_with_no_staff_stays_unassigned(self):
        from datetime import datetime

        Sale.objects.create(
            sale_number='UNASSIGNED-2019',
            status='completed',
            sale_type='pos',
            entry_source='pos',
            subtotal=Decimal('15.00'),
            total=Decimal('15.00'),
            amount_paid=Decimal('15.00'),
            payment_method='cash',
            cashier=None,
            served_by=None,
            occurred_at=timezone.make_aware(datetime(2019, 7, 4, 9, 0, 0)),
        )
        response = self.client.get('/api/reports/sales_by_person/', {'month': '2019-07'})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data['staff'][0]['display_name'], 'Unassigned')
        self.assertEqual(response.data['staff'][0]['shop_sales'], 15.0)
        self.assertEqual(len(response.data['transactions']), 1)
        self.assertNotIn('0718', response.content.decode())
