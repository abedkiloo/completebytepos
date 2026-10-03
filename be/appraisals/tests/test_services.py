from datetime import date, datetime
from decimal import Decimal

from django.utils import timezone

from appraisals.policy import default_template, save_template
from appraisals.services import staff_snapshot
from sales.models import Sale
from settings.models import ModuleSettings
from utils.tests.api_test_base import SalesAPITestCase


def _enable_appraisals():
    ModuleSettings.objects.update_or_create(
        module_name='appraisals',
        defaults={'is_enabled': True, 'description': 'Staff appraisals'},
    )


class AppraisalServiceTests(SalesAPITestCase):
    def setUp(self):
        super().setUp()
        _enable_appraisals()
        save_template(default_template())

    def test_incomplete_first_cycle_records_days_but_is_not_four_star_eligible(self):
        today = date(2026, 10, 20)
        self.sales_user.date_joined = timezone.make_aware(datetime(2026, 10, 15, 9, 0))
        self.sales_user.save(update_fields=['date_joined'])
        Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('50000'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('50000'),
            amount_paid=Decimal('50000'),
            cashier=self.sales_user,
            served_by=self.sales_user,
            occurred_at=timezone.make_aware(datetime(2026, 10, 20, 12, 0)),
        )
        snap = staff_snapshot(self.sales_user, year=2026, today=today)
        self.assertFalse(snap['month']['four_star_month_eligible'])
        self.assertFalse(snap['month']['four_star_month'])
        self.assertEqual(snap['today']['stars'], 5)
        dates = [row['date'] for row in snap['month']['days']]
        self.assertTrue(all(day >= '2026-10-15' for day in dates))
        self.assertIn('2026-10-20', dates)
        self.assertNotIn('2026-10-01', dates)
