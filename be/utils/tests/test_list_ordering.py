from django.contrib.auth.models import User
from rest_framework import status

from employees.models import Employee
from sales.models import Customer, Sale
from settings.models import ModuleSettings
from utils.list_ordering import (
    infer_name_target,
    infer_saved_target,
    mapped_ordering,
)
from utils.tests.api_test_base import ManagerAPITestCase


class InferListOrderingTests(ManagerAPITestCase):
    def test_customer_uses_name_and_created_at(self):
        self.assertEqual(infer_name_target(Customer), 'name')
        self.assertEqual(infer_saved_target(Customer), 'created_at')

    def test_employee_uses_first_and_last_name(self):
        self.assertEqual(infer_name_target(Employee), ('first_name', 'last_name'))
        self.assertEqual(infer_saved_target(Employee), 'created_at')

    def test_sale_uses_customer_name(self):
        self.assertEqual(infer_name_target(Sale), 'customer__name')
        self.assertEqual(infer_saved_target(Sale), 'created_at')

    def test_user_uses_person_name_and_date_joined(self):
        self.assertEqual(infer_name_target(User), ('first_name', 'last_name'))
        self.assertEqual(infer_saved_target(User), 'date_joined')

    def test_mapped_saved_alias(self):
        self.assertEqual(
            mapped_ordering('-saved', aliases={'saved': 'created_at'}),
            ['-created_at'],
        )
        self.assertEqual(
            mapped_ordering('name', aliases={'name': ('first_name', 'last_name')}),
            ['first_name', 'last_name'],
        )


class CustomerListOrderingAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        ModuleSettings.objects.update_or_create(
            module_name='customers',
            defaults={'description': 'customers', 'is_enabled': True},
        )
        Customer.objects.create(name='Zebra Duka', phone='0700000001')
        Customer.objects.create(name='Apple Duka', phone='0700000002')

    def test_rank_customers_by_name(self):
        response = self.client.get('/api/sales/customers/?ordering=name')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in response.data['results']]
        self.assertEqual(names[:2], ['Apple Duka', 'Zebra Duka'])

    def test_rank_customers_by_saved_date(self):
        response = self.client.get('/api/sales/customers/?ordering=-saved')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in response.data['results']]
        # Newest saved first: Apple was created after Zebra.
        self.assertEqual(names[:2], ['Apple Duka', 'Zebra Duka'])
