from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from .models import ExpenseCategory, Expense
from .serializers import (
    ExpenseCategorySerializer, ExpenseSerializer, ExpenseListSerializer
)
from .services import ExpenseCategoryService, ExpenseService
from utils.list_ordering import NameSavedOrderingFilter
from accounts.permissions import RequireModuleEnabled, RequirePermPerAction, IsSuperAdmin
from utils.audit_events import log_approval_event
from utils.audit_helpers import audited_perform_create, audited_perform_update
from approvals.financial_workflow import finalize_financial_create, prepare_financial_update
from utils.audit_mixin import AuditedModelViewSetMixin
from settings.utils import get_current_branch, get_current_tenant, is_branch_support_enabled
import logging

logger = logging.getLogger(__name__)


def _user_has_expenses_perm(user, action: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.has_permission('expenses', action))


class CanUpdateExpense(permissions.BasePermission):
    """
    expenses.update — edit any non-voided expense (admin default, grantable).

    Creators with expenses.create may still edit their own pending/rejected rows.
    """

    message = 'You do not have permission to edit this expense.'

    def has_permission(self, request, view):
        if _user_has_expenses_perm(request.user, 'update'):
            return True
        return _user_has_expenses_perm(request.user, 'create')

    def has_object_permission(self, request, view, obj):
        if _user_has_expenses_perm(request.user, 'update'):
            return getattr(obj, 'status', None) != 'voided'
        if getattr(obj, 'status', None) not in ('pending', 'rejected'):
            return False
        return obj.created_by_id == getattr(request.user, 'id', None)


EXPENSE_CATEGORY_PERMS = RequirePermPerAction('expenses', {
    'list': 'view',
    'retrieve': 'view',
    'create': 'create',
    # Category maintenance uses create; expense row edits use expenses.update.
    'update': 'create',
    'partial_update': 'create',
    'destroy': 'delete',
})

EXPENSES_PERMS = RequirePermPerAction('expenses', {
    'list': 'view',
    'retrieve': 'view',
    'create': 'create',
    'destroy': 'delete',
    'void': 'delete',
    'statistics': 'view',
    'approve': 'approve',
    'reject': 'approve',
    # update / partial_update / resubmit use CanUpdateExpense via get_permissions
})


class ExpenseCategoryViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated, EXPENSE_CATEGORY_PERMS]
    audit_module = 'expense_categories'
    filter_backends = [filters.SearchFilter, NameSavedOrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category_service = ExpenseCategoryService()

    def get_permissions(self):
        """Only super admins may hard-delete expense categories."""
        if self.action == 'destroy':
            return [IsAuthenticated(), IsSuperAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        """Get queryset using service layer"""
        filters = {}
        if 'is_active' in self.request.query_params:
            filters['is_active'] = self.request.query_params.get('is_active')
        if 'search' in self.request.query_params:
            filters['search'] = self.request.query_params.get('search')
        return self.category_service.build_queryset(filters)

    def create(self, request, *args, **kwargs):
        """
        Create category, or reuse an existing name (reactivate if inactive).
        Avoids 400 duplicate errors when the UI tries to re-add a seeded category.
        """
        name = (request.data.get('name') or '').strip()
        if name:
            existing = ExpenseCategory.objects.filter(name__iexact=name).first()
            if existing:
                changed = False
                if not existing.is_active:
                    existing.is_active = True
                    changed = True
                description = request.data.get('description')
                if description is not None and description != existing.description:
                    existing.description = description
                    changed = True
                if changed:
                    existing.save()
                serializer = self.get_serializer(existing)
                return Response(serializer.data, status=status.HTTP_200_OK)
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        try:
            self.category_service.delete_unused_category(category)
        except DjangoValidationError as e:
            messages = getattr(e, 'messages', None) or [str(e)]
            return Response({'error': messages[0]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExpenseViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Expense.objects.all().select_related('category', 'created_by', 'approved_by')
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated, EXPENSES_PERMS]
    audit_module = 'expenses'
    filter_backends = [filters.SearchFilter, NameSavedOrderingFilter]
    search_fields = ['expense_number', 'description', 'vendor', 'receipt_number']
    ordering_fields = ['expense_date', 'amount', 'created_at']
    ordering = ['-expense_date', '-created_at']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.expense_service = ExpenseService()

    def get_permissions(self):
        if getattr(self, 'action', None) in ('update', 'partial_update', 'resubmit'):
            return [
                IsAuthenticated(),
                RequireModuleEnabled('expenses')(),
                CanUpdateExpense(),
            ]
        return super().get_permissions()

    def get_serializer_class(self):
        if getattr(self, 'action', None) == 'list':
            return ExpenseListSerializer
        return ExpenseSerializer

    def get_queryset(self):
        """Get queryset using service layer - all query logic moved to service"""
        filters = {}
        query_params = self.request.query_params
        
        # Extract all filter parameters
        for param in [
            'branch_id',
            'show_all',
            'category',
            'status',
            'date_from',
            'date_to',
            'payment_method',
            'approved_by',
            'created_by',
            'include_in_trading_profit',
        ]:
            if param in query_params:
                filters[param] = query_params.get(param)
        
        return self.expense_service.build_queryset(filters, request=self.request)

    def perform_create(self, serializer):
        branch = None
        if is_branch_support_enabled():
            branch = get_current_branch(self.request)
        instance = audited_perform_create(
            self,
            serializer,
            created_by=self.request.user,
            branch=branch,
        )
        finalize_financial_create(self.request, instance)

    def perform_update(self, serializer):
        allow_finalized = _user_has_expenses_perm(self.request.user, 'update')
        prepare_financial_update(
            self.request,
            serializer.instance,
            allow_finalized=allow_finalized,
        )
        audited_perform_update(self, serializer)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve an expense - thin view, business logic in service"""
        expense = self.get_object()
        try:
            approved_expense = self.expense_service.approve_expense(expense, request.user)
            log_approval_event(request, approved_expense, module='expenses')
            serializer = self.get_serializer(approved_expense)
            return Response(serializer.data)
        except (ValidationError, DjangoValidationError) as e:
            detail = getattr(e, 'detail', None) or str(e)
            return Response({'error': detail}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        expense = self.get_object()
        from approvals.financial_workflow import require_rejection_reason

        try:
            reason = require_rejection_reason(request)
            rejected = self.expense_service.reject_expense(expense, request.user, reason)
            log_approval_event(request, rejected, module='expenses')
            return Response(self.get_serializer(rejected).data)
        except (ValidationError, DjangoValidationError) as e:
            payload = getattr(e, 'message_dict', None)
            if payload:
                return Response(payload, status=status.HTTP_400_BAD_REQUEST)
            detail = getattr(e, 'detail', None) or str(e)
            return Response({'error': detail}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def resubmit(self, request, pk=None):
        expense = self.get_object()
        try:
            queued = self.expense_service.resubmit_expense(expense, request.user)
            return Response(self.get_serializer(queued).data)
        except (ValidationError, DjangoValidationError) as e:
            detail = getattr(e, 'detail', None) or str(e)
            return Response({'error': detail}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def void(self, request, pk=None):
        """Void an expense and reverse posted journals."""
        expense = self.get_object()
        reason = (request.data.get('reason') or '').strip()
        try:
            voided = self.expense_service.void_expense(
                expense, reason=reason, user=request.user
            )
        except (ValidationError, DjangoValidationError) as e:
            payload = getattr(e, 'message_dict', None)
            if payload:
                return Response(payload, status=status.HTTP_400_BAD_REQUEST)
            detail = getattr(e, 'detail', None) or str(e)
            return Response({'error': detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(voided).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Expense totals for the current filters (same queryset as the list).

        Query params: date_from, date_to, category, status, payment_method, search, …
        Returns total_amount / expense_count for that set, plus approved-only
        total_expenses for the same date/branch window.
        """
        qs = self.filter_queryset(self.get_queryset())
        agg = qs.aggregate(total=Sum('amount'), count=Count('id'))
        approved_total = (
            qs.filter(status__in=('approved', 'paid')).aggregate(total=Sum('amount'))['total']
            or 0
        )

        current_branch = get_current_branch(request)
        date_from = request.query_params.get('date_from') or None
        date_to = request.query_params.get('date_to') or None
        legacy = self.expense_service.get_expense_statistics(
            branch=current_branch,
            date_from=date_from,
            date_to=date_to,
        )

        return Response(
            {
                **legacy,
                'total_amount': float(agg['total'] or 0),
                'expense_count': int(agg['count'] or 0),
                # Posted spend in the filtered set (approved + paid)
                'posted_total': float(approved_total),
                'date_from': date_from,
                'date_to': date_to,
            }
        )
