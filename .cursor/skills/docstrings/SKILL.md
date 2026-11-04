---
name: docstrings
description: >-
  Write and maintain Google-style docstrings and module summaries for
  CompleteBytePOS (Python/Django BE and JS/TS/Dart FE). Use when creating or
  editing any function, class, method, module, ViewSet, service, serializer,
  React component, or Flutter widget; when documenting modules; when the user
  asks for docs, coverage of documentation, or clearer code reading.
---

# Docstrings & module documentation

Every **new** and **edited** public function, method, class, or module file must
carry a docstring that makes future reading easy without guessing. During a
module documentation pass, bring **existing** public APIs in that module up to
the same standard even when behavior is unchanged.

## When this applies

- Adding or changing Python under `be/`
- Adding or changing significant JS/TS under `fe/src/` or Dart under `mobile/`
- Module-by-module documentation / coverage passes (existing code included)
- Refactors that rename or change signatures (update the docstring in the same change)

Private helpers (`_foo`) may use a one-line docstring; still state purpose and
non-obvious bounds.

## Required content (Python)

Use **Google style**. Include at least:

| Section | Required | What to write |
|---------|----------|----------------|
| Summary | Always | One line: what it does (imperative or present tense). |
| Extended | When non-obvious | Why it exists, side effects (DB writes, stock, audit, journals). |
| `Args` | Always if params | Name, type, meaning, units, defaults. |
| `Returns` | Always if returns | Type and meaning. Use `None` explicitly when void. |
| `Raises` | When it can fail | Exception type + when (validation, 404, conflict). |
| Bounds / limits | Always when numeric or size-related | Min/max, inclusive ranges, empty-list behavior, pagination caps. |
| Invariants | Domain code | What must remain true (e.g. stock never negative unless flag off). |

### Template — function / method

```python
def adjust_stock(
    self,
    product_id: int,
    quantity: int,
    *,
    user=None,
    request=None,
) -> StockMovement:
    """
    Apply a signed stock adjustment and write an audit row.

    Creates one ``StockMovement`` (type ``adjustment``). Positive ``quantity``
    adds stock; negative removes stock. Audits ``stock_before`` / ``stock_after``.

    Args:
        product_id: Primary key of the product (must exist and track stock).
        quantity: Signed units to apply. Must be non-zero. No hard upper bound
            beyond fitting in the movement integer field; negative adjusts cannot
            drive on-hand below 0 unless sale negative-stock is allowed elsewhere.
        user: Acting user stored on the movement; may be None for system jobs.
        request: Optional HTTP request for IP/path on the audit row.

    Returns:
        The created ``StockMovement`` instance (refreshed stock already applied).

    Raises:
        ValidationError: Product missing, does not track stock, quantity is 0,
            or resulting stock would be negative.
    """
```

### Template — class

```python
class StockMovementService(BaseService):
    """
    Business operations for inventory ledger rows and on-hand quantity.

    Owns create paths for adjust / purchase / transfer / undo. Views stay thin
    and call these methods. Every mutating path emits an ``AuditLog`` entry.

    Attributes:
        model: Bound to ``StockMovement``.
    """
```

### Template — module (`"""` at top of file)

```python
"""
Inventory stock movements and on-hand quantity.

Public entry points:
    - StockMovementService.adjust_stock / purchase_stock / transfer_stock
    - StockMovementViewSet HTTP API under /api/inventory/

Side effects: updates Product/ProductVariant.stock_quantity, optional FIFO
layers, AuditLog rows. Does not create sales.
"""
```

## Required content (JS / TS / Dart)

Use JSDoc / Dart doc comments with the same information:

```js
/**
 * Merge a product into the POS cart by summing quantity for the same line key.
 *
 * @param {object} product - Catalog or variant payload; may include `quantity`.
 * @param {number} [product.quantity=1] - Units to add; integer ≥ 1. Picker
 *   double-fires within 500ms with the same key+qty are ignored.
 * @returns {void} Updates cart state; does not return the new cart.
 */
```

```dart
/// Load current pay estimate and locked payslips for the signed-in employee.
///
/// Returns [Result] success with parsed models, or failure with API/parse error.
/// Does not download PDF bytes — call [downloadPayslipPdf] separately.
```

## Bounds checklist (do not skip)

For every numeric / collection / string argument, document when applicable:

- Minimum and maximum (inclusive vs exclusive)
- Empty / null / blank behavior
- Pagination defaults (`page_size` max)
- Money scale (2 decimal places, currency)
- Date/time timezone (local vs UTC)
- Idempotency / double-submit guards

## Module summary docs

When documenting a Django app end-to-end, also update:

1. `docs/modules/<app>.md` — purpose, actors, key models, APIs, invariants, audit
2. One-line row in `docs/modules/README.md` index
3. Keep `be/STRUCTURE.md` App map in sync if a new app is added

## Do / don’t

- **Do** document side effects (audit, stock, wallet, journals).
- **Do** update the docstring in the same PR as signature or behavior changes.
- **Don’t** restate the type hints only (`x: int` → “The int x”) — say meaning.
- **Don’t** invent bounds that the code does not enforce; if unbounded, say so.
- **Don’t** leave `TODO` or `Pass` as the only docstring on public APIs.

## Workflow for module-by-module passes

1. Read app `models.py`, `services.py`, `views.py`, `urls.py`.
2. Write/refresh `docs/modules/<app>.md` (purpose, models, APIs, bounds, audit, gaps).
3. Add/fix **module** docstring + every **public** class/function/method:
   Args (meaning + units), Returns, Raises, limits/upper–lower bounds, side effects.
4. Prefer services and models first; then ViewSets and serializers that encode rules.
5. Note coverage gaps (missing tests / missing audit / thin docstrings) under **Gaps**.
6. Update the wave table in `docs/modules/README.md`.
7. Run the app’s tests if doc-only changes touch executable examples.

## Packaging (modules & packages)

This product is sold in modules/packages. When a docstring pass or feature change
adds a capability, also follow
`.cursor/skills/module-packaging/SKILL.md` (catalog ModuleFeature / ModuleSetting,
API + nav gates). Document the toggle under **Gaps** or **Public APIs** in
`docs/modules/<app>.md` when the module is configurable.
