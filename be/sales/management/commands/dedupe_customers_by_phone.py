"""
Find (and optionally deactivate) active customers that share the same phone.

Keeps the duka with the most sales (then oldest). Clears phone on deactivated
rows so a later register cannot collide.

  python manage.py dedupe_customers_by_phone --dry-run
  python manage.py dedupe_customers_by_phone --apply
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from sales.customer_phones import find_duplicate_phone_groups
from sales.models import Customer


class Command(BaseCommand):
    help = (
        'List active customers that share a phone number. '
        'With --apply, deactivate duplicates and clear their phone.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show duplicate groups without changing data (default).',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Deactivate duplicate dukas and clear their phone field.',
        )

    def handle(self, *args, **options):
        apply = bool(options.get('apply'))
        dry_run = not apply or bool(options.get('dry_run'))
        if options.get('apply') and options.get('dry_run'):
            dry_run = True

        groups = find_duplicate_phone_groups(include_inactive=False)
        if not groups:
            self.stdout.write(self.style.SUCCESS('No duplicate active phones found.'))
            return

        self.stdout.write(
            f'Found {len(groups)} phone group(s) with duplicates'
            + (' (dry-run)' if dry_run else ' — applying')
            + ':\n'
        )
        deactivate_total = 0
        for group in groups:
            self.stdout.write(
                f"  {group['phone']}: keep #{group['keep_id']} {group['keep_name']!r}; "
                f"deactivate {group['deactivate_ids']} {group['deactivate_names']}"
            )
            deactivate_total += len(group['deactivate_ids'])

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\nDry-run only. Would deactivate {deactivate_total} duplicate duka(s). '
                    'Re-run with --apply to fix.'
                )
            )
            return

        with transaction.atomic():
            for group in groups:
                Customer.objects.filter(pk__in=group['deactivate_ids']).update(
                    is_active=False,
                    phone='',
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDeactivated {deactivate_total} duplicate duka(s) and cleared their phones. '
                f'Kept {len(groups)} primary record(s).'
            )
        )
