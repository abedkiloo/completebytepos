"""Ward call days: nearby wards share a day, and a plan row still wins."""

from decimal import Decimal

from django.test import SimpleTestCase

from sales.call_book import build_call_book, ward_call_groups, weekday_for_customer
from sales.call_day_algorithm import assign_ward_weekdays, haversine_km
from sales.kenya_admin import DEFAULT_COUNTY, DEFAULT_SUB_COUNTY, DEFAULT_WARD
from sales.models import CallDayPlan, Customer
from sales.tests.test_call_book import MONDAY, _customer
from utils.tests.api_test_base import SuperAdminAPITestCase


def _ward(name, lat, lon, weight=2, sub='Starehe', county='Nairobi'):
    return {
        'county': county,
        'sub_county': sub,
        'ward': name,
        'weight': weight,
        'latitude': lat,
        'longitude': lon,
    }


class CallDayAlgorithmUnitTests(SimpleTestCase):
    """Distance, neighbour days, and the no-pin fallback."""

    def test_same_point_is_zero_kilometres(self):
        self.assertEqual(haversine_km(-1.28, 36.82, -1.28, 36.82), 0)
        self.assertGreater(haversine_km(-1.28, 36.82, -1.29, 36.82), 1)
        self.assertLess(haversine_km(-1.28, 36.82, -1.29, 36.82), 2)

    def test_a_missing_pin_and_a_blank_ward_are_ignored(self):
        assigned = assign_ward_weekdays([
            {
                'county': '',
                'sub_county': 'Starehe',
                'ward': 'Landimawe',
                'weight': 3,
                'latitude': -1.28,
                'longitude': 36.82,
            },
            {
                'county': 'Nairobi',
                'sub_county': 'Starehe',
                'ward': '',
                'weight': 3,
                'latitude': -1.28,
                'longitude': 36.82,
            },
            {
                'county': 'Nairobi',
                'sub_county': 'Starehe',
                'ward': 'Empty',
                'weight': 0,
                'latitude': -1.28,
                'longitude': 36.82,
            },
            {
                'county': 'Nairobi',
                'sub_county': 'Starehe',
                'ward': 'Bad pin',
                'weight': 1,
                'latitude': 'north',
                'longitude': 36.82,
            },
        ])
        self.assertEqual(
            [key for key in assigned if key[2] != 'bad pin'],
            [],
        )
        self.assertIn(assigned[('nairobi', 'starehe', 'bad pin')], range(5))

    def test_neighbouring_wards_share_a_day_and_a_far_ward_does_not(self):
        assigned = assign_ward_weekdays([
            _ward('Landimawe', -1.286, 36.838, weight=5),
            _ward('Nairobi Central', -1.283, 36.842, weight=3),
            _ward('Kangemi', -1.270, 36.700, weight=4, sub='Westlands'),
        ])
        starehe = assigned[('nairobi', 'starehe', 'landimawe')]
        self.assertEqual(assigned[('nairobi', 'starehe', 'nairobi central')], starehe)
        self.assertNotEqual(assigned[('nairobi', 'westlands', 'kangemi')], starehe)
        self.assertLessEqual(max(assigned.values()), 4)

    def test_a_ward_without_a_pin_follows_its_sub_county(self):
        assigned = assign_ward_weekdays([
            _ward('Landimawe', -1.286, 36.838, weight=4),
            _ward('Pangani', None, None, weight=2),
            _ward('Kangemi', -1.270, 36.700, weight=4, sub='Westlands'),
        ])
        self.assertEqual(
            assigned[('nairobi', 'starehe', 'pangani')],
            assigned[('nairobi', 'starehe', 'landimawe')],
        )

    def test_the_same_input_is_stable_across_three_hundred_wards(self):
        groups = [
            _ward(
                f'Ward {index}',
                -1.2 - (index % 20) * 0.05,
                36.7 + (index // 20) * 0.05,
                weight=(index % 7) + 1,
                sub=f'Sub {index // 20}',
                county='Nairobi',
            )
            for index in range(300)
        ]
        first = assign_ward_weekdays(groups)
        second = assign_ward_weekdays(list(reversed(groups)))
        self.assertEqual(first, second)
        self.assertEqual(len(first), 300)
        self.assertTrue(all(0 <= day <= 4 for day in first.values()))
        self.assertTrue(all('0718' not in '|'.join(key) for key in first))


class CallDayAlgorithmCorrectedTests(SuperAdminAPITestCase):
    """The book uses the ward day, and a saved plan still replaces it."""

    def test_two_shops_in_one_ward_stay_together_when_their_pins_differ(self):
        near = _customer('Near shop', '0718000101', ward='Landimawe')
        other = _customer('Other shop', '0718000102', ward='Landimawe')
        near.latitude = Decimal('-1.2860')
        near.longitude = Decimal('36.8380')
        other.latitude = Decimal('-1.3000')
        other.longitude = Decimal('36.8500')
        near.save(update_fields=['latitude', 'longitude'])
        other.save(update_fields=['latitude', 'longitude'])
        groups = ward_call_groups(Customer.objects.filter(id__in=[near.id, other.id]))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['weight'], 2)
        book = build_call_book(today=MONDAY, scope='week', page_size=50)
        days = {row['customer_id']: row['weekday'] for row in book['results']}
        self.assertEqual(days[near.id], days[other.id])

    def test_the_open_book_puts_close_wards_on_one_day(self):
        landimawe = _customer('Landimawe shop', '0718000201', ward='Landimawe')
        central = _customer('Central shop', '0718000202', ward='Nairobi Central')
        kangemi = _customer(
            'Kangemi shop',
            '0718000203',
            ward='Kangemi',
            sub_county='Westlands',
        )
        landimawe.latitude = Decimal('-1.2860')
        landimawe.longitude = Decimal('36.8380')
        central.latitude = Decimal('-1.2830')
        central.longitude = Decimal('36.8420')
        kangemi.latitude = Decimal('-1.2700')
        kangemi.longitude = Decimal('36.7000')
        for customer in (landimawe, central, kangemi):
            customer.save(update_fields=['latitude', 'longitude'])
        book = build_call_book(today=MONDAY, scope='week', page_size=50)
        days = {row['ward']: row['weekday'] for row in book['results']}
        self.assertEqual(days['Landimawe'], days['Nairobi Central'])
        self.assertNotEqual(days['Landimawe'], days['Kangemi'])
        self.assertNotIn('0718000201', str(days))

    def test_a_plan_row_still_beats_the_distance(self):
        customer = _customer('Planned', '0718000301')
        customer.latitude = Decimal('-1.2860')
        customer.longitude = Decimal('36.8380')
        customer.save(update_fields=['latitude', 'longitude'])
        assignments = assign_ward_weekdays(ward_call_groups([customer]))
        plan = CallDayPlan(
            weekday=4,
            county=DEFAULT_COUNTY,
            sub_county=DEFAULT_SUB_COUNTY,
            ward=DEFAULT_WARD,
        )
        self.assertEqual(weekday_for_customer(customer, [plan], 0, assignments), 4)
        self.assertNotEqual(
            4,
            assignments[(
                DEFAULT_COUNTY.lower(),
                DEFAULT_SUB_COUNTY.lower(),
                DEFAULT_WARD.lower(),
            )],
        )
