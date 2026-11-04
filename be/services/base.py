"""
Shared service base classes for Django app services.

Public entry points:
    - ``BaseService`` — generic CRUD helpers bound to a model class
    - ``QueryService`` — date-range filters and simple aggregates

No audit or permission checks — callers enforce domain rules in app services.
"""
from typing import Optional, List, Dict, Any
from django.db import models
from django.db.models import QuerySet
from django.core.exceptions import ValidationError, ObjectDoesNotExist


class BaseService:
    """
    Generic CRUD helpers for a single Django model.

    Subclasses set ``model`` via ``super().__init__(ModelClass)``. Methods operate
    on the default manager unless overridden in subclasses.

    Attributes:
        model: Django model class bound at init.
    """

    def __init__(self, model: models.Model):
        """
        Bind this service instance to a model class.

        Args:
            model: Django model class (not an instance).
        """
        self.model = model

    def get(self, pk: int) -> models.Model:
        """
        Fetch one row by primary key.

        Args:
            pk: Integer primary key.

        Returns:
            Model instance.

        Raises:
            ObjectDoesNotExist: When no row matches ``pk``.
        """
        try:
            return self.model.objects.get(pk=pk)
        except self.model.DoesNotExist:
            raise ObjectDoesNotExist(f"{self.model.__name__} with pk={pk} does not exist")

    def get_or_none(self, pk: int) -> Optional[models.Model]:
        """
        Fetch one row by primary key or return ``None``.

        Args:
            pk: Integer primary key.

        Returns:
            Instance or ``None`` when missing.
        """
        try:
            return self.model.objects.get(pk=pk)
        except self.model.DoesNotExist:
            return None

    def list(self, filters: Optional[Dict[str, Any]] = None,
             ordering: Optional[List[str]] = None) -> QuerySet:
        """
        List rows with optional ORM filter kwargs and ordering.

        Args:
            filters: Passed to ``QuerySet.filter(**filters)`` when non-empty.
            ordering: Field names for ``order_by``; omitted leaves model default order.

        Returns:
            Unevaluated ``QuerySet`` (may be empty).
        """
        queryset = self.model.objects.all()

        if filters:
            queryset = queryset.filter(**filters)

        if ordering:
            queryset = queryset.order_by(*ordering)

        return queryset

    def create(self, data: Dict[str, Any], **kwargs) -> models.Model:
        """
        Insert one row via ``objects.create``.

        Args:
            data: Model field kwargs.
            **kwargs: Additional field kwargs merged into create.

        Returns:
            Saved instance.

        Raises:
            ValidationError: Wraps any underlying DB/validation error message.
        """
        try:
            return self.model.objects.create(**data, **kwargs)
        except Exception as e:
            raise ValidationError(f"Error creating {self.model.__name__}: {str(e)}")

    def update(self, instance: models.Model, data: Dict[str, Any]) -> models.Model:
        """
        Apply in-memory field updates and save.

        Args:
            instance: Existing model instance.
            data: ``setattr`` map of field names to values.

        Returns:
            Same instance after ``save()``.
        """
        for key, value in data.items():
            setattr(instance, key, value)
        instance.save()
        return instance

    def delete(self, instance: models.Model) -> bool:
        """
        Delete one instance.

        Args:
            instance: Row to remove.

        Returns:
            ``True`` after successful delete.
        """
        instance.delete()
        return True

    def bulk_create(self, items: List[Dict[str, Any]]) -> List[models.Model]:
        """
        Bulk insert unsaved dict payloads.

        Args:
            items: List of field dicts; empty list yields empty result without IO.

        Returns:
            List of instances returned by ``bulk_create`` (PKs set when supported).
        """
        objects = [self.model(**item) for item in items]
        return self.model.objects.bulk_create(objects)

    def bulk_update(self, instances: List[models.Model],
                   fields: List[str]) -> List[models.Model]:
        """
        Bulk update the given fields on saved instances.

        Args:
            instances: Saved rows to update (may be empty).
            fields: Model field names passed to ``bulk_update``.

        Returns:
            Same ``instances`` list after update.
        """
        self.model.objects.bulk_update(instances, fields)
        return instances

    def bulk_delete(self, instances: List[models.Model]) -> int:
        """
        Delete each instance in a loop (not a single SQL DELETE).

        Args:
            instances: Rows to delete.

        Returns:
            Count deleted (length of input list).
        """
        count = len(instances)
        for instance in instances:
            instance.delete()
        return count


class QueryService:
    """Static helpers for date-bounded querysets and aggregates."""

    @staticmethod
    def filter_by_date_range(queryset: QuerySet,
                           date_field: str,
                           date_from: Optional[str] = None,
                           date_to: Optional[str] = None) -> QuerySet:
        """
        Apply inclusive string date bounds on a datetime/date field.

        Args:
            queryset: Base queryset to filter.
            date_field: ORM field name (without lookup suffix).
            date_from: Lower bound string for ``__gte`` when set.
            date_to: Upper bound string for ``__lte`` when set.

        Returns:
            Filtered queryset (unchanged when both bounds omitted).
        """
        if date_from:
            queryset = queryset.filter(**{f"{date_field}__gte": date_from})
        if date_to:
            queryset = queryset.filter(**{f"{date_field}__lte": date_to})
        return queryset

    @staticmethod
    def aggregate_sum(queryset: QuerySet, field: str) -> float:
        """
        Sum a numeric field across the queryset.

        Args:
            queryset: Rows to aggregate.
            field: Numeric model field name.

        Returns:
            ``float`` total, or ``0.0`` when null/empty.
        """
        from django.db.models import Sum
        result = queryset.aggregate(total=Sum(field))['total']
        return float(result) if result else 0.0

    @staticmethod
    def aggregate_count(queryset: QuerySet) -> int:
        """
        Count rows in the queryset.

        Returns:
            Non-negative integer (SQL ``COUNT``).
        """
        return queryset.count()

    @staticmethod
    def aggregate_avg(queryset: QuerySet, field: str) -> float:
        """
        Average a numeric field across the queryset.

        Args:
            queryset: Rows to aggregate.
            field: Numeric model field name.

        Returns:
            ``float`` average, or ``0.0`` when null/empty.
        """
        from django.db.models import Avg
        result = queryset.aggregate(avg=Avg(field))['avg']
        return float(result) if result else 0.0
