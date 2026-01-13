from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import datetime
from .models import IncomeCategory, Income
from .serializers import IncomeCategorySerializer, IncomeSerializer
from settings.utils import get_current_branch, get_current_tenant
import logging

logger = logging.getLogger(__name__)


class IncomeCategoryViewSet(viewsets.ModelViewSet):
    queryset = IncomeCategory.objects.all()
    serializer_class = IncomeCategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        queryset = IncomeCategory.objects.annotate(
            income_count=Count('incomes')
        )
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset


class IncomeViewSet(viewsets.ModelViewSet):
    queryset = Income.objects.all().select_related('category', 'created_by', 'approved_by')
    serializer_class = IncomeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['income_number', 'description', 'payer', 'reference_number']
    ordering_fields = ['income_date', 'amount', 'created_at']
    ordering = ['-income_date', '-created_at']

    def get_queryset(self):
        queryset = Income.objects.all().select_related('category', 'created_by', 'approved_by', 'branch')
        
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
            queryset = queryset.filter(income_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(income_date__lte=date_to)
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
        """Approve an income"""
        income = self.get_object()
        if income.status == 'approved':
            return Response(
                {'error': 'Income is already approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        income.status = 'approved'
        income.approved_by = request.user
        income.save()
        
        # Create journal entry for income
        try:
            from accounting.views import create_income_journal_entry
            create_income_journal_entry(income)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating journal entry for income: {e}")
        
        serializer = self.get_serializer(income)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get income statistics"""
        today = timezone.now().date()
        start_of_month = timezone.make_aware(datetime(today.year, today.month, 1))
        
        # Filter by branch if specified
        current_branch = get_current_branch(request)
        income_queryset = Income.objects.all()
        if current_branch:
            income_queryset = income_queryset.filter(branch=current_branch)
        
        total_income = income_queryset.filter(status='approved').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        month_income = income_queryset.filter(
            status='approved',
            income_date__gte=start_of_month.date()
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        by_category = income_queryset.filter(status='approved').values(
            'category__name'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        by_status = income_queryset.values('status').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        return Response({
            'total_income': float(total_income),
            'month_income': float(month_income),
            'by_category': list(by_category),
            'by_status': list(by_status),
        })
