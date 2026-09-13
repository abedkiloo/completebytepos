# Copy-paste starter — begin any sprint

Paste into a new Cursor agent chat in this exact order:

---

## 1) Master laws

Open and paste the full contents of:

`docs/mobile/MASTER_PROMPT.md`

---

## 2) Sprint brief

Paste **one** sprint file only, for example:

`docs/mobile/sprints/S01_FOUNDATION.md`

---

## 3) Optional context (attach as files, don’t paste whole repo)

- `docs/mobile/UX_MENTAL_MODELS.md`
- `docs/mobile/COVERAGE_POLICY.md`
- Requirements canvas: `mobile-app-requirements-map`
- Existing API: `fe/src/services/api.js`, `be/sales/`, `be/accounts/role_definitions.py`

---

## 4) Closing instruction (add at end of your message)

```
Work ONLY on this sprint.
Follow TDD.
Do not mark Done until flutter analyze is clean AND coverage ≥98% on sprint-touched code
(and Django ≥98% on any new backend modules).
Android-first.
If you discover extra scope, append it to docs/mobile/BACKLOG.md instead of building it.
When finished, output the DoD checklist with [x] marks and coverage percentages.
```

---

## Suggested calendar (indicative)

| Sprint | Focus | Weeks |
|--------|-------|------|
| S00 | Discovery | 1–2 |
| S01–S02 | Foundation + auth | 2–3 |
| S03 | Offline core | 2 |
| S04–S06 | Store app | 4–6 |
| S07–S09 | Agents + map/upload + delivery | 5–7 |
| S10 | STK + SMS | 2–4 |
| S11 | Release | 1–2 |
