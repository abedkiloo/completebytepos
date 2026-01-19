# Generated manually to add supplier FK to existing products table
# Uses RunSQL to avoid dependency issues

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_rename_products_pr_sku_idx_products_pr_sku_ca0cdc_idx_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            # Add the column if it doesn't exist
            sql="ALTER TABLE products_product ADD COLUMN supplier_id INTEGER REFERENCES suppliers_supplier(id);",
            reverse_sql="ALTER TABLE products_product DROP COLUMN supplier_id;",
        ),
    ]
