from django.db import migrations


def create_permission(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.get_or_create(
        module='website',
        action='manage',
        defaults={
            'name': 'website.manage',
            'description': 'Write and publish website blog posts',
        },
    )


def remove_permission(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(module='website', action='manage').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0001_initial'),
        ('accounts', '0012_alter_permission_module'),
    ]

    operations = [
        migrations.RunPython(create_permission, remove_permission),
    ]
