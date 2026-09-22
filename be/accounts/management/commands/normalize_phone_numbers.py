"""
Backfill stored phone numbers with the default country prefix (254).

  python manage.py normalize_phone_numbers --dry-run
  python manage.py normalize_phone_numbers
"""

from django.apps import apps
from django.core.management.base import BaseCommand

from utils.phone import PhoneNumberError, default_country_code, normalize_phone_number

PHONE_FIELDS = (
    ('sales', 'Customer', 'phone'),
    ('accounts', 'UserProfile', 'phone_number'),
    ('suppliers', 'Supplier', 'phone'),
    ('suppliers', 'Supplier', 'alternate_phone'),
    ('employees', 'Employee', 'phone'),
    ('settings', 'Tenant', 'phone'),
    ('settings', 'Branch', 'phone'),
    ('sales', 'Invoice', 'customer_phone'),
    ('payments', 'PaymentIntent', 'phone'),
    ('messaging', 'MessageOutbox', 'to_phone'),
)


class Command(BaseCommand):
    help = (
        'Normalize existing contact phone numbers with the default country '
        'prefix (254). Skips blank and invalid values.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        country = default_country_code()
        self.stdout.write(
            f'Normalizing phones with country prefix {country}'
            + (' (dry-run)' if dry_run else '')
            + '\n'
        )

        totals = {'scanned': 0, 'updated': 0, 'unchanged': 0, 'skipped': 0}
        for app_label, model_name, field in PHONE_FIELDS:
            try:
                model = apps.get_model(app_label, model_name)
            except LookupError:
                self.stdout.write(self.style.WARNING(
                    f'  skip {app_label}.{model_name}: model not installed'
                ))
                continue
            counts = self._normalize_model(model, field, dry_run=dry_run)
            for key in totals:
                totals[key] += counts[key]
            self.stdout.write(
                f'  {app_label}.{model_name}.{field}: '
                f'{counts["updated"]} updated, {counts["unchanged"]} unchanged, '
                f'{counts["skipped"]} skipped ({counts["scanned"]} scanned)'
            )

        verb = 'Would update' if dry_run else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'\n{verb} {totals["updated"]} numbers. '
            f'{totals["unchanged"]} already prefixed, {totals["skipped"]} skipped.'
        ))

    def _normalize_model(self, model, field, *, dry_run):
        counts = {'scanned': 0, 'updated': 0, 'unchanged': 0, 'skipped': 0}
        qs = model.objects.exclude(**{field: ''}).exclude(**{f'{field}__isnull': True})
        for instance in qs.iterator():
            counts['scanned'] += 1
            current = getattr(instance, field) or ''
            try:
                normalized = normalize_phone_number(current)
            except PhoneNumberError:
                counts['skipped'] += 1
                continue
            if not normalized or normalized == current:
                counts['unchanged'] += 1
                continue
            counts['updated'] += 1
            if dry_run:
                continue
            setattr(instance, field, normalized)
            update_fields = [field]
            if hasattr(instance, 'updated_at'):
                update_fields.append('updated_at')
            instance.save(update_fields=update_fields)
        return counts
