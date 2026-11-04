# Backend testing package

Shared coverage gates and helpers. App tests live in `<app>/tests/`.

## Layout

```
be/
├── testing/
│   ├── coverage_gates.json   # Per-module 95% targets (logic layer)
│   └── check_gates.py        # Fails CI if a gate is below minimum
├── utils/tests/api_test_base.py
└── <app>/tests/test_*.py
```

## Run

```bash
cd be
USE_SQLITE=true ./run_tests_coverage.sh           # full report; fails on whole-tree fail_under
USE_SQLITE=true ./run_tests_coverage.sh --gates   # enforce 98% on gated packages (CI bar)
```

## Gate philosophy

| Layer | Target | What to test |
|-------|--------|----------------|
| Gated packages in `coverage_gates.json` | **98%** | Services, exports, module settings, core views/serializers listed |
| Whole tree (`.coveragerc` `fail_under`) | aspirational floor | Reported always; with `--gates`, package gates decide pass/fail |
| Migrations, admin, populate commands | Excluded | — |

Views should stay thin; push logic into services and test there. When adding a
sellable module feature, add/extend a gate package and tests in the same change.
