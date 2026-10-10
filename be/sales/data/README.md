# Kenya administrative units (county → sub-county → ward)

`kenya_admin_units.json` is a nested lookup used to validate customer location fields.

Source: [Open Admin Data — Kenya](https://openadmindata.org/ke/) (CC-BY-4.0), generated from their public API.

To regenerate:

```bash
python3 scripts/build_kenya_admin_units.py
```

(Or run the build logic documented in `sales/kenya_admin.py`.)
