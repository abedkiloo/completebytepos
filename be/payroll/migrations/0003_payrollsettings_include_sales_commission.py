from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0002_role_pay_packages'),
    ]

    operations = [
        migrations.AddField(
            model_name='payrollsettings',
            name='include_sales_commission',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'Pull field-sales commission into earnings when calculating '
                    '(requires Payroll → Sales commission feature).'
                ),
            ),
        ),
    ]
