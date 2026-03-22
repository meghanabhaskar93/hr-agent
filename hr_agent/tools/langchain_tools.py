"""
HR Tools - LangChain Implementation

LangChain-compatible tool definitions for the HR Agent.
These tools wrap the existing service layer with LangChain's @tool decorator.

Benefits:
- Automatic schema generation from type hints
- Built-in error handling and retries
- Compatible with LangGraph workflows
- Traceable with LangSmith
"""

from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..services.base import (
    get_employee_service,
    get_holiday_service,
    get_compensation_service,
    get_company_service,
    get_escalation_service,
)


# ============================================================================
# INPUT SCHEMAS (Pydantic models for structured tool inputs)
# ============================================================================


class EmployeeSearchInput(BaseModel):
    """Input for searching employees."""

    query: str = Field(description="Search query - can be name, email, or job title")
    limit: int = Field(default=10, description="Maximum number of results to return")


class EmployeeIdInput(BaseModel):
    """Input for employee-specific operations."""

    employee_id: int = Field(description="The unique employee ID")


class HolidayBalanceInput(BaseModel):
    """Input for checking holiday balance."""

    employee_id: int = Field(description="The employee ID to check balance for")
    year: int = Field(description="The year to check balance for (e.g., 2026)")


class HolidayRequestInput(BaseModel):
    """Input for submitting a holiday request."""

    employee_id: int = Field(description="The employee ID submitting the request")
    start_date: str = Field(description="Start date in YYYY-MM-DD format")
    end_date: str = Field(description="End date in YYYY-MM-DD format")
    days: float = Field(description="Number of days requested")
    reason: Optional[str] = Field(
        default=None, description="Optional reason for the request"
    )


class HolidayActionInput(BaseModel):
    """Input for holiday request actions (cancel/approve/reject)."""

    employee_id: int = Field(
        description="The employee or manager ID performing the action"
    )
    request_id: int = Field(description="The holiday request ID")
    reason: Optional[str] = Field(
        default=None, description="Optional reason (for rejection)"
    )


class TeamCalendarInput(BaseModel):
    """Input for team calendar view."""

    manager_employee_id: int = Field(description="The manager's employee ID")
    year: int = Field(description="The year to view")
    month: Optional[int] = Field(
        default=None, description="Optional specific month (1-12)"
    )


class DepartmentInput(BaseModel):
    """Input for department queries."""

    department: str = Field(
        description="Department name (e.g., 'Engineering', 'Sales', 'HR')"
    )


class OrgChartInput(BaseModel):
    """Input for org chart retrieval."""

    root_employee_id: Optional[int] = Field(
        default=None, description="Starting employee ID (defaults to CEO)"
    )
    max_depth: int = Field(default=3, description="Maximum depth of the org chart")


class PolicyInput(BaseModel):
    """Input for policy details."""

    policy_id: int = Field(description="The policy ID to retrieve")


class YearInput(BaseModel):
    """Input for year-based queries."""

    year: int = Field(description="The year to query (e.g., 2026)")


class LimitInput(BaseModel):
    """Input for queries with a limit."""

    limit: int = Field(default=10, description="Maximum number of results")


class EscalationCategoryInsightsInput(BaseModel):
    """Input for escalation category analytics."""

    month: Optional[str] = Field(
        default=None,
        description="Month in YYYY-MM format. Defaults to current month.",
    )
    limit: int = Field(default=5, description="Maximum number of categories to return")


# ============================================================================
# EMPLOYEE SEARCH & INFO TOOLS
# ============================================================================


@tool(args_schema=EmployeeSearchInput)
def search_employee(query: str, limit: int = 10) -> list[dict]:
    """Search for employees by name, email, or job title.

    Use this tool when:
    - Looking up an employee by name (e.g., "Find Alex Kim")
    - Searching by job title (e.g., "Find all Product Managers")
    - Looking up someone's email

    Returns a list of matching employees with their basic info.
    """
    return get_employee_service().search(query, limit)


@tool(args_schema=EmployeeIdInput)
def get_employee_basic(employee_id: int) -> dict | None:
    """Get basic information about an employee.

    Use this tool when:
    - Getting someone's job title, department, or email
    - Looking up employee details by their ID
    - Answering questions about "my" info (use the requester's employee_id)

    Returns: name, email, title, department, hire_date, employee_id
    """
    return get_employee_service().get_basic_info(employee_id)


@tool(args_schema=EmployeeIdInput)
def get_employee_tenure(employee_id: int) -> dict | None:
    """Get employee tenure information including hire date and years of service.

    Use this tool when:
    - Asked "When did I start working here?"
    - Asked "How long have I been employed?"
    - Looking up hire dates or tenure

    Returns: hire_date, years_of_service, months_of_service
    """
    return get_employee_service().get_tenure(employee_id)


# ============================================================================
# ORGANIZATION STRUCTURE TOOLS
# ============================================================================


@tool(args_schema=EmployeeIdInput)
def get_manager(employee_id: int) -> dict | None:
    """Get the direct manager of an employee.

    Use this tool when:
    - Asked "Who is my manager?"
    - Asked "Who do I report to?"
    - Looking up someone's supervisor

    Returns: manager's name, email, title, employee_id
    """
    return get_employee_service().get_manager(employee_id)


@tool(args_schema=EmployeeIdInput)
def get_direct_reports(manager_employee_id: int) -> list[dict]:
    """Get all employees who report directly to a manager.

    Use this tool when:
    - Asked "Who reports to me?"
    - Asked "Show my team members"
    - Looking up a manager's direct reports

    Returns: list of employees with name, title, email
    """
    return get_employee_service().get_direct_reports(manager_employee_id)


@tool(args_schema=EmployeeIdInput)
def get_manager_chain(employee_id: int) -> list[dict]:
    """Get the full management chain from an employee up to the CEO.

    Use this tool when:
    - Asked "Show me my chain of command"
    - Asked "Who is above my manager?"
    - Looking up the full reporting hierarchy

    Returns: list of managers from direct manager to CEO
    """
    return get_employee_service().get_manager_chain(employee_id, max_depth=6)


@tool(args_schema=EmployeeIdInput)
def get_team_overview(manager_employee_id: int) -> dict:
    """Get a summary overview of a manager's team.

    Use this tool when:
    - Asked "Give me an overview of my team"
    - Looking up team statistics (headcount, departments)

    Returns: team size, departments represented, direct reports summary
    """
    return get_employee_service().get_team_overview(manager_employee_id)


@tool(args_schema=DepartmentInput)
def get_department_directory(department: str) -> list[dict]:
    """Get all employees in a specific department.

    Use this tool when:
    - Asked "Who works in Engineering?"
    - Looking up department members
    - Asked "List everyone in Sales"

    Returns: list of employees in the department
    """
    return get_employee_service().get_department_directory(department)


@tool(args_schema=OrgChartInput)
def get_org_chart(root_employee_id: int | None = None, max_depth: int = 3) -> dict:
    """Get organizational chart showing reporting structure.

    Use this tool when:
    - Asked for org chart or organizational structure
    - Visualizing reporting relationships
    - Finding the CEO or executives

    Returns: hierarchical org structure starting from specified employee or CEO
    """
    return get_employee_service().get_org_chart(root_employee_id, max_depth)


# ============================================================================
# HOLIDAY / TIME-OFF TOOLS
# ============================================================================


@tool(args_schema=HolidayBalanceInput)
def get_holiday_balance(employee_id: int, year: int) -> dict:
    """Get PTO/vacation balance for an employee.

    Use this tool when:
    - Asked "How many vacation days do I have?"
    - Asked "What's my PTO balance?"
    - Checking remaining time off

    Returns: total_days, used_days, remaining_days, pending_days
    """
    return get_holiday_service().get_balance(employee_id, year)


@tool(args_schema=HolidayBalanceInput)
def get_holiday_requests(employee_id: int, year: int) -> list[dict]:
    """Get all holiday/PTO requests for an employee.

    Use this tool when:
    - Asked "Show my vacation requests"
    - Asked "What time off have I requested?"
    - Reviewing past or pending requests

    Returns: list of requests with dates, status, and days
    """
    return get_holiday_service().get_requests(employee_id, year)


@tool(args_schema=HolidayRequestInput)
def submit_holiday_request(
    employee_id: int,
    start_date: str,
    end_date: str,
    days: float,
    reason: str | None = None,
) -> dict:
    """Submit a new vacation/PTO request.

    Use this tool when:
    - Employee wants to request time off
    - Submitting vacation dates

    IMPORTANT: This action requires confirmation before execution.

    Returns: request details with status (pending approval)
    """
    return get_holiday_service().submit_request(
        employee_id, start_date, end_date, days, reason
    )


@tool
def cancel_holiday_request(employee_id: int, request_id: int) -> dict:
    """Cancel a pending or approved holiday request.

    Use this tool when:
    - Employee wants to cancel their time off request

    IMPORTANT: This action requires confirmation before execution.

    Returns: cancellation confirmation
    """
    return get_holiday_service().cancel_request(employee_id, request_id)


@tool(args_schema=EmployeeIdInput)
def get_pending_approvals(manager_employee_id: int) -> list[dict]:
    """Get all pending holiday requests awaiting manager approval.

    Use this tool when (MANAGERS ONLY):
    - Asked "Do I have any requests to approve?"
    - Reviewing team's pending time off requests

    Returns: list of pending requests from direct reports
    """
    return get_holiday_service().get_pending_approvals(manager_employee_id)


@tool
def approve_holiday_request(manager_employee_id: int, request_id: int) -> dict:
    """Approve a holiday request (manager only).

    Use this tool when:
    - Manager wants to approve a team member's time off

    IMPORTANT: This action requires confirmation before execution.

    Returns: approval confirmation
    """
    return get_holiday_service().approve_request(manager_employee_id, request_id)


@tool
def reject_holiday_request(
    manager_employee_id: int, request_id: int, reason: str | None = None
) -> dict:
    """Reject a holiday request (manager only).

    Use this tool when:
    - Manager wants to reject a team member's time off

    IMPORTANT: This action requires confirmation before execution.

    Returns: rejection confirmation
    """
    return get_holiday_service().reject_request(manager_employee_id, request_id, reason)


@tool(args_schema=TeamCalendarInput)
def get_team_calendar(
    manager_employee_id: int, year: int, month: int | None = None
) -> list[dict]:
    """Get approved time off calendar for a manager's team.

    Use this tool when:
    - Asked "When is my team taking time off?"
    - Viewing team vacation schedule
    - Planning around team availability

    Returns: list of approved time off for team members
    """
    return get_holiday_service().get_team_calendar(manager_employee_id, year, month)


# ============================================================================
# COMPENSATION TOOLS
# ============================================================================


@tool(args_schema=EmployeeIdInput)
def get_compensation(employee_id: int) -> dict | None:
    """Get compensation/salary details for an employee.

    Use this tool when:
    - Asked "What is my salary?"
    - Looking up compensation info

    AUTHORIZATION: Users can only view their own compensation.
    HR staff and managers (for direct reports) have broader access.

    Returns: base_salary, bonus, total_compensation, currency
    """
    return get_compensation_service().get_compensation(employee_id)


@tool(args_schema=EmployeeIdInput)
def get_salary_history(employee_id: int) -> list[dict]:
    """Get salary change history for an employee.

    Use this tool when:
    - Asked about salary changes or raises
    - Looking up compensation history

    AUTHORIZATION: Same restrictions as get_compensation.

    Returns: list of salary changes with dates and amounts
    """
    return get_compensation_service().get_salary_history(employee_id)


@tool(args_schema=EmployeeIdInput)
def get_team_compensation_summary(manager_employee_id: int) -> dict:
    """Get compensation summary for a manager's team (HR/Finance only).

    Use this tool when:
    - Asked for team salary overview
    - Budget planning

    AUTHORIZATION: Restricted to HR and Finance roles only.

    Returns: team compensation statistics (min, max, avg, total)
    """
    return get_compensation_service().get_team_summary(manager_employee_id)


# ============================================================================
# COMPANY POLICIES & INFO
# ============================================================================


@tool
def get_company_policies() -> list[dict]:
    """Get list of all company policies.

    Use this tool when:
    - Asked "What are the company policies?"
    - Looking up available policies

    Returns: list of policies with id, name, and category
    """
    return get_company_service().get_policies()


@tool(args_schema=PolicyInput)
def get_policy_details(policy_id: int) -> dict | None:
    """Get full details of a specific company policy.

    Use this tool when:
    - Asked about a specific policy
    - Need policy details after listing policies

    Returns: full policy text and metadata
    """
    return get_company_service().get_policy_details(policy_id)


@tool(args_schema=YearInput)
def get_company_holidays(year: int) -> list[dict]:
    """Get company-observed holidays for a specific year.

    Use this tool when:
    - Asked "What are the company holidays?"
    - Asked "When is the office closed?"
    - Planning around holidays

    Returns: list of holiday dates and names
    """
    return get_company_service().get_holidays(year)


# ============================================================================
# ANNOUNCEMENTS & EVENTS
# ============================================================================


@tool(args_schema=LimitInput)
def get_announcements(limit: int = 10) -> list[dict]:
    """Get recent company announcements.

    Use this tool when:
    - Asked "What are the latest announcements?"
    - Looking for company news

    Returns: list of recent announcements
    """
    return get_company_service().get_announcements(limit)


@tool
def get_upcoming_events(days_ahead: int = 30) -> list[dict]:
    """Get upcoming company events.

    Use this tool when:
    - Asked "What events are coming up?"
    - Looking for company activities

    Returns: list of upcoming events with dates
    """
    return get_company_service().get_upcoming_events(days_ahead)


# ============================================================================
# HR OPS ANALYTICS TOOLS
# ============================================================================


@tool(args_schema=EscalationCategoryInsightsInput)
def get_top_escalation_categories(
    month: str | None = None, limit: int = 5
) -> dict:
    """Get top escalation categories for a month with status and resolution insights.

    Use this tool when:
    - Asked for escalation analytics or category trends
    - Asked "What are the top escalation categories this month?"

    Returns: month totals, status breakdown, resolution rate, and top categories
    """
    return get_escalation_service().get_top_categories(month=month, limit=limit)


# ============================================================================
# TOOL REGISTRY - Export all tools for LangGraph
# ============================================================================


def get_all_tools() -> list:
    """Get all available HR tools for the agent."""
    return [
        # Employee Info
        search_employee,
        get_employee_basic,
        get_employee_tenure,
        # Organization
        get_manager,
        get_direct_reports,
        get_manager_chain,
        get_team_overview,
        get_department_directory,
        get_org_chart,
        # Time Off
        get_holiday_balance,
        get_holiday_requests,
        submit_holiday_request,
        cancel_holiday_request,
        get_pending_approvals,
        approve_holiday_request,
        reject_holiday_request,
        get_team_calendar,
        # Compensation
        get_compensation,
        get_salary_history,
        get_team_compensation_summary,
        # Company Info
        get_company_policies,
        get_policy_details,
        get_company_holidays,
        get_announcements,
        get_upcoming_events,
        # HR Ops Analytics
        get_top_escalation_categories,
    ]


def get_read_only_tools() -> list:
    """Get only read-only tools (no state-changing operations)."""
    return [
        search_employee,
        get_employee_basic,
        get_employee_tenure,
        get_manager,
        get_direct_reports,
        get_manager_chain,
        get_team_overview,
        get_department_directory,
        get_org_chart,
        get_holiday_balance,
        get_holiday_requests,
        get_pending_approvals,
        get_team_calendar,
        get_compensation,
        get_salary_history,
        get_team_compensation_summary,
        get_company_policies,
        get_policy_details,
        get_company_holidays,
        get_announcements,
        get_upcoming_events,
        get_top_escalation_categories,
    ]


def get_tools_requiring_confirmation() -> list:
    """Get tools that require human confirmation before execution."""
    return [
        submit_holiday_request,
        cancel_holiday_request,
        approve_holiday_request,
        reject_holiday_request,
    ]


# Tool name to function mapping for easy lookup
TOOL_MAP = {tool.name: tool for tool in get_all_tools()}
