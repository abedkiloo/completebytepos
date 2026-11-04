"""
Expense vouchers, categories, and status transitions.

Public entry points:
    - ``ExpenseService.approve_expense`` / ``reject_expense`` / ``resubmit_expense`` /
      ``void_expense`` / ``build_queryset`` / ``get_expense_statistics``
    - ``ExpenseCategoryService.build_queryset`` / ``delete_unused_category``
    - HTTP under ``/api/expenses/``

Approve may create an accounting journal (best-effort). Void reverses posted
journals for approved/paid rows.
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum, Count, QuerySet
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
from .models import ExpenseCategory, Expense
from settings.models import Branch
from settings.utils import get_current_branch, is_branch_support_enabled
from services.base import BaseService


def _clean_filter_value(value: Any) -> Optional[str]:
    """
    Drop empty / client sentinel filter values (e.g. ``undefined`` from bad selects).

    Args:
        value: Raw query param.

    Returns:
        Stripped string, or None when empty/sentinel.
    """
    if value is None:
        return None
    text = str(value).strip()
    if text in ('', 'undefined', 'null', 'None'):
        return None
    return text


class ExpenseCategoryService(BaseService):
    """List/filter expense categories and safe hard-delete when unused."""

    def __init__(self):
        super().__init__(ExpenseCategory)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for category listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - is_active: bool or str ('true'/'false')
        
        Returns:
            QuerySet of categories with expense_count annotation
        """
        queryset = self.model.objects.annotate(expense_count=Count('expenses'))
        
        if not filters:
            return queryset.order_by('name')
        
        is_active = filters.get('is_active')
        if is_active is not None:
            if isinstance(is_active, str):
                is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)

        search = _clean_filter_value(filters.get('search'))
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        
        return queryset.order_by('name')

    def delete_unused_category(self, category: ExpenseCategory) -> None:
        """
        Hard-delete a category only when no expenses reference it.

        Args:
            category: Category instance to delete.

        Returns:
            None.

        Raises:
            ValidationError: When one or more expenses still use the category
                (caller should deactivate instead).
        """
        usage = Expense.objects.filter(category=category).count()
        if usage:
            raise ValidationError(
                f'Cannot delete “{category.name}”: it is used by {usage} expense(s). '
                'Deactivate it instead, or reassign those expenses first.'
            )
        category.delete()


EXPENSE_ADMIN_ONLY_MESSAGE = 'Only an admin can approve or return expenses.'


def require_expense_admin(user) -> None:
    """
    Require admin-checker override for expense approve/return.

    Args:
        user: Acting user.

    Raises:
        PermissionDenied: When the user lacks admin checker override.
    """
    from django.core.exceptions import PermissionDenied

    from approvals.permissions import user_has_admin_checker_override

    if not user_has_admin_checker_override(user):
        raise PermissionDenied(EXPENSE_ADMIN_ONLY_MESSAGE)


class ExpenseService(BaseService):
    """
    Expense list filters and approve/reject/resubmit/void transitions.

    Amount bounds live on the model (``amount`` ≥ 0.01). Status machine:
    pending ↔ rejected (resubmit) → approved/paid → voided.
    """

    def __init__(self):
        super().__init__(Expense)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None, request=None) -> QuerySet:
        """
        Build queryset with filters for expense listing.
        Moves query building logic from views to service layer.
        
        Args:
            filters: Dictionary with filter parameters:
                - branch_id: int (branch ID)
                - show_all: bool or str ('true'/'false')
                - category: int (category ID)
                - status: str (expense status)
                - date_from: str (date string)
                - date_to: str (date string)
                - payment_method: str
            request: HttpRequest (optional, for branch detection)
        
        Returns:
            QuerySet of expenses with proper select_related/prefetch_related
        """
        queryset = self.model.objects.all().select_related(
            'category', 'created_by', 'approved_by', 'branch'
        )
        
        if not filters:
            filters = {}

        show_all = filters.get('show_all', 'false')
        if isinstance(show_all, str):
            show_all = show_all.lower() == 'true'

        # Branch filter only when multi-branch is enabled.
        # Include unassigned (NULL) rows so older expenses remain visible.
        if not show_all and is_branch_support_enabled():
            branch_id = _clean_filter_value(filters.get('branch_id'))
            if not branch_id and request:
                current_branch = get_current_branch(request)
                if current_branch:
                    branch_id = current_branch.id

            if branch_id:
                try:
                    bid = int(branch_id)
                    queryset = queryset.filter(Q(branch_id=bid) | Q(branch__isnull=True))
                except (ValueError, TypeError):
                    queryset = queryset.none()

        # Category filter
        category = _clean_filter_value(filters.get('category'))
        if category:
            try:
                queryset = queryset.filter(category_id=int(category))
            except (ValueError, TypeError):
                queryset = queryset.none()

        # Status filter
        status_filter = _clean_filter_value(filters.get('status'))
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Accountability: expenses this user approved
        approved_by = _clean_filter_value(filters.get('approved_by'))
        if approved_by:
            try:
                queryset = queryset.filter(approved_by_id=int(approved_by))
            except (TypeError, ValueError):
                pass

        created_by = _clean_filter_value(filters.get('created_by'))
        if created_by:
            try:
                queryset = queryset.filter(created_by_id=int(created_by))
            except (TypeError, ValueError):
                pass

        # Date filters
        date_from = _clean_filter_value(filters.get('date_from'))
        if date_from:
            queryset = queryset.filter(expense_date__gte=date_from)

        date_to = _clean_filter_value(filters.get('date_to'))
        if date_to:
            queryset = queryset.filter(expense_date__lte=date_to)

        # Payment method filter
        payment_method = _clean_filter_value(filters.get('payment_method'))
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

        include_tp = _clean_filter_value(filters.get('include_in_trading_profit'))
        if include_tp is not None:
            if include_tp.lower() in ('true', '1', 'yes'):
                queryset = queryset.filter(
                    Q(category__isnull=True) | Q(category__include_in_trading_profit=True)
                )
            elif include_tp.lower() in ('false', '0', 'no'):
                queryset = queryset.filter(category__include_in_trading_profit=False)

        return queryset.order_by('-expense_date', '-created_at')
    
    @transaction.atomic
    def approve_expense(self, expense: Expense, approved_by) -> Expense:
        """
        Approve a pending expense and attempt to post its journal.

        Args:
            expense: Must be ``pending`` (not already approved).
            approved_by: Admin checker; must not be the maker; past-dated
                rows require admin past-date override.

        Returns:
            Expense with ``status='approved'`` and ``approved_by`` set.

        Raises:
            PermissionDenied: Non-admin checker.
            ValidationError: Wrong status or maker/checker / past-date rules.

        Side effects:
            Completes rejection notices; best-effort
            ``create_expense_journal_entry`` (journal failure is logged and
            does **not** roll back approval status).
        """
        from approvals.financial_workflow import (
            validate_checker_not_maker,
            validate_past_dated_checker,
        )

        require_expense_admin(approved_by)
        validate_checker_not_maker(approved_by, expense.created_by_id)
        validate_past_dated_checker(approved_by, expense.expense_date, expense.created_at)
        if expense.status == 'approved':
            raise ValidationError('Expense is already approved')
        if expense.status != 'pending':
            raise ValidationError('Only pending expenses can be approved.')
        
        expense.status = 'approved'
        expense.approved_by = approved_by
        expense.save()
        from daily_notes.approval_notice import SOURCE_EXPENSE, complete_rejection_notices

        complete_rejection_notices(source=SOURCE_EXPENSE, record_id=expense.id)
        
        # Create journal entry for expense
        try:
            from accounting.services import create_expense_journal_entry
            create_expense_journal_entry(expense)
        except Exception as e:
            # Log error but don't fail the approval
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating journal entry for expense: {e}")
        
        return expense

    @transaction.atomic
    def reject_expense(self, expense: Expense, rejected_by, reason: str) -> Expense:
        """
        Return a pending expense to the requester with a required reason.

        Args:
            expense: Must be ``pending``.
            rejected_by: Admin checker (≠ maker).
            reason: Non-blank explanation; appended into ``notes``.

        Returns:
            Expense with ``status='rejected'``.

        Raises:
            PermissionDenied / ValidationError: Auth or status/reason failures.

        Side effects:
            Notifies requester via daily-notes approval notice.
        """
        from approvals.financial_workflow import (
            validate_checker_not_maker,
            validate_past_dated_checker,
        )
        from daily_notes.approval_notice import SOURCE_EXPENSE, notify_approval_rejected

        require_expense_admin(rejected_by)
        validate_checker_not_maker(rejected_by, expense.created_by_id)
        validate_past_dated_checker(rejected_by, expense.expense_date, expense.created_at)
        reason = (reason or '').strip()
        if not reason:
            raise ValidationError({'rejection_reason': 'Say why you are returning this expense.'})
        if expense.status != 'pending':
            raise ValidationError('Only pending expenses can be returned to the requester.')
        expense.status = 'rejected'
        note = f'[Rejected by {getattr(rejected_by, "username", "checker")}] {reason}'
        expense.notes = f'{expense.notes}\n{note}'.strip() if expense.notes else note
        expense.save(update_fields=['status', 'notes', 'updated_at'])
        notify_approval_rejected(
            requester=expense.created_by,
            checker=rejected_by,
            action_type='expense',
            entity_repr=expense.expense_number or expense.description,
            rejection_reason=reason,
            source=SOURCE_EXPENSE,
            record_id=expense.id,
        )
        return expense

    @transaction.atomic
    def resubmit_expense(self, expense: Expense, user) -> Expense:
        """
        Move a rejected expense back to ``pending`` for another check.

        Args:
            expense: Must be ``rejected``.
            user: Must be the original ``created_by`` (or superuser).

        Returns:
            Expense with ``status='pending'``.

        Raises:
            ValidationError: Wrong status or not the owner.
        """
        if expense.status != 'rejected':
            raise ValidationError('Only rejected expenses can be sent back for approval.')
        if (
            expense.created_by_id
            and expense.created_by_id != getattr(user, 'id', None)
            and not getattr(user, 'is_superuser', False)
        ):
            raise ValidationError('You can only resubmit your own expenses.')
        expense.status = 'pending'
        expense.save(update_fields=['status', 'updated_at'])
        from daily_notes.approval_notice import SOURCE_EXPENSE, complete_rejection_notices

        complete_rejection_notices(source=SOURCE_EXPENSE, record_id=expense.id)
        return expense

    @transaction.atomic
    def void_expense(self, expense: Expense, *, reason: str, user) -> Expense:
        """
        Void an expense and reverse journals when it was posted.

        Args:
            expense: ``pending``/``rejected`` void without journal reverse;
                ``approved``/``paid`` reverse source journals first.
            reason: Required non-blank void reason (appended to notes).
            user: Actor passed to accounting reversal.

        Returns:
            Expense with ``status='voided'``.

        Raises:
            ValidationError: Blank reason, already voided, or unsupported status.
        """
        reason = (reason or '').strip()
        if not reason:
            raise ValidationError({'reason': 'A reason is required to void an expense.'})
        if expense.status == 'voided':
            raise ValidationError('This expense is already voided.')
        if expense.status in ('approved', 'paid'):
            from accounting.reversal import reverse_source_documents

            reverse_source_documents(
                'expense',
                expense.id,
                reason=reason,
                user=user,
            )
        elif expense.status not in ('pending', 'rejected'):
            raise ValidationError('This expense cannot be voided.')
        expense.status = 'voided'
        note = f'VOIDED: {reason}'
        expense.notes = f'{expense.notes}\n{note}'.strip() if expense.notes else note
        expense.save(update_fields=['status', 'notes', 'updated_at'])
        return expense
    
    def get_expense_statistics(self, branch: Optional[Branch] = None,
                              date_from: Optional[str] = None,
                              date_to: Optional[str] = None) -> Dict[str, Any]:
        """
        Aggregate approved expense totals (and status breakdown) for a window.

        Args:
            branch: Optional branch filter; ``None`` = all branches.
            date_from / date_to: Inclusive ``expense_date`` bounds as date
                strings accepted by Django (``YYYY-MM-DD``). ``None`` = open.

        Returns:
            Dict with ``total_expenses``, ``month_expenses`` (current calendar
            month of approved rows), ``by_category``, ``by_status``. Money
            totals returned as float for API compatibility.
        """
        queryset = self.model.objects.all()
        
        if branch:
            queryset = queryset.filter(branch=branch)
        
        if date_from:
            queryset = queryset.filter(expense_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(expense_date__lte=date_to)
        
        today = timezone.now().date()
        start_of_month = timezone.make_aware(datetime(today.year, today.month, 1))
        
        approved_queryset = queryset.filter(status='approved')
        
        total_expenses = approved_queryset.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        month_expenses = approved_queryset.filter(
            expense_date__gte=start_of_month.date()
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
            'total_expenses': float(total_expenses),
            'month_expenses': float(month_expenses),
            'by_category': by_category,
            'by_status': by_status,
        }
