"""Debt, daily sales, and payments reports follow a moved sale or payment."""

from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from sales.daily_sales import get_customer_day_detail, get_daily_sales_report
from sales.debt_management import (
    build_debt_summary,
    list_debt_collections,
    list_debtors,
)
from sales.debt_settlement_correction import transfer_debt_settlement_customer
from sales.payments_trail import list_payments_trail
from sales.sale_customer_transfer import transfer_sale_customer
from sales.services import CustomerService
from sales.tests.test_sale_customer_transfer import (
    CUST1_PHONE,
    CUST2_PHONE,
    CUST4_PHONE,
    _assert_books,
    _debt_sale,
)
from utils.tests.api_test_base import SuperAdminAPITestCase


def _debtor_amount(rows, customer_id):
    """Debt shown for one customer on the debtor list.

    Args:
        rows: Rows from ``list_debtors``. 0–500.
        customer_id: Customer primary key, 1–2^31-1.

    Returns:
        Debt amount as Decimal, or None when that customer is not listed.
    """
    for row in rows:
        if row['id'] == customer_id:
            return Decimal(row['debt_amount'])
    return None


class CustomerTransferReportTests(SuperAdminAPITestCase):
    """Reports keep the corrected customer and amount across repeated reads."""

    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User

        from accounts.models import UserProfile
        from accounts.role_definitions import ROLE_SALES, ensure_permissions, sync_default_roles
        from sales.models import Customer

        ensure_permissions()
        roles = sync_default_roles(created_by=self.admin)
        self.sales = User.objects.create_user('report_clerk', password='x')
        UserProfile.objects.create(
            user=self.sales,
            role='cashier',
            custom_role=roles[ROLE_SALES],
            is_active=True,
        )
        self.cust1 = Customer.objects.create(
            name='Customer One', phone=CUST1_PHONE, wallet_balance=Decimal('0.00'), is_active=True,
        )
        self.cust2 = Customer.objects.create(
            name='Customer Two', phone=CUST2_PHONE, wallet_balance=Decimal('0.00'), is_active=True,
        )
        self.cust3 = Customer.objects.create(
            name='Customer Three', phone='0711888003', wallet_balance=Decimal('0.00'), is_active=True,
        )
        self.cust4 = Customer.objects.create(
            name='Customer Four', phone=CUST4_PHONE, wallet_balance=Decimal('0.00'), is_active=True,
        )
        self.sale1 = _debt_sale(self.cust1, self.sales, 'RPT-1000', '1000.00')
        self.sale2 = _debt_sale(self.cust2, self.sales, 'RPT-200', '200.00')
        self.sale4 = _debt_sale(self.cust4, self.sales, 'RPT-800', '800.00')
        self.txn = CustomerService().record_wallet_payment(
            customer=self.cust2,
            amount=Decimal('500.00'),
            payment_method='cash',
            user=self.admin,
        )
        transfer_debt_settlement_customer(
            txn_id=self.txn.id,
            target_customer_id=self.cust1.id,
            user=self.admin,
            move_sales=False,
            send_sms=False,
        )
        transfer_sale_customer(
            sale_id=self.sale4.id,
            target_customer_id=self.cust3.id,
            user=self.admin,
            send_sms=False,
        )

    def _snapshot(self):
        """Read every customer-facing report once.

        Returns:
            Dict of debtor amounts, today's collection names, daily-sales
            customer ids by sale number, and each customer's day wallet debt.
            Amounts are Decimal quantized to 0.01. Names are 0–200 characters.

        Raises:
            AssertionError: A report row carries the wrong customer's phone.
        """
        debtors, _total = list_debtors(page=1, page_size=50, user=self.admin)
        summary = build_debt_summary(user=self.admin)
        collections = list_debt_collections(on_date=timezone.localdate(), page_size=50, user=self.admin)
        daily = get_daily_sales_report(page=1, page_size=100, user=self.admin)
        trail = list_payments_trail(
            date_from=timezone.localdate().isoformat(),
            date_to=timezone.localdate().isoformat(),
            page=1,
            page_size=50,
            user=self.admin,
        )
        days = {
            customer.id: get_customer_day_detail(customer_id=customer.id)
            for customer in (self.cust1, self.cust2, self.cust3, self.cust4)
        }
        for row in collections['results']:
            if row['id'] == self.txn.id and CUST2_PHONE in str(row.get('customer_phone') or ''):
                raise AssertionError('Collection report still shows the wrong customer phone')
        return {
            'debtors': {row['id']: Decimal(row['debt_amount']) for row in debtors},
            'total_debt': summary['total_debt'],
            'collected_today': summary['collected_today'],
            'collection_names': {
                row['id']: row['customer_name'] for row in collections['results']
            },
            'order_customers': {
                order['sale_number']: (order['customer'] or {}).get('id')
                for order in daily['orders']
            },
            'collected_on_daily': daily['summary']['total_debt_collected'],
            'trail_customers': {
                row['id']: row.get('customer_id')
                for row in trail['results']
                if row.get('kind') == 'debt_settlement'
            },
            'day_debt': {
                cid: Decimal(day['customer']['wallet_debt']) for cid, day in days.items()
            },
            'day_orders': {
                cid: [order['sale_number'] for order in day['orders']]
                for cid, day in days.items()
            },
        }

    def test_reports_stay_aligned_across_eight_reads(self):
        """The same customers and amounts come back on every read."""
        _assert_books(self.cust1, self.cust2, self.cust3, self.cust4)
        first = self._snapshot()
        self.assertEqual(first['debtors'].get(self.cust1.id), Decimal('500.00'))
        self.assertEqual(first['debtors'].get(self.cust2.id), Decimal('200.00'))
        self.assertEqual(first['debtors'].get(self.cust3.id), Decimal('800.00'))
        self.assertNotIn(self.cust4.id, first['debtors'])
        self.assertEqual(first['total_debt'], Decimal('1500.00'))
        self.assertEqual(first['collected_today'], Decimal('500.00'))
        self.assertEqual(first['collection_names'][self.txn.id], 'Customer One')
        self.assertEqual(first['order_customers']['RPT-1000'], self.cust1.id)
        self.assertEqual(first['order_customers']['RPT-200'], self.cust2.id)
        self.assertEqual(first['order_customers']['RPT-800'], self.cust3.id)
        self.assertEqual(first['collected_on_daily'], '500.00')
        self.assertEqual(first['trail_customers'][self.txn.id], self.cust1.id)
        self.assertEqual(first['day_debt'][self.cust1.id], Decimal('500.00'))
        self.assertEqual(first['day_debt'][self.cust2.id], Decimal('200.00'))
        self.assertEqual(first['day_debt'][self.cust3.id], Decimal('800.00'))
        self.assertEqual(first['day_debt'][self.cust4.id], Decimal('0.00'))
        self.assertEqual(first['day_orders'][self.cust1.id], ['RPT-1000'])
        self.assertEqual(first['day_orders'][self.cust2.id], ['RPT-200'])
        self.assertEqual(first['day_orders'][self.cust3.id], ['RPT-800'])
        self.assertEqual(first['day_orders'][self.cust4.id], [])
        for _ in range(8):
            self.assertEqual(self._snapshot(), first)

    def test_debt_summary_api_matches_the_books(self):
        client = APIClient()
        anon = client.get('/api/sales/customers/debt-summary/')
        self.assertEqual(anon.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn(CUST2_PHONE, str(anon.data))

        client.force_authenticate(user=self.sales)
        denied = client.get('/api/sales/customers/debt-summary/')
        self.assertIn(denied.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_200_OK))
        self.assertNotIn(CUST4_PHONE, str(denied.data))

        client.force_authenticate(user=self.admin)
        ok = client.get('/api/sales/customers/debt-summary/')
        self.assertEqual(ok.status_code, status.HTTP_200_OK, ok.data)
        self.assertEqual(ok.data['total_debt'], '1500.00')
        self.assertEqual(ok.data['collected_today'], '500.00')
        self.assertNotIn(CUST1_PHONE, str(ok.data))
        self.assertNotIn(CUST2_PHONE, str(ok.data))
