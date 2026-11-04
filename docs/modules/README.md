# Module documentation index

Senior-readable summaries of each CompleteBytePOS backend app. Detail lives in
`docs/modules/<app>.md`. Coding layout rules: `be/STRUCTURE.md`. Docstring
standard: `.cursor/skills/docstrings/SKILL.md`.

| App | One-line purpose | Doc |
|-----|------------------|-----|
| `config` | Django settings, root URLs, exception handler | [config.md](./config.md) |
| `accounts` | Users, roles, permissions, **AuditLog** | [accounts.md](./accounts.md) |
| `products` | Catalog, variants, sizes/colors | [products.md](./products.md) |
| `sales` | POS sales, customers, debt, invoices | [sales.md](./sales.md) |
| `inventory` | Stock movements, checkpoints, layers | [inventory.md](./inventory.md) |
| `approvals` | Maker-checker pending changes | [approvals.md](./approvals.md) |
| `payroll` | Pay components, packages, runs, payslips | [payroll.md](./payroll.md) |
| `employees` | Staff records linked to users | [employees.md](./employees.md) |
| `appraisals` | Target-delivery stars / bonus inputs | [appraisals.md](./appraisals.md) |
| `expenses` | Expense categories and vouchers | [expenses.md](./expenses.md) |
| `income` | Income categories and receipts | [income.md](./income.md) |
| `bankaccounts` | Bank accounts and transactions | [bankaccounts.md](./bankaccounts.md) |
| `transfers` | Inter-account money transfers | [transfers.md](./transfers.md) |
| `accounting` | Journals, accounts, reversals | [accounting.md](./accounting.md) |
| `agents` | Field sites and field orders | [agents.md](./agents.md) |
| `dispatch` | Pack / assign for delivery | [dispatch.md](./dispatch.md) |
| `delivery` | Delivery stops and POD | [delivery.md](./delivery.md) |
| `payments` | Payment intents / M-Pesa hooks | [payments.md](./payments.md) |
| `messaging` | SMS templates and sends | [messaging.md](./messaging.md) |
| `cms` | Public website / enquiries / blog | [cms.md](./cms.md) |
| `settings` | Tenant, branch, module feature flags | [settings.md](./settings.md) |
| `reports` | Aggregated reporting APIs | [reports.md](./reports.md) |
| `suppliers` | Supplier master data | [suppliers.md](./suppliers.md) |
| `daily_notes` | Sticky notes / daily tasks | [daily_notes.md](./daily_notes.md) |
| `idempotency` | Idempotency-Key middleware | [idempotency.md](./idempotency.md) |
| `utils` | Audit helpers, branding, shared tests | [utils.md](./utils.md) |
| `services` | Cross-app base service / date filters | [services.md](./services.md) |

## Documentation pass status

| Wave | Apps | Status |
|------|------|--------|
| 1 | accounts, inventory, payroll, products, sales | **Done** (briefs + key service/model docstrings) |
| 2 | employees, appraisals, approvals, settings | **Done** (briefs + public API docstrings) |
| 3 | expenses, income, bankaccounts, transfers, accounting | **Done** (briefs + models/services docstrings; views still thin) |
| 4 | agents, dispatch, delivery, payments, messaging, cms | **Done** (briefs + models/services docstrings; thin ViewSet methods OK) |
| 5 | reports, suppliers, daily_notes, idempotency, utils, services, config | **Done** (briefs + public helpers/audit/idempotency/base services) |

**Skill / rule:** `.cursor/skills/docstrings/SKILL.md`, `.cursor/rules/docstrings.mdc` — every new **or existing** public function/class/module (on edit or docs pass) must document Args, Returns, Raises, and limits/bounds.
