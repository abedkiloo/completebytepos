from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0016_permission_action_unvoid'),
    ]

    operations = [
        migrations.AddField(
            model_name='auditlog',
            name='client_channel',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text="Where the action ran: 'web', 'mobile', or 'unknown'.",
                max_length=16,
            ),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(
                fields=['client_channel', 'created_at'],
                name='accounts_au_client__7c2a1b_idx',
            ),
        ),
    ]
