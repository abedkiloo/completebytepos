"""
Drop-in DRF mixins that auto-write ``AuditLog`` for CRUD and detail reads.
"""

from __future__ import annotations

from rest_framework.response import Response

from utils.audit_helpers import (
    audited_perform_create,
    audited_perform_destroy,
    audited_perform_update,
    log_sensitive_read,
)


class AuditedRetrieveMixin:
    """
    Opt-in detail-read auditing for viewsets that already log writes manually.

    Attributes:
        audit_module: Optional module string on ``AuditLog``.
        audit_reads: When False, skip view logging (default True).
    """

    audit_module: str | None = None
    audit_reads: bool = True

    def retrieve(self, request, *args, **kwargs):
        """
        Return one object and optionally append a ``view`` audit row.

        Args:
            request: DRF request.
            *args: Positional route args.
            **kwargs: Keyword route args.

        Returns:
            ``Response`` with serialized detail payload.
        """
        instance = self.get_object()
        if getattr(self, 'audit_reads', True):
            module = getattr(self, 'audit_module', None) or ''
            log_sensitive_read(
                request,
                instance,
                module=module,
                purpose='detail',
            )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class AuditedModelViewSetMixin(AuditedRetrieveMixin):
    """
    Drop-in DRF mixin that audits create, update, destroy, and (optionally) retrieve.

    Set ``audit_module`` on the viewset to override the default app label used
    on ``AuditLog.module``. Does not audit custom ``@action`` endpoints — call
    ``log_domain_event`` there.

    Detail reads (``retrieve``) are logged as ``view`` when ``audit_reads`` is
    True (default) and package feature ``settings.audit_sensitive_reads`` is on.
    Lists are never logged. Deduped per user/object (~5 minutes).

    For next modules: inherit this mixin on every ``ModelViewSet`` that owns
    money, PII, or permissioned records. Set ``audit_reads = False`` on
    high-churn catalog endpoints (products search/detail in POS).

    Attributes:
        audit_module: Optional permission module string (e.g. ``'sales'``).
        audit_reads: When False, skip detail-view logging.
    """

    audit_module: str | None = None
    audit_reads: bool = True

    def perform_create(self, serializer):
        """Delegate to ``audited_perform_create``."""
        return audited_perform_create(self, serializer)

    def perform_update(self, serializer):
        """Delegate to ``audited_perform_update``."""
        return audited_perform_update(self, serializer)

    def perform_destroy(self, instance):
        """Delegate to ``audited_perform_destroy``."""
        audited_perform_destroy(self, instance)
