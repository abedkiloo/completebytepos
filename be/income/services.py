"""
Business logic for income categories and receipt approval workflow.

Public entry points:
    - ``IncomeCategoryService.build_queryset`` — filtered category lists
    - ``IncomeService.build_queryset`` — branch/category/status/date filters
    - ``IncomeService.approve_income`` / ``reject_income`` / ``resubmit_income`` / ``void_income``
    - ``IncomeService.get_income_statistics`` — aggregates for dashboards

Side effects: approve may create GL journals; reject/resubmit update daily notes;
void reverses posted journals for approved/received rows. Checker/maker rules from
``approvals.financial_workflow``.
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum, Count, QuerySet
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime
from .models import IncomeCategory, Income
from settings.models import Branch
from settings.utils import get_current_branch, is_branch_support_enabled
from services.base import BaseService


class IncomeCategoryService(BaseService):
    """
    Read-side filtering and annotations for income categories.

    Attributes:
        model: Bound to ``IncomeCategory``.
    """

    def __init__(self):
        super().__init__(IncomeCategory)

    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build a category queryset with optional active filter and income counts.

        Args:
            filters: Optional dict. Supported keys:
                is_active: bool or ``'true'``/``'false'`` string; omit for all.

        Returns:
            ``QuerySet`` of ``IncomeCategory`` ordered by name, each annotated
            with ``income_count`` (related income rows, any status).
        """
        queryset = self.model.objects.annotate(income_count=Count('incomes'))

        if not filters:
            return queryset

        is_active = filters.get('is_active')
        if is_active is not None:
            if isinstance(is_active, str):
                is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)

        return queryset.order_by('name')


class IncomeService(BaseService):
    """
    Income listing, approval workflow, void, and reporting aggregates.

    Mutating methods run in ``atomic`` transactions and enforce financial
    checker rules (not maker, past-dated checks).

    Attributes:
        model: Bound to ``Income``.
    """

    def __init__(self):
        super().__init__(Income)

    def build_queryset(self, filters: Optional[Dict[str, Any]] = None, request=None) -> QuerySet:
        """
        Build an income list queryset with branch scoping and common filters.

        When ``show_all`` is false and ``branch_id`` is omitted, uses
        ``get_current_branch(request)`` when branch support is enabled.

        Args:
            filters: Optional dict. Supported keys:
                branch_id: int branch PK; invalid values yield empty queryset.
                show_all: bool or string; true disables branch filter.
                category: category PK (int as string allowed).
                status: exact status string (pending, approved, etc.).
                date_from / date_to: inclusive ``income_date`` bounds (ISO date strings).
                payment_method: exact payment method code.
            request: Optional HTTP request for current-branch detection.

        Returns:
            ``QuerySet`` with ``select_related`` on category, users, branch;
            ordered by ``-income_date``, ``-created_at``.
        """
        queryset = self.model.objects.all().select_related(
            'category', 'created_by', 'approved_by', 'branch'
        )

        if not filters:
            filters = {}

        # Handle branch filtering
        show_all = filters.get('show_all', 'false')
        if isinstance(show_all, str):
            show_all = show_all.lower() == 'true'

        if not show_all:
            branch_id = filters.get('branch_id')
            if not branch_id and request:
                current_branch = get_current_branch(request)
                if current_branch:
                    branch_id = current_branch.id

            if branch_id:
                try:
                    queryset = queryset.filter(branch_id=int(branch_id))
                except (ValueError, TypeError):
                    queryset = queryset.none()

        # Category filter
        category = filters.get('category')
        if category:
            try:
                queryset = queryset.filter(category_id=int(category))
            except (ValueError, TypeError):
                queryset = queryset.none()

        # Status filter
        status_filter = filters.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Date filters
        date_from = filters.get('date_from')
        if date_from:
            queryset = queryset.filter(income_date__gte=date_from)

        date_to = filters.get('date_to')
        if date_to:
            queryset = queryset.filter(income_date__lte=date_to)

        # Payment method filter
        payment_method = filters.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

        return queryset.order_by('-income_date', '-created_at')

    @transaction.atomic
    def approve_income(self, income: Income, approved_by) -> Income:
        """
        Mark income approved and post GL journals when possible.

        Args:
            income: Row to approve; must not already be ``approved``.
            approved_by: User acting as checker (stored on ``approved_by``).

        Returns:
            Updated ``Income`` instance (status ``approved``).

        Raises:
            ValidationError: Checker is maker, past-dated rule fails, or already approved.

        Side effects:
            Updates income row; clears rejection daily notes; calls
            ``create_income_journal_entry`` (errors logged, approval not rolled back).
        """
        from approvals.financial_workflow import (
            validate_checker_not_maker,
            validate_past_dated_checker,
        )

        validate_checker_not_maker(approved_by, income.created_by_id)
        validate_past_dated_checker(approved_by, income.income_date, income.created_at)
        if income.status == 'approved':
            raise ValidationError('Income is already approved')

        income.status = 'approved'
        income.approved_by = approved_by
        income.save()
        from daily_notes.approval_notice import SOURCE_INCOME, complete_rejection_notices

        complete_rejection_notices(source=SOURCE_INCOME, record_id=income.id)

        # Create journal entry for income
        try:
            from accounting.services import create_income_journal_entry
            create_income_journal_entry(income)
        except Exception as e:
            # Log error but don't fail the approval
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating journal entry for income: {e}")

        return income

    @transaction.atomic
    def reject_income(self, income: Income, rejected_by, reason: str) -> Income:
        """
        Return pending income to the requester with a mandatory reason.

        Args:
            income: Must be ``pending``.
            rejected_by: Checker user (not the maker).
            reason: Non-blank explanation after strip; shown in notes and notification.

        Returns:
            Updated ``Income`` with status ``rejected``.

        Raises:
            ValidationError: Empty reason, wrong status, checker/maker or date rules.

        Side effects:
            Appends rejection note; notifies requester via daily notes.
        """
        from approvals.financial_workflow import (
            validate_checker_not_maker,
            validate_past_dated_checker,
        )
        from daily_notes.approval_notice import SOURCE_INCOME, notify_approval_rejected

        validate_checker_not_maker(rejected_by, income.created_by_id)
        validate_past_dated_checker(rejected_by, income.income_date, income.created_at)
        reason = (reason or '').strip()
        if not reason:
            raise ValidationError({'rejection_reason': 'Say why you are returning this income.'})
        if income.status != 'pending':
            raise ValidationError('Only pending income can be returned to the requester.')
        income.status = 'rejected'
        note = f'[Rejected by {getattr(rejected_by, "username", "checker")}] {reason}'
        income.notes = f'{income.notes}\n{note}'.strip() if income.notes else note
        income.save(update_fields=['status', 'notes', 'updated_at'])
        notify_approval_rejected(
            requester=income.created_by,
            checker=rejected_by,
            action_type='income',
            entity_repr=income.income_number or income.description,
            rejection_reason=reason,
            source=SOURCE_INCOME,
            record_id=income.id,
        )
        return income

    @transaction.atomic
    def resubmit_income(self, income: Income, user) -> Income:
        """
        Move rejected income back to pending for another approval cycle.

        Args:
            income: Must be ``rejected``.
            user: Requester resubmitting; must be ``created_by`` unless superuser.

        Returns:
            Updated ``Income`` with status ``pending``.

        Raises:
            ValidationError: Wrong status or user is not owner.

        Side effects:
            Clears completed rejection notices for this income record.
        """
        if income.status != 'rejected':
            raise ValidationError('Only rejected income can be sent back for approval.')
        if (
            income.created_by_id
            and income.created_by_id != getattr(user, 'id', None)
            and not getattr(user, 'is_superuser', False)
        ):
            raise ValidationError('You can only resubmit your own income records.')
        income.status = 'pending'
        income.save(update_fields=['status', 'updated_at'])
        from daily_notes.approval_notice import SOURCE_INCOME, complete_rejection_notices

        complete_rejection_notices(source=SOURCE_INCOME, record_id=income.id)
        return income

    @transaction.atomic
    def void_income(self, income: Income, *, reason: str, user) -> Income:
        """
        Void income and reverse posted journals when books were affected.

        Args:
            income: Row to void; must not already be ``voided``.
            reason: Non-blank void reason (stored in notes).
            user: Acting user passed to journal reversal.

        Returns:
            Updated ``Income`` with status ``voided``.

        Raises:
            ValidationError: Missing reason, already voided, or status cannot void.

        Side effects:
            For ``approved`` or ``received``, calls ``reverse_source_documents``
            with reference_type ``income``; always appends VOID note to ``notes``.
        """
        reason = (reason or '').strip()
        if not reason:
            raise ValidationError({'reason': 'A reason is required to void income.'})
        if income.status == 'voided':
            raise ValidationError('This income is already voided.')
        if income.status in ('approved', 'received'):
            from accounting.reversal import reverse_source_documents

            reverse_source_documents(
                'income',
                income.id,
                reason=reason,
                user=user,
            )
        elif income.status not in ('pending', 'rejected'):
            raise ValidationError('This income cannot be voided.')
        income.status = 'voided'
        note = f'VOIDED: {reason}'
        income.notes = f'{income.notes}\n{note}'.strip() if income.notes else note
        income.save(update_fields=['status', 'notes', 'updated_at'])
        return income

    def get_income_statistics(self, branch: Optional[Branch] = None,
                             date_from: Optional[str] = None,
                             date_to: Optional[str] = None) -> Dict[str, Any]:
        """
        Aggregate approved income totals and breakdowns for reporting.

        Month-to-date uses calendar month start in the active timezone.

        Args:
            branch: Optional branch filter; None includes all branches.
            date_from: Optional inclusive lower bound on ``income_date`` (string).
            date_to: Optional inclusive upper bound on ``income_date`` (string).

        Returns:
            Dict with ``total_income``, ``month_income`` (floats, approved only),
            ``by_category`` and ``by_status`` (list of dicts with totals and counts).
            Empty approved set yields 0.0 totals.
        """
        queryset = self.model.objects.all()

        if branch:
            queryset = queryset.filter(branch=branch)

        if date_from:
            queryset = queryset.filter(income_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(income_date__lte=date_to)

        today = timezone.now().date()
        start_of_month = timezone.make_aware(datetime(today.year, today.month, 1))

        approved_queryset = queryset.filter(status='approved')

        total_income = approved_queryset.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        month_income = approved_queryset.filter(
            income_date__gte=start_of_month.date()
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        by_category = list(approved_queryset.values(
            'category__name'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ))

        by_status = list(queryset.values('status').annotate(
            total=Sum('amount'),
            count=Count('id')
        ))

        return {
            'total_income': float(total_income),
            'month_income': float(month_income),
            'by_category': by_category,
            'by_status': by_status,
        }
