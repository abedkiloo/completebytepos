"""Cost of goods stays with admin unless the permission is checked."""

from decimal import Decimal

from django.contrib.auth.models import AnonymousUser, User
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import (
    ROLE_MANAGER,
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from products.cost_access import redact_cost_fields, user_is_management, user_may_see_cost
from products.models import Product

HIDDEN_COST = Decimal('77.77')
SUPPLIER_PHONE = '0711666009'


class CostVisibilityTests(APITestCase):
    """A sales person and a manager do not receive cost. An admin does."""

    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.sales = cls._person('cost_sales', ROLE_SALES, 'cashier')
        cls.manager = cls._person('cost_manager', ROLE_MANAGER, 'manager')
        cls.admin = User.objects.create_superuser(
            'cost_super', 'cost-super@example.com', 'admin123',
        )
        cls.product = Product.objects.create(
            name='Hidden cost stand',
            sku='COST-HIDE-1',
            price=Decimal('200.00'),
            cost=HIDDEN_COST,
            stock_quantity=4,
            unit='piece',
            supplier_contact=SUPPLIER_PHONE,
        )
        for index in range(40):
            Product.objects.create(
                name=f'Batch stand {index}',
                sku=f'COST-BATCH-{index}',
                price=Decimal('10.00'),
                cost=HIDDEN_COST,
                stock_quantity=1,
                unit='piece',
            )

    @classmethod
    def _person(cls, username, role_name, legacy):
        user = User.objects.create_user(username, password='pass12345')
        UserProfile.objects.create(
            user=user,
            role=legacy,
            custom_role=Role.objects.get(name=role_name),
            is_active=True,
        )
        return user

    def _auth(self, user):
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def _body(self, user):
        self._auth(user)
        response = self.client.get('/api/products/?page_size=50&search=stand')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return str(response.data)

    def test_scope_names(self):
        self.assertFalse(user_may_see_cost(None))
        self.assertFalse(user_may_see_cost(AnonymousUser()))
        self.assertFalse(user_may_see_cost(self.sales))
        self.assertFalse(user_may_see_cost(self.manager))
        self.assertTrue(user_may_see_cost(self.admin))
        self.assertFalse(user_is_management(self.sales))
        self.assertTrue(user_is_management(self.manager))
        self.assertTrue(user_is_management(self.admin))

    def test_sales_and_manager_lists_omit_cost_and_admin_keeps_it(self):
        sales_body = self._body(self.sales)
        self.assertNotIn('77.77', sales_body)
        self.assertNotIn(SUPPLIER_PHONE, sales_body)
        self.assertIn('200.00', sales_body)
        manager_body = self._body(self.manager)
        self.assertNotIn('77.77', manager_body)
        self._auth(self.manager)
        detail = self.client.get(f'/api/products/{self.product.id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK, detail.data)
        self.assertNotIn('cost', detail.data)
        self.assertNotIn('77.77', str(detail.data))
        self.assertEqual(detail.data.get('supplier_contact'), SUPPLIER_PHONE)
        admin_body = self._body(self.admin)
        self.assertIn('77.77', admin_body)

    def test_checked_permission_reveals_cost_to_that_role(self):
        role = Role.objects.create(name='Cost reader', is_active=True, is_system_role=False)
        role.permissions.add(
            Permission.objects.get(module='products', action='view'),
            Permission.objects.get(module='products', action='view_cost'),
        )
        reader = User.objects.create_user('cost_reader', password='pass12345')
        UserProfile.objects.create(
            user=reader, role='cashier', custom_role=role, is_active=True,
        )
        self.assertTrue(user_may_see_cost(reader))
        body = self._body(reader)
        self.assertIn('77.77', body)

    def test_sales_cannot_open_the_cost_on_the_product(self):
        self._auth(self.sales)
        response = self.client.get(f'/api/products/{self.product.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertNotIn('cost', response.data)
        self.assertNotIn('profit_amount', response.data)
        self.assertNotIn('supplier_contact', response.data)
        self.assertNotIn('77.77', str(response.data))
        self.assertNotIn(SUPPLIER_PHONE, str(response.data))
        self.assertEqual(response.data['price'], '200.00')

    def test_anonymous_cannot_list_products(self):
        self.client.credentials()
        response = self.client.get('/api/products/', {'phone': SUPPLIER_PHONE})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn(SUPPLIER_PHONE, str(response.data))
        self.assertNotIn('77.77', str(response.data))

    def test_redact_keeps_delivery_cost_and_drops_unit_cost(self):
        factory = APIRequestFactory()
        request = factory.get('/api/products/')
        request.user = self.sales
        payload = redact_cost_fields(
            {'unit_cost': '77.77', 'delivery_cost': '50.00', 'price': '200.00'},
            request=request,
        )
        self.assertNotIn('unit_cost', payload)
        self.assertEqual(payload['delivery_cost'], '50.00')
        self.assertEqual(payload['price'], '200.00')
        untouched = redact_cost_fields({'unit_cost': '77.77'})
        self.assertEqual(untouched['unit_cost'], '77.77')

    def test_forty_rows_stay_without_cost_for_sales(self):
        self._auth(self.sales)
        response = self.client.get('/api/products/?page_size=50&search=Batch stand')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        rows = response.data.get('results', response.data)
        self.assertGreaterEqual(len(rows), 40)
        self.assertNotIn('77.77', str(response.data))
        self.assertTrue(all(row.get('price') == '10.00' for row in rows[:40]))
