"""
HR Agent - LangGraph Implementation

A LangGraph-based agent for HR operations with:
- State-based workflow management
- Authorization checks
- Tool execution with structured outputs
- Langfuse tracing support
"""

from typing import TypedDict, Annotated, Literal, Any, Sequence
from datetime import datetime
import json
import operator

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from ..tools.langchain_tools import (
    get_all_tools,
    TOOL_MAP,
)
from ..services.base import get_employee_service
from ..configs.config import settings, get_langfuse_handler
from ..tracing.observability import logger
from ..policies.policy_engine import get_policy_engine, PolicyContext


# ============================================================================
# STATE DEFINITION
# ============================================================================


class AgentState(TypedDict):
    """State for the HR Agent graph.

    Attributes:
        messages: Conversation history
        user_email: The authenticated user's email
        user_id: The authenticated user's employee ID
        user_role: The user's role (employee, manager, hr, finance)
        tools_called: List of tools called in this session
        current_date: Today's date for context
    """

    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_email: str
    user_id: int
    user_role: str
    tools_called: list[str]
    current_date: str


# ============================================================================
# SYSTEM PROMPT
# ============================================================================


SYSTEM_PROMPT = """You are an intelligent HR assistant for ACME Corporation. You help employees with HR-related questions and tasks.

Current Date: {current_date}
User: {user_name} ({user_email}) - {user_role}
User Employee ID: {user_id}

**CRITICAL RULES:**
1. You MUST use tools to retrieve ALL factual information about employees, PTO, salaries, etc.
2. NEVER make up or guess any data - always use the appropriate tool first.
3. When the user says "my" or "I", use their employee_id ({user_id}) as the target.
4. To look up another employee by name, use search_employee first to get their ID.
5. For HR analytics questions (for example, "top escalation categories this month"), call get_top_escalation_categories before answering and summarize both category mix and status/resolution insights.

**Available Tool Categories:**
- Employee Info: search_employee, get_employee_basic, get_employee_tenure
- Organization: get_manager, get_direct_reports, get_manager_chain, get_team_overview, get_department_directory, get_org_chart
- Time Off: get_holiday_balance, get_holiday_requests, submit_holiday_request, cancel_holiday_request, get_pending_approvals, approve_holiday_request, reject_holiday_request, get_team_calendar
- Compensation: get_compensation, get_salary_history, get_team_compensation_summary (restricted)
- Company Info: get_company_policies, get_policy_details, get_company_holidays, get_announcements, get_upcoming_events
- HR Ops Analytics: get_top_escalation_categories

**Authorization:**
- Users can access their own information
- Managers can view their direct reports' info
- HR can access all employee data
- Compensation data is restricted - users can only see their own salary

**Guidelines:**
- Be helpful and concise
- If access is denied, explain what the user CAN do instead
- For sensitive actions (submitting requests, approvals), confirmation will be requested
"""


def get_system_message(state: AgentState) -> SystemMessage:
    """Generate system message with user context."""
    # Get user info
    user_info = get_employee_service().get_basic_info(state["user_id"])
    user_name = user_info.get("preferred_name", "User") if user_info else "User"

    return SystemMessage(
        content=SYSTEM_PROMPT.format(
            current_date=state["current_date"],
            user_name=user_name,
            user_email=state["user_email"],
            user_role=state["user_role"],
            user_id=state["user_id"],
        )
    )


# ============================================================================
# LLM SETUP (cached)
# ============================================================================

_cached_llm = None


def get_llm():
    """Get the configured LLM with tools bound (cached)."""
    global _cached_llm
    if _cached_llm is not None:
        return _cached_llm

    if settings.llm_base_url:
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
        )
    else:
        llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=0,
        )

    tools = get_all_tools()
    _cached_llm = llm.bind_tools(tools)
    return _cached_llm


# ============================================================================
# NODE FUNCTIONS
# ============================================================================


def agent_node(state: AgentState) -> dict:
    """Main agent node - calls LLM to decide next action."""
    llm = get_llm()

    # Build messages with system prompt
    messages = [get_system_message(state)] + list(state["messages"])

    # Call LLM
    response = llm.invoke(messages)

    return {"messages": [response]}


def check_authorization(state: AgentState) -> dict:
    """Check if the requested tool call is authorized."""
    messages = state["messages"]
    last_message = messages[-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}

    policy_engine = get_policy_engine()

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        # Get target employee ID if specified
        target_id = tool_args.get("employee_id") or tool_args.get("manager_employee_id")

        # Create policy context
        ctx = PolicyContext(
            requester_id=state["user_id"],
            requester_email=state["user_email"],
            requester_role=state["user_role"],
            action=tool_name,
            target_id=target_id,
        )

        # Check authorization
        if not policy_engine.is_allowed(ctx):
            # Create a denial message
            denial_msg = ToolMessage(
                content=json.dumps(
                    {
                        "error": "Access Denied",
                        "message": "You don't have permission to access this information. You can only view your own data or data for your direct reports.",
                    }
                ),
                tool_call_id=tool_call["id"],
            )
            return {"messages": [denial_msg]}

    return {}


def tool_node(state: AgentState) -> dict:
    """Execute tool calls."""
    messages = state["messages"]
    last_message = messages[-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}

    tool_messages = []
    tools_called = list(state.get("tools_called", []))

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        # Track tool call
        if tool_name not in tools_called:
            tools_called.append(tool_name)

        # Get the tool function
        tool_func = TOOL_MAP.get(tool_name)

        if tool_func is None:
            result = {"error": f"Unknown tool: {tool_name}"}
        else:
            try:
                # Invoke the tool
                result = tool_func.invoke(tool_args)
            except Exception as e:
                result = {"error": str(e)}

        # Create tool message
        tool_messages.append(
            ToolMessage(
                content=json.dumps(result, default=str),
                tool_call_id=tool_call["id"],
            )
        )

    return {
        "messages": tool_messages,
        "tools_called": tools_called,
    }


# ============================================================================
# ROUTING FUNCTIONS
# ============================================================================


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Determine if we should continue to tools or end."""
    messages = state["messages"]
    last_message = messages[-1]

    # If there are tool calls, continue to tools
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # Otherwise, end
    return "end"


def after_tools(state: AgentState) -> Literal["agent", "end"]:
    """Determine next step after tool execution."""
    messages = state["messages"]

    # Check if the last message is a tool result
    if messages and isinstance(messages[-1], ToolMessage):
        # Continue to agent to process the result
        return "agent"

    return "end"


def check_auth_result(state: AgentState) -> Literal["execute", "agent"]:
    """Check authorization result."""
    messages = state["messages"]
    if not messages:
        return "execute"

    last_message = messages[-1]

    # If the last message is a ToolMessage with an error, go back to agent
    if isinstance(last_message, ToolMessage):
        try:
            content = json.loads(last_message.content)
            if content.get("error") == "Access Denied":
                return "agent"
        except (json.JSONDecodeError, TypeError):
            pass

    return "execute"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================


def create_hr_agent_graph() -> StateGraph:
    """Create the HR Agent LangGraph workflow."""

    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("check_auth", check_authorization)
    workflow.add_node("tools", tool_node)

    # Set entry point
    workflow.set_entry_point("agent")

    # Add edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "check_auth",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "check_auth",
        check_auth_result,
        {
            "execute": "tools",
            "agent": "agent",  # Go back to agent if auth denied
        },
    )

    workflow.add_conditional_edges(
        "tools",
        after_tools,
        {
            "agent": "agent",
            "end": END,
        },
    )

    return workflow


def compile_hr_agent(checkpointer=None):
    """Compile the HR Agent graph."""
    workflow = create_hr_agent_graph()

    if checkpointer is not None:
        return workflow.compile(checkpointer=checkpointer)

    return workflow.compile()


# ============================================================================
# HR AGENT CLASS (Wrapper for compatibility)
# ============================================================================


class HRAgentLangGraph:
    """
    LangGraph-based HR Agent.

    Drop-in replacement for the original HRAgent class.
    """

    def __init__(
        self,
        user_email: str,
        session_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ):
        self.user_email = user_email
        self.session_id = (
            session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        self._trace_metadata = trace_metadata or {}

        # Get user context
        self.requester_context = self._get_requester_context(user_email)

        # Compile the graph (no checkpointer -- we manage history ourselves)
        self.graph = compile_hr_agent()

        # Conversation history for multi-turn support
        self._message_history: list[BaseMessage] = []

        # Track tools called (for eval compatibility)
        self._tools_called: list[str] = []

    def _get_requester_context(self, user_email: str) -> dict:
        """Get the requester's context including role and permissions."""
        return get_employee_service().get_requester_context(user_email)

    def load_history_from_turns(self, turns: Sequence[dict[str, Any]]) -> None:
        """Hydrate in-memory message history from stored session turns."""
        hydrated_history: list[BaseMessage] = []
        for turn in turns:
            query = str(turn.get("query", "")).strip()
            response = str(turn.get("response", "")).strip()
            if query:
                hydrated_history.append(HumanMessage(content=query))
            if response:
                hydrated_history.append(AIMessage(content=response))
        self._message_history = hydrated_history

    def chat(self, query: str) -> str:
        """Process a user query and return the response."""
        self._message_history.append(HumanMessage(content=query))

        initial_state: AgentState = {
            "messages": list(self._message_history),
            "user_email": self.user_email,
            "user_id": self.requester_context.get("employee_id", 0),
            "user_role": self.requester_context.get("role", "employee"),
            "tools_called": [],
            "current_date": datetime.now().strftime("%Y-%m-%d"),
        }

        config = {
            "configurable": {"thread_id": self.session_id},
            "metadata": {
                "user_email": self.user_email,
                "user_id": self.requester_context.get("employee_id"),
                "user_role": self.requester_context.get("role"),
                "session_id": self.session_id,
            },
            "tags": ["hr-agent", "langgraph"],
        }

        callbacks = []
        langfuse_handler = get_langfuse_handler()
        if langfuse_handler:
            langfuse_handler.session_id = self.session_id
            langfuse_handler.user_id = self.user_email
            metadata = {
                "user_role": self.requester_context.get("role"),
                "user_id": self.requester_context.get("employee_id"),
            }
            if self._trace_metadata:
                metadata.update(self._trace_metadata)
            langfuse_handler.metadata = metadata
            callbacks.append(langfuse_handler)

        if callbacks:
            config["callbacks"] = callbacks

        try:
            result = self.graph.invoke(initial_state, config)

            # Track tools called
            self._tools_called = result.get("tools_called", [])

            # Get the final response
            messages = result.get("messages", [])

            # Find the last AI message and add it to history
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content:
                    self._message_history.append(msg)
                    return msg.content if isinstance(msg.content, str) else str(msg.content)

            return "I'm sorry, I couldn't process your request."

        except Exception as e:
            logger.error("Agent chat error", error=str(e))
            return f"An error occurred: {str(e)}"

    def chat_stream(self, user_input: str):
        """Stream the agent response for better UX.

        Yields chunks of the response as they become available.
        """
        self._message_history.append(HumanMessage(content=user_input))

        initial_state: AgentState = {
            "messages": list(self._message_history),
            "user_email": self.user_email,
            "user_id": self.requester_context.get("employee_id", 0),
            "user_role": self.requester_context.get("role", "employee"),
            "tools_called": [],
            "current_date": datetime.now().strftime("%Y-%m-%d"),
        }

        config = {
            "configurable": {"thread_id": self.session_id},
            "metadata": {
                "user_email": self.user_email,
                "user_id": self.requester_context.get("employee_id"),
                "user_role": self.requester_context.get("role"),
                "session_id": self.session_id,
            },
            "tags": ["hr-agent", "langgraph"],
        }

        callbacks = []
        langfuse_handler = get_langfuse_handler()
        if langfuse_handler:
            langfuse_handler.session_id = self.session_id
            langfuse_handler.user_id = self.user_email
            metadata = {
                "user_role": self.requester_context.get("role"),
                "user_id": self.requester_context.get("employee_id"),
            }
            if self._trace_metadata:
                metadata.update(self._trace_metadata)
            langfuse_handler.metadata = metadata
            callbacks.append(langfuse_handler)

        if callbacks:
            config["callbacks"] = callbacks

        try:
            # Stream events from the graph
            for event in self.graph.stream(
                initial_state, config, stream_mode="messages"
            ):
                if isinstance(event, tuple) and len(event) == 2:
                    msg, metadata = event
                    if isinstance(msg, AIMessage) and msg.content:
                        # Yield content chunks
                        if isinstance(msg.content, str):
                            yield msg.content
        except Exception as e:
            logger.error("Agent stream error", error=str(e))
            yield f"An error occurred: {str(e)}"

    @property
    def tools_called(self) -> list[str]:
        """Get the list of tools called in the last interaction."""
        return self._tools_called

    # Compatibility property for evals
    class _SessionCompat:
        def __init__(self, agent: "HRAgentLangGraph"):
            self._agent = agent
            self.turns: list[dict[str, Any]] = []

        def get_context(self, key: str):
            if key == "tools_called":
                return self._agent._tools_called
            return None

        def update_context(self, key: str, value: Any):
            pass

    @property
    def session(self):
        """Compatibility property for evals."""
        return self._SessionCompat(self)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def run_hr_agent(
    user_email: str,
    question: str,
    session_id: str | None = None,
    prior_turns: Sequence[dict[str, Any]] | None = None,
) -> str:
    """Run the HR agent with a single query.

    Args:
        user_email: The email of the user making the request
        question: The question to ask
        session_id: Session identifier for multi-turn continuity
        prior_turns: Previously stored turns for the session

    Returns:
        The agent's response
    """
    agent = HRAgentLangGraph(user_email, session_id=session_id)
    if prior_turns:
        agent.load_history_from_turns(prior_turns)
    return agent.chat(question)


# ============================================================================
# VISUALIZATION
# ============================================================================


def visualize_graph():
    """Generate a visualization of the agent graph."""
    workflow = create_hr_agent_graph()

    try:
        # Try to generate a PNG visualization
        png_data = workflow.compile().get_graph().draw_mermaid_png()

        # Save to file
        with open("hr_agent_graph.png", "wb") as f:
            f.write(png_data)
        logger.info("Graph visualization saved to hr_agent_graph.png")

    except Exception:
        # Fall back to Mermaid text representation
        logger.info(
            "Mermaid diagram:\n" + workflow.compile().get_graph().draw_mermaid()
        )
