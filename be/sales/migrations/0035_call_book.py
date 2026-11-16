import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0034_sale_pay_later_mpesa_destination_receipt'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CallBookSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('unlocated_weekday', models.PositiveSmallIntegerField(
                    default=0,
                    help_text='0=Monday … 4=Friday. Customers with no valid ward land here.',
                    validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(4)],
                )),
                ('hold_minutes', models.PositiveSmallIntegerField(
                    default=5,
                    help_text='Minutes a Call button reserves the customer. Range 1–30.',
                    validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(30)],
                )),
            ],
            options={
                'verbose_name': 'Call book settings',
                'verbose_name_plural': 'Call book settings',
            },
        ),
        migrations.CreateModel(
            name='CallDayPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weekday', models.PositiveSmallIntegerField(
                    help_text='0=Monday … 4=Friday. Saturday and Sunday are not call days.',
                    validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(4)],
                )),
                ('county', models.CharField(blank=True, default='', max_length=100)),
                ('sub_county', models.CharField(blank=True, default='', max_length=100)),
                ('ward', models.CharField(blank=True, default='', max_length=100)),
            ],
            options={
                'ordering': ['weekday', 'county', 'sub_county', 'ward'],
            },
        ),
        migrations.CreateModel(
            name='CustomerCall',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('called_at', models.DateTimeField(auto_now_add=True)),
                ('week_start', models.DateField(db_index=True, help_text='Monday of the call week in Africa/Nairobi.')),
                ('outcome', models.CharField(choices=[('called', 'Called'), ('ask_later', 'Ask later'), ('no_answer', 'No answer')], max_length=20)),
                ('request_summary', models.CharField(blank=True, default='', help_text='What they asked for, or a note to ask later. 0–500 characters.', max_length=500)),
                ('called_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='customer_calls', to=settings.AUTH_USER_MODEL)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='calls', to='sales.customer')),
            ],
            options={
                'ordering': ['-called_at'],
            },
        ),
        migrations.CreateModel(
            name='CallHold',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('customer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='call_hold', to='sales.customer')),
                ('held_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='call_holds', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name='customercall',
            index=models.Index(fields=['customer', 'week_start'], name='sales_custo_custome_call_idx'),
        ),
        migrations.AddIndex(
            model_name='customercall',
            index=models.Index(fields=['week_start', 'called_at'], name='sales_custo_week_st_call_idx'),
        ),
        migrations.AddConstraint(
            model_name='calldayplan',
            constraint=models.UniqueConstraint(fields=('county', 'sub_county', 'ward'), name='calldayplan_location_uniq'),
        ),
    ]
