"""Ensure customer editing is on so the mobile app can update dukas."""

from django.db import migrations


def enable_customer_edit(apps, schema_editor):
    ModuleSetting = apps.get_model('settings', 'ModuleSetting')
    ModuleSetting.objects.update_or_create(
        module='customers',
        key='enable_customer_edit',
        defaults={
            'label': 'Allow editing customers',
            'description': 'When off, existing customer records cannot be updated.',
            'default_value': True,
            'value': True,
            'display_order': 11,
        },
    )


def noop_reverse(apps, schema_editor):
    # Keep edit enabled on reverse; admins can toggle in Module Settings.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0029_customer_gender'),
        ('settings', '0005_modulesetting'),
    ]

    operations = [
        migrations.RunPython(enable_customer_edit, noop_reverse),
    ]
