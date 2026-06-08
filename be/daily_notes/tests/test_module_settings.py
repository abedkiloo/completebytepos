from django.core.cache import cache
from django.test import TestCase

from daily_notes.module_settings import (
    daily_notes_allow_manager_view_all,
    daily_notes_allow_sales_access,
    daily_notes_allow_sales_view_all,
)
from settings.models import ModuleSetting


class DailyNotesModuleSettingsTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_defaults_when_unset(self):
        self.assertTrue(daily_notes_allow_sales_access())
        self.assertTrue(daily_notes_allow_manager_view_all())
        self.assertFalse(daily_notes_allow_sales_view_all())

    def test_reads_stored_values(self):
        ModuleSetting.objects.create(
            module='daily_notes',
            key='allow_sales_view_all',
            label='x',
            description='',
            default_value=False,
            value=True,
        )
        cache.clear()
        self.assertTrue(daily_notes_allow_sales_view_all())
