"""Managers and admins can move a sale onto another business date."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounting.models import JournalEntry, Transaction
from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES
from products.models import Category, Product
from sales.daily_sales import get_daily_sales_report
from sales.models import Sale
from sales.sale_date import DATE_CORRECTION_FUTURE
from utils.tests.api_test_base import ManagerAPITestCase


class SaleDateCorrectionTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = Category.objects.create(name='Date Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Date Item',
            sku='DATE-1',
            category=cls.category,
            price=Decimal('100.00'),
            cost=Decimal('40.00'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        cls.sales_user = User.objects.create_user('date_cashier', password='x')
        UserProfile.objects.create(
            user=cls.sales_user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        self.tenant, self.branch, _ = self.create_tenant_with_branches(self.manager_user)
        self.set_session_branch(self.tenant, self.branch)

    def _sale_payload(self):
        return {
            'items': [{'product_id': self.product.id, 'quantity': '1'}],
            'payment_method': 'cash',
            'amount_paid': '100.00',
            'sale_type': 'pos',
            'client_channel': 'web',
        }

    def _create_completed_sale(self):
        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        sale = Sale.objects.get(pk=created.data['id'])
        self.assertEqual(sale.status, 'completed')
        return sale

    def test_manager_moves_sale_date_and_books(self):
        sale = self._create_completed_sale()
        original_local = timezone.localtime(sale.occurred_at)
        target = (timezone.localdate() - timedelta(days=1)).isoformat()

        response = self.client.post(
            f'/api/sales/{sale.id}/correct-date/',
            {'occurred_on': target},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        sale.refresh_from_db()
        self.assertEqual(timezone.localtime(sale.occurred_at).date().isoformat(), target)
        self.assertEqual(timezone.localtime(sale.occurred_at).time(), original_local.time())
        self.assertTrue(response.data['can_correct_date'])
        self.assertEqual(
            set(
                JournalEntry.objects.filter(
                    reference_type='sale', reference_id=sale.id
                ).values_list('entry_date', flat=True)
            ),
            {timezone.localtime(sale.occurred_at).date()},
        )
        txn = Transaction.objects.get(reference_type='sale', reference_id=sale.id)
        self.assertEqual(txn.transaction_date, timezone.localtime(sale.occurred_at).date())

        yesterday = get_daily_sales_report(date_str=target)
        ids = [row['id'] for row in yesterday['orders']]
        self.assertIn(sale.id, ids)

    def test_admin_can_set_tomorrow(self):
        sale = self._create_completed_sale()
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.post(
            f'/api/sales/{sale.id}/correct-date/',
            {'occurred_on': tomorrow},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        sale.refresh_from_db()
        self.assertEqual(timezone.localtime(sale.occurred_at).date().isoformat(), tomorrow)

    def test_cannot_set_two_days_ahead(self):
        sale = self._create_completed_sale()
        far = (timezone.localdate() + timedelta(days=2)).isoformat()
        response = self.client.post(
            f'/api/sales/{sale.id}/correct-date/',
            {'occurred_on': far},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(DATE_CORRECTION_FUTURE, str(response.data))

    def test_salesperson_cannot_change_date(self):
        sale = self._create_completed_sale()
        client = self.client.__class__()
        token = RefreshToken.for_user(self.sales_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        session = client.session
        session['current_tenant_id'] = self.tenant.id
        session['current_branch_id'] = self.branch.id
        session.save()
        response = client.post(
            f'/api/sales/{sale.id}/correct-date/',
            {'occurred_on': timezone.localdate().isoformat()},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cancelled_sale_is_blocked(self):
        sale = self._create_completed_sale()
        sale.status = 'cancelled'
        sale.save(update_fields=['status'])
        response = self.client.post(
            f'/api/sales/{sale.id}/correct-date/',
            {'occurred_on': timezone.localdate().isoformat()},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
