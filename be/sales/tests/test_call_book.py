"""Weekly call book: Monday–Friday coverage that resets from the call date."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import AuditLog, Role, UserProfile
from accounts.role_definitions import (
    ROLE_DELIVERY_AGENT,
    ROLE_FIELD_AGENT,
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from sales.call_book import (
    build_call_book,
    call_later_due,
    sub_county_call_groups,
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

    def test_blank_locations_are_spread_across_the_week(self):
        days = set()
        first = None
        for index in range(30):
            customer = _customer(
                f'No place {index}',
                f'0728{index:06d}',
                county='',
                sub_county='',
                ward='',
            )
            day = weekday_for_customer(customer, [], 0)
            self.assertIn(day, range(5))
            self.assertEqual(day, weekday_for_customer(customer, [], 3))
            days.add(day)
            if first is None:
                first = day
        self.assertGreater(len(days), 1)

    def test_the_same_stored_ward_shares_a_day_without_the_official_list(self):
        one = _customer('Belt One', '0728001001', county='Nairobi', sub_county='Roysambu', ward='Custom Belt')
        two = _customer('Belt Two', '0728001002', county='Nairobi', sub_county='Roysambu', ward='Custom Belt')
        other = _customer('Other Belt', '0728001003', county='Nairobi', sub_county='Westlands', ward='Other Belt')
        self.assertEqual(weekday_for_customer(one, [], 0), weekday_for_customer(two, [], 0))
        self.assertEqual(len(sub_county_call_groups([one, two, other])), 2)

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

    def test_the_book_includes_general_customer_information(self):
        shop = Customer.objects.create(
            name='Info Shop',
            phone='0718000077',
            customer_code='INFO-1',
            owner_name='Asha',
            contact_person='Kamau',
            email='shop@example.com',
            address='Stall 4',
            city='Nairobi',
            county=DEFAULT_COUNTY,
            sub_county=DEFAULT_SUB_COUNTY,
            ward=DEFAULT_WARD,
            engagement_tier='buyer',
            typical_goods=['Zippers', '0718999999'],
            last_purchased_at=timezone.make_aware(datetime(2026, 11, 1, 10, 0)),
            tax_id='P051234567X',
            notes='Private note 0718111222',
            is_active=True,
        )
        book = build_call_book(today=MONDAY, scope='week', status='all', page_size=50)
        row = next(item for item in book['results'] if item['customer_id'] == shop.id)
        self.assertEqual(row['owner_name'], 'Asha')
        self.assertEqual(row['contact_person'], 'Kamau')
        self.assertEqual(row['customer_code'], 'INFO-1')
        self.assertEqual(row['address'], 'Stall 4')
        self.assertEqual(row['typical_goods'], ['Zippers', '0718999999'])
        self.assertIn('2026-11-01', row['last_purchased_at'])
        self.assertNotIn('tax_id', row)
        self.assertNotIn('notes', row)
        self.assertNotIn('wallet_balance', row)
        self.assertNotIn('0718111222', str(row['owner_name']) + row['address'])


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

    def test_a_recorded_call_leaves_the_paged_day_list(self):
        shops = Customer.objects.bulk_create([
            Customer(
                name=f'Page Shop {index:02d}',
                customer_code=f'CBP-{index:06d}',
                phone=f'0738{index:06d}',
                county=DEFAULT_COUNTY,
                sub_county=DEFAULT_SUB_COUNTY,
                ward=DEFAULT_WARD,
                is_active=True,
            )
            for index in range(12)
        ])
        done = shops[0]
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            marked = self.client.post(
                f'/api/sales/call-book/{done.id}/mark/',
                {'outcome': 'called', 'request_summary': 'Spoke'},
                format='json',
            )
            self.assertEqual(marked.status_code, status.HTTP_200_OK)
            self.assertNotIn(done.phone, marked.content.decode())
            located = self.client.get(
                '/api/sales/call-book/', {'scope': 'week', 'page_size': 50},
            ).json()
            day = next(
                row['weekday'] for row in located['results'] if row['customer_id'] == done.id
            )
            first = self.client.get('/api/sales/call-book/', {
                'scope': 'week',
                'status': 'not_called',
                'weekday': day,
                'page': 1,
                'page_size': 10,
            })
            second = self.client.get('/api/sales/call-book/', {
                'scope': 'week',
                'status': 'not_called',
                'weekday': day,
                'page': 2,
                'page_size': 10,
            })
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        page_one = first.json()
        page_two = second.json()
        shown = [row['customer_id'] for row in page_one['results'] + page_two['results']]
        self.assertNotIn(done.id, shown)
        self.assertNotIn(done.phone, first.content.decode())
        self.assertEqual(len(page_one['results']), 10)
        self.assertGreaterEqual(page_one['count'], 11)
        self.assertEqual(page_one['page_size'], 10)
        self.assertGreaterEqual(len(page_two['results']), 1)

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
                {
                    'outcome': 'called',
                    'follow_up_on': '2027-06-01',
                    'request_summary': 'Reached them about the handle',
                },
                format='json',
            )
            # Called + invalid optional follow-up still saves notes (date dropped).
            self.assertEqual(late.status_code, status.HTTP_200_OK, late.content)
            self.assertTrue(late.json().get('updated'))
            self.assertEqual(late.json().get('follow_up_on'), '')
            self.assertEqual(
                late.json().get('request_summary'),
                'Reached them about the handle',
            )
            self.assertNotIn(shop.phone, late.content.decode())
        self.assertEqual(len(book['summary']['days']), 5)
        self.assertEqual(sum(item['called'] for item in book['summary']['days']), 1)

    def test_each_day_header_lists_its_sub_counties_once(self):
        _customer('Header A', '0718111001', county='Nairobi', sub_county='Starehe', ward='Landimawe')
        _customer('Header B', '0718111002', county='Nairobi', sub_county=' starehe ', ward='Ngara')
        _customer('Header C', '0718111003', county='Nairobi', sub_county='Westlands', ward='Kangemi')
        _customer('Header D', '0718111004', county='', sub_county='', ward='')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            book = build_call_book(scope='week', status='all', page_size=1000)
        names = []
        for item in book['summary']['days']:
            names.extend(item['sub_counties'])
        self.assertEqual(names.count('Starehe') + names.count('starehe'), 1)
        self.assertIn('Westlands', names)
        self.assertIn('No sub-county', names)
        self.assertNotIn('0718111001', str(book['summary']['days']))
        anonymous = APIClient().get('/api/sales/call-book/')
        self.assertEqual(anonymous.status_code, status.HTTP_401_UNAUTHORIZED)
        crowded = [
            {'weekday': 0, 'called_this_week': False, 'sub_county': f'Area {index:02d}'}
            for index in range(50)
        ]
        from sales.call_book import _day_counts
        wide = _day_counts(crowded)
        self.assertEqual(len(wide[0]['sub_counties']), 40)
        self.assertEqual(wide[1]['sub_counties'], [])

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
        opened = self.client.get('/api/sales/call-book/', {'weekday': 0, 'page': 1, 'page_size': 10})
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

    def test_a_bad_weekday_does_not_echo_the_phone(self):
        shop = _customer('Hidden Day', '0718000777')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            marked = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'Spoke'},
                format='json',
            )
            listed = self.client.get('/api/sales/call-book/', {
                'status': 'not_called', 'weekday': 'nope', 'page_size': 10,
            })
        self.assertEqual(marked.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertNotIn(shop.phone, marked.content.decode())
        self.assertNotIn(shop.phone, listed.content.decode())
        self.assertNotIn(shop.id, [row['customer_id'] for row in listed.json()['results']])

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
        logged = AuditLog.objects.get(action='call_marked', object_id=str(shop.id))
        self.assertEqual(logged.changes['outcome'], 'called')
        self.assertEqual(logged.changes['request_summary'], 'Piping')
        self.assertNotIn('0718000041', str(logged.changes))
        self.assertNotIn('0718000041', logged.object_repr)
        self.assertFalse(AuditLog.objects.filter(action='call_plan_saved').exists())

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

    def test_selecting_the_next_customer_frees_the_previous_one(self):
        first = _customer('First Shop', '0718000044')
        second = _customer('Second Shop', '0718000045')
        other = User.objects.create_user(username='call_book_next', password='x')
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
            self.client.post(f'/api/sales/call-book/{first.id}/hold/')
            moved = self.client.post(f'/api/sales/call-book/{second.id}/hold/')
            still_taken = other_client.post(f'/api/sales/call-book/{second.id}/hold/')
            now_free = other_client.post(f'/api/sales/call-book/{first.id}/hold/')
        self.assertEqual(moved.status_code, status.HTTP_200_OK)
        self.assertEqual(still_taken.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(now_free.status_code, status.HTTP_200_OK)
        body = still_taken.content.decode() + now_free.content.decode()
        self.assertNotIn(first.phone, body)
        self.assertNotIn(second.phone, body)

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


class CallBookCoverageTests(SuperAdminAPITestCase):
    """Branches the week book uses for bad input, plans, and holds."""

    def test_plan_scores_holds_and_rejected_inputs(self):
        from datetime import time
        from types import SimpleNamespace

        from accounts.models import AuditLog, UserProfile
        from sales.call_book import (
            _combine_follow_up,
            _display_name,
            _parse_clock,
            _parse_follow_up,
            hold_customer,
            mark_called,
            plan_payload,
            replace_plan,
            sub_county_call_groups,
            user_may_edit_call_plan,
        )

        blank = _customer('Blank ward', '0728100001', county='Nairobi', sub_county='', ward='')
        starehe = _customer(
            'Starehe shop', '0728100002', county='Nairobi', sub_county='Starehe', ward='Custom Belt',
        )
        groups = sub_county_call_groups([blank, starehe])
        self.assertEqual(len(groups), 2)
        self.assertEqual(sum(group['weight'] for group in groups), 2)

        county_plan = SimpleNamespace(county='Nairobi', sub_county='', ward='', weekday=1)
        sub_plan = SimpleNamespace(county='Nairobi', sub_county='Starehe', ward='', weekday=2)
        self.assertEqual(weekday_for_customer(starehe, [county_plan], 0), 1)
        self.assertEqual(weekday_for_customer(starehe, [sub_plan], 0), 2)

        self.assertFalse(user_may_edit_call_plan(None))
        stranger = User.objects.create_user(username='cover_stranger', password='x')
        self.assertFalse(user_may_edit_call_plan(stranger))
        UserProfile.objects.create(user=stranger, role='manager', is_active=True)
        self.assertTrue(user_may_edit_call_plan(stranger))
        named = User.objects.create_user(
            username='cover_named', password='x', first_name='Ada', last_name='Lovelace',
        )
        self.assertEqual(_display_name(named), 'Ada Lovelace')
        self.assertFalse(call_later_due('ask_later', None, None))

        odd = build_call_book(today=MONDAY, scope='nope', status='nope', page_size=10)
        self.assertEqual(odd['summary']['scope'], 'today')
        called = build_call_book(today=MONDAY, scope='week', status='called', page_size=10)
        self.assertIsInstance(called['results'], list)

        with self.assertRaises(ValueError):
            _parse_follow_up('2026', MONDAY)
        with self.assertRaises(ValueError):
            _parse_follow_up('2026-13-40', MONDAY)
        with self.assertRaises(ValueError):
            _parse_clock('ab:cd')
        with self.assertRaises(ValueError):
            _parse_clock('25:00')
        with patch('sales.call_book.timezone.is_naive', return_value=False):
            same = _combine_follow_up(MONDAY, time(9, 0))
        self.assertEqual(same.hour, 9)

        missing = mark_called(
            customer_id=999999, user=self.admin, outcome='called', request_summary='', today=MONDAY,
        )
        self.assertEqual(missing[0], 'not_found')
        nophone = _customer('No phone cover', '')
        self.assertEqual(
            mark_called(
                customer_id=nophone.id, user=self.admin, outcome='called', request_summary='', today=MONDAY,
            )[0],
            'no_phone',
        )
        shop = _customer('Long note', '0728100004')
        self.assertEqual(
            mark_called(
                customer_id=shop.id, user=self.admin, outcome='called', request_summary='x' * 501, today=MONDAY,
            )[0],
            'too_long',
        )
        self.assertEqual(hold_customer(customer_id=shop.id, user=self.admin, today=SATURDAY)[0], 'weekend')
        self.assertEqual(hold_customer(customer_id=999999, user=self.admin, today=MONDAY)[0], 'not_found')
        self.assertEqual(hold_customer(customer_id=nophone.id, user=self.admin, today=MONDAY)[0], 'no_phone')
        self.assertEqual(hold_customer(customer_id=shop.id, user=self.admin, today=MONDAY)[0], 'ok')
        self.assertEqual(hold_customer(customer_id=shop.id, user=self.admin, today=MONDAY)[0], 'ok')
        shown = build_call_book(today=MONDAY, scope='week', viewer_id=self.admin.id)
        row = next(item for item in shown['results'] if item['customer_id'] == shop.id)
        self.assertTrue(row['hold']['held_by_me'])
        self.assertTrue(row['hold']['day_claim'])

        self.assertEqual(replace_plan(unlocated_weekday='nope', hold_minutes=5, rows=[])[0], 'bad_plan')
        self.assertEqual(replace_plan(unlocated_weekday=9, hold_minutes=5, rows=[])[0], 'bad_plan')
        self.assertEqual(replace_plan(unlocated_weekday=0, hold_minutes=0, rows=[])[0], 'bad_plan')
        self.assertEqual(replace_plan(unlocated_weekday=0, hold_minutes=5, rows='nope')[0], 'bad_plan')
        self.assertEqual(replace_plan(unlocated_weekday=0, hold_minutes=5, rows=['nope'])[0], 'bad_plan')
        self.assertEqual(
            replace_plan(unlocated_weekday=0, hold_minutes=5, rows=[{'weekday': 'x'}])[0],
            'bad_plan',
        )
        self.assertEqual(
            replace_plan(
                unlocated_weekday=0, hold_minutes=5, rows=[{'weekday': 8, 'county': 'Nairobi'}],
            )[0],
            'bad_plan',
        )
        self.assertEqual(
            replace_plan(unlocated_weekday=0, hold_minutes=5, rows=[{'weekday': 0}])[0],
            'bad_plan',
        )
        duplicate = {'weekday': 0, 'county': 'Nairobi', 'sub_county': '', 'ward': ''}
        self.assertEqual(
            replace_plan(unlocated_weekday=0, hold_minutes=5, rows=[duplicate, duplicate])[0],
            'bad_plan',
        )
        self.assertIn('rows', plan_payload())


class CallBookSearchTests(SuperAdminAPITestCase):
    """Find one customer in the call centre the same way the customer list does."""

    def setUp(self):
        super().setUp()
        _enable_call_book(True)
        self.javala = _customer('Javala Alence', '0718555001')
        self.other = _customer('Belt Shop', '0728666002')
        self.javala.customer_code = 'JA-14'
        self.javala.save(update_fields=['customer_code'])

    def test_name_code_and_phone_find_one_customer(self):
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            by_name = build_call_book(
                today=MONDAY, scope='week', status='not_called', weekday=4, search='javala',
            )
            by_code = build_call_book(today=MONDAY, scope='week', search='JA-14')
            by_phone = build_call_book(today=MONDAY, scope='week', search='254718555001')
        self.assertEqual([row['customer_id'] for row in by_name['results']], [self.javala.id])
        self.assertEqual(by_name['summary']['callable'] >= 2, True)
        self.assertEqual([row['name'] for row in by_code['results']], ['Javala Alence'])
        self.assertEqual([row['customer_id'] for row in by_phone['results']], [self.javala.id])
        self.assertNotIn(self.other.phone, str(by_name['results']))
        self.assertNotIn('_match', by_name['results'][0])

    def test_blank_search_keeps_the_day_list(self):
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            book = build_call_book(today=MONDAY, scope='week', status='all', search='   ')
        ids = {row['customer_id'] for row in book['results']}
        self.assertIn(self.javala.id, ids)
        self.assertIn(self.other.id, ids)

    def test_api_search_and_anonymous_refusal(self):
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            found = self.client.get('/api/sales/call-book/', {'search': 'Alence', 'scope': 'week'})
        self.assertEqual(found.status_code, 200, found.data)
        self.assertEqual(found.data['results'][0]['name'], 'Javala Alence')
        self.assertNotIn(self.other.phone, str(found.data['results']))
        anon = APIClient()
        denied = anon.get('/api/sales/call-book/', {'search': 'Javala'})
        self.assertEqual(denied.status_code, 401)
        self.assertNotIn(self.javala.phone, str(denied.data))


class CallBookDayClaimAndPriorityTests(SuperAdminAPITestCase):
    """Same-day exclusive claims, last-week priority, and day caller log."""

    def setUp(self):
        super().setUp()
        _enable_call_book(True)

    def _other_client(self, username='call_day_other'):
        """
        Authenticated sales client for a second staff member.

        Args:
            username: Unique username, 1–40 characters.

        Returns:
            APIClient: JWT-authenticated client for that user.
        """
        other = User.objects.create_user(username=username, password='x')
        UserProfile.objects.create(
            user=other,
            role='cashier',
            custom_role=Role.objects.get(name='Sales Personnel'),
            is_active=True,
        )
        client = APIClient()
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken.for_user(other)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        client.user = other
        return client

    def test_unit_day_claim_expires_at_end_of_nairobi_day(self):
        from sales.call_book import end_of_nairobi_day, hold_customer
        shop = _customer('Day Claim Shop', '0718000901')
        code, payload = hold_customer(customer_id=shop.id, user=self.admin, today=MONDAY)
        self.assertEqual(code, 'ok')
        self.assertTrue(payload['day_claim'])
        self.assertEqual(payload['expires_at'], end_of_nairobi_day(MONDAY).isoformat())

    def test_unit_missed_last_week_sorts_before_called_last_week(self):
        missed = _customer('Missed Priority', '0718000902')
        covered = _customer('Covered Last Week', '0718000903')
        other = User.objects.create_user(username='prior_caller', password='x')
        CustomerCall.objects.create(
            customer=covered,
            called_by=other,
            week_start=MONDAY - timedelta(days=7),
            outcome=CustomerCall.OUTCOME_CALLED,
            request_summary='Last week ok',
        )
        book = build_call_book(today=MONDAY, scope='week', status='not_called', page_size=50)
        ids = [row['customer_id'] for row in book['results']]
        self.assertLess(ids.index(missed.id), ids.index(covered.id))
        missed_row = next(row for row in book['results'] if row['customer_id'] == missed.id)
        covered_row = next(row for row in book['results'] if row['customer_id'] == covered.id)
        self.assertTrue(missed_row['missed_last_week'])
        self.assertFalse(covered_row['missed_last_week'])
        self.assertEqual(covered_row['callers_last_week'][0]['called_by_id'], other.id)

    def test_integration_second_person_cannot_mark_after_first_called_today(self):
        shop = _customer('Once A Day', '0718000904')
        other_client = self._other_client('call_once_day')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            first = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'First'},
                format='json',
            )
            second = other_client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'Second'},
                format='json',
            )
            hold = other_client.post(f'/api/sales/call-book/{shop.id}/hold/')
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(hold.status_code, status.HTTP_409_CONFLICT)
        self.assertNotIn(shop.phone, second.content.decode())
        self.assertNotIn(shop.phone, hold.content.decode())
        self.assertEqual(CustomerCall.objects.filter(customer=shop).count(), 1)

    def test_module_day_log_lists_who_called_without_phones(self):
        shop = _customer('Logged Shop', '0718000905')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            marked = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'no_answer', 'request_summary': 'Tried once'},
                format='json',
            )
            log = self.client.get('/api/sales/call-book/day-log/', {'date': MONDAY.isoformat()})
        self.assertEqual(marked.status_code, status.HTTP_200_OK)
        self.assertEqual(log.status_code, status.HTTP_200_OK)
        body = log.json()
        self.assertEqual(body['day'], MONDAY.isoformat())
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['results'][0]['name'], 'Logged Shop')
        self.assertEqual(body['results'][0]['outcome'], 'no_answer')
        self.assertTrue(body['callers'])
        self.assertNotIn('phone', body['results'][0])
        self.assertNotIn(shop.phone, log.content.decode())

    def test_stress_many_same_day_claims_stay_exclusive(self):
        from sales.call_book import hold_customer, mark_called
        shop = _customer('Stress Claim', '0718000906')
        users = []
        for index in range(25):
            user = User.objects.create_user(username=f'stress_claim_{index}', password='x')
            users.append(user)
        winners = 0
        for user in users:
            code, _ = hold_customer(customer_id=shop.id, user=user, today=MONDAY)
            if code == 'ok':
                winners += 1
            else:
                self.assertEqual(code, 'held')
        self.assertEqual(winners, 1)
        owner = users[0]
        hold_customer(customer_id=shop.id, user=owner, today=MONDAY)
        ok, _ = mark_called(
            customer_id=shop.id,
            user=owner,
            outcome='called',
            request_summary='done',
            today=MONDAY,
        )
        self.assertEqual(ok, 'ok')
        for user in users[1:]:
            code, payload = mark_called(
                customer_id=shop.id,
                user=user,
                outcome='called',
                request_summary='nope',
                today=MONDAY,
            )
            self.assertEqual(code, 'called_today')
            self.assertNotIn('0718000906', str(payload))

    def test_corrected_caller_changed_when_different_people_call_weeks(self):
        shop = _customer('Rotate Callers', '0718000907')
        alice = User.objects.create_user(
            username='alice_caller', password='x', first_name='Alice', last_name='A',
        )
        bob = User.objects.create_user(
            username='bob_caller', password='x', first_name='Bob', last_name='B',
        )
        CustomerCall.objects.create(
            customer=shop,
            called_by=alice,
            week_start=MONDAY - timedelta(days=7),
            outcome=CustomerCall.OUTCOME_CALLED,
            request_summary='Alice last week',
        )
        CustomerCall.objects.create(
            customer=shop,
            called_by=bob,
            week_start=MONDAY,
            outcome=CustomerCall.OUTCOME_CALLED,
            request_summary='Bob this week',
        )
        call = CustomerCall.objects.filter(customer=shop, week_start=MONDAY).first()
        CustomerCall.objects.filter(pk=call.pk).update(
            called_at=timezone.make_aware(datetime(2026, 11, 16, 10, 0)),
        )
        book = build_call_book(today=MONDAY, scope='week', status='all', page_size=50)
        row = next(item for item in book['results'] if item['customer_id'] == shop.id)
        self.assertTrue(row['caller_changed'])
        self.assertIn('Alice', row['callers_last_week'][0]['called_by'])
        self.assertIn('Bob', row['callers_this_week'][0]['called_by'])
        from sales.call_book import build_day_call_log
        day_log = build_day_call_log(day=MONDAY, page_size=50)
        names = [item['name'] for item in day_log['results']]
        self.assertIn('Rotate Callers', names)

    def test_security_day_log_denies_anonymous_and_field_sales(self):
        shop = _customer('Private Day Log', '0718000908')
        CustomerCall.objects.create(
            customer=shop,
            called_by=self.admin,
            week_start=MONDAY,
            outcome=CustomerCall.OUTCOME_CALLED,
            request_summary='Secret',
        )
        anon = APIClient()
        denied = anon.get('/api/sales/call-book/day-log/', {'date': MONDAY.isoformat()})
        self.assertEqual(denied.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn(shop.phone, denied.content.decode())
        ensure_permissions()
        sync_default_roles()
        agent = User.objects.create_user(username='day_log_field', password='x')
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
        blocked = client.get('/api/sales/call-book/day-log/', {'date': MONDAY.isoformat()})
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(shop.phone, blocked.content.decode())
        self.assertNotIn('Secret', blocked.content.decode())


class CallBookNoteUpdateTests(SuperAdminAPITestCase):
    """Corrected: staff can update this week's call notes without a second row."""

    def setUp(self):
        super().setUp()
        _enable_call_book(True)

    def test_unit_mark_called_updates_own_week_note(self):
        from sales.call_book import mark_called
        from sales.models import CustomerCall

        shop = _customer('Note Update Duka', '0718000910')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            first, payload = mark_called(
                customer_id=shop.id,
                user=self.admin,
                outcome='called',
                request_summary='First note',
                today=MONDAY,
            )
            second, updated = mark_called(
                customer_id=shop.id,
                user=self.admin,
                outcome='ask_later',
                request_summary='Corrected note',
                follow_up_time='14:30',
                today=MONDAY,
            )
        self.assertEqual(first, 'ok')
        self.assertFalse(payload.get('updated'))
        self.assertEqual(second, 'ok')
        self.assertTrue(updated.get('updated'))
        self.assertEqual(updated['request_summary'], 'Corrected note')
        self.assertEqual(CustomerCall.objects.filter(customer=shop).count(), 1)
        row = CustomerCall.objects.get(customer=shop)
        self.assertEqual(row.outcome, 'ask_later')
        self.assertEqual(row.request_summary, 'Corrected note')

    def test_integration_http_update_note_and_audit(self):
        shop = _customer('HTTP Note Shop', '0718000911')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            created = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'Draft note'},
                format='json',
            )
            revised = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'Final note for zippers'},
                format='json',
            )
            book = self.client.get(
                '/api/sales/call-book/',
                {'scope': 'week', 'status': 'all', 'search': 'HTTP Note'},
            ).json()
        self.assertEqual(created.status_code, status.HTTP_200_OK)
        self.assertFalse(created.json().get('updated'))
        self.assertEqual(revised.status_code, status.HTTP_200_OK)
        self.assertTrue(revised.json().get('updated'))
        self.assertEqual(revised.json()['request_summary'], 'Final note for zippers')
        row = next(item for item in book['results'] if item['customer_id'] == shop.id)
        self.assertEqual(row['request_summary'], 'Final note for zippers')
        self.assertEqual(CustomerCall.objects.filter(customer=shop).count(), 1)
        self.assertTrue(
            AuditLog.objects.filter(
                action='call_updated',
                object_id=str(shop.id),
            ).exists()
        )
        self.assertNotIn(shop.phone, revised.content.decode())

    def test_security_other_user_cannot_overwrite_todays_call(self):
        shop = _customer('Owned Note', '0718000912')
        other = User.objects.create_user(username='note_other', password='x')
        ensure_permissions()
        sync_default_roles()
        UserProfile.objects.create(
            user=other,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        other_client = APIClient()
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken.for_user(other)
        other_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            mine = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'Mine'},
                format='json',
            )
            theirs = other_client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': shop.phone},
                format='json',
            )
        self.assertEqual(mine.status_code, status.HTTP_200_OK)
        self.assertEqual(theirs.status_code, status.HTTP_409_CONFLICT)
        self.assertNotIn(shop.phone, theirs.content.decode())
        self.assertEqual(
            CustomerCall.objects.get(customer=shop).request_summary,
            'Mine',
        )

    def test_security_unauthenticated_update_denied(self):
        shop = _customer('Anon Note', '0718000913')
        anon = APIClient()
        denied = anon.post(
            f'/api/sales/call-book/{shop.id}/mark/',
            {'outcome': 'called', 'request_summary': 'leak'},
            format='json',
        )
        self.assertEqual(denied.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('leak', denied.content.decode())

    def test_module_feature_off_blocks_note_update(self):
        shop = _customer('Feature Off Note', '0718000914')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'Keep'},
                format='json',
            )
        _enable_call_book(False)
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            blocked = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {'outcome': 'called', 'request_summary': 'Nope'},
                format='json',
            )
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)

    def test_stress_repeated_note_updates_stay_one_row(self):
        from sales.call_book import mark_called

        shop = _customer('Stress Note', '0718000915')
        with patch('sales.call_book.nairobi_today', return_value=MONDAY):
            mark_called(
                customer_id=shop.id,
                user=self.admin,
                outcome='called',
                request_summary='n0',
                today=MONDAY,
            )
            for index in range(120):
                code, payload = mark_called(
                    customer_id=shop.id,
                    user=self.admin,
                    outcome='called',
                    request_summary=f'n{index}',
                    today=MONDAY,
                )
                self.assertEqual(code, 'ok')
                self.assertTrue(payload['updated'])
        self.assertEqual(CustomerCall.objects.filter(customer=shop).count(), 1)
        self.assertEqual(
            CustomerCall.objects.get(customer=shop).request_summary,
            'n119',
        )

    def test_corrected_called_with_follow_up_date_like_screenshot(self):
        """Screenshot: Called + notes + follow-up tomorrow must save on a weekday."""
        from sales.call_book import mark_called

        wednesday = date(2026, 11, 25)
        shop = _customer(
            'Handle Shop',
            '0718000916',
            county='Nairobi',
            sub_county='Starehe',
            ward='Landimawe',
        )
        with patch('sales.call_book.nairobi_today', return_value=wednesday):
            code, payload = mark_called(
                customer_id=shop.id,
                user=self.admin,
                outcome='called',
                request_summary=(
                    'Called him updated him about the handle, he will visiting '
                    'the shop to see them physically'
                ),
                follow_up_on='2026-11-26',
                today=wednesday,
            )
            http = self.client.post(
                f'/api/sales/call-book/{shop.id}/mark/',
                {
                    'outcome': 'called',
                    'request_summary': 'Updated handle note',
                    'follow_up_on': '2026-11-26',
                },
                format='json',
            )
        self.assertEqual(code, 'ok')
        self.assertFalse(payload.get('updated'))
        self.assertEqual(payload.get('follow_up_on'), '2026-11-26')
        self.assertEqual(http.status_code, status.HTTP_200_OK, http.content)
        self.assertTrue(http.json().get('updated'))
        self.assertNotIn(shop.phone, http.content.decode())
