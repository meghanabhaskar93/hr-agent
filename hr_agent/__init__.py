"""
HR Agent v2.0 - A production-ready HR assistant

Built with LangChain/LangGraph/LangSmith stack:
- LangGraph: Stateful agent workflow with checkpointing
- LangChain: Tool definitions and LLM integration
- LangSmith: Tracing and observability

Architecture:
- agent/: LangGraph agent workflow
- domain/: Models, schemas, and enums
- services/: Business logic
- tools/: LangChain tool wrappers
- repositories/: Data access layer
- configs/: Configuration models
- tracing/: Observability and tracing
- utils/: Cross-cutting utilities
- policies/: YAML policy configurations
"""

# LangGraph Agent
from .agent.langgraph_agent import HRAgentLangGraph, run_hr_agent

# Services
from .services import (
    get_employee_service,
    get_holiday_service,
    get_compensation_service,
    get_company_service,
    get_escalation_service,
    EmployeeService,
    HolidayService,
    CompensationService,
    CompanyService,
    EscalationService,
)
from .tools.langchain_tools import get_all_tools

# Domain Models
from .domain.models import (
    UserRole,
    HolidayRequestStatus,
    EscalationStatus,
    AgentAction,
    ChatRequest,
    ChatResponse,
    UserContext,
)

# Infrastructure
from .utils.registry import registry, AppRegistry
from .utils.errors import (
    HRAgentError,
    AuthorizationError,
    ValidationError,
    ResourceNotFoundError,
)

__all__ = [
    # Agent
    "HRAgentLangGraph",
    "run_hr_agent",
    # Services
    "get_employee_service",
    "get_holiday_service",
    "get_compensation_service",
    "get_company_service",
    "get_escalation_service",
    "EmployeeService",
    "HolidayService",
    "CompensationService",
    "CompanyService",
    "EscalationService",
    # Tools
    "get_all_tools",
    # Registry
    "registry",
    "AppRegistry",
    # Models
    "UserRole",
    "HolidayRequestStatus",
    "EscalationStatus",
    "AgentAction",
    "ChatRequest",
    "ChatResponse",
    "UserContext",
    # Errors
    "HRAgentError",
    "AuthorizationError",
    "ValidationError",
    "ResourceNotFoundError",
]
