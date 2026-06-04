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

    def user_message(self, attempted_name: str) -> str:
        cat = self.category
        status = 'inactive' if not cat.is_active else 'active'
        level = 'subcategory' if cat.parent_id else 'top-level category'
        return (
            f'A category named "{cat.name}" already exists ({status} {level}). '
            f'Set the list filter to All or Inactive to find it, or choose a different name.'
        )
