"""Fill remaining agents coverage for serializers, views, and variants."""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
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
from agents.models import CustomerSite, FieldOrder, FieldOrderLine
from agents.order_serializers import (
    FieldOrderPlaceSerializer,
    FieldOrderSerializer,
    _line_display_name,
    _variant_label,
    user_is_delivery_driver,
)
from agents.order_services import FieldOrderTransitionError
from agents.services import assert_can_finalize, finalize_site
from products.models import Color, Product, ProductVariant, Size
from sales.models import Customer

from .test_field_orders_extra import _png


class AgentsCoverageGapTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.agent = User.objects.create_user('gap_agent', password='x')
        UserProfile.objects.create(
            user=cls.agent,
            role='agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        cls.driver = User.objects.create_user(
            'gap_drv', password='x', first_name='Ken', last_name='Wheels',
        )
        UserProfile.objects.create(
            user=cls.driver,
            role='delivery',
            custom_role=Role.objects.get(name=ROLE_DELIVERY_AGENT),
            is_active=True,
        )
        cls.customer = Customer.objects.create(name='Gap Cust', phone='0733')
        cls.product = Product.objects.create(
            name='Ballast', sku='BAL-1', price=80, cost=40,
        )
        cls.site = CustomerSite.objects.create(
            customer=cls.customer,
            latitude='-1.2',
            longitude='36.8',
            created_by=cls.agent,
            status=CustomerSite.STATUS_FINALIZED,
        )

    def setUp(self):
        token = RefreshToken.for_user(self.agent)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_list_filters_dates_and_search(self):
        created = self.client.post(
            '/api/visits/field-orders/',
            {
                'site_id': self.site.id,
                'notes': 'Blue gate drop',
                'lines': [{'product_id': self.product.id, 'quantity': '1'}],
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        order_id = created.data['id']
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        listed = self.client.get(
            '/api/visits/field-orders/',
            {
                'status': 'draft',
                'mine': 'yes',
                'date_from': yesterday,
                'date_to': today,
                'search': 'Blue gate',
            },
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        rows = listed.data if isinstance(listed.data, list) else listed.data.get('results', [])
        self.assertTrue(any(row['id'] == order_id for row in rows))
        by_id = self.client.get(
            '/api/visits/field-orders/',
            {'search': str(order_id), 'mine': 'true'},
        )
        self.assertEqual(by_id.status_code, status.HTTP_200_OK)

    def test_place_and_submit_transition_errors(self):
        empty = self.client.post(
            '/api/visits/field-orders/place/',
            {
                'customer_id': self.customer.id,
                'latitude': '-1.29',
                'longitude': '36.82',
                'lines': [],
            },
            format='json',
        )
        self.assertEqual(empty.status_code, status.HTTP_400_BAD_REQUEST)
        missing = self.client.post(
            '/api/visits/field-orders/place/',
            {
                'customer_id': 999999,
                'latitude': '-1.29',
                'longitude': '36.82',
                'lines': [{'product_id': self.product.id, 'quantity': '1'}],
            },
            format='json',
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        with patch(
            'agents.order_serializers.submit_order',
            side_effect=FieldOrderTransitionError({'status': 'blocked'}),
        ):
            blocked = self.client.post(
                '/api/visits/field-orders/place/',
                {
                    'customer_id': self.customer.id,
                    'latitude': '-1.29',
                    'longitude': '36.82',
                    'lines': [{'product_id': self.product.id, 'quantity': '1'}],
                },
                format='json',
            )
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        draft = FieldOrder.objects.create(
            site=self.site, customer=self.customer, created_by=self.agent,
        )
        submit = self.client.post(f'/api/visits/field-orders/{draft.id}/submit/')
        self.assertEqual(submit.status_code, status.HTTP_400_BAD_REQUEST)

    def test_variant_labels_and_line_create(self):
        size = Size.objects.create(name='Large', code='LGAP')
        color = Color.objects.create(name='Grey')
        sized = ProductVariant.objects.create(
            product=self.product, size=size, color=color, sku='BAL-LG', price=90,
        )
        sku_only = ProductVariant.objects.create(
            product=self.product, sku='BAL-DEF', price=70,
        )
        self.assertEqual(_variant_label(None), '')
        self.assertEqual(_variant_label(sized), 'Large / Grey')
        self.assertEqual(_variant_label(sku_only), 'BAL-DEF')
        self.assertEqual(_line_display_name(self.product, None), 'Ballast')
        created = self.client.post(
            '/api/visits/field-orders/',
            {
                'site_id': self.site.id,
                'lines': [
                    {
                        'product_id': self.product.id,
                        'variant_id': sized.id,
                        'quantity': '1',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertIn('Large', created.data['lines'][0]['product_name'])
        bad_variant = self.client.post(
            '/api/visits/field-orders/',
            {
                'site_id': self.site.id,
                'lines': [
                    {
                        'product_id': self.product.id,
                        'variant_id': 999999,
                        'quantity': '1',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(bad_variant.status_code, status.HTTP_400_BAD_REQUEST)

    def test_serializer_media_and_driver_name(self):
        self.assertTrue(user_is_delivery_driver(self.driver))
        order = FieldOrder.objects.create(site=self.site, created_by=self.agent)
        order.site_id = None
        data = FieldOrderSerializer(order).data
        self.assertEqual(data['site_media'], [])
        self.assertIsNone(data['assigned_delivery_agent_name'])
        order = FieldOrder.objects.create(
            site=self.site, customer=self.customer, created_by=self.agent,
        )
        order.assigned_delivery_agent = self.driver
        order.save(update_fields=['assigned_delivery_agent'])
        named = FieldOrderSerializer(order).data['assigned_delivery_agent_name']
        self.assertEqual(named, 'Ken Wheels')

    def test_finalize_requires_photos_when_min_media_set(self):
        site = CustomerSite.objects.create(
            customer=self.customer,
            latitude='-1.2',
            longitude='36.8',
            created_by=self.agent,
        )
        with self.assertRaises(Exception):
            assert_can_finalize(site, min_media=1)
        from agents.models import SiteMedia
        SiteMedia.objects.create(site=site, image=_png('p.png'), created_by=self.agent)
        finalize_site(site, min_media=1)
        with patch('agents.views.MIN_SITE_MEDIA', 1):
            blocked = self.client.delete(
                f'/api/visits/sites/{site.id}/media/{site.media.first().id}/',
            )
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)

    def test_place_default_label(self):
        from django.test import RequestFactory

        request = RequestFactory().post('/')
        request.user = self.agent
        ser = FieldOrderPlaceSerializer(
            data={
                'customer_id': self.customer.id,
                'latitude': '-1.2921',
                'longitude': '36.8219',
                'label': '  ',
                'lines': [{'product_id': self.product.id, 'quantity': '1'}],
            },
            context={'request': request},
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        order = ser.save()
        self.assertIn(self.customer.name, order.site.label)
        self.assertEqual(order.status, FieldOrder.STATUS_SUBMITTED)

    def test_assign_rejects_non_driver(self):
        order = FieldOrder.objects.create(
            site=self.site,
            customer=self.customer,
            status=FieldOrder.STATUS_READY,
            stock_allocated=True,
            created_by=self.agent,
        )
        FieldOrderLine.objects.create(
            order=order, product=self.product, quantity=1, unit_price=80, product_name='Ballast',
        )
        from accounts.role_definitions import ROLE_DISPATCHER

        dispatcher = User.objects.create_user('gap_disp', password='x')
        UserProfile.objects.create(
            user=dispatcher,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_DISPATCHER),
            is_active=True,
        )
        plain = User.objects.create_user('gap_plain', password='x')
        UserProfile.objects.create(user=plain, role='cashier', is_active=True)
        token = RefreshToken.for_user(dispatcher)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        res = self.client.post(
            f'/api/dispatch/field-orders/{order.id}/assign/',
            {'delivery_agent_id': plain.id},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
