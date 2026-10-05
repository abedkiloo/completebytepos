"""One sale followed from the till to stock, books and every report."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounting.models import JournalEntry
from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SUPER_ADMIN
from agents.push import FakePushNotifier, set_push_notifier
from inventory.models import StockMovement
from products.models import Category, Product
from sales.models import Sale
from settings.test_utils import enable_maker_checker
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class SaleToReportFlowTests(SalesAPITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        set_push_notifier(FakePushNotifier())
        enable_maker_checker()
        self.manager = User.objects.create_user('flow_mgr', password='x')
        UserProfile.objects.create(
            user=self.manager, role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER), is_active=True,
        )
        self.admin = User.objects.create_superuser('flow_admin', 'flow@t.com', 'x')
        UserProfile.objects.create(
            user=self.admin, role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN), is_active=True,
        )
        category = Category.objects.create(name='Flow', is_active=True)
        self.soap = Product.objects.create(
            name='Soap', sku='FLOW-SOAP', category=category, price=Decimal('100'),
            cost=Decimal('60'), stock_quantity=20, track_stock=True, is_active=True,
        )
        self.salt = Product.objects.create(
            name='Salt', sku='FLOW-SALT', category=category, price=Decimal('50'),
            cost=Decimal('20'), stock_quantity=10, track_stock=True, is_active=True,
        )
        self.tenant, self.branch, _ = ManagerAPITestCase.create_tenant_with_branches(
            self.sales_user
        )
        self._bind(self.client)

    def tearDown(self):
        set_push_notifier(FakePushNotifier())
        super().tearDown()

    def _bind(self, client):
        session = client.session
        session['current_tenant_id'] = self.tenant.id
        session['current_branch_id'] = self.branch.id
        session.save()
        return client

    def _client(self, user):
        client = self.client.__class__()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}'
        )
        return self._bind(client)

    def _report(self, path):
        response = self._client(self.admin).get(f'/api/reports/{path}')
        self.assertEqual(response.status_code, 200, (path, response.data))
        return response.data

    def _stock(self):
        self.soap.refresh_from_db()
        self.salt.refresh_from_db()
        return self.soap.stock_quantity, self.salt.stock_quantity

    def _assert_reports(self, *, count, revenue, items, soap_sold, salt_sold, by_person):
        sales = self._report('sales/')['summary']
        self.assertEqual(sales['total_sales'], count)
        self.assertEqual(Decimal(str(sales['total_revenue'] or 0)), Decimal(revenue))
        self.assertEqual(sales['total_items'], items)

        overview = self._report('sales_overview/?period=today')['summary']
        self.assertEqual(overview['sales_count'], count)
        self.assertEqual(overview['gross_revenue'], float(revenue))
        self.assertEqual(overview['items_sold'], items)

        dashboard = self._report('dashboard/')
        self.assertEqual(dashboard['today'], {'sales_count': count, 'total': float(revenue)})
        self.assertEqual(dashboard['month']['total'], float(revenue))

        self.assertEqual(
            self._report('profit_loss/')['summary']['total_revenue'], float(revenue)
        )

        sold = {p['product__name']: p['quantity_sold'] for p in self._report('products/')['products']}
        self.assertEqual(sold.get('Soap', 0), soap_sold)
        self.assertEqual(sold.get('Salt', 0), salt_sold)
        top = {p['name']: p['quantity_sold'] for p in self._report('top_products/?period=today')['items']}
        self.assertEqual(top.get('Soap', 0), soap_sold)
        self.assertEqual(top.get('Salt', 0), salt_sold)

        person = self._report('sales_by_person/?period=today')
        self.assertEqual(person['summary']['sales_count'], count)
        self.assertEqual(person['summary']['gross_sales'], float(revenue))
        self.assertEqual(person['summary']['items_sold'], items)
        self.assertEqual(
            {s['username']: (s['sales_count'], s['gross_sales']) for s in person['staff']},
            by_person,
        )

        daily = self._client(self.admin).get(
            '/api/sales/daily/', {'date': timezone.localdate().isoformat()}
        ).data['summary']
        self.assertEqual(daily['orders_count'], count)
        self.assertEqual(Decimal(daily['total_sales']), Decimal(revenue))

    def _assert_stock_value(self, soap, salt):
        valuation = self._report('stock_valuation/')
        quantities = {row['item']: row['quantity'] for row in valuation['items']}
        self.assertEqual(quantities, {'Soap': soap, 'Salt': salt})
        self.assertEqual(
            valuation['summary']['inventory_value'], float(soap * 60 + salt * 20)
        )
        self.assertEqual(
            self._report('inventory/')['total_inventory_value'], float(soap * 60 + salt * 20)
        )

    def _revenue_booked(self, sale):
        return JournalEntry.objects.filter(
            reference_type='sale', reference_id=sale.id,
            account__account_code='4000', entry_type='credit',
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    def test_sale_moves_stock_books_and_every_report(self):
        self._assert_reports(count=0, revenue='0', items=0, soap_sold=0, salt_sold=0, by_person={})

        created = self.client.post('/api/sales/', {
            'items': [
                {'product_id': self.soap.id, 'quantity': '2'},
                {'product_id': self.salt.id, 'quantity': '3'},
            ],
            'payment_method': 'cash', 'amount_paid': '350',
            'sale_type': 'pos', 'client_channel': 'web',
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data['status'], 'pending_approval')
        sale = Sale.objects.get(pk=created.data['id'])

        self.assertEqual(self._stock(), (20, 10))
        self.assertFalse(StockMovement.objects.filter(reference=sale.sale_number).exists())
        self.assertEqual(self._revenue_booked(sale), Decimal('0'))
        self._assert_reports(count=0, revenue='0', items=0, soap_sold=0, salt_sold=0, by_person={})
        self._assert_stock_value(20, 10)

        approved = self._client(self.manager).post(f'/api/sales/{sale.id}/complete/', {}, format='json')
        self.assertEqual(approved.status_code, 200, approved.data)
        self.assertEqual(approved.data['status'], 'completed')

        self.assertEqual(self._stock(), (18, 7))
        movements = StockMovement.objects.filter(
            reference=sale.sale_number, movement_type='sale',
        ).values_list('product__name', 'quantity')
        self.assertEqual(sorted(movements), [('Salt', 3), ('Soap', 2)])
        self.assertEqual(self._revenue_booked(sale), Decimal('350'))
        self._assert_reports(
            count=1, revenue='350', items=5, soap_sold=2, salt_sold=3,
            by_person={self.sales_user.username: (1, 350.0)},
        )
        self._assert_stock_value(18, 7)

        direct = self._client(self.manager).post('/api/sales/', {
            'items': [{'product_id': self.soap.id, 'quantity': '1'}],
            'payment_method': 'cash', 'amount_paid': '100',
            'sale_type': 'pos', 'client_channel': 'web',
        }, format='json')
        self.assertEqual(direct.status_code, 201, direct.data)
        self.assertEqual(direct.data['status'], 'completed')
        self.assertEqual(self._stock(), (17, 7))
        self.assertEqual(self._revenue_booked(Sale.objects.get(pk=direct.data['id'])), Decimal('100'))
        self._assert_reports(
            count=2, revenue='450', items=6, soap_sold=3, salt_sold=3,
            by_person={self.sales_user.username: (1, 350.0), 'flow_mgr': (1, 100.0)},
        )
        self._assert_stock_value(17, 7)

        salt_line = sale.items.get(product=self.salt)
        refund = self._client(self.admin).post(f'/api/sales/{sale.id}/refund/', {
            'items': [{'sale_item_id': salt_line.id, 'quantity': 1}],
            'reason': 'Damaged bag', 'refund_method': 'cash',
        }, format='json')
        self.assertEqual(refund.status_code, 202, refund.data)
        self.assertEqual(self._stock(), (17, 7))
        self.assertEqual(self._report('dashboard/')['sales_returns'], {'total': 0.0, 'count': 0})

        change_id = refund.data['pending_change']['id']
        checked = self._client(self.manager).post(
            f'/api/approvals/pending-changes/{change_id}/approve/', {}, format='json',
        )
        self.assertEqual(checked.status_code, 200, checked.data)
        self.assertEqual(self._stock(), (17, 8))
        self.assertTrue(
            StockMovement.objects.filter(movement_type='return', product=self.salt, quantity=1).exists()
        )
        self._assert_stock_value(17, 8)
        dashboard = self._report('dashboard/')
        self.assertEqual(dashboard['sales_returns'], {'total': 50.0, 'count': 1})
        person = self._report('sales_by_person/?period=today')['summary']
        self.assertEqual(person['refunds_total'], 50.0)
        self.assertEqual(person['net_sales'], 400.0)
