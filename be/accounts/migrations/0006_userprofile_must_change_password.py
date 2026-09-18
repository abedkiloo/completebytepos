from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_add_debt_management_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='must_change_password',
            field=models.BooleanField(
                default=False,
                help_text='If true, the user must choose a new password after signing in.',
            ),
        ),
    ]
