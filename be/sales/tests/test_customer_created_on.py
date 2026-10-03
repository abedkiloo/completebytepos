from datetime import timedelta

from django.utils import timezone
from rest_framework import status

from sales.models import Customer
from utils.tests.api_test_base import ManagerAPITestCase


class CustomerCreatedOnFilterTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        self.today_customer = Customer.objects.create(name='Fresh Duka')
        self.old_customer = Customer.objects.create(name='Old Duka')
        Customer.objects.filter(pk=self.old_customer.pk).update(
            created_at=timezone.now() - timedelta(days=3),
        )

    def _ids(self, params):
        resp = self.client.get('/api/sales/customers/', params)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        rows = resp.data.get('results', resp.data)
        return {row['id'] for row in rows}

    def test_created_on_today(self):
        ids = self._ids({'created_on': 'today'})
        self.assertIn(self.today_customer.id, ids)
        self.assertNotIn(self.old_customer.id, ids)

    def test_created_on_specific_date(self):
        day = timezone.localtime(
            Customer.objects.get(pk=self.old_customer.pk).created_at
        ).date()
        ids = self._ids({'created_on': day.isoformat()})
        self.assertEqual(ids & {self.today_customer.id, self.old_customer.id}, {self.old_customer.id})

    def test_created_on_invalid_returns_nothing(self):
        self.assertEqual(self._ids({'created_on': 'not-a-date'}), set())
