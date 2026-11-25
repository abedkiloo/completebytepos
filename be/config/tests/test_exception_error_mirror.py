"""Ensure DRF detail bodies also expose ``error`` for older web toasts."""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from config.exceptions import _mirror_detail_as_error, custom_exception_handler
from sales.models import Customer
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import SuperAdminAPITestCase


def _enable_call_book(enabled=True):
    module, _ = ModuleSettings.objects.get_or_create(
        module_name='customers',
        defaults={'is_enabled': True, 'description': 'customers'},
    )
    module.is_enabled = True
    module.save(update_fields=['is_enabled'])
    feature, _ = ModuleFeature.objects.get_or_create(
        module=module,
        feature_key='call_book',
        defaults={'feature_name': 'Weekly call book', 'is_enabled': enabled},
    )
    feature.is_enabled = enabled
    feature.save(update_fields=['is_enabled'])


class ExceptionErrorMirrorTests(SuperAdminAPITestCase):
    """Unit + integration: permission denials carry an ``error`` string."""

    def test_unit_mirror_copies_detail_to_error(self):
        response = Response({'detail': 'You do not have permission: customers.call_book'})
        _mirror_detail_as_error(response)
        self.assertEqual(
            response.data['error'],
            'You do not have permission: customers.call_book',
        )

    def test_unit_mirror_skips_when_error_already_set(self):
        response = Response({'detail': 'ignored', 'error': 'Keep me'})
        _mirror_detail_as_error(response)
        self.assertEqual(response.data['error'], 'Keep me')

    def test_unit_handler_mirrors_permission_denied(self):
        factory = APIRequestFactory()
        request = factory.post('/api/sales/call-book/1/mark/')
        user = User.objects.create_user('deny_user', password='x')
        force_authenticate(request, user=user)
        response = custom_exception_handler(
            PermissionDenied(detail='Feature off'),
            {'request': request, 'view': None},
        )
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data.get('error'), 'Feature off')

    def test_integration_call_book_feature_off_returns_error_key(self):
        _enable_call_book(True)
        shop = Customer.objects.create(
            name='Mirror Shop',
            phone='0718000999',
            is_active=True,
        )
        _enable_call_book(False)
        blocked = self.client.post(
            f'/api/sales/call-book/{shop.id}/mark/',
            {'outcome': 'unreachable', 'request_summary': ''},
            format='json',
        )
        self.assertEqual(blocked.status_code, 403)
        self.assertTrue(str(blocked.data.get('error') or '').strip())
        self.assertNotIn(shop.phone, str(blocked.data))

    def test_corrected_unreachable_with_empty_notes_saves(self):
        _enable_call_book(True)
        shop = Customer.objects.create(
            name='Unreachable Empty',
            phone='0718000998',
            county='Nairobi',
            sub_county='Starehe',
            ward='Landimawe',
            is_active=True,
        )
        wednesday = date(2026, 11, 25)
        with patch('sales.call_book.nairobi_today', return_value=wednesday):
            marked = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {
                    'outcome': 'unreachable',
                    'request_summary': '',
                    'follow_up_on': '',
                    'follow_up_time': '',
                },
                format='json',
            )
        self.assertEqual(marked.status_code, 200, marked.content)
        self.assertEqual(marked.json().get('outcome'), 'unreachable')
        self.assertFalse(marked.json().get('updated'))
