"""
HR Agent API Server

A FastAPI-based REST API for the HR Agent, enabling integration with
web frontends, Slack bots, Microsoft Teams, and other applications.

Built with LangGraph for agent orchestration.
"""

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import uvicorn
import uuid
from functools import lru_cache

from hr_agent.agent.langgraph_agent import run_hr_agent
from hr_agent.seed import seed_if_needed
from hr_agent.configs.config import settings
from hr_agent.utils.security import rate_limiter, audit_logger, AuditAction
from hr_agent.tracing.observability import logger, metrics
from hr_agent.utils.errors import HRAgentError, RateLimitError
from hr_agent.repositories.employee import EmployeeRepository
from hr_agent.services import get_escalation_service, get_hr_request_service


# ============================================================================
# API MODELS
# ============================================================================


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    message: str = Field(..., description="The user's message/question")
    session_id: Optional[str] = Field(
        None, description="Session ID for conversation continuity"
    )


class ChatResponse(BaseModel):
    """Response body for chat endpoint."""

    response: str = Field(..., description="The agent's response")
    session_id: str = Field(..., description="Session ID for follow-up messages")
    timestamp: str = Field(..., description="Response timestamp")


class SessionInfo(BaseModel):
    """Session information response."""

    session_id: str
    user_email: str
    created_at: str
    turn_count: int
    has_pending_confirmation: bool
    title: Optional[str] = None


class SessionTurnRecord(BaseModel):
    """Session turn history record."""

    query: str
    response: str
    timestamp: str


class UserContext(BaseModel):
    """User context information."""

    employee_id: int
    name: str
    email: str
    role: str
    direct_reports_count: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    version: str = "2.0.0"


class EscalationCreateRequest(BaseModel):
    """Request body for creating an escalation."""

    thread_id: str = Field(..., min_length=1, max_length=255)
    source_message_excerpt: str = Field(..., min_length=1, max_length=2000)
    priority: str = Field(default="MEDIUM", min_length=1, max_length=16)
    category: Optional[str] = Field(default=None, max_length=120)
    agent_suggestion: Optional[str] = Field(default=None, max_length=4000)


class EscalationTransitionRequest(BaseModel):
    """Request body for escalation status transitions."""

    new_status: str = Field(..., min_length=1, max_length=32)
    resolution_note: Optional[str] = Field(default=None, max_length=2000)


class EscalationAssignRequest(BaseModel):
    """Assign or unassign an escalation request."""

    assignee_email: Optional[str] = Field(default=None, max_length=255)


class EscalationPriorityRequest(BaseModel):
    """Change escalation priority."""

    priority: str = Field(..., min_length=1, max_length=16)


class EscalationMessageRequest(BaseModel):
    """Message the original requester."""

    message: str = Field(..., min_length=1, max_length=4000)


class EscalationRequesterReplyRequest(BaseModel):
    """Requester reply for an active escalation."""

    message: str = Field(..., min_length=1, max_length=4000)


class EscalationEscalateRequest(BaseModel):
    """Escalate request severity."""

    note: Optional[str] = Field(default=None, max_length=2000)


class EscalationRecord(BaseModel):
    """Escalation request payload."""

    escalation_id: int
    requester_employee_id: int
    requester_email: str
    thread_id: str
    source_message_excerpt: str
    status: str
    created_at: str
    updated_at: str
    updated_by_employee_id: Optional[int] = None
    resolution_note: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    assigned_to_employee_id: Optional[int] = None
    assigned_to_email: Optional[str] = None
    assigned_to_name: Optional[str] = None
    requester_name: Optional[str] = None
    requester_department: Optional[str] = None
    requester_title: Optional[str] = None
    agent_suggestion: Optional[str] = None
    last_message_to_requester: Optional[str] = None
    last_message_at: Optional[str] = None
    escalation_level: Optional[int] = None


class EscalationTimelineEvent(BaseModel):
    """Escalation timeline event payload."""

    event_id: int
    escalation_id: int
    event_type: str
    event_note: Optional[str] = None
    actor_employee_id: Optional[int] = None
    actor_email: Optional[str] = None
    actor_name: Optional[str] = None
    metadata_json: Optional[str] = None
    created_at: str


class EscalationDetailResponse(BaseModel):
    """Escalation detail payload used by HR dashboard."""

    request: EscalationRecord
    timeline: list[EscalationTimelineEvent]
    missing_fields: list[str]
    completeness_percent: int


class EscalationCounts(BaseModel):
    """Escalation counts summary."""

    total: int
    pending: int
    in_review: int
    resolved: int


class EscalationActionResult(BaseModel):
    """Generic escalation action result."""

    success: bool
    escalation_id: Optional[int] = None
    error: Optional[str] = None


class HRRequestCreateRequest(BaseModel):
    """Request body for creating canonical HR requests."""

    tenant_id: str = Field(default="default", min_length=1, max_length=120)
    subject_employee_id: Optional[int] = None
    type: str = Field(..., min_length=1, max_length=64)
    subtype: str = Field(..., min_length=1, max_length=128)
    summary: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1, max_length=5000)
    priority: str = Field(default="P2", min_length=2, max_length=2)
    risk_level: str = Field(default="LOW", min_length=3, max_length=4)
    sla_due_at: Optional[str] = Field(default=None, max_length=64)
    required_fields: list[str] = Field(default_factory=list)
    captured_fields: dict[str, Any] = Field(default_factory=dict)


class HRRequestAssignRequest(BaseModel):
    """Assign or unassign HR request."""

    assignee_user_id: Optional[str] = Field(default=None, max_length=255)


class HRRequestPriorityRequest(BaseModel):
    """Update HR request priority."""

    priority: str = Field(..., min_length=2, max_length=2)


class HRRequestStatusRequest(BaseModel):
    """Transition HR request status."""

    new_status: str = Field(..., min_length=3, max_length=32)
    resolution_text: Optional[str] = Field(default=None, max_length=4000)
    resolution_sources: list[str] = Field(default_factory=list)
    escalation_ticket_id: Optional[str] = Field(default=None, max_length=255)


class HRRequestMessageRequest(BaseModel):
    """Message requester for additional information."""

    message: str = Field(..., min_length=1, max_length=4000)


class HRRequestRequesterReplyRequest(BaseModel):
    """Requester reply on an active HR request."""

    message: str = Field(..., min_length=1, max_length=4000)


class HRRequestCaptureFieldsRequest(BaseModel):
    """Update captured fields and recompute missing fields."""

    captured_fields: dict[str, Any] = Field(default_factory=dict)


class HRRequestEscalateRequest(BaseModel):
    """Escalate HR request severity/ticketing."""

    note: Optional[str] = Field(default=None, max_length=4000)
    escalation_ticket_id: Optional[str] = Field(default=None, max_length=255)


class HRRequestRecord(BaseModel):
    """Canonical HR request payload."""

    request_id: int
    tenant_id: str

    requester_user_id: str
    requester_role: str
    subject_employee_id: Optional[int] = None

    requester_name: Optional[str] = None
    requester_department: Optional[str] = None
    requester_title: Optional[str] = None
    subject_employee_name: Optional[str] = None

    type: str
    subtype: str
    summary: str
    description: str

    priority: str
    risk_level: str
    sla_due_at: Optional[str] = None

    status: str
    assignee_user_id: Optional[str] = None
    assignee_name: Optional[str] = None
    required_fields: list[str] = Field(default_factory=list)
    captured_fields: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)

    created_at: str
    updated_at: str
    last_action_at: str

    resolution_text: Optional[str] = None
    resolution_sources: list[str] = Field(default_factory=list)
    escalation_ticket_id: Optional[str] = None
    last_message_to_requester: Optional[str] = None
    last_message_at: Optional[str] = None


class HRRequestEventRecord(BaseModel):
    """Append-only HR request event payload."""

    event_id: int
    request_id: int
    tenant_id: str
    event_type: str
    event_note: Optional[str] = None
    actor_user_id: Optional[str] = None
    actor_role: Optional[str] = None
    actor_name: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class HRRequestDetailResponse(BaseModel):
    """HR request detail used by dashboard."""

    request: HRRequestRecord
    timeline: list[HRRequestEventRecord]
    missing_fields: list[str]
    completeness_percent: int


class HRRequestCounts(BaseModel):
    """Aggregate HR request counts."""

    total: int
    new: int
    needs_info: int
    ready: int
    in_progress: int
    resolved: int
    escalated: int
    cancelled: int


class HRRequestActionResult(BaseModel):
    """Generic HR request action response."""

    success: bool
    request_id: Optional[int] = None
    error: Optional[str] = None


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="HR Agent API",
    description="An intelligent HR assistant API powered by LangGraph",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# SESSION STORAGE (In-memory for demo, use Redis in production)
# ============================================================================

_sessions: dict[str, dict] = {}


def get_or_create_session(session_id: str | None, user_email: str) -> tuple[str, dict]:
    """Get or create a session for the user."""
    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        if session["user_email"] == user_email:
            return session_id, session

    # Create new session
    new_session_id = session_id or str(uuid.uuid4())
    _sessions[new_session_id] = {
        "user_email": user_email,
        "created_at": datetime.utcnow(),
        "turns": [],
        "pending_confirmation": None,
    }
    return new_session_id, _sessions[new_session_id]


def build_session_title(session: dict) -> Optional[str]:
    """Return a concise session title from the first user query."""
    for turn in session.get("turns", []):
        query = str(turn.get("query", "")).strip()
        if query:
            condensed = " ".join(query.split())
            return f"{condensed[:48]}..." if len(condensed) > 48 else condensed
    return None


# ============================================================================
# MIDDLEWARE
# ============================================================================


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """Add request tracking, logging, and rate limiting."""
    request_id = str(uuid.uuid4())
    start_time = datetime.utcnow()

    # Set request context for logging
    logger.set_context(request_id=request_id)

    # Log request
    logger.info(
        "Request started",
        method=request.method,
        path=request.url.path,
    )

    try:
        response = await call_next(request)

        # Calculate duration
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Log response
        logger.info(
            "Request completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        # Record metrics
        metrics.histogram(
            "api.latency_ms", duration_ms, tags={"path": request.url.path}
        )
        metrics.increment(
            "api.requests",
            tags={"path": request.url.path, "status": str(response.status_code)},
        )

        # Add headers
        response.headers["X-Request-ID"] = request_id

        return response
    except Exception as e:
        logger.error("Request failed", error=str(e))
        raise


# ============================================================================
# ERROR HANDLERS
# ============================================================================


@app.exception_handler(HRAgentError)
async def hr_agent_error_handler(_request: Request, exc: HRAgentError):
    """Handle custom HR Agent errors."""
    return JSONResponse(
        status_code=_get_status_code(exc),
        content=exc.to_dict(),
    )


@app.exception_handler(RateLimitError)
async def rate_limit_error_handler(_request: Request, exc: RateLimitError):
    """Handle rate limit errors with proper headers."""
    return JSONResponse(
        status_code=429,
        content=exc.to_dict(),
        headers={"Retry-After": str(exc.details.get("retry_after_seconds", 60))},
    )


def _get_status_code(exc: HRAgentError) -> int:
    """Map exception types to HTTP status codes."""
    from hr_agent.utils.errors import (
        AuthorizationError,
        ValidationError,
        ResourceNotFoundError,
    )

    if isinstance(exc, AuthorizationError):
        return 403
    elif isinstance(exc, ValidationError):
        return 400
    elif isinstance(exc, ResourceNotFoundError):
        return 404
    return 500


def _raise_escalation_http_error(message: str, default_status: int = 400) -> None:
    """Map escalation service errors to HTTP errors."""
    lowered = message.lower()
    if "only hr/manager" in lowered or "only requester" in lowered:
        raise HTTPException(status_code=403, detail=message)
    if "not found" in lowered:
        raise HTTPException(status_code=404, detail=message)
    raise HTTPException(status_code=default_status, detail=message)


def _raise_hr_request_http_error(message: str, default_status: int = 400) -> None:
    """Map HR request service errors to HTTP errors."""
    lowered = message.lower()
    if "only hr/manager" in lowered or "only requester" in lowered:
        raise HTTPException(status_code=403, detail=message)
    if "different hr reviewer" in lowered:
        raise HTTPException(status_code=403, detail=message)
    if "not found" in lowered:
        raise HTTPException(status_code=404, detail=message)
    raise HTTPException(status_code=default_status, detail=message)


# ============================================================================
# AUTHENTICATION (Simplified for demo)
# ============================================================================


def get_requester_context(user_email: str) -> dict:
    """Get the context for the requesting user."""
    employee_repo = EmployeeRepository()
    employee = employee_repo.get_by_email(user_email)

    if not employee:
        raise ValueError(f"User {user_email} not found")

    direct_reports = employee_repo.get_direct_reports(employee["employee_id"])

    return {
        "employee_id": employee["employee_id"],
        "user_email": employee["email"],
        "name": employee["preferred_name"] or employee.get("legal_name", "Unknown"),
        "role": employee_repo.get_role_by_email(user_email),
        "department": employee["department"],
        "direct_reports": [r["employee_id"] for r in direct_reports],
        "is_manager": len(direct_reports) > 0,
    }


@lru_cache(maxsize=1)
def get_allowed_test_user_emails() -> set[str]:
    """Parse ALLOWED_TEST_USER_EMAILS into a normalized set."""
    raw = settings.allowed_test_user_emails.strip()
    if not raw:
        return set()
    return {
        email.strip().lower()
        for email in raw.split(",")
        if email and email.strip()
    }


async def get_current_user(
    request: Request, x_user_email: str = Header(..., alias="X-User-Email")
) -> dict:
    """
    Extract the current user from the request header.
    With rate limiting and audit logging.
    """
    normalized_email = x_user_email.strip().lower()
    allowed_test_emails = get_allowed_test_user_emails()
    if allowed_test_emails and normalized_email not in allowed_test_emails:
        raise HTTPException(
            status_code=403,
            detail="Access to this deployment is restricted. Contact the app owner.",
        )

    # Rate limit check
    allowed, _info = rate_limiter.is_allowed(normalized_email)
    if not allowed:
        raise RateLimitError("API", retry_after=60)

    try:
        context = get_requester_context(normalized_email)

        # Audit login/access
        audit_logger.log(
            action=AuditAction.LOGIN,
            user_email=normalized_email,
            resource_type="api",
            ip_address=request.client.host if request.client else None,
        )

        return context
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except (TypeError, KeyError) as e:
        raise HTTPException(
            status_code=500, detail=f"Authentication error: {str(e)}"
        ) from e


# ============================================================================
# STARTUP EVENT
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """Initialize the database on startup."""
    seed_if_needed()


# ============================================================================
# ENDPOINTS
# ============================================================================


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check the health of the API."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
    )


@app.get("/me", response_model=UserContext, tags=["User"])
async def get_my_info(user: dict = Depends(get_current_user)):
    """Get the current user's context information."""
    return UserContext(
        employee_id=user["employee_id"],
        name=user["name"],
        email=user["user_email"],
        role=user["role"],
        direct_reports_count=len(user.get("direct_reports", [])),
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    """
    Send a message to the HR Agent and get a response.

    Supports multi-turn conversations using session_id.
    Uses LangGraph for agent orchestration.
    """
    try:
        session_id, session = get_or_create_session(
            request.session_id, user["user_email"]
        )

        # Run the LangGraph agent
        response = run_hr_agent(
            user_email=user["user_email"],
            question=request.message,
            session_id=session_id,
            prior_turns=session.get("turns", []),
        )

        # Store the turn
        session["turns"].append(
            {
                "query": request.message,
                "response": response,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        return ChatResponse(
            response=response,
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
        )
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}") from e


@app.post("/sessions", response_model=SessionInfo, tags=["Sessions"])
async def create_new_session(user: dict = Depends(get_current_user)):
    """Create a new conversation session."""
    session_id, session = get_or_create_session(None, user["user_email"])

    return SessionInfo(
        session_id=session_id,
        user_email=user["user_email"],
        created_at=session["created_at"].isoformat(),
        turn_count=0,
        has_pending_confirmation=False,
        title=None,
    )


@app.get("/sessions/{session_id}", response_model=SessionInfo, tags=["Sessions"])
async def get_session_info(session_id: str, user: dict = Depends(get_current_user)):
    """Get information about a conversation session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    if session["user_email"] != user["user_email"]:
        raise HTTPException(status_code=403, detail="Access denied to this session")

    return SessionInfo(
        session_id=session_id,
        user_email=session["user_email"],
        created_at=session["created_at"].isoformat(),
        turn_count=len(session["turns"]),
        has_pending_confirmation=session["pending_confirmation"] is not None,
        title=build_session_title(session),
    )


@app.get(
    "/sessions/{session_id}/turns",
    response_model=list[SessionTurnRecord],
    tags=["Sessions"],
)
async def get_session_turns(session_id: str, user: dict = Depends(get_current_user)):
    """Get turn history for a conversation session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    if session["user_email"] != user["user_email"]:
        raise HTTPException(status_code=403, detail="Access denied to this session")

    turns: list[SessionTurnRecord] = []
    for turn in session.get("turns", []):
        turns.append(
            SessionTurnRecord(
                query=str(turn.get("query", "")),
                response=str(turn.get("response", "")),
                timestamp=str(turn.get("timestamp", datetime.now().isoformat())),
            )
        )
    return turns


@app.delete("/sessions/{session_id}", tags=["Sessions"])
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    """Delete a conversation session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    if session["user_email"] != user["user_email"]:
        raise HTTPException(status_code=403, detail="Access denied to this session")

    del _sessions[session_id]
    return {"message": "Session deleted successfully"}


@app.get("/sessions", response_model=list[SessionInfo], tags=["Sessions"])
async def list_my_sessions(user: dict = Depends(get_current_user)):
    """List all sessions for the current user."""
    user_sessions = [
        SessionInfo(
            session_id=sid,
            user_email=s["user_email"],
            created_at=s["created_at"].isoformat(),
            turn_count=len(s["turns"]),
            has_pending_confirmation=s["pending_confirmation"] is not None,
            title=build_session_title(s),
        )
        for sid, s in _sessions.items()
        if s["user_email"] == user["user_email"]
    ]
    return user_sessions


@app.get("/escalations", response_model=list[EscalationRecord], tags=["Escalations"])
async def list_escalations(
    status: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(get_current_user),
):
    """List escalation requests visible to the current user."""
    escalation_service = get_escalation_service()
    rows = escalation_service.list_requests(
        viewer_email=user["user_email"],
        status=status.upper() if status else None,
        limit=limit,
    )
    return [EscalationRecord(**row) for row in rows]


@app.get(
    "/escalations/{escalation_id}/detail",
    response_model=EscalationDetailResponse,
    tags=["Escalations"],
)
async def get_escalation_detail(escalation_id: int, user: dict = Depends(get_current_user)):
    """Get complete detail for one escalation request."""
    escalation_service = get_escalation_service()
    result = escalation_service.get_request_detail(
        viewer_email=user["user_email"], escalation_id=escalation_id
    )
    if not result.get("success"):
        message = result.get("error", "Failed to load escalation detail.")
        _raise_escalation_http_error(message, default_status=404)
    return EscalationDetailResponse(
        request=EscalationRecord(**result["request"]),
        timeline=[EscalationTimelineEvent(**event) for event in result["timeline"]],
        missing_fields=result["missing_fields"],
        completeness_percent=result["completeness_percent"],
    )


@app.get("/escalations/counts", response_model=EscalationCounts, tags=["Escalations"])
async def list_escalation_counts(user: dict = Depends(get_current_user)):
    """List aggregate escalation counts visible to the current user."""
    escalation_service = get_escalation_service()
    counts = escalation_service.list_counts(user["user_email"])
    return EscalationCounts(**counts)


@app.post(
    "/escalations",
    response_model=EscalationActionResult,
    tags=["Escalations"],
)
async def create_escalation(
    request: EscalationCreateRequest,
    user: dict = Depends(get_current_user),
):
    """Create a new escalation request from the current user."""
    escalation_service = get_escalation_service()
    result = escalation_service.create_request(
        requester_employee_id=user["employee_id"],
        requester_email=user["user_email"],
        thread_id=request.thread_id,
        source_message_excerpt=request.source_message_excerpt,
        priority=request.priority.upper(),
        category=request.category,
        agent_suggestion=request.agent_suggestion,
    )
    if not result.get("success"):
        message = result.get("error", "Failed to create escalation request.")
        _raise_escalation_http_error(message)
    return EscalationActionResult(**result)


@app.post(
    "/escalations/{escalation_id}/transition",
    response_model=EscalationActionResult,
    tags=["Escalations"],
)
async def transition_escalation(
    escalation_id: int,
    request: EscalationTransitionRequest,
    user: dict = Depends(get_current_user),
):
    """Transition escalation status for triage roles."""
    escalation_service = get_escalation_service()
    result = escalation_service.transition_status(
        viewer_email=user["user_email"],
        actor_employee_id=user["employee_id"],
        escalation_id=escalation_id,
        new_status=request.new_status.upper(),
        resolution_note=request.resolution_note,
    )
    if not result.get("success"):
        message = result.get("error", "Failed to transition escalation.")
        _raise_escalation_http_error(message)
    return EscalationActionResult(**result)


@app.post(
    "/escalations/{escalation_id}/assign",
    response_model=EscalationActionResult,
    tags=["Escalations"],
)
async def assign_escalation(
    escalation_id: int,
    request: EscalationAssignRequest,
    user: dict = Depends(get_current_user),
):
    """Assign or unassign escalation request ownership."""
    escalation_service = get_escalation_service()
    assignee_email = request.assignee_email.strip().lower() if request.assignee_email else None
    result = escalation_service.assign_request(
        viewer_email=user["user_email"],
        actor_employee_id=user["employee_id"],
        escalation_id=escalation_id,
        assignee_email=assignee_email,
    )
    if not result.get("success"):
        message = result.get("error", "Failed to assign escalation.")
        _raise_escalation_http_error(message)
    return EscalationActionResult(**result)


@app.post(
    "/escalations/{escalation_id}/priority",
    response_model=EscalationActionResult,
    tags=["Escalations"],
)
async def change_escalation_priority(
    escalation_id: int,
    request: EscalationPriorityRequest,
    user: dict = Depends(get_current_user),
):
    """Change escalation priority."""
    escalation_service = get_escalation_service()
    result = escalation_service.update_priority(
        viewer_email=user["user_email"],
        actor_employee_id=user["employee_id"],
        escalation_id=escalation_id,
        priority=request.priority.upper(),
    )
    if not result.get("success"):
        message = result.get("error", "Failed to update escalation priority.")
        _raise_escalation_http_error(message)
    return EscalationActionResult(**result)


@app.post(
    "/escalations/{escalation_id}/message",
    response_model=EscalationActionResult,
    tags=["Escalations"],
)
async def message_escalation_requester(
    escalation_id: int,
    request: EscalationMessageRequest,
    user: dict = Depends(get_current_user),
):
    """Record a message sent to the requester."""
    escalation_service = get_escalation_service()
    result = escalation_service.message_requester(
        viewer_email=user["user_email"],
        actor_employee_id=user["employee_id"],
        escalation_id=escalation_id,
        message=request.message,
    )
    if not result.get("success"):
        message = result.get("error", "Failed to message requester.")
        _raise_escalation_http_error(message)
    return EscalationActionResult(**result)


@app.post(
    "/escalations/{escalation_id}/requester-reply",
    response_model=EscalationActionResult,
    tags=["Escalations"],
)
async def reply_to_escalation_as_requester(
    escalation_id: int,
    request: EscalationRequesterReplyRequest,
    user: dict = Depends(get_current_user),
):
    """Record requester reply to HR on an active escalation."""
    escalation_service = get_escalation_service()
    result = escalation_service.reply_as_requester(
        viewer_email=user["user_email"],
        actor_employee_id=user["employee_id"],
        escalation_id=escalation_id,
        message=request.message,
    )
    if not result.get("success"):
        message = result.get("error", "Failed to record requester reply.")
        _raise_escalation_http_error(message)
    return EscalationActionResult(**result)


@app.post(
    "/escalations/{escalation_id}/escalate",
    response_model=EscalationActionResult,
    tags=["Escalations"],
)
async def escalate_escalation_request(
    escalation_id: int,
    request: EscalationEscalateRequest,
    user: dict = Depends(get_current_user),
):
    """Escalate case severity and urgency."""
    escalation_service = get_escalation_service()
    result = escalation_service.escalate_request(
        viewer_email=user["user_email"],
        actor_employee_id=user["employee_id"],
        escalation_id=escalation_id,
        note=request.note,
    )
    if not result.get("success"):
        message = result.get("error", "Failed to escalate request.")
        _raise_escalation_http_error(message)
    return EscalationActionResult(**result)


# ============================================================================
# HR REQUEST ENDPOINTS (Canonical Request Entity)
# ============================================================================


@app.get("/hr-requests", response_model=list[HRRequestRecord], tags=["HR Requests"])
async def list_hr_requests(
    status: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(get_current_user),
):
    """List HR requests visible to the current user."""
    hr_request_service = get_hr_request_service()
    rows = hr_request_service.list_requests(
        viewer_email=user["user_email"],
        status=status.upper() if status else None,
        limit=limit,
    )
    return [HRRequestRecord(**row) for row in rows]


@app.get("/hr-requests/counts", response_model=HRRequestCounts, tags=["HR Requests"])
async def list_hr_request_counts(user: dict = Depends(get_current_user)):
    """List aggregate HR request counts visible to current user."""
    hr_request_service = get_hr_request_service()
    counts = hr_request_service.list_counts(user["user_email"])
    return HRRequestCounts(**counts)


@app.get(
    "/hr-requests/{request_id}/detail",
    response_model=HRRequestDetailResponse,
    tags=["HR Requests"],
)
async def get_hr_request_detail(request_id: int, user: dict = Depends(get_current_user)):
    """Get full detail for one canonical HR request."""
    hr_request_service = get_hr_request_service()
    result = hr_request_service.get_request_detail(
        viewer_email=user["user_email"],
        request_id=request_id,
    )
    if not result.get("success"):
        message = result.get("error", "Failed to load HR request detail.")
        _raise_hr_request_http_error(message, default_status=404)
    return HRRequestDetailResponse(
        request=HRRequestRecord(**result["request"]),
        timeline=[HRRequestEventRecord(**event) for event in result["timeline"]],
        missing_fields=result["missing_fields"],
        completeness_percent=result["completeness_percent"],
    )


@app.post(
    "/hr-requests",
    response_model=HRRequestActionResult,
    tags=["HR Requests"],
)
async def create_hr_request(
    request: HRRequestCreateRequest,
    user: dict = Depends(get_current_user),
):
    """Create canonical HR request entity for incoming item."""
    hr_request_service = get_hr_request_service()
    result = hr_request_service.create_request(
        requester_user_id=user["user_email"],
        requester_role=user["role"],
        request_type=request.type.strip(),
        request_subtype=request.subtype.strip(),
        summary=request.summary,
        description=request.description,
        tenant_id=request.tenant_id.strip() or "default",
        subject_employee_id=request.subject_employee_id,
        priority=request.priority.upper(),
        risk_level=request.risk_level.upper(),
        sla_due_at=request.sla_due_at,
        required_fields=request.required_fields,
        captured_fields=request.captured_fields,
    )
    if not result.get("success"):
        message = result.get("error", "Failed to create HR request.")
        _raise_hr_request_http_error(message)
    return HRRequestActionResult(**result)


@app.post(
    "/hr-requests/{request_id}/assign",
    response_model=HRRequestActionResult,
    tags=["HR Requests"],
)
async def assign_hr_request(
    request_id: int,
    request: HRRequestAssignRequest,
    user: dict = Depends(get_current_user),
):
    """Assign or unassign an HR request."""
    hr_request_service = get_hr_request_service()
    assignee = request.assignee_user_id.strip().lower() if request.assignee_user_id else None
    result = hr_request_service.assign_request(
        viewer_email=user["user_email"],
        request_id=request_id,
        assignee_user_id=assignee,
    )
    if not result.get("success"):
        message = result.get("error", "Failed to assign HR request.")
        _raise_hr_request_http_error(message)
    return HRRequestActionResult(**result)


@app.post(
    "/hr-requests/{request_id}/priority",
    response_model=HRRequestActionResult,
    tags=["HR Requests"],
)
async def update_hr_request_priority(
    request_id: int,
    request: HRRequestPriorityRequest,
    user: dict = Depends(get_current_user),
):
    """Update HR request priority."""
    hr_request_service = get_hr_request_service()
    result = hr_request_service.update_priority(
        viewer_email=user["user_email"],
        request_id=request_id,
        priority=request.priority.upper(),
    )
    if not result.get("success"):
        message = result.get("error", "Failed to update priority.")
        _raise_hr_request_http_error(message)
    return HRRequestActionResult(**result)


@app.post(
    "/hr-requests/{request_id}/status",
    response_model=HRRequestActionResult,
    tags=["HR Requests"],
)
async def transition_hr_request_status(
    request_id: int,
    request: HRRequestStatusRequest,
    user: dict = Depends(get_current_user),
):
    """Transition HR request status."""
    hr_request_service = get_hr_request_service()
    result = hr_request_service.transition_status(
        viewer_email=user["user_email"],
        request_id=request_id,
        new_status=request.new_status.upper(),
        resolution_text=request.resolution_text,
        resolution_sources=request.resolution_sources or None,
        escalation_ticket_id=request.escalation_ticket_id,
    )
    if not result.get("success"):
        message = result.get("error", "Failed to transition request status.")
        _raise_hr_request_http_error(message)
    return HRRequestActionResult(**result)


@app.post(
    "/hr-requests/{request_id}/message-requester",
    response_model=HRRequestActionResult,
    tags=["HR Requests"],
)
async def message_hr_request_requester(
    request_id: int,
    request: HRRequestMessageRequest,
    user: dict = Depends(get_current_user),
):
    """Message requester for missing clarification."""
    hr_request_service = get_hr_request_service()
    result = hr_request_service.message_requester(
        viewer_email=user["user_email"],
        request_id=request_id,
        message=request.message,
    )
    if not result.get("success"):
        message = result.get("error", "Failed to message requester.")
        _raise_hr_request_http_error(message)
    return HRRequestActionResult(**result)


@app.post(
    "/hr-requests/{request_id}/requester-reply",
    response_model=HRRequestActionResult,
    tags=["HR Requests"],
)
async def reply_on_hr_request(
    request_id: int,
    request: HRRequestRequesterReplyRequest,
    user: dict = Depends(get_current_user),
):
    """Record requester reply for an active HR request."""
    hr_request_service = get_hr_request_service()
    result = hr_request_service.reply_as_requester(
        viewer_email=user["user_email"],
        request_id=request_id,
        message=request.message,
    )
    if not result.get("success"):
        message = result.get("error", "Failed to record requester reply.")
        _raise_hr_request_http_error(message)
    return HRRequestActionResult(**result)


@app.post(
    "/hr-requests/{request_id}/capture-fields",
    response_model=HRRequestActionResult,
    tags=["HR Requests"],
)
async def capture_hr_request_fields(
    request_id: int,
    request: HRRequestCaptureFieldsRequest,
    user: dict = Depends(get_current_user),
):
    """Update captured fields for multi-step request completion."""
    hr_request_service = get_hr_request_service()
    result = hr_request_service.capture_fields(
        viewer_email=user["user_email"],
        request_id=request_id,
        captured_fields=request.captured_fields,
    )
    if not result.get("success"):
        message = result.get("error", "Failed to capture fields.")
        _raise_hr_request_http_error(message)
    return HRRequestActionResult(success=True, request_id=request_id)


@app.post(
    "/hr-requests/{request_id}/escalate",
    response_model=HRRequestActionResult,
    tags=["HR Requests"],
)
async def escalate_hr_request(
    request_id: int,
    request: HRRequestEscalateRequest,
    user: dict = Depends(get_current_user),
):
    """Escalate canonical HR request."""
    hr_request_service = get_hr_request_service()
    result = hr_request_service.escalate_request(
        viewer_email=user["user_email"],
        request_id=request_id,
        escalation_ticket_id=request.escalation_ticket_id,
        note=request.note,
    )
    if not result.get("success"):
        message = result.get("error", "Failed to escalate request.")
        _raise_hr_request_http_error(message)
    return HRRequestActionResult(**result)


# ============================================================================
# METRICS ENDPOINT
# ============================================================================


@app.get("/metrics", tags=["System"])
async def get_metrics():
    """Get current metrics (for Prometheus scraping or debugging)."""
    return metrics.get_stats()


@app.get("/health/detailed", tags=["System"])
async def detailed_health_check():
    """Detailed health check with dependency status."""
    from hr_agent.utils.db import get_engine

    checks: dict[str, dict[str, Any]] = {}
    health: dict[str, Any] = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "checks": checks,
    }

    # Check database
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy"}
    except (SQLAlchemyError, OSError) as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"

    # Check LLM
    checks["llm"] = {
        "status": "configured",
        "model": settings.llm_model,
        "provider": settings.llm_provider,
    }

    # Check Langfuse tracing
    if settings.langfuse_enabled and settings.langfuse_public_key:
        checks["langfuse"] = {
            "status": "enabled",
            "host": settings.langfuse_host,
        }
    else:
        checks["langfuse"] = {"status": "disabled"}

    return health


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def main():
    """Run the API server."""
    uvicorn.run(
        "hr_agent.api:app",
        host=settings.api_host if hasattr(settings, "api_host") else "0.0.0.0",
        port=settings.api_port if hasattr(settings, "api_port") else 8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
