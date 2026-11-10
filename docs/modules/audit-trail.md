# Audit trail — security & accounting

**Goal:** Every state-changing action (and authenticated permission denial) leaves an append-only row so nobody can credibly deny what they did. Audit **never** blocks business logic.

## What every row records

| Field | Purpose |
|-------|---------|
| User + username snapshot | Who acted (survives user deletion) |
| Action / module / object | What they touched |
| `changes` | Before/after or money payload |
| IP, path, method, user agent | Request context |
| **`client_channel`** | **`web`** vs **`mobile`** (app) vs `unknown` |

Web sends `X-Client-Channel: web` on every API call; the mobile app sends `mobile`. Sales also stamp the same channel on the sale itself.

## How writes get audited

1. **CRUD viewsets** — `AuditedModelViewSetMixin` (create / update / delete).
2. **Custom money & workflow** — `utils.audit_events` / `log_domain_event` (checkout, debt settlement, refund, approval, payroll run, stock, login/logout, …).
3. **Authenticated 403** — `config.exceptions.custom_exception_handler` writes `permission_denied` (non-blocking).

`utils.audit.log_audit` swallows all write errors so a logging failure cannot roll back a sale, payroll run, or wallet credit.

## Where to review

Web **Audit log** page: filter by module, action, user, date, and **Web / Mobile app**. Detail drawer shows client channel + full changes.

## Non-goals

- Read-only GETs (list/dashboard) are not logged by default (noise + performance).
- Anonymous probes are not logged as permission_denied (authenticated denials only).
