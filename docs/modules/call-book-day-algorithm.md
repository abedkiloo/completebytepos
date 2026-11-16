# How a ward gets its call day

The book still runs Monday to Friday. This note is the rule that decides which day a ward is phoned, and the only numbers you change when that rule needs tuning.

The code lives in `be/sales/call_day_algorithm.py`. The constants at the top of that file are the settings. After a change, run `sales.tests.test_call_day_algorithm`.

## What is grouped

Kenya files places as county, then sub-county, then ward, then location, then sublocation. The customer record stores the first three, plus the shop pin when someone dropped it on the map. It does not store the sublocation name.

The call day is chosen for the **ward**. Every shop in that ward is phoned on that day. That keeps the sublocations inside the ward on one day, so a caller is not sent back to the same estate on Thursday after working it on Monday.

A ward with no valid county / sub-county / ward, or whose phone cannot be dialled, is not part of this rule. Those customers stay on the unlocated day (default Monday).

## The steps

1. One row per ward. Its weight is how many customers there have a usable phone.
2. Its map point is the **median** pin of those shops. One pin that was dropped in the wrong place does not drag the ward. A ward with no pin has no point.
3. Heaviest wards are placed first.
4. The first ward opens Monday.
5. The next ward joins a day already open when either of these is true:
   - its point is within **12 km** of a shop-pin already on that day, or
   - that day already has the same sub-county, and the points are within **25 km**.
6. When two days are within **2 km** of each other for this ward, the day with fewer customers wins.
7. A ward that is not close to an open day opens the next free weekday, Tuesday then Wednesday, up to Friday.
8. Once all five days are open, a far ward joins the nearest day anyway.
9. A ward with no pin copies the busiest day already chosen in its sub-county. If the sub-county has no pin, it copies the busiest day in its county. If the county has no pin, it keeps a fixed hash of its name so the day does not move between visits.

A row on the call-day plan (the editor on the week screen) still wins over all of this. Use that when a ward must sit on a chosen day. The algorithm does not write those rows.

## Settings

| Constant | Default | Allowed | What changing it does |
| --- | --- | --- | --- |
| `NEIGHBOR_KM` | 12 | 0–200 | How close two wards must be to share a day. Raise it to pull a wider belt onto one day. Set it to 0 to stop distance from joining days. |
| `SUB_COUNTY_KM` | 25 | 0–300 | How far a ward may sit from another ward in the same sub-county and still share the day. Set it equal to `NEIGHBOR_KM` to ignore the sub-county. |
| `TIE_KM` | 2 | 0–50 | Inside this gap, the quieter day is chosen. |
| `MIN_PINS` | 1 | 1–10000 | Pins a ward needs before it has a map point. Raise it if a single bad pin is placing wards. |
| `MAX_WARDS` | 2000 | 1–5000 | Heaviest wards kept. Kenya has about 1,450 wards. |
| `WEEKDAY_COUNT` | 5 | 5 | Monday–Friday. The book does not call on Saturday or Sunday. |

Distance is straight-line kilometres, not the road. To switch to driving minutes later, replace `haversine_km` and keep the steps above. Do not change the plan-row override.

## A small example

Landimawe and Nairobi Central are both in Starehe. Their pins are about a kilometre apart, so they share a day. Kangemi in Westlands, about 15 km away and in another sub-county, opens the next day. Pangani, also in Starehe but with no pin yet, follows Starehe’s day rather than being scattered.

## What this replaced

Wards used to be spread with a hash of the name. Two wards on the same road could land on Monday and Thursday. The hash remains only for a county where no shop has a pin.
