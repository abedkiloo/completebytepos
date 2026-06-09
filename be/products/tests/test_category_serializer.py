"""Category serializer validation (two-level hierarchy)."""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from products.models import Category
from products.serializers import CategorySerializer


class CategorySerializerValidationTests(TestCase):
    def setUp(self):
        self.parent = Category.objects.create(name='Furniture', is_active=True)
        self.sub = Category.objects.create(
            name='Sofas',
            parent=self.parent,
            is_active=True,
        )

    def test_rejects_subcategory_as_parent(self):
        serializer = CategorySerializer(data={
            'name': 'Invalid',
            'parent': self.sub.id,
            'is_active': True,
        })
        with self.assertRaises(ValidationError) as ctx:
            serializer.is_valid(raise_exception=True)
        self.assertIn('parent', ctx.exception.detail)

    def test_allows_top_level_parent(self):
        serializer = CategorySerializer(data={
            'name': 'Tables',
            'parent': self.parent.id,
            'is_active': True,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_blocks_parent_change_when_children_exist(self):
        other_parent = Category.objects.create(name='Electronics', is_active=True)
        serializer = CategorySerializer(
            instance=self.parent,
            data={'parent': other_parent.id},
            partial=True,
        )
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_rejects_case_insensitive_duplicate_name(self):
        Category.objects.create(name='Beverages', is_active=False)
        serializer = CategorySerializer(
            data={'name': 'beverages', 'is_active': True},
        )
        with self.assertRaises(ValidationError) as ctx:
            serializer.is_valid(raise_exception=True)
        self.assertIn('inactive', str(ctx.exception.detail).lower())

    def test_duplicate_subcategory_under_same_parent_message(self):
        serializer = CategorySerializer(
            data={
                'name': 'sofas',
                'parent': self.parent.id,
                'is_active': True,
            },
        )
        with self.assertRaises(ValidationError) as ctx:
            serializer.is_valid(raise_exception=True)
        detail = str(ctx.exception.detail)
        self.assertIn('Furniture', detail)
        self.assertIn('Select it from the subcategory list', detail)

    def test_strips_whitespace_on_create(self):
        serializer = CategorySerializer(
            data={'name': '  Outdoor   Gear  ', 'is_active': True},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['name'], 'Outdoor Gear')
