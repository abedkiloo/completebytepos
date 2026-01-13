from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from .models import ExpenseCategory, Expense
from .serializers import (
    ExpenseCategorySerializer, ExpenseSerializer, ExpenseListSerializer
)
from settings.utils import get_current_branch, get_current_tenant, is_branch_support_enabled
import logging

logger = logging.getLogger(__name__)


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        queryset = ExpenseCategory.objects.annotate(
            expense_count=Count('expenses')
        )
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all().select_related('category', 'created_by', 'approved_by')
    serializer_class = ExpenseSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['expense_number', 'description', 'vendor', 'receipt_number']
    ordering_fields = ['expense_date', 'amount', 'created_at']
    ordering = ['-expense_date', '-created_at']

    def get_queryset(self):
        queryset = Expense.objects.all().select_related('category', 'created_by', 'approved_by', 'branch')
        
        # Filter by branch if specified (skip if show_all is true)
        show_all = self.request.query_params.get('show_all', 'false').lower() == 'true'
        branch_id = self.request.query_params.get('branch_id', None)
        
        if not show_all:
            if not branch_id:
                # Try to get from current branch
                current_branch = get_current_branch(self.request)
                if current_branch:
                    branch_id = current_branch.id
            
            if branch_id:
                queryset = queryset.filter(branch_id=branch_id)
        
        # Filters
        category = self.request.query_params.get('category', None)
        status_filter = self.request.query_params.get('status', None)
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        payment_method = self.request.query_params.get('payment_method', None)
        
        if category:
            queryset = queryset.filter(category_id=category)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if date_from:
            queryset = queryset.filter(expense_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(expense_date__lte=date_to)
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        
        return queryset

    def perform_create(self, serializer):
        # Get current branch only if branch support is enabled
        branch = None
        if is_branch_support_enabled():
            branch = get_current_branch(self.request)
        serializer.save(created_by=self.request.user, branch=branch)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve an expense"""
        expense = self.get_object()
        if expense.status == 'approved':
            return Response(
                {'error': 'Expense is already approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        expense.status = 'approved'
        expense.approved_by = request.user
        expense.save()
        
        # Create journal entry for expense
        try:
            from accounting.views import create_expense_journal_entry
            create_expense_journal_entry(expense)
        except Exception as e:
            # Log error but don't fail the approval
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating journal entry for expense: {e}")
        
        serializer = self.get_serializer(expense)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get expense statistics"""
        today = timezone.now().date()
        start_of_month = timezone.make_aware(datetime(today.year, today.month, 1))
        
        # Filter by branch if specified
        current_branch = get_current_branch(request)
        expense_queryset = Expense.objects.all()
        if current_branch:
            expense_queryset = expense_queryset.filter(branch=current_branch)
        
        total_expenses = expense_queryset.filter(status='approved').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        month_expenses = expense_queryset.filter(
            status='approved',
            expense_date__gte=start_of_month.date()
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        by_category = expense_queryset.filter(status='approved').values(
            'category__name'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        by_status = expense_queryset.values('status').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        return Response({
            'total_expenses': float(total_expenses),
            'month_expenses': float(month_expenses),
            'by_category': list(by_category),
            'by_status': list(by_status),
        })
