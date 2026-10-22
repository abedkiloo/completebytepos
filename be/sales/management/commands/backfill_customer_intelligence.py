"""Recompute denormalized buyer/prospect tiers for all customers."""

from django.core.management.base import BaseCommand

from sales.customer_intelligence import backfill_customer_intelligence


class Command(BaseCommand):
    help = (
        'Backfill engagement_tier / buyer_segment / purchase stats on Customer '
        '(safe to re-run; uses completed sales only).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Customers processed between progress logs (default 500).',
        )

    def handle(self, *args, **options):
        result = backfill_customer_intelligence(batch_size=options['batch_size'])
        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {result['processed']} customers — "
                f"{result['buyers']} buyers, {result['prospects']} prospects."
            )
        )
