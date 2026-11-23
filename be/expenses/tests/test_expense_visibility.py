"""Who sees which rows on the expenses list."""

from decimal import Decimal

from django.contrib.auth.models import AnonymousUser, User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import (
    ROLE_DIRECTOR,
    ROLE_MANAGER,
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from expenses.models import Expense
from expenses.views import expense_list_scope
from settings.models import ModuleFeature, ModuleSettings

HIDDEN_PHONE = '0711666009'


class ExpenseListScopeTests(APITestCase):
    """Admin sees the book. A manager sees claims. A sales person sees their own."""

    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.sales = cls._person('vis_sales', ROLE_SALES, 'cashier')
        cls.manager = cls._person('vis_manager', ROLE_MANAGER, 'manager')
        cls.director = cls._person('vis_director', ROLE_DIRECTOR, 'director')
        cls.admin = User.objects.create_superuser(
            'vis_admin', 'vis-admin@example.com', 'admin123',
        )
        ModuleSettings.objects.update_or_create(
            module_name='expenses',
            defaults={'description': 'expenses', 'is_enabled': True},
        )
        today = timezone.localdate()
        cls.shop = Expense.objects.create(
            description='Shop power',
            amount=Decimal('500.00'),
            expense_date=today,
            status='approved',
            created_by=cls.admin,
            notes=HIDDEN_PHONE,
        )
        cls.claim = Expense.objects.create(
            description='Sales fare',
            amount=Decimal('40.00'),
            expense_date=today,
            status='approved',
            is_claim=True,
            created_by=cls.sales,
        )
        cls.manager_row = Expense.objects.create(
            description='Manager lunch',
            amount=Decimal('25.00'),
            expense_date=today,
            status='pending',
            created_by=cls.manager,
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

    def _descriptions(self, user):
        self._auth(user)
        response = self.client.get('/api/expenses/?page_size=50')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        rows = response.data.get('results', response.data)
        return {row['description'] for row in rows}

    def test_scope_names_for_each_job(self):
        self.assertEqual(expense_list_scope(None), 'own')
        self.assertEqual(expense_list_scope(AnonymousUser()), 'own')
        self.assertEqual(expense_list_scope(self.sales), 'own')
        self.assertEqual(expense_list_scope(self.manager), 'claims')
        self.assertEqual(expense_list_scope(self.director), 'claims')
        self.assertEqual(expense_list_scope(self.admin), 'all')

    def test_sales_manager_and_admin_see_different_rows(self):
        sales_rows = self._descriptions(self.sales)
        self.assertEqual(sales_rows, {'Sales fare'})
        self._auth(self.sales)
        sales_body = self.client.get('/api/expenses/?page_size=50')
        self.assertNotIn(HIDDEN_PHONE, str(sales_body.data))
        manager_rows = self._descriptions(self.manager)
        self.assertEqual(manager_rows, {'Sales fare', 'Manager lunch'})
        self._auth(self.manager)
        manager_body = self.client.get('/api/expenses/?page_size=50')
        self.assertNotIn(HIDDEN_PHONE, str(manager_body.data))
        admin_rows = self._descriptions(self.admin)
        self.assertEqual(admin_rows, {'Shop power', 'Sales fare', 'Manager lunch'})

    def test_view_permission_does_not_open_the_shop_book(self):
        """A non-admin with expenses.view still sees only rows they raised."""
        book = Role.objects.create(name='Bookkeeper', is_system_role=False, is_active=True)
        book.permissions.add(Permission.objects.get(module='expenses', action='view'))
        keeper = User.objects.create_user('vis_book', password='pass12345')
        UserProfile.objects.create(
            user=keeper, role='cashier', custom_role=book, is_active=True,
        )
        self.assertTrue(keeper.profile.has_permission('expenses', 'view'))
        self.assertEqual(self._descriptions(keeper), set())

    def test_approved_claim_stays_visible_to_the_manager(self):
        self.claim.status = 'approved'
        self.claim.save(update_fields=['status'])
        self.assertIn('Sales fare', self._descriptions(self.manager))
        self.assertNotIn('Shop power', self._descriptions(self.manager))

    def test_manager_totals_skip_the_shop_book(self):
        self._auth(self.manager)
        response = self.client.get('/api/expenses/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['expense_count'], 2)
        self.assertEqual(response.data['total_amount'], 65.0)
        self.assertNotIn(HIDDEN_PHONE, str(response.data))
        self.assertNotIn('500', str(response.data['total_expenses']))

    def test_sales_cannot_open_someone_elses_expense(self):
        self._auth(self.sales)
        hidden = self.client.get(f'/api/expenses/{self.shop.id}/')
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn(HIDDEN_PHONE, str(hidden.data))
        own = self.client.get(f'/api/expenses/{self.claim.id}/')
        self.assertEqual(own.status_code, status.HTTP_200_OK)

    def test_anonymous_cannot_list(self):
        self.client.credentials()
        response = self.client.get('/api/expenses/', {'phone': HIDDEN_PHONE})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn(HIDDEN_PHONE, str(response.data))

    def test_claims_feature_off_does_not_reveal_the_shop_book(self):
        module = ModuleSettings.objects.get(module_name='expenses')
        feature, _ = ModuleFeature.objects.get_or_create(
            module=module,
            feature_key='employee_claims',
            defaults={'feature_name': 'Employee expense claims', 'is_enabled': False},
        )
        feature.is_enabled = False
        feature.save(update_fields=['is_enabled'])
        try:
            self.assertNotIn('Shop power', self._descriptions(self.manager))
            self.assertIn('Sales fare', self._descriptions(self.manager))
        finally:
            feature.is_enabled = True
            feature.save(update_fields=['is_enabled'])

    def test_forty_claims_and_forty_shop_rows_stay_separated(self):
        today = timezone.localdate()
        for index in range(40):
            Expense.objects.create(
                description=f'Batch claim {index}',
                amount=Decimal('1.00'),
                expense_date=today,
                status='pending',
                is_claim=True,
                created_by=self.sales,
            )
            Expense.objects.create(
                description=f'Batch shop {index}',
                amount=Decimal('2.00'),
                expense_date=today,
                status='approved',
                created_by=self.admin,
                notes=HIDDEN_PHONE,
            )
        self._auth(self.sales)
        sales = self.client.get('/api/expenses/?page_size=200')
        sales_rows = sales.data.get('results', sales.data)
        self.assertEqual(
            sum(1 for row in sales_rows if str(row['description']).startswith('Batch claim')),
            40,
        )
        self.assertFalse(
            any(str(row['description']).startswith('Batch shop') for row in sales_rows)
        )
        self.assertNotIn(HIDDEN_PHONE, str(sales.data))
        self._auth(self.manager)
        manager = self.client.get('/api/expenses/?page_size=200')
        manager_rows = manager.data.get('results', manager.data)
        self.assertEqual(
            sum(1 for row in manager_rows if str(row['description']).startswith('Batch claim')),
            40,
        )
        self.assertFalse(
            any(str(row['description']).startswith('Batch shop') for row in manager_rows)
        )
        claimed = [
            Decimal(str(row['amount']))
            for row in sales_rows
            if str(row['description']).startswith('Batch claim')
        ]
        self.assertEqual(sum(claimed), Decimal('40.00'))
