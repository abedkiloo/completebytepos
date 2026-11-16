"""Weekly call book: Monday–Friday coverage that resets from the call date."""

from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    ROLE_DELIVERY_AGENT,
    ROLE_FIELD_AGENT,
    ensure_permissions,
    sync_default_roles,
)
from sales.call_book import (
    build_call_book,
    call_later_due,
    usable_phone,
    weekday_for_customer,
)
from sales.kenya_admin import DEFAULT_COUNTY, DEFAULT_SUB_COUNTY, DEFAULT_WARD
from sales.models import CallDayPlan, Customer, CustomerCall
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import SalesAPITestCase, SuperAdminAPITestCase

MONDAY = date(2026, 11, 16)
SATURDAY = date(2026, 11, 14)
NEXT_MONDAY = date(2026, 11, 23)


def _enable_call_book(enabled=True):
    """
    Turn the customers.call_book feature on or off.

    Args:
        enabled: Desired toggle. The customers module itself stays on.

    Returns:
        None. Side effect: writes ModuleSettings and ModuleFeature.
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


def _customer(name, phone, **location):
    """
    Create an active customer for the book.

    Args:
        name: Display name, 1–200 characters.
        phone: Raw phone, at most 20 characters.
        **location: Optional county, sub_county, ward.

    Returns:
        Customer: Saved row.
    """
    return Customer.objects.create(
        name=name,
        phone=phone,
        county=location.get('county', DEFAULT_COUNTY),
        sub_county=location.get('sub_county', DEFAULT_SUB_COUNTY),
        ward=location.get('ward', DEFAULT_WARD),
        is_active=True,
    )


class CallBookUnitTests(SuperAdminAPITestCase):
    """Pure rules: phone, weekday, and the Monday reset."""

    def test_usable_phone_needs_nine_to_fifteen_digits(self):
        self.assertFalse(usable_phone(''))
        self.assertFalse(usable_phone('12345'))
        self.assertTrue(usable_phone('0718 515 142'))
        self.assertFalse(usable_phone('1' * 16))

    def test_blank_location_lands_on_the_unlocated_weekday(self):
        customer = _customer('No place', '0718000001', county='', sub_county='', ward='')
        self.assertEqual(weekday_for_customer(customer, [], 0), 0)
        self.assertEqual(weekday_for_customer(customer, [], 3), 3)

    def test_same_ward_keeps_the_same_weekday(self):
        one = _customer('A', '0718000001')
        two = _customer('B', '0718000002')
        self.assertEqual(
            weekday_for_customer(one, [], 0),
            weekday_for_customer(two, [], 0),
        )

    def test_plan_row_overrides_the_hash(self):
        customer = _customer('Planned', '0718000003')
        plan = CallDayPlan(
            weekday=2,
            county=DEFAULT_COUNTY,
            sub_county=DEFAULT_SUB_COUNTY,
            ward=DEFAULT_WARD,
        )
        self.assertEqual(weekday_for_customer(customer, [plan], 0), 2)

    def test_call_later_is_due_only_after_its_time(self):
        moment = timezone.make_aware(datetime(2026, 11, 16, 9, 0))
        before = timezone.make_aware(datetime(2026, 11, 16, 8, 59))
        self.assertFalse(call_later_due('ask_later', moment, before))
        self.assertTrue(call_later_due('ask_later', moment, moment))
        self.assertFalse(call_later_due('called', moment, moment))
        self.assertFalse(call_later_due('ask_later', None, moment))


class CallBookCorrectedTests(SuperAdminAPITestCase):
    """The book the shop described: week, ask later, Saturday, not-called first."""

    def setUp(self):
        super().setUp()
        _enable_call_book(True)

    def test_ask_later_counts_this_week_and_the_note_survives_monday(self):
        shop = _customer('Ask Later Duka', '0718000011')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            marked = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {
                    'outcome': 'ask_later',
                    'request_summary': 'Wants No 10 zippers',
                    'follow_up_time': '16:00',
                },
                format='json',
            )
            self.assertEqual(marked.status_code, status.HTTP_200_OK)
            self.assertIn('16:00', marked.json()['follow_up_at'])
            book = self.client.get('/api/sales/call-book/', {'scope': 'week'}).json()
        row = next(item for item in book['results'] if item['customer_id'] == shop.id)
        self.assertTrue(row['called_this_week'])
        self.assertEqual(row['request_summary'], 'Wants No 10 zippers')
        self.assertEqual(book['summary']['called'], 1)

        with patch('sales.call_book.nairobi_today', return_value=NEXT_MONDAY):
            nxt = self.client.get('/api/sales/call-book/', {'status': 'not_called', 'scope': 'week'}).json()
        again = next(item for item in nxt['results'] if item['customer_id'] == shop.id)
        self.assertFalse(again['called_this_week'])
        self.assertEqual(again['previous_summary'], 'Wants No 10 zippers')
        self.assertEqual(nxt['summary']['not_called'], 1)

    def test_unreachable_and_a_follow_up_count_without_echoing_the_number(self):
        shop = _customer('Silent Duka', '0718000019')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            marked = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {
                    'outcome': 'unreachable',
                    'request_summary': 'Number does not connect',
                    'follow_up_on': '2026-11-20',
                },
                format='json',
            )
            self.assertEqual(marked.status_code, status.HTTP_200_OK, marked.content)
            self.assertEqual(marked.json()['follow_up_on'], '2026-11-20')
            self.assertNotIn(shop.phone, marked.content.decode())
            book = self.client.get('/api/sales/call-book/', {'scope': 'week'}).json()
            late = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'follow_up_on': '2027-06-01', 'request_summary': shop.phone},
                format='json',
            )
        self.assertEqual(late.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(shop.phone, late.json().get('error', ''))
        self.assertEqual(len(book['summary']['days']), 5)
        self.assertEqual(sum(item['called'] for item in book['summary']['days']), 1)

    def test_saturday_can_be_read_and_cannot_be_marked(self):
        shop = _customer('Saturday Duka', '0718000012')
        with patch('sales.call_book.nairobi_today', return_value=SATURDAY):
            marked = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'No'},
                format='json',
            )
            book = self.client.get('/api/sales/call-book/').json()
        self.assertEqual(marked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('0718000012', marked.content.decode())
        self.assertFalse(book['summary']['is_call_day'])
        self.assertEqual(book['summary']['scope'], 'week')
        self.assertEqual(book['summary']['not_called'], 1)
        self.assertEqual(CustomerCall.objects.count(), 0)

    def test_not_called_is_listed_before_called_and_dormant_first(self):
        dormant = _customer('Dormant Duka', '0718000021', buyer_segment='dormant')
        cooling = _customer('Cooling Duka', '0718000022', buyer_segment='at_risk')
        done = _customer('Done Duka', '0718000023')
        Customer.objects.filter(pk=dormant.pk).update(buyer_segment='dormant')
        Customer.objects.filter(pk=cooling.pk).update(buyer_segment='at_risk')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            self.client.post(
                f'/api/sales/call-book/{done.id}/mark/',
                {'outcome': 'no_answer', 'request_summary': ''},
                format='json',
            )
            book = build_call_book(today=MONDAY, scope='week', status='all', page_size=50)
        names = [row['name'] for row in book['results']]
        self.assertLess(names.index('Dormant Duka'), names.index('Cooling Duka'))
        self.assertLess(names.index('Cooling Duka'), names.index('Done Duka'))

    def test_a_reached_call_later_time_is_first_on_load(self):
        waiting = _customer('Alpha Waiting', '0718000061')
        first_due = _customer('Bravo Callback', '0718000062')
        second_due = _customer('Zulu Callback', '0718000063')
        ahead = _customer('Charlie Later', '0718000064')
        before = timezone.make_aware(datetime(2026, 11, 16, 7, 30))
        after = timezone.make_aware(datetime(2026, 11, 16, 10, 0))
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            for shop, clock in (
                (first_due, '08:00'),
                (second_due, '09:00'),
                (ahead, '18:00'),
            ):
                marked = self.client.post(
                    f'/api/sales/call-book/{shop.id}/mark/',
                    {'outcome': 'ask_later', 'request_summary': 'Ring back', 'follow_up_time': clock},
                    format='json',
                )
                self.assertEqual(marked.status_code, status.HTTP_200_OK, marked.content)
            with patch('sales.call_book.timezone.now', return_value=before):
                early = self.client.get('/api/sales/call-book/', {'scope': 'week'}).json()
            with patch('sales.call_book.timezone.now', return_value=after):
                late = self.client.get('/api/sales/call-book/', {'scope': 'week'}).json()

        def names(payload):
            wanted = {waiting.id, first_due.id, second_due.id, ahead.id}
            return [row['name'] for row in payload['results'] if row['customer_id'] in wanted]

        self.assertEqual(names(early)[0], 'Alpha Waiting')
        self.assertFalse(next(row for row in early['results'] if row['name'] == 'Bravo Callback')['call_later_due'])
        self.assertEqual(names(late)[:3], ['Bravo Callback', 'Zulu Callback', 'Alpha Waiting'])
        self.assertGreater(names(late).index('Charlie Later'), names(late).index('Alpha Waiting'))
        self.assertTrue(next(row for row in late['results'] if row['name'] == 'Bravo Callback')['call_later_due'])
        self.assertNotIn('0718000062', str(late['summary']))

    def test_customer_without_a_number_is_cannot_call(self):
        _customer('No Number', '')
        _customer('Has Number', '0718000031')
        book = build_call_book(today=MONDAY, scope='week')
        self.assertEqual(book['summary']['cannot_call'], 1)
        self.assertEqual(book['summary']['callable'], 1)
        self.assertNotIn('No Number', [row['name'] for row in book['results']])


class CallBookModuleTests(SuperAdminAPITestCase):
    """The package toggle gates the API."""

    def test_feature_off_is_403_and_on_opens_the_book(self):
        _enable_call_book(False)
        denied = self.client.get('/api/sales/call-book/')
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('phone', denied.content.decode().lower())
        _enable_call_book(True)
        opened = self.client.get('/api/sales/call-book/')
        self.assertEqual(opened.status_code, status.HTTP_200_OK)
        self.assertIn('not_called', opened.json()['summary'])


class CallBookSecurityTests(SalesAPITestCase):
    """Anonymous denied, sales can mark, only a manager edits the plan."""

    def setUp(self):
        super().setUp()
        _enable_call_book(True)

    def test_anonymous_is_denied(self):
        shop = _customer('Secret Shop', '0718999888')
        client = APIClient()
        response = client.get('/api/sales/call-book/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        mark = client.post(
            f'/api/sales/call-book/{shop.id}/mark/',
            {'outcome': 'called', 'request_summary': '0718999888'},
            format='json',
        )
        self.assertEqual(mark.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('0718999888', mark.content.decode())

    def test_sales_can_mark_and_cannot_edit_the_plan(self):
        shop = _customer('Shared Shop', '0718000041')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            marked = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'Piping'},
                format='json',
            )
            plan = self.client.put(
                '/api/sales/call-book/plan/',
                {'unlocated_weekday': 1, 'hold_minutes': 5, 'rows': []},
                format='json',
            )
        self.assertEqual(marked.status_code, status.HTTP_200_OK)
        self.assertEqual(plan.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('0718000041', plan.content.decode())

    def test_bad_outcome_does_not_echo_the_phone(self):
        shop = _customer('Quiet Shop', '0718000042')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            response = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'wrong', 'request_summary': shop.phone},
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(shop.phone, response.json().get('error', ''))

    def test_a_bad_call_later_time_does_not_echo_the_phone(self):
        shop = _customer('Timed Shop', '0718000044')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            missing = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'ask_later', 'request_summary': shop.phone},
                format='json',
            )
            bad = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'ask_later', 'follow_up_time': shop.phone, 'request_summary': shop.phone},
                format='json',
            )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(shop.phone, missing.content.decode())
        self.assertNotIn(shop.phone, bad.content.decode())

    def test_a_hold_blocks_the_second_caller(self):
        shop = _customer('Held Shop', '0718000043')
        other = User.objects.create_user(username='call_book_other', password='x')
        UserProfile.objects.create(
            user=other,
            role='cashier',
            custom_role=Role.objects.get(name='Sales Personnel'),
            is_active=True,
        )
        other_client = APIClient()
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken.for_user(other)
        other_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            held = self.client.post(f'/api/sales/call-book/{shop.id}/hold/')
            blocked = other_client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'Too late'},
                format='json',
            )
            own = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'Spoke'},
                format='json',
            )
        self.assertEqual(held.status_code, status.HTTP_200_OK)
        self.assertEqual(blocked.status_code, status.HTTP_409_CONFLICT)
        self.assertNotIn(shop.phone, blocked.content.decode())
        self.assertEqual(own.status_code, status.HTTP_200_OK)

    def test_delivery_driver_can_open_the_shared_book(self):
        ensure_permissions()
        sync_default_roles()
        driver = User.objects.create_user(username='call_book_driver', password='x')
        UserProfile.objects.create(
            user=driver,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_DELIVERY_AGENT),
            is_active=True,
        )
        client = APIClient()
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken.for_user(driver)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        opened = client.get('/api/sales/call-book/')
        self.assertEqual(opened.status_code, status.HTTP_200_OK)
        plan = client.put(
            '/api/sales/call-book/plan/',
            {'unlocated_weekday': 0, 'hold_minutes': 5, 'rows': []},
            format='json',
        )
        self.assertEqual(plan.status_code, status.HTTP_403_FORBIDDEN)

    def test_field_sales_cannot_open_the_book_or_see_a_number(self):
        ensure_permissions()
        sync_default_roles()
        shop = _customer('Hidden Shop', '0718000099')
        agent = User.objects.create_user(username='call_book_field', password='x')
        UserProfile.objects.create(
            user=agent,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        client = APIClient()
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken.for_user(agent)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        opened = client.get('/api/sales/call-book/')
        self.assertEqual(opened.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(shop.phone, opened.content.decode())
        marked = client.post(
            f'/api/sales/call-book/{shop.id}/mark/',
            {'outcome': 'called', 'request_summary': shop.phone},
            format='json',
        )
        self.assertEqual(marked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(shop.phone, marked.content.decode())


class CallBookIntegrationTests(SuperAdminAPITestCase):
    """Manager saves a ward onto Wednesday and the book follows it."""

    def setUp(self):
        super().setUp()
        _enable_call_book(True)

    def test_manager_plan_moves_a_ward_to_wednesday(self):
        shop = _customer('Wednesday Shop', '0718000051')
        saved = self.client.put(
            '/api/sales/call-book/plan/',
            {
                'unlocated_weekday': 0,
                'hold_minutes': 8,
                'rows': [{
                    'weekday': 2,
                    'county': DEFAULT_COUNTY,
                    'sub_county': DEFAULT_SUB_COUNTY,
                    'ward': DEFAULT_WARD,
                }],
            },
            format='json',
        )
        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        self.assertEqual(saved.json()['hold_minutes'], 8)
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            today = self.client.get('/api/sales/call-book/', {'scope': 'today'}).json()
            week = self.client.get('/api/sales/call-book/', {'scope': 'week'}).json()
        self.assertEqual(today['results'], [])
        row = week['results'][0]
        self.assertEqual(row['customer_id'], shop.id)
        self.assertEqual(row['weekday'], 2)
        wednesday = MONDAY + timedelta(days=2)
        with patch('sales.call_book.nairobi_today', return_value=wednesday):
            on_day = self.client.get('/api/sales/call-book/', {'scope': 'today'}).json()
        self.assertEqual(on_day['results'][0]['customer_id'], shop.id)


class CallBookStressTests(SuperAdminAPITestCase):
    """A few hundred customers still resolve a stable week."""

    def test_four_hundred_customers_build_under_the_page_cap(self):
        Customer.objects.bulk_create([
            Customer(
                name=f'Shop {index:03d}',
                customer_code=f'CB-{index:06d}',
                phone=f'0718{index:06d}',
                county=DEFAULT_COUNTY,
                sub_county=DEFAULT_SUB_COUNTY,
                ward=DEFAULT_WARD,
                is_active=True,
            )
            for index in range(400)
        ])
        started = timezone.now()
        book = build_call_book(today=MONDAY, scope='week', page=1, page_size=200)
        elapsed = timezone.now() - started
        self.assertEqual(book['summary']['callable'], 400)
        self.assertEqual(book['summary']['not_called'], 400)
        self.assertEqual(len(book['results']), 200)
        self.assertLess(elapsed.total_seconds(), 5)
        first = book['results'][0]['weekday']
        self.assertGreaterEqual(first, 0)
        self.assertLessEqual(first, 4)

    def test_three_hundred_due_callbacks_stay_earliest_first(self):
        shops = Customer.objects.bulk_create([
            Customer(
                name=f'Due {index:03d}',
                customer_code=f'CBD-{index:06d}',
                phone=f'0728{index:06d}',
                county=DEFAULT_COUNTY,
                sub_county=DEFAULT_SUB_COUNTY,
                ward=DEFAULT_WARD,
                is_active=True,
            )
            for index in range(300)
        ])
        CustomerCall.objects.bulk_create([
            CustomerCall(
                customer=shop,
                week_start=MONDAY,
                outcome=CustomerCall.OUTCOME_ASK_LATER,
                request_summary='',
                follow_up_on=MONDAY,
                follow_up_at=timezone.make_aware(datetime(2026, 11, 16, 8 + (index // 60), index % 60)),
            )
            for index, shop in enumerate(shops)
        ])
        clock = timezone.make_aware(datetime(2026, 11, 16, 15, 0))
        with patch('sales.call_book.timezone.now', return_value=clock):
            book = build_call_book(today=MONDAY, scope='week', page_size=200)
        due = [row['follow_up_at'] for row in book['results'] if row['call_later_due']]
        self.assertEqual(len(due), 200)
        self.assertEqual(due, sorted(due))
        self.assertTrue(book['results'][0]['call_later_due'])
        self.assertNotIn('0728', str(book['summary']))
