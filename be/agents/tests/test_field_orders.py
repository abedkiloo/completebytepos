"""Field order state machine + dispatch board."""

import io
import uuid

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    ROLE_DISPATCHER,
    ROLE_FIELD_AGENT,
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from agents.models import CustomerSite, FieldOrder, FieldOrderLine, SiteMedia
from agents.order_services import (
    FieldOrderTransitionError,
    assign_delivery_agent,
    pack_order,
    submit_order,
    transition,
)
from agents.push import FakePushNotifier, set_push_notifier
from products.models import Product
from sales.models import Customer


def _png(name='s.png'):
    buf = io.BytesIO()
    Image.new('RGB', (16, 16), color=(1, 2, 3)).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class FieldOrderAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.agent_user = User.objects.create_user('fo_agent', password='x')
        UserProfile.objects.create(
            user=cls.agent_user,
            role='agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        cls.dispatch_user = User.objects.create_user('fo_dispatch', password='x')
        UserProfile.objects.create(
            user=cls.dispatch_user,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_DISPATCHER),
            is_active=True,
        )
        cls.driver = User.objects.create_user('fo_driver', password='x')
        cls.sales_user = User.objects.create_user('fo_sales', password='x')
        UserProfile.objects.create(
            user=cls.sales_user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.customer = Customer.objects.create(name='FO Cust', phone='0711')
        cls.product = Product.objects.create(
            name='Cement', sku='CEM-1', price=500, cost=400,
        )
        cls.site = CustomerSite.objects.create(
            customer=cls.customer,
            label='Yard',
            latitude='-1.29',
            longitude='36.82',
            created_by=cls.agent_user,
            status=CustomerSite.STATUS_FINALIZED,
        )
        SiteMedia.objects.create(site=cls.site, image=_png(), created_by=cls.agent_user)

    def setUp(self):
        set_push_notifier(FakePushNotifier())
        token = RefreshToken.for_user(self.agent_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def _auth(self, user):
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def _create_order(self):
        res = self.client.post(
            '/api/agents/field-orders/',
            {
                'site_id': self.site.id,
                'client_uuid': str(uuid.uuid4()),
                'lines': [
                    {'product_id': self.product.id, 'quantity': '2', 'unit_price': '500'},
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        return res.data['id']

    def test_illegal_transition_fails(self):
        order = FieldOrder.objects.create(
            site=self.site, customer=self.customer, created_by=self.agent_user,
        )
        FieldOrderLine.objects.create(
            order=order, product=self.product, quantity=1, unit_price=10, product_name='Cement',
        )
        with self.assertRaises(FieldOrderTransitionError):
            transition(order, FieldOrder.STATUS_READY)

    def test_submit_without_site_pin_fails(self):
        bad_site = CustomerSite.objects.create(
            customer=self.customer, created_by=self.agent_user,
        )
        SiteMedia.objects.create(site=bad_site, image=_png('b.png'), created_by=self.agent_user)
        order = FieldOrder.objects.create(
            site=bad_site, customer=self.customer, created_by=self.agent_user,
        )
        FieldOrderLine.objects.create(
            order=order, product=self.product, quantity=1, unit_price=10, product_name='Cement',
        )
        res = self.client.post(f'/api/agents/field-orders/{order.id}/submit/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('location', res.data)

    def test_submit_without_media_ok(self):
        site = CustomerSite.objects.create(
            customer=self.customer,
            latitude='-1.2',
            longitude='36.8',
            created_by=self.agent_user,
        )
        order = FieldOrder.objects.create(
            site=site, customer=self.customer, created_by=self.agent_user,
        )
        FieldOrderLine.objects.create(
            order=order, product=self.product, quantity=1, unit_price=10, product_name='Cement',
        )
        submit_order(order)
        order.refresh_from_db()
        self.assertEqual(order.status, FieldOrder.STATUS_SUBMITTED)

    def test_agent_create_submit_dispatch_pack_assign(self):
        order_id = self._create_order()
        sub = self.client.post(f'/api/agents/field-orders/{order_id}/submit/')
        self.assertEqual(sub.status_code, status.HTTP_200_OK, sub.data)
        self.assertEqual(sub.data['status'], 'submitted')

        self._auth(self.dispatch_user)
        queue = self.client.get('/api/dispatch/queue/')
        self.assertEqual(queue.status_code, status.HTTP_200_OK)
        self.assertTrue(any(o['id'] == order_id for o in queue.data))

        packed = self.client.post(f'/api/dispatch/field-orders/{order_id}/pack/')
        self.assertEqual(packed.status_code, status.HTTP_200_OK, packed.data)
        self.assertEqual(packed.data['status'], 'ready')
        self.assertTrue(packed.data['stock_allocated'])

        assigned = self.client.post(
            f'/api/dispatch/field-orders/{order_id}/assign/',
            {'delivery_agent_id': self.driver.id},
            format='json',
        )
        self.assertEqual(assigned.status_code, status.HTTP_200_OK, assigned.data)
        self.assertEqual(assigned.data['assigned_delivery_agent_id'], self.driver.id)

    def test_assign_requires_agent(self):
        order_id = self._create_order()
        self.client.post(f'/api/agents/field-orders/{order_id}/submit/')
        self._auth(self.dispatch_user)
        self.client.post(f'/api/dispatch/field-orders/{order_id}/pack/')
        res = self.client.post(
            f'/api/dispatch/field-orders/{order_id}/assign/',
            {},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sales_denied_field_orders_and_dispatch(self):
        self._auth(self.sales_user)
        self.assertEqual(
            self.client.get('/api/agents/field-orders/').status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.get('/api/dispatch/queue/').status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_pack_service_allocate_on_pack(self):
        order = FieldOrder.objects.create(
            site=self.site,
            customer=self.customer,
            status=FieldOrder.STATUS_SUBMITTED,
            created_by=self.agent_user,
        )
        FieldOrderLine.objects.create(
            order=order, product=self.product, quantity=1, unit_price=10, product_name='Cement',
        )
        packed = pack_order(order)
        self.assertTrue(packed.stock_allocated)
        self.assertEqual(packed.status, FieldOrder.STATUS_READY)

    def test_assign_before_pack_fails(self):
        order = FieldOrder.objects.create(
            site=self.site,
            customer=self.customer,
            status=FieldOrder.STATUS_SUBMITTED,
            created_by=self.agent_user,
        )
        with self.assertRaises(FieldOrderTransitionError):
            assign_delivery_agent(order, self.driver)

    def test_str_and_line_total(self):
        order = FieldOrder.objects.create(site=self.site, created_by=self.agent_user)
        line = FieldOrderLine.objects.create(
            order=order, product=self.product, quantity=2, unit_price=5, product_name='Cement',
        )
        self.assertIn('FieldOrder', str(order))
        self.assertIn('Line', str(line))
        self.assertEqual(line.line_total, 10)

    def test_place_visit_order_one_shot(self):
        res = self.client.post(
            '/api/agents/field-orders/place/',
            {
                'customer_id': self.customer.id,
                'latitude': '-1.2921',
                'longitude': '36.8219',
                'accuracy': 8.5,
                'landmark': 'Blue gate',
                'label': '',
                'notes': 'Urgent',
                'lines': [
                    {
                        'product_id': self.product.id,
                        'quantity': '2',
                        'unit_price': '500.00',
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data['status'], 'submitted')
        self.assertEqual(res.data['customer_name'], self.customer.name)
        self.assertEqual(len(res.data['lines']), 1)
        self.assertEqual(res.data['site_detail']['status'], 'finalized')
        self.assertTrue(res.data['site_detail']['has_pin'])

    def test_dispatch_list_filters_and_pack(self):
        order_id = self._create_order()
        self.client.post(f'/api/agents/field-orders/{order_id}/submit/')
        self._auth(self.dispatch_user)

        listed = self.client.get(
            '/api/dispatch/field-orders/',
            {'status': 'awaiting_pack', 'search': 'FO Cust'},
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK, listed.data)
        rows = listed.data['results'] if isinstance(listed.data, dict) else listed.data
        self.assertTrue(any(o['id'] == order_id for o in rows))

        packed = self.client.post(f'/api/dispatch/field-orders/{order_id}/pack/')
        self.assertEqual(packed.status_code, status.HTTP_200_OK, packed.data)
        self.assertEqual(packed.data['status'], 'ready')

    def test_create_missing_product_and_empty_lines(self):
        bad = self.client.post(
            '/api/agents/field-orders/',
            {'site_id': self.site.id, 'lines': []},
            format='json',
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        missing = self.client.post(
            '/api/agents/field-orders/',
            {
                'site_id': self.site.id,
                'lines': [{'product_id': 999999, 'quantity': '1'}],
            },
            format='json',
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
