from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0004_expense_include_in_trading_profit'),
    ]

    operations = [
        migrations.AddField(
            model_name='expensecategory',
            name='include_in_trading_profit',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'When true (default), approved expenses in this category are subtracted '
                    'in trading profit. Turn off for categories that should not affect trading P&L '
                    '(e.g. owner drawings).'
                ),
            ),
        ),
        migrations.RemoveIndex(
            model_name='expense',
            name='expenses_ex_include_8a1b2c_idx',
        ),
        migrations.RemoveField(
            model_name='expense',
            name='include_in_trading_profit',
        ),
    ]
