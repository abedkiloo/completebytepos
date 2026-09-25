"""Extra coverage for field-order services, serializers, push, dispatch edges."""

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
    ROLE_DELIVERY_AGENT,
    ROLE_DISPATCHER,
    ROLE_FIELD_AGENT,
    ensure_permissions,
    sync_default_roles,
)
from agents.models import CustomerSite, FieldOrder, FieldOrderLine, SiteMedia
from agents.order_services import (
    FieldOrderTransitionError,
    assert_site_ready_for_order,
    assign_delivery_agent,
    cancel_order,
    claim_ready_order,
    pack_order,
    start_packing,
    submit_order,
)
from agents.push import FakePushNotifier, NoOpPushNotifier, get_push_notifier, set_push_notifier
from products.models import Product
from sales.models import Customer


def _png(name='x.png'):
    buf = io.BytesIO()
    Image.new('RGB', (8, 8), color=(9, 9, 9)).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class FieldOrderExtraTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.agent = User.objects.create_user('fo2_agent', password='x')
        UserProfile.objects.create(
            user=cls.agent, role='agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT), is_active=True,
        )
        cls.dispatch = User.objects.create_user('fo2_disp', password='x')
        UserProfile.objects.create(
            user=cls.dispatch, role='manager',
            custom_role=Role.objects.get(name=ROLE_DISPATCHER), is_active=True,
        )
        cls.driver = User.objects.create_user('fo2_drv', password='x')
        UserProfile.objects.create(
            user=cls.driver, role='delivery',
            custom_role=Role.objects.get(name=ROLE_DELIVERY_AGENT), is_active=True,
        )
        cls.customer = Customer.objects.create(name='C2', phone='0722')
        cls.product = Product.objects.create(name='Sand', sku='SND-1', price=100, cost=50)
        cls.site = CustomerSite.objects.create(
            customer=cls.customer, latitude='-1.1', longitude='36.7',
            created_by=cls.agent, status=CustomerSite.STATUS_FINALIZED,
        )
        SiteMedia.objects.create(site=cls.site, image=_png(), created_by=cls.agent)

    def setUp(self):
        set_push_notifier(FakePushNotifier())
        token = RefreshToken.for_user(self.agent)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_assert_site_ready_edges(self):
        with self.assertRaises(FieldOrderTransitionError):
            assert_site_ready_for_order(None)
        orphan = CustomerSite.objects.create(
            latitude='-1', longitude='36', created_by=self.agent,
        )
        SiteMedia.objects.create(site=orphan, image=_png('o.png'), created_by=self.agent)
        with self.assertRaises(FieldOrderTransitionError):
            assert_site_ready_for_order(orphan)

    def test_submit_empty_lines_and_customer_copy(self):
        order = FieldOrder.objects.create(site=self.site, created_by=self.agent)
        with self.assertRaises(FieldOrderTransitionError):
            submit_order(order)
        FieldOrderLine.objects.create(
            order=order, product=self.product, quantity=1, unit_price=100, product_name='Sand',
        )
        submit_order(order)
        order.refresh_from_db()
        self.assertEqual(order.customer_id, self.customer.id)

    def test_start_packing_cancel_noop_push(self):
        order = FieldOrder.objects.create(
            site=self.site, customer=self.customer,
            status=FieldOrder.STATUS_SUBMITTED, created_by=self.agent,
        )
        start_packing(order)
        order.refresh_from_db()
        self.assertEqual(order.status, FieldOrder.STATUS_PACKING)
        cancel_order(order)
        order.refresh_from_db()
        self.assertEqual(order.status, FieldOrder.STATUS_CANCELLED)

        set_push_notifier(NoOpPushNotifier())
        self.assertFalse(get_push_notifier().notify(user_id=1, title='t', body='b'))
        # abstract interface
        from agents.push import PushNotifier
        with self.assertRaises(NotImplementedError):
            PushNotifier().notify(user_id=1, title='t', body='b')

    def test_assign_from_packing_auto_packs(self):
        order = FieldOrder.objects.create(
            site=self.site, customer=self.customer,
            status=FieldOrder.STATUS_PACKING, created_by=self.agent,
        )
        FieldOrderLine.objects.create(
            order=order, product=self.product, quantity=1, unit_price=1, product_name='Sand',
        )
        assign_delivery_agent(order, self.driver)
        order.refresh_from_db()
        self.assertTrue(order.stock_allocated)
        self.assertEqual(order.assigned_delivery_agent_id, self.driver.id)

    def test_assign_none_and_done_status(self):
        order = FieldOrder.objects.create(
            site=self.site, status=FieldOrder.STATUS_READY, created_by=self.agent,
        )
        with self.assertRaises(FieldOrderTransitionError):
            assign_delivery_agent(order, None)
        order.status = FieldOrder.STATUS_DONE
        order.save(update_fields=['status'])
        with self.assertRaises(FieldOrderTransitionError):
            assign_delivery_agent(order, self.driver)

    def test_pack_wrong_status(self):
        order = FieldOrder.objects.create(
            site=self.site, status=FieldOrder.STATUS_DRAFT, created_by=self.agent,
        )
        with self.assertRaises(FieldOrderTransitionError):
            pack_order(order)

    def test_list_filters_and_default_unit_price(self):
        order_id = self.client.post(
            '/api/visits/field-orders/',
            {
                'site_id': self.site.id,
                'notes': 'n',
                'client_uuid': str(uuid.uuid4()),
                'lines': [{'product_id': self.product.id, 'quantity': '1'}],
            },
            format='json',
        ).data['id']
        listed = self.client.get('/api/visits/field-orders/?status=draft&mine=1')
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        rows = listed.data if isinstance(listed.data, list) else listed.data.get('results', [])
        self.assertTrue(any(o['id'] == order_id for o in rows))

        token = RefreshToken.for_user(self.dispatch)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        q = self.client.get('/api/dispatch/queue/?status=submitted')
        self.assertEqual(q.status_code, status.HTTP_200_OK)

        agent_token = RefreshToken.for_user(self.agent)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {agent_token.access_token}')
        self.client.post(f'/api/visits/field-orders/{order_id}/submit/')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        packed = self.client.post(f'/api/dispatch/field-orders/{order_id}/pack/')
        self.assertEqual(packed.status_code, status.HTTP_200_OK)
        again = self.client.post(f'/api/dispatch/field-orders/{order_id}/pack/')
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)
        bad_agent = self.client.post(
            f'/api/dispatch/field-orders/{order_id}/assign/',
            {'delivery_agent_id': 999999},
            format='json',
        )
        self.assertEqual(bad_agent.status_code, status.HTTP_400_BAD_REQUEST)
        # TransitionError on assign after forcing bad status
        order = FieldOrder.objects.get(pk=order_id)
        order.status = FieldOrder.STATUS_DONE
        order.save(update_fields=['status'])
        assign_fail = self.client.post(
            f'/api/dispatch/field-orders/{order_id}/assign/',
            {'delivery_agent_id': self.driver.id},
            format='json',
        )
        self.assertEqual(assign_fail.status_code, status.HTTP_400_BAD_REQUEST)
        missing = self.client.post('/api/dispatch/field-orders/999999/pack/')
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        missing_a = self.client.post(
            '/api/dispatch/field-orders/999999/assign/',
            {'delivery_agent_id': self.driver.id},
            format='json',
        )
        self.assertEqual(missing_a.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_unknown_site(self):
        res = self.client.post(
            '/api/visits/field-orders/',
            {'site_id': 999999, 'lines': [{'product_id': self.product.id, 'quantity': '1'}]},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_requires_site_customer(self):
        orphan = CustomerSite.objects.create(
            latitude='-1', longitude='36', created_by=self.agent,
        )
        res = self.client.post(
            '/api/visits/field-orders/',
            {
                'site_id': orphan.id,
                'lines': [{'product_id': self.product.id, 'quantity': '1'}],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('customer', res.data)

    def test_pack_requires_customer_and_posts_debt_once(self):
        from decimal import Decimal

        from agents.order_services import pack_order, post_field_order_debt
        from sales.models import CustomerWalletTransaction

        orphan_site = CustomerSite.objects.create(
            latitude='-1.1', longitude='36.7', created_by=self.agent,
        )
        orphan = FieldOrder.objects.create(
            site=orphan_site, status=FieldOrder.STATUS_SUBMITTED, created_by=self.agent,
        )
        FieldOrderLine.objects.create(
            order=orphan, product=self.product, quantity=1, unit_price=50, product_name='Sand',
        )
        with self.assertRaises(FieldOrderTransitionError):
            pack_order(orphan)

        order = FieldOrder.objects.create(
            site=self.site, customer=self.customer,
            status=FieldOrder.STATUS_SUBMITTED, created_by=self.agent,
        )
        FieldOrderLine.objects.create(
            order=order, product=self.product, quantity=2, unit_price=100, product_name='Sand',
        )
        pack_order(order, user=self.dispatch)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('-200.00'))
        self.assertEqual(
            CustomerWalletTransaction.objects.filter(reference=f'FO-{order.id}').count(),
            1,
        )
        post_field_order_debt(order, user=self.dispatch)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('-200.00'))
        self.assertEqual(
            CustomerWalletTransaction.objects.filter(reference=f'FO-{order.id}').count(),
            1,
        )

    def test_pack_skips_debt_when_total_is_zero(self):
        from decimal import Decimal

        from sales.models import CustomerWalletTransaction

        order = FieldOrder.objects.create(
            site=self.site, customer=self.customer,
            status=FieldOrder.STATUS_PACKING, created_by=self.agent,
        )
        FieldOrderLine.objects.create(
            order=order, product=self.product, quantity=1, unit_price=0, product_name='Sand',
        )
        pack_order(order)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('0.00'))
        self.assertFalse(
            CustomerWalletTransaction.objects.filter(reference=f'FO-{order.id}').exists()
        )

    def test_pack_copies_customer_from_site(self):
        from decimal import Decimal

        order = FieldOrder.objects.create(
            site=self.site, status=FieldOrder.STATUS_SUBMITTED, created_by=self.agent,
        )
        FieldOrderLine.objects.create(
            order=order, product=self.product, quantity=1, unit_price=40, product_name='Sand',
        )
        pack_order(order)
        order.refresh_from_db()
        self.assertEqual(order.customer_id, self.customer.id)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('-40.00'))

    def test_site_media_and_claim_guards(self):
        site = CustomerSite.objects.create(
            customer=self.customer, latitude='-1.1', longitude='36.7',
            created_by=self.agent,
        )
        with self.assertRaises(FieldOrderTransitionError):
            assert_site_ready_for_order(site, min_media=1)

        order = FieldOrder.objects.create(
            site=self.site, customer=self.customer,
            status=FieldOrder.STATUS_READY, created_by=self.agent,
        )
        with self.assertRaises(FieldOrderTransitionError):
            claim_ready_order(order, None)
        order.assigned_delivery_agent = self.driver
        order.save(update_fields=['assigned_delivery_agent'])
        with self.assertRaises(FieldOrderTransitionError):
            claim_ready_order(order, self.agent)
