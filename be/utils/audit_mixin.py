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
    """Auto-log create/update/destroy events for any DRF ModelViewSet."""

    audit_module: str | None = None

    def perform_create(self, serializer):
        return audited_perform_create(self, serializer)

    def perform_update(self, serializer):
        return audited_perform_update(self, serializer)

    def perform_destroy(self, instance):
        audited_perform_destroy(self, instance)
