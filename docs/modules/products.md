# products

## Purpose

Product catalog: categories, sizes/colors, units, products, and variants. Owns sellable qty/price/cost helpers and role-based field stripping. **Stock deltas belong in inventory/sales**, not ad-hoc catalog edits (except permitted stock fields).

## Key models

| Model | Role |
|-------|------|
| `Category` | Tree (parent/child) |
| `Size` / `Color` / `UnitOfMeasure` | Variant dimensions / units |
| `Product` | SKU/barcode, price/cost, stock, tax |
| `ProductVariant` | Size×color row with own sku/price/cost/stock |

## Public entry points

- `ProductService` / `ProductVariantService` create/update/bulk/CSV
- `sellable_stock_quantity` / `sellable_unit_price` / `build_variant_sku`
- HTTP: `/api/products/` (products, categories, sizes, colors, units, variants)

## Bounds & invariants

- Create product + variants in **one** `transaction.atomic()`.
- Duplicate product **names** → 400. SKU/barcode unique.
- Stock/price/cost ≥ 0 (DB check on stock).
- Variant parents: sellable stock is variant-level for POS.
- Hard delete blocked if stock/history/sales usage exists.

## Audit

Catalog ViewSets use `AuditedModelViewSetMixin`. Single-product writes also use `log_product_write`.

## Gaps

- Bulk activate/deactivate/CSV import may not emit per-row audit events.
- Legacy `supplier_name` coexists with supplier FK.
