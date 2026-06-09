"""Reports / analytics module flags via SettingsService."""

from settings.settings_service import SettingsService

MODULE = 'reports'

# Maps ReportViewSet @action names to (setting key, user-facing label).
REPORT_ACTION_GATES: dict[str, tuple[str, str]] = {
    'dashboard': ('enable_dashboard_summary', 'Dashboard summary'),
    'sales': ('enable_sales_reports', 'Sales reports'),
    'sales_overview': ('enable_sales_reports', 'Sales reports'),
    'sales_by_person': ('enable_sales_reports', 'Sales reports'),
    'products': ('enable_product_reports', 'Product reports'),
    'top_products': ('enable_product_reports', 'Product reports'),
    'inventory': ('enable_inventory_reports', 'Inventory reports'),
    'inventory_health': ('enable_inventory_reports', 'Inventory reports'),
    'purchase': ('enable_inventory_reports', 'Inventory reports'),
    'expense': ('enable_financial_reports', 'Financial reports'),
    'income': ('enable_financial_reports', 'Financial reports'),
    'tax': ('enable_financial_reports', 'Financial reports'),
    'profit_loss': ('enable_financial_reports', 'Financial reports'),
    'annual': ('enable_financial_reports', 'Financial reports'),
    'invoice': ('enable_invoice_reports', 'Invoice reports'),
    'customer_outstanding': ('enable_invoice_reports', 'Invoice reports'),
    'supplier': ('enable_supplier_reports', 'Supplier reports'),
    'customer': ('enable_customer_reports', 'Customer reports'),
    'cash_and_payments': ('enable_cash_reports', 'Cash and payment reports'),
}


def _enabled(key: str, default: bool = True) -> bool:
    return bool(SettingsService.get(MODULE, key, default=default))


def reports_enable_dashboard_summary() -> bool:
    return _enabled('enable_dashboard_summary', True)


def reports_enable_sales_reports() -> bool:
    return _enabled('enable_sales_reports', True)


def reports_enable_product_reports() -> bool:
    return _enabled('enable_product_reports', True)


def reports_enable_inventory_reports() -> bool:
    return _enabled('enable_inventory_reports', True)


def reports_enable_financial_reports() -> bool:
    return _enabled('enable_financial_reports', True)


def reports_enable_invoice_reports() -> bool:
    return _enabled('enable_invoice_reports', True)


def reports_enable_supplier_reports() -> bool:
    return _enabled('enable_supplier_reports', True)


def reports_enable_customer_reports() -> bool:
    return _enabled('enable_customer_reports', True)


def reports_enable_cash_reports() -> bool:
    return _enabled('enable_cash_reports', True)


def reports_show_discount() -> bool:
    return _enabled('show_discount_in_reports', True)


def reports_show_tax() -> bool:
    return _enabled('show_tax_in_reports', True)


def reports_show_cost_and_profit() -> bool:
    return _enabled('show_cost_and_profit', True)


def reports_show_legacy_catalog() -> bool:
    return _enabled('show_legacy_report_catalog', True)


def reports_action_enabled(action_name: str) -> bool:
    gate = REPORT_ACTION_GATES.get(action_name)
    if not gate:
        return True
    return _enabled(gate[0], True)


def reports_action_label(action_name: str) -> str:
    gate = REPORT_ACTION_GATES.get(action_name)
    return gate[1] if gate else 'Reports'


def _strip_summary(summary: dict) -> dict:
    summary = dict(summary)
    if not reports_show_discount():
        for key in ('discount', 'total_discount', 'discount_amount'):
            summary.pop(key, None)
    if not reports_show_tax():
        for key in ('tax', 'total_tax', 'tax_amount', 'tax_rate'):
            summary.pop(key, None)
    if not reports_show_cost_and_profit():
        for key in (
            'profit',
            'net_profit',
            'profit_margin',
            'total_purchase',
            'total_purchases',
            'inventory_value',
            'total_inventory_value',
        ):
            summary.pop(key, None)
    return summary


def apply_report_response_flags(data: dict) -> dict:
    """Strip sensitive report fields based on display toggles."""
    if not isinstance(data, dict):
        return data

    data = dict(data)

    if isinstance(data.get('summary'), dict):
        data['summary'] = _strip_summary(data['summary'])

    if not reports_show_tax():
        data.pop('tax_breakdown', None)

    if not reports_show_cost_and_profit():
        data.pop('profit', None)
        data.pop('net_profit', None)
        data.pop('profit_margin', None)
        data.pop('total_purchase', None)
        data.pop('total_purchases', None)
        data.pop('total_expenses', None)
        if isinstance(data.get('growth'), dict):
            growth = dict(data['growth'])
            growth.pop('profit', None)
            growth.pop('purchase', None)
            growth.pop('expenses', None)
            data['growth'] = growth
        if isinstance(data.get('monthly_breakdown'), list):
            data['monthly_breakdown'] = [
                {k: v for k, v in row.items() if k != 'profit'}
                for row in data['monthly_breakdown']
            ]
        if isinstance(data.get('monthly_data'), list):
            data['monthly_data'] = [
                {k: v for k, v in row.items() if k != 'profit'}
                for row in data['monthly_data']
            ]
        if isinstance(data.get('recent_movements'), list):
            stripped = []
            for row in data['recent_movements']:
                row = dict(row)
                row.pop('unit_cost', None)
                row.pop('total_cost', None)
                stripped.append(row)
            data['recent_movements'] = stripped
        if isinstance(data.get('purchases'), list):
            stripped = []
            for row in data['purchases']:
                row = dict(row)
                row.pop('unit_cost', None)
                row.pop('total_cost', None)
                stripped.append(row)
            data['purchases'] = stripped

    return data
