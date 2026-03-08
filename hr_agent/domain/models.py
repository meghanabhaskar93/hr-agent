"""
Domain Models

Centralized Pydantic models and enums for the HR Agent.
This eliminates model definitions scattered across multiple files.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import date, datetime
from enum import Enum
from typing import Optional, Any


# ============================================================================
# ENUMS
# ============================================================================


class UserRole(str, Enum):
    """User role within the organization."""

    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    HR = "HR"
    FINANCE = "FINANCE"
    ADMIN = "ADMIN"


class HolidayRequestStatus(str, Enum):
    """Status of a holiday/PTO request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class EscalationStatus(str, Enum):
    """Status of an HR escalation request."""

    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"


class PolicyEffect(str, Enum):
    """Effect of a policy rule."""

    ALLOW = "allow"
    DENY = "deny"


# ============================================================================
# DOMAIN MODELS
# ============================================================================


class Employee(BaseModel):
    """Employee information."""

    model_config = ConfigDict(from_attributes=True)

    employee_id: int
    email: str
    preferred_name: str
    title: Optional[str] = None
    department: Optional[str] = None
    hire_date: Optional[date] = None
    manager_id: Optional[int] = None
    cost_center: Optional[str] = None


class Manager(BaseModel):
    """Manager information."""

    employee_id: int
    preferred_name: str
    email: str
    title: Optional[str] = None


class HolidayBalance(BaseModel):
    """Holiday/PTO balance for an employee."""

    employee_id: int
    year: int
    total_days: float
    used_days: float
    remaining: float
    pending_days: float = 0


class HolidayRequest(BaseModel):
    """A holiday/PTO request."""

    request_id: int
    employee_id: int
    start_date: date
    end_date: date
    days: float
    status: HolidayRequestStatus
    reason: Optional[str] = None
    created_at: datetime
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None


class Compensation(BaseModel):
    """Employee compensation details."""

    employee_id: int
    base_salary: float
    currency: str = "USD"
    bonus_target: Optional[float] = None
    equity_shares: Optional[int] = None
    effective_date: date


class CompanyPolicy(BaseModel):
    """Company policy document."""

    policy_id: int
    title: str
    category: str
    summary: Optional[str] = None
    content: Optional[str] = None
    effective_date: Optional[date] = None


class CompanyHoliday(BaseModel):
    """Company-observed holiday."""

    date: date
    name: str
    country: str = "US"


class Announcement(BaseModel):
    """Company announcement."""

    announcement_id: int
    title: str
    content: str
    published_at: datetime
    author: Optional[str] = None


class TeamOverview(BaseModel):
    """Overview of a manager's team."""

    manager_id: int
    manager_name: str
    headcount: int
    departments: list[str]
    direct_reports: list[Employee]


# ============================================================================
# REQUEST/RESPONSE MODELS (API Schemas)
# ============================================================================


class UserContext(BaseModel):
    """Context information about the current user."""

    user_email: str
    employee_id: int
    name: str
    role: UserRole
    direct_reports: list[int] = Field(default_factory=list)


class AgentAction(BaseModel):
    """
    Schema for agent actions.

    This is the structured format the LLM uses to invoke tools.
    """

    action: str = Field(..., description="The tool to use or final_answer")

    # Employee search/targeting
    employee_query: Optional[str] = Field(
        default=None, description="Search query for employees"
    )
    target_employee_id: Optional[int] = Field(
        default=None, description="Target employee ID"
    )

    # Time/date parameters
    year: Optional[int] = Field(
        default=None, description="Year for holiday/calendar queries"
    )
    month: Optional[int] = Field(default=None, description="Month for calendar queries")
    start_date: Optional[str] = Field(
        default=None, description="Start date (YYYY-MM-DD)"
    )
    end_date: Optional[str] = Field(default=None, description="End date (YYYY-MM-DD)")
    days: Optional[float] = Field(
        default=None, description="Number of days for requests"
    )

    # Request handling
    reason: Optional[str] = Field(
        default=None, description="Reason for request/rejection"
    )
    request_id: Optional[int] = Field(default=None, description="Holiday request ID")
    policy_id: Optional[int] = Field(default=None, description="Policy ID")

    # Filtering
    department: Optional[str] = Field(default=None, description="Department name")
    limit: Optional[int] = Field(default=None, description="Limit for results")
    page: Optional[int] = Field(default=None, description="Page number for pagination")

    # Human-in-the-loop
    confirm: Optional[bool] = Field(
        default=None, description="Confirmation for sensitive actions"
    )

    # Final response
    answer: Optional[str] = Field(default=None, description="Final answer text")

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError("Date must be in YYYY-MM-DD format") from exc
        return v


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    message: str = Field(
        ..., description="The user's message/question", min_length=1, max_length=10000
    )
    session_id: Optional[str] = Field(
        None, description="Session ID for conversation continuity"
    )


class ChatResponse(BaseModel):
    """Response body for chat endpoint."""

    response: str = Field(..., description="The agent's response")
    session_id: str = Field(..., description="Session ID for follow-up messages")
    timestamp: str = Field(..., description="Response timestamp")
    request_id: Optional[str] = Field(None, description="Unique request ID for tracing")


class SessionInfo(BaseModel):
    """Session information response."""

    session_id: str
    user_email: str
    created_at: str
    turn_count: int
    has_pending_confirmation: bool


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    version: str = "2.0.0"
    components: dict[str, str] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None


# ============================================================================
# POLICY MODELS
# ============================================================================


class PolicyContext(BaseModel):
    """Context for policy evaluation."""

    requester_id: int
    requester_email: str
    requester_role: UserRole
    target_id: Optional[int] = None
    action: str = ""
    resource_type: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class PolicyResult(BaseModel):
    """Result of policy evaluation."""

    allowed: bool
    reason: str
    matched_rule: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_message: Optional[str] = None
