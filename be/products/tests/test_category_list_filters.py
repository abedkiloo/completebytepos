"""Category list API filters (parent, exact_name, search)."""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from products.models import Category


class CategoryListFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123',
        )
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

        self.parent = Category.objects.create(name='Sofa Stand', is_active=True)
        self.other_parent = Category.objects.create(name='Tables', is_active=True)
        self.sub = Category.objects.create(
            name='SLANDING',
            parent=self.parent,
            is_active=True,
        )

    def test_parent_filter_returns_only_children(self):
        response = self.client.get(
            '/api/products/categories/',
            {'parent': self.parent.id, 'is_active': 'true'},
        )
        self.assertEqual(response.status_code, 200)
        names = [row['name'] for row in response.data]
        self.assertEqual(names, ['SLANDING'])

    def test_exact_name_finds_subcategory_regardless_of_parent_param(self):
        response = self.client.get(
            '/api/products/categories/',
            {'exact_name': 'slanding', 'is_active': 'true'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'SLANDING')
        self.assertEqual(response.data[0]['parent'], self.parent.id)

    def test_parent_plus_search_narrows_subcategories(self):
        Category.objects.create(name='SLIDING', parent=self.parent, is_active=True)
        response = self.client.get(
            '/api/products/categories/',
            {
                'parent': self.parent.id,
                'is_active': 'true',
                'search': 'land',
            },
        )
        self.assertEqual(response.status_code, 200)
        names = sorted(row['name'] for row in response.data)
        self.assertEqual(names, ['SLANDING'])
