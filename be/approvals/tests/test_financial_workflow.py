"""
TDD: maker-checker on expenses, income, and money transfers (own status workflow).
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SUPER_ADMIN, sync_default_roles
from bankaccounts.models import BankAccount
from expenses.models import Expense, ExpenseCategory
from income.models import Income, IncomeCategory
from settings.models import StoreSettings
from transfers.models import MoneyTransfer
from utils.tests.api_test_base import ManagerAPITestCase


def _enable_maker_checker(enabled=True):
    store = StoreSettings.load()
    store.maker_checker_enabled = enabled
    store.save(update_fields=['maker_checker_enabled'])


class ExpenseMakerCheckerAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = ExpenseCategory.objects.create(name='Ops MC', is_active=True)

    def setUp(self):
        super().setUp()
        _enable_maker_checker(True)

    def tearDown(self):
        _enable_maker_checker(False)
        super().tearDown()

    def test_create_requires_proposal_reason_when_mc_on(self):
        resp = self.client.post(
            '/api/expenses/',
            {
                'category': self.category.id,
                'amount': '50.00',
                'description': 'Supplies',
                'expense_date': '2026-05-01',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)
        self.assertTrue(
            'proposal_reason' in resp.data
            or 'non_field_errors' in resp.data
            or str(resp.data).find('proposal_reason') >= 0
        )

    def test_create_stays_pending_until_checker_approves(self):
        resp = self.client.post(
            '/api/expenses/',
            {
                'category': self.category.id,
                'amount': '75.00',
                'description': 'Fuel',
                'expense_date': '2026-05-02',
                'proposal_reason': 'Monthly fuel',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['status'], 'pending')
        expense_id = resp.data['id']

        self_approve = self.client.post(f'/api/expenses/{expense_id}/approve/')
        self.assertEqual(self_approve.status_code, status.HTTP_400_BAD_REQUEST)

        sync_default_roles()
        checker = User.objects.create_user('exp_checker', password='x', is_staff=True)
        UserProfile.objects.create(
            user=checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        ok = client.post(f'/api/expenses/{expense_id}/approve/')
        self.assertEqual(ok.status_code, status.HTTP_200_OK, ok.data)
        self.assertEqual(ok.data['status'], 'approved')

    def test_expense_double_approve_returns_400(self):
        create = self.client.post(
            '/api/expenses/',
            {
                'category': self.category.id,
                'amount': '40.00',
                'description': 'Snack',
                'expense_date': '2026-05-06',
                'proposal_reason': 'Team snack',
            },
            format='json',
        )
        expense_id = create.data['id']
        sync_default_roles()
        checker = User.objects.create_user('chk_exp2', password='x', is_staff=True)
        UserProfile.objects.create(
            user=checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        client.post(f'/api/expenses/{expense_id}/approve/')
        again = client.post(f'/api/expenses/{expense_id}/approve/')
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expense_approve_journal_error_is_non_fatal(self):
        create = self.client.post(
            '/api/expenses/',
            {
                'category': self.category.id,
                'amount': '55.00',
                'description': 'Ledger test',
                'expense_date': '2026-05-07',
                'proposal_reason': 'GL test',
            },
            format='json',
        )
        expense_id = create.data['id']
        sync_default_roles()
        checker = User.objects.create_user('chk_gl', password='x', is_staff=True)
        UserProfile.objects.create(
            user=checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        with patch(
            'accounting.services.create_expense_journal_entry',
            side_effect=RuntimeError('ledger down'),
        ):
            ok = client.post(f'/api/expenses/{expense_id}/approve/')
        self.assertEqual(ok.status_code, status.HTTP_200_OK, ok.data)
        self.assertEqual(ok.data['status'], 'approved')

    def test_approved_expense_not_editable_when_mc_on(self):
        expense = Expense.objects.create(
            category=self.category,
            amount=Decimal('10.00'),
            description='Locked',
            expense_date='2026-05-03',
            status='approved',
            created_by=self.manager_user,
        )
        resp = self.client.patch(
            f'/api/expenses/{expense.id}/',
            {'description': 'Changed', 'proposal_reason': 'Try edit'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class IncomeMakerCheckerAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = IncomeCategory.objects.create(name='Sales MC', is_active=True)

    def setUp(self):
        super().setUp()
        _enable_maker_checker(True)

    def tearDown(self):
        _enable_maker_checker(False)
        super().tearDown()

    def test_income_approve_journal_error_is_non_fatal(self):
        create = self.client.post(
            '/api/income/',
            {
                'category': self.category.id,
                'amount': '88.00',
                'description': 'GL income',
                'income_date': '2026-05-08',
                'proposal_reason': 'GL income test',
            },
            format='json',
        )
        income_id = create.data['id']
        sync_default_roles()
        checker = User.objects.create_user('chk_inc_gl', password='x', is_staff=True)
        UserProfile.objects.create(
            user=checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        with patch(
            'accounting.services.create_income_journal_entry',
            side_effect=RuntimeError('ledger down'),
        ):
            ok = client.post(f'/api/income/{income_id}/approve/')
        self.assertEqual(ok.status_code, status.HTTP_200_OK, ok.data)
        self.assertEqual(ok.data['status'], 'approved')

    def test_income_double_approve_returns_400(self):
        create = self.client.post(
            '/api/income/',
            {
                'category': self.category.id,
                'amount': '60.00',
                'description': 'Duplicate',
                'income_date': '2026-05-09',
                'proposal_reason': 'Dup test',
            },
            format='json',
        )
        income_id = create.data['id']
        sync_default_roles()
        checker = User.objects.create_user('chk_inc2', password='x', is_staff=True)
        UserProfile.objects.create(
            user=checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        client.post(f'/api/income/{income_id}/approve/')
        again = client.post(f'/api/income/{income_id}/approve/')
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)

    def test_income_maker_cannot_self_approve(self):
        resp = self.client.post(
            '/api/income/',
            {
                'category': self.category.id,
                'amount': '120.00',
                'description': 'Consulting',
                'income_date': '2026-05-04',
                'proposal_reason': 'Client payment',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        again = self.client.post(f'/api/income/{resp.data["id"]}/approve/')
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)


class TransferMakerCheckerAPITests(ManagerAPITestCase):
    def tearDown(self):
        _enable_maker_checker(False)
        super().tearDown()

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.from_account = BankAccount.objects.create(
            account_name='From MC',
            account_number='MC-FROM-1',
            bank_name='KCB',
            created_by=cls.manager_user,
        )
        cls.to_account = BankAccount.objects.create(
            account_name='To MC',
            account_number='MC-TO-1',
            bank_name='KCB',
            created_by=cls.manager_user,
        )

    def setUp(self):
        super().setUp()
        _enable_maker_checker(True)

    def test_transfer_create_pending_and_checker_approves(self):
        resp = self.client.post(
            '/api/transfers/',
            {
                'from_account': self.from_account.id,
                'to_account': self.to_account.id,
                'amount': '100.00',
                'transfer_type': 'bank_to_bank',
                'description': 'Float top-up',
                'transfer_date': '2026-05-05',
                'proposal_reason': 'Branch float',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['status'], 'pending')

        sync_default_roles()
        checker = User.objects.create_user('xfer_checker', password='x', is_staff=True)
        UserProfile.objects.create(
            user=checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        ok = client.post(f'/api/transfers/{resp.data["id"]}/approve/')
        self.assertEqual(ok.status_code, status.HTTP_200_OK, ok.data)
        self.assertEqual(ok.data['status'], 'completed')
