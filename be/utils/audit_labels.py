"""
Human-readable labels for ``AuditLog.action`` verbs.

Public entry points:
    - ``ACTION_LABELS`` — canonical verb → display name
    - ``action_display_label`` — resolve one verb (never returns a bare number)
    - ``module_display_label`` — permission module → short desk name

Keep FE ``ACTION_LABELS`` in sync when adding verbs. Prefer this registry as
the source of truth via API ``action_display``.
"""

from __future__ import annotations

ACTION_LABELS: dict[str, str] = {
    # Core CRUD / auth
    'create': 'Created',
    'update': 'Updated',
    'delete': 'Deleted',
    'view': 'Opened / viewed',
    'read': 'Opened / viewed',
    'login': 'Signed in',
    'logout': 'Signed out',
    'login_failed': 'Failed sign-in',
    'permission_denied': 'Permission denied',
    'change_password': 'Password changed',
    'assign_role': 'Role assigned',
    'assign_permissions': 'Permissions assigned',
    'apply_preset': 'Settings preset applied',
    # Sales / money
    'checkout': 'Sale money posted',
    'sale_completed': 'Sale money posted',
    'holding_save': 'Saved holding',
    'holding_cancel': 'Cancelled holding',
    'refund': 'Refund',
    'rollback': 'Rollback',
    'uncancel': 'Sale uncancelled',
    'unvoid': 'Sale unvoided',
    'sale_discarded': 'Sale discarded',
    'debt_settlement_posted': 'Debt money posted',
    'debt_settlement_corrected': 'Debt settlement corrected',
    'debt_settlement_transferred': 'Debt settlement transferred',
    'sale_staff_transferred': 'Sale staff transferred',
    'sale_customer_transferred': 'Sale customer transferred',
    # Approvals
    'approve': 'Approved',
    'reject': 'Rejected',
    'pending_submit': 'Submitted (awaiting approval)',
    'pending_approve': 'Approved (workflow)',
    'pending_reject': 'Rejected change',
    'pending_resubmit': 'Resubmitted for approval',
    # Inventory
    'stock_adjust': 'Stock adjust',
    'stock_purchase': 'Stock purchase',
    'stock_transfer': 'Stock transfer',
    'stock_undo': 'Stock undo',
    # Payroll
    'payroll_run_created': 'Payroll run created',
    'payroll_run_calculated': 'Payroll calculated',
    'payroll_run_submitted': 'Payroll submitted',
    'payroll_run_locked': 'Payroll locked',
    'payroll_run_rejected': 'Payroll rejected',
    'payroll_run_cancelled': 'Payroll cancelled',
    # Dispatch / delivery
    'pack': 'Packed field order',
    'assign': 'Assigned delivery',
    'create_driver': 'Created driver',
    'arrive': 'Delivery arrive',
    'start': 'Delivery start',
    'collect': 'Delivery collect',
    'pod': 'Proof of delivery',
    'complete': 'Delivery complete',
    'propose_pin': 'Proposed map pin',
    'lines_update': 'Delivery lines update',
    # Payments / messaging
    'stk_push': 'M-Pesa STK push',
    'sms_template_update': 'SMS template updated',
    'sms_template_reset': 'SMS template reset',
    'sms_debt_reminders_queue': 'Debt SMS queued',
    'sms_debt_reminders_send': 'Debt SMS sent',
    # Expenses / calls / notes
    'expense_claim_filed': 'Expense claim filed',
    'expense_claim_decided': 'Expense claim decided',
    'expense_resubmitted': 'Expense resubmitted',
    'expense_voided': 'Expense voided',
    'expense_redo': 'Expense redo',
    'expense_updated': 'Expense updated',
    'call_marked': 'Call marked',
    'call_updated': 'Call updated',
    'call_held': 'Call held',
    'call_plan_saved': 'Call plan saved',
    'note_review_requested': 'Note review requested',
    'note_review_completed': 'Note review completed',
}

MODULE_LABELS: dict[str, str] = {
    'sales': 'Sales / POS',
    'products': 'Products',
    'inventory': 'Inventory',
    'customers': 'Customers',
    'users': 'Users',
    'roles': 'Roles',
    'approvals': 'Approvals',
    'expenses': 'Expenses',
    'income': 'Income',
    'bankaccounts': 'Bank accounts',
    'transfers': 'Money transfers',
    'accounting': 'Accounting',
    'payroll': 'Payroll',
    'employees': 'Employees',
    'appraisals': 'Target delivery',
    'suppliers': 'Suppliers',
    'agents': 'Field / sites',
    'dispatch': 'Dispatch',
    'delivery': 'Delivery',
    'payments': 'Payments',
    'messaging': 'Messaging',
    'daily_notes': 'Daily notes',
    'settings': 'Settings',
    'module_settings': 'Module settings',
    'website': 'Website / CMS',
    'reports': 'Reports',
}


def action_display_label(action: str | None) -> str:
    """
    Resolve a friendly action name for people-facing audit UI.

    Args:
        action: Raw ``AuditLog.action`` verb (0–32 chars typical), or None.

    Returns:
        Known label from ``ACTION_LABELS``, else title-cased snake_case.
        Never returns an empty string; ``—`` when action is blank.
        Digits-only codes are prefixed with ``Action`` so they never look
        like bare row numbers.
    """
    raw = (action or '').strip()
    if not raw:
        return '—'
    if raw in ACTION_LABELS:
        return ACTION_LABELS[raw]
    if raw.isdigit():
        return f'Action {raw}'
    return raw.replace('_', ' ').replace('-', ' ').strip().title() or '—'


def module_display_label(module: str | None) -> str:
    """
    Resolve a short module desk name.

    Args:
        module: Permission / audit module key, or None.

    Returns:
        Label from ``MODULE_LABELS``, else title-cased key, or ``—``.
    """
    raw = (module or '').strip()
    if not raw:
        return '—'
    if raw in MODULE_LABELS:
        return MODULE_LABELS[raw]
    return raw.replace('_', ' ').title()
