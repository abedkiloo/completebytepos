"""Employee expense claims: file, appear in Expenses, manager decides."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    ROLE_DIRECTOR,
    ROLE_MANAGER,
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from expenses.models import Expense
from settings.models import ModuleFeature, ModuleSettings

OTHER_PHONE = '0711555019'


class EmployeeClaimTests(APITestCase):
    """A staff claim shows in Expenses and a manager approves it."""

    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.sales = cls._person('claim_sales', ROLE_SALES, 'cashier')
        cls.other = cls._person('claim_other', ROLE_SALES, 'cashier')
        cls.manager = cls._person('claim_manager', ROLE_MANAGER, 'manager')
        cls.director = cls._person('claim_director', ROLE_DIRECTOR, 'director')
        cls.admin = User.objects.create_superuser(
            'claim_admin', 'claim-admin@example.com', 'admin123',
        )
        ModuleSettings.objects.update_or_create(
            module_name='expenses',
            defaults={'description': 'expenses', 'is_enabled': True},
        )

    @classmethod
    def _person(cls, username, role_name, legacy):
        user = User.objects.create_user(username, password='pass12345')
        UserProfile.objects.create(
            user=user,
            role=legacy,
            custom_role=Role.objects.get(name=role_name),
            is_active=True,
        )
        return user

    def _auth(self, user):
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def _claim(self, user, **extra):
        self._auth(user)
        payload = {
            'amount': '250.00',
            'description': 'Matatu to the market',
            'payment_method': 'cash',
        }
        payload.update(extra)
        return self.client.post('/api/expenses/claims/', payload, format='json')

    def test_bounds_refuse_blank_huge_and_old_dates(self):
        today = timezone.localdate()
        blank = self._claim(self.sales, description='  ', amount='0')
        self.assertEqual(blank.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(OTHER_PHONE, str(blank.data))
        huge = self._claim(self.sales, amount='100000000.00', description='Fare')
        self.assertEqual(huge.status_code, status.HTTP_400_BAD_REQUEST)
        old = self._claim(
            self.sales,
            description='Fare',
            expense_date=(today - timedelta(days=31)).isoformat(),
        )
        self.assertEqual(old.status_code, status.HTTP_400_BAD_REQUEST)
        future = self._claim(
            self.sales,
            description='Fare',
            expense_date=(today + timedelta(days=1)).isoformat(),
        )
        self.assertEqual(future.status_code, status.HTTP_400_BAD_REQUEST)
        long_note = self._claim(self.sales, description='Fare', notes='n' * 301)
        self.assertEqual(long_note.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Expense.objects.filter(is_claim=True).count(), 0)

    def test_employee_claim_appears_in_expenses_and_manager_approval_posts_it(self):
        store = Expense.objects.create(
            amount=Decimal('10.00'),
            description=f'Store cost {OTHER_PHONE}',
            expense_date=timezone.localdate(),
            created_by=self.manager,
            status='pending',
        )
        filed = self._claim(self.sales, amount='250.50', description='Fare')
        self.assertEqual(filed.status_code, status.HTTP_201_CREATED)
        self.assertTrue(filed.data['is_claim'])
        self.assertEqual(filed.data['status'], 'pending')
        self.assertEqual(filed.data['created_by'], self.sales.id)
        self.assertNotIn(OTHER_PHONE, str(filed.data))
        claim_id = filed.data['id']

        self._auth(self.sales)
        own = self.client.get('/api/expenses/')
        self.assertEqual(own.status_code, status.HTTP_200_OK)
        rows = own.data['results'] if isinstance(own.data, dict) else own.data
        ids = [row['id'] for row in rows]
        self.assertIn(claim_id, ids)
        self.assertNotIn(store.id, ids)
        self.assertNotIn(OTHER_PHONE, str(own.data))
        hidden = self.client.get(f'/api/expenses/{store.id}/')
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn(OTHER_PHONE, str(hidden.data))

        self._auth(self.manager)
        listed = self.client.get('/api/expenses/')
        listed_ids = [
            row['id'] for row in (listed.data['results'] if isinstance(listed.data, dict) else listed.data)
        ]
        self.assertIn(claim_id, listed_ids)
        decided = self.client.post(
            f'/api/expenses/{claim_id}/decide-claim/',
            {'decision': 'approved'},
            format='json',
        )
        self.assertEqual(decided.status_code, status.HTTP_200_OK)
        self.assertEqual(decided.data['status'], 'approved')
        self.assertEqual(decided.data['approved_by'], self.manager.id)
        self.assertEqual(Decimal(decided.data['amount']), Decimal('250.50'))
        self.assertTrue(decided.data['is_claim'])
        self.assertNotIn(OTHER_PHONE, str(decided.data))

        self._auth(self.admin)
        blocked = self.client.post(f'/api/expenses/{claim_id}/approve/', {}, format='json')
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(OTHER_PHONE, str(blocked.data))

    def test_employee_cannot_decide_and_a_manager_cannot_decide_their_own(self):
        filed = self._claim(self.sales, description='Lunch')
        claim_id = filed.data['id']
        self._auth(self.sales)
        denied = self.client.post(
            f'/api/expenses/{claim_id}/decide-claim/',
            {'decision': 'approved'},
            format='json',
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(OTHER_PHONE, str(denied.data))
        self.assertEqual(Expense.objects.get(pk=claim_id).status, 'pending')

        own = self._claim(self.manager, description='Manager fare', amount='80.00')
        self._auth(self.manager)
        self_denied = self.client.post(
            f'/api/expenses/{own.data["id"]}/decide-claim/',
            {'decision': 'approved'},
            format='json',
        )
        self.assertEqual(self_denied.status_code, status.HTTP_403_FORBIDDEN)
        self._auth(self.director)
        allowed = self.client.post(
            f'/api/expenses/{own.data["id"]}/decide-claim/',
            {'decision': 'approved'},
            format='json',
        )
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertEqual(allowed.data['status'], 'approved')

    def test_return_then_the_same_claim_can_be_sent_again(self):
        filed = self._claim(self.sales, description='Glue')
        claim_id = filed.data['id']
        self._auth(self.manager)
        missing = self.client.post(
            f'/api/expenses/{claim_id}/decide-claim/',
            {'decision': 'rejected', 'rejection_reason': ''},
            format='json',
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        returned = self.client.post(
            f'/api/expenses/{claim_id}/decide-claim/',
            {'decision': 'rejected', 'rejection_reason': 'Bring the receipt'},
            format='json',
        )
        self.assertEqual(returned.status_code, status.HTTP_200_OK)
        self.assertEqual(returned.data['status'], 'rejected')
        self.assertNotIn(OTHER_PHONE, str(returned.data))
        self._auth(self.sales)
        again = self.client.post(f'/api/expenses/{claim_id}/resubmit/', {}, format='json')
        self.assertEqual(again.status_code, status.HTTP_200_OK)
        self.assertEqual(again.data['status'], 'pending')

    def test_feature_off_and_anonymous_do_not_file(self):
        self.client.credentials()
        anon = self.client.post(
            '/api/expenses/claims/',
            {'amount': '10.00', 'description': 'Fare', 'phone': OTHER_PHONE},
            format='json',
        )
        self.assertEqual(anon.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn(OTHER_PHONE, str(anon.data))

        module = ModuleSettings.objects.get(module_name='expenses')
        feature, _ = ModuleFeature.objects.get_or_create(
            module=module,
            feature_key='employee_claims',
            defaults={'feature_name': 'Employee expense claims', 'is_enabled': False},
        )
        feature.is_enabled = False
        feature.save(update_fields=['is_enabled'])
        try:
            before = Expense.objects.count()
            blocked = self._claim(self.sales, description='Fare', phone=OTHER_PHONE)
            self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)
            self.assertNotIn(OTHER_PHONE, str(blocked.data))
            self.assertEqual(Expense.objects.count(), before)
            put = self.client.put('/api/expenses/claims/', {'amount': '1.00'}, format='json')
            self.assertIn(put.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED))
        finally:
            feature.is_enabled = True
            feature.save(update_fields=['is_enabled'])

    def test_one_hundred_claims_stay_on_the_employee(self):
        self._auth(self.sales)
        for index in range(100):
            response = self.client.post(
                '/api/expenses/claims/',
                {'amount': '1.00', 'description': f'Fare {index}'},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        rows = Expense.objects.filter(is_claim=True, created_by=self.sales, amount=Decimal('1.00'))
        self.assertEqual(rows.count(), 100)
        self.assertEqual(sum(row.amount for row in rows), Decimal('100.00'))
        self.assertTrue(all(row.status == 'pending' for row in rows))
