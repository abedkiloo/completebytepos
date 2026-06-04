from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from .models import MoneyTransfer
from .serializers import MoneyTransferSerializer
from .services import MoneyTransferService
from accounts.permissions import RequirePermPerAction
from utils.audit_events import log_approval_event
from utils.audit_helpers import audited_perform_create, audited_perform_update
from approvals.financial_workflow import finalize_financial_create, prepare_financial_update
from utils.audit_mixin import AuditedModelViewSetMixin


TRANSFERS_PERMS = RequirePermPerAction('money_transfer', {
    'list': 'view',
    'retrieve': 'view',
    'create': 'create',
    'update': 'update',
    'partial_update': 'update',
    'destroy': 'delete',
    'statistics': 'view',
    'approve': 'approve',
    'reject': 'approve',
})


class MoneyTransferViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = MoneyTransfer.objects.all().select_related('from_account', 'to_account', 'created_by', 'approved_by')
    serializer_class = MoneyTransferSerializer
    permission_classes = [IsAuthenticated, TRANSFERS_PERMS]
    audit_module = 'money_transfer'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['transfer_number', 'description', 'reference']
    ordering_fields = ['transfer_date', 'amount', 'created_at']
    ordering = ['-transfer_date', '-created_at']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transfer_service = MoneyTransferService()

    def get_queryset(self):
        """Get queryset using service layer - all query logic moved to service"""
        filters = {}
        query_params = self.request.query_params
        
        # Extract all filter parameters
        for param in ['status', 'date_from', 'date_to', 'transfer_type', 'account']:
            if param in query_params:
                filters[param] = query_params.get(param)
        
        return self.transfer_service.build_queryset(filters)

    def perform_create(self, serializer):
        instance = audited_perform_create(self, serializer, created_by=self.request.user)
        finalize_financial_create(self.request, instance)

    def perform_update(self, serializer):
        prepare_financial_update(self.request, serializer.instance)
        audited_perform_update(self, serializer)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a transfer - thin view, business logic in service"""
        transfer = self.get_object()
        try:
            approved_transfer = self.transfer_service.approve_transfer(transfer, request.user)
            log_approval_event(request, approved_transfer, module='money_transfer')
            serializer = self.get_serializer(approved_transfer)
            return Response(serializer.data)
        except (ValidationError, DjangoValidationError) as e:
            detail = getattr(e, 'detail', None) or str(e)
            return Response({'error': detail}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get transfer statistics - thin view, business logic in service"""
        stats = self.transfer_service.get_transfer_statistics()
        return Response(stats)
