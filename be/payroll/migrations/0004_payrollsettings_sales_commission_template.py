from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0003_payrollsettings_include_sales_commission'),
    ]

    operations = [
        migrations.AddField(
            model_name='payrollsettings',
            name='sales_commission_template',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    'Editable daily commission template (bands + transport). '
                    'Empty uses the Omuwenga PDF starter defaults.'
                ),
            ),
        ),
        migrations.AlterField(
            model_name='payrollsettings',
            name='include_sales_commission',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'Pull sales-agent commission into earnings when calculating '
                    '(default: daily band template; editable under sales_commission_template)'
                ),
            ),
        ),
    ]
