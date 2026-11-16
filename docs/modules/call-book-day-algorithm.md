# How a sub-county gets its call day

The book runs Monday to Friday. The unit is the **sub-county already stored on the customer**. Every shop in that sub-county, whichever ward it is in, is phoned on the same day.

The code is `be/sales/call_day_algorithm.py`.

## The steps

1. One row per county and sub-county. Its weight is how many customers there have a usable phone. A blank sub-county is its own row, so those shops are not mixed into a named sub-county.
2. The rows are sorted by county name, then sub-county name.
3. They are handed out in that order: Monday, Tuesday, Wednesday, Thursday, Friday, then Monday again.
4. The first name is Monday. The sixth sub-county is Monday as well.

A row on the call-day plan still wins over this. Use that when one ward must sit on a chosen day. The round robin does not write those rows.

`WEEKDAY_COUNT` is 5. Do not set it above 5. `MAX_SUB_COUNTIES` is 2000, which is more than Kenya has.
