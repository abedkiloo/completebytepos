import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0019_customerwallettransaction_payment_method'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='customerwallettransaction',
            index=models.Index(
                fields=['source_type', 'created_at'],
                name='sales_custo_source__7c2a1b_idx',
            ),
        ),
        migrations.CreateModel(
            name='DebtSettlementAllocation',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'amount',
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal('0.01'))
                        ],
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'sale',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='debt_settlement_allocations',
                        to='sales.sale',
                    ),
                ),
                (
                    'wallet_transaction',
                    models.ForeignKey(
                        limit_choices_to={'source_type': 'debt_settlement'},
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='sale_allocations',
                        to='sales.customerwallettransaction',
                    ),
                ),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='debtsettlementallocation',
            index=models.Index(
                fields=['wallet_transaction'],
                name='sales_debts_wallet__a1b2c3_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='debtsettlementallocation',
            index=models.Index(
                fields=['sale'],
                name='sales_debts_sale_id_d4e5f6_idx',
            ),
        ),
    ]
