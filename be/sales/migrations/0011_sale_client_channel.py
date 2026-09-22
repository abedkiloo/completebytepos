from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0010_rename_sales_sale_occurre_91a2f1_idx_sales_sale_occurre_f971c6_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='sale',
            name='client_channel',
            field=models.CharField(
                choices=[
                    ('web', 'Web'),
                    ('mobile', 'Mobile app'),
                    ('unknown', 'Unknown'),
                ],
                db_index=True,
                default='unknown',
                help_text='Whether this sale was recorded from the web POS or the mobile app.',
                max_length=16,
            ),
        ),
    ]
