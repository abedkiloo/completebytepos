"""Default chart of accounts types — shared by init command and report endpoints."""

from .models import AccountType

DEFAULT_ACCOUNT_TYPES = (
    {'name': 'asset', 'description': 'Assets', 'normal_balance': 'debit'},
    {'name': 'liability', 'description': 'Liabilities', 'normal_balance': 'credit'},
    {'name': 'equity', 'description': 'Equity', 'normal_balance': 'credit'},
    {'name': 'revenue', 'description': 'Revenue', 'normal_balance': 'credit'},
    {'name': 'expense', 'description': 'Expenses', 'normal_balance': 'debit'},
)


def ensure_default_account_types():
    """Create the five standard account types if missing. Returns name → instance."""
    result = {}
    for spec in DEFAULT_ACCOUNT_TYPES:
        obj, _created = AccountType.objects.get_or_create(
            name=spec['name'],
            defaults={
                'description': spec['description'],
                'normal_balance': spec['normal_balance'],
            },
        )
        result[spec['name']] = obj
    return result


def get_account_type(name):
    """Return an account type, creating defaults on first use."""
    spec = next((t for t in DEFAULT_ACCOUNT_TYPES if t['name'] == name), None)
    if spec is None:
        raise ValueError(f'Unknown account type: {name}')
    obj, _created = AccountType.objects.get_or_create(
        name=spec['name'],
        defaults={
            'description': spec['description'],
            'normal_balance': spec['normal_balance'],
        },
    )
    return obj
