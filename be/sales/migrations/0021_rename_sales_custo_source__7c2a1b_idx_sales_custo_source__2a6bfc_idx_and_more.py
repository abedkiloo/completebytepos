# Align wallet/debt index names with Django autodetection (also present on VPS).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0020_debtsettlementallocation_and_wallet_indexes'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='customerwallettransaction',
            new_name='sales_custo_source__2a6bfc_idx',
            old_name='sales_custo_source__7c2a1b_idx',
        ),
        migrations.RenameIndex(
            model_name='debtsettlementallocation',
            new_name='sales_debts_wallet__ac95ce_idx',
            old_name='sales_debts_wallet__a1b2c3_idx',
        ),
        migrations.RenameIndex(
            model_name='debtsettlementallocation',
            new_name='sales_debts_sale_id_2d26dc_idx',
            old_name='sales_debts_sale_id_d4e5f6_idx',
        ),
    ]
