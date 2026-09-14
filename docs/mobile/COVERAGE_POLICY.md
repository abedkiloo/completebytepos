# Coverage policy — 98% gate

## What must hit ≥98% line coverage

For each sprint, measure coverage on:

1. All **new** Dart files under `lib/` created in the sprint
2. All **modified** Dart files under `lib/` (entire file, not just diff)
3. All **new/modified** Django modules/packages for APIs added this sprint (`be/...`)

## What may be excluded (document in PR/notes)

- `main.dart` bootstrap wiring (keep thin)
- Generated files (`*.g.dart`, `*.freezed.dart`)
- Platform channel stubs that cannot run in VM — cover with interface fakes instead
- Pure design-token constants files (prefer testing widgets that use them)

Exclusions must be listed in the sprint completion notes. Do not exclude business logic.

## How to run (Flutter)

```bash
flutter test --coverage
dart run tools/check_coverage.dart --min=98 \
  --paths=lib/core,lib/design_system,lib/features,lib/app \
  --exclude=lib/main.dart
```

Logic lives in `mobile/lib/core/coverage/lcov_gate.dart` (unit-tested). The CLI wrapper is `mobile/tools/check_coverage.dart`.
## How to run (Django)

```bash
cd be
python -m coverage run --source=<module> manage.py test <tests>
python -m coverage report -m --include='path/to/module.py'
```

New modules (e.g. `agents`, `deliveries`) must show **≥98%** before sprint Done.

## TDD expectations

- Domain/use-cases: unit tests
- Widgets: widget tests for mental-model CTAs and empty/error states
- Sync/outbox: unit tests for queue, retry, idempotency
- API: Django APITestCase for new endpoints
- Golden/screenshot tests optional — never a substitute for logic coverage
