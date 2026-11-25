# Same-day call claims: called_at is set by the book, not auto_now_add.

import django.core.validators
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0038_call_later_time"),
    ]

    operations = [
        migrations.AlterField(
            model_name="callbooksettings",
            name="hold_minutes",
            field=models.PositiveSmallIntegerField(
                default=5,
                help_text=(
                    "Legacy tuning field (1–30). Opening a customer now claims them "
                    "until the end of the Nairobi day regardless of this value."
                ),
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(30),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="customercall",
            name="called_at",
            field=models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
                help_text="When the call was recorded in Africa/Nairobi.",
            ),
        ),
    ]
