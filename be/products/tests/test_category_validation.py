"""Tests for category name normalization and duplicate detection."""

from django.test import TestCase

from products.category_validation import (
    DuplicateCategoryInfo,
    find_duplicate_category,
    normalize_category_name,
)
from products.models import Category


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
