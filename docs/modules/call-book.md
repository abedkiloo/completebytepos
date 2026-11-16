# Weekly call book

Feature: **customers → call_book** (`Weekly call book`).

Staff open **Customers → Call centre**. The week is Monday–Friday in Africa/Nairobi. Saturday and Sunday show who was not called and do not accept a new mark. “Called this week” comes from the call’s Monday date, so the list starts again on Monday without anyone clearing a box.

Every signed-in role except Field Sales receives `customers.call_book`. Field agents meet customers in person, so they do not work the phone list. Everyone else copies the number onto their own cell phone and records the result here. The screen does not place the call. Copying the number holds that shop for the configured minutes (default 5, range 1–30) so two people do not call the same customer together. Manager and Super Admin edit which wards fall on which day, and where customers with no valid location sit (default Monday). Where no plan row is saved, the ward algorithm in [call-book-day-algorithm.md](call-book-day-algorithm.md) puts nearby wards, and every sublocation inside a ward, on the same day.

Called, call later, no answer, and unreachable all count for the week. Call later also records the time to call again (`HH:MM`, Nairobi). On the next load or refresh, a customer whose time has been reached is placed at the top of the list, earliest time first. A time that is still ahead stays in the normal order. The note stays so next Monday’s caller can see it. An optional follow-up date can be today or up to 90 days ahead. A note does not become an order. Customers with fewer than 9 phone digits are counted as cannot-call and stay off the list.

The Full retail preset turns the feature on. A store can switch it off under Module Settings; the API then returns 403 and the nav item hides.
