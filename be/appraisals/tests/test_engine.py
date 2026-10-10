from django.test import SimpleTestCase

from appraisals.engine import (
    daily_star,
    greeting_copy,
    increment_progress_message,
    is_four_star_month,
    monthly_average,
    monthly_bonus,
    star_tone,
    year_end_result,
)
from appraisals.policy import (
    default_template,
    normalize_template,
    validate_template,
    PolicyError,
    template_at_date,
    template_for_role,
    template_for_track,
)
from appraisals.tips import pick_daily_tips


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
        self.assertEqual(below['status_label'], 'Near target')
        self.assertLess(below['progress'], 1)

    def test_monthly_bonus_bands(self):
        cases = [
            (0, 1, 0),
            (599999, 1, 0),
            (600000, 2, 0),  # stars below 4★ → no cash
            (800000, 3, 0),
            (1000000, 4, 2000),  # base bonus at 4★
            (1250000, 4.5, 6000),
            (1500000, 5, 10000),
            (2000000, 5, 10000),
        ]
        for amount, stars, bonus in cases:
            rating = monthly_bonus(amount, self.template)
            self.assertEqual(rating['stars'], stars, msg=amount)
            self.assertEqual(rating['bonus'], bonus, msg=amount)
        almost = monthly_bonus(1100000, self.template)
        self.assertEqual(almost['bonus'], 2000)
        self.assertEqual(almost['next_bonus'], 6000)
        self.assertEqual(almost['amount_to_next'], 150000)

    def test_bonus_gated_below_four_stars_even_if_band_misconfigured(self):
        custom = normalize_template({
            **self.template,
            'bonus_min_stars': 4,
            'monthly_bonus_bands': [
                {'min': 0, 'stars': 1, 'bonus': 0},
                {'min': 500000, 'stars': 2, 'bonus': 0},
                {'min': 1000000, 'stars': 4, 'bonus': 2000},
            ],
        })
        self.assertEqual(monthly_bonus(500000, custom)['bonus'], 0)
        self.assertEqual(monthly_bonus(1000000, custom)['bonus'], 2000)

    def test_validate_aligns_bonus_min_stars_to_paid_ladder(self):
        """Admins can save a cash ladder from 1★ without manually lowering starts-at."""
        saved = validate_template({
            **self.template,
            'bonus_min_stars': 4,
            'monthly_bonus_bands': [
                {'min': 520000, 'stars': 1, 'bonus': 2000, 'label': 'BASE'},
                {'min': 850000, 'stars': 2, 'bonus': 5000, 'label': 'BUILDER'},
                {'min': 1175000, 'stars': 3, 'bonus': 7500, 'label': 'PRO'},
                {'min': 1500000, 'stars': 4, 'bonus': 10000, 'label': 'CHAMPION'},
            ],
        })
        self.assertEqual(saved['bonus_min_stars'], 1)
        self.assertEqual(monthly_bonus(520000, saved)['bonus'], 2000)

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

        exactly_four = [4.0] * 12
        self.assertTrue(year_end_result(exactly_four, self.template)['qualifies'])
        below_annual = [4.0] * 7 + [3.0] * 5
        missed_avg = year_end_result(below_annual, self.template)
        self.assertEqual(missed_avg['four_star_months'], 7)
        self.assertFalse(missed_avg['qualifies'])

    def test_year_on_year_qualification_is_repeatable(self):
        year_one = year_end_result([4.5] * 8 + [3.0] * 4, self.template)
        self.assertTrue(year_one['qualifies'])
        self.assertEqual(year_one['new_basic'], 18000)
        year_two = year_end_result([4.1] * 12, {
            **self.template,
            'basic_pay': year_one['new_basic'],
        })
        self.assertTrue(year_two['qualifies'])
        self.assertEqual(year_two['new_basic'], 21000)

    def test_role_frameworks_override_targets_and_increments(self):
        template = normalize_template({
            'role_frameworks': {
                'Sales Personnel': {'daily_target': 20000, 'year_end_increment': 3000},
                'Field Sales': {'daily_target': 30000, 'year_end_increment': 4000},
                'Manager': {'daily_target': 40000, 'year_end_increment': 5000},
            },
        })
        field = template_for_role(template, 'Field Sales')
        self.assertEqual(field['daily_target'], 30000)
        self.assertEqual(field['year_end_increment'], 4000)
        self.assertEqual(daily_star(30000, field)['stars'], 4)
        manager = template_for_role(template, 'Manager')
        self.assertEqual(manager['daily_target'], 40000)
        self.assertEqual(daily_star(40000, manager)['stars'], 4)

    def test_historical_template_does_not_rewrite_past_days(self):
        from datetime import date

        old = normalize_template({'daily_target': 20000, 'active_from': '2026-01-01'})
        new = normalize_template({
            'daily_target': 25000,
            'role_daily_targets': {
                'Manager': 35000,
                'Sales Personnel': 25000,
                'Field Sales': 20000,
            },
            'active_from': '2026-07-01',
            'versions': [{
                'id': 1,
                'effective_from': '2026-01-01',
                'effective_until': '2026-07-01',
                'snapshot': {
                    'daily_target': 20000,
                    'role_daily_targets': old['role_daily_targets'],
                    'daily_star_bands': old['daily_star_bands'],
                    'role_frameworks': old['role_frameworks'],
                },
            }],
        })
        january = template_for_role(template_at_date(new, date(2026, 1, 15)), 'Sales Personnel')
        july = template_for_role(template_at_date(new, date(2026, 7, 15)), 'Sales Personnel')
        self.assertEqual(january['daily_target'], 20000)
        self.assertEqual(daily_star(20000, january)['stars'], 4)
        self.assertEqual(july['daily_target'], 25000)
        self.assertEqual(daily_star(20000, july)['stars'], 3)

    def test_increment_progress_message_only_when_supported(self):
        self.assertEqual(
            increment_progress_message(
                {'four_star_months': 7, 'four_star_months_required': 8, 'annual_average': 4.1, 'qualifies': False},
                self.template,
            ),
            'One more 4-Star month to qualify for your KES 3,000 annual increment.',
        )
        self.assertEqual(
            increment_progress_message(
                {'four_star_months': 3, 'four_star_months_required': 8, 'annual_average': 3.2, 'qualifies': False},
                self.template,
            ),
            '',
        )

    def test_invalid_inverted_star_bands_rejected(self):
        with self.assertRaises(PolicyError):
            validate_template({
                'daily_star_bands': [
                    {'min': 0, 'stars': 1},
                    {'min': 30000, 'stars': 4},
                    {'min': 10000, 'stars': 5},
                ],
            })

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
            'bonus_cap': 20000,
        })
        self.assertEqual(daily_star(5000, custom)['stars'], 5)
        self.assertEqual(monthly_bonus(100000, custom)['bonus'], 20000)
        result = year_end_result([5.0] * 6 + [3.0] * 6, custom)
        self.assertTrue(result['qualifies'])
        self.assertEqual(result['new_basic'], 25000)

    def test_manager_daily_target_scales_star_bands(self):
        template = default_template()
        self.assertEqual(template['manager_daily_target'], 35000)
        manager = template_for_track(template, manager=True)
        self.assertEqual(manager['daily_target'], 35000)
        met = daily_star(35000, manager)
        self.assertEqual(met['stars'], 4)
        self.assertEqual(met['label'], 'TARGET MET')
        self.assertEqual(met['amount_to_target'], 0)
        short = daily_star(28000, manager)
        self.assertEqual(short['stars'], 3)
        self.assertEqual(short['amount_to_target'], 7000)
        over = daily_star(42000, manager)
        self.assertEqual(over['stars'], 5)
        self.assertEqual(over['label'], 'OVER TARGET')
        sales = template_for_track(template, manager=False)
        self.assertEqual(sales['daily_target'], 20000)
        self.assertEqual(daily_star(20000, sales)['stars'], 4)

    def test_each_role_has_its_own_daily_target(self):
        template = normalize_template({
            'role_daily_targets': {
                'Manager': 35000,
                'Sales Personnel': 20000,
                'Field Sales': 25000,
            },
        })
        self.assertEqual(template['role_daily_targets']['Field Sales'], 25000)
        field = template_for_role(template, 'Field Sales')
        self.assertEqual(field['daily_target'], 25000)
        self.assertEqual(daily_star(25000, field)['stars'], 4)
        self.assertEqual(daily_star(25000, field)['label'], 'TARGET MET')
        sales = template_for_role(template, 'Sales Personnel')
        self.assertEqual(sales['daily_target'], 20000)
        self.assertEqual(daily_star(20000, sales)['stars'], 4)
        manager = template_for_role(template, 'Manager')
        self.assertEqual(manager['daily_target'], 35000)
        self.assertEqual(daily_star(35000, manager)['stars'], 4)
        self.assertEqual(daily_star(20000, manager)['stars'], 2)

    def test_monthly_bonus_ladder_scales_with_role_daily_target(self):
        template = normalize_template({
            'role_daily_targets': {
                'Manager': 35000,
                'Sales Personnel': 20000,
                'Field Sales': 25000,
            },
        })
        sales = template_for_role(template, 'Sales Personnel')
        self.assertEqual(monthly_bonus(1000000, sales)['bonus'], 2000)
        self.assertEqual(monthly_bonus(999999, sales)['bonus'], 0)

        # Manager target is 1.75× Sales → 4★ bonus threshold becomes 1,750,000.
        manager = template_for_role(template, 'Manager')
        four = next(b for b in manager['monthly_bonus_bands'] if abs(b['stars'] - 4) < 0.01)
        self.assertEqual(four['min'], 1750000)
        self.assertEqual(four['bonus'], 2000)  # cash award unchanged
        self.assertEqual(monthly_bonus(1000000, manager)['bonus'], 0)
        self.assertEqual(monthly_bonus(1750000, manager)['bonus'], 2000)
        self.assertEqual(monthly_bonus(2625000, manager)['bonus'], 10000)

        # Field Sales 1.25× → 4★ at 1,250,000.
        field = template_for_role(template, 'Field Sales')
        field_four = next(b for b in field['monthly_bonus_bands'] if abs(b['stars'] - 4) < 0.01)
        self.assertEqual(field_four['min'], 1250000)
        self.assertEqual(monthly_bonus(1250000, field)['bonus'], 2000)

    def test_framework_own_bands_still_scale_so_four_star_equals_target(self):
        """Preview/runtime: own bands copied from Sales (4★=20k) still scale to role target."""
        template = normalize_template({
            'role_frameworks': {
                'Field Sales': {
                    'daily_target': 25000,
                    'daily_star_bands': default_template()['daily_star_bands'],
                    'monthly_bonus_bands': default_template()['monthly_bonus_bands'],
                },
            },
        })
        field = template_for_role(template, 'Field Sales')
        self.assertEqual(field['daily_target'], 25000)
        four = next(b for b in field['daily_star_bands'] if abs(b['stars'] - 4) < 0.01)
        self.assertEqual(four['min'], 25000)
        self.assertEqual(daily_star(25000, field)['stars'], 4)
        bonus_four = next(b for b in field['monthly_bonus_bands'] if abs(b['stars'] - 4) < 0.01)
        self.assertEqual(bonus_four['min'], 1250000)

    def test_admin_roles_are_not_given_a_daily_target(self):
        template = normalize_template({
            'role_daily_targets': {
                'Super Admin': 20000,
                'Admin': 15000,
                'Administrator': 18000,
                'Manager': 35000,
                'Sales Personnel': 20000,
            },
        })
        self.assertNotIn('Super Admin', template['role_daily_targets'])
        self.assertNotIn('Admin', template['role_daily_targets'])
        self.assertNotIn('Administrator', template['role_daily_targets'])
        self.assertEqual(template_for_role(template, 'Super Admin')['daily_target'], 0)
        self.assertEqual(template_for_role(template, 'Admin')['daily_target'], 0)

    def test_greeting_omits_bonus_and_daily_tips_rotate(self):
        today = daily_star(18500, self.template)
        greeting = greeting_copy(
            today,
            {'official_average': 3.0},
            {'four_star_months': 1, 'four_star_months_required': 8},
        )
        self.assertIn('KES 1,500', greeting['headline'])
        self.assertNotIn('Bonus', greeting['detail'])
        self.assertIn('4-star month', greeting['detail'].lower())
        self.assertNotIn('four-star months this year', greeting['detail'])
        with_increment = greeting_copy(
            today,
            {'official_average': 3.0},
            {'four_star_months': 1, 'four_star_months_required': 8},
            show_increment=True,
        )
        self.assertIn('1/8 four-star months this year', with_increment['detail'])
        from datetime import date
        first = pick_daily_tips(self.template, date(2026, 9, 29))
        second = pick_daily_tips(self.template, date(2026, 9, 30))
        self.assertEqual(len(first['tips']), 5)
        self.assertTrue(first['title'])
        self.assertNotEqual(first['id'], second['id'])
        self.assertNotIn(first['id'], {
            'reach-workshops', 'choose-sofa-stands', 'recliners-meeting',
            'workshop-experience', 'teach-then-sell',
        })
        replaced = pick_daily_tips({
            'daily_tip_packs': [{
                'id': 'reach-workshops',
                'title': 'Old hardware pack',
                'tips': ['A', 'B', 'C', 'D', 'E'],
            }],
        }, date(2026, 1, 1))
        self.assertNotEqual(replaced['id'], 'reach-workshops')
        custom = normalize_template({
            'daily_tip_packs': [{
                'title': 'Custom pack',
                'why': 'Pasted by admin',
                'tips': ['One', 'Two', 'Three', 'Four', 'Five'],
            }],
        })
        picked = pick_daily_tips(custom, date(2026, 1, 1))
        self.assertEqual(picked['title'], 'Custom pack')
        self.assertEqual(picked['tips'][0], 'One')

    def test_invalid_bands_rejected(self):
        with self.assertRaises(PolicyError):
            validate_template({
                'daily_star_bands': [
                    {'min': 0, 'stars': 1},
                    {'min': 0, 'stars': 2},
                ],
            })
