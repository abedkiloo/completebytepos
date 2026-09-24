"""Delivery routes, stop state machine, POD hard rule."""

import io
from decimal import Decimal

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
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from agents.models import CustomerSite, FieldOrder, FieldOrderLine, SiteMedia
from agents.order_services import assign_delivery_agent, pack_order, submit_order
from delivery.config import REQUIRE_POD_TO_COMPLETE
from delivery.models import DeliveryStop, ProofOfDelivery
from delivery.services import (
    DeliveryTransitionError,
    arrive,
    collect_money,
    complete_stop,
    next_open_stop,
    save_pod,
    start_delivery,
    transition_stop,
    update_line_results,
    validate_line_quantities,
)
from products.models import Product
from sales.models import Customer


def _png(name='p.png'):
    buf = io.BytesIO()
    Image.new('RGB', (12, 12), color=(9, 8, 7)).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class DeliveryAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.agent = User.objects.create_user('del_agent', password='x')
        UserProfile.objects.create(
            user=cls.agent,
            role='agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        cls.dispatch = User.objects.create_user('del_dispatch', password='x')
        UserProfile.objects.create(
            user=cls.dispatch,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_DISPATCHER),
            is_active=True,
        )
        cls.driver = User.objects.create_user('del_driver', password='x')
        UserProfile.objects.create(
            user=cls.driver,
            role='delivery',
            custom_role=Role.objects.get(name=ROLE_DELIVERY_AGENT),
            is_active=True,
        )
        cls.driver2 = User.objects.create_user('del_driver2', password='x')
        UserProfile.objects.create(
            user=cls.driver2,
            role='delivery',
            custom_role=Role.objects.get(name=ROLE_DELIVERY_AGENT),
            is_active=True,
        )
        cls.sales = User.objects.create_user('del_sales', password='x')
        UserProfile.objects.create(
            user=cls.sales,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.customer = Customer.objects.create(name='Del Cust', phone='0700')
        cls.product = Product.objects.create(
            name='Paint', sku='PNT-1', price=100, cost=50,
        )
        cls.site = CustomerSite.objects.create(
            customer=cls.customer,
            label='Blue gate',
            latitude='-1.30',
            longitude='36.80',
            landmark='Blue container',
            created_by=cls.agent,
            status=CustomerSite.STATUS_FINALIZED,
        )
        SiteMedia.objects.create(site=cls.site, image=_png(), created_by=cls.agent)

    def _auth(self, user):
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def _ready_order(self):
        order = FieldOrder.objects.create(
            site=self.site,
            customer=self.customer,
            created_by=self.agent,
        )
        FieldOrderLine.objects.create(
            order=order,
            product=self.product,
            quantity=Decimal('4'),
            unit_price=Decimal('100'),
            product_name='Paint',
        )
        submit_order(order)
        order.refresh_from_db()
        pack_order(order)
        order.refresh_from_db()
        assign_delivery_agent(order, self.driver)
        order.refresh_from_db()
        return order

    def test_assign_enqueues_stop_on_today_route(self):
        order = self._ready_order()
        self.assertEqual(order.status, FieldOrder.STATUS_OUT_FOR_DELIVERY)
        self.assertTrue(hasattr(order, 'delivery_stop'))
        self._auth(self.driver)
        res = self.client.get('/api/delivery/routes/today/')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(len(res.data['stops']), 1)
        stop = res.data['stops'][0]
        self.assertEqual(stop['status'], 'pending')
        self.assertIn('site', stop)
        self.assertEqual(stop['site']['label'], 'Blue gate')
        self.assertTrue(stop['site']['media'])
        # Map + media before lines in payload shape
        self.assertIn('lines', stop)

    def test_two_stop_route_and_next_stop(self):
        o1 = self._ready_order()
        site2 = CustomerSite.objects.create(
            customer=self.customer,
            label='Yard 2',
            latitude='-1.31',
            longitude='36.81',
            created_by=self.agent,
            status=CustomerSite.STATUS_FINALIZED,
        )
        SiteMedia.objects.create(site=site2, image=_png('2.png'), created_by=self.agent)
        o2 = FieldOrder.objects.create(
            site=site2, customer=self.customer, created_by=self.agent,
        )
        FieldOrderLine.objects.create(
            order=o2, product=self.product, quantity=1, unit_price=10, product_name='Paint',
        )
        submit_order(o2)
        o2.refresh_from_db()
        pack_order(o2)
        o2.refresh_from_db()
        assign_delivery_agent(o2, self.driver)
        self._auth(self.driver)
        res = self.client.get('/api/delivery/routes/today/')
        self.assertEqual(len(res.data['stops']), 2)
        self.assertEqual(res.data['next_stop_id'], o1.delivery_stop.id)

    def test_cannot_complete_without_pod(self):
        self.assertTrue(REQUIRE_POD_TO_COMPLETE)
        order = self._ready_order()
        stop = order.delivery_stop
        arrive(stop)
        stop.refresh_from_db()
        start_delivery(stop)
        stop.refresh_from_db()
        update_line_results(stop, [{
            'product_id': self.product.id,
            'delivered_quantity': '4',
            'returned_quantity': '0',
        }])
        stop.refresh_from_db()
        collect_money(stop, method='cash', amount=Decimal('400'))
        stop.refresh_from_db()
        with self.assertRaises(DeliveryTransitionError):
            complete_stop(stop)

        self._auth(self.driver)
        res = self.client.post(f'/api/delivery/stops/{stop.id}/complete/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('pod', res.data)

    def test_partial_quantities_validation(self):
        with self.assertRaises(DeliveryTransitionError):
            validate_line_quantities(Decimal('2'), Decimal('3'), Decimal('0'))
        with self.assertRaises(DeliveryTransitionError):
            validate_line_quantities(Decimal('2'), Decimal('1'), Decimal('2'))
        validate_line_quantities(Decimal('2'), Decimal('1'), Decimal('1'))

        order = self._ready_order()
        stop = order.delivery_stop
        self._auth(self.driver)
        bad = self.client.post(
            f'/api/delivery/stops/{stop.id}/lines/',
            {
                'lines': [{
                    'product_id': self.product.id,
                    'delivered_quantity': '5',
                    'returned_quantity': '0',
                }],
            },
            format='json',
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        ok = self.client.post(
            f'/api/delivery/stops/{stop.id}/lines/',
            {
                'lines': [{
                    'product_id': self.product.id,
                    'delivered_quantity': '3',
                    'returned_quantity': '1',
                }],
            },
            format='json',
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK, ok.data)
        line = ok.data['lines'][0]
        self.assertEqual(Decimal(line['delivered_quantity']), Decimal('3'))
        self.assertTrue(line['stock_applied'])

    def test_full_happy_path_with_pod(self):
        order = self._ready_order()
        stop_id = order.delivery_stop.id
        self._auth(self.driver)

        self.assertEqual(
            self.client.post(f'/api/delivery/stops/{stop_id}/arrive/').status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.post(f'/api/delivery/stops/{stop_id}/start/').status_code,
            status.HTTP_200_OK,
        )
        self.client.post(
            f'/api/delivery/stops/{stop_id}/lines/',
            {
                'lines': [{
                    'product_id': self.product.id,
                    'delivered_quantity': '4',
                    'returned_quantity': '0',
                }],
            },
            format='json',
        )
        self.client.post(
            f'/api/delivery/stops/{stop_id}/collect/',
            {'method': 'cash', 'amount': '400'},
            format='json',
        )
        pod = self.client.post(
            f'/api/delivery/stops/{stop_id}/pod/',
            {
                'latitude': '-1.301',
                'longitude': '36.802',
                'notes': 'left at gate',
                'signature': _png('sig.png'),
                'photo': _png('pod.png'),
            },
            format='multipart',
        )
        self.assertEqual(pod.status_code, status.HTTP_200_OK, pod.data)
        self.assertTrue(pod.data['is_complete'])

        done = self.client.post(f'/api/delivery/stops/{stop_id}/complete/')
        self.assertEqual(done.status_code, status.HTTP_200_OK, done.data)
        self.assertEqual(done.data['status'], 'completed')
        order.refresh_from_db()
        self.assertEqual(order.status, FieldOrder.STATUS_DONE)

    def test_illegal_stop_transition(self):
        order = self._ready_order()
        stop = order.delivery_stop
        with self.assertRaises(DeliveryTransitionError):
            transition_stop(stop, DeliveryStop.STATUS_COMPLETED)

    def test_sales_can_open_today_route(self):
        self._auth(self.sales)
        res = self.client.get('/api/delivery/routes/today/')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

    def test_config_and_propose_pin(self):
        order = self._ready_order()
        self._auth(self.driver)
        cfg = self.client.get('/api/delivery/config/')
        self.assertEqual(cfg.status_code, status.HTTP_200_OK)
        self.assertTrue(cfg.data['require_pod_to_complete'])
        self.assertTrue(cfg.data['allow_offline_pod_queue'])
        pin = self.client.post(
            f'/api/delivery/stops/{order.delivery_stop.id}/propose-pin/',
            {'latitude': '-1.4', 'longitude': '36.9', 'note': 'moved'},
            format='json',
        )
        self.assertEqual(pin.status_code, status.HTTP_201_CREATED, pin.data)

    def test_next_open_stop_helper(self):
        order = self._ready_order()
        route = order.delivery_stop.route
        self.assertEqual(next_open_stop(route).id, order.delivery_stop.id)

    def test_collect_invalid_method(self):
        order = self._ready_order()
        stop = order.delivery_stop
        arrive(stop)
        stop.refresh_from_db()
        start_delivery(stop)
        stop.refresh_from_db()
        with self.assertRaises(DeliveryTransitionError):
            collect_money(stop, method='bitcoin')

    def test_str_helpers(self):
        order = self._ready_order()
        stop = order.delivery_stop
        self.assertIn('Stop', str(stop))
        self.assertIn('Route', str(stop.route))
        line = stop.line_results.first()
        self.assertIn('LineResult', str(line))
        save_pod(
            stop,
            signature_image=_png('s.png'),
            photo=_png('ph.png'),
            latitude=Decimal('-1.3'),
            longitude=Decimal('36.8'),
        )
        pod = ProofOfDelivery.objects.get(stop=stop)
        self.assertIn('POD', str(pod))
        self.assertTrue(pod.is_complete)
