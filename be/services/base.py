"""
Base service classes for common patterns
"""
from typing import Optional, List, Dict, Any
from django.db import models
from django.db.models import QuerySet
from django.core.exceptions import ValidationError, ObjectDoesNotExist


class BaseService:
    """Base service class with common CRUD operations"""
    
    def __init__(self, model: models.Model):
        self.model = model
    
    def get(self, pk: int) -> models.Model:
        """Get a single object by primary key"""
        try:
            return self.model.objects.get(pk=pk)
        except self.model.DoesNotExist:
            raise ObjectDoesNotExist(f"{self.model.__name__} with pk={pk} does not exist")
    
    def get_or_none(self, pk: int) -> Optional[models.Model]:
        """Get a single object by primary key or return None"""
        try:
            return self.model.objects.get(pk=pk)
        except self.model.DoesNotExist:
            return None
    
    def list(self, filters: Optional[Dict[str, Any]] = None, 
             ordering: Optional[List[str]] = None) -> QuerySet:
        """List all objects with optional filters"""
        queryset = self.model.objects.all()
        
        if filters:
            queryset = queryset.filter(**filters)
        
        if ordering:
            queryset = queryset.order_by(*ordering)
        
        return queryset
    
    def create(self, data: Dict[str, Any], **kwargs) -> models.Model:
        """Create a new object"""
        try:
            return self.model.objects.create(**data, **kwargs)
        except Exception as e:
            raise ValidationError(f"Error creating {self.model.__name__}: {str(e)}")
    
    def update(self, instance: models.Model, data: Dict[str, Any]) -> models.Model:
        """Update an existing object"""
        for key, value in data.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
    def delete(self, instance: models.Model) -> bool:
        """Delete an object"""
        instance.delete()
        return True
    
    def bulk_create(self, items: List[Dict[str, Any]]) -> List[models.Model]:
        """Bulk create objects"""
        objects = [self.model(**item) for item in items]
        return self.model.objects.bulk_create(objects)
    
    def bulk_update(self, instances: List[models.Model], 
                   fields: List[str]) -> List[models.Model]:
        """Bulk update objects"""
        self.model.objects.bulk_update(instances, fields)
        return instances
    
    def bulk_delete(self, instances: List[models.Model]) -> int:
        """Bulk delete objects"""
        count = len(instances)
        for instance in instances:
            instance.delete()
        return count


class QueryService:
    """Service for complex queries and aggregations"""
    
    @staticmethod
    def filter_by_date_range(queryset: QuerySet, 
                           date_field: str,
                           date_from: Optional[str] = None,
                           date_to: Optional[str] = None) -> QuerySet:
        """Filter queryset by date range"""
        if date_from:
            queryset = queryset.filter(**{f"{date_field}__gte": date_from})
        if date_to:
            queryset = queryset.filter(**{f"{date_field}__lte": date_to})
        return queryset
    
    @staticmethod
    def aggregate_sum(queryset: QuerySet, field: str) -> float:
        """Sum a field across queryset"""
        from django.db.models import Sum
        result = queryset.aggregate(total=Sum(field))['total']
        return float(result) if result else 0.0
    
    @staticmethod
    def aggregate_count(queryset: QuerySet) -> int:
        """Count objects in queryset"""
        return queryset.count()
    
    @staticmethod
    def aggregate_avg(queryset: QuerySet, field: str) -> float:
        """Average a field across queryset"""
        from django.db.models import Avg
        result = queryset.aggregate(avg=Avg(field))['avg']
        return float(result) if result else 0.0
