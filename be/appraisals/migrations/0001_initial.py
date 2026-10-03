from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AppraisalSalaryIncrement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.PositiveIntegerField()),
                ('role_name', models.CharField(blank=True, max_length=120)),
                ('previous_basic', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('increment_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('new_basic', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('annual_average', models.FloatField(default=0)),
                ('four_star_months', models.PositiveSmallIntegerField(default=0)),
                ('four_star_months_required', models.PositiveSmallIntegerField(default=8)),
                ('qualifies', models.BooleanField(default=False)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending approval'),
                        ('approved', 'Approved'),
                        ('rejected', 'Rejected'),
                        ('not_eligible', 'Not eligible'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('effective_date', models.DateField(blank=True, null=True)),
                ('reason', models.CharField(blank=True, max_length=500)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='appraisal_increments_approved',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='appraisal_increments',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-year', 'user_id'],
                'unique_together': {('user', 'year')},
            },
        ),
    ]
