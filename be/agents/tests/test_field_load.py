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
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from agents.field_load_service import FieldLoadError, _parse_qty
from products.models import Product
from sales.models import Customer
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
        self.assertEqual(sold.data['money']['collected'], '750.00')

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
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        other = self._client(self.other)
        hidden = other.get(f"/api/agents/field-loads/{issued.data['id']}/")
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn('Locked Cups', hidden.content.decode())

    def test_sales_can_issue_and_cannot_accept(self):
        sales = self._client(self.sales)
        issued = sales.post(
            '/api/agents/field-loads/',
            {
                'agent_id': self.agent.id,
                'lines': [{'product_id': self.cups.id, 'quantity': 2}],
            },
            format='json',
        )
        self.assertEqual(issued.status_code, status.HTTP_201_CREATED, issued.content)
        line_id = issued.data['lines'][0]['id']
        sales.post(
            f"/api/agents/field-loads/{issued.data['id']}/return/",
            {'lines': [{'line_id': line_id, 'quantity_returned': 2}]},
            format='json',
        )
        accepted = sales.post(f"/api/agents/field-loads/{issued.data['id']}/accept/", {}, format='json')
        self.assertEqual(accepted.status_code, status.HTTP_403_FORBIDDEN)
        self.cups.refresh_from_db()
        self.assertEqual(self.cups.stock_quantity, 28)

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
                'payment_method': 'split',
                'tender': 'mpesa',
            },
            format='json',
        )
        self.assertEqual(sold.status_code, status.HTTP_200_OK, sold.content)
        sale = Sale.objects.get(field_load_sale__load_id=issued.data['id'])
        self.assertEqual(sale.entry_source, 'field_load')
        self.assertFalse(sale.is_field_sale)
        self.assertTrue(sale.is_field_load_sale)
        self.assertEqual(sale.sale_origin, 'field_load')
        self.assertEqual(sale.payment_method, 'mpesa')
        self.assertEqual(sold.data['money']['mpesa'], '200.00')
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
        with self.assertRaises(FieldLoadError):
            _resolve_tender(payment_method='split', paid=Decimal('1'), total=Decimal('5'), has_customer=False, tender='cash')
        with self.assertRaises(FieldLoadError):
            _resolve_tender(payment_method='split', paid=Decimal('0'), total=Decimal('5'), has_customer=True, tender='cash')
        with self.assertRaises(FieldLoadError):
            _resolve_tender(payment_method='split', paid=Decimal('1'), total=Decimal('5'), has_customer=True, tender='card')
        self.assertEqual(
            _resolve_tender(payment_method='split', paid=Decimal('1'), total=Decimal('5'), has_customer=True, tender='cash')[0],
            'cash',
        )
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
        denied_agents = agent.get('/api/agents/field-loads/agents/')
        self.assertEqual(denied_agents.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(self.customer.phone, denied_agents.content.decode())

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
        self.assertEqual(blocked_stock.status_code, 400)
        self.assertNotIn(self.customer.phone, blocked_stock.content.decode())

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
