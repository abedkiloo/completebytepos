from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0007_storesettings_maker_checker'),
    ]

    operations = [
        migrations.AddField(
            model_name='storesettings',
            name='maker_checker_sales_controls',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Optional future: require approval for limited post-completion sale edits '
                    '(notes/payment method). Does not affect POS checkout.'
                ),
            ),
        ),
    ]
