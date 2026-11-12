---
name: testing-required
description: >-
  Hard gate for Omuwenga / CompleteBytePOS: every code update must ship unit,
  integration, module, stress, corrected-functionality, and security tests
  (plus related suite types). Use when adding or changing APIs, UI, mobile,
  payments, sales, debt, receipts, modules, or any feature behavior.
---

# Testing required on every code update

**Hard rule:** each code update must write and run **all** of these test types
for the changed functionality, including **corrected functionality tests** and
**security tests**.

## Required test types (every change)

| Type | What it proves | Where (examples) |
|------|----------------|------------------|
| **Unit** | Pure helpers / serializers / labels / validators in isolation | `be/**/tests/test_*.py` SimpleTestCase; `fe/src/**/*.test.js`; `mobile/test/**/*_test.dart` |
| **Integration** | API + DB / client + HTTP / page click → dialog/API | ManagerAPITestCase / APIClient; Jest page tests; Flutter MockClient API tests |
| **Module** | Package/module gates (feature off → 403/hidden; on → works) | Feature flags, `ModuleSettings` / `ModuleFeature`, nav + API both gated |
| **Stress** | Many iterations / concurrent reads / bulk payloads still correct | Loops ≥ hundreds; ThreadPool / parallel fetches where safe |
| **Corrected functionality** | The bug/fix just shipped stays fixed (regressions) | Explicit cases for the user-facing correction (e.g. pay-later ≠ cash; till before code; payment detail click) |
| **Security** | Authn/authz, IDOR, privilege, unsafe methods, error non-leakage | `*security*` suites; unauthenticated; wrong role; scoped visibility; correct/admin-only actions |
| **Other applicable** | E2E / widget / contract when the surface needs them | Playwright/e2e when UI flow is critical; Flutter widget tests for new screens |

Do **not** skip a type because “it is small.” If a type does not apply, say so
in the PR/summary with a one-line reason (e.g. “no module flag for this util”).

## Security tests (required for each functionality)

For every new or changed API / money / customer / payment / admin surface, write
security coverage that asserts at least:

1. **Unauthenticated** access is denied (401/403)  
2. **Wrong role / missing permission** is denied  
3. **IDOR / scoped visibility** when the feature is tenant-, customer-, or agent-scoped  
4. **Privilege actions** (correct / approve / delete / export) stay on the intended role  
5. **Unsafe methods** rejected where the endpoint is read-only  
6. **Error bodies** do not leak payer, proof, reference, amount, or phone fields  

Place them in `test_<feature>_security.py`, `<Feature>.security.test.js`, or a
`security` group in Dart tests. Run them with the rest of the focused suite.

## When this applies

- New or edited backend views, services, serializers, payments, sales, debt
- New or edited FE pages/dialogs/hooks/utils
- New or edited mobile pages/API/domain
- Bug fixes and “corrected functionality” (labels, validation order, detail views)
- Refactors that change behavior or public contracts

## Minimum per change (checklist)

Before finishing the change:

1. **Unit** — happy path + empty/null + invalid bounds  
2. **Integration** — at least one real call path (API or UI → API mock)  
3. **Module** — if sellable/configurable, assert off and on  
4. **Stress** — batch or concurrent exercise of the hot path  
5. **Corrected functionality** — named test for the exact user-facing fix  
6. **Security** — authn/authz/IDOR/privilege (+ non-leak) for the new surface  
7. **Run** the new/updated tests and fix failures  

## Naming / placement

- Prefer suite files that name the concern: `test_<feature>_suite.py`,
  `<Feature>.integration.test.js`, `<feature>_test.dart`
- Put stress cases in `*stress*` or a clearly named `Stress` class/group
- Put security cases in `*security*` or a clearly named `Security` class/group
- Put corrected cases with explicit names:
  `test_pay_later_never_listed_as_cash`, `opens_payment_detail_after_receive`

## Payment / tender / receipt changes (current product rules)

When touching payments, debt collections, sale tender, or history labels, tests
must cover:

- Till vs bank chosen **before** M-Pesa code  
- Screenshot required for non-cash till/bank on debt **and** sale  
- Pay later / unpaid **not** labeled Cash in history/detail/receipts  
- Click payment → full detail (amount, payer, method, reference, proof) after receive  
- Payment detail GET / correct stays permission-scoped (no IDOR, no unauth read)

## Agent behavior

1. Read this skill at the start of **every** Omuwenga / CompleteBytePOS code change.  
2. In the **same** change, write unit + integration + module + stress +
   corrected-functionality + **security** tests (and other applicable types).  
3. Run the focused suites (BE with `USE_SQLITE=1` when local Postgres host is unavailable).  
4. Fix failures before finishing — do not claim done until the new/updated tests pass.  
5. If a type truly does not apply, state a one-line reason; never silently skip.

## Pointers

- Project skill lives here: `CompleteBytePOS/.cursor/skills/testing-required/SKILL.md`
- Personal alias: `~/.agents/skills/omuwenga-testing-required/SKILL.md`
- Also follow `module-packaging` and `docstrings` skills on the same change.
