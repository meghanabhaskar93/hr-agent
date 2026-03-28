import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HRChat from "@/pages/HRChat";

const { toast, backend, authState, ticketState } = vi.hoisted(() => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
  backend: {
    createHRRequest: vi.fn(),
    createSession: vi.fn(),
    deleteSession: vi.fn(),
    fetchHRRequestDetail: vi.fn(),
    fetchHRRequests: vi.fn(),
    fetchSessions: vi.fn(),
    fetchSessionTurns: vi.fn(),
    sendChat: vi.fn(),
  },
  authState: {
    user: { email: "mina.patel@acme.com" },
    session: { user: { email: "mina.patel@acme.com" } },
    role: "hr" as const,
  },
  ticketState: {
    ticket: {
      id: "42",
      employee: "Jordan Lee",
      question: "Can I take unpaid leave for 3 months to care for a family member abroad?",
      aiDraft:
        "Hi Jordan,\n\nUnder our Extended Leave Policy, you have a few options:\n\n1. FMLA Leave\n2. Personal Leave\n3. Remote Work\n\nBest,\nHR Team",
      status: "pending" as const,
      priority: "critical" as const,
      category: "Leave & Time Off",
      timestamp: new Date("2026-03-21T09:00:00Z"),
      assignedTo: "mina.patel",
      slaHours: 48,
    },
  },
}));

vi.mock("sonner", () => ({ toast }));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => authState,
}));

vi.mock("@/contexts/HRTicketsContext", () => ({
  useHRTickets: () => ({
    getAssignedTickets: () => [ticketState.ticket],
    getAssignedRequests: () => [
      {
        id: ticketState.ticket.id,
        summary: "Need leave guidance",
        fullSummary: "Jordan asked for leave guidance.",
        aiResponse: ticketState.ticket.aiDraft,
        status: "pending",
        priority: "critical",
        category: ticketState.ticket.category,
        timestamp: ticketState.ticket.timestamp,
        auditLog: [{ label: "Assigned", timestamp: ticketState.ticket.timestamp }],
      },
    ],
    getTicketById: (id: string) => (id === ticketState.ticket.id ? ticketState.ticket : undefined),
    addResolutionNote: vi.fn(),
    updateTicketStatus: vi.fn(),
  }),
}));

vi.mock("@/lib/backend", () => backend);

vi.mock("@/components/HRConversationSidebar", () => ({
  default: ({ assignedCount }: { assignedCount: number }) => (
    <aside data-testid="hr-sidebar">assigned:{assignedCount}</aside>
  ),
}));

vi.mock("@/components/MyRequestsPanel", () => ({
  default: ({ isOpen }: { isOpen: boolean }) => (
    <div data-testid="my-requests-panel">{isOpen ? "open" : "closed"}</div>
  ),
}));

vi.mock("@/components/ChatMessageBubble", () => ({
  default: ({ msg }: { msg: { role: string; content: string } }) => (
    <div>{`${msg.role}: ${msg.content}`}</div>
  ),
}));

vi.mock("@/components/HRCategoryCards", () => ({
  default: ({ onSelectCategory }: { onSelectCategory: (value: string) => void }) => (
    <button onClick={() => onSelectCategory("Need leave help")}>HR quick category</button>
  ),
}));

vi.mock("@/components/TicketActionBar", () => ({
  default: () => <div data-testid="ticket-action-bar" />,
}));

describe("HRChat page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    backend.fetchSessions.mockResolvedValue([
      {
        session_id: "session-1",
        user_email: authState.user.email,
        created_at: "2026-03-21T08:00:00Z",
        turn_count: 1,
        has_pending_confirmation: false,
        title: "Leave follow-up",
      },
    ]);
    backend.fetchSessionTurns.mockResolvedValue([]);
    backend.fetchHRRequests.mockResolvedValue([
      {
        request_id: 42,
        tenant_id: "default",
        requester_user_id: "jordan.lee@acme.com",
        requester_role: "EMPLOYEE",
        requester_name: "Jordan Lee",
        requester_department: "Engineering",
        requester_title: "Engineer",
        type: "HR",
        subtype: "ESCALATION",
        summary: "Need leave guidance",
        description: "Jordan asked for leave guidance.",
        priority: "P1",
        risk_level: "MED",
        status: "NEW",
        assignee_user_id: "mina.patel@acme.com",
        assignee_name: "mina.patel",
        required_fields: [],
        captured_fields: {},
        missing_fields: [],
        created_at: "2026-03-21T09:00:00Z",
        updated_at: "2026-03-21T09:00:00Z",
        last_action_at: "2026-03-21T09:00:00Z",
        resolution_sources: [],
      },
    ]);
    backend.fetchHRRequestDetail.mockResolvedValue(null);
    backend.createSession.mockResolvedValue({
      session_id: "session-2",
      created_at: "2026-03-21T10:00:00Z",
    });
    backend.sendChat.mockResolvedValue({
      response: "Here is a grounded HR response",
      session_id: "session-2",
      timestamp: "2026-03-21T10:00:03Z",
    });
    backend.createHRRequest.mockResolvedValue({ success: true, request_id: 91 });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("boots from sessions, shows assigned tickets, and injects ticket context on deep link", async () => {
    render(
      <MemoryRouter initialEntries={["/hr-chat?ticket=42"]}>
        <HRChat />
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(backend.fetchSessions).toHaveBeenCalledWith("mina.patel@acme.com")
    );
    await waitFor(() =>
      expect(screen.getByTestId("hr-sidebar")).toHaveTextContent("assigned:1")
    );
    expect(
      screen.getByRole("button", { name: /My Assigned/i })
    ).toHaveTextContent("1");
    expect(
      screen.getByText("Working on: Jordan Lee's request")
    ).toBeInTheDocument();

    await new Promise((resolve) => setTimeout(resolve, 350));
    await waitFor(() => expect(backend.sendChat).toHaveBeenCalled());
    expect(backend.sendChat).toHaveBeenCalledWith(
      "mina.patel@acme.com",
      expect.stringContaining("Jordan Lee"),
      "ticket-42"
    );
    expect(backend.createSession).not.toHaveBeenCalled();
  });

  it("can send a new HR chat message from the draft composer", async () => {
    render(
      <MemoryRouter initialEntries={["/hr-chat"]}>
        <HRChat />
      </MemoryRouter>
    );

    const input = screen.getByPlaceholderText(
      "Look up employees, draft responses, check policies..."
    );
    fireEvent.change(input, { target: { value: "Need help with leave policy" } });
    fireEvent.submit(input.closest("form")!);

    expect(await screen.findByText("user: Need help with leave policy")).toBeInTheDocument();
    expect(
      await screen.findByText("assistant: Here is a grounded HR response")
    ).toBeInTheDocument();
    expect(backend.createSession).toHaveBeenCalledWith("mina.patel@acme.com");
    expect(backend.sendChat).toHaveBeenCalledWith(
      "mina.patel@acme.com",
      "Need help with leave policy",
      "session-2"
    );
  });
});
