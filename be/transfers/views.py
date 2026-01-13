from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count, Q
from .models import MoneyTransfer
from .serializers import MoneyTransferSerializer


class MoneyTransferViewSet(viewsets.ModelViewSet):
    queryset = MoneyTransfer.objects.all().select_related('from_account', 'to_account', 'created_by', 'approved_by')
    serializer_class = MoneyTransferSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['transfer_number', 'description', 'reference']
    ordering_fields = ['transfer_date', 'amount', 'created_at']
    ordering = ['-transfer_date', '-created_at']

    def get_queryset(self):
        queryset = MoneyTransfer.objects.all().select_related('from_account', 'to_account', 'created_by', 'approved_by')
        
        status_filter = self.request.query_params.get('status', None)
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        transfer_type = self.request.query_params.get('transfer_type', None)
        account = self.request.query_params.get('account', None)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if date_from:
            queryset = queryset.filter(transfer_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(transfer_date__lte=date_to)
        if transfer_type:
            queryset = queryset.filter(transfer_type=transfer_type)
        if account:
            queryset = queryset.filter(
                Q(from_account_id=account) | Q(to_account_id=account)
            )
        
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a transfer"""
        transfer = self.get_object()
        if transfer.status == 'completed':
            return Response(
                {'error': 'Transfer is already completed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        transfer.status = 'completed'
        transfer.approved_by = request.user
        transfer.save()
        
        serializer = self.get_serializer(transfer)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get transfer statistics"""
        total_transfers = MoneyTransfer.objects.filter(status='completed').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        by_type = MoneyTransfer.objects.filter(status='completed').values('transfer_type').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        by_status = MoneyTransfer.objects.values('status').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        return Response({
            'total_transferred': float(total_transfers),
            'by_type': list(by_type),
            'by_status': list(by_status),
        })
