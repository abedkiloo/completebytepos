# Delivery stop view model (S07 → S09)

Delivery agents consume finalized `CustomerSite` + `SiteMedia` with **map + gallery first**.

## Fields the stop UI will need

| Field | Source | Notes |
|-------|--------|-------|
| `siteId` | `CustomerSite.id` | Stable stop identity |
| `label` | `CustomerSite.label` | Short place name |
| `latitude` / `longitude` | pin | Required on finalize |
| `accuracy` | GPS assist | Optional confidence |
| `landmark` | agent notes | Free text (“blue container”) |
| `customerId` / `customerName` | FK + denorm | Who receives goods |
| `photoUrls[]` | `SiteMedia.image_url` | Ordered gallery above line items |

Flutter helper: `DeliveryStopViewModel.fromSiteJson` in `mobile/lib/features/agents/domain/site_visit.dart`.

S09 must not invent a parallel location model — reuse this shape.
