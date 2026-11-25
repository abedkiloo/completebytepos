from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0004_payrollsettings_sales_commission_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='payrollsettings',
            name='prorate_mid_join',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'When on, employees hired mid-period receive proportional basic '
                    '(join halfway ≈ half salary). Requires the mid_join_proration '
                    'module feature.'
                ),
            ),
        ),
        migrations.AddField(
            model_name='payrollsettings',
            name='min_month_days',
            field=models.PositiveSmallIntegerField(
                default=28,
                help_text=(
                    'Minimum days treated as a full pay month (at least 4 weeks = 28). '
                    'Proration uses max(calendar days in period, this value). '
                    'Range 28–31.'
                ),
            ),
        ),
    ]
