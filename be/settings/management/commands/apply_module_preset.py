from django.core.management.base import BaseCommand

from settings.module_catalog import apply_module_preset
from settings.module_registry import get_preset_manifest


class Command(BaseCommand):
    help = 'Apply a module install preset (see module_registry.PRESETS)'

    def add_arguments(self, parser):
        parser.add_argument(
            'preset_id',
            type=str,
            help='Preset id, e.g. retail_starter, retail_full, finance_pack',
        )

    def handle(self, *args, **options):
        preset_id = options['preset_id']
        try:
            apply_module_preset(preset_id)
        except ValueError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            self.stdout.write('Available presets:')
            for p in get_preset_manifest():
                self.stdout.write(f"  - {p['id']}: {p['label']}")
            return
        self.stdout.write(self.style.SUCCESS(f'Applied preset "{preset_id}".'))
