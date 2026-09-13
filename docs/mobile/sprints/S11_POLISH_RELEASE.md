# S11 — Polish, device trust, Android release, coverage audit

**Paste after `MASTER_PROMPT.md`.**

## Goal

Production-ready Android build: performance, accessibility, device registry lite, crash-free smoke paths, and a **full coverage audit** across mobile packages + new backend modules.

## In scope

- Performance pass (list jank, image cache, map dispose)
- Accessibility: tap targets, semantics labels on primary CTAs
- Device registry: register device id on login; remote logout endpoint
- ProGuard/R8 config; release signing instructions (secrets not committed)
- Play-ready store listing checklist (internal)
- End-to-end smoke script list (manual) for all personas
- Coverage audit report: each feature package ≥98% or justify exclusion
- Fix any coverage holes from prior sprints
- iOS compile check optional (no signing required)

## Out of scope

- New major features
- Route optimization
- Full MDM vendor

## Tests

- Regression suite green
- Integration tests for: login, cash sale, site pin+photo, stop complete (mocked maps if needed)
- BE regression for agents/payments modules

## Definition of Done

- [ ] `flutter build apk` (or appbundle) succeeds
- [ ] Coverage audit document `docs/mobile/COVERAGE_AUDIT_S11.md`
- [ ] Known issues filed in BACKLOG
- [ ] Handoff notes for ops (env vars, Daraja, SMS)
