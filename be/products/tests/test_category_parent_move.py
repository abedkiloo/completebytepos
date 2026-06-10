"""Subcategory parent move rules."""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from products.models import Category, Product
from products.serializers import CategorySerializer


class SubcategoryParentMoveTests(TestCase):
    def setUp(self):
        self.parent_a = Category.objects.create(name='Sofa Stand', is_active=True)
        self.parent_b = Category.objects.create(name='Tables', is_active=True)
        self.sub = Category.objects.create(
            name='SLANDING',
            parent=self.parent_a,
            is_active=True,
        )

    def test_allows_parent_change_when_no_products(self):
        serializer = CategorySerializer(
            instance=self.sub,
            data={'parent': self.parent_b.id},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        updated.refresh_from_db()
        self.assertEqual(updated.parent_id, self.parent_b.id)

    def test_blocks_parent_change_when_product_linked_as_subcategory(self):
        Product.objects.create(
            name='Smooth Stand',
            sku='SKU-1',
            category=self.parent_a,
            subcategory=self.sub,
            selling_price=100,
            is_active=True,
        )
        serializer = CategorySerializer(
            instance=self.sub,
            data={'parent': self.parent_b.id},
            partial=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            serializer.is_valid(raise_exception=True)
        self.assertIn('parent', ctx.exception.detail)
        self.assertIn('products are already linked', str(ctx.exception.detail).lower())

    def test_list_serializer_exposes_can_move_parent(self):
        serializer = CategorySerializer(self.sub)
        self.assertTrue(serializer.data['can_move_parent'])
        Product.objects.create(
            name='Item',
            sku='SKU-2',
            category=self.parent_a,
            subcategory=self.sub,
            selling_price=50,
            is_active=True,
        )
        serializer = CategorySerializer(self.sub)
        self.assertFalse(serializer.data['can_move_parent'])
        self.assertEqual(serializer.data['linked_product_count'], 1)
