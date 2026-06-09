"""Tests for category name normalization and duplicate detection."""

from django.test import TestCase

from products.category_validation import (
    DuplicateCategoryInfo,
    category_linked_product_count,
    find_duplicate_category,
    normalize_category_name,
    subcategory_parent_movable,
)
from products.models import Category, Product


class CategoryValidationTests(TestCase):
    def test_normalize_collapses_whitespace(self):
        self.assertEqual(normalize_category_name('  Foo   Bar  '), 'Foo Bar')

    def test_find_duplicate_case_insensitive(self):
        Category.objects.create(name='Snacks', is_active=True)
        dup = find_duplicate_category('snacks')
        self.assertIsNotNone(dup)
        self.assertEqual(dup.name, 'Snacks')

    def test_duplicate_message_mentions_inactive(self):
        cat = Category.objects.create(name='Hidden', is_active=False)
        msg = DuplicateCategoryInfo(cat).user_message('hidden')
        self.assertIn('inactive', msg.lower())

    def test_duplicate_message_same_parent_subcategory(self):
        parent = Category.objects.create(name='Sofa Stand', is_active=True)
        existing = Category.objects.create(
            name='SLANDING',
            parent=parent,
            is_active=True,
        )
        msg = DuplicateCategoryInfo(existing).user_message(
            'slanding',
            attempted_parent_id=parent.id,
        )
        self.assertIn('Sofa Stand', msg)
        self.assertIn('Select it from the subcategory list', msg)

    def test_duplicate_message_different_parent_subcategory(self):
        parent_a = Category.objects.create(name='Sofa Stand', is_active=True)
        parent_b = Category.objects.create(name='Tables', is_active=True)
        existing = Category.objects.create(
            name='SLANDING',
            parent=parent_a,
            is_active=True,
        )
        msg = DuplicateCategoryInfo(existing).user_message(
            'slanding',
            attempted_parent_id=parent_b.id,
        )
        self.assertIn('Sofa Stand', msg)
        self.assertIn('unique across the store', msg)

    def test_linked_product_count_includes_subcategory_usage(self):
        parent = Category.objects.create(name='Parent', is_active=True)
        sub = Category.objects.create(name='Child', parent=parent, is_active=True)
        Product.objects.create(
            name='Item',
            sku='L-1',
            category=parent,
            subcategory=sub,
            selling_price=10,
            is_active=True,
        )
        self.assertEqual(category_linked_product_count(sub), 1)
        self.assertFalse(subcategory_parent_movable(sub))

    def test_duplicate_message_top_level_blocks_subcategory(self):
        Category.objects.create(name='SLANDING', is_active=True)
        msg = DuplicateCategoryInfo(
            find_duplicate_category('slanding')
        ).user_message('slanding', attempted_parent_id=99)
        self.assertIn('top-level category', msg.lower())
