import inspect

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _check(q, name):
    """Build a CheckConstraint for Django 4 or 5."""
    cls = models.CheckConstraint
    params = inspect.signature(cls.__init__).parameters
    if 'condition' in params:
        return cls(condition=q, name=name)
    return cls(check=q, name=name)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('employees', '0004_employee_id_number'),
    ]

    operations = [
        migrations.CreateModel(
            name='LeaveRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('leave', 'Day off'), ('sick', 'Sick day')], max_length=8)),
                ('day', models.DateField()),
                ('note', models.CharField(blank=True, max_length=300)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], db_index=True, default='pending', max_length=12)),
                ('decision_note', models.CharField(blank=True, max_length=300)),
                ('decided_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('decided_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='leave_decisions', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leave_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='leaverequest',
            constraint=_check(models.Q(kind__in=['leave', 'sick']), 'leave_request_kind'),
        ),
        migrations.AddConstraint(
            model_name='leaverequest',
            constraint=_check(models.Q(status__in=['pending', 'approved', 'rejected']), 'leave_request_status'),
        ),
    ]
