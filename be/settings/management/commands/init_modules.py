from django.core.management.base import BaseCommand

from settings.models import ModuleFeature, ModuleSettings
from settings.module_registry import MODULE_DEFINITIONS


class Command(BaseCommand):
    help = 'Initialize module settings and features from module_registry.py'

    def handle(self, *args, **options):
        self.stdout.write('Initializing modules from canonical registry…')

        for module_config in MODULE_DEFINITIONS:
            module, created = ModuleSettings.objects.get_or_create(
                module_name=module_config['module_name'],
                defaults={
                    'description': module_config.get('description', ''),
                    'is_enabled': module_config.get('default_enabled', True),
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Created module: {module.module_name}'))
            else:
                if module.description != module_config.get('description', ''):
                    module.description = module_config.get('description', '')
                    module.save(update_fields=['description'])

            for feature_config in module_config.get('features', []):
                enabled_default = feature_config.get('enabled_by_default', True)
                feature, feature_created = ModuleFeature.objects.get_or_create(
                    module=module,
                    feature_key=feature_config['key'],
                    defaults={
                        'feature_name': feature_config['name'],
                        'description': feature_config.get('description', ''),
                        'is_enabled': enabled_default,
                        'display_order': feature_config.get('order', 0),
                    },
                )
                if feature_created:
                    self.stdout.write(
                        self.style.SUCCESS(f'    + feature: {feature.feature_name}')
                    )
                else:
                    updated = False
                    if feature.feature_name != feature_config['name']:
                        feature.feature_name = feature_config['name']
                        updated = True
                    if feature.description != feature_config.get('description', ''):
                        feature.description = feature_config.get('description', '')
                        updated = True
                    if feature.display_order != feature_config.get('order', 0):
                        feature.display_order = feature_config.get('order', 0)
                        updated = True
                    if updated:
                        feature.save()

        from django.core.management import call_command

        call_command('init_module_settings', verbosity=0)
        self.stdout.write(self.style.SUCCESS('Module registry sync complete.'))
