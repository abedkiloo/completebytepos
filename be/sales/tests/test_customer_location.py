"""Customer location ping from the mobile app + welcome SMS."""

from decimal import Decimal
from unittest.mock import patch

from rest_framework import status

from agents.models import CustomerSite
from messaging.models import MessageOutbox
from sales.models import Customer
from utils.tests.api_test_base import SuperAdminAPITestCase


class CustomerLocationPingTests(SuperAdminAPITestCase):
    def test_create_without_location_still_allowed_for_desk(self):
        """Web/desk create must not force GPS — location is an app field flow."""
        response = self.client.post(
            '/api/sales/customers/',
            {'name': 'Desk Duka', 'customer_type': 'business', 'phone': '0712345678'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIsNone(response.data.get('latitude'))
        self.assertEqual(response.data.get('county'), 'Nairobi')

    @patch('messaging.customer_notify.dispatch_outbox')
    def test_create_with_location_saves_default_site(self, _dispatch):
        response = self.client.post(
            '/api/sales/customers/',
            {
                'name': 'Field Duka',
                'customer_type': 'business',
                'phone': '0712345678',
                'latitude': -1.2921,
                'longitude': 36.8219,
                'location_accuracy': 12.5,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Decimal(str(response.data['latitude'])), Decimal('-1.2921000'))
        customer = Customer.objects.get(id=response.data['id'])
        site = CustomerSite.objects.get(customer=customer, is_default=True)
        self.assertEqual(site.latitude, customer.latitude)
        self.assertEqual(site.longitude, customer.longitude)
        self.assertEqual(site.status, CustomerSite.STATUS_FINALIZED)

    @patch('messaging.customer_notify.dispatch_outbox')
    def test_create_accepts_high_precision_gps_doubles(self, _dispatch):
        """Phone GPS often sends >7 decimal places; must not 400 on max_digits."""
        response = self.client.post(
            '/api/sales/customers/',
            {
                'name': 'Precise GPS Duka',
                'customer_type': 'business',
                'phone': '0722200022',
                'latitude': -1.262148765432109,
                'longitude': 36.65973456789012,
                'location_accuracy': 14.0,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            Decimal(str(response.data['latitude'])),
            Decimal('-1.2621488'),
        )
        self.assertEqual(
            Decimal(str(response.data['longitude'])),
            Decimal('36.6597346'),
        )

    @patch('messaging.customer_notify.dispatch_outbox')
    def test_create_queues_welcome_sms_when_phone_set(self, _dispatch):
        response = self.client.post(
            '/api/sales/customers/',
            {
                'name': 'Wambua Hardware',
                'customer_type': 'business',
                'phone': '0712345678',
                'latitude': -1.29,
                'longitude': 36.82,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        msg = MessageOutbox.objects.filter(
            customer_id=response.data['id'],
            template_key=MessageOutbox.TEMPLATE_CUSTOMER_WELCOME,
        ).first()
        self.assertIsNotNone(msg)
        self.assertLessEqual(len(msg.body), 300)
        self.assertIn('Omuwenga', msg.body)
        self.assertIn('price', msg.body.lower())
