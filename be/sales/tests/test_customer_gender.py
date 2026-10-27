"""Customer gender: required on create, optional for existing blank records."""

from rest_framework import status

from accounts.models import Permission, Role, UserProfile
from django.contrib.auth.models import User
from sales.models import Customer
from utils.tests.api_test_base import SuperAdminAPITestCase


class CustomerGenderAPITests(SuperAdminAPITestCase):
    def test_create_allows_missing_gender_for_older_app_builds(self):
        """Until the gender UI build is released, blank/missing gender is OK."""
        response = self.client.post(
            '/api/sales/customers/',
            {'name': 'No Gender Duka', 'customer_type': 'business'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data.get('gender') or '', '')

    def test_create_accepts_male_or_female(self):
        phones = {'male': '0700111001', 'female': '0700111002'}
        for gender in ('male', 'female'):
            with self.subTest(gender=gender):
                response = self.client.post(
                    '/api/sales/customers/',
                    {
                        'name': f'{gender.title()} Duka',
                        'customer_type': 'business',
                        'gender': gender,
                        'phone': phones[gender],
                    },
                    format='json',
                )
                self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
                self.assertEqual(response.data['gender'], gender)

    def test_create_rejects_invalid_gender(self):
        response = self.client.post(
            '/api/sales/customers/',
            {
                'name': 'Bad Gender Duka',
                'customer_type': 'business',
                'gender': 'other',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn('gender', response.data)

    def test_update_allows_existing_blank_gender(self):
        customer = Customer.objects.create(name='Legacy Duka', gender='')
        response = self.client.patch(
            f'/api/sales/customers/{customer.id}/',
            {'name': 'Legacy Duka Updated'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        customer.refresh_from_db()
        self.assertEqual(customer.gender, '')
        self.assertEqual(customer.name, 'Legacy Duka Updated')

    def test_update_can_set_gender_later(self):
        customer = Customer.objects.create(name='Fill Gender Later', gender='')
        response = self.client.patch(
            f'/api/sales/customers/{customer.id}/',
            {'name': customer.name, 'gender': 'male'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        customer.refresh_from_db()
        self.assertEqual(customer.gender, 'male')


class CustomerAppEditPermissionTests(SuperAdminAPITestCase):
    def test_create_permission_alone_can_edit_customer(self):
        """App field staff with create (no update) may still patch dukas."""
        role = Role.objects.create(
            name='App Create Only',
            is_system_role=False,
            is_active=True,
        )
        role.permissions.set(
            Permission.objects.filter(
                module='customers',
                action__in=['view', 'create'],
            )
        )
        user = User.objects.create_user(username='app_create_only', password='pass')
        UserProfile.objects.create(
            user=user,
            role='cashier',
            custom_role=role,
            is_active=True,
        )
        self.client.force_authenticate(user=user)

        customer = Customer.objects.create(name='Editable From App', phone='0700555011')
        response = self.client.patch(
            f'/api/sales/customers/{customer.id}/',
            {'name': 'Editable From App', 'phone': '0700555099'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        customer.refresh_from_db()
        self.assertTrue(customer.phone.endswith('700555099'), customer.phone)
        self.assertEqual(customer.name, 'Editable From App')
