from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0006_expense_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='expense',
            name='needs_redo',
            field=models.BooleanField(
                default=False,
                help_text='Admin mark: this expense must be entered again.',
            ),
        ),
    ]
