import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HROps from "@/pages/HROps";

const { toast, backend, authState } = vi.hoisted(() => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
  backend: {
    assignHRRequest: vi.fn(),
    changeHRRequestPriority: vi.fn(),
    escalateHRRequest: vi.fn(),
    fetchHRRequestDetail: vi.fn(),
    fetchHRRequests: vi.fn(),
    fetchSessions: vi.fn(),
    messageHRRequestRequester: vi.fn(),
    transitionHRRequestStatus: vi.fn(),
  },
  authState: {
    user: { email: "mina.patel@acme.com" },
    session: { user: { email: "mina.patel@acme.com" } },
    role: "hr" as const,
  },
}));

vi.mock("sonner", () => ({ toast }));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => authState,
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

function makeRequest(overrides: Record<string, unknown> = {}) {
  return {
    request_id: 101,
    tenant_id: "default",
    requester_user_id: "alex.kim@acme.com",
    requester_role: "EMPLOYEE",
    subject_employee_id: null,
    requester_name: "Alex Kim",
    requester_department: "Engineering",
    requester_title: "Engineer",
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
    created_at: "2026-03-21T08:00:00Z",
    updated_at: "2026-03-21T09:00:00Z",
    last_action_at: "2026-03-21T09:00:00Z",
    resolution_text: null,
    resolution_sources: [],
    escalation_ticket_id: null,
    last_message_to_requester: null,
    last_message_at: null,
    ...overrides,
  };
}

describe("HROps page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    backend.fetchHRRequests.mockResolvedValue([
      makeRequest(),
      makeRequest({
        request_id: 102,
        priority: "P0",
        status: "IN_PROGRESS",
        assignee_user_id: null,
        assignee_name: null,
        summary: "Urgent benefits correction",
      }),
    ]);
    backend.fetchSessions.mockResolvedValue([
      {
        session_id: "session-1",
        user_email: authState.user.email,
        created_at: "2026-03-21T07:00:00Z",
        turn_count: 1,
        has_pending_confirmation: false,
        title: "HR follow-up",
      },
    ]);
    backend.fetchHRRequestDetail.mockResolvedValue({
      request: makeRequest({
        request_id: 101,
        assignee_user_id: authState.user.email,
        assignee_name: "Mina Patel",
      }),
      timeline: [],
      missing_fields: [],
      completeness_percent: 100,
    });
    backend.assignHRRequest.mockResolvedValue({ success: true });
    backend.changeHRRequestPriority.mockResolvedValue({ success: true });
    backend.escalateHRRequest.mockResolvedValue({ success: true });
    backend.messageHRRequestRequester.mockResolvedValue({ success: true });
    backend.transitionHRRequestStatus.mockResolvedValue({ success: true });
  });

  it("boots the queue and filters rows by priority", async () => {
    render(
      <MemoryRouter>
        <HROps />
      </MemoryRouter>
    );

    expect(await screen.findByText("HR Request Queue")).toBeInTheDocument();
    expect(screen.getByTestId("hr-sidebar")).toHaveTextContent("assigned:0");
    await waitFor(() =>
      expect(screen.queryByText("Loading queue...")).not.toBeInTheDocument()
    );
    expect(screen.getByText("Queue (2)")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show Filters" }));
    fireEvent.click(screen.getByLabelText("Filter by priority"));
    const listbox = await screen.findByRole("listbox");
    fireEvent.click(within(listbox).getByText("P0"));

    await waitFor(() => expect(screen.getByText("1 active filter")).toBeInTheDocument());
    expect(screen.getByText("Queue (1)")).toBeInTheDocument();
    expect(screen.getByText("Urgent benefits correction")).toBeInTheDocument();
    expect(screen.queryByText("Need payroll correction")).not.toBeInTheDocument();
  });

  it("assigns a request to the current user from the queue", async () => {
    render(
      <MemoryRouter>
        <HROps />
      </MemoryRouter>
    );

    expect(await screen.findByText("Need payroll correction")).toBeInTheDocument();

    const requestRow = screen.getByText("Need payroll correction").closest("tr");
    expect(requestRow).not.toBeNull();
    fireEvent.click(within(requestRow as HTMLTableRowElement).getByRole("button", { name: "Assign to me" }));

    await waitFor(() =>
      expect(backend.assignHRRequest).toHaveBeenCalledWith(
        "mina.patel@acme.com",
        101,
        "mina.patel@acme.com"
      )
    );
    expect(backend.fetchHRRequestDetail).toHaveBeenCalledWith("mina.patel@acme.com", 101);
    expect(await screen.findByRole("button", { name: "Unassign" })).toBeInTheDocument();
    expect(toast.success).toHaveBeenCalledWith("Assigned to you");
  });
});
