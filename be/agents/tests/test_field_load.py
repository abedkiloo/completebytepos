"""Field loads: stock leaves the shop, sales do not take it twice, returns come back on OK."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    ROLE_FIELD_AGENT,
    ROLE_MANAGER,
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from agents.field_load_service import FieldLoadError, _parse_qty
from products.models import Product
from sales.models import Customer, Sale
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import SuperAdminAPITestCase


def _enable(enabled=True):
    """
    Toggle the sales.field_load feature.

    Args:
        enabled: Desired flag. The sales module stays on.

    Returns:
        None. Writes ModuleSettings and ModuleFeature.
    """
    module, _ = ModuleSettings.objects.get_or_create(
        module_name='sales',
        defaults={'is_enabled': True, 'description': 'sales'},
    )
    module.is_enabled = True
    module.save(update_fields=['is_enabled'])
    feature, _ = ModuleFeature.objects.get_or_create(
        module=module,
        feature_key='field_load',
        defaults={'feature_name': 'Field loads', 'is_enabled': enabled},
    )
    feature.is_enabled = enabled
    feature.save(update_fields=['is_enabled'])


def _product(name, sku, stock):
    """
    Create a tracked product.

    Args:
        name: Product name, 1–200 characters.
        sku: Unique sku.
        stock: Starting on-hand, 0–100000.

    Returns:
        Product.
    """
    return Product.objects.create(
        name=name,
        sku=sku,
        price=Decimal('50.00'),
        cost=Decimal('20.00'),
        stock_quantity=stock,
        track_stock=True,
        is_active=True,
    )


def _approve_creates(test):
    """
    Open loads that this test's admin writes, using a different manager.

    Existing flow tests sell from an open load. Writing a load no longer
    moves stock, so this wrapper approves each successful create.

    Args:
        test: A ``SuperAdminAPITestCase`` whose ``client.post`` writes loads.

    Returns:
        None. Replaces ``test.client.post``.
    """
    approver = User.objects.create_user(
        username=f'load_mgr_{User.objects.count()}',
        password='x',
    )
    UserProfile.objects.create(
        user=approver,
        role='manager',
        custom_role=Role.objects.get(name=ROLE_MANAGER),
        is_active=True,
    )
    approver_client = APIClient()
    approver_client.force_authenticate(user=approver)
    original = test.client.post

    def post(path, data=None, **kwargs):
        response = original(path, data, **kwargs)
        normalized = str(path).split('?')[0].rstrip('/')
        if response.status_code == 201 and normalized.endswith('/field-loads'):
            confirmed = approver_client.post(
                f"/api/agents/field-loads/{response.data['id']}/approve-issue/",
                {},
                format='json',
            )
            if confirmed.status_code == 200:
                response.data = confirmed.data
        return response

    test.client.post = post


class FieldLoadUnitTests(SimpleTestCase):
    """Quantity bounds reject fractions and huge numbers."""

    def test_quantity_bounds(self):
        self.assertEqual(_parse_qty(1, allow_zero=False), 1)
        self.assertEqual(_parse_qty(0, allow_zero=True), 0)
        with self.assertRaises(FieldLoadError):
            _parse_qty(0, allow_zero=False)
        with self.assertRaises(FieldLoadError):
            _parse_qty('1.5', allow_zero=False)
        with self.assertRaises(FieldLoadError):
            _parse_qty(100001, allow_zero=False)

    def test_display_status_marks_a_gap_as_shortage(self):
        from agents.field_load_service import display_status, load_reference, missing_units

        self.assertEqual(display_status('pending_review', 2), 'shortage')
        self.assertEqual(display_status('pending_review', 0), 'pending_review')
        self.assertEqual(display_status('open', 9), 'open')
        self.assertEqual(display_status('awaiting_issue', 0), 'awaiting_issue')
        self.assertEqual(display_status('issue_rejected', 0), 'issue_rejected')
        self.assertEqual(missing_units(40, 5, 35), 0)
        self.assertIsNone(missing_units(40, 5, None))
        label = load_reference(type('Load', (), {'pk': 125, 'issued_at': None})())
        self.assertTrue(label.startswith('FL-'))
        self.assertTrue(label.endswith('-00125'))


class FieldLoadFlowTests(SuperAdminAPITestCase):
    """Issue, sell, return, and accept without double-counting stock."""

    def setUp(self):
        super().setUp()
        _enable(True)
        self.cups = _product('Cups', 'FL-CUPS', 100)
        self.agent = User.objects.create_user(username='load_agent', password='x')
        ensure_permissions()
        sync_default_roles()
        UserProfile.objects.create(
            user=self.agent,
            role='field_agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        self.customer = Customer.objects.create(name='Field Duka', phone='0718111222')
        _approve_creates(self)

    def _issue(self, qty=40):
        return self.client.post(
            '/api/agents/field-loads/',
            {
                'agent_id': self.agent.id,
                'lines': [{'product_id': self.cups.id, 'quantity': qty}],
            },
            format='json',
        )

    def test_stock_drops_on_issue_not_on_sale_and_returns_on_accept(self):
        issued = self._issue(40)
        self.assertEqual(issued.status_code, status.HTTP_201_CREATED, issued.content)
        load_id = issued.data['id']
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 60)

        token = RefreshToken.for_user(self.agent)
        agent_client = APIClient()
        agent_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        sold = agent_client.post(
            f'/api/agents/field-loads/{load_id}/sell/',
            {
                'product_id': self.cups.id,
                'quantity': 15,
                'customer_id': self.customer.id,
                'amount_paid': '750.00',
            },
            format='json',
        )
        self.assertEqual(sold.status_code, status.HTTP_200_OK, sold.content)
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 60)
        self.assertEqual(sold.data['lines'][0]['quantity_sold'], 15)
        self.assertEqual(sold.data['money']['collected'], '0.00')
        self.assertEqual(sold.data['money']['expected'], '750.00')
        from sales.models import Sale
        pending = Sale.objects.get(field_load_sale__load_id=load_id)
        self.assertEqual(pending.status, 'pending_approval')
        self.assertEqual(sold.data['sales'][0]['status'], 'pending_approval')
        approved = self.client.post(f'/api/sales/{pending.id}/complete/', {}, format='json')
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.content)
        pending.refresh_from_db()
        self.assertEqual(pending.status, 'completed')
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 60)

        line_id = sold.data['lines'][0]['id']
        counted = agent_client.post(
            f'/api/agents/field-loads/{load_id}/return/',
            {'lines': [{'line_id': line_id, 'quantity_returned': 20}]},
            format='json',
        )
        self.assertEqual(counted.status_code, status.HTTP_200_OK, counted.content)
        self.assertEqual(counted.data['lines'][0]['quantity_missing'], 5)
        self.assertEqual(counted.data['status'], 'pending_review')

        accepted = self.client.post(
            f'/api/agents/field-loads/{load_id}/accept/',
            {'note': 'Count matches'},
            format='json',
        )
        self.assertEqual(accepted.status_code, status.HTTP_200_OK, accepted.content)
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 80)
        self.assertEqual(accepted.data['status'], 'accepted')

    def test_one_sale_sells_several_products_and_leaves_shop_stock(self):
        legs = _product('Legs', 'FL-LEGS', 30)
        issued = self.client.post(
            '/api/agents/field-loads/',
            {
                'agent_id': self.agent.id,
                'lines': [
                    {'product_id': self.cups.id, 'quantity': 10},
                    {'product_id': legs.id, 'quantity': 4},
                ],
            },
            format='json',
        )
        self.assertEqual(issued.status_code, status.HTTP_201_CREATED, issued.content)
        load_id = issued.data['id']
        token = RefreshToken.for_user(self.agent)
        agent_client = APIClient()
        agent_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        sold = agent_client.post(
            f'/api/agents/field-loads/{load_id}/sell/',
            {
                'lines': [
                    {'product_id': self.cups.id, 'quantity': 2},
                    {'product_id': legs.id, 'quantity': 1},
                ],
                'customer_id': self.customer.id,
                'amount_paid': '100.00',
                'payment_method': 'cash',
            },
            format='json',
        )
        self.assertEqual(sold.status_code, status.HTTP_200_OK, sold.content)
        self.assertNotIn('0718111222', str(sold.data))
        by_name = {row['product_name']: row['quantity_sold'] for row in sold.data['lines']}
        self.assertEqual(by_name['Cups'], 2)
        self.assertEqual(by_name['Legs'], 1)
        self.assertEqual(sold.data['money']['collected'], '0.00')
        self.assertEqual(sold.data['money']['expected'], '150.00')
        sale = Sale.objects.get(field_load_sale__load_id=load_id)
        self.assertEqual(sale.status, 'pending_approval')
        self.assertEqual(sale.items.count(), 2)
        self.assertEqual(sale.total, Decimal('150.00'))
        self.assertEqual(sale.amount_paid, Decimal('100.00'))
        approved = self.client.post(f'/api/sales/{sale.id}/complete/', {}, format='json')
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.content)
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'completed')
        self.cups.refresh_from_db()
        legs.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 90)
        self.assertEqual(legs.stock_quantity, 26)
        too_many = [{'product_id': self.cups.id, 'quantity': 1} for _ in range(41)]
        huge = agent_client.post(
            f'/api/agents/field-loads/{load_id}/sell/',
            {'lines': too_many, 'amount_paid': '50', 'customer_id': self.customer.id},
            format='json',
        )
        self.assertEqual(huge.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('0718111222', str(huge.data))
        self.assertEqual(Sale.objects.filter(field_load_sale__load_id=load_id).count(), 1)
        duplicate = agent_client.post(
            f'/api/agents/field-loads/{load_id}/sell/',
            {
                'lines': [
                    {'product_id': self.cups.id, 'quantity': 1},
                    {'product_id': self.cups.id, 'quantity': 1},
                ],
                'amount_paid': '50',
                'customer_id': self.customer.id,
            },
            format='json',
        )
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        over = agent_client.post(
            f'/api/agents/field-loads/{load_id}/sell/',
            {
                'lines': [
                    {'product_id': self.cups.id, 'quantity': 9},
                    {'product_id': legs.id, 'quantity': 1},
                ],
                'amount_paid': '500',
                'customer_id': self.customer.id,
            },
            format='json',
        )
        self.assertEqual(over.status_code, status.HTTP_400_BAD_REQUEST)
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 90)
        self.assertEqual(Sale.objects.filter(field_load_sale__load_id=load_id).count(), 1)

    def test_corrected_field_agent_sale_waits_for_manager_without_restock(self):
        """Corrected: agent field-load sales wait for manager; shop stock does not move again."""
        issued = self._issue(10)
        self.assertEqual(issued.status_code, status.HTTP_201_CREATED, issued.content)
        load_id = issued.data['id']
        self.cups.refresh_from_db()
        after_issue = self.cups.stock_quantity
        token = RefreshToken.for_user(self.agent)
        agent = APIClient()
        agent.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        sold = agent.post(
            f'/api/agents/field-loads/{load_id}/sell/',
            {
                'product_id': self.cups.id,
                'quantity': 3,
                'customer_id': self.customer.id,
                'amount_paid': '150.00',
                'payment_method': 'cash',
            },
            format='json',
        )
        self.assertEqual(sold.status_code, status.HTTP_200_OK, sold.content)
        sale = Sale.objects.get(field_load_sale__load_id=load_id)
        self.assertEqual(sale.status, 'pending_approval')
        self.assertEqual(sold.data['lines'][0]['quantity_sold'], 3)
        self.assertEqual(sold.data['money']['collected'], '0.00')
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, after_issue)
        approved = self.client.post(f'/api/sales/{sale.id}/complete/', {}, format='json')
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.content)
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'completed')
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, after_issue)
        self.assertNotIn('0718', str(sold.data))

    def test_security_field_agent_cannot_complete_own_field_load_sale(self):
        """Security: field agent cannot self-approve the queued field-load sale."""
        issued = self._issue(5)
        load_id = issued.data['id']
        token = RefreshToken.for_user(self.agent)
        agent = APIClient()
        agent.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        sold = agent.post(
            f'/api/agents/field-loads/{load_id}/sell/',
            {
                'product_id': self.cups.id,
                'quantity': 1,
                'amount_paid': '50.00',
                'payment_method': 'cash',
            },
            format='json',
        )
        self.assertEqual(sold.status_code, status.HTTP_200_OK, sold.content)
        sale = Sale.objects.get(field_load_sale__load_id=load_id)
        self.assertEqual(sale.status, 'pending_approval')
        own = agent.post(f'/api/sales/{sale.id}/complete/', {}, format='json')
        self.assertIn(own.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST))
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'pending_approval')
        self.assertNotIn('0718', own.content.decode())

    def test_send_back_does_not_restock_and_blocks_a_second_load(self):
        issued = self._issue(10)
        load_id = issued.data['id']
        line_id = issued.data['lines'][0]['id']
        self.client.post(
            f'/api/agents/field-loads/{load_id}/return/',
            {'lines': [{'line_id': line_id, 'quantity_returned': 10}]},
            format='json',
        )
        rejected = self.client.post(
            f'/api/agents/field-loads/{load_id}/reject/',
            {'note': 'Count again'},
            format='json',
        )
        self.assertEqual(rejected.status_code, status.HTTP_200_OK)
        self.assertEqual(rejected.data['status'], 'open')
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 90)
        again = self._issue(5)
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already has a load', again.data['error'])

    def test_cannot_sell_more_than_was_taken(self):
        issued = self._issue(4)
        response = self.client.post(
            f"/api/agents/field-loads/{issued.data['id']}/sell/",
            {
                'product_id': self.cups.id,
                'quantity': 5,
                'customer_id': self.customer.id,
                'amount_paid': '0',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(self.customer.phone, response.content.decode())
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 96)

    def test_twenty_sales_leave_the_remainder(self):
        issued = self._issue(25)
        load_id = issued.data['id']
        for _ in range(20):
            response = self.client.post(
                f'/api/agents/field-loads/{load_id}/sell/',
                {
                    'product_id': self.cups.id,
                    'quantity': 1,
                    'customer_id': self.customer.id,
                    'amount_paid': '50.00',
                },
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data['lines'][0]['quantity_sold'], 20)
        self.assertEqual(response.data['lines'][0]['still_out'], 5)
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 75)

    def test_three_loads_are_read_together(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from agents.field_load_service import serialize_loads
        from agents.models import FieldLoad

        ids = []
        for index in range(3):
            agent = User.objects.create_user(username=f'batch_agent_{index}', password='x')
            issued = self.client.post(
                '/api/agents/field-loads/',
                {
                    'agent_id': agent.id,
                    'lines': [{'product_id': self.cups.id, 'quantity': 1}],
                },
                format='json',
            )
            self.assertEqual(issued.status_code, status.HTTP_201_CREATED, issued.content)
            ids.append(issued.data['id'])
        loads = list(
            FieldLoad.objects.filter(id__in=ids).select_related(
                'agent', 'issued_by', 'reviewed_by', 'issue_approved_by',
            )
        )
        with CaptureQueriesContext(connection) as captured:
            rows = serialize_loads(loads)
        self.assertEqual(serialize_loads([]), [])
        self.assertEqual(len(rows), 3)
        self.assertLessEqual(len(captured), 4)
        self.assertNotIn(self.customer.phone, str(rows))


class FieldLoadModuleTests(SuperAdminAPITestCase):
    """The package toggle closes the API."""

    def test_feature_off_is_forbidden(self):
        _enable(False)
        response = self.client.get('/api/agents/field-loads/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('phone', response.content.decode().lower())
        _enable(True)
        opened = self.client.get('/api/agents/field-loads/')
        self.assertEqual(opened.status_code, status.HTTP_200_OK)

    def test_revise_is_forbidden_while_the_feature_is_off(self):
        _enable(False)
        response = self.client.post(
            '/api/agents/field-loads/1/revise-issue/',
            {'lines': [{'product_id': 1, 'quantity': 1}]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('0718123456', response.content.decode())
        _enable(True)


class FieldLoadSecurityTests(SuperAdminAPITestCase):
    """Anonymous denied, agents see only their load, sales cannot accept."""

    def setUp(self):
        super().setUp()
        _enable(True)
        ensure_permissions()
        sync_default_roles()
        self.cups = _product('Locked Cups', 'FL-LOCK', 30)
        self.agent = User.objects.create_user(username='load_agent_sec', password='x')
        self.other = User.objects.create_user(username='load_agent_other', password='x')
        role = Role.objects.get(name=ROLE_FIELD_AGENT)
        for user in (self.agent, self.other):
            UserProfile.objects.create(
                user=user,
                role='field_agent',
                custom_role=role,
                is_active=True,
            )
        self.sales = User.objects.create_user(username='load_sales', password='x')
        UserProfile.objects.create(
            user=self.sales,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        _approve_creates(self)

    def _client(self, user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
        return client

    def test_anonymous_is_denied(self):
        response = APIClient().get('/api/agents/field-loads/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_agent_cannot_issue_or_see_another_load(self):
        issued = self.client.post(
            '/api/agents/field-loads/',
            {
                'agent_id': self.agent.id,
                'lines': [{'product_id': self.cups.id, 'quantity': 3}],
            },
            format='json',
        )
        self.assertEqual(issued.status_code, status.HTTP_201_CREATED, issued.content)
        agent = self._client(self.agent)
        denied = agent.post(
            '/api/agents/field-loads/',
            {
                'agent_id': self.other.id,
                'lines': [{'product_id': self.cups.id, 'quantity': 1}],
            },
            format='json',
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('Locked Cups', denied.content.decode())
        other = self._client(self.other)
        hidden = other.get(f"/api/agents/field-loads/{issued.data['id']}/")
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn('Locked Cups', hidden.content.decode())

    def test_sales_can_issue_and_cannot_accept(self):
        sales = self._client(self.sales)
        issued = sales.post(
            '/api/agents/field-loads/',
            {
                'agent_id': self.sales.id,
                'lines': [{'product_id': self.cups.id, 'quantity': 2}],
            },
            format='json',
        )
        self.assertEqual(issued.status_code, status.HTTP_201_CREATED, issued.content)
        self.assertEqual(issued.data['status'], 'awaiting_issue')
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 30)
        line_id = issued.data['lines'][0]['id']
        sales.post(
            f"/api/agents/field-loads/{issued.data['id']}/return/",
            {'lines': [{'line_id': line_id, 'quantity_returned': 2}]},
            format='json',
        )
        accepted = sales.post(f"/api/agents/field-loads/{issued.data['id']}/accept/", {}, format='json')
        self.assertEqual(accepted.status_code, status.HTTP_403_FORBIDDEN)
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 30)
        self.assertNotIn(self.cups.sku, accepted.content.decode())

    def test_another_agent_cannot_sell_this_load(self):
        issued = self.client.post(
            '/api/agents/field-loads/',
            {
                'agent_id': self.agent.id,
                'lines': [{'product_id': self.cups.id, 'quantity': 2}],
            },
            format='json',
        )
        other = self._client(self.other)
        response = other.post(
            f"/api/agents/field-loads/{issued.data['id']}/sell/",
            {
                'product_id': self.cups.id,
                'quantity': 1,
                'amount_paid': '50.00',
                'payment_method': 'cash',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn('0718', response.content.decode())

    def test_the_agent_list_is_sales_employees_from_the_roster(self):
        from datetime import date

        from employees.models import Employee

        seller = User.objects.create_user(username='sales_emp_load', password='x')
        Employee.objects.create(
            user=seller,
            employee_id='EMP-SALE-1',
            first_name='Amina',
            last_name='Seller',
            phone='0718999001',
            position='Sales',
            department='sales',
            hire_date=date(2026, 1, 1),
            status='active',
        )
        Employee.objects.create(
            user=User.objects.create_user(username='prod_emp_load', password='x'),
            employee_id='EMP-PROD-1',
            first_name='Petro',
            last_name='Maker',
            phone='0718999002',
            position='Maker',
            department='production',
            hire_date=date(2026, 1, 1),
            status='active',
        )
        Employee.objects.create(
            user=User.objects.create_user(username='gone_emp_load', password='x'),
            employee_id='EMP-GONE-1',
            first_name='Gone',
            last_name='Seller',
            position='Sales',
            department='sales',
            hire_date=date(2026, 1, 1),
            status='inactive',
        )
        response = self.client.get('/api/agents/field-loads/agents/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()['results']
        self.assertEqual(rows[0]['id'], self.admin.id)
        self.assertIn({'id': seller.id, 'name': 'Amina Seller'}, rows)
        self.assertNotIn('Petro Maker', [row['name'] for row in rows])
        self.assertNotIn('Gone Seller', [row['name'] for row in rows])
        body = response.content.decode()
        self.assertNotIn('0718999001', body)
        self.assertNotIn('0718999002', body)


class FieldLoadCorrectedTests(SuperAdminAPITestCase):
    """A field-load sale stays distinct from a packed field order."""

    def setUp(self):
        super().setUp()
        _enable(True)
        self.cups = _product('Origin Cups', 'FL-ORIGIN', 100)
        self.agent = User.objects.create_user(username='load_origin', password='x')
        ensure_permissions()
        sync_default_roles()
        UserProfile.objects.create(
            user=self.agent,
            role='field_agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        self.customer = Customer.objects.create(name='Origin Duka', phone='0718000111')
        _approve_creates(self)

    def test_load_sale_is_not_a_field_order_and_missing_uses_the_formula(self):
        from sales.models import Sale

        issued = self.client.post(
            '/api/agents/field-loads/',
            {
                'agent_id': self.agent.id,
                'lines': [{'product_id': self.cups.id, 'quantity': 40}],
            },
            format='json',
        )
        self.assertEqual(issued.status_code, status.HTTP_201_CREATED, issued.content)
        self.assertTrue(issued.data['reference'].startswith('FL-'))
        sold = self.client.post(
            f"/api/agents/field-loads/{issued.data['id']}/sell/",
            {
                'product_id': self.cups.id,
                'quantity': 10,
                'customer_id': self.customer.id,
                'amount_paid': '200.00',
                'payment_method': 'cash',
            },
            format='json',
        )
        self.assertEqual(sold.status_code, status.HTTP_200_OK, sold.content)
        sale = Sale.objects.get(field_load_sale__load_id=issued.data['id'])
        self.assertEqual(sale.entry_source, 'field_load')
        self.assertFalse(sale.is_field_sale)
        self.assertTrue(sale.is_field_load_sale)
        self.assertEqual(sale.sale_origin, 'field_load')
        self.assertEqual(sale.payment_method, 'cash')
        self.assertEqual(sold.data['money']['cash'], '200.00')
        self.assertEqual(sold.data['money']['credit'], '300.00')
        self.assertEqual(Sale.objects.filter(entry_source='field').count(), 0)
        line_id = sold.data['lines'][0]['id']
        counted = self.client.post(
            f"/api/agents/field-loads/{issued.data['id']}/return/",
            {'lines': [{'line_id': line_id, 'quantity_returned': 28}]},
            format='json',
        )
        self.assertEqual(counted.data['lines'][0]['quantity_missing'], 2)
        self.assertEqual(counted.data['display_status'], 'shortage')
        self.assertNotIn(self.customer.phone, counted.content.decode())

    def test_bad_payment_does_not_echo_a_phone(self):
        issued = self.client.post(
            '/api/agents/field-loads/',
            {
                'agent_id': self.agent.id,
                'lines': [{'product_id': self.cups.id, 'quantity': 4}],
            },
            format='json',
        )
        response = self.client.post(
            f"/api/agents/field-loads/{issued.data['id']}/sell/",
            {
                'product_id': self.cups.id,
                'quantity': 1,
                'customer_id': self.customer.id,
                'amount_paid': '10.00',
                'payment_method': 'mpesa',
                'notes': self.customer.phone,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(self.customer.phone, response.content.decode())
        self.assertFalse(response.data['error'].__contains__(self.customer.phone))

    def test_a_split_payment_is_rejected_without_echoing_the_phone(self):
        issued = self.client.post(
            '/api/agents/field-loads/',
            {
                'agent_id': self.agent.id,
                'lines': [{'product_id': self.cups.id, 'quantity': 4}],
            },
            format='json',
        )
        response = self.client.post(
            f"/api/agents/field-loads/{issued.data['id']}/sell/",
            {
                'product_id': self.cups.id,
                'quantity': 1,
                'customer_id': self.customer.id,
                'amount_paid': '10.00',
                'payment_method': 'split',
                'notes': self.customer.phone,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(self.customer.phone, response.content.decode())


class FieldLoadStressTests(SimpleTestCase):
    """The reconciliation formula stays stable across a few hundred lines."""

    def test_three_hundred_lines_use_taken_minus_sold_minus_returned(self):
        from agents.field_load_service import missing_units

        for index in range(300):
            self.assertEqual(missing_units(40 + index, 5, 8), 27 + index)
            self.assertIsNone(missing_units(10, 1, None))


class FieldLoadCoverageTests(SuperAdminAPITestCase):
    """Error branches, payment choices, and the operations summary."""

    def setUp(self):
        super().setUp()
        _enable(True)
        ensure_permissions()
        sync_default_roles()
        self.cups = _product('Cover Cups', 'FL-COVER', 30)
        self.agent = User.objects.create_user(username='load_cover', password='x', first_name='Asha')
        UserProfile.objects.create(
            user=self.agent,
            role='field_agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        self.customer = Customer.objects.create(name='Cover Duka', phone='0718999000')
        _approve_creates(self)

    def _issue(self, qty=10, agent=None, lines=None):
        return self.client.post(
            '/api/agents/field-loads/',
            {
                'agent_id': (agent or self.agent).id,
                'lines': lines or [{'product_id': self.cups.id, 'quantity': qty}],
            },
            format='json',
        )

    def test_helpers_and_rejected_inputs(self):
        from decimal import Decimal
        from django.core.exceptions import ValidationError
        from unittest.mock import patch

        from agents.field_load_service import (
            _can_touch,
            _display_name,
            _resolve_tender,
            user_may_approve,
            user_may_issue,
        )
        from agents.models import FieldLoad

        self.assertFalse(user_may_issue(None))
        self.assertFalse(user_may_approve(None))
        self.assertEqual(_display_name(None), '')
        stranger = User.objects.create_user(username='load_no_profile', password='x')
        self.assertFalse(user_may_issue(stranger))
        self.assertFalse(user_may_approve(stranger))
        self.assertFalse(_can_touch(FieldLoad(agent=self.agent), None))
        self.assertTrue(_display_name(self.agent).startswith('Asha'))

        with self.assertRaises(FieldLoadError):
            _resolve_tender(payment_method='card', paid=Decimal('1'), total=Decimal('1'), has_customer=True, tender='cash')
        with self.assertRaises(FieldLoadError):
            _resolve_tender(payment_method='credit', paid=Decimal('1'), total=Decimal('1'), has_customer=True, tender='cash')
        with self.assertRaises(FieldLoadError):
            _resolve_tender(payment_method='credit', paid=Decimal('0'), total=Decimal('1'), has_customer=False, tender='cash')
        self.assertEqual(
            _resolve_tender(payment_method='credit', paid=Decimal('0'), total=Decimal('1'), has_customer=True, tender='cash')[0],
            'on_account',
        )
        self.assertEqual(
            _resolve_tender(payment_method='debt', paid=Decimal('0'), total=Decimal('1'), has_customer=True, tender='cash')[0],
            'on_account',
        )
        self.assertEqual(
            _resolve_tender(payment_method='on_account', paid=Decimal('0'), total=Decimal('1'), has_customer=True, tender='cash')[0],
            'on_account',
        )
        with self.assertRaises(FieldLoadError):
            _resolve_tender(payment_method='debt', paid=Decimal('0'), total=Decimal('1'), has_customer=False, tender='cash')
        with self.assertRaises(FieldLoadError):
            _resolve_tender(payment_method='split', paid=Decimal('1'), total=Decimal('5'), has_customer=False, tender='cash')
        with self.assertRaises(FieldLoadError):
            _resolve_tender(payment_method='split', paid=Decimal('0'), total=Decimal('5'), has_customer=True, tender='cash')
        with self.assertRaises(FieldLoadError):
            _resolve_tender(payment_method='split', paid=Decimal('1'), total=Decimal('5'), has_customer=True, tender='card')
        with self.assertRaises(FieldLoadError):
            _resolve_tender(payment_method='split', paid=Decimal('1'), total=Decimal('5'), has_customer=True, tender='cash')
        with self.assertRaises(FieldLoadError):
            _resolve_tender(payment_method='cash', paid=Decimal('9'), total=Decimal('5'), has_customer=True, tender='cash')
        with self.assertRaises(FieldLoadError):
            _resolve_tender(payment_method='cash', paid=Decimal('1'), total=Decimal('5'), has_customer=False, tender='cash')
        with self.assertRaises(FieldLoadError):
            _resolve_tender(payment_method='cash', paid=Decimal('0'), total=Decimal('5'), has_customer=False, tender='cash')
        self.assertEqual(
            _resolve_tender(payment_method='cash', paid=Decimal('0'), total=Decimal('5'), has_customer=True, tender='cash')[0],
            'on_account',
        )

        self.assertEqual(self.client.get('/api/agents/field-loads/agents/').status_code, status.HTTP_200_OK)
        agent = APIClient()
        agent.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.agent).access_token}')
        own_roster = agent.get('/api/agents/field-loads/agents/')
        self.assertEqual(own_roster.status_code, status.HTTP_200_OK)
        self.assertFalse(own_roster.data.get('choose_employee'))
        self.assertEqual(own_roster.data['results'][0]['id'], self.agent.id)
        self.assertNotIn(self.customer.phone, own_roster.content.decode())

        inactive = User.objects.create_user(username='load_inactive', password='x', is_active=False)
        self.assertEqual(self._issue(agent=inactive).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.post('/api/agents/field-loads/', {'agent_id': self.agent.id, 'lines': []}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/agents/field-loads/', {'agent_id': self.agent.id, 'lines': ['nope']}, format='json').status_code, 400)
        duplicate = self.client.post(
            '/api/agents/field-loads/',
            {'agent_id': self.agent.id, 'lines': [
                {'product_id': self.cups.id, 'quantity': 1},
                {'product_id': self.cups.id, 'quantity': 1},
            ]},
            format='json',
        )
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            self.client.post('/api/agents/field-loads/', {'agent_id': 999999, 'lines': [{'product_id': self.cups.id, 'quantity': 1}]}, format='json').status_code,
            400,
        )
        missing_product = self.client.post(
            '/api/agents/field-loads/',
            {'agent_id': self.agent.id, 'lines': [{'product_id': 999999, 'quantity': 1}]},
            format='json',
        )
        self.assertEqual(missing_product.status_code, 400)
        plain = _product('Untracked', 'FL-UNTRACK', 5)
        plain.track_stock = False
        plain.save(update_fields=['track_stock'])
        self.assertEqual(
            self.client.post('/api/agents/field-loads/', {'agent_id': self.agent.id, 'lines': [{'product_id': plain.id, 'quantity': 1}]}, format='json').status_code,
            400,
        )
        from products.models import ProductVariant
        ProductVariant.objects.create(product=self.cups, sku='FL-COVER-V')
        self.assertEqual(self._issue().status_code, 400)
        self.assertEqual(
            self.client.post(
                '/api/agents/field-loads/',
                {'agent_id': self.agent.id, 'lines': [{'product_id': self.cups.id, 'variant_id': 999999, 'quantity': 1}]},
                format='json',
            ).status_code,
            400,
        )
        ProductVariant.objects.filter(product=self.cups).delete()
        from inventory.services import StockMovementService
        with patch.object(StockMovementService, 'adjust_stock', side_effect=ValidationError('closed for count')):
            blocked_stock = self.client.post(
                '/api/agents/field-loads/',
                {'agent_id': self.agent.id, 'lines': [{'product_id': self.cups.id, 'quantity': 1}]},
                format='json',
            )
        self.assertEqual(blocked_stock.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(self.customer.phone, blocked_stock.content.decode())
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 30)

        short = _product('Short', 'FL-SHORT', 1)
        self.assertEqual(
            self.client.post('/api/agents/field-loads/', {'agent_id': self.agent.id, 'lines': [{'product_id': short.id, 'quantity': 5}]}, format='json').status_code,
            400,
        )

        issued = self._issue(4)
        self.assertEqual(issued.status_code, status.HTTP_201_CREATED, issued.content)
        load_id = issued.data['id']
        added = self.client.post(
            f'/api/agents/field-loads/{load_id}/lines/',
            {'product_id': self.cups.id, 'quantity': 1},
            format='json',
        )
        self.assertEqual(added.status_code, status.HTTP_200_OK, added.content)
        self.assertEqual(
            self.client.post(f'/api/agents/field-loads/999999/lines/', {'product_id': self.cups.id, 'quantity': 1}, format='json').status_code,
            404,
        )
        self.assertEqual(agent.post(f'/api/agents/field-loads/{load_id}/lines/', {'product_id': self.cups.id, 'quantity': 1}, format='json').status_code, 403)

        walk_in = self.client.post(
            f'/api/agents/field-loads/{load_id}/sell/',
            {'product_id': self.cups.id, 'quantity': 1, 'amount_paid': '50.00', 'payment_method': 'cash', 'client_channel': 'tablet'},
            format='json',
        )
        self.assertEqual(walk_in.status_code, status.HTTP_200_OK, walk_in.content)
        from sales.models import Sale
        self.assertEqual(Sale.objects.get(field_load_sale__load_id=load_id).client_channel, 'web')

        credit = self.client.post(
            f'/api/agents/field-loads/{load_id}/sell/',
            {'product_id': self.cups.id, 'quantity': 1, 'customer_id': self.customer.id, 'amount_paid': '0', 'payment_method': 'credit'},
            format='json',
        )
        self.assertEqual(credit.status_code, status.HTTP_200_OK, credit.content)
        self.assertEqual(credit.data['money']['credit'], '50.00')

        from products.models import Product
        Product.objects.filter(pk=self.cups.id).update(price=Decimal('-5'))
        negative = self.client.get(f'/api/agents/field-loads/{load_id}/')
        self.assertEqual(negative.data['lines'][0]['unit_price'], '0.00')
        self.client.post(
            f'/api/agents/field-loads/{load_id}/sell/',
            {'product_id': self.cups.id, 'quantity': 1, 'amount_paid': '0'},
            format='json',
        )
        Product.objects.filter(pk=self.cups.id).update(price=Decimal('50'))
        self.assertEqual(
            self.client.post(
                f'/api/agents/field-loads/{load_id}/sell/',
                {'product_id': self.cups.id, 'quantity': 1, 'amount_paid': '80'},
                format='json',
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                f'/api/agents/field-loads/{load_id}/sell/',
                {'product_id': self.cups.id, 'quantity': 1, 'customer_id': 999999, 'amount_paid': '50'},
                format='json',
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                f'/api/agents/field-loads/{load_id}/sell/',
                {'product_id': self.cups.id, 'quantity': 1, 'amount_paid': '10'},
                format='json',
            ).status_code,
            400,
        )
        Sale.objects.filter(field_load_sale__load_id=load_id).update(amount_paid=Decimal('80.00'))
        over = self.client.get(f'/api/agents/field-loads/{load_id}/')
        self.assertEqual(over.status_code, status.HTTP_200_OK)

        self.assertEqual(
            self.client.post(f'/api/agents/field-loads/{load_id}/sell/', {'product_id': self.cups.id, 'quantity': 1, 'amount_paid': 'nope'}, format='json').status_code,
            400,
        )
        self.assertEqual(
            self.client.post(f'/api/agents/field-loads/{load_id}/sell/', {'product_id': self.cups.id, 'quantity': 1, 'amount_paid': '-1'}, format='json').status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                f'/api/agents/field-loads/{load_id}/sell/',
                {'product_id': self.cups.id, 'quantity': 1, 'amount_paid': '50', 'notes': 'n' * 501},
                format='json',
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(f'/api/agents/field-loads/{load_id}/sell/', {'product_id': 999999, 'quantity': 1, 'amount_paid': '50'}, format='json').status_code,
            400,
        )
        with patch('sales.services.SaleService.create_sale', side_effect=ValidationError('stock blocked')):
            blocked = self.client.post(
                f'/api/agents/field-loads/{load_id}/sell/',
                {'product_id': self.cups.id, 'quantity': 1, 'amount_paid': '50'},
                format='json',
            )
        self.assertEqual(blocked.status_code, 400)
        self.assertNotIn(self.customer.phone, blocked.content.decode())
        with patch('accounting.services.create_sale_journal_entry', side_effect=RuntimeError('journal down')):
            journal = self.client.post(
                f'/api/agents/field-loads/{load_id}/sell/',
                {'product_id': self.cups.id, 'quantity': 1, 'amount_paid': '50', 'payment_method': 'mpesa'},
                format='json',
            )
        self.assertEqual(journal.status_code, status.HTTP_200_OK, journal.content)

        line_id = issued.data['lines'][0]['id']
        self.assertEqual(self.client.post(f'/api/agents/field-loads/{load_id}/return/', {'lines': []}, format='json').status_code, 400)
        self.assertEqual(
            self.client.post(
                f'/api/agents/field-loads/999999/return/',
                {'lines': [{'line_id': line_id, 'quantity_returned': 0}]},
                format='json',
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f'/api/agents/field-loads/{load_id}/return/',
                {'lines': [
                    {'line_id': line_id, 'quantity_returned': 0},
                    {'line_id': line_id, 'quantity_returned': 0},
                ]},
                format='json',
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(f'/api/agents/field-loads/{load_id}/return/', {'lines': ['nope']}, format='json').status_code,
            400,
        )
        self.assertEqual(
            self.client.post(f'/api/agents/field-loads/{load_id}/return/', {'lines': [{'line_id': 'nope', 'quantity_returned': 0}]}, format='json').status_code,
            400,
        )
        self.assertEqual(
            self.client.post(f'/api/agents/field-loads/{load_id}/return/', {'lines': [{'line_id': 999999, 'quantity_returned': 0}]}, format='json').status_code,
            400,
        )
        self.assertEqual(
            self.client.post(f'/api/agents/field-loads/{load_id}/return/', {'lines': [{'line_id': line_id, 'quantity_returned': 100}]}, format='json').status_code,
            400,
        )
        counted = self.client.post(
            f'/api/agents/field-loads/{load_id}/return/',
            {'lines': [{'line_id': line_id, 'quantity_returned': 0}]},
            format='json',
        )
        self.assertEqual(counted.status_code, status.HTTP_200_OK, counted.content)
        self.assertEqual(
            self.client.post(
                f'/api/agents/field-loads/{load_id}/return/',
                {'lines': [{'line_id': line_id, 'quantity_returned': 0}]},
                format='json',
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(f'/api/agents/field-loads/{load_id}/sell/', {'product_id': self.cups.id, 'quantity': 1, 'amount_paid': '50'}, format='json').status_code,
            400,
        )
        self.assertEqual(
            self.client.post(f'/api/agents/field-loads/{load_id}/lines/', {'product_id': self.cups.id, 'quantity': 1}, format='json').status_code,
            400,
        )
        self.assertEqual(self.client.post('/api/agents/field-loads/999999/accept/', {}, format='json').status_code, 404)
        self.assertEqual(
            self.client.post(f'/api/agents/field-loads/{load_id}/accept/', {'note': 'n' * 501}, format='json').status_code,
            400,
        )
        self.client.post(f'/api/agents/field-loads/{load_id}/reject/', {}, format='json')
        self.assertEqual(self.client.post(f'/api/agents/field-loads/{load_id}/reject/', {}, format='json').status_code, 400)

        huge = self._issue(1, agent=User.objects.create_user(username='load_huge', password='x'))
        # The second agent has no field role; issuing does not require the carrier to have the role.
        if huge.status_code != 201:
            carrier = User.objects.create_user(username='load_huge2', password='x')
            UserProfile.objects.create(
                user=carrier,
                role='field_agent',
                custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
                is_active=True,
            )
            huge = self._issue(1, agent=carrier)
        self.assertEqual(huge.status_code, status.HTTP_201_CREATED, huge.content)
        extra = _product('Added', 'FL-ADDED', 5)
        self.assertEqual(
            self.client.post(
                f"/api/agents/field-loads/{huge.data['id']}/lines/",
                {'product_id': extra.id, 'quantity': 1},
                format='json',
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.post(
                f"/api/agents/field-loads/{huge.data['id']}/lines/",
                {'product_id': self.cups.id, 'quantity': 100000},
                format='json',
            ).status_code,
            400,
        )

        many = []
        carrier = User.objects.create_user(username='load_many', password='x')
        UserProfile.objects.create(
            user=carrier,
            role='field_agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        for index in range(40):
            product = _product(f'Line {index}', f'FL-MANY-{index}', 1)
            many.append({'product_id': product.id, 'quantity': 1})
        packed = self._issue(agent=carrier, lines=many)
        self.assertEqual(packed.status_code, status.HTTP_201_CREATED, packed.content)
        extra = _product('Line extra', 'FL-MANY-X', 1)
        self.assertEqual(
            self.client.post(
                f"/api/agents/field-loads/{packed.data['id']}/lines/",
                {'product_id': extra.id, 'quantity': 1},
                format='json',
            ).status_code,
            400,
        )
        book = self.client.get('/api/agents/field-loads/')
        self.assertGreaterEqual(book.data['summary']['active'], 1)

    def test_summary_counts_each_display_status(self):
        second = User.objects.create_user(username='load_cover_b', password='x')
        UserProfile.objects.create(
            user=second,
            role='field_agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        third = User.objects.create_user(username='load_cover_c', password='x')
        UserProfile.objects.create(
            user=third,
            role='field_agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        open_load = self._issue(2)
        balanced = self._issue(2, agent=second)
        short = self._issue(2, agent=third)
        self.client.post(
            f"/api/agents/field-loads/{balanced.data['id']}/return/",
            {'lines': [{'line_id': balanced.data['lines'][0]['id'], 'quantity_returned': 2}]},
            format='json',
        )
        self.client.post(
            f"/api/agents/field-loads/{short.data['id']}/return/",
            {'lines': [{'line_id': short.data['lines'][0]['id'], 'quantity_returned': 0}]},
            format='json',
        )
        waiting = self.client.get('/api/agents/field-loads/')
        self.assertGreaterEqual(waiting.data['summary']['awaiting_approval'], 1)
        self.client.post(f"/api/agents/field-loads/{balanced.data['id']}/accept/", {}, format='json')
        book = self.client.get('/api/agents/field-loads/')
        self.assertGreaterEqual(book.data['summary']['active'], 1)
        self.assertGreaterEqual(book.data['summary']['accepted'], 1)
        self.assertGreaterEqual(book.data['summary']['shortage'], 1)
        self.assertIn(open_load.data['id'], [row['id'] for row in book.data['results']])


class FieldLoadMakerCheckerTests(SuperAdminAPITestCase):
    """A sales person writes the quantities. A different manager approves them."""

    def setUp(self):
        super().setUp()
        _enable(True)
        ensure_permissions()
        sync_default_roles()
        self.cups = _product('Check Cups', 'FL-CHECK', 50)
        self.agent = User.objects.create_user(username='load_check_agent', password='x')
        UserProfile.objects.create(
            user=self.agent,
            role='field_agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        self.sales = User.objects.create_user(username='load_check_sales', password='x')
        UserProfile.objects.create(
            user=self.sales,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )

    def _write(self, client, qty=10, agent_id=None):
        """
        Write a load as ``client``.

        A sales client writes for themselves. The admin client writes for
        the field agent unless ``agent_id`` is set.

        Args:
            client: DRF client.
            qty: Units, 1–100000.
            agent_id: Carrier login id, or None for the default above.

        Returns:
            Response.
        """
        if agent_id is None:
            agent_id = self.agent.id if client is self.client else self.sales.id
        return client.post(
            '/api/agents/field-loads/',
            {
                'agent_id': agent_id,
                'lines': [{'product_id': self.cups.id, 'quantity': qty}],
            },
            format='json',
        )

    def test_field_sales_agent_writes_load_for_manager_approval(self):
        """Corrected: Field Sales create a load; stock waits for a manager."""
        agent = APIClient()
        agent.force_authenticate(user=self.agent)
        written = self._write(agent, qty=5, agent_id=self.agent.id)
        self.assertEqual(written.status_code, status.HTTP_201_CREATED, written.content)
        self.assertEqual(written.data['status'], 'awaiting_issue')
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 50)
        for_other = agent.post(
            '/api/agents/field-loads/',
            {
                'agent_id': self.sales.id,
                'lines': [{'product_id': self.cups.id, 'quantity': 1}],
            },
            format='json',
        )
        self.assertEqual(for_other.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(self.cups.sku, for_other.content.decode())
        self.assertNotIn('0718', for_other.content.decode())
        approved = self.client.post(
            f"/api/agents/field-loads/{written.data['id']}/approve-issue/",
            {},
            format='json',
        )
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.content)
        self.assertEqual(approved.data['status'], 'open')
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 45)

    def test_stock_stays_until_a_different_manager_approves(self):
        sales = APIClient()
        sales.force_authenticate(user=self.sales)
        written = self._write(sales)
        self.assertEqual(written.status_code, status.HTTP_201_CREATED, written.content)
        self.assertEqual(written.data['status'], 'awaiting_issue')
        self.assertFalse(written.data['can_confirm_issue'])
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 50)
        own = sales.post(
            f"/api/agents/field-loads/{written.data['id']}/approve-issue/",
            {},
            format='json',
        )
        self.assertEqual(own.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('0718123456', own.content.decode())
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 50)
        approved = self.client.post(
            f"/api/agents/field-loads/{written.data['id']}/approve-issue/",
            {},
            format='json',
        )
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.content)
        self.assertEqual(approved.data['status'], 'open')
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 40)

    def test_a_manager_issues_for_themselves_or_someone_else_without_approval(self):
        from agents.models import FieldLoad

        roster = self.client.get('/api/agents/field-loads/agents/')
        self.assertEqual(roster.status_code, status.HTTP_200_OK)
        self.assertTrue(roster.data['choose_employee'])
        self.assertEqual(roster.data['results'][0]['id'], self.admin.id)
        self.assertNotIn('0718123456', roster.content.decode())

        sales = APIClient()
        sales.force_authenticate(user=self.sales)
        waiting = self._write(sales, qty=2)
        self.assertEqual(waiting.status_code, status.HTTP_201_CREATED, waiting.content)
        self.assertEqual(waiting.data['status'], 'awaiting_issue')
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 50)

        own = self._write(self.client, qty=3, agent_id=self.admin.id)
        self.assertEqual(own.status_code, status.HTTP_201_CREATED, own.content)
        self.assertEqual(own.data['status'], 'open')
        self.assertEqual(own.data['agent_id'], self.admin.id)
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 47)
        again = self.client.post(
            f"/api/agents/field-loads/{own.data['id']}/approve-issue/",
            {},
            format='json',
        )
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 47)

        other = self._write(self.client, qty=4, agent_id=self.agent.id)
        self.assertEqual(other.status_code, status.HTTP_201_CREATED, other.content)
        self.assertEqual(other.data['status'], 'open')
        self.assertEqual(other.data['agent_id'], self.agent.id)
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 43)

        anonymous = APIClient().post(
            '/api/agents/field-loads/',
            {
                'agent_id': self.admin.id,
                'lines': [{'product_id': self.cups.id, 'quantity': 1}],
            },
            format='json',
        )
        self.assertEqual(anonymous.status_code, status.HTTP_401_UNAUTHORIZED)

        _enable(False)
        hidden = self._write(self.client, qty=1, agent_id=self.admin.id)
        self.assertEqual(hidden.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('0718123456', hidden.content.decode())
        _enable(True)
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 43)
        self.assertEqual(
            FieldLoad.objects.filter(agent=self.admin, status='open').count(),
            1,
        )

        carrier = User.objects.create_user(username='load_mgr_wide', password='x')
        products = [
            _product(f'Stress cup {index}', f'FL-MGR-{index}', 2)
            for index in range(40)
        ]
        wide = self.client.post(
            '/api/agents/field-loads/',
            {
                'agent_id': carrier.id,
                'lines': [
                    {'product_id': product.id, 'quantity': 1}
                    for product in products
                ],
            },
            format='json',
        )
        self.assertEqual(wide.status_code, status.HTTP_201_CREATED, wide.content)
        self.assertEqual(wide.data['status'], 'open')
        self.assertEqual(len(wide.data['lines']), 40)
        for product in products:
            product.refresh_from_db()
            self.assertEqual(product.stock_quantity, 1)
        spare = User.objects.create_user(username='load_mgr_spare', password='x')
        too_many = self.client.post(
            '/api/agents/field-loads/',
            {
                'agent_id': spare.id,
                'lines': [{'product_id': self.cups.id, 'quantity': 1}] * 41,
            },
            format='json',
        )
        self.assertEqual(too_many.status_code, status.HTTP_400_BAD_REQUEST)
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 43)
        self.assertFalse(FieldLoad.objects.filter(agent=spare).exists())

    def test_sending_the_quantities_back_does_not_move_stock(self):
        sales = APIClient()
        sales.force_authenticate(user=self.sales)
        written = self._write(sales, qty=6)
        declined = self.client.post(
            f"/api/agents/field-loads/{written.data['id']}/decline-issue/",
            {'note': 'Check the quantities'},
            format='json',
        )
        self.assertEqual(declined.status_code, status.HTTP_200_OK, declined.content)
        self.assertEqual(declined.data['status'], 'issue_rejected')
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 50)
        again = self._write(sales, qty=3)
        self.assertEqual(again.status_code, status.HTTP_201_CREATED, again.content)

    def test_a_blocked_approval_does_not_move_stock_or_echo_a_phone(self):
        from unittest.mock import patch

        from django.core.exceptions import ValidationError
        from inventory.services import StockMovementService

        sales = APIClient()
        sales.force_authenticate(user=self.sales)
        written = self._write(sales, qty=2)
        with patch.object(StockMovementService, 'adjust_stock', side_effect=ValidationError('closed for count')):
            blocked = self.client.post(
                f"/api/agents/field-loads/{written.data['id']}/approve-issue/",
                {},
                format='json',
            )
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('0718123456', blocked.content.decode())
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 50)

    def test_a_sales_person_cannot_write_a_load_for_someone_else(self):
        from agents.models import FieldLoad

        sales = APIClient()
        sales.force_authenticate(user=self.sales)
        roster = sales.get('/api/agents/field-loads/agents/')
        self.assertEqual(roster.status_code, status.HTTP_200_OK)
        self.assertFalse(roster.data['choose_employee'])
        self.assertEqual(
            roster.data['results'],
            [{'id': self.sales.id, 'name': 'load_check_sales'}],
        )
        denied = self._write(sales, agent_id=self.agent.id)
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('themselves', denied.data['error'])
        self.assertNotIn('0718123456', denied.content.decode())
        self.assertFalse(FieldLoad.objects.filter(agent=self.agent).exists())

    def test_the_writer_can_fix_a_sent_back_load_and_send_it_again(self):
        sales = APIClient()
        sales.force_authenticate(user=self.sales)
        written = self._write(sales, qty=6)
        declined = self.client.post(
            f"/api/agents/field-loads/{written.data['id']}/decline-issue/",
            {'note': 'Take fewer cups'},
            format='json',
        )
        self.assertEqual(declined.status_code, status.HTTP_200_OK, declined.content)
        book = sales.get('/api/agents/field-loads/')
        row = next(item for item in book.data['results'] if item['id'] == written.data['id'])
        self.assertTrue(row['can_revise_issue'])
        self.assertEqual(row['review_note'], 'Take fewer cups')
        self.assertEqual(row['lines'][0]['product_name'], 'Check Cups')
        revised = sales.post(
            f"/api/agents/field-loads/{written.data['id']}/revise-issue/",
            {'lines': [{'product_id': self.cups.id, 'quantity': 2}]},
            format='json',
        )
        self.assertEqual(revised.status_code, status.HTTP_200_OK, revised.content)
        self.assertEqual(revised.data['status'], 'awaiting_issue')
        self.assertFalse(revised.data['can_revise_issue'])
        self.assertEqual(revised.data['lines'][0]['quantity_taken'], 2)
        self.assertEqual(revised.data['review_note'], '')
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 50)
        approved = self.client.post(
            f"/api/agents/field-loads/{written.data['id']}/approve-issue/",
            {},
            format='json',
        )
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.content)
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 48)

    def test_revising_empty_or_huge_lists_does_not_change_the_load(self):
        from agents.field_load_service import FieldLoadError, revise_issue
        from agents.models import FieldLoad

        sales = APIClient()
        sales.force_authenticate(user=self.sales)
        written = self._write(sales, qty=4)
        self.client.post(
            f"/api/agents/field-loads/{written.data['id']}/decline-issue/",
            {'note': 'Check'},
            format='json',
        )
        for _ in range(200):
            with self.assertRaises(FieldLoadError):
                revise_issue(load_id=written.data['id'], lines=[], user=self.sales)
        too_many = sales.post(
            f"/api/agents/field-loads/{written.data['id']}/revise-issue/",
            {'lines': [{'product_id': self.cups.id, 'quantity': 1}] * 41},
            format='json',
        )
        self.assertEqual(too_many.status_code, status.HTTP_400_BAD_REQUEST)
        kept = FieldLoad.objects.get(pk=written.data['id'])
        self.assertEqual(kept.status, 'issue_rejected')
        self.assertEqual(kept.lines.get().quantity_taken, 4)
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 50)

    def test_someone_else_cannot_change_a_sent_back_load(self):
        from agents.models import FieldLoad

        sales = APIClient()
        sales.force_authenticate(user=self.sales)
        written = self._write(sales, qty=5)
        self.client.post(
            f"/api/agents/field-loads/{written.data['id']}/decline-issue/",
            {'note': 'Check'},
            format='json',
        )
        stranger = User.objects.create_user(username='load_check_other', password='x')
        UserProfile.objects.create(
            user=stranger,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        other = APIClient()
        other.force_authenticate(user=stranger)
        denied = other.post(
            f"/api/agents/field-loads/{written.data['id']}/revise-issue/",
            {'lines': [{'product_id': self.cups.id, 'quantity': 1}]},
            format='json',
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('0718123456', denied.content.decode())
        anonymous = APIClient()
        hidden = anonymous.post(
            f"/api/agents/field-loads/{written.data['id']}/revise-issue/",
            {'lines': [{'product_id': self.cups.id, 'quantity': 1}]},
            format='json',
        )
        self.assertEqual(hidden.status_code, status.HTTP_401_UNAUTHORIZED)
        manager = self.client.post(
            f"/api/agents/field-loads/{written.data['id']}/revise-issue/",
            {'lines': [{'product_id': self.cups.id, 'quantity': 1}]},
            format='json',
        )
        self.assertEqual(manager.status_code, status.HTTP_403_FORBIDDEN)
        waiting = sales.post(
            '/api/agents/field-loads/',
            {
                'agent_id': self.sales.id,
                'lines': [{'product_id': self.cups.id, 'quantity': 1}],
            },
            format='json',
        )
        early = sales.post(
            f"/api/agents/field-loads/{waiting.data['id']}/revise-issue/",
            {'lines': [{'product_id': self.cups.id, 'quantity': 1}]},
            format='json',
        )
        self.assertEqual(early.status_code, status.HTTP_400_BAD_REQUEST)
        kept = FieldLoad.objects.get(pk=written.data['id'])
        self.assertEqual(kept.status, 'issue_rejected')
        self.assertEqual(kept.lines.get().quantity_taken, 5)
