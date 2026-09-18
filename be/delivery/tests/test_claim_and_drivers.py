"""Drivers list, claim ready pool, assign-priority over self-claim."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    ROLE_DELIVERY_AGENT,
    ROLE_DISPATCHER,
    ROLE_FIELD_AGENT,
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from agents.models import CustomerSite, FieldOrder, FieldOrderLine, SiteMedia
from agents.order_services import assign_delivery_agent, pack_order, submit_order
from agents.push import FakePushNotifier, set_push_notifier
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
import io
from products.models import Product
from sales.models import Customer


def _png(name='c.png'):
    buf = io.BytesIO()
    Image.new('RGB', (10, 10), color=(3, 4, 5)).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class ClaimAndDriversAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.agent = User.objects.create_user('claim_agent', password='x')
        UserProfile.objects.create(
            user=cls.agent,
            role='agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        cls.dispatch = User.objects.create_user('claim_disp', password='x')
        UserProfile.objects.create(
            user=cls.dispatch,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_DISPATCHER),
            is_active=True,
        )
        cls.driver = User.objects.create_user(
            'claim_drv', password='x', first_name='Ann', last_name='Driver',
        )
        UserProfile.objects.create(
            user=cls.driver,
            role='delivery',
            custom_role=Role.objects.get(name=ROLE_DELIVERY_AGENT),
            is_active=True,
        )
        cls.driver2 = User.objects.create_user('claim_drv2', password='x')
        UserProfile.objects.create(
            user=cls.driver2,
            role='delivery',
            custom_role=Role.objects.get(name=ROLE_DELIVERY_AGENT),
            is_active=True,
        )
        cls.sales = User.objects.create_user('claim_sales', password='x')
        UserProfile.objects.create(
            user=cls.sales,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.customer = Customer.objects.create(name='Claim Cust', phone='0799')
        cls.product = Product.objects.create(
            name='Tiles', sku='TIL-1', price=50, cost=20,
        )
        cls.site = CustomerSite.objects.create(
            customer=cls.customer,
            label='Gate',
            latitude='-1.28',
            longitude='36.83',
            created_by=cls.agent,
            status=CustomerSite.STATUS_FINALIZED,
        )
        SiteMedia.objects.create(site=cls.site, image=_png(), created_by=cls.agent)

    def setUp(self):
        set_push_notifier(FakePushNotifier())

    def _auth(self, user):
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def _ready_unassigned(self):
        order = FieldOrder.objects.create(
            site=self.site,
            customer=self.customer,
            created_by=self.agent,
        )
        FieldOrderLine.objects.create(
            order=order,
            product=self.product,
            quantity=Decimal('2'),
            unit_price=Decimal('50'),
            product_name='Tiles',
        )
        submit_order(order)
        order.refresh_from_db()
        pack_order(order)
        order.refresh_from_db()
        self.assertEqual(order.status, FieldOrder.STATUS_READY)
        self.assertIsNone(order.assigned_delivery_agent_id)
        return order

    def test_drivers_list_for_dispatch(self):
        self._auth(self.dispatch)
        res = self.client.get('/api/dispatch/drivers/')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        ids = {row['id'] for row in res.data}
        self.assertIn(self.driver.id, ids)
        self.assertIn(self.driver2.id, ids)
        self.assertNotIn(self.sales.id, ids)
        ann = next(r for r in res.data if r['id'] == self.driver.id)
        self.assertEqual(ann['display_name'], 'Ann Driver')

        # Router nested path also works
        nested = self.client.get('/api/dispatch/field-orders/drivers/')
        self.assertEqual(nested.status_code, status.HTTP_200_OK)

        self._auth(self.sales)
        forbidden = self.client.get('/api/dispatch/drivers/')
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

    def test_assign_rejects_non_driver(self):
        order = self._ready_unassigned()
        self._auth(self.dispatch)
        res = self.client.post(
            f'/api/dispatch/field-orders/{order.id}/assign/',
            {'delivery_agent_id': self.sales.id},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('delivery_agent_id', res.data)

    def test_available_and_claim_flow(self):
        order = self._ready_unassigned()
        self._auth(self.driver)
        avail = self.client.get('/api/delivery/available/')
        self.assertEqual(avail.status_code, status.HTTP_200_OK, avail.data)
        self.assertTrue(any(o['id'] == order.id for o in avail.data))

        claim = self.client.post(f'/api/delivery/field-orders/{order.id}/claim/')
        self.assertEqual(claim.status_code, status.HTTP_200_OK, claim.data)
        self.assertEqual(claim.data['status'], 'out_for_delivery')
        self.assertEqual(claim.data['assigned_delivery_agent_id'], self.driver.id)
        self.assertEqual(claim.data['assigned_delivery_agent_name'], 'Ann Driver')

        order.refresh_from_db()
        self.assertTrue(hasattr(order, 'delivery_stop'))

        route = self.client.get('/api/delivery/routes/today/')
        self.assertEqual(route.status_code, status.HTTP_200_OK)
        self.assertEqual(len(route.data['stops']), 1)

        # Gone from available pool
        avail2 = self.client.get('/api/delivery/available/')
        self.assertFalse(any(o['id'] == order.id for o in avail2.data))

    def test_dispatch_assign_takes_priority_over_claim(self):
        order = self._ready_unassigned()
        self._auth(self.dispatch)
        assigned = self.client.post(
            f'/api/dispatch/field-orders/{order.id}/assign/',
            {'delivery_agent_id': self.driver.id},
            format='json',
        )
        self.assertEqual(assigned.status_code, status.HTTP_200_OK, assigned.data)

        self._auth(self.driver2)
        avail = self.client.get('/api/delivery/available/')
        self.assertFalse(any(o['id'] == order.id for o in avail.data))

        claim = self.client.post(f'/api/delivery/field-orders/{order.id}/claim/')
        self.assertEqual(claim.status_code, status.HTTP_400_BAD_REQUEST)
        # Still on original driver's route
        self._auth(self.driver)
        route = self.client.get('/api/delivery/routes/today/')
        self.assertEqual(len(route.data['stops']), 1)
        self._auth(self.driver2)
        route2 = self.client.get('/api/delivery/routes/today/')
        self.assertEqual(len(route2.data['stops']), 0)

    def test_claim_rejects_non_ready_and_sales(self):
        order = FieldOrder.objects.create(
            site=self.site,
            customer=self.customer,
            created_by=self.agent,
            status=FieldOrder.STATUS_SUBMITTED,
        )
        FieldOrderLine.objects.create(
            order=order, product=self.product, quantity=1, unit_price=10,
            product_name='Tiles',
        )
        self._auth(self.driver)
        bad = self.client.post(f'/api/delivery/field-orders/{order.id}/claim/')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        ready = self._ready_unassigned()
        self._auth(self.sales)
        forbidden = self.client.post(
            f'/api/delivery/field-orders/{ready.id}/claim/',
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

    def test_claim_service_blocks_preassigned(self):
        order = self._ready_unassigned()
        assign_delivery_agent(order, self.driver)
        order.refresh_from_db()
        from agents.order_services import FieldOrderTransitionError, claim_ready_order
        with self.assertRaises(FieldOrderTransitionError):
            claim_ready_order(order, self.driver2)
