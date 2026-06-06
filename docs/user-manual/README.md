# CompleteByte POS — User Manual (Excel)

Shareable onboarding workbook for **Managers** and **Super Admins**.

## Files

| File | Description |
|------|-------------|
| `CompleteBytePOS-Manager-Admin-Manual.xlsx` | Main user manual with steps, tips, and screenshots |
| `screenshots/` | PNG captures embedded in the workbook |

## Workbook sheets

1. **Cover** — purpose, default logins, how to refresh screenshots  
2. **Getting Started** — login, navigation, roles  
3. **Manager Daily Ops** — dashboard and daily workflow  
4. **Sales & POS** — retail POS, terminal POS, refunds, normal sale  
5. **Products & Inventory** — catalog, stock, barcodes  
6. **Finance & Reports** — customers, invoices, expenses, accounting, reports  
7. **Approvals & Audit** — maker-checker queue, audit log  
8. **Super Admin** — users, roles, module/system settings, branches  
9. **Quick Reference** — route × role matrix  
10. **Screenshot Gallery** — visual index of all captures  

## Regenerate the manual

```bash
# From repo root
pip install openpyxl pillow
python scripts/generate_user_manual.py
```

## Capture real UI screenshots

Start the stack, then capture and rebuild:

```bash
docker compose -f docker-compose.dev.yml up -d
cd fe && npm run test:e2e:install   # first time only
node ../scripts/capture_user_manual_screenshots.js
python ../scripts/generate_user_manual.py
```

Remote server:

```bash
PLAYWRIGHT_BASE_URL=http://YOUR_SERVER_IP:3000 node scripts/capture_user_manual_screenshots.js
```

## Default accounts (change in production)

| Role | Username | Password |
|------|----------|----------|
| Super Admin | `admin` | `admin123` |
| Manager | `manager` | `manager123` |
| Sales | `sales` | `sales123` |

## Related documentation

- [SETUP.md](../SETUP.md) — installation  
- [POS_UX_ROLES_AND_TESTING.md](../POS_UX_ROLES_AND_TESTING.md) — roles detail  
- [MAKER_CHECKER.md](../MAKER_CHECKER.md) — approval workflows  
