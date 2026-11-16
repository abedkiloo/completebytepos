# Weekly call book

Feature: **customers → call_book** (`Weekly call book`).

Staff open **Customers → Call book**. The week is Monday–Friday in Africa/Nairobi. Saturday and Sunday show who was not called and do not accept a new mark. “Called this week” comes from the call’s Monday date, so the list starts again on Monday without anyone clearing a box.

Every signed-in role receives `customers.call_book` (view the book, see the number, hold, and mark). Manager and Super Admin edit which wards fall on which day, where customers with no valid location sit (default Monday), and how many minutes a Call button reserves that shop (default 5, range 1–30).

Ask later, no answer, and called all count for the week. The note stays so next Monday’s caller can see it. A note does not become an order. Customers with fewer than 9 phone digits are counted as cannot-call and stay off the dial list.

The Full retail preset turns the feature on. A store can switch it off under Module Settings; the API then returns 403 and the nav item hides.
