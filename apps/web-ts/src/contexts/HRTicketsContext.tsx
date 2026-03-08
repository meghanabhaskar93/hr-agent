import { createContext, useContext, useState, ReactNode } from "react";
import type { EscalatedRequest } from "@/components/MyRequestsPanel";

type Priority = "critical" | "high" | "medium";
type TicketStatus = "pending" | "assigned" | "in_progress" | "in_review" | "resolved";

export type ResolutionTag = "needs_info" | "ready" | "in_progress" | "escalated" | "resolved";

export const resolutionTagConfig: Record<ResolutionTag, { label: string; className: string }> = {
  needs_info: { label: "Needs Info", className: "border-warning/30 text-warning bg-warning/5" },
  ready: { label: "Ready", className: "border-info/30 text-info bg-info/5" },
  in_progress: { label: "In Progress", className: "border-primary/30 text-primary bg-primary/5" },
  escalated: { label: "Escalated", className: "border-destructive/30 text-destructive bg-destructive/5" },
  resolved: { label: "Resolved", className: "border-success/30 text-success bg-success/5" },
};

export interface HRTicket {
  id: string;
  employee: string;
  question: string;
  aiDraft: string;
  status: TicketStatus;
  priority: Priority;
  category: string;
  timestamp: Date;
  assignedTo?: string;
  timeToResolve?: number;
  resolutionNote?: string;
  resolutionTag?: ResolutionTag;
  inReviewSince?: Date;
  slaHours: number;
}

const initialTickets: HRTicket[] = [
  {
    id: "1",
    employee: "Jordan Lee",
    question: "Can I take unpaid leave for 3 months to care for a family member abroad?",
    aiDraft: "Hi Jordan,\n\nUnder our Extended Leave Policy, you have a few options:\n\n1. **FMLA Leave** — up to 12 weeks protected leave\n2. **Personal Leave** — up to 6 months with VP approval\n3. **Remote Work** — possible depending on role\n\nBest,\nHR Team",
    status: "pending",
    priority: "critical",
    category: "Leave & Time Off",
    timestamp: new Date(Date.now() - 2 * 3600000),
    slaHours: 48,
  },
  {
    id: "2",
    employee: "Sam Patel",
    question: "Stock options vesting schedule differs from offer letter",
    aiDraft: "Hi Sam,\n\nThank you for flagging this. I've created a ticket for Equity Administration to review your vesting schedule.\n\nExpected response: 2–3 business days.\n\nBest,\nHR Team",
    status: "pending",
    priority: "high",
    category: "Compensation",
    timestamp: new Date(Date.now() - 5 * 3600000),
    slaHours: 48,
  },
  {
    id: "3",
    employee: "Alex Kim",
    question: "Internal transfer process to another team — what are the steps?",
    aiDraft: "Hi Alex,\n\n1. Express interest to current manager\n2. Apply via Internal Job Board\n3. Interview with receiving team\n4. Both managers approve\n5. HR facilitates transition\n\nBest,\nHR Team",
    status: "pending",
    priority: "medium",
    category: "Career Development",
    timestamp: new Date(Date.now() - 86400000),
    slaHours: 48,
  },
  {
    id: "4",
    employee: "Morgan Chen",
    question: "Tuition reimbursement for part-time MBA program — am I eligible?",
    aiDraft: "Hi Morgan,\n\nYes! Up to $10,000/year for approved programs. Requirements: accredited institution, 1 year employment, B average.\n\nBest,\nHR Team",
    status: "pending",
    priority: "medium",
    category: "Benefits",
    timestamp: new Date(Date.now() - 2 * 86400000),
    slaHours: 48,
  },
  {
    id: "5",
    employee: "Riley Park",
    question: "When is the next pay day and how do I update my bank details?",
    aiDraft: "Hi Riley,\n\nNext pay date: March 15, 2026 (bi-weekly cycle).\n\nTo update bank details: HR Portal → My Profile → Payment Info.\n\nBest,\nHR Team",
    status: "pending",
    priority: "medium",
    category: "Payroll & Pay",
    timestamp: new Date(Date.now() - 3 * 86400000),
    slaHours: 48,
  },
];

interface HRTicketsContextType {
  tickets: HRTicket[];
  assignTicketToMe: (id: string, displayName: string) => void;
  updateTicketStatus: (id: string, status: TicketStatus) => void;
  addResolutionNote: (id: string, note: string, tag?: ResolutionTag) => void;
  getTicketById: (id: string) => HRTicket | undefined;
  getAssignedTickets: (displayName: string) => HRTicket[];
  getAssignedRequests: (displayName: string) => EscalatedRequest[];
}

const HRTicketsContext = createContext<HRTicketsContextType | null>(null);

export function useHRTickets() {
  const ctx = useContext(HRTicketsContext);
  if (!ctx) throw new Error("useHRTickets must be used within HRTicketsProvider");
  return ctx;
}

export function HRTicketsProvider({ children }: { children: ReactNode }) {
  const [tickets, setTickets] = useState<HRTicket[]>(initialTickets);

  const assignTicketToMe = (id: string, displayName: string) => {
    setTickets((prev) =>
      prev.map((t) =>
        t.id === id ? { ...t, status: "assigned" as TicketStatus, assignedTo: displayName } : t
      )
    );
  };

  const updateTicketStatus = (id: string, status: TicketStatus) => {
    setTickets((prev) =>
      prev.map((t) =>
        t.id === id
          ? {
              ...t,
              status,
              inReviewSince: status === "in_review" ? new Date() : t.inReviewSince,
              timeToResolve: status === "resolved" ? Math.floor(Math.random() * 60 + 15) : t.timeToResolve,
            }
          : t
      )
    );
  };

  const addResolutionNote = (id: string, note: string, tag?: ResolutionTag) => {
    setTickets((prev) =>
      prev.map((t) =>
        t.id === id ? { ...t, resolutionNote: note, resolutionTag: tag } : t
      )
    );
  };

  const getTicketById = (id: string) => tickets.find((t) => t.id === id);

  const getAssignedTickets = (displayName: string) => {
    const normalizedName = displayName.trim().toLowerCase();
    return tickets.filter((t) => t.assignedTo?.trim().toLowerCase() === normalizedName);
  };

  const getAssignedRequests = (displayName: string): EscalatedRequest[] =>
    getAssignedTickets(displayName).map((t) => ({
      id: t.id,
      summary: t.question.length > 50 ? t.question.slice(0, 50) + "..." : t.question,
      fullSummary: `${t.employee} asked: "${t.question}". AI drafted a response pending your review.`,
      aiResponse: t.aiDraft,
      status: t.status === "resolved" ? "resolved" : t.status === "in_review" ? "in_review" : t.status === "in_progress" ? "in_progress" : t.status === "assigned" ? "assigned" : "pending",
      priority: t.priority,
      category: t.category,
      timestamp: t.timestamp,
      resolutionTag: t.resolutionTag,
      auditLog: [
        { label: `Assigned to ${displayName}`, timestamp: new Date() },
        { label: "Escalated by employee", timestamp: t.timestamp },
      ],
    }));

  return (
    <HRTicketsContext.Provider value={{ tickets, assignTicketToMe, updateTicketStatus, addResolutionNote, getTicketById, getAssignedTickets, getAssignedRequests }}>
      {children}
    </HRTicketsContext.Provider>
  );
}
