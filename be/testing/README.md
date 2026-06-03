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
USE_SQLITE=true ./run_tests_coverage.sh           # full report
USE_SQLITE=true ./run_tests_coverage.sh --gates   # enforce 95% on gated modules
```

## Gate philosophy

| Layer | Target | What to test |
|-------|--------|----------------|
| `services.py`, `catalog_rules.py`, `user_write.py`, `config/` | **95%** | Business rules, pure helpers |
| Serializers | **90%** | Validation, `create`/`update` |
| Views | **75%+** | API contracts via `APITestCase` |
| Migrations, admin, populate commands | Excluded | — |

Views should stay thin; push logic into services and test there.
