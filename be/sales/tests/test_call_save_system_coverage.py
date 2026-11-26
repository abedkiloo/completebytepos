"""
Cross-system coverage for call reserve → save after dialing.

Covers unit, integration, module, stress/load, performance, corrected
functionality, security, contract, audit trail, and outlier paths that span
customers + call book + audit — not the call-book module alone.
"""

from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import AuditLog, Role, UserProfile
from accounts.role_definitions import (
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from sales.call_book import (
    _aware,
    _hold_blocks_other,
    _normalize_mark_inputs,
    call_later_due,
    end_of_nairobi_day,
    hold_customer,
    mark_called,
    usable_phone,
)
from sales.kenya_admin import DEFAULT_COUNTY, DEFAULT_SUB_COUNTY, DEFAULT_WARD
from sales.models import CallHold, Customer, CustomerCall
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import SuperAdminAPITestCase

THURSDAY = date(2026, 11, 26)
MONDAY = date(2026, 11, 16)


def _enable_call_book(enabled=True):
    """
    Toggle customers.call_book for coverage runs.

    Args:
        enabled: Desired feature flag.

    Returns:
        None.
    """
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


def _shop(name='Save After Call Shop', phone='0718000930'):
    """
    Create an active callable customer.

    Args:
        name: Display name, 1–200 characters.
        phone: Dialable phone, 9–15 digits.

    Returns:
        Customer.
    """
    return Customer.objects.create(
        name=name,
        phone=phone,
        county=DEFAULT_COUNTY,
        sub_county=DEFAULT_SUB_COUNTY,
        ward=DEFAULT_WARD,
        is_active=True,
    )


class CallSaveUnitOutlierTests(SuperAdminAPITestCase):
    """Unit: helpers and outlier inputs for reserve/save."""

    def test_unit_normalize_and_phone_outliers(self):
        self.assertEqual(_normalize_mark_inputs('called', '  note  '), ('called', 'note'))
        self.assertEqual(_normalize_mark_inputs({'x': 1}, 'n')[0], None)
        self.assertEqual(_normalize_mark_inputs('called', ['bad'])[1], '')
        self.assertTrue(usable_phone('254117056787'))
        self.assertFalse(usable_phone('123'))
        self.assertFalse(usable_phone(''))
        naive = datetime(2026, 11, 26, 12, 0, 0)
        self.assertFalse(timezone.is_naive(_aware(naive)))
        self.assertIsNone(_aware(None))

    def test_unit_expired_or_own_hold_does_not_block(self):
        shop = _shop('Unit Hold', '0718000931')
        past = timezone.now() - timedelta(hours=1)
        hold = CallHold.objects.create(
            customer=shop,
            held_by=self.admin,
            expires_at=past,
        )
        self.assertFalse(
            _hold_blocks_other(hold=hold, now=timezone.now(), user_id=self.admin.id)
        )
        hold.expires_at = end_of_nairobi_day(THURSDAY)
        hold.save(update_fields=['expires_at'])
        other = User.objects.create_user(username='call_unit_other', password='x')
        self.assertTrue(
            _hold_blocks_other(hold=hold, now=timezone.now(), user_id=other.id)
        )
        self.assertFalse(
            _hold_blocks_other(hold=hold, now=timezone.now(), user_id=self.admin.id)
        )

    def test_unit_call_later_due_tolerates_naive_clock(self):
        due = datetime(2026, 11, 26, 8, 0, 0)
        now = datetime(2026, 11, 26, 9, 0, 0)
        self.assertTrue(call_later_due('ask_later', due, now))
        self.assertFalse(call_later_due('called', due, now))


class CallSaveCorrectedIntegrationTests(SuperAdminAPITestCase):
    """Corrected + integration: after dialing, reserve then save must work."""

    def setUp(self):
        super().setUp()
        _enable_call_book(True)

    def test_corrected_after_calling_reserve_then_save_all_outcomes(self):
        """Screenshot path: hold → mark for every outcome, including empty notes."""
        notes = (
            'Called her informed her about the arrival of vecro in two weeks time'
        )
        cases = [
            ('called', notes, '', ''),
            ('no_answer', '', '', ''),
            ('unreachable', '', '', ''),
            ('ask_later', 'Call again', '', '15:30'),
        ]
        with patch('sales.call_book.nairobi_today', return_value=THURSDAY):
            for index, (outcome, summary, follow_on, follow_time) in enumerate(cases):
                shop = _shop(f'Outcome {outcome}', f'071800094{index}')
                held = self.client.post(
                    f'/api/sales/call-book/{shop.id}/hold/',
                    {},
                    format='json',
                )
                saved = self.client.post(
                    f'/api/sales/call-book/{shop.id}/mark/',
                    {
                        'outcome': outcome,
                        'request_summary': summary,
                        'follow_up_on': follow_on,
                        'follow_up_time': follow_time,
                    },
                    format='json',
                )
                self.assertEqual(held.status_code, status.HTTP_200_OK, held.content)
                self.assertEqual(saved.status_code, status.HTTP_200_OK, saved.content)
                self.assertEqual(saved.json()['outcome'], outcome)
                self.assertNotIn(shop.phone, saved.content.decode())
                self.assertEqual(
                    CustomerCall.objects.filter(customer=shop).count(),
                    1,
                )
                # Same user can correct notes after the call without a second row.
                again = self.client.post(
                    f'/api/sales/call-book/{shop.id}/mark/',
                    {
                        'outcome': outcome,
                        'request_summary': (summary or 'follow-up note')[:500],
                        'follow_up_on': follow_on,
                        'follow_up_time': follow_time,
                    },
                    format='json',
                )
                self.assertEqual(again.status_code, status.HTTP_200_OK, again.content)
                self.assertTrue(again.json().get('updated'))
                self.assertEqual(
                    CustomerCall.objects.filter(customer=shop).count(),
                    1,
                )

    def test_integration_audit_row_written_on_save(self):
        shop = _shop('Audit Call Shop', '0718000950')
        with patch('sales.call_book.nairobi_today', return_value=THURSDAY):
            saved = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'Logged for audit'},
                format='json',
            )
        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        self.assertTrue(
            AuditLog.objects.filter(
                action='call_marked',
                object_id=str(shop.id),
            ).exists()
        )
        self.assertFalse(
            AuditLog.objects.filter(changes__icontains=shop.phone).exists()
        )

    def test_contract_error_bodies_never_include_phone(self):
        shop = _shop('Contract Leak', '0718000951')
        with patch('sales.call_book.nairobi_today', return_value=THURSDAY):
            bad = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'not-a-real-outcome', 'request_summary': shop.phone},
                format='json',
            )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(shop.phone, bad.content.decode())
        self.assertIn('error', bad.json())


class CallSaveModuleSecurityTests(SuperAdminAPITestCase):
    """Module gate + security across authn/authz/IDOR/unsafe methods."""

    def setUp(self):
        super().setUp()
        _enable_call_book(True)
        ensure_permissions()
        sync_default_roles()

    def test_module_off_blocks_hold_and_mark_on(self):
        shop = _shop('Module Gate', '0718000952')
        _enable_call_book(False)
        with patch('sales.call_book.nairobi_today', return_value=THURSDAY):
            hold = self.client.post(
                f'/api/sales/call-book/{shop.id}/hold/', {}, format='json',
            )
            mark = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'x'},
                format='json',
            )
        self.assertEqual(hold.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(mark.status_code, status.HTTP_403_FORBIDDEN)
        _enable_call_book(True)
        with patch('sales.call_book.nairobi_today', return_value=THURSDAY):
            ok = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'back on'},
                format='json',
            )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)

    def test_security_unauth_wrong_role_idor_and_unsafe_methods(self):
        shop = _shop('Sec Call', '0718000953')
        anon = APIClient()
        self.assertEqual(
            anon.post(
                f'/api/sales/call-book/{shop.id}/hold/', {}, format='json',
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            anon.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called'},
                format='json',
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        # Authenticated user with an empty role must not mark calls.
        empty_role = Role.objects.create(name='call_save_no_perms')
        outsider = User.objects.create_user(username='call_outsider', password='x')
        UserProfile.objects.create(
            user=outsider,
            role='cashier',
            custom_role=empty_role,
            is_active=True,
        )
        denied = APIClient()
        denied.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(outsider).access_token}'
        )
        with patch('sales.call_book.nairobi_today', return_value=THURSDAY):
            blocked = denied.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': shop.phone},
                format='json',
            )
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(shop.phone, blocked.content.decode())

        # Read-only surface rejects unsafe write methods on the book list.
        self.assertEqual(
            self.client.delete('/api/sales/call-book/').status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.put(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called'},
                format='json',
            ).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

        # Another sales user cannot overwrite today's call (scoped write).
        sales = User.objects.create_user(username='call_sales_sec', password='x')
        UserProfile.objects.create(
            user=sales,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        other = APIClient()
        other.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(sales).access_token}'
        )
        with patch('sales.call_book.nairobi_today', return_value=THURSDAY):
            mine = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'Mine'},
                format='json',
            )
            theirs = other.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': shop.phone},
                format='json',
            )
        self.assertEqual(mine.status_code, status.HTTP_200_OK)
        self.assertEqual(theirs.status_code, status.HTTP_409_CONFLICT)
        self.assertNotIn(shop.phone, theirs.content.decode())


class CallSaveLoadPerformanceTests(SuperAdminAPITestCase):
    """Load/stress and performance bounds for hold+mark under volume."""

    def setUp(self):
        super().setUp()
        _enable_call_book(True)

    def test_stress_load_many_sequential_reserve_save_cycles(self):
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            for index in range(120):
                shop = _shop(f'Load {index}', f'0718001{index:04d}'[-12:])
                code_h, _ = hold_customer(
                    customer_id=shop.id, user=self.admin, today=MONDAY,
                )
                code_m, payload = mark_called(
                    customer_id=shop.id,
                    user=self.admin,
                    outcome='called',
                    request_summary=f'n{index}',
                    today=MONDAY,
                )
                self.assertEqual(code_h, 'ok')
                self.assertEqual(code_m, 'ok')
                self.assertFalse(payload.get('updated'))
        self.assertEqual(CustomerCall.objects.count(), 120)

    def test_performance_mark_stays_within_query_budget(self):
        shop = _shop('Perf Call', '0718000960')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            with CaptureQueriesContext(connection) as ctx:
                code, _ = mark_called(
                    customer_id=shop.id,
                    user=self.admin,
                    outcome='called',
                    request_summary='perf',
                    today=MONDAY,
                )
        self.assertEqual(code, 'ok')
        # Customer lock + hold + prior + existing + insert (+ optional deletes).
        self.assertLessEqual(len(ctx.captured_queries), 25)

    def test_load_many_users_save_distinct_customers(self):
        """Load: many staff each save their own shop without collisions."""
        ensure_permissions()
        sync_default_roles()
        codes = []
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            for index in range(40):
                shop = _shop(f'Conc {index}', f'0718002{index:04d}'[-12:])
                user = User.objects.create_user(
                    username=f'call_conc_{index}', password='x',
                )
                UserProfile.objects.create(
                    user=user,
                    role='cashier',
                    custom_role=Role.objects.get(name=ROLE_SALES),
                    is_active=True,
                )
                codes.append(
                    mark_called(
                        customer_id=shop.id,
                        user=user,
                        outcome='called',
                        request_summary='load',
                        today=MONDAY,
                    )[0]
                )
        self.assertEqual(codes.count('ok'), 40)
        self.assertEqual(CustomerCall.objects.count(), 40)
