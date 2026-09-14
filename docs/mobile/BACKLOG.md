# Mobile backlog (deferred)

Items discovered during sprints that are **out of current sprint scope**.  
Move into a future sprint prompt when prioritized.

| Date | From sprint | Item | Notes |
|------|-------------|------|-------|
| 2026-09-14 | S06 | Export PDF on device | Sales history / receipt export deferred from mobile |
| 2026-09-14 | S01 | Bundle Plus Jakarta Sans font assets | Typography uses family name; Material fallback until assets added |
| 2026-09-14 | S04 | Holdings v2 (billing POS save/resume) | Lite uses direct `POST /sales/`; holding+checkout deferred |
| 2026-09-14 | S03 | Full SQLCipher DB-file encryption | Field-level AES ships; whole-file cipher if threat model requires |
| 2026-09-14 | S02 | Biometric unlock (Face/Touch ID) | Stub later; password login ships in S02 |
| 2026-09-14 | S00 | Generate checked-in OpenAPI from DRF | Contract currently markdown-only in `API_MOBILE_CONTRACT.md` |
| 2026-09-14 | S00 | Inventory write flows on mobile | Adjust/purchase/transfer stay web-first |
| 2026-09-14 | S00 | Mapbox fallback | Only if Google Maps billing/keys block Android |
| 2026-09-14 | S08 | Real FCM / APNs push | Interface + `FakePushNotifier` / BE stub shipped; wire provider when keys ready |
| 2026-09-14 | S08 | Field-order catalog search UX | Cart uses sample/add line for smoke; reuse full POS search later |
| 2026-09-14 | S09 | Real camera/signature capture widgets | Stop POD uses toggle stubs in tests; device capture UI polish later |
| 2026-09-14 | S10 | Airtel pay-link | Safaricom STK only this sprint |
| 2026-09-14 | S10 | OTP-on-SMS enhancement | Optional second factor on invoice/reminder SMS |
| 2026-09-14 | S10 | Full marketing campaign tool | MessageOutbox is transactional only |

## Parking lot (from requirements — not yet scheduled deeper)

- Full multi-stop route optimization / OR-Tools
- Agent commission engines & targets dashboards
- Customer-facing native app (public invoice PWA may be enough)
- MDM vendor integration beyond device registry + remote logout
- iOS TestFlight pipeline (architecture ready from S01; signing later)
- Airtel/Telkom pay-link fallback if STK is Safaricom-only
