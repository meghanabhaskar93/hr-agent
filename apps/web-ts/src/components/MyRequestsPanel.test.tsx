import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import MyRequestsPanel, { type EscalatedRequest } from "@/components/MyRequestsPanel";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    role: "employee",
  }),
}));

function makeRequest(
  id: string,
  summary: string,
  status: EscalatedRequest["status"]
): EscalatedRequest {
  return {
    id,
    summary,
    fullSummary: `${summary} full`,
    aiResponse: "AI response",
    status,
    priority: "medium",
    category: "General",
    timestamp: new Date("2026-03-13T10:00:00Z"),
    auditLog: [{ label: "Created", timestamp: new Date("2026-03-13T10:00:00Z") }],
  };
}

describe("MyRequestsPanel status filters", () => {
  it("shows assigned and in_progress requests in Active", () => {
    const requests: EscalatedRequest[] = [
      makeRequest("1", "Pending ticket", "pending"),
      makeRequest("2", "Assigned ticket", "assigned"),
      makeRequest("3", "In progress ticket", "in_progress"),
      makeRequest("4", "In review ticket", "in_review"),
      makeRequest("5", "Resolved ticket", "resolved"),
    ];

    render(
      <MemoryRouter>
        <MyRequestsPanel isOpen onClose={() => {}} requests={requests} />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "Active" }));

    expect(screen.getByText("Assigned ticket")).toBeInTheDocument();
    expect(screen.getByText("In progress ticket")).toBeInTheDocument();
    expect(screen.queryByText("Pending ticket")).not.toBeInTheDocument();
    expect(screen.queryByText("In review ticket")).not.toBeInTheDocument();
    expect(screen.queryByText("Resolved ticket")).not.toBeInTheDocument();
  });

  it("keeps other tabs scoped to their status", () => {
    const requests: EscalatedRequest[] = [
      makeRequest("1", "Pending ticket", "pending"),
      makeRequest("2", "Assigned ticket", "assigned"),
      makeRequest("3", "In progress ticket", "in_progress"),
      makeRequest("4", "In review ticket", "in_review"),
      makeRequest("5", "Resolved ticket", "resolved"),
    ];

    render(
      <MemoryRouter>
        <MyRequestsPanel isOpen onClose={() => {}} requests={requests} />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "Pending" }));
    expect(screen.getByText("Pending ticket")).toBeInTheDocument();
    expect(screen.queryByText("Assigned ticket")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "In Review" }));
    expect(screen.getByText("In review ticket")).toBeInTheDocument();
    expect(screen.queryByText("In progress ticket")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Resolved" }));
    expect(screen.getByText("Resolved ticket")).toBeInTheDocument();
    expect(screen.queryByText("Pending ticket")).not.toBeInTheDocument();
  });

  it("notifies when a request is viewed by expanding it", () => {
    const requests: EscalatedRequest[] = [makeRequest("9", "Resolved ticket", "resolved")];
    const onRequestViewed = vi.fn();

    render(
      <MemoryRouter>
        <MyRequestsPanel
          isOpen
          onClose={() => {}}
          requests={requests}
          onRequestViewed={onRequestViewed}
        />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "Expand request 9" }));

    expect(onRequestViewed).toHaveBeenCalledTimes(1);
    expect(onRequestViewed).toHaveBeenCalledWith(
      expect.objectContaining({ id: "9", status: "resolved" })
    );
  });
});
