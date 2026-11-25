# reports

## Purpose

Aggregated dashboards/exports over sales, stock, expenses, and income. No own domain tables — reads other apps via scoped query helpers.

## Key models

*(none)*

## Public APIs

Prefix: `/api/reports/`

## Bounds & invariants

- Sale reports use posted-sale scope helpers, not raw drafts.
- Feature flags/labels from module settings gate/annotate responses.
- Date filters should use inclusive start/end helpers from `services`.
- **Product performance** (`?report=product-performance` on Reports, and the product desk Performance tab) uses `/api/reports/product-trends/`. Gated by `enable_product_reports` + package feature `reports.product_trends`. Pick a primary SKU, add up to 4 peers (`compare_ids`), and choose any end month (`end=YYYY-MM`) or quarter (`end=YYYY-Qn`) — not only “through today”. Charts cover sold/received, revenue, channels, variant compare, multi-product lines, plus rule-based **purchase cues** for the next buy.
- **Product profitability** (`?report=products` + hub Top products): `/api/reports/products/` and `/api/reports/top_products/` return COGS, gross profit, and `margin_pct`, and accept `sort=gross_profit|margin_pct|revenue|quantity`. Package feature `reports.product_profitability` + `show_cost_and_profit` + `products.view_cost` (or admin). Shows which goods earn more for the business.

## Audit

Read-only; no domain mutations. Export endpoints may still log access if required by policy.

## Gaps

- Public API docstrings: **done** for ``sale_scope``, ``services`` (``resolve_period``, dashboard), and view helpers ``request_date_bounds`` / ``sale_report_queryset``; export/specialized report modules still partial.
