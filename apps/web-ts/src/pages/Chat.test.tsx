import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatPage from "@/pages/Chat";

const { toast, backend } = vi.hoisted(() => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
  backend: {
    createHRRequest: vi.fn(),
    createSession: vi.fn(),
    deleteSession: vi.fn(),
    fetchHRRequests: vi.fn(),
    fetchSessionTurns: vi.fn(),
    fetchSessions: vi.fn(),
    replyToHRRequestAsRequester: vi.fn(),
    sendChat: vi.fn(),
  },
}));

const authState = {
  user: { email: "alex.kim@acme.com" },
  session: { user: { email: "alex.kim@acme.com" } },
};

vi.mock("sonner", () => ({ toast }));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => authState,
}));

vi.mock("@/lib/backend", () => backend);

vi.mock("@/components/ConversationSidebar", () => ({
  default: ({
    conversations,
    onSelectConversation,
  }: {
    conversations: Array<{ id: string; preview: string }>;
    onSelectConversation: (id: string) => void;
  }) => (
    <div>
      <div data-testid="conversation-count">{conversations.length}</div>
      {conversations.map((conversation) => (
        <button
          key={conversation.id}
          onClick={() => onSelectConversation(conversation.id)}
        >
          {conversation.preview}
        </button>
      ))}
    </div>
  ),
}));

vi.mock("@/components/MyRequestsPanel", () => ({
  default: ({ requests, isOpen }: { requests: Array<{ summary: string }>; isOpen: boolean }) => (
    <div data-testid="requests-panel">
      {isOpen ? "open" : "closed"}:{requests.length}
    </div>
  ),
}));

vi.mock("@/components/ChatMessageBubble", () => ({
  default: ({ msg }: { msg: { content: string; role: string } }) => (
    <div>{`${msg.role}: ${msg.content}`}</div>
  ),
}));

vi.mock("@/components/CategoryCards", () => ({
  default: ({ onSelectCategory }: { onSelectCategory: (value: string) => void }) => (
    <button onClick={() => onSelectCategory("Need payroll help")}>Quick category</button>
  ),
}));

describe("ChatPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    backend.fetchSessions.mockResolvedValue([]);
    backend.fetchHRRequests.mockResolvedValue([]);
    backend.createSession.mockResolvedValue({
      session_id: "session-123",
      created_at: "2026-03-21T12:00:00Z",
    });
    backend.sendChat.mockResolvedValue({
      response: "Here is your answer",
      session_id: "session-123",
      timestamp: "2026-03-21T12:00:02Z",
    });
    backend.fetchSessionTurns.mockResolvedValue([]);
    backend.deleteSession.mockResolvedValue({ message: "deleted" });
    backend.createHRRequest.mockResolvedValue({ success: true, request_id: 17 });
    backend.replyToHRRequestAsRequester.mockResolvedValue({ success: true });
  });

  it("loads existing sessions and escalated requests on mount", async () => {
    backend.fetchSessions.mockResolvedValue([
      {
        session_id: "session-a",
        user_email: authState.user.email,
        created_at: "2026-03-21T10:00:00Z",
        turn_count: 2,
        has_pending_confirmation: false,
        title: "Payroll follow-up",
      },
    ]);
    backend.fetchHRRequests.mockResolvedValue([
      {
        request_id: 5,
        tenant_id: "default",
        requester_user_id: authState.user.email,
        requester_role: "EMPLOYEE",
        requester_name: "Alex Kim",
        requester_department: "Engineering",
        requester_title: "Engineer",
        subject_employee_id: null,
        subject_employee_name: null,
        type: "ESCALATION",
        subtype: "PAYROLL",
        summary: "Need payroll correction",
        description: "March net pay mismatch",
        priority: "P1",
        risk_level: "MED",
        sla_due_at: null,
        status: "NEW",
        assignee_user_id: null,
        assignee_name: null,
        required_fields: [],
        captured_fields: {},
        missing_fields: [],
        created_at: "2026-03-21T10:00:00Z",
        updated_at: "2026-03-21T11:00:00Z",
        last_action_at: "2026-03-21T11:00:00Z",
        resolution_text: null,
        resolution_sources: [],
        escalation_ticket_id: null,
        last_message_to_requester: null,
        last_message_at: null,
      },
    ]);

    render(<ChatPage />);

    expect(await screen.findByText("Payroll follow-up")).toBeInTheDocument();
    await waitFor(() =>
      expect(backend.fetchSessions).toHaveBeenCalledWith("alex.kim@acme.com")
    );
    expect(backend.fetchHRRequests).toHaveBeenCalledWith("alex.kim@acme.com");
    expect(screen.getByRole("button", { name: /My Requests/i })).toHaveTextContent("1");
  });

  it("creates a session and sends a message successfully", async () => {
    render(<ChatPage />);

    const input = screen.getByPlaceholderText(
      "Ask anything about HR, leave, payroll, benefits..."
    );

    fireEvent.change(input, { target: { value: "What is my PTO balance?" } });
    fireEvent.submit(input.closest("form")!);

    expect(await screen.findByText("user: What is my PTO balance?")).toBeInTheDocument();
    expect(await screen.findByText("assistant: Here is your answer")).toBeInTheDocument();

    expect(backend.createSession).toHaveBeenCalledWith("alex.kim@acme.com");
    expect(backend.sendChat).toHaveBeenCalledWith(
      "alex.kim@acme.com",
      "What is my PTO balance?",
      "session-123"
    );
    expect(screen.getByText("What is my PTO balance?")).toBeInTheDocument();
  });

  it("shows an in-chat error message when sendChat fails", async () => {
    backend.sendChat.mockRejectedValue(new Error("Backend unavailable"));

    render(<ChatPage />);

    const input = screen.getByPlaceholderText(
      "Ask anything about HR, leave, payroll, benefits..."
    );

    fireEvent.change(input, { target: { value: "Help with payroll" } });
    fireEvent.submit(input.closest("form")!);

    expect(await screen.findByText("user: Help with payroll")).toBeInTheDocument();
    expect(
      await screen.findByText("assistant: Sorry, I hit an error: Backend unavailable")
    ).toBeInTheDocument();
    expect(toast.error).toHaveBeenCalledWith("Backend unavailable");
  });
});
