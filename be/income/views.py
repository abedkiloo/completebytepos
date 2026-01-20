from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import datetime
from .models import IncomeCategory, Income
from .serializers import IncomeCategorySerializer, IncomeSerializer
from .services import IncomeCategoryService, IncomeService
from settings.utils import get_current_branch, get_current_tenant, is_branch_support_enabled
import logging

logger = logging.getLogger(__name__)


class IncomeCategoryViewSet(viewsets.ModelViewSet):
    queryset = IncomeCategory.objects.all()
    serializer_class = IncomeCategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category_service = IncomeCategoryService()

    def get_queryset(self):
        """Get queryset using service layer"""
        filters = {}
        if 'is_active' in self.request.query_params:
            filters['is_active'] = self.request.query_params.get('is_active')
        return self.category_service.build_queryset(filters)


class IncomeViewSet(viewsets.ModelViewSet):
    queryset = Income.objects.all().select_related('category', 'created_by', 'approved_by')
    serializer_class = IncomeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['income_number', 'description', 'payer', 'reference_number']
    ordering_fields = ['income_date', 'amount', 'created_at']
    ordering = ['-income_date', '-created_at']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.income_service = IncomeService()

    def get_queryset(self):
        """Get queryset using service layer - all query logic moved to service"""
        filters = {}
        query_params = self.request.query_params
        
        # Extract all filter parameters
        for param in ['branch_id', 'show_all', 'category', 'status', 'date_from', 'date_to', 'payment_method']:
            if param in query_params:
                filters[param] = query_params.get(param)
        
        return self.income_service.build_queryset(filters, request=self.request)

    def perform_create(self, serializer):
        # Get current branch only if branch support is enabled
        branch = None
        if is_branch_support_enabled():
            branch = get_current_branch(self.request)
        serializer.save(created_by=self.request.user, branch=branch)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve an income - thin view, business logic in service"""
        income = self.get_object()
        try:
            approved_income = self.income_service.approve_income(income, request.user)
            serializer = self.get_serializer(approved_income)
            return Response(serializer.data)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get income statistics - thin view, business logic in service"""
        current_branch = get_current_branch(request)
        stats = self.income_service.get_income_statistics(branch=current_branch)
        return Response(stats)
