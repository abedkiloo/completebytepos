from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0037_field_load_sale_origin'),
    ]

    operations = [
        migrations.AddField(
            model_name='customercall',
            name='follow_up_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When a call-later should return to the top of the list. Blank unless the outcome is call later.',
                null=True,
            ),
        ),
    ]
