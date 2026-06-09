"""Sales staff performance report."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status

from sales.models import Sale, SaleRefund
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class SalesPersonReportTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.sales_user2 = User.objects.create_user('staff_b', password='x')
        cls.sale_a = Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            amount_paid=Decimal('100.00'),
            cashier=cls.manager_user,
        )
        cls.sale_b = Sale.objects.create(
            status='completed',
            payment_method='mpesa',
            subtotal=Decimal('250.00'),
            total=Decimal('250.00'),
            amount_paid=Decimal('250.00'),
            cashier=cls.sales_user2,
        )
        SaleRefund.objects.create(
            sale=cls.sale_a,
            refund_type='partial',
            amount=Decimal('20.00'),
            reason='Customer return',
            refunded_by=cls.manager_user,
        )

    def test_sales_by_person_json(self):
        month = timezone.now().strftime('%Y-%m')
        response = self.client.get('/api/reports/sales_by_person/', {'month': month})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('staff', response.data)
        self.assertIn('summary', response.data)
        self.assertGreaterEqual(len(response.data['staff']), 2)
        mgr = next(r for r in response.data['staff'] if r['user_id'] == self.manager_user.id)
        self.assertEqual(mgr['sales_count'], 1)
        self.assertEqual(mgr['gross_sales'], 100.0)
        self.assertEqual(mgr['refunds_total'], 20.0)
        self.assertEqual(mgr['net_sales'], 80.0)

    def test_sales_by_person_filter_cashier(self):
        month = timezone.now().strftime('%Y-%m')
        response = self.client.get(
            '/api/reports/sales_by_person/',
            {'month': month, 'cashier_id': self.sales_user2.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['staff']), 1)
        self.assertEqual(response.data['staff'][0]['net_sales'], 250.0)
        self.assertEqual(len(response.data['transactions']), 1)

    def test_sales_by_person_csv(self):
        month = timezone.now().strftime('%Y-%m')
        response = self.client.get(
            '/api/reports/sales_by_person/',
            {'month': month, 'format': 'csv'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/csv', response['Content-Type'])
        body = response.content.decode('utf-8-sig')
        self.assertIn('Sales staff performance report', body)
        self.assertIn('staff_b', body)

    def test_holding_sales_excluded(self):
        Sale.objects.create(
            status='holding',
            payment_method='cash',
            subtotal=Decimal('999.00'),
            total=Decimal('999.00'),
            amount_paid=Decimal('0'),
            cashier=self.manager_user,
        )
        month = timezone.now().strftime('%Y-%m')
        response = self.client.get('/api/reports/sales_by_person/', {'month': month})
        mgr = next(r for r in response.data['staff'] if r['user_id'] == self.manager_user.id)
        self.assertEqual(mgr['gross_sales'], 100.0)


class SalesPersonReportAccessTests(SalesAPITestCase):
    def test_sales_persona_denied_without_reports_view(self):
        month = timezone.now().strftime('%Y-%m')
        response = self.client.get('/api/reports/sales_by_person/', {'month': month})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
