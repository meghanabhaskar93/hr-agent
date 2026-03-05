"""
Repository Layer - Data Access Abstraction

This layer abstracts database operations behind clean interfaces.
Benefits:
- Easy to swap data sources (SQL → API → Mock)
- Testable with mock implementations
- Clean separation between business logic and data access
"""

from .base import BaseRepository
from .employee import EmployeeRepository
from .holiday import HolidayRepository
from .compensation import CompensationRepository
from .company import CompanyRepository
from .escalation import EscalationRepository

# Singleton instances
_employee_repo: EmployeeRepository | None = None
_holiday_repo: HolidayRepository | None = None
_compensation_repo: CompensationRepository | None = None
_company_repo: CompanyRepository | None = None
_escalation_repo: EscalationRepository | None = None


def get_employee_repo() -> EmployeeRepository:
    global _employee_repo
    if _employee_repo is None:
        _employee_repo = EmployeeRepository()
    return _employee_repo


def get_holiday_repo() -> HolidayRepository:
    global _holiday_repo
    if _holiday_repo is None:
        _holiday_repo = HolidayRepository()
    return _holiday_repo


def get_compensation_repo() -> CompensationRepository:
    global _compensation_repo
    if _compensation_repo is None:
        _compensation_repo = CompensationRepository()
    return _compensation_repo


def get_company_repo() -> CompanyRepository:
    global _company_repo
    if _company_repo is None:
        _company_repo = CompanyRepository()
    return _company_repo


def get_escalation_repo() -> EscalationRepository:
    global _escalation_repo
    if _escalation_repo is None:
        _escalation_repo = EscalationRepository()
    return _escalation_repo


__all__ = [
    "BaseRepository",
    "EmployeeRepository",
    "HolidayRepository",
    "CompensationRepository",
    "CompanyRepository",
    "EscalationRepository",
    "get_employee_repo",
    "get_holiday_repo",
    "get_compensation_repo",
    "get_company_repo",
    "get_escalation_repo",
]
