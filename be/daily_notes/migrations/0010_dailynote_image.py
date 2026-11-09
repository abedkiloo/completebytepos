from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('daily_notes', '0009_dailynote_dailytask_priority'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailynote',
            name='image',
            field=models.ImageField(
                blank=True,
                help_text='Optional photo attached to this note (receipt, damage, handover proof).',
                null=True,
                upload_to='daily_notes/',
            ),
        ),
    ]
