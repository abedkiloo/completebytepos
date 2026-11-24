"""Sale Detail must open field-load / null-branch sales that History lists."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_FIELD_AGENT, ensure_permissions, sync_default_roles
from sales.models import Customer, Sale
from settings.models import Branch, ModuleFeature, ModuleSettings, Tenant
from utils.tests.api_test_base import SuperAdminAPITestCase


def _enable_multi_branch(enabled=True):
    module, _ = ModuleSettings.objects.get_or_create(
        module_name='settings',
        defaults={'is_enabled': True, 'description': 'settings'},
    )
    module.is_enabled = True
    module.save(update_fields=['is_enabled'])
    feature, _ = ModuleFeature.objects.get_or_create(
        module=module,
        feature_key='multi_branch_support',
        defaults={'feature_name': 'Multi branch', 'is_enabled': enabled},
    )
    feature.is_enabled = enabled
    feature.save(update_fields=['is_enabled'])


class FieldLoadSaleDetailVisibilityTests(SuperAdminAPITestCase):
    """Corrected: past field-load sales open on Sale Detail under multi-branch."""

    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles()
        _enable_multi_branch(True)
        self.tenant = Tenant.objects.create(name='Load Tenant', code='LT1', is_active=True)
        self.hq = Branch.objects.create(
            name='HQ',
            branch_code='HQ1',
            tenant=self.tenant,
            is_headquarters=True,
            is_active=True,
        )
        self.agent = User.objects.create_user(username='detail_agent', password='x')
        UserProfile.objects.create(
            user=self.agent,
            role='field_agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        self.customer = Customer.objects.create(
            name='Detail Duka',
            phone='0718000111',
            created_by=self.agent,
        )

    def _agent_client(self):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.agent).access_token}'
        )
        return client

    def test_unit_null_branch_field_load_is_listed_and_retrieved(self):
        sale = Sale.objects.create(
            sale_number='FL-DET-1',
            sale_type='pos',
            status='completed',
            branch=None,
            cashier=self.agent,
            served_by=self.agent,
            customer=self.customer,
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            amount_paid=Decimal('100.00'),
            payment_method='cash',
            entry_source='field_load',
            client_channel='mobile',
        )
        client = self._agent_client()
        listed = client.get('/api/sales/')
        self.assertEqual(listed.status_code, status.HTTP_200_OK, listed.content)
        rows = listed.data.get('results', listed.data)
        ids = [row['id'] for row in rows]
        self.assertIn(sale.id, ids)

        detail = client.get(f'/api/sales/{sale.id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK, detail.content)
        self.assertEqual(detail.data['id'], sale.id)
        self.assertEqual(detail.data.get('entry_source'), 'field_load')
        self.assertTrue(detail.data.get('is_field_load_sale'))

    def test_corrected_functionality_friendly_404_for_missing_sale(self):
        client = self._agent_client()
        missing = client.get('/api/sales/999999999/')
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        detail = missing.data.get('detail', '')
        self.assertNotIn('No Sale matches the given query', detail)
        self.assertIn('not available', detail.lower())

    def test_security_field_sales_cannot_open_another_agents_shop_sale(self):
        other = User.objects.create_user(username='detail_other', password='x')
        shop = Sale.objects.create(
            sale_number='SHOP-DET-1',
            sale_type='pos',
            status='completed',
            branch=self.hq,
            cashier=other,
            served_by=other,
            customer=self.customer,
            subtotal=Decimal('50.00'),
            total=Decimal('50.00'),
            amount_paid=Decimal('50.00'),
            payment_method='cash',
            entry_source='pos',
            client_channel='mobile',
        )
        client = self._agent_client()
        denied = client.get(f'/api/sales/{shop.id}/')
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn(other.username, denied.content.decode())

    def test_integration_customer_detail_orders_match_sale_retrieve(self):
        sale = Sale.objects.create(
            sale_number='FL-DET-2',
            sale_type='pos',
            status='completed',
            branch=None,
            cashier=self.agent,
            served_by=self.agent,
            customer=self.customer,
            subtotal=Decimal('80.00'),
            total=Decimal('80.00'),
            amount_paid=Decimal('80.00'),
            payment_method='cash',
            entry_source='field_load',
            client_channel='mobile',
        )
        client = self._agent_client()
        profile = client.get(f'/api/sales/customers/{self.customer.id}/detail/')
        self.assertEqual(profile.status_code, status.HTTP_200_OK, profile.content)
        order_ids = [row['id'] for row in profile.data.get('orders', [])]
        self.assertIn(sale.id, order_ids)
        detail = client.get(f'/api/sales/{sale.id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK, detail.content)

    def test_stress_many_null_branch_load_sales_still_retrieve(self):
        client = self._agent_client()
        created = []
        for i in range(40):
            sale = Sale.objects.create(
                sale_number=f'FL-STRESS-{i}',
                sale_type='pos',
                status='completed',
                branch=None,
                cashier=self.agent,
                served_by=self.agent,
                customer=self.customer,
                subtotal=Decimal('10.00'),
                total=Decimal('10.00'),
                amount_paid=Decimal('10.00'),
                payment_method='cash',
                entry_source='field_load',
                client_channel='mobile',
            )
            created.append(sale.id)
        for sale_id in created[::5]:
            response = client.get(f'/api/sales/{sale_id}/')
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
