"""Unit tests for shared BaseService and QueryService."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.test import TestCase
from django.utils import timezone

from income.models import Income, IncomeCategory
from products.models import Category, Product
from services.base import BaseService, QueryService


class BaseServiceTests(TestCase):
    def setUp(self):
        self.income_category = IncomeCategory.objects.create(name='SvcCat', is_active=True)
        self.service = BaseService(IncomeCategory)

    def test_get_returns_instance(self):
        found = self.service.get(self.income_category.id)
        self.assertEqual(found.pk, self.income_category.pk)

    def test_get_raises_when_missing(self):
        with self.assertRaises(ObjectDoesNotExist):
            self.service.get(999_999)

    def test_get_or_none(self):
        self.assertIsNone(self.service.get_or_none(999_999))
        self.assertEqual(self.service.get_or_none(self.income_category.id).name, 'SvcCat')

    def test_list_with_filters_and_ordering(self):
        IncomeCategory.objects.create(name='B', is_active=True)
        IncomeCategory.objects.create(name='A', is_active=True)
        qs = self.service.list(filters={'is_active': True}, ordering=['name'])
        names = list(qs.values_list('name', flat=True))
        self.assertEqual(names, sorted(names))

    def test_list_without_optional_args(self):
        self.assertGreaterEqual(self.service.list().count(), 1)

    def test_create_update_delete(self):
        user = User.objects.create_user('svc_u', password='x')
        income_svc = BaseService(Income)
        cat = IncomeCategory.objects.create(name='Inc', is_active=True)
        created = income_svc.create(
            {
                'category': cat,
                'description': 'Test',
                'amount': Decimal('1.00'),
                'income_date': timezone.localdate(),
                'status': 'pending',
                'created_by': user,
            }
        )
        self.assertEqual(created.description, 'Test')
        updated = income_svc.update(created, {'description': 'Updated'})
        self.assertEqual(updated.description, 'Updated')
        self.assertTrue(income_svc.delete(updated))

    def test_create_wraps_errors_as_validation_error(self):
        with self.assertRaises(ValidationError):
            self.service.create({'name': None})

    def test_bulk_create_update_delete(self):
        product_svc = BaseService(Product)
        cat = Category.objects.create(name='BulkCat')
        items = [
            {'name': f'Bulk {i}', 'sku': f'BULK-SKU-{i}', 'price': 1, 'category': cat}
            for i in range(3)
        ]
        created = product_svc.bulk_create(items)
        self.assertEqual(len(created), 3)
        for p in created:
            p.price = Decimal('2.00')
        product_svc.bulk_update(created, ['price'])
        self.assertEqual(Product.objects.get(pk=created[0].pk).price, Decimal('2.00'))
        count = product_svc.bulk_delete(created)
        self.assertEqual(count, 3)


class QueryServiceTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='QCat')
        Product.objects.create(name='P1', sku='Q-1', price=10, category=self.cat)
        Product.objects.create(name='P2', sku='Q-2', price=30, category=self.cat)
        self.qs = Product.objects.all()

    def test_filter_by_date_range(self):
        self.assertEqual(QueryService.filter_by_date_range(self.qs, 'created_at').count(), 2)
        only_from = QueryService.filter_by_date_range(
            self.qs, 'created_at', date_from='2000-01-01'
        )
        self.assertEqual(only_from.count(), 2)
        only_to = QueryService.filter_by_date_range(
            self.qs, 'created_at', date_to='2099-12-31'
        )
        self.assertEqual(only_to.count(), 2)

    def test_aggregates(self):
        self.assertEqual(QueryService.aggregate_count(self.qs), 2)
        self.assertEqual(QueryService.aggregate_sum(self.qs, 'price'), 40.0)
        self.assertEqual(QueryService.aggregate_avg(self.qs, 'price'), 20.0)
        empty = Product.objects.filter(sku='missing')
        self.assertEqual(QueryService.aggregate_sum(empty, 'price'), 0.0)
        self.assertEqual(QueryService.aggregate_avg(empty, 'price'), 0.0)
