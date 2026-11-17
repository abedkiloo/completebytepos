"""
Field loads: stock an agent carries, sells from that load, and returns.

A sales person writes the quantities. Shop stock leaves only when a
different manager approves that load. The person the load is written for
is an active sales employee from the staff roster. A field-load sale does
not remove stock again, and it is not a field order.
Accepting the return puts ``quantity_returned`` back on the shelf.
Missing units stay out: ``taken - sold - returned``.

Bounds: 1–40 lines on a load. Each quantity is an integer from 1 to 100000
when issuing, and 0 to the unsold quantity when returning. Notes are 0–500
characters. One open or pending load per agent.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from agents.models import FieldLoad, FieldLoadLine, FieldLoadSale

MAX_LINES = 40
MAX_QTY = 100000
NOTE_MAX = 500
OPEN_STATUSES = (
    FieldLoad.STATUS_AWAITING,
    FieldLoad.STATUS_OPEN,
    FieldLoad.STATUS_PENDING,
)
LOAD_PAYMENTS = ('cash', 'mpesa', 'credit')


class FieldLoadError(Exception):
    """A field-load rule failed. ``code`` is a short machine key."""

    def __init__(self, code: str, message: str):
        """
        Args:
            code: Stable key such as ``no_stock`` or ``over_sold``. At most 40 chars.
            message: Staff-facing text. At most 300 characters. No phone numbers.
        """
        super().__init__(message)
        self.code = code
        self.message = message


def user_may_issue(user) -> bool:
    """
    Whether this user may write a field load for a manager to confirm.

    Args:
        user: Authenticated user.

    Returns:
        bool: True for a superuser or ``agents.field_load_issue``.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    return profile.has_permission('agents', 'field_load_issue')


def user_may_approve(user) -> bool:
    """
    Whether this user may confirm a written load or accept a return count.

    Args:
        user: Authenticated user.

    Returns:
        bool: True for a superuser or ``agents.field_load_approve``.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    return profile.has_permission('agents', 'field_load_approve')


def loads_for_user(user):
    """
    Loads this user is allowed to see.

    Args:
        user: Authenticated user. Issuers and approvers see every load.
            Everyone else sees only loads where they are the agent.

    Returns:
        QuerySet of ``FieldLoad``. No writes.
    """
    qs = FieldLoad.objects.select_related(
        'agent', 'issued_by', 'reviewed_by', 'issue_approved_by',
    )
    if user_may_issue(user) or user_may_approve(user):
        return qs
    return qs.filter(agent=user)


def _display_name(user) -> str:
    """
    Staff label.

    Args:
        user: User or None.

    Returns:
        str: Full name, else username, else empty. Length 0–150.
    """
    if user is None:
        return ''
    full = (user.get_full_name() or '').strip()
    return (full or user.username or '')[:150]


def _sold_map(load: FieldLoad) -> dict:
    """
    Units sold on this load, keyed by (product_id, variant_id).

    Args:
        load: Load whose linked completed sales are counted. Refunded sales
            are excluded.

    Returns:
        dict: Values are ints 0–100000. No writes.
    """
    from sales.models import SaleItem

    rows = (
        SaleItem.objects.filter(
            sale__field_load_sale__load=load,
            sale__status='completed',
        )
        .exclude(sale__refund_status='refunded')
        .values('product_id', 'variant_id')
        .annotate(qty=Sum('quantity'))
    )
    return {(row['product_id'], row['variant_id']): int(row['qty'] or 0) for row in rows}


def _line_numbers(line: FieldLoadLine, sold: int) -> dict:
    """
    Taken, sold, returned, and missing for one line.

    Args:
        line: Load line. ``quantity_taken`` is 1–100000.
        sold: Units already sold, 0–quantity_taken.

    Returns:
        dict: ``missing`` is null until a return count exists. Otherwise
        ``taken - sold - returned``, which is 0 or more when the count is valid.
    """
    returned = line.quantity_returned
    missing = None if returned is None else line.quantity_taken - sold - returned
    price = Decimal(str(line.product.price or 0)).quantize(Decimal('0.01'))
    if price < 0:
        price = Decimal('0.00')
    return {
        'id': line.id,
        'product_id': line.product_id,
        'product_name': line.product.name,
        'variant_id': line.variant_id,
        'unit_price': f'{price:.2f}',
        'quantity_taken': line.quantity_taken,
        'quantity_sold': sold,
        'quantity_returned': returned,
        'quantity_missing': missing,
        'still_out': line.quantity_taken - sold - (returned or 0),
        'available': line.quantity_taken - sold,
    }


def serialize_load(load: FieldLoad) -> dict:
    """
    Full load for the screen, including money from its sales.

    Args:
        load: One load. Lines, sales, and customer names are read here.

    Returns:
        dict: Status, people, line counts, and ``money``. No writes.

    Raises:
        None.
    """
    rows = serialize_loads([load])
    return rows[0]


def serialize_loads(loads) -> list:
    """
    Serialize many loads with one read for lines, one for units sold, and
    one for the sales.

    Args:
        loads: Field loads, at most 100. Each may already include the agent,
            issuer, reviewer, and issue approver.

    Returns:
        list[dict]: Same shape as ``serialize_load``, in the given order.
        An empty input returns an empty list. No writes.

    Raises:
        None.
    """
    from collections import defaultdict

    from sales.models import Sale, SaleItem

    load_list = list(loads)[:100]
    if not load_list:
        return []
    ids = [load.id for load in load_list]
    lines_by_load = defaultdict(list)
    for line in FieldLoadLine.objects.filter(load_id__in=ids).select_related('product'):
        lines_by_load[line.load_id].append(line)
    sold = {}
    sold_rows = (
        SaleItem.objects.filter(
            sale__field_load_sale__load_id__in=ids,
            sale__status='completed',
        )
        .exclude(sale__refund_status='refunded')
        .values('sale__field_load_sale__load_id', 'product_id', 'variant_id')
        .annotate(qty=Sum('quantity'))
    )
    for row in sold_rows:
        sold[(row['sale__field_load_sale__load_id'], row['product_id'], row['variant_id'])] = int(row['qty'] or 0)
    sales_by_load = defaultdict(list)
    sales = (
        Sale.objects.filter(field_load_sale__load_id__in=ids, status='completed')
        .exclude(refund_status='refunded')
        .select_related('customer', 'field_load_sale')
        .order_by('id')
    )
    for sale in sales:
        sales_by_load[sale.field_load_sale.load_id].append(sale)
    return [
        _serialize_ready(
            load,
            lines_by_load[load.id],
            sold,
            sales_by_load[load.id],
        )
        for load in load_list
    ]


def _serialize_ready(load, line_rows, sold, sales) -> dict:
    """
    Build one load payload from rows already loaded.

    Args:
        load: The load. People on it are already loaded.
        line_rows: That load's lines, each with its product. 0–40.
        sold: Map of ``(load id, product id, variant id)`` to units sold.
        sales: Completed sales for this load, customer already loaded. 0–500.

    Returns:
        dict: The screen payload. No writes.

    Raises:
        None.
    """
    lines = []
    for line in line_rows:
        key = (load.id, line.product_id, line.variant_id)
        lines.append(_line_numbers(line, sold.get(key, 0)))
    expected = Decimal('0.00')
    collected = Decimal('0.00')
    cash = Decimal('0.00')
    mpesa = Decimal('0.00')
    credit = Decimal('0.00')
    sale_rows = []
    for sale in sales:
        total = Decimal(sale.total or 0)
        paid = Decimal(sale.amount_paid or 0)
        expected += total
        collected += paid
        gap = total - paid
        if gap < 0:
            gap = Decimal('0.00')
        if sale.payment_method == 'mpesa':
            mpesa += paid
        elif sale.payment_method == 'on_account':
            credit += total
            gap = Decimal('0.00')
        else:
            cash += paid
        credit += gap
        sale_rows.append({
            'id': sale.id,
            'sale_number': sale.sale_number,
            'total': f'{total.quantize(Decimal("0.01")):.2f}',
            'amount_paid': f'{paid.quantize(Decimal("0.01")):.2f}',
            'payment_method': sale.payment_method,
            'customer_name': sale.customer.name if sale.customer_id and sale.customer else '',
            'origin': 'field_load',
        })
    shortage = sum(
        line['quantity_missing']
        for line in lines
        if line['quantity_missing'] is not None and line['quantity_missing'] > 0
    )
    return {
        'id': load.id,
        'reference': load_reference(load),
        'status': load.status,
        'display_status': display_status(load.status, shortage),
        'shortage_units': shortage,
        'units_taken': sum(line['quantity_taken'] for line in lines),
        'units_sold': sum(line['quantity_sold'] for line in lines),
        'agent_id': load.agent_id,
        'agent_name': _display_name(load.agent),
        'issued_by_id': load.issued_by_id,
        'issued_by': _display_name(load.issued_by),
        'issue_approved_by': _display_name(load.issue_approved_by),
        'issued_at': load.issued_at.isoformat() if load.issued_at else None,
        'submitted_at': load.submitted_at.isoformat() if load.submitted_at else None,
        'reviewed_by': _display_name(load.reviewed_by),
        'reviewed_at': load.reviewed_at.isoformat() if load.reviewed_at else None,
        'review_note': load.review_note,
        'lines': lines,
        'sales': sale_rows,
        'money': {
            'expected': f'{expected.quantize(Decimal("0.01")):.2f}',
            'collected': f'{collected.quantize(Decimal("0.01")):.2f}',
            'cash': f'{cash.quantize(Decimal("0.01")):.2f}',
            'mpesa': f'{mpesa.quantize(Decimal("0.01")):.2f}',
            'credit': f'{credit.quantize(Decimal("0.01")):.2f}',
        },
    }


def load_reference(load: FieldLoad) -> str:
    """
    Stable label for a load, built from the issue year and primary key.

    Args:
        load: Saved load. ``pk`` is a positive integer. ``issued_at`` may be null
            on an unsaved instance, in which case the current year is used.

    Returns:
        str: ``FL-YYYY-NNNNN``, 14 characters. No writes.
    """
    when = load.issued_at or timezone.now()
    return f'FL-{when.year}-{int(load.pk or 0):05d}'


def display_status(status: str, shortage_units: int) -> str:
    """
    Screen status. Shortage is a pending count that does not balance.

    Args:
        status: Stored status. One of ``awaiting_issue``, ``open``,
            ``pending_review``, ``accepted``, or ``issue_rejected``.
        shortage_units: Units still unaccounted, 0–100000.

    Returns:
        str: ``awaiting_issue``, ``issue_rejected``, ``open``, ``accepted``,
        ``shortage``, or ``pending_review``.
    """
    if status == FieldLoad.STATUS_AWAITING:
        return 'awaiting_issue'
    if status == FieldLoad.STATUS_ISSUE_REJECTED:
        return 'issue_rejected'
    if status == FieldLoad.STATUS_ACCEPTED:
        return 'accepted'
    if status == FieldLoad.STATUS_OPEN:
        return 'open'
    if shortage_units > 0:
        return 'shortage'
    return 'pending_review'


def missing_units(taken: int, sold: int, returned) -> int | None:
    """
    Units that did not come back and were not sold.

    Args:
        taken: Units issued, 1–100000.
        sold: Units sold from the load, 0–taken.
        returned: Physical count, or None before the shop counts.

    Returns:
        int or None: ``taken - sold - returned`` once a count exists, else None.
        A valid count is 0 or more.
    """
    if returned is None:
        return None
    return int(taken) - int(sold) - int(returned)


def _parse_qty(value, *, allow_zero: bool) -> int:
    """
    Parse a quantity bound to the load rules.

    Args:
        value: Raw number.
        allow_zero: When True, 0 is valid (a full sell-through return).

    Returns:
        int: 0 or 1 through 100000.

    Raises:
        FieldLoadError: ``bad_qty`` when the value is missing, fractional,
        negative, or above 100000.
    """
    try:
        qty = int(value)
    except (TypeError, ValueError):
        raise FieldLoadError('bad_qty', 'Quantity must be a whole number.')
    lower = 0 if allow_zero else 1
    if qty < lower or qty > MAX_QTY:
        raise FieldLoadError('bad_qty', 'Quantity must be between 1 and 100000.')
    return qty


def _stock_move(*, product, variant, quantity: int, user, note: str):
    """
    Apply a signed stock adjustment for a load.

    Args:
        product: Product that tracks stock.
        variant: Variant or None.
        quantity: Negative when goods leave, positive when they return.
            Non-zero. Absolute value 1–100000.
        user: Acting user.
        note: Movement note, at most 200 characters.

    Returns:
        None. Side effect: one stock movement and a changed on-hand quantity.

    Raises:
        FieldLoadError: ``no_stock`` when the shelf does not have enough,
        or ``bad_product`` when the adjustment is rejected.
    """
    from django.core.exceptions import ValidationError
    from inventory.services import StockMovementService

    service = StockMovementService()
    try:
        service.adjust_stock(
            product_id=product.id,
            variant_id=variant.id if variant is not None else None,
            quantity=quantity,
            notes=note[:200],
            user=user,
            use_catalog_cost=quantity > 0,
        )
    except ValidationError as exc:
        text = '; '.join(getattr(exc, 'messages', []) or [str(exc)])
        if 'Insufficient' in text:
            raise FieldLoadError('no_stock', f'{product.name} does not have enough stock in the shop.')
        raise FieldLoadError('bad_product', text[:300])


def _product_for_line(product_id, variant_id):
    """
    Load a stock-tracked product and optional variant.

    Args:
        product_id: Positive product primary key.
        variant_id: Variant primary key, or None.

    Returns:
        tuple: ``(product, variant or None)``.

    Raises:
        FieldLoadError: ``bad_product`` when missing, inactive, or not tracked.
    """
    from products.models import Product, ProductVariant

    product = Product.objects.filter(pk=product_id, is_active=True).first()
    if product is None:
        raise FieldLoadError('bad_product', 'Product not found.')
    if not product.track_stock:
        raise FieldLoadError('bad_product', f'{product.name} does not track stock.')
    variant = None
    if variant_id:
        variant = ProductVariant.objects.filter(pk=variant_id, product=product).first()
        if variant is None:
            raise FieldLoadError('bad_product', 'That variant is not on this product.')
    elif product.variants.exists():
        raise FieldLoadError('bad_product', f'{product.name} needs a variant.')
    return product, variant


def list_field_agents():
    """
    Active sales employees a load can be written for.

    The list is the staff roster, not the Field Sales login role. Only
    employees in the sales department with an active login are returned,
    because the load is carried by that login.

    Returns:
        list[dict]: Up to 200 rows of ``id`` (the login user id) and
        ``name`` (1–150 characters). Phone numbers are not included.
        No writes.

    Raises:
        None. An empty list means no active sales employee has a login.
    """
    from employees.models import Employee

    rows = (
        Employee.objects.filter(
            status='active',
            department='sales',
            user__isnull=False,
            user__is_active=True,
        )
        .select_related('user')
        .order_by('first_name', 'last_name', 'employee_id')[:200]
    )
    result = []
    for row in rows:
        name = f'{row.first_name} {row.last_name}'.strip()[:150]
        result.append({'id': row.user_id, 'name': name or 'Sales employee'})
    return result


def carrier_choices(user) -> dict:
    """
    Who a load can be written for.

    A sales person writes only for themselves. A manager chooses any active
    sales employee.

    Args:
        user: Authenticated user who may issue loads.

    Returns:
        dict: ``choose_employee`` and ``results``. Results hold at most 200
        rows of ``id`` and ``name`` (1–150 characters). No phone numbers.
        No writes.

    Raises:
        None.
    """
    if user_may_approve(user):
        return {'choose_employee': True, 'results': list_field_agents()}
    return {'choose_employee': False, 'results': [_self_carrier(user)]}


def _self_carrier(user) -> dict:
    """
    The signed-in person as the only carrier of their own load.

    Args:
        user: The sales person writing the load.

    Returns:
        dict: ``id`` is their login id. ``name`` is the employee name, else
        the account name, else the username. Length 1–150. No phone number.
    """
    from employees.models import Employee

    employee = Employee.objects.filter(user=user, status='active').first()
    if employee is not None:
        name = f'{employee.first_name} {employee.last_name}'.strip()[:150]
    else:
        name = _display_name(user)
    if not name:
        name = (getattr(user, 'username', '') or 'Sales employee')[:150]
    return {'id': user.id, 'name': name}


def issue_load(*, agent_id: int, lines: list, user) -> FieldLoad:
    """
    Write a load for a manager to approve. Shop stock does not move yet.

    Args:
        agent_id: Active user who will carry the stock.
        lines: 1–40 dicts with ``product_id``, optional ``variant_id``, and
            ``quantity`` 1–100000. The same product cannot appear twice.
        user: Staff member with issue rights. A sales person can write the
            load only for themselves. A manager may choose the carrier.
            The writer cannot approve the load.

    Returns:
        FieldLoad: The new load in ``awaiting_issue``.

    Raises:
        FieldLoadError: ``forbidden``, ``bad_agent``, ``open_load``,
        ``bad_lines``, ``bad_qty``, ``bad_product``, or ``no_stock``.

    Side effects:
        Inserts the load and lines. Does not change shop stock.
    """
    if not user_may_issue(user):
        raise FieldLoadError('forbidden', 'You cannot issue a field load.')
    if not user_may_approve(user):
        if agent_id not in (None, '', user.pk) and str(agent_id) != str(user.pk):
            raise FieldLoadError('bad_agent', 'A sales person writes a load only for themselves.')
        agent_id = user.pk
    agent = User.objects.filter(pk=agent_id, is_active=True).first()
    if agent is None:
        raise FieldLoadError('bad_agent', 'Choose an active staff member.')
    if FieldLoad.objects.filter(agent=agent, status__in=OPEN_STATUSES).exists():
        raise FieldLoadError('open_load', 'This person already has a load that is not accepted.')
    if not isinstance(lines, list) or not lines or len(lines) > MAX_LINES:
        raise FieldLoadError('bad_lines', 'A load needs between 1 and 40 products.')
    parsed = []
    seen = set()
    for raw in lines:
        if not isinstance(raw, dict):
            raise FieldLoadError('bad_lines', 'Each line needs a product and a quantity.')
        qty = _parse_qty(raw.get('quantity'), allow_zero=False)
        product, variant = _product_for_line(raw.get('product_id'), raw.get('variant_id'))
        key = (product.id, variant.id if variant else None)
        if key in seen:
            raise FieldLoadError('bad_lines', f'{product.name} is already on this load.')
        seen.add(key)
        on_hand = int(product.stock_quantity or 0)
        if on_hand < qty:
            raise FieldLoadError('no_stock', f'{product.name} does not have enough stock in the shop.')
        parsed.append((product, variant, qty))
    with transaction.atomic():
        load = FieldLoad.objects.create(
            agent=agent,
            issued_by=user,
            status=FieldLoad.STATUS_AWAITING,
        )
        for product, variant, qty in parsed:
            FieldLoadLine.objects.create(
                load=load,
                product=product,
                variant=variant,
                quantity_taken=qty,
            )
    return load


def confirm_issue(*, load_id: int, user) -> FieldLoad:
    """
    A manager approves the written quantities and the stock leaves the shop.

    Args:
        load_id: Load in ``awaiting_issue``.
        user: User with approve rights. Must not be the person who wrote it.

    Returns:
        FieldLoad: Status ``open``.

    Raises:
        FieldLoadError: ``forbidden`` when the user cannot approve or wrote
        the load, ``not_found``, ``not_pending``, ``no_stock``, or ``bad_product``.

    Side effects:
        One negative stock movement per line. Sets ``issue_approved_by``
        and ``issue_approved_at``. Rolls back if any line cannot leave.
    """
    if not user_may_approve(user):
        raise FieldLoadError('forbidden', 'Only a manager can approve a load.')
    with transaction.atomic():
        load = FieldLoad.objects.select_for_update().filter(pk=load_id).first()
        if load is None:
            raise FieldLoadError('not_found', 'Load not found.')
        if load.status != FieldLoad.STATUS_AWAITING:
            raise FieldLoadError('not_pending', 'This load is not waiting for a manager.')
        if load.issued_by_id == getattr(user, 'id', None):
            raise FieldLoadError('forbidden', 'The person who wrote the load cannot approve it.')
        for line in load.lines.select_related('product', 'variant'):
            _stock_move(
                product=line.product,
                variant=line.variant,
                quantity=-line.quantity_taken,
                user=user,
                note=f'Field load {load.pk} issued',
            )
        load.status = FieldLoad.STATUS_OPEN
        load.issue_approved_by = user
        load.issue_approved_at = timezone.now()
        load.save(update_fields=['status', 'issue_approved_by', 'issue_approved_at'])
    return load


def decline_issue(*, load_id: int, user, note: str = '') -> FieldLoad:
    """
    Send a written load back to the sales person. Shop stock does not move.

    Args:
        load_id: Load in ``awaiting_issue``.
        user: User with approve rights, and not the person who wrote it.
        note: Optional note, 0–500 characters.

    Returns:
        FieldLoad: Status ``issue_rejected``. The agent can be given another load.

    Raises:
        FieldLoadError: ``forbidden``, ``not_found``, ``not_pending``, ``bad_note``.

    Side effects:
        Stores the note and reviewer. No stock movement.
    """
    if not user_may_approve(user):
        raise FieldLoadError('forbidden', 'Only a manager can send a load back.')
    text = (note or '').strip()
    if len(text) > NOTE_MAX:
        raise FieldLoadError('bad_note', 'The note must be 500 characters or fewer.')
    with transaction.atomic():
        load = FieldLoad.objects.select_for_update().filter(pk=load_id).first()
        if load is None:
            raise FieldLoadError('not_found', 'Load not found.')
        if load.status != FieldLoad.STATUS_AWAITING:
            raise FieldLoadError('not_pending', 'This load is not waiting for a manager.')
        if load.issued_by_id == getattr(user, 'id', None):
            raise FieldLoadError('forbidden', 'The person who wrote the load cannot send it back.')
        load.status = FieldLoad.STATUS_ISSUE_REJECTED
        load.review_note = text
        load.reviewed_by = user
        load.reviewed_at = timezone.now()
        load.save(update_fields=['status', 'review_note', 'reviewed_by', 'reviewed_at'])
    return load


def add_line(*, load_id: int, product_id: int, quantity, user, variant_id=None) -> FieldLoad:
    """
    Add more shop stock to an open load.

    Args:
        load_id: Open load primary key.
        product_id: Product to add or increase.
        quantity: Extra units, 1–100000. The line total cannot pass 100000.
        user: Staff member with issue rights.
        variant_id: Optional variant primary key.

    Returns:
        FieldLoad: The same load.

    Raises:
        FieldLoadError: ``forbidden``, ``not_found``, ``not_open``,
        ``bad_lines``, ``no_stock``.

    Side effects:
        Increases ``quantity_taken`` or inserts a line, and removes that
        quantity from shop stock.
    """
    if not user_may_issue(user):
        raise FieldLoadError('forbidden', 'You cannot add stock to a field load.')
    qty = _parse_qty(quantity, allow_zero=False)
    with transaction.atomic():
        load = FieldLoad.objects.select_for_update().filter(pk=load_id).first()
        if load is None:
            raise FieldLoadError('not_found', 'Load not found.')
        if load.status != FieldLoad.STATUS_OPEN:
            raise FieldLoadError('not_open', 'Stock can be added only while the load is out.')
        if load.lines.count() >= MAX_LINES:
            raise FieldLoadError('bad_lines', 'A load can have at most 40 products.')
        product, variant = _product_for_line(product_id, variant_id)
        line = load.lines.filter(product=product, variant=variant).first()
        if line is None:
            line = FieldLoadLine(load=load, product=product, variant=variant, quantity_taken=0)
        if line.quantity_taken + qty > MAX_QTY:
            raise FieldLoadError('bad_qty', 'Quantity must be between 1 and 100000.')
        _stock_move(
            product=product,
            variant=variant,
            quantity=-qty,
            user=user,
            note=f'Field load {load.pk} added',
        )
        line.quantity_taken += qty
        line.save()
    return load


def sell_from_load(
    *,
    load_id: int,
    user,
    customer_id,
    product_id,
    quantity,
    amount_paid,
    variant_id=None,
    payment_method='cash',
    tender='cash',
    notes='',
    client_channel='web',
) -> FieldLoad:
    """
    Record a field-load sale that consumes units already on the load.

    This is not a field order. A field order is packed for a customer and
    removes shop stock. This sale only reduces what the agent is carrying.

    Args:
        load_id: Open load.
        user: The agent on the load, or someone who may issue loads.
        customer_id: Customer primary key. Required when the sale is not
            fully paid so the remainder can sit on their wallet.
        product_id: A product that is on the load.
        quantity: Whole units, 1 up to the unsold remainder.
        amount_paid: Money received now, 0 up to the line total.
        variant_id: Optional variant, matching the load line.
        payment_method: ``cash``, ``mpesa``, or ``credit``.
        tender: Ignored. Kept so older clients can still send it.
        notes: Optional staff note, 0–500 characters. No phone numbers.
        client_channel: ``web`` or ``mobile``. Anything else is stored as ``web``.

    Returns:
        FieldLoad: The load after the sale is linked.

    Raises:
        FieldLoadError: ``forbidden``, ``not_found``, ``not_open``,
        ``bad_product``, ``over_sold``, ``bad_money``, ``bad_customer``,
        ``bad_note``.

    Side effects:
        Creates one completed sale with ``entry_source='field_load'`` and one
        ``FieldLoadSale``. Does not change shop stock. Posts customer debt
        for any unpaid remainder.
    """
    qty = _parse_qty(quantity, allow_zero=False)
    try:
        paid = Decimal(str(amount_paid if amount_paid is not None else 0)).quantize(Decimal('0.01'))
    except Exception:
        raise FieldLoadError('bad_money', 'Amount paid must be a number.')
    if paid < 0:
        raise FieldLoadError('bad_money', 'Amount paid cannot be negative.')
    with transaction.atomic():
        load = (
            FieldLoad.objects.select_for_update()
            .filter(pk=load_id)
            .first()
        )
        if load is None or not _can_touch(load, user):
            raise FieldLoadError('not_found', 'Load not found.')
        if load.status != FieldLoad.STATUS_OPEN:
            raise FieldLoadError('not_open', 'Sales can be recorded only while the load is out.')
        line = load.lines.select_related('product').filter(
            product_id=product_id,
            variant_id=variant_id,
        ).first()
        if line is None:
            raise FieldLoadError('bad_product', 'That product is not on this load.')
        sold = _sold_map(load).get((line.product_id, line.variant_id), 0)
        remaining = line.quantity_taken - sold
        if qty > remaining:
            raise FieldLoadError('over_sold', f'Only {remaining} left on this load.')
        unit_price = Decimal(str(line.product.price or 0)).quantize(Decimal('0.01'))
        if unit_price < 0:
            unit_price = Decimal('0.00')
        total = (unit_price * qty).quantize(Decimal('0.01'))
        if paid > total:
            raise FieldLoadError('bad_money', 'Amount paid cannot be more than the sale.')
        customer = None
        if customer_id:
            from sales.models import Customer
            customer = Customer.objects.filter(pk=customer_id, is_active=True).first()
            if customer is None:
                raise FieldLoadError('bad_customer', 'Customer not found.')
        elif paid < total:
            raise FieldLoadError('bad_customer', 'Choose a customer when the sale is not fully paid.')
        note = str(notes or '').strip()
        if len(note) > NOTE_MAX:
            raise FieldLoadError('bad_note', 'The note can be at most 500 characters.')
        stored_method, stored_paid = _resolve_tender(
            payment_method=payment_method,
            paid=paid,
            total=total,
            has_customer=customer is not None,
            tender=tender,
        )
        channel = client_channel if client_channel in ('web', 'mobile') else 'web'
        _create_load_sale(
            load=load,
            line=line,
            quantity=qty,
            unit_price=unit_price,
            total=total,
            paid=stored_paid,
            customer=customer,
            user=user,
            payment_method=stored_method,
            notes=note,
            client_channel=channel,
        )
    return load


def _resolve_tender(*, payment_method, paid: Decimal, total: Decimal, has_customer: bool, tender) -> tuple:
    """
    Map the screen's payment choice onto a stored sale tender.

    Args:
        payment_method: ``cash``, ``mpesa``, or ``credit``.
        paid: Amount the caller says was received, 2 dp, 0 through ``total``.
        total: Sale total, 2 dp, zero or more.
        has_customer: Whether a customer is attached.
        tender: Kept for callers. Ignored. Cash and M-Pesa are chosen by
            ``payment_method``.

    Returns:
        tuple: Stored payment method and the amount to record as paid.

    Raises:
        FieldLoadError: ``bad_money`` or ``bad_customer``. A ``split``
        choice is rejected.
    """
    method = (payment_method or 'cash').strip().lower()
    if method not in LOAD_PAYMENTS:
        raise FieldLoadError('bad_money', 'Choose cash, M-Pesa, or credit.')
    if method == 'credit':
        if paid != 0:
            raise FieldLoadError('bad_money', 'Credit records nothing received now.')
        if not has_customer:
            raise FieldLoadError('bad_customer', 'Choose a customer when the sale is not fully paid.')
        return 'on_account', Decimal('0.00')
    if method == 'mpesa':
        if paid != total:
            raise FieldLoadError('bad_money', 'M-Pesa pays this field load sale in full.')
        return 'mpesa', paid
    if paid > total:
        raise FieldLoadError('bad_money', 'Amount paid cannot be more than the sale.')
    if paid < total and not has_customer:
        raise FieldLoadError('bad_customer', 'Choose a customer when the sale is not fully paid.')
    if paid <= 0:
        if not has_customer:
            raise FieldLoadError('bad_customer', 'Choose a customer when the sale is not fully paid.')
        return 'on_account', Decimal('0.00')
    return 'cash', paid


def _can_touch(load: FieldLoad, user) -> bool:
    """
    Whether this user may sell or count this load.

    Args:
        load: The load.
        user: Authenticated user.

    Returns:
        bool: True for the agent, an issuer, or an approver.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if load.agent_id == user.id:
        return True
    return user_may_issue(user) or user_may_approve(user)


def _create_load_sale(
    *,
    load,
    line,
    quantity,
    unit_price,
    total,
    paid,
    customer,
    user,
    payment_method,
    notes,
    client_channel,
):
    """
    Insert the field-load sale and link it without moving stock.

    Args:
        load: Open load.
        line: Product line being sold.
        quantity: Positive int.
        unit_price: Catalog unit price, 2 dp, zero or more.
        total: ``unit_price * quantity``.
        paid: Amount received, 0 through ``total``.
        customer: Customer or None when fully paid.
        user: Acting user stored on the sale as a fallback.
        payment_method: Stored tender, one of cash, mpesa, on_account.
        notes: Optional note, already trimmed to 500 characters.
        client_channel: ``web`` or ``mobile``.

    Returns:
        None. Side effects: sale, sale item, journal, optional debt, link.

    Raises:
        FieldLoadError: ``bad_product`` when sale creation fails.
    """
    from django.core.exceptions import ValidationError
    from products.stock_utils import sellable_unit_cost
    from sales.services import SaleService

    service = SaleService()
    try:
        sale = service.create_sale(
            {
                'sale_type': 'pos',
                'payment_method': payment_method,
                'amount_paid': paid,
                'allow_partial_payment': paid < total,
                'customer': customer,
                'served_by': load.agent,
                'entry_source': 'field_load',
                'client_channel': client_channel,
                'notes': f'Field load #{load.pk}' if not notes else f'Field load #{load.pk}. {notes}',
            },
            [],
            user=load.agent or user,
            validated_items=[{
                'product': line.product,
                'variant': line.variant,
                'quantity': quantity,
                'unit_price': unit_price,
                'unit_cost': sellable_unit_cost(line.product, line.variant),
                'subtotal': total,
            }],
            complete=False,
        )
    except ValidationError as exc:
        text = '; '.join(getattr(exc, 'messages', []) or [str(exc)])
        raise FieldLoadError('bad_product', text[:300])
    sale.status = 'completed'
    sale.save(update_fields=['status', 'updated_at'])
    try:
        from accounting.services import create_sale_journal_entry
        create_sale_journal_entry(sale)
    except Exception:
        pass
    if customer is not None:
        service._apply_sale_payment(
            customer,
            sale,
            load.agent or user,
            {
                'wallet_amount_used': Decimal('0'),
                'wallet_credit_added': Decimal('0'),
                'change': Decimal('0'),
                'pending_debt': (total - paid).quantize(Decimal('0.01')),
                'amount_paid_recorded': paid,
            },
        )
    else:
        from sales.customer_intelligence import on_sale_completed
        on_sale_completed(sale)
    FieldLoadSale.objects.create(load=load, sale=sale)


def submit_return(*, load_id: int, user, lines: list) -> FieldLoad:
    """
    Record what physically came back and send the load for review.

    Args:
        load_id: Open load.
        user: The agent or someone who may issue or approve.
        lines: One dict per load line with ``line_id`` and
            ``quantity_returned``. Returned units are 0 through
            ``taken - sold``.

    Returns:
        FieldLoad: Status ``pending_review``.

    Raises:
        FieldLoadError: ``not_found``, ``not_open``, ``bad_lines``, ``bad_qty``.

    Side effects:
        Saves ``quantity_returned`` and ``submitted_at``. Does not move stock.
    """
    if not isinstance(lines, list) or not lines:
        raise FieldLoadError('bad_lines', 'Enter a return count for every product.')
    with transaction.atomic():
        load = FieldLoad.objects.select_for_update().filter(pk=load_id).first()
        if load is None or not _can_touch(load, user):
            raise FieldLoadError('not_found', 'Load not found.')
        if load.status != FieldLoad.STATUS_OPEN:
            raise FieldLoadError('not_open', 'A return count can be submitted only while the load is out.')
        by_id = {line.id: line for line in load.lines.all()}
        if len(lines) != len(by_id):
            raise FieldLoadError('bad_lines', 'Enter a return count for every product.')
        sold = _sold_map(load)
        seen = set()
        for raw in lines:
            if not isinstance(raw, dict):
                raise FieldLoadError('bad_lines', 'Each return needs a line and a quantity.')
            try:
                line_id = int(raw.get('line_id'))
            except (TypeError, ValueError):
                raise FieldLoadError('bad_lines', 'Each return needs a line and a quantity.')
            line = by_id.get(line_id)
            if line is None or line_id in seen:
                raise FieldLoadError('bad_lines', 'Each return needs a line and a quantity.')
            seen.add(line_id)
            returned = _parse_qty(raw.get('quantity_returned'), allow_zero=True)
            sold_qty = sold.get((line.product_id, line.variant_id), 0)
            if returned > line.quantity_taken - sold_qty:
                raise FieldLoadError(
                    'bad_qty',
                    'Returned quantity cannot be more than what was not sold.',
                )
            line.quantity_returned = returned
            line.save(update_fields=['quantity_returned'])
        load.status = FieldLoad.STATUS_PENDING
        load.submitted_at = timezone.now()
        load.save(update_fields=['status', 'submitted_at'])
    return load


def review_load(*, load_id: int, user, accept: bool, note: str = '') -> FieldLoad:
    """
    Accept the return or send the count back.

    Args:
        load_id: Load in ``pending_review``.
        user: User with approve rights.
        accept: True puts returned units back on the shelf and closes the
            load. False reopens it so the count can be corrected. Sales
            already recorded stay recorded.
        note: Optional note, 0–500 characters.

    Returns:
        FieldLoad: ``accepted`` or ``open``.

    Raises:
        FieldLoadError: ``forbidden``, ``not_found``, ``not_pending``, ``bad_note``.

    Side effects:
        On accept, one positive stock movement per line with a return above
        zero. On reject, no stock movement.
    """
    if not user_may_approve(user):
        raise FieldLoadError('forbidden', 'Only a manager can accept or send back a load.')
    text = (note or '').strip()
    if len(text) > NOTE_MAX:
        raise FieldLoadError('bad_note', 'The note must be 500 characters or fewer.')
    with transaction.atomic():
        load = FieldLoad.objects.select_for_update().filter(pk=load_id).first()
        if load is None:
            raise FieldLoadError('not_found', 'Load not found.')
        if load.status != FieldLoad.STATUS_PENDING:
            raise FieldLoadError('not_pending', 'This load is not waiting for a manager.')
        load.review_note = text
        load.reviewed_by = user
        load.reviewed_at = timezone.now()
        if not accept:
            load.status = FieldLoad.STATUS_OPEN
            load.save(update_fields=['status', 'review_note', 'reviewed_by', 'reviewed_at'])
            return load
        for line in load.lines.select_related('product', 'variant'):
            returned = line.quantity_returned or 0
            if returned > 0:
                _stock_move(
                    product=line.product,
                    variant=line.variant,
                    quantity=returned,
                    user=user,
                    note=f'Field load {load.pk} returned',
                )
        load.status = FieldLoad.STATUS_ACCEPTED
        load.save(update_fields=['status', 'review_note', 'reviewed_by', 'reviewed_at'])
    return load
