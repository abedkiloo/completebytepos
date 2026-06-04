"""Unit tests for approvals.financial_workflow helpers."""

from decimal import Decimal
from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from approvals.financial_workflow import (
    PROPOSAL_REASON_FIELD,
    append_reason_to_notes,
    apply_pending_status_on_create,
    finalize_financial_create,
    prepare_financial_update,
    require_proposal_reason,
    validate_checker_not_maker,
    validate_locked_record_update,
)
from expenses.models import Expense
from settings.models import StoreSettings


def _set_mc(enabled: bool):
    store = StoreSettings.load()
    store.maker_checker_enabled = enabled
    store.save(update_fields=['maker_checker_enabled'])


class FinancialWorkflowUnitTests(TestCase):
    def setUp(self):
        _set_mc(True)

    def tearDown(self):
        _set_mc(False)
        super().tearDown()
        super().tearDown()

    def test_require_proposal_reason_when_enabled(self):
        class Req:
            data = {}

        with self.assertRaises(ValidationError) as ctx:
            require_proposal_reason(Req())
        self.assertIn(PROPOSAL_REASON_FIELD, ctx.exception.detail)

    def test_validate_checker_not_maker_blocks_self_approve(self):
        user = User.objects.create_user('maker', password='x')
        with self.assertRaises(ValidationError):
            validate_checker_not_maker(user, user.id)

    def test_append_reason_to_notes(self):
        expense = Expense(description='x', amount='1', expense_date='2026-01-01')
        append_reason_to_notes(expense, 'Fuel run')
        self.assertIn('[Maker-checker] Fuel run', expense.notes)

    def test_apply_pending_status_on_create(self):
        expense = Expense(
            description='x',
            amount='1',
            expense_date='2026-01-01',
            status='approved',
        )
        fields = apply_pending_status_on_create(expense)
        self.assertEqual(expense.status, 'pending')
        self.assertIn('status', fields)

    def test_validate_locked_record_update_blocks_approved(self):
        expense = Expense(
            description='x',
            amount='1',
            expense_date='2026-01-01',
            status='approved',
        )
        with self.assertRaises(ValidationError):
            validate_locked_record_update(expense)

    def test_finalize_financial_create_sets_pending_and_notes(self):
        expense = Expense.objects.create(
            description='Office',
            amount=Decimal('25.00'),
            expense_date='2026-06-01',
            status='approved',
        )
        req = MagicMock()
        req.data = {'proposal_reason': 'Supplies order'}
        finalize_financial_create(req, expense)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'pending')
        self.assertIn('[Maker-checker] Supplies order', expense.notes)

    def test_prepare_financial_update_appends_reason_on_pending(self):
        expense = Expense.objects.create(
            description='Pending edit',
            amount=Decimal('10.00'),
            expense_date='2026-06-02',
            status='pending',
        )
        req = MagicMock()
        req.data = {'proposal_reason': 'Correct amount'}
        prepare_financial_update(req, expense)
        expense.refresh_from_db()
        self.assertIn('[Maker-checker] Correct amount', expense.notes)


class FinancialWorkflowDisabledTests(TestCase):
    def test_require_proposal_reason_skipped_when_mc_off(self):
        _set_mc(False)
        class Req:
            data = {}

        self.assertIsNone(require_proposal_reason(Req()))
        _set_mc(False)
