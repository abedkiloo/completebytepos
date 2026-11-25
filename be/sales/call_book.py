"""
Weekly customer call book.

Monday–Friday in Africa/Nairobi. Saturday and Sunday are not call days.
"Called this week" is derived from ``CustomerCall.week_start`` (that week's
Monday), so the list resets itself on Monday. Staff copy the number and
call on their own cell phone. The system only records the result. Clicking
or copying a number claims that shop for the rest of the Nairobi day so
two people cannot dial the same customer on the same day. Customers not
called last week float above other pending shops. Customers with no
usable phone are counted as cannot-call and are left off the list.

Bounds: summaries are 0–500 characters. A day claim lasts until 23:59:59
Nairobi. A day plan has at most 200 location rows. Weekday indexes are 0
(Monday) through 4 (Friday). Day logs return at most 1000 rows per page.
"""

from __future__ import annotations

import zlib
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from sales.call_day_algorithm import assign_sub_county_weekdays
from sales.models import CallBookSettings, CallDayPlan, CallHold, Customer, CustomerCall

WEEKDAY_COUNT = 5
SUMMARY_MAX = 500
PLAN_ROW_MAX = 200
PAGE_SIZE_DEFAULT = 100
PAGE_SIZE_MAX = 1000
OUTCOMES = {
    CustomerCall.OUTCOME_CALLED,
    CustomerCall.OUTCOME_ASK_LATER,
    CustomerCall.OUTCOME_NO_ANSWER,
    CustomerCall.OUTCOME_UNREACHABLE,
}
FOLLOW_UP_DAYS = 90
SEGMENT_RANK = {
    'dormant': 0,
    'at_risk': 1,
    'active': 2,
    'new': 3,
    'champion': 4,
    'none': 5,
}


def nairobi_today() -> date:
    """
    Calendar date in the active Django timezone (Africa/Nairobi).

    Returns:
        date: Local today. No side effects.
    """
    return timezone.localdate()


def nairobi_day_bounds(day: date) -> tuple[datetime, datetime]:
    """
    Inclusive start and exclusive end of a Nairobi calendar day.

    Args:
        day: Local calendar date.

    Returns:
        tuple: ``(start, end)`` as aware datetimes. ``start`` is 00:00:00
        on ``day``. ``end`` is 00:00:00 on the next day. No writes.

    Raises:
        None.
    """
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), tz)
    end = timezone.make_aware(datetime.combine(day + timedelta(days=1), time.min), tz)
    return start, end


def end_of_nairobi_day(day: date) -> datetime:
    """
    When a same-day call claim expires.

    Args:
        day: Local calendar date of the claim.

    Returns:
        datetime: Aware 23:59:59 on ``day`` in Africa/Nairobi. No writes.

    Raises:
        None.
    """
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(day, time(23, 59, 59)), tz)


def operation_now(day: date) -> datetime:
    """
    Clock used for claims, due checks, and recording ``called_at``.

    Args:
        day: Nairobi calendar day for this operation.

    Returns:
        datetime: ``timezone.now()`` when that matches ``day``. Otherwise
        noon on ``day``, so tests that freeze the calendar still keep
        same-day claims active. No writes.

    Raises:
        None.
    """
    now = timezone.now()
    if timezone.localdate(now) == day:
        return now
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(day, time(12, 0)), tz)


def week_monday(day: date) -> date:
    """
    Monday of the week that contains ``day``.

    Args:
        day: Any calendar date.

    Returns:
        date: The Monday on or before ``day``. The returned date is always
        0–6 days earlier than ``day``.
    """
    return day - timedelta(days=day.weekday())


def is_call_day(day: date) -> bool:
    """
    Whether staff may mark calls on ``day``.

    Args:
        day: Calendar date.

    Returns:
        bool: True for Monday–Friday (weekday 0–4). False for Saturday
        and Sunday.
    """
    return day.weekday() < WEEKDAY_COUNT


def usable_phone(phone: str | None) -> bool:
    """
    Whether a stored phone can be dialled.

    Args:
        phone: Raw customer phone. May be blank. At most the model cap
        of 20 characters is expected.

    Returns:
        bool: True when the digit count is between 9 and 15 inclusive.
    """
    digits = ''.join(ch for ch in (phone or '') if ch.isdigit())
    return 9 <= len(digits) <= 15


def sub_county_call_groups(customers) -> list[dict]:
    """
    Collapse customers into one group per stored sub-county.

    The sub-county already saved on the customer is the group. Every ward
    inside that sub-county stays on the same call day. The official Kenya
    list is not required.

    Args:
        customers: Active customers. Each needs a phone. County and
            sub-county may be blank. A customer with fewer than 9 phone
            digits is left out.

    Returns:
        list[dict]: At most one row per county and sub-county. ``weight``
        is the number of included customers, 1–100000. A blank sub-county
        is its own group so those shops are not mixed into a named one.
        No writes.

    Raises:
        None.
    """
    buckets: dict[tuple[str, str], int] = {}
    for customer in customers:
        if not usable_phone(getattr(customer, 'phone', '')):
            continue
        key = (
            _norm(getattr(customer, 'county', '')),
            _norm(getattr(customer, 'sub_county', '')),
        )
        buckets[key] = buckets.get(key, 0) + 1
    return [
        {'county': county, 'sub_county': sub, 'weight': weight}
        for (county, sub), weight in buckets.items()
    ]


def _norm(value: str | None) -> str:
    """
    Compare locations without case or surrounding space.

    Args:
        value: Location fragment. May be blank.

    Returns:
        str: Lowercased strip. Length 0–100.
    """
    return (value or '').strip().lower()


def weekday_for_customer(customer, plans, unlocated_weekday: int, assignments=None) -> int:
    """
    Resolve which Monday–Friday this customer is phoned on.

    Args:
        customer: Object with ``county``, ``sub_county``, and ``ward``.
        plans: Iterable of plan rows with those fields plus ``weekday``.
        unlocated_weekday: 0–4. Kept for callers. A customer with no county
            and no sub-county is spread by a fixed hash of their id.
        assignments: Optional map from ``(county, sub_county)`` in lower
            case to weekday 0–4, produced by the sub-county round robin.
            None skips it. A matching plan still wins.

    Returns:
        int: Weekday 0–4. Order: matching plan, then the sub-county round
        robin, then a stable hash of the county and sub-county. Every shop
        in one sub-county shares that day, whichever ward they are in.

    Raises:
        None. Out-of-range ``unlocated_weekday`` is ignored.
    """
    county = _norm(getattr(customer, 'county', ''))
    sub = _norm(getattr(customer, 'sub_county', ''))
    ward = _norm(getattr(customer, 'ward', ''))
    if not county and not sub:
        token = f"{getattr(customer, 'id', '')}|{_norm(getattr(customer, 'name', ''))}"
        return zlib.crc32(token.encode('utf-8')) % WEEKDAY_COUNT
    best = None
    best_score = -1
    for plan in plans:
        score = _plan_score(plan, county, sub, ward)
        if score > best_score:
            best = int(plan.weekday)
            best_score = score
    if best is not None and best_score > 0:
        return min(4, max(0, best))
    if assignments:
        found = assignments.get((county, sub))
        if found is not None:
            return min(4, max(0, int(found)))
    key = f'{county}|{sub}'.encode('utf-8')
    return zlib.crc32(key) % WEEKDAY_COUNT


def _plan_score(plan, county: str, sub: str, ward: str) -> int:
    """
    How specifically a plan row matches a customer location.

    Args:
        plan: Row with county, sub_county, ward.
        county: Normalised customer county.
        sub: Normalised customer sub-county.
        ward: Normalised customer ward.

    Returns:
        int: 3 ward, 2 sub-county, 1 county, 0 no match.
    """
    plan_county = _norm(plan.county)
    plan_sub = _norm(plan.sub_county)
    plan_ward = _norm(plan.ward)
    if plan_ward:
        if plan_county == county and plan_sub == sub and plan_ward == ward:
            return 3
        return 0
    if plan_sub:
        if plan_county == county and plan_sub == sub:
            return 2
        return 0
    if plan_county and plan_county == county:
        return 1
    return 0


def user_may_edit_call_plan(user) -> bool:
    """
    Whether this user may replace the day plan and hold settings.

    Args:
        user: Authenticated user or anonymous.

    Returns:
        bool: True for a superuser, or a profile whose role or custom role
        is Super Admin or Manager. Everyone else may still view and mark.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    legacy = (getattr(profile, 'role', '') or '').strip()
    if legacy in ('super_admin', 'manager'):
        return True
    role = getattr(profile, 'custom_role', None)
    name = (getattr(role, 'name', '') or '').strip()
    return name in ('Super Admin', 'Manager')


def _display_name(user) -> str:
    """
    Staff label stored on a call or hold.

    Args:
        user: User or None.

    Returns:
        str: Full name, else username, else "Staff". Length 1–150.
    """
    if user is None:
        return 'Staff'
    full = (user.get_full_name() or '').strip()
    if full:
        return full[:150]
    return (getattr(user, 'username', '') or 'Staff')[:150]


def _weekday_filter(weekday) -> int | None:
    """
    Keep a weekday query only when it is Monday–Friday.

    Args:
        weekday: Requested day. None, blank, or a non-integer means no filter.
            Integers outside 0–4 are ignored.

    Returns:
        int | None: 0–4, or None when the page should include every day.

    Raises:
        None.
    """
    if weekday is None or weekday == '':
        return None
    try:
        day = int(weekday)
    except (TypeError, ValueError):
        return None
    if day < 0 or day > 4:
        return None
    return day


def _customer_search_text(customer) -> str:
    """
    Text a call-centre search can match, lowercased.

    Args:
        customer: Customer row. Name, owner, contact, code, email, phone,
            and place fields are included. Each field is 0–200 characters.

    Returns:
        str: One line, at most 2000 characters. Blank fields are skipped.
    """
    parts = [
        getattr(customer, 'name', '') or '',
        getattr(customer, 'owner_name', '') or '',
        getattr(customer, 'contact_person', '') or '',
        getattr(customer, 'customer_code', '') or '',
        getattr(customer, 'email', '') or '',
        getattr(customer, 'phone', '') or '',
        getattr(customer, 'tax_id', '') or '',
        getattr(customer, 'county', '') or '',
        getattr(customer, 'sub_county', '') or '',
        getattr(customer, 'ward', '') or '',
        getattr(customer, 'city', '') or '',
        getattr(customer, 'address', '') or '',
    ]
    return ' '.join(part.strip() for part in parts if part and str(part).strip())[:2000].lower()


def _customer_matches_search(customer, search: str) -> bool:
    """
    True when this customer matches the same text used on the customer list.

    Args:
        customer: Customer row with name and phone.
        search: Typed text, trimmed to 100 characters. Blank matches everyone.

    Returns:
        bool: Name, code, place, or phone. A phone of at least 3 digits
        also matches the 07 and 254 forms.

    Raises:
        None.
    """
    from sales.customer_search import _digits_only, _phone_search_variants

    term = (search or '').strip()[:100]
    if not term:
        return True
    if term.lower() in _customer_search_text(customer):
        return True
    digits = _digits_only(term)
    if len(digits) < 3:
        return False
    phone_digits = _digits_only(getattr(customer, 'phone', '') or '')
    return any(variant in phone_digits for variant in _phone_search_variants(digits))


def build_call_book(*, today: date | None = None, scope: str = 'today', status: str = 'all', page: int = 1, page_size: int = PAGE_SIZE_DEFAULT, viewer_id: int | None = None, weekday: int | None = None, search: str | None = None) -> dict:
    """
    Build the shared book for one week.

    Args:
        today: Nairobi date. Defaults to ``nairobi_today``.
        scope: ``today`` or ``week``. On Saturday and Sunday the book always
        uses the week so the leftover list stays visible.
        status: ``not_called``, ``called``, or ``all``.
        page: 1-based page. Values below 1 are treated as 1.
        page_size: 1–1000. Out of range is clamped.
        viewer_id: User id used to flag holds that belong to the viewer.
        weekday: Optional 0–4 (Monday–Friday). Limits the page to that day.
            A customer whose call-later time has been reached stays on the
            page even when their own day is different. Outside 0–4 is ignored.
        search: Optional customer text, 0–100 characters. Blank keeps the
            day and status filters. A name, code, place, or phone searches
            the whole week, including customers already called. Phone digits
            match 07 and 254. Week totals in ``summary`` stay the full book.

    Returns:
        dict: ``summary`` counts plus ``results`` for this page. Customers
        whose call-later time has been reached come first, earliest time
        first. Then not-called shops that were missed last week, then other
        not-called shops, dormant before at-risk. Each row includes phone,
        place, this week's mark, every caller this week and last week, a
        ``caller_changed`` flag, ``missed_last_week``, the callback time,
        and whether that time has been reached. No side effects.

    Raises:
        None. Unknown scope/status fall back to today/all.
    """
    day = today or nairobi_today()
    monday = week_monday(day)
    friday = monday + timedelta(days=4)
    last_monday = monday - timedelta(days=7)
    call_day = is_call_day(day)
    if scope not in ('today', 'week'):
        scope = 'today'
    if not call_day:
        scope = 'week'
    if status not in ('not_called', 'called', 'all'):
        status = 'all'
    page = max(1, int(page or 1))
    page_size = min(PAGE_SIZE_MAX, max(1, int(page_size or PAGE_SIZE_DEFAULT)))

    settings_row = CallBookSettings.load()
    plans = list(CallDayPlan.objects.all())
    customers = list(
        Customer.objects.filter(is_active=True).only(
            'id', 'name', 'phone', 'owner_name', 'contact_person',
            'customer_code', 'email', 'tax_id', 'county', 'sub_county',
            'ward', 'city', 'address', 'latitude', 'longitude', 'buyer_segment',
            'engagement_tier', 'typical_goods', 'last_purchased_at',
        )
    )
    assignments = assign_sub_county_weekdays(sub_county_call_groups(customers))
    week_calls = (
        CustomerCall.objects.filter(week_start=monday)
        .select_related('called_by')
        .order_by('called_at')
    )
    this_week = {}
    week_call_lists: dict[int, list] = defaultdict(list)
    for call in week_calls:
        this_week[call.customer_id] = call
        week_call_lists[call.customer_id].append(call)
    last_week_calls = (
        CustomerCall.objects.filter(week_start=last_monday)
        .select_related('called_by')
        .order_by('called_at')
    )
    last_week_ids: set[int] = set()
    last_week_lists: dict[int, list] = defaultdict(list)
    for call in last_week_calls:
        last_week_ids.add(call.customer_id)
        last_week_lists[call.customer_id].append(call)
    latest_prior = (
        CustomerCall.objects.filter(week_start__lt=monday)
        .values('customer_id')
        .annotate(latest_id=Max('id'))
    )
    previous = {
        call.customer_id: call
        for call in CustomerCall.objects.filter(
            id__in=[row['latest_id'] for row in latest_prior],
        )
    }
    now = operation_now(day)
    holds = {
        hold.customer_id: hold
        for hold in CallHold.objects.filter(expires_at__gt=now).select_related('held_by')
    }

    rows = []
    cannot_call = 0
    for customer in customers:
        if not usable_phone(customer.phone):
            cannot_call += 1
            continue
        weekday = weekday_for_customer(
            customer,
            plans,
            settings_row.unlocated_weekday,
            assignments,
        )
        call = this_week.get(customer.id)
        prior = previous.get(customer.id)
        hold = holds.get(customer.id)
        due_at = _due_moment(call, prior)
        due = call_later_due(
            call.outcome if call else (prior.outcome if prior and call is None else ''),
            due_at,
            now,
        )
        callers_this_week = _caller_entries(week_call_lists.get(customer.id, []))
        callers_last_week = _caller_entries(last_week_lists.get(customer.id, []))
        missed_last_week = customer.id not in last_week_ids
        rows.append({
            '_match': _customer_matches_search(customer, search),
            'customer_id': customer.id,
            'name': customer.name,
            'phone': customer.phone,
            'county': customer.county or '',
            'sub_county': customer.sub_county or '',
            'ward': customer.ward or '',
            'buyer_segment': customer.buyer_segment or 'none',
            **_profile_fields(customer),
            'weekday': weekday,
            'called_this_week': call is not None,
            'outcome': call.outcome if call else '',
            'request_summary': call.request_summary if call else '',
            'called_at': call.called_at.isoformat() if call else None,
            'called_by': _display_name(call.called_by) if call else '',
            'callers_this_week': callers_this_week,
            'callers_last_week': callers_last_week,
            'caller_changed': _callers_changed(callers_this_week, callers_last_week),
            'missed_last_week': missed_last_week,
            'previous_summary': prior.request_summary if prior else '',
            'previous_outcome': prior.outcome if prior else '',
            'follow_up_on': call.follow_up_on.isoformat() if call and call.follow_up_on else '',
            'follow_up_at': due_at.isoformat() if due_at else (
                call.follow_up_at.isoformat() if call and call.follow_up_at else ''
            ),
            'previous_follow_up_on': prior.follow_up_on.isoformat() if prior and prior.follow_up_on else '',
            'call_later_due': due,
            'hold': _hold_payload(hold, viewer_id) if hold else None,
        })

    def sort_key(row):
        due_rank = 0 if row['call_later_due'] else 1
        due_when = row['follow_up_at'] if row['call_later_due'] else ''
        called_rank = 0 if (not row['called_this_week'] or row['call_later_due']) else 1
        missed_rank = 0 if (
            (not row['called_this_week'] or row['call_later_due']) and row['missed_last_week']
        ) else 1
        segment = SEGMENT_RANK.get(row['buyer_segment'], 9)
        return (
            due_rank,
            due_when,
            called_rank,
            missed_rank,
            segment,
            (row['name'] or '').lower(),
            row['customer_id'],
        )

    rows.sort(key=sort_key)
    callable_count = len(rows)
    called_count = sum(1 for row in rows if row['called_this_week'])
    today_rows = [row for row in rows if row['weekday'] == day.weekday()] if call_day else []
    scoped = today_rows if scope == 'today' else rows
    if status == 'not_called':
        scoped = [row for row in scoped if not row['called_this_week'] or row['call_later_due']]
    elif status == 'called':
        scoped = [row for row in scoped if row['called_this_week']]
    term = (search or '').strip()[:100]
    if term:
        scoped = [row for row in rows if row.get('_match')]
    else:
        day_filter = _weekday_filter(weekday)
        if day_filter is not None:
            scoped = [
                row for row in scoped
                if row['weekday'] == day_filter or row['call_later_due']
            ]
    total = len(scoped)
    start = (page - 1) * page_size
    page_rows = []
    for row in scoped[start:start + page_size]:
        cleaned = dict(row)
        cleaned.pop('_match', None)
        page_rows.append(cleaned)
    return {
        'summary': {
            'week_start': monday.isoformat(),
            'week_end': friday.isoformat(),
            'is_call_day': call_day,
            'weekday': day.weekday(),
            'scope': scope,
            'callable': callable_count,
            'called': called_count,
            'not_called': callable_count - called_count,
            'cannot_call': cannot_call,
            'today_callable': len(today_rows),
            'today_not_called': sum(1 for row in today_rows if not row['called_this_week']),
            'missed_last_week': sum(
                1 for row in rows
                if row['missed_last_week'] and not row['called_this_week']
            ),
            'follow_ups': sum(1 for row in rows if row['outcome'] == CustomerCall.OUTCOME_ASK_LATER),
            'days': _day_counts(rows),
        },
        'count': total,
        'page': page,
        'page_size': page_size,
        'results': page_rows,
    }


def _caller_entries(calls: list) -> list[dict]:
    """
    Compact caller list for one customer in one week.

    Args:
        calls: Ordered ``CustomerCall`` rows with ``called_by`` loaded.
            At most a few dozen per customer per week are expected.

    Returns:
        list[dict]: Each entry has ``called_by`` (1–150 chars), optional
        ``called_by_id``, ``outcome``, and ``called_at`` ISO time. Empty
        when there are no calls. No phone numbers. No writes.

    Raises:
        None.
    """
    entries = []
    for call in calls:
        entries.append({
            'called_by': _display_name(call.called_by),
            'called_by_id': call.called_by_id,
            'outcome': call.outcome or '',
            'called_at': call.called_at.isoformat() if call.called_at else '',
        })
    return entries


def _callers_changed(this_week: list[dict], last_week: list[dict]) -> bool:
    """
    Whether a different set of people called this week vs last week.

    Args:
        this_week: Caller entries from ``_caller_entries`` for this week.
        last_week: Caller entries from ``_caller_entries`` for last week.

    Returns:
        bool: True when both weeks have at least one named caller and the
        sets of ``called_by_id`` differ. False when either week is empty
        or the same people called.

    Raises:
        None.
    """
    ids_this = {entry.get('called_by_id') for entry in this_week if entry.get('called_by_id')}
    ids_last = {entry.get('called_by_id') for entry in last_week if entry.get('called_by_id')}
    if not ids_this or not ids_last:
        return False
    return ids_this != ids_last


def build_day_call_log(*, day: date | None = None, page: int = 1, page_size: int = PAGE_SIZE_DEFAULT) -> dict:
    """
    Who called which customers on one Nairobi calendar day.

    Args:
        day: Local date. Defaults to ``nairobi_today``. May be any past or
            present date; future dates return an empty page.
        page: 1-based page. Values below 1 become 1.
        page_size: 1–1000. Out of range is clamped.

    Returns:
        dict: ``day``, ``count``, ``page``, ``page_size``, ``callers``
        (unique staff names, 0–200), and ``results``. Each result has
        customer id and name, caller name, outcome, summary (0–500), and
        ``called_at``. Phone numbers are omitted. No writes.

    Raises:
        None.
    """
    target = day or nairobi_today()
    page = max(1, int(page or 1))
    page_size = min(PAGE_SIZE_MAX, max(1, int(page_size or PAGE_SIZE_DEFAULT)))
    start, end = nairobi_day_bounds(target)
    calls = list(
        CustomerCall.objects.filter(called_at__gte=start, called_at__lt=end)
        .select_related('customer', 'called_by')
        .order_by('called_at', 'id')
    )
    caller_names = []
    seen_names = set()
    for call in calls:
        name = _display_name(call.called_by)
        key = name.lower()
        if key not in seen_names:
            seen_names.add(key)
            caller_names.append(name)
    total = len(calls)
    start_index = (page - 1) * page_size
    page_calls = calls[start_index:start_index + page_size]
    results = [
        {
            'customer_id': call.customer_id,
            'name': (call.customer.name if call.customer_id else '')[:200],
            'called_by': _display_name(call.called_by),
            'outcome': call.outcome or '',
            'request_summary': (call.request_summary or '')[:SUMMARY_MAX],
            'called_at': call.called_at.isoformat() if call.called_at else '',
        }
        for call in page_calls
    ]
    return {
        'day': target.isoformat(),
        'count': total,
        'page': page,
        'page_size': page_size,
        'callers': caller_names[:200],
        'results': results,
    }


def _day_counts(rows: list) -> list:
    """
    Monday–Friday coverage for the week planner.

    Args:
        rows: Every callable customer this week, before paging. Each row
        has ``weekday`` 0–4 and ``called_this_week``.

    Returns:
        list: Five dicts, Monday first. Each has ``weekday``, ``callable``,
        ``called``, ``not_called``, and ``sub_counties`` (0–40 names).
        Counts are 0–100000. No writes.
    """
    days = []
    for index in range(WEEKDAY_COUNT):
        day_rows = [row for row in rows if row['weekday'] == index]
        called = sum(1 for row in day_rows if row['called_this_week'])
        days.append({
            'weekday': index,
            'callable': len(day_rows),
            'called': called,
            'not_called': len(day_rows) - called,
            'sub_counties': _day_sub_counties(day_rows),
        })
    return days


def _day_sub_counties(day_rows: list) -> list:
    """
    Sub-counties that share one call day.

    The sub-county is the top location on that day's list. Ward is not
    included. The same sub-county is listed once.

    Args:
        day_rows: Callable customers already assigned to one weekday.
            Each row may have ``sub_county``, 0–100 characters.

    Returns:
        list[str]: Alphabetical labels, at most 40. A blank sub-county
        is ``No sub-county``. No writes.
    """
    seen = {}
    for row in day_rows:
        raw = str(row.get('sub_county') or '').strip()[:100]
        label = raw or 'No sub-county'
        seen.setdefault(label.lower(), label)
    return sorted(seen.values(), key=str.lower)[:40]


def _parse_follow_up(value, today: date):
    """
    Parse an optional follow-up date.

    Args:
        value: Blank, or an ISO date string of at most 10 characters.
        today: Nairobi date. The follow-up must fall on this day or within
        the next 90 days.

    Returns:
        date or None: None when the value is blank.

    Raises:
        ValueError: When the text is not a date in that window.
    """
    if value in (None, ''):
        return None
    text = str(value).strip()
    if len(text) != 10:
        raise ValueError('date')
    try:
        parsed = datetime.strptime(text, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError('date')
    if parsed < today or parsed > today + timedelta(days=FOLLOW_UP_DAYS):
        raise ValueError('date')
    return parsed


def _parse_clock(value):
    """
    Parse a call-later clock time.

    Args:
        value: Blank, or ``HH:MM`` using a 24-hour clock. Hours 00–23,
            minutes 00–59. Anything else is rejected, including a phone number.

    Returns:
        time or None: None when the value is blank.

    Raises:
        ValueError: When the text is not a clock time. The message is
        ``time`` and does not repeat the input.
    """
    if value in (None, ''):
        return None
    text = str(value).strip()
    if len(text) != 5 or text[2] != ':':
        raise ValueError('time')
    hour, minute = text[:2], text[3:]
    if not (hour.isdigit() and minute.isdigit()):
        raise ValueError('time')
    hours, minutes = int(hour), int(minute)
    if hours > 23 or minutes > 59:
        raise ValueError('time')
    return time(hours, minutes)


def _combine_follow_up(day: date, clock: time) -> datetime:
    """
    Build the Nairobi moment when a call-later becomes due.

    Args:
        day: Follow-up date, today through 90 days.
        clock: Time of day, 00:00–23:59.

    Returns:
        datetime: Timezone-aware in the active Django timezone. No writes.
    """
    local = datetime.combine(day, clock)
    if timezone.is_naive(local):
        return timezone.make_aware(local, timezone.get_current_timezone())
    return local


def call_later_due(outcome: str, follow_up_at, now: datetime) -> bool:
    """
    Whether a call-later should sit at the top of the list.

    Args:
        outcome: Stored outcome. Only ``ask_later`` can be due.
        follow_up_at: Aware datetime, or None when no time was stored.
        now: Aware clock used for this page load.

    Returns:
        bool: True when the outcome is call later and ``follow_up_at`` is
        at or before ``now``. False when the time is still ahead, missing,
        or the outcome is anything else.

    Raises:
        None.
    """
    if outcome != CustomerCall.OUTCOME_ASK_LATER or follow_up_at is None or now is None:
        return False
    return follow_up_at <= now


def _due_moment(call, prior):
    """
    Callback time that can move a customer to the top.

    Args:
        call: This week's ``CustomerCall``, or None.
        prior: The newest call from an earlier week, or None.

    Returns:
        datetime or None: This week's call-later time. When this week has
        no call, the previous call-later time. None when the latest relevant
        outcome is not call later or no time was stored.

    Raises:
        None.
    """
    if call is not None:
        if call.outcome == CustomerCall.OUTCOME_ASK_LATER:
            return call.follow_up_at
        return None
    if prior is not None and prior.outcome == CustomerCall.OUTCOME_ASK_LATER:
        return prior.follow_up_at
    return None


def _clip(value, limit: int) -> str:
    """
    Short text for a call-book field.

    Args:
        value: Any stored value. None becomes an empty string.
        limit: Maximum characters, 1–300.

    Returns:
        str: Trimmed text, at most ``limit`` characters.
    """
    return str(value or '').strip()[:limit]


def _profile_fields(customer) -> dict:
    """
    General customer information for the call centre.

    Args:
        customer: Active customer. Owner, contact, code, email, address,
            city, tier, goods, and last purchase are read. Tax id, notes,
            and balances are left out.

    Returns:
        dict: Clipped strings. ``typical_goods`` is 0–12 names, each at
        most 80 characters. ``last_purchased_at`` is an ISO time or empty.
        No writes.
    """
    raw_goods = customer.typical_goods if isinstance(customer.typical_goods, list) else []
    goods = []
    for item in raw_goods[:12]:
        text = _clip(item, 80)
        if text:
            goods.append(text)
    last = customer.last_purchased_at
    return {
        'owner_name': _clip(customer.owner_name, 200),
        'contact_person': _clip(customer.contact_person, 200),
        'customer_code': _clip(customer.customer_code, 50),
        'email': _clip(customer.email, 254),
        'address': _clip(customer.address, 300),
        'city': _clip(customer.city, 100),
        'engagement_tier': _clip(customer.engagement_tier, 20) or 'prospect',
        'typical_goods': goods,
        'last_purchased_at': last.isoformat() if last else '',
    }


def _hold_payload(hold, viewer_id: int | None) -> dict:
    """
    Describe an active same-day claim without the customer's phone.

    Args:
        hold: ``CallHold`` with ``held_by`` loaded.
        viewer_id: Current user id, or None.

    Returns:
        dict: Holder name, whether it is the viewer, expiry ISO time, and
        ``day_claim`` True so the UI can say the lock lasts for the day.
    """
    return {
        'held_by': _display_name(hold.held_by),
        'held_by_me': viewer_id is not None and hold.held_by_id == viewer_id,
        'expires_at': hold.expires_at.isoformat(),
        'day_claim': True,
    }


def mark_called(*, customer_id: int, user, outcome: str, request_summary: str, follow_up_on=None, follow_up_time=None, today: date | None = None) -> tuple[str, dict]:
    """
    Record a call for this week.

    Args:
        customer_id: Active customer primary key. Positive integer.
        user: Authenticated staff member.
        outcome: ``called``, ``ask_later``, ``no_answer``, or ``unreachable``.
        request_summary: 0–500 characters. Blank is allowed. Every outcome
            counts as covered this week.
        follow_up_on: Blank, or an ISO date from today through 90 days.
            Call later with a blank date uses ``today``.
        follow_up_time: ``HH:MM``. Required when the outcome is call later.
            Ignored for the other outcomes.
        today: Nairobi date override for tests.

    Returns:
        tuple: ``(code, payload)``. Codes are ``ok``, ``weekend``,
        ``not_found``, ``no_phone``, ``bad_outcome``, ``too_long``,
        ``held``, ``called_today``, ``bad_date``, or ``bad_time``.
        Payloads never include the phone number. Side effect on ``ok``:
        inserts one ``CustomerCall`` and deletes any hold on that customer.

    Raises:
        None. Failures are returned as codes.
    """
    day = today or nairobi_today()
    if not is_call_day(day):
        return 'weekend', {'error': 'Calls are marked Monday to Friday.'}
    if outcome not in OUTCOMES:
        return 'bad_outcome', {'error': 'Choose called, call later, no answer, or unreachable.'}
    summary = (request_summary or '').strip()
    if len(summary) > SUMMARY_MAX:
        return 'too_long', {'error': 'Request summary must be 500 characters or fewer.'}
    try:
        follow_up = _parse_follow_up(follow_up_on, day)
        clock = _parse_clock(follow_up_time)
    except ValueError as exc:
        if str(exc) == 'time':
            return 'bad_time', {'error': 'Call later needs a time, as HH:MM.'}
        return 'bad_date', {'error': 'Follow-up must be today or within 90 days.'}
    follow_at = None
    if outcome == CustomerCall.OUTCOME_ASK_LATER:
        if clock is None:
            return 'bad_time', {'error': 'Call later needs a time, as HH:MM.'}
        follow_up = follow_up or day
        follow_at = _combine_follow_up(follow_up, clock)
    with transaction.atomic():
        customer = (
            Customer.objects.select_for_update()
            .filter(pk=customer_id, is_active=True)
            .first()
        )
        if customer is None:
            return 'not_found', {'error': 'Customer not found.'}
        if not usable_phone(customer.phone):
            return 'no_phone', {'error': 'This customer has no number to call.'}
        now = operation_now(day)
        hold = CallHold.objects.select_for_update().filter(customer=customer).first()
        if hold is not None and hold.expires_at > now and hold.held_by_id != user.id:
            return 'held', {
                'error': (
                    f'{_display_name(hold.held_by)} already claimed this customer today. '
                    'Only one person can call them on this day.'
                ),
                'held_by': _display_name(hold.held_by),
            }
        day_start, day_end = nairobi_day_bounds(day)
        prior_today = (
            CustomerCall.objects.select_for_update()
            .filter(
                customer=customer,
                called_at__gte=day_start,
                called_at__lt=day_end,
            )
            .select_related('called_by')
            .order_by('called_at')
            .first()
        )
        if prior_today is not None and prior_today.called_by_id != user.id:
            return 'called_today', {
                'error': (
                    f'{_display_name(prior_today.called_by)} already called this customer today. '
                    'Only one person can call them on this day.'
                ),
                'called_by': _display_name(prior_today.called_by),
            }
        CustomerCall.objects.create(
            customer=customer,
            called_by=user,
            called_at=now,
            week_start=week_monday(day),
            outcome=outcome,
            request_summary=summary,
            follow_up_on=follow_up,
            follow_up_at=follow_at,
        )
        if hold is not None:
            hold.delete()
    return 'ok', {
        'called_this_week': True,
        'outcome': outcome,
        'request_summary': summary,
        'follow_up_on': follow_up.isoformat() if follow_up else '',
        'follow_up_at': follow_at.isoformat() if follow_at else '',
    }


def hold_customer(*, customer_id: int, user, today: date | None = None) -> tuple[str, dict]:
    """
    Claim a customer for this user for the rest of the Nairobi day.

    Args:
        customer_id: Active customer primary key.
        user: Authenticated staff member.
        today: Nairobi date override. Claims are refused on the weekend.

    Returns:
        tuple: ``(code, payload)`` with the same codes as ``mark_called``
        plus ``ok`` carrying ``expires_at`` and ``day_claim``. Also
        ``called_today`` when someone else already recorded a call today.
        No phone number in the payload. Side effect on ``ok``: this user
        claims this customer until end of day and their earlier claims are
        released. One person blocks one customer for that day.
    """
    day = today or nairobi_today()
    if not is_call_day(day):
        return 'weekend', {'error': 'Calls are marked Monday to Friday.'}
    with transaction.atomic():
        customer = (
            Customer.objects.select_for_update()
            .filter(pk=customer_id, is_active=True)
            .first()
        )
        if customer is None:
            return 'not_found', {'error': 'Customer not found.'}
        if not usable_phone(customer.phone):
            return 'no_phone', {'error': 'This customer has no number to call.'}
        now = operation_now(day)
        day_start, day_end = nairobi_day_bounds(day)
        prior_today = (
            CustomerCall.objects.select_for_update()
            .filter(
                customer=customer,
                called_at__gte=day_start,
                called_at__lt=day_end,
            )
            .select_related('called_by')
            .order_by('called_at')
            .first()
        )
        if prior_today is not None and prior_today.called_by_id != user.id:
            return 'called_today', {
                'error': (
                    f'{_display_name(prior_today.called_by)} already called this customer today. '
                    'Only one person can call them on this day.'
                ),
                'called_by': _display_name(prior_today.called_by),
            }
        hold = CallHold.objects.select_for_update().filter(customer=customer).first()
        if hold is not None and hold.expires_at > now and hold.held_by_id != user.id:
            return 'held', {
                'error': (
                    f'{_display_name(hold.held_by)} already claimed this customer today. '
                    'Only one person can call them on this day.'
                ),
                'held_by': _display_name(hold.held_by),
            }
        CallHold.objects.filter(held_by=user).exclude(customer=customer).delete()
        expires = end_of_nairobi_day(day)
        if hold is None:
            CallHold.objects.create(customer=customer, held_by=user, expires_at=expires)
        else:
            hold.held_by = user
            hold.expires_at = expires
            hold.save(update_fields=['held_by', 'expires_at'])
    return 'ok', {
        'expires_at': expires.isoformat(),
        'day_claim': True,
        'hold_minutes': max(1, int((expires - now).total_seconds() // 60) or 1),
    }


def plan_payload() -> dict:
    """
    Current day plan and tuning.

    Returns:
        dict: ``unlocated_weekday`` 0–4, ``hold_minutes`` 1–30, and ``rows``.
        Side effect: may create the settings singleton.
    """
    settings_row = CallBookSettings.load()
    rows = [
        {
            'weekday': row.weekday,
            'county': row.county,
            'sub_county': row.sub_county,
            'ward': row.ward,
        }
        for row in CallDayPlan.objects.all()
    ]
    return {
        'unlocated_weekday': settings_row.unlocated_weekday,
        'hold_minutes': settings_row.hold_minutes,
        'rows': rows,
    }


def replace_plan(*, unlocated_weekday: int, hold_minutes: int, rows: list) -> tuple[str, dict]:
    """
    Replace the day plan and tuning.

    Args:
        unlocated_weekday: 0–4.
        hold_minutes: 1–30.
        rows: List of dicts with weekday, county, sub_county, ward.
        At most 200 rows. Each row needs a weekday 0–4 and at least one
        location part, each part at most 100 characters.

    Returns:
        tuple: ``(code, payload)``. ``ok`` returns ``plan_payload``.
        ``bad_plan`` returns an error string and does not write.
        Side effect on ``ok``: updates the singleton and replaces every
        ``CallDayPlan`` row.

    Raises:
        None.
    """
    try:
        weekday = int(unlocated_weekday)
        minutes = int(hold_minutes)
    except (TypeError, ValueError):
        return 'bad_plan', {'error': 'Weekday and hold minutes must be numbers.'}
    if weekday < 0 or weekday > 4:
        return 'bad_plan', {'error': 'Unlocated customers must sit on Monday to Friday.'}
    if minutes < 1 or minutes > 30:
        return 'bad_plan', {'error': 'Hold minutes must be between 1 and 30.'}
    if not isinstance(rows, list) or len(rows) > PLAN_ROW_MAX:
        return 'bad_plan', {'error': 'The day plan can have at most 200 locations.'}
    cleaned = []
    seen = set()
    for raw in rows:
        if not isinstance(raw, dict):
            return 'bad_plan', {'error': 'Each plan row must be an object.'}
        try:
            row_day = int(raw.get('weekday'))
        except (TypeError, ValueError):
            return 'bad_plan', {'error': 'Each location needs a Monday–Friday day.'}
        if row_day < 0 or row_day > 4:
            return 'bad_plan', {'error': 'Each location needs a Monday–Friday day.'}
        county = str(raw.get('county') or '').strip()[:100]
        sub = str(raw.get('sub_county') or '').strip()[:100]
        ward = str(raw.get('ward') or '').strip()[:100]
        if not county and not sub and not ward:
            return 'bad_plan', {'error': 'Each plan row needs a county, sub-county, or ward.'}
        key = (county.lower(), sub.lower(), ward.lower())
        if key in seen:
            return 'bad_plan', {'error': 'That location is already on the plan.'}
        seen.add(key)
        cleaned.append({
            'weekday': row_day,
            'county': county,
            'sub_county': sub,
            'ward': ward,
        })
    with transaction.atomic():
        settings_row = CallBookSettings.load()
        settings_row.unlocated_weekday = weekday
        settings_row.hold_minutes = minutes
        settings_row.save(update_fields=['unlocated_weekday', 'hold_minutes'])
        CallDayPlan.objects.all().delete()
        CallDayPlan.objects.bulk_create([
            CallDayPlan(**row) for row in cleaned
        ])
    return 'ok', plan_payload()
