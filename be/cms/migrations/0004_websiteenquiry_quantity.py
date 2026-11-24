from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0003_website_enquiry'),
    ]

    operations = [
        migrations.AddField(
            model_name='websiteenquiry',
            name='quantity',
            field=models.CharField(
                blank=True,
                help_text='Amount or quantity the visitor asked for (1–80 characters).',
                max_length=80,
            ),
        ),
    ]
