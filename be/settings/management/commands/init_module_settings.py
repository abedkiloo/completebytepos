from django.core.management.base import BaseCommand

from settings.models import ModuleSetting
from settings.module_settings_registry import MODULE_SETTING_DEFINITIONS


class Command(BaseCommand):
    help = 'Seed per-module settings from module_settings_registry (fresh installs only).'

    def handle(self, *args, **options):
        self.stdout.write('Syncing module settings from registry…')
        created_count = 0
        for module, definitions in MODULE_SETTING_DEFINITIONS.items():
            for definition in definitions:
                _row, created = ModuleSetting.objects.update_or_create(
                    module=module,
                    key=definition['key'],
                    defaults={
                        'label': definition['label'],
                        'description': definition.get('description', ''),
                        'default_value': definition['default_value'],
                        'display_order': definition.get('display_order', 0),
                    },
                )
                if created:
                    _row.value = definition['default_value']
                    _row.save(update_fields=['value'])
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  + {module}.{definition["key"]}')
                    )
                else:
                    changed = []
                    for field in ('label', 'description', 'display_order'):
                        new_val = definition.get(field, getattr(_row, field))
                        if getattr(_row, field) != new_val:
                            setattr(_row, field, new_val)
                            changed.append(field)
                    if changed:
                        _row.save(update_fields=changed)
        self.stdout.write(
            self.style.SUCCESS(f'Module settings sync complete ({created_count} new).')
        )
