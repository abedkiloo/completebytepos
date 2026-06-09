"""Category name normalization and duplicate detection."""

from __future__ import annotations

import re
from typing import Optional

from products.models import Category


def normalize_category_name(name: str) -> str:
    """Strip and collapse whitespace for consistent search and uniqueness."""
    if name is None:
        return ''
    return re.sub(r'\s+', ' ', str(name)).strip()


def find_duplicate_category(
    name: str,
    *,
    exclude_pk: Optional[int] = None,
):
    """Case-insensitive name lookup (DB unique constraint is case-sensitive)."""
    normalized = normalize_category_name(name)
    if not normalized:
        return None
    qs = Category.objects.filter(name__iexact=normalized)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.select_related('parent').first()


class DuplicateCategoryInfo:
    def __init__(self, category: Category):
        self.category = category

    def user_message(
        self,
        attempted_name: str,
        *,
        attempted_parent_id: Optional[int] = None,
    ) -> str:
        cat = self.category
        display_name = cat.name

        if not cat.is_active:
            level = 'subcategory' if cat.parent_id else 'top-level category'
            parent_hint = ''
            if cat.parent_id and cat.parent:
                parent_hint = f' under {cat.parent.name}'
            return (
                f'A category named "{display_name}" already exists{parent_hint} '
                f'but is inactive ({level}). '
                f'Open Categories, set the filter to All or Inactive to find it, '
                f'or choose a different name.'
            )

        if cat.parent_id:
            parent_name = cat.parent.name if cat.parent else 'another category'
            if (
                attempted_parent_id is not None
                and cat.parent_id == attempted_parent_id
            ):
                return (
                    f'"{display_name}" is already a subcategory under {parent_name}. '
                    f'Select it from the subcategory list instead of creating a new one.'
                )
            return (
                f'"{display_name}" already exists as a subcategory under {parent_name}. '
                f'Category names must be unique across the store — choose a different name.'
            )

        if attempted_parent_id:
            return (
                f'"{display_name}" already exists as a top-level category. '
                f'You cannot reuse that name for a subcategory.'
            )

        return (
            f'"{display_name}" already exists as a top-level category. '
            f'Choose a different name.'
        )
