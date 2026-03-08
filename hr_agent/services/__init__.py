"""
Services Module - Business Logic Layer

Contains:
- Service classes for business logic
- LangChain-formatted tools for the LangGraph agent
"""

from .base import (
    EmployeeService,
    HolidayService,
    CompensationService,
    CompanyService,
    EscalationService,
    get_employee_service,
    get_holiday_service,
    get_compensation_service,
    get_company_service,
    get_escalation_service,
)

# LangChain tools
__all__ = [
    # Services
    "EmployeeService",
    "HolidayService",
    "CompensationService",
    "CompanyService",
    "EscalationService",
    "get_employee_service",
    "get_holiday_service",
    "get_compensation_service",
    "get_company_service",
    "get_escalation_service",
]
