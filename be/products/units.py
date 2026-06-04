"""Unit of measure registry and validation."""

from __future__ import annotations

from django.core.exceptions import ValidationError

from products.models import UnitOfMeasure

BUILTIN_UNITS: list[tuple[str, str, int]] = [
    ('piece', 'Piece', 1),
    ('kg', 'Kilogram', 2),
    ('g', 'Gram', 3),
    ('l', 'Liter', 4),
    ('ml', 'Milliliter', 5),
    ('box', 'Box', 6),
    ('pack', 'Pack', 7),
    ('bottle', 'Bottle', 8),
    ('can', 'Can', 9),
    ('roll', 'Roll', 10),
]


def ensure_builtin_units() -> None:
    for code, label, order in BUILTIN_UNITS:
        UnitOfMeasure.objects.update_or_create(
            code=code,
            defaults={
                'label': label,
                'display_order': order,
                'is_active': True,
            },
        )


def list_active_units() -> list[dict[str, str]]:
    ensure_builtin_units()
    return [
        {'code': row.code, 'label': row.label}
        for row in UnitOfMeasure.objects.filter(is_active=True).order_by(
            'display_order', 'label'
        )
    ]


def normalize_unit_code(raw: str | None) -> str:
    return str(raw or '').strip().lower()


def validate_unit_code(code: str | None) -> str:
    normalized = normalize_unit_code(code)
    if not normalized:
        raise ValidationError({'unit': 'Unit of measure is required.'})
    ensure_builtin_units()
    if not UnitOfMeasure.objects.filter(code=normalized, is_active=True).exists():
        raise ValidationError(
            {'unit': f'Unknown or inactive unit "{normalized}". Add it under Products → Units.'}
        )
    return normalized


def create_unit(code: str, label: str) -> UnitOfMeasure:
    normalized = normalize_unit_code(code)
    if not normalized:
        raise ValidationError({'code': 'Unit code is required.'})
    if not str(label or '').strip():
        raise ValidationError({'label': 'Unit label is required.'})
    row, _created = UnitOfMeasure.objects.update_or_create(
        code=normalized,
        defaults={
            'label': str(label).strip(),
            'is_active': True,
            'display_order': UnitOfMeasure.objects.count() + 1,
        },
    )
    return row
