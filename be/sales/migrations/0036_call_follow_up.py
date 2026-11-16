from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0035_call_book'),
    ]

    operations = [
        migrations.AddField(
            model_name='customercall',
            name='follow_up_on',
            field=models.DateField(
                blank=True,
                help_text='Optional date to call again. Blank, or today through 90 days ahead.',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='customercall',
            name='outcome',
            field=models.CharField(
                choices=[
                    ('called', 'Called'),
                    ('ask_later', 'Call later'),
                    ('no_answer', 'No answer'),
                    ('unreachable', 'Unreachable'),
                ],
                max_length=20,
            ),
        ),
    ]
