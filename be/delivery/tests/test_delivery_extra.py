"""Extra branches for delivery coverage gate."""

import io
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    ROLE_DELIVERY_AGENT,
    ROLE_FIELD_AGENT,
    ensure_permissions,
    sync_default_roles,
)
from agents.models import CustomerSite, FieldOrder, FieldOrderLine, SiteMedia
from agents.order_services import assign_delivery_agent, pack_order, submit_order
from delivery.models import DeliveryStop, ProposedPinCorrection
from delivery.services import (
    DeliveryTransitionError,
    collect_money,
    complete_stop,
    enqueue_assigned_order,
    propose_pin_correction,
    save_pod,
    update_line_results,
    validate_line_quantities,
)
from products.models import Product
from sales.models import Customer


def _png(name='x.png'):
    buf = io.BytesIO()
    Image.new('RGB', (8, 8), color=(1, 1, 1)).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class DeliveryExtraCoverageTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.agent = User.objects.create_user('dx_agent', password='x')
        UserProfile.objects.create(
            user=cls.agent, role='agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT), is_active=True,
        )
        cls.driver = User.objects.create_user('dx_driver', password='x')
        UserProfile.objects.create(
            user=cls.driver, role='delivery',
            custom_role=Role.objects.get(name=ROLE_DELIVERY_AGENT), is_active=True,
        )
        cls.superuser = User.objects.create_superuser('dx_su', 'su@x.com', 'x')
        cls.customer = Customer.objects.create(name='DX', phone='071')
        cls.product = Product.objects.create(name='X', sku='X1', price=1, cost=1)
        cls.site = CustomerSite.objects.create(
            customer=cls.customer, label='L', latitude='-1', longitude='36',
            created_by=cls.agent, status=CustomerSite.STATUS_FINALIZED,
        )
        SiteMedia.objects.create(site=cls.site, image=_png(), created_by=cls.agent)

    def _auth(self, user):
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def _order(self):
        order = FieldOrder.objects.create(
            site=self.site, customer=self.customer, created_by=self.agent,
        )
        FieldOrderLine.objects.create(
            order=order, product=self.product, quantity=2, unit_price=1, product_name='X',
        )
        submit_order(order)
        order.refresh_from_db()
        pack_order(order)
        order.refresh_from_db()
        assign_delivery_agent(order, self.driver)
        order.refresh_from_db()
        return order

    def test_enqueue_guards_and_create_path(self):
        order = FieldOrder.objects.create(
            site=self.site, customer=self.customer, created_by=self.agent,
            status=FieldOrder.STATUS_READY,
        )
        with self.assertRaises(DeliveryTransitionError):
            enqueue_assigned_order(order)
        order.assigned_delivery_agent = self.driver
        order.status = FieldOrder.STATUS_SUBMITTED
        order.save()
        with self.assertRaises(DeliveryTransitionError):
            enqueue_assigned_order(order)

        order.status = FieldOrder.STATUS_READY
        order.save()
        with patch('delivery.services.sync_assigned_orders_onto_route', side_effect=lambda r: r):
            stop = enqueue_assigned_order(order)
        self.assertIsNotNone(stop.id)

    def test_negative_qty_unknown_product_collect_status(self):
        with self.assertRaises(DeliveryTransitionError):
            validate_line_quantities(Decimal('1'), Decimal('-1'), Decimal('0'))
        order = self._order()
        stop = order.delivery_stop
        with self.assertRaises(DeliveryTransitionError):
            collect_money(stop, method='cash')
        stop.status = DeliveryStop.STATUS_COMPLETED
        stop.save(update_fields=['status'])
        with self.assertRaises(DeliveryTransitionError):
            update_line_results(stop, [{
                'product_id': self.product.id,
                'delivered_quantity': '1',
                'returned_quantity': '0',
            }])
        stop.status = DeliveryStop.STATUS_ARRIVED
        stop.save(update_fields=['status'])
        with self.assertRaises(DeliveryTransitionError):
            update_line_results(stop, [{
                'product_id': 999999,
                'delivered_quantity': '1',
                'returned_quantity': '0',
            }])
        # arrived → delivering inside update
        stop.status = DeliveryStop.STATUS_ARRIVED
        stop.save(update_fields=['status'])
        update_line_results(stop, [{
            'product_id': self.product.id,
            'delivered_quantity': '1',
            'returned_quantity': '0',
        }])
        stop.refresh_from_db()
        self.assertEqual(stop.status, DeliveryStop.STATUS_DELIVERING)

    def test_incomplete_pod_and_complete_without_require(self):
        order = self._order()
        stop = order.delivery_stop
        stop.status = DeliveryStop.STATUS_COLLECTED
        stop.save(update_fields=['status'])
        save_pod(stop, latitude=Decimal('-1'), longitude=Decimal('36'))
        with self.assertRaises(DeliveryTransitionError):
            complete_stop(stop)
        complete_stop(stop, require_pod=False)
        stop.refresh_from_db()
        self.assertEqual(stop.status, DeliveryStop.STATUS_COMPLETED)
        self.assertIn('PinCorrection', str(propose_pin_correction(
            stop, latitude=Decimal('-1.1'), longitude=Decimal('36.1'), user=self.driver,
        )))
        self.assertTrue(ProposedPinCorrection.objects.filter(stop=stop).exists())

    def test_api_error_paths_and_superuser(self):
        order = self._order()
        stop_id = order.delivery_stop.id
        self._auth(self.driver)
        # arrive twice → illegal transition
        self.client.post(f'/api/delivery/stops/{stop_id}/arrive/')
        bad = self.client.post(f'/api/delivery/stops/{stop_id}/arrive/')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        bad_start = self.client.post(f'/api/delivery/stops/{stop_id}/start/')
        self.assertEqual(bad_start.status_code, status.HTTP_200_OK)
        # start again from delivering fails
        again = self.client.post(f'/api/delivery/stops/{stop_id}/start/')
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)
        # collect while wrong status after reset? already delivering — ok
        # force collect error via service path on pending stop
        o2 = FieldOrder.objects.create(
            site=self.site, customer=self.customer, created_by=self.agent,
        )
        FieldOrderLine.objects.create(
            order=o2, product=self.product, quantity=1, unit_price=1, product_name='X',
        )
        submit_order(o2)
        o2.refresh_from_db()
        pack_order(o2)
        o2.refresh_from_db()
        assign_delivery_agent(o2, self.driver)
        sid2 = o2.delivery_stop.id
        bad_collect = self.client.post(
            f'/api/delivery/stops/{sid2}/collect/',
            {'method': 'cash'},
            format='json',
        )
        self.assertEqual(bad_collect.status_code, status.HTTP_400_BAD_REQUEST)

        self._auth(self.superuser)
        listing = self.client.get('/api/delivery/stops/')
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(listing.data), 1)

    def test_serializer_abs_without_request(self):
        from delivery.serializers import ProofOfDeliverySerializer
        order = self._order()
        stop = order.delivery_stop
        pod = save_pod(
            stop,
            signature_image=_png('s.png'),
            photo=_png('p.png'),
            latitude=Decimal('-1'),
            longitude=Decimal('36'),
        )
        data = ProofOfDeliverySerializer(pod).data
        self.assertIsNotNone(data['signature_url'])
