from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0003_merge_status_and_occurred_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='expense',
            name='include_in_trading_profit',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'When true (default), an approved expense is subtracted in trading profit. '
                    'Turn off for spend that should not affect trading P&L.'
                ),
            ),
        ),
        migrations.AddIndex(
            model_name='expense',
            index=models.Index(
                fields=['include_in_trading_profit', 'status'],
                name='expenses_ex_include_8a1b2c_idx',
            ),
        ),
    ]
