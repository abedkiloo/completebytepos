"""
Drop-in DRF mixin that auto-writes ``AuditLog`` entries for every write
performed through a ``ModelViewSet``.
"""

from __future__ import annotations

from utils.audit_helpers import (
    audited_perform_create,
    audited_perform_destroy,
    audited_perform_update,
)


class AuditedModelViewSetMixin:
    """
    Drop-in DRF mixin that audits create, update, and destroy hooks.

    Set ``audit_module`` on the viewset to override the default app label used
    on ``AuditLog.module``. Does not audit custom ``@action`` endpoints — call
    ``log_domain_event`` there.

    Attributes:
        audit_module: Optional permission module string (e.g. ``'sales'``).
    """

    audit_module: str | None = None

    def perform_create(self, serializer):
        """Delegate to ``audited_perform_create``."""
        return audited_perform_create(self, serializer)

    def perform_update(self, serializer):
        """Delegate to ``audited_perform_update``."""
        return audited_perform_update(self, serializer)

    def perform_destroy(self, instance):
        """Delegate to ``audited_perform_destroy``."""
        audited_perform_destroy(self, instance)
