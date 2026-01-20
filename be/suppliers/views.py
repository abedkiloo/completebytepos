from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Sum, Avg, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal

from .models import Supplier
from .serializers import SupplierSerializer, SupplierListSerializer
from .services import SupplierService
from accounts.permissions import IsSuperAdmin, IsAdmin, HasPermission, HasModuleAccess
from settings.models import ModuleSettings


class HasSupplierPermission(permissions.BasePermission):
    """Check if user has supplier create or update permission, or is admin"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user is admin
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        if hasattr(request.user, 'profile'):
            # Check if user is admin via profile
            if request.user.profile.is_admin:
                return True
            
            # Check if user has create or update permission
            if request.user.profile.has_permission('suppliers', 'create'):
                return True
            if request.user.profile.has_permission('suppliers', 'update'):
                return True
        
        return False


class SupplierViewSet(viewsets.ModelViewSet):
    """Supplier management viewset"""
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'supplier_code', 'email', 'phone', 'contact_person', 'tax_id']
    ordering_fields = ['name', 'created_at', 'rating', 'account_balance']
    ordering = ['name']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.supplier_service = SupplierService()
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve']:
            # Anyone authenticated can view (if module enabled)
            # Check module access in get_queryset instead of blocking here
            return [IsAuthenticated()]
        elif self.action in ['create', 'update', 'partial_update']:
            # Admins and users with create/update permission can modify
            return [
                IsAuthenticated(), 
                HasModuleAccess('suppliers'),
                HasSupplierPermission()
            ]
        elif self.action == 'destroy':
            # Only admins can delete
            return [IsAuthenticated(), HasModuleAccess('suppliers'), IsAdmin()]
        return [IsAuthenticated()]
    
    def get_serializer_class(self):
        """Use lightweight serializer for list action"""
        if self.action == 'list':
            return SupplierListSerializer
        return SupplierSerializer
    
    def get_queryset(self):
        """Get queryset using service layer - all query logic moved to service"""
        # Check if suppliers module is enabled
        if not ModuleSettings.is_module_enabled('suppliers'):
            return Supplier.objects.none()
        
        filters = {}
        query_params = self.request.query_params
        
        # Extract all filter parameters
        for param in ['is_active', 'supplier_type', 'is_preferred', 'search']:
            if param in query_params:
                filters[param] = query_params.get(param)
        
        queryset = self.supplier_service.build_queryset(filters)
        
        # Handle min_rating filter (not in build_queryset yet)
        min_rating = query_params.get('min_rating')
        if min_rating:
            try:
                queryset = queryset.filter(rating__gte=int(min_rating))
            except ValueError:
                pass  # Invalid min_rating, ignore it
        
        return queryset
    
    def perform_create(self, serializer):
        """Set created_by when creating supplier"""
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get supplier statistics - thin view, business logic in service"""
        try:
            if not ModuleSettings.is_module_enabled('suppliers'):
                return Response({
                    'total_suppliers': 0,
                    'preferred_suppliers': 0,
                    'total_account_balance': 0.0,
                    'by_type': []
                })
            
            stats = self.supplier_service.get_all_supplier_statistics()
            
            # Add average rating calculation
            queryset = self.get_queryset()
            rating_agg = queryset.aggregate(
                avg_rating=Coalesce(Avg('rating'), Decimal('0'), output_field=DecimalField())
            )
            stats['average_rating'] = float(rating_agg['avg_rating'] or Decimal('0'))
            stats['active_suppliers'] = queryset.filter(is_active=True).count()
            
            return Response(stats)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'error': str(e),
                'total_suppliers': 0,
                'preferred_suppliers': 0,
                'total_account_balance': 0.0,
                'by_type': [],
                'average_rating': 0.0
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get all products from this supplier"""
        if not ModuleSettings.is_module_enabled('suppliers'):
            return Response({'error': 'Suppliers module is disabled'}, status=status.HTTP_403_FORBIDDEN)
        
        supplier = self.get_object()
        from products.models import Product
        from products.serializers import ProductListSerializer
        
        products = Product.objects.filter(supplier=supplier)
        serializer = ProductListSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)
