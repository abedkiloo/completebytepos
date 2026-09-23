# Maps configuration (Google Maps Platform)

Planned delivery maps: **shop depot → numbered stops → cached road line**.  
Live GPS / Redis fleet tracking is **not** in this sprint — do not write phone-rate coordinates to Postgres.

Keys are **placeholders** in git. Paste real keys locally, in CI secrets, and on the VPS. Never commit an unrestricted key.

---

## 1. Google Cloud (once)

1. Enable billing on the Google Cloud project. Set a **budget alert**.
2. Enable APIs:
   - Maps SDK for Android
   - Maps SDK for iOS
   - Maps JavaScript API
   - **Routes API** (server polyline). Directions API is the older equivalent.
   - Optional: Geocoding API (one-shot shop address → depot pin)
3. Create **four restricted keys** (not one unrestricted key):

| Key | Application restriction | API restriction | Where it lives |
|---|---|---|---|
| Android | App (`com.completebyte.completebyte_pos_mobile`) + SHA-1 | Maps SDK for Android | `mobile/android/local.properties` → `MAPS_API_KEY` |
| iOS | Bundle ID (`com.completebyte.completebytePosMobile` — confirm in Xcode) | Maps SDK for iOS | `mobile/ios/Runner/Info.plist` → `GMSApiKey` |
| Web JS | HTTP referrers: `https://omuwenga.com/*`, `https://*.omuwenga.com/*`, UAT host, `http://localhost:3000/*` | Maps JavaScript API | `REACT_APP_GOOGLE_MAPS_KEY` (frontend env only) |
| Server | VPS public IP | **Routes API only** | Django `GOOGLE_MAPS_SERVER_KEY` |

The phone and browser **draw** the cached polyline. They must **not** call Routes/Directions. Only Django calls Routes, and only when the stop list (or depot) changes.

---

## 2. Placeholders (safe to ship)

| Variable | Placeholder | Used by |
|---|---|---|
| `MAPS_API_KEY` | `REPLACE_WITH_MAPS_API_KEY` | Android Gradle (`AndroidManifest` `com.google.android.geo.API_KEY`) |
| `GMSApiKey` | `REPLACE_WITH_MAPS_API_KEY` | iOS `Info.plist` + `GMSServices.provideAPIKey` in `AppDelegate.swift` |
| `REACT_APP_GOOGLE_MAPS_KEY` | `REPLACE_WITH_MAPS_JS_API_KEY` | React Field sales map |
| `GOOGLE_MAPS_SERVER_KEY` | `REPLACE_WITH_MAPS_SERVER_KEY` | Django Routes API |

If a value is empty or still contains `REPLACE_WITH` / `YOUR_KEY` / `CHANGE-ME`, the app treats it as **unset**. Maps still work: numbered pins + a **straight** line. Tiles and road geometry appear after real keys are pasted.

---

## 3. Android

`mobile/android/app/build.gradle.kts` already reads `MAPS_API_KEY` from Gradle properties (including `local.properties`).

Add to **`mobile/android/local.properties`** (this file is machine-local; do not commit the real key):

```
MAPS_API_KEY=AIza...your-android-key
```

CI: inject the same property (`-PMAPS_API_KEY=...` or a `local.properties` step). Debug and release SHA-1 fingerprints must both be allowed on the Android key.

Package id today: `com.completebyte.completebyte_pos_mobile`.

---

## 4. iOS

`Info.plist` has `GMSApiKey`. `AppDelegate` calls `GMSServices.provideAPIKey` with that value.

Replace the placeholder in `mobile/ios/Runner/Info.plist`:

```xml
<key>GMSApiKey</key>
<string>AIza...your-ios-key</string>
```

Or keep `REPLACE_WITH_MAPS_API_KEY` in git and override via an xcconfig / CI build setting named `MAPS_API_KEY` if you later change the plist value to `$(MAPS_API_KEY)`.

After changing the key: `cd mobile/ios && pod install`.

Location (for the existing pin picker): `NSLocationWhenInUseUsageDescription` is in Info.plist.

---

## 5. Web (React)

CRA bakes `REACT_APP_*` at **build** time.

| Env file | Variable |
|---|---|
| `CompleteBytePOS/fe/.env` / `.env.local` | `REACT_APP_GOOGLE_MAPS_KEY=AIza...` |
| Workspace root `.env` (Docker) | same name, passed into the frontend image |

**Production / UAT:** rebuild the frontend image after changing the JS key:

```bash
# from CompleteBytePOS/
docker compose build --build-arg REACT_APP_GOOGLE_MAPS_KEY=AIza... frontend
docker compose up -d frontend
```

`docker-compose.yml` and `Dockerfile` pass `REACT_APP_GOOGLE_MAPS_KEY`. Leave the placeholder until the restricted web key exists.

Without a real JS key, Field sales **Driver map** still shows an SVG of shop + numbered stops.

---

## 6. Django (Routes API — VPS only)

In workspace root `.env` / `.env.uat` / production `.env`:

```
GOOGLE_MAPS_SERVER_KEY=REPLACE_WITH_MAPS_SERVER_KEY
```

Replace with the **IP-restricted** server key. Restart Gunicorn after changing it.

- Empty / placeholder → Django encodes a **straight** polyline and stores it on `DeliveryRoute`.
- Real key → Django calls Routes **once per route change**, then stores `encoded_polyline` + `polyline_source=google`.
- Clients never receive this key (`GET /api/delivery/config/` only returns `maps.routes_api_configured: true|false`).

---

## 7. Depot pin (shop start)

The shop is no longer address-only.

1. Open **Branches** on web.
2. Edit the branch → **Depot latitude / longitude**.
3. Save.

Until those fields are set, maps use a Nairobi CBD default and show a short notice. Optional: use Geocoding once from the street address, then paste the result.

---

## 8. What the apps call

| Who | Endpoint | What you see |
|---|---|---|
| Driver (app) | `GET /api/delivery/routes/today/geometry/` | Own today’s map |
| Admin / dispatcher (web Field sales → Driver map) | `GET /api/delivery/routes/geometry/?agent_id=&date=` | That driver’s planned path even before they leave |
| Anyone with `delivery.view` | `GET /api/delivery/config/` | `maps.routes_api_configured`, `live_tracking_enabled: false` |

Stop complete / collect / POD stay on the existing delivery API. POD lat/lng is **not** tracking.

---

## 9. Cache (this sprint vs later)

| Store | What | Why |
|---|---|---|
| **Postgres** | Stops, sequence, customer pins, branch depot, **one polyline per `DeliveryRoute`** | Source of truth. Cheap to read. |
| **Device / browser** | Map tiles (Google) | Billed as map loads, not as GPS pings |
| **Redis** | *Not in this sprint* | Needed before live `driver:{id}:loc` pings. LocMem cannot share GPS across Gunicorn workers. |

Do **not** insert a GPS row per ping. Phase 4 (live marker) should not ship on LocMem.

---

## 10. Cost and privacy

- Map **loads** (tiles / JS) are the usual bill. Cached Routes is a few calls per driver per day.
- The moving dot (later) must not call Google after the line exists.
- Track only while on duty / route open when live GPS is built. This sprint does not ping location.

---

## 11. Verify without billing keys

1. Assign a visit order with a customer pin to a driver.
2. App → Today’s route: numbered list + map card (fallback pins if Android key is still a placeholder).
3. Web → Field sales → **Driver map**: pick the driver, see shop + stop #1.
4. Save a branch depot pin; refresh the map — shop label/position updates after the polyline fingerprint changes.

When keys are live: Android/iOS show Google tiles; web shows Maps JS; Django `polyline_source` becomes `google` on the next stop-list change.
