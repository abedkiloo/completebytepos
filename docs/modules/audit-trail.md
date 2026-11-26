# Audit trail — security & accounting

**Goal:** Every state-changing action, authenticated permission denial, and (when enabled) sensitive **record open** leaves an append-only row so nobody can credibly deny what they did. Audit **never** blocks business logic.

## What every row records

| Field | Purpose |
|-------|---------|
| User + username snapshot | Who acted (survives user deletion) |
| Action / module / object | What they touched |
| **`action_display` / `module_display`** | People-facing names from `utils.audit_labels` (never bare numbers) |
| `changes` | Before/after or money payload (reads: `{purpose, kind: read}` only) |
| IP, path, method, user agent | Request context |
| **`client_channel`** | **`web`** vs **`mobile`** (app) vs `unknown` |

## How activity gets audited

1. **CRUD viewsets** — `AuditedModelViewSetMixin` (create / update / delete + optional detail **view**).
2. **Manual write paths** — `log_domain_event` / `utils.audit_events` (checkout, debt, refund, payroll, …).
3. **Sensitive reads** — `AuditedRetrieveMixin` / mixin `retrieve` → `log_sensitive_read` (`action=view`), gated by package feature **`settings.audit_sensitive_reads`**. Deduped ~5 minutes per user/object. **Lists are not logged.**
4. **Authenticated 403** — `permission_denied` (non-blocking).

`utils.audit.log_audit` swallows all write errors so a logging failure cannot roll back a sale, payroll run, or wallet credit.

## Next modules / next code changes

When adding a new `ModelViewSet` that owns money, PII, or permissioned records:

1. Inherit **`AuditedModelViewSetMixin`** (writes + detail reads).
2. Or, if writes are already logged manually, inherit **`AuditedRetrieveMixin`** only.
3. Set `audit_module = '…'` to the permission module key.
4. Set `audit_reads = False` only for high-churn catalog (e.g. POS product detail).
5. For custom `@action` writes, call `log_domain_event` with a **named verb** (snake_case) and add the label to `utils/audit_labels.py` + FE `ACTION_LABELS`.

## Where to review

Web **Audit log** page: filter by module, action, user, date, and **Web / Mobile app**. Action badges show **named** labels (`Opened / viewed`, `Sale money posted`, …); technical code is secondary in the detail drawer.

## Feature gate

| Feature | Module | Effect |
|---------|--------|--------|
| `audit_sensitive_reads` | `settings` | Enables `view` rows on detail opens |

## Non-goals

- List / dashboard / report list GETs (noise + performance).
- Auditing the audit-log API itself.
- Dumping response bodies, phones, tokens, or passwords into `changes`.
- Anonymous probes as `permission_denied` (authenticated denials only).
