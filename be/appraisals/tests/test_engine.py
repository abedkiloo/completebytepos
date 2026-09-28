from django.test import SimpleTestCase

from appraisals.engine import (
    daily_star,
    is_four_star_month,
    monthly_average,
    monthly_bonus,
    star_tone,
    year_end_result,
)
from appraisals.policy import default_template, normalize_template, validate_template, PolicyError


class AppraisalEngineTests(SimpleTestCase):
    def setUp(self):
        self.template = default_template()

    def test_daily_star_bands(self):
        cases = [
            (0, 1),
            (9999, 1),
            (10000, 2),
            (15999, 2),
            (16000, 3),
            (19999, 3),
            (20000, 4),
            (23999, 4),
            (24000, 5),
            (80000, 5),
        ]
        for amount, stars in cases:
            rating = daily_star(amount, self.template)
            self.assertEqual(rating['stars'], stars, msg=amount)
        target = daily_star(20000, self.template)
        self.assertEqual(target['label'], 'TARGET MET')
        self.assertEqual(target['tone'], 'emerald')
        over = daily_star(24000, self.template)
        self.assertEqual(over['label'], 'OVER TARGET')
        self.assertEqual(over['tone'], 'gold')
        below = daily_star(18500, self.template)
        self.assertEqual(below['amount_to_target'], 1500)
        self.assertLess(below['progress'], 1)

    def test_monthly_bonus_bands(self):
        cases = [
            (0, 1, 0),
            (599999, 1, 0),
            (600000, 2, 2000),
            (800000, 3, 4000),
            (1000000, 4, 7000),
            (1200000, 4.5, 8500),
            (1500000, 5, 10000),
            (2000000, 5, 10000),
        ]
        for amount, stars, bonus in cases:
            rating = monthly_bonus(amount, self.template)
            self.assertEqual(rating['stars'], stars, msg=amount)
            self.assertEqual(rating['bonus'], bonus, msg=amount)
        almost = monthly_bonus(900000, self.template)
        self.assertEqual(almost['next_bonus'], 7000)
        self.assertEqual(almost['amount_to_next'], 100000)

    def test_monthly_average_and_four_star_month(self):
        avg = monthly_average(104, 26)
        self.assertEqual(avg, 4.0)
        self.assertTrue(is_four_star_month(avg, self.template))
        self.assertFalse(is_four_star_month(3.99, self.template))

    def test_year_end_requires_average_and_eight_months(self):
        eight_fours = [4.5] * 8 + [3.0] * 4
        result = year_end_result(eight_fours, self.template)
        self.assertGreaterEqual(result['annual_average'], 4.0)
        self.assertEqual(result['four_star_months'], 8)
        self.assertTrue(result['qualifies'])
        self.assertEqual(result['new_basic'], 18000)
        self.assertEqual(result['increment_awarded'], 3000)

        seven_fours = [5.0] * 7 + [3.0] * 5
        missed = year_end_result(seven_fours, self.template)
        self.assertGreaterEqual(missed['annual_average'], 4.0)
        self.assertEqual(missed['four_star_months'], 7)
        self.assertFalse(missed['qualifies'])
        self.assertEqual(missed['new_basic'], 15000)
        self.assertIn('consistency', missed['summary'].lower())

        high_avg_few_months = [5.0] * 5 + [3.6] * 7
        still_no = year_end_result(high_avg_few_months, self.template)
        self.assertGreaterEqual(still_no['annual_average'], 4.0)
        self.assertEqual(still_no['four_star_months'], 5)
        self.assertFalse(still_no['qualifies'])

        perfect = [5.0] * 12
        capped = year_end_result(perfect, self.template)
        self.assertTrue(capped['qualifies'])
        self.assertEqual(capped['increment_awarded'], 3000)

        low = [3.0] * 12
        none = year_end_result(low, self.template)
        self.assertFalse(none['qualifies'])
        self.assertIn('stays', none['summary'].lower())

    def test_star_tone_scale(self):
        self.assertEqual(star_tone(1), 'rose')
        self.assertEqual(star_tone(2), 'orange')
        self.assertEqual(star_tone(3), 'amber')
        self.assertEqual(star_tone(4), 'emerald')
        self.assertEqual(star_tone(4.5), 'teal')
        self.assertEqual(star_tone(5), 'gold')

    def test_template_is_configurable(self):
        custom = normalize_template({
            'basic_pay': 20000,
            'year_end_increment': 5000,
            'working_days': 22,
            'four_star_months_required': 6,
            'annual_avg_required': 4.0,
            'daily_star_bands': [
                {'min': 0, 'stars': 1},
                {'min': 5000, 'stars': 5},
            ],
            'monthly_bonus_bands': [
                {'min': 0, 'stars': 1, 'bonus': 0},
                {'min': 100000, 'stars': 5, 'bonus': 20000},
            ],
        })
        self.assertEqual(daily_star(5000, custom)['stars'], 5)
        self.assertEqual(monthly_bonus(100000, custom)['bonus'], 20000)
        result = year_end_result([5.0] * 6 + [3.0] * 6, custom)
        self.assertTrue(result['qualifies'])
        self.assertEqual(result['new_basic'], 25000)

    def test_invalid_bands_rejected(self):
        with self.assertRaises(PolicyError):
            validate_template({
                'daily_star_bands': [
                    {'min': 0, 'stars': 1},
                    {'min': 0, 'stars': 2},
                ],
            })
