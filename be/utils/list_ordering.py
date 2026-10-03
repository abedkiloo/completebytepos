"""Name + saved-date ranking for list APIs.

Clients pass ``?ordering=name`` / ``-name`` / ``saved`` / ``-saved``.
``saved`` always means the row's save timestamp (``created_at``, or
``date_joined`` on users). ``name`` maps to the model's display name,
including related customer/product names when there is no local name field.
"""

from __future__ import annotations

from rest_framework import filters

DEFAULT_ALIASES = {
    'saved': 'created_at',
}

_NAME_FIELD_CANDIDATES = (
    'name',
    'title',
    'account_name',
    'customer_name',
    'label',
    'username',
    'description',
    'sale_number',
    'invoice_number',
    'transfer_number',
    'object_repr',
    'module',
)


def _field_names(model) -> set[str]:
    try:
        return {field.name for field in model._meta.get_fields()}
    except Exception:
        return set()


def infer_name_target(model, aliases: dict | None = None):
    aliases = aliases or {}
    if 'name' in aliases:
        return aliases['name']
    names = _field_names(model)
    if 'name' in names:
        return 'name'
    if 'first_name' in names:
        return ('first_name', 'last_name') if 'last_name' in names else 'first_name'
    if 'customer' in names:
        return 'customer__name'
    if 'product' in names:
        return 'product__name'
    if 'invoice' in names:
        return 'invoice__invoice_number'
    for candidate in _NAME_FIELD_CANDIDATES:
        if candidate == 'name':
            continue
        if candidate in names:
            return candidate
    return None


def infer_saved_target(model, aliases: dict | None = None):
    aliases = aliases or {}
    if 'saved' in aliases:
        return aliases['saved']
    names = _field_names(model)
    if 'created_at' in names:
        return 'created_at'
    if 'date_joined' in names:
        return 'date_joined'
    return None


def resolve_aliases(model, extra: dict | None = None) -> dict:
    aliases = dict(DEFAULT_ALIASES)
    if extra:
        aliases.update(extra)
    name_target = infer_name_target(model, aliases)
    if name_target is not None:
        aliases['name'] = name_target
    saved_target = infer_saved_target(model, aliases)
    if saved_target is not None:
        aliases['saved'] = saved_target
    return aliases


def map_ordering_fields(fields, aliases: dict | None = None) -> list[str]:
    aliases = aliases or {}
    mapped: list[str] = []
    for field in fields:
        if not field:
            continue
        descending = str(field).startswith('-')
        key = str(field).lstrip('-')
        target = aliases.get(key, key)
        prefix = '-' if descending else ''
        if isinstance(target, (list, tuple)):
            mapped.extend(f'{prefix}{part}' for part in target if part)
        else:
            mapped.append(f'{prefix}{target}')
    return mapped


def mapped_ordering(
    ordering: str | None,
    *,
    aliases: dict | None = None,
    allowed: set[str] | None = None,
    default=None,
) -> list[str]:
    """Map a query ``ordering`` string to ORM order_by fields."""
    aliases = {**DEFAULT_ALIASES, **(aliases or {})}
    raw = (ordering or '').strip()
    if not raw:
        if default is None:
            return []
        if isinstance(default, str):
            return [default]
        return list(default)

    requested = [part.strip() for part in raw.split(',') if part.strip()]
    if allowed is not None:
        valid = []
        for field in requested:
            key = field.lstrip('-')
            if key in allowed or key in aliases:
                valid.append(field)
        requested = valid
        if not requested:
            if default is None:
                return []
            if isinstance(default, str):
                return [default]
            return list(default)
    return map_ordering_fields(requested, aliases)


class NameSavedOrderingFilter(filters.OrderingFilter):
    """OrderingFilter that always accepts ``name`` and ``saved`` aliases."""

    def get_valid_fields(self, queryset, view, context=None):
        aliases = resolve_aliases(
            getattr(queryset, 'model', None),
            getattr(view, 'ordering_aliases', None),
        )
        declared = getattr(view, 'ordering_fields', self.ordering_fields)
        if declared == '__all__':
            existing = super().get_valid_fields(queryset, view, context=context)
        elif declared:
            existing = [
                (item, item) if isinstance(item, str) else item
                for item in declared
            ]
        else:
            existing = []

        seen = {item[0] for item in existing}
        extra = []
        for key in ('name', 'saved', 'created_at', 'date_joined'):
            if key in seen:
                continue
            if key in aliases or (declared and key in {
                item[0] for item in existing
            }):
                extra.append((key, key))
                seen.add(key)
                continue
            target = aliases.get(key)
            if target:
                extra.append((key, key))
                seen.add(key)
        return existing + extra

    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        if not ordering:
            return ordering
        aliases = resolve_aliases(
            getattr(queryset, 'model', None),
            getattr(view, 'ordering_aliases', None),
        )
        return map_ordering_fields(ordering, aliases)
