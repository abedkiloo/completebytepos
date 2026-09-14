# S01 — App foundation (Flutter + TDD harness)

**Paste after `MASTER_PROMPT.md`.**

## Goal

Create the Flutter Android-first app skeleton with theme, routing, DI, design system primitives, and a **coverage gate tooling** so every later sprint can enforce ≥98%.

## In scope

- `flutter create` project at the path chosen in S00
- App bootstrap, env/flavor config (dev/staging/prod base URLs)
- Design system: typography, colors, buttons, app scaffold, empty/error/loading
- GoRouter (or equivalent) with typed routes shell
- DI container
- Result/Either error type
- `tools/check_coverage.dart` (or Melos script) failing under 98% for given paths
- Example feature module `features/health` hitting `/api/` health or login ping — TDD
- CI-friendly `flutter analyze` clean

## Out of scope

- Full login UI polish (S02)
- Offline DB (S03)
- POS (S04)

## UX mental model

- Splash → cold start only; never trap users
- Unauthenticated → Login route
- Motion: fade splash → login

## Tests (write first)

- Widget test: App loads MaterialApp / theme
- Unit test: Result type mapping
- Unit test: coverage checker logic (≥98% pass/fail)
- Widget test: EmptyState primary CTA callback

## Backend

- None required unless health endpoint missing

## Definition of Done

- [x] Android emulator/device build succeeds (`flutter build apk --debug`)
- [x] `flutter analyze` clean
- [x] Coverage tooling exists (`tools/check_coverage.dart` + `lib/core/coverage/lcov_gate.dart`) and documented in `COVERAGE_POLICY.md`
- [x] Sprint-touched lib code ≥98% (`99.18%` on lib/core,lib/design_system,lib/features,lib/app excluding main.dart)
- [x] README in `mobile/` with run instructions
