"""Sub-county call days: one sub-county per turn, and a plan row still wins."""

from django.test import SimpleTestCase

from sales.call_book import build_call_book, sub_county_call_groups, weekday_for_customer
from sales.call_day_algorithm import assign_sub_county_weekdays
from sales.kenya_admin import DEFAULT_COUNTY, DEFAULT_SUB_COUNTY, DEFAULT_WARD
from sales.models import CallDayPlan
from sales.tests.test_call_book import MONDAY, _customer
from utils.tests.api_test_base import SuperAdminAPITestCase


def _sub(name, weight=2, county='Nairobi'):
    return {'county': county, 'sub_county': name, 'weight': weight}


class CallDayAlgorithmUnitTests(SimpleTestCase):
    """Round robin across sub-counties, and rejected weights."""

    def test_blank_weight_and_a_bad_weight_are_skipped(self):
        assigned = assign_sub_county_weekdays([
            {'county': 'Nairobi', 'sub_county': 'Empty', 'weight': 0},
            {'county': 'Nairobi', 'sub_county': 'Bad', 'weight': 'nope'},
            {'county': 'Nairobi', 'sub_county': 'Negative', 'weight': -3},
            _sub('Starehe', weight=4),
        ])
        self.assertEqual(list(assigned), [('nairobi', 'starehe')])
        self.assertEqual(assigned[('nairobi', 'starehe')], 0)

    def test_sub_counties_take_turns_and_the_sixth_returns_to_monday(self):
        names = ['Dagoretti', 'Embakasi', 'Kamukunji', 'Langata', 'Starehe', 'Westlands']
        assigned = assign_sub_county_weekdays([_sub(name, weight=3) for name in names])
        days = [assigned[('nairobi', name.lower())] for name in names]
        self.assertEqual(days, [0, 1, 2, 3, 4, 0])
        self.assertEqual(len(set(days[:5])), 5)

    def test_the_same_input_is_stable_across_three_hundred_sub_counties(self):
        groups = [
            _sub(f'Sub {index:03d}', weight=(index % 7) + 1, county='Nairobi')
            for index in range(300)
        ]
        first = assign_sub_county_weekdays(groups)
        second = assign_sub_county_weekdays(list(reversed(groups)))
        self.assertEqual(first, second)
        self.assertEqual(len(first), 300)
        self.assertTrue(all(0 <= day <= 4 for day in first.values()))
        self.assertNotIn('0718', str(first))


class CallDayAlgorithmCorrectedTests(SuperAdminAPITestCase):
    """The book uses the sub-county day, and a saved plan still replaces it."""

    def test_two_wards_in_one_sub_county_share_a_day(self):
        landimawe = _customer('Landimawe shop', '0718000201', ward='Landimawe')
        central = _customer('Central shop', '0718000202', ward='Nairobi Central')
        kangemi = _customer(
            'Kangemi shop',
            '0718000203',
            ward='Kangemi',
            sub_county='Westlands',
        )
        book = build_call_book(today=MONDAY, scope='week', page_size=50)
        days = {row['ward']: row['weekday'] for row in book['results']}
        self.assertEqual(days['Landimawe'], days['Nairobi Central'])
        self.assertNotEqual(days['Landimawe'], days['Kangemi'])
        self.assertNotIn('0718000201', str(days))
        self.assertEqual(landimawe.sub_county, central.sub_county)

    def test_a_plan_row_still_beats_the_round_robin(self):
        customer = _customer('Planned', '0718000301')
        assignments = assign_sub_county_weekdays(sub_county_call_groups([customer]))
        plan = CallDayPlan(
            weekday=4,
            county=DEFAULT_COUNTY,
            sub_county=DEFAULT_SUB_COUNTY,
            ward=DEFAULT_WARD,
        )
        self.assertEqual(weekday_for_customer(customer, [plan], 0, assignments), 4)
        self.assertNotEqual(
            4,
            assignments[(DEFAULT_COUNTY.lower(), DEFAULT_SUB_COUNTY.lower())],
        )
