from utils.money_format import format_grouped_number, format_kes


def test_format_grouped_number():
    assert format_grouped_number(1000, decimals=None) == '1,000'
    assert format_grouped_number('1000.50', decimals=None) == '1,000.5'
    assert format_grouped_number(1234567.8, decimals=2) == '1,234,567.80'
    assert format_grouped_number(1500, decimals=0) == '1,500'


def test_format_kes():
    assert format_kes(1000) == 'KES 1,000.00'
