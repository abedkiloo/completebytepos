"""
Drop-in DRF mixin that auto-writes ``AuditLog`` entries for every write
performed through a ``ModelViewSet``.

Usage:

    from utils.audit_mixin import AuditedModelViewSetMixin

    class SaleViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
        ...

The mixin overrides only the three side-effectful hooks - ``perform_create``,
``perform_update``, ``perform_destroy`` - so it never changes the queryset,
serializer, or response shape. Audit failure is swallowed (see ``log_audit``).
"""

from __future__ import annotations

from utils.audit import log_audit, diff_instance


class AuditedModelViewSetMixin:
    """Auto-log create/update/destroy events for any DRF ModelViewSet."""

    #: Optional override of the permission module used in AuditLog rows.
    #: Defaults to the model's app_label. Set this on the viewset when the
    #: app_label is misleading (e.g. ``CustomerViewSet`` lives in ``sales``
    #: but we want the audit row tagged as ``customers``).
    audit_module: str | None = None

    def perform_create(self, serializer):
        instance = serializer.save()
        log_audit(
            self.request,
            'create',
            instance,
            module=self.audit_module or '',
            changes={'__created__': self._safe_serialized(serializer)},
        )
        return instance

    def perform_update(self, serializer):
        before = serializer.instance
        # Snapshot fields BEFORE save - serializer.instance will be updated
        # in-place by .save().
        before_snapshot = self._snapshot(before)
        instance = serializer.save()
        log_audit(
            self.request,
            'update',
            instance,
            module=self.audit_module or '',
            changes=self._diff(before_snapshot, instance),
        )
        return instance

    def perform_destroy(self, instance):
        # Snapshot before delete - after delete the instance has no pk.
        snapshot = self._snapshot(instance)
        super().perform_destroy(instance) if hasattr(super(), 'perform_destroy') else instance.delete()
        log_audit(
            self.request,
            'delete',
            None,
            module=self.audit_module or instance._meta.app_label,
            object_repr=snapshot.get('__str__') if snapshot else None,
            changes={'__deleted__': snapshot},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_serialized(serializer):
        """Return serializer.data wrapped in a dict, or {} on failure."""
        try:
            return dict(serializer.data)
        except Exception:
            return {}

    @staticmethod
    def _snapshot(instance):
        """Return a plain ``model_to_dict``-style snapshot of the instance."""
        if instance is None:
            return {}
        try:
            from django.forms.models import model_to_dict
            snap = model_to_dict(instance)
            snap['__str__'] = str(instance)[:255]
            # Make all values JSON-safe.
            from utils.audit import _json_safe  # noqa: WPS437
            return {k: _json_safe(v) for k, v in snap.items()}
        except Exception:
            return {}

    @staticmethod
    def _diff(before_snapshot, after_instance):
        """Compute a diff dict between a snapshot and a model instance."""
        after_snapshot = AuditedModelViewSetMixin._snapshot(after_instance)
        diff: dict = {}
        for key in (before_snapshot.keys() | after_snapshot.keys()):
            if key.startswith('__'):
                continue
            if before_snapshot.get(key) != after_snapshot.get(key):
                diff[key] = {
                    'from': before_snapshot.get(key),
                    'to': after_snapshot.get(key),
                }
        return diff
