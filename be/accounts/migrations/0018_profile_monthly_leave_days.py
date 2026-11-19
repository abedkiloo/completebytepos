from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0017_auditlog_client_channel'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='monthly_leave_days',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Days off allowed each month for this person. Empty uses the shop number. 0–31.',
                null=True,
            ),
        ),
    ]
