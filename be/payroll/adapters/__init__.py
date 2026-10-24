from payroll.adapters.attendance import fetch_absence_deduction
from payroll.adapters.bonus import fetch_appraisal_bonus
from payroll.adapters.loans import fetch_loan_deduction

__all__ = [
    'fetch_appraisal_bonus',
    'fetch_loan_deduction',
    'fetch_absence_deduction',
]
