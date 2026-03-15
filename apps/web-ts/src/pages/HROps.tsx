import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowUpDown,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  Filter,
  Mail,
  MessageSquare,
  ShieldAlert,
  UserPlus,
  UserX,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import HRConversationSidebar from "@/components/HRConversationSidebar";
import MyRequestsPanel, { type EscalatedRequest } from "@/components/MyRequestsPanel";
import type { Conversation } from "@/components/ConversationSidebar";
import { useAuth } from "@/contexts/AuthContext";
import {
  assignHRRequest,
  changeHRRequestPriority,
  escalateHRRequest,
  fetchHRRequestDetail,
  fetchHRRequests,
  fetchSessions,
  messageHRRequestRequester,
  transitionHRRequestStatus,
  type BackendHRRequest,
  type BackendHRRequestDetail,
} from "@/lib/backend";

type Priority = "P0" | "P1" | "P2";
type Status =
  | "NEW"
  | "NEEDS_INFO"
  | "READY"
  | "IN_PROGRESS"
  | "RESOLVED"
  | "ESCALATED"
  | "CANCELLED";
type SortableQueueColumn =
  | "priority"
  | "requester"
  | "summary"
  | "type"
  | "due"
  | "assignee"
  | "status";
type SortDirection = "asc" | "desc";
type QueueColumnSort = {
  column: SortableQueueColumn;
  direction: SortDirection;
};

export type HROpsQueueFilters = {
  priority: "all" | Priority;
  type: "all" | string;
  status: "all" | Status;
  dueSoon: "all" | "due_soon";
};

const DEFAULT_QUEUE_FILTERS: HROpsQueueFilters = {
  priority: "all",
  type: "all",
  status: "all",
  dueSoon: "all",
};

function countActiveQueueFilters(filters: HROpsQueueFilters): number {
  let count = 0;
  if (filters.priority !== "all") count += 1;
  if (filters.type !== "all") count += 1;
  if (filters.status !== "all") count += 1;
  if (filters.dueSoon !== "all") count += 1;
  return count;
}

const priorityConfig: Record<Priority, { label: string; className: string }> = {
  P0: {
    label: "P0",
    className: "bg-destructive/10 text-destructive border-destructive/20",
  },
  P1: {
    label: "P1",
    className: "bg-warning/10 text-warning border-warning/20",
  },
  P2: {
    label: "P2",
    className: "bg-muted text-muted-foreground border-border",
  },
};

const statusConfig: Record<Status, { label: string; icon: typeof Clock; color: string }> = {
  NEW: { label: "New", icon: AlertTriangle, color: "text-warning" },
  NEEDS_INFO: { label: "Needs Info", icon: MessageSquare, color: "text-amber-500" },
  READY: { label: "Ready", icon: Clock, color: "text-info" },
  IN_PROGRESS: { label: "In Progress", icon: Clock, color: "text-info" },
  ESCALATED: { label: "Escalated", icon: ShieldAlert, color: "text-destructive" },
  RESOLVED: { label: "Resolved", icon: CheckCircle2, color: "text-emerald-500" },
  CANCELLED: { label: "Cancelled", icon: XCircle, color: "text-muted-foreground" },
};

const DUE_SOON_HOURS = 24;

const priorityOrder: Record<Priority, number> = {
  P0: 0,
  P1: 1,
  P2: 2,
};

const riskOrder: Record<BackendHRRequest["risk_level"], number> = {
  HIGH: 0,
  MED: 1,
  LOW: 2,
};

const statusSortOrder: Record<Status, number> = {
  NEW: 0,
  READY: 1,
  NEEDS_INFO: 2,
  IN_PROGRESS: 3,
  ESCALATED: 4,
  RESOLVED: 5,
  CANCELLED: 6,
};

function mapPriority(p: string | null | undefined): Priority {
  if (p === "P0" || p === "P1" || p === "P2") return p;
  return "P2";
}

function toTypeLabel(item: BackendHRRequest): string {
  return `${item.type || "General"} / ${item.subtype || "General"}`;
}

function toTimestamp(iso?: string | null): number | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.getTime();
}

function isReadyLikeStatus(status: Status): boolean {
  return status === "READY" || status === "IN_PROGRESS";
}

function shouldKeepNeedsInfoAhead(
  needsInfoItem: BackendHRRequest,
  otherItem: BackendHRRequest
): boolean {
  if (mapPriority(needsInfoItem.priority) !== "P0") return false;
  const needsInfoSla = toTimestamp(needsInfoItem.sla_due_at);
  if (needsInfoSla === null) return false;
  const otherSla = toTimestamp(otherItem.sla_due_at);
  if (otherSla === null) return true;
  return needsInfoSla < otherSla;
}

export function compareHRQueueOrder(
  a: BackendHRRequest,
  b: BackendHRRequest
): number {
  const priorityDiff = priorityOrder[mapPriority(a.priority)] - priorityOrder[mapPriority(b.priority)];
  if (priorityDiff !== 0) return priorityDiff;

  const aSla = toTimestamp(a.sla_due_at) ?? Number.POSITIVE_INFINITY;
  const bSla = toTimestamp(b.sla_due_at) ?? Number.POSITIVE_INFINITY;
  if (aSla !== bSla) return aSla - bSla;

  const aRisk = riskOrder[a.risk_level] ?? riskOrder.LOW;
  const bRisk = riskOrder[b.risk_level] ?? riskOrder.LOW;
  if (aRisk !== bRisk) return aRisk - bRisk;

  const aIsNeedsInfo = a.status === "NEEDS_INFO";
  const bIsNeedsInfo = b.status === "NEEDS_INFO";
  const aIsReadyLike = isReadyLikeStatus(a.status);
  const bIsReadyLike = isReadyLikeStatus(b.status);

  if (aIsNeedsInfo && bIsReadyLike) {
    if (!shouldKeepNeedsInfoAhead(a, b)) return 1;
  } else if (bIsNeedsInfo && aIsReadyLike) {
    if (!shouldKeepNeedsInfoAhead(b, a)) return -1;
  }

  const aGroup = aIsReadyLike ? 0 : aIsNeedsInfo ? 1 : 2;
  const bGroup = bIsReadyLike ? 0 : bIsNeedsInfo ? 1 : 2;
  if (aGroup !== bGroup) return aGroup - bGroup;

  const aCreated = toTimestamp(a.created_at) ?? Number.POSITIVE_INFINITY;
  const bCreated = toTimestamp(b.created_at) ?? Number.POSITIVE_INFINITY;
  if (aCreated !== bCreated) return aCreated - bCreated;

  return a.request_id - b.request_id;
}

export function sortHRQueue(items: BackendHRRequest[]): BackendHRRequest[] {
  return [...items].sort(compareHRQueueOrder);
}

function applyQueueColumnSort(
  items: BackendHRRequest[],
  sort: QueueColumnSort | null
): BackendHRRequest[] {
  if (!sort) return sortHRQueue(items);

  const direction = sort.direction === "asc" ? 1 : -1;
  const compareText = (a: string, b: string) => a.localeCompare(b);

  return [...items].sort((a, b) => {
    let value = 0;

    if (sort.column === "priority") {
      value = priorityOrder[mapPriority(a.priority)] - priorityOrder[mapPriority(b.priority)];
    } else if (sort.column === "requester") {
      value = compareText(
        (a.requester_name || a.requester_user_id || "").toLowerCase(),
        (b.requester_name || b.requester_user_id || "").toLowerCase()
      );
    } else if (sort.column === "summary") {
      value = compareText(a.summary.toLowerCase(), b.summary.toLowerCase());
    } else if (sort.column === "type") {
      value = compareText(toTypeLabel(a).toLowerCase(), toTypeLabel(b).toLowerCase());
    } else if (sort.column === "due") {
      const aDue = toTimestamp(a.sla_due_at);
      const bDue = toTimestamp(b.sla_due_at);
      if (aDue === null && bDue === null) value = 0;
      else if (aDue === null) value = 1;
      else if (bDue === null) value = -1;
      else value = aDue - bDue;
    } else if (sort.column === "assignee") {
      value = compareText(
        (a.assignee_name || a.assignee_user_id || "Unassigned").toLowerCase(),
        (b.assignee_name || b.assignee_user_id || "Unassigned").toLowerCase()
      );
    } else if (sort.column === "status") {
      value = statusSortOrder[a.status] - statusSortOrder[b.status];
    }

    if (value !== 0) return value * direction;
    return compareHRQueueOrder(a, b);
  });
}

export function isBlockedNeedsInfo(item: BackendHRRequest): boolean {
  return item.status === "NEEDS_INFO" || (item.missing_fields?.length ?? 0) > 0;
}

export function isDueSoon(
  item: BackendHRRequest,
  now: Date = new Date(),
  windowHours: number = DUE_SOON_HOURS
): boolean {
  if (item.status === "RESOLVED" || item.status === "CANCELLED") return false;
  const dueAt = toTimestamp(item.sla_due_at);
  if (dueAt === null) return false;
  const nowTs = now.getTime();
  const maxTs = nowTs + windowHours * 60 * 60 * 1000;
  return dueAt >= nowTs && dueAt <= maxTs;
}

function toSessionPreview(session: {
  title?: string | null;
  turn_count: number;
  created_at: string;
}): string {
  if (session.title && session.title.trim()) return session.title;
  if (session.turn_count > 0) {
    return `Conversation ${new Date(session.created_at).toLocaleDateString()}`;
  }
  return "New conversation";
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString();
}

function hrRequestViewsStorageKey(userEmail: string): string {
  return `pinghr:hr-request-views:${userEmail.toLowerCase()}`;
}

function loadHRRequestViews(userEmail: string): Record<string, number> {
  try {
    const raw = localStorage.getItem(hrRequestViewsStorageKey(userEmail));
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    if (!parsed || typeof parsed !== "object") return {};
    const cleaned: Record<string, number> = {};
    for (const [requestId, value] of Object.entries(parsed)) {
      if (typeof value === "number" && Number.isFinite(value) && value > 0) {
        cleaned[requestId] = value;
      }
    }
    return cleaned;
  } catch {
    return {};
  }
}

function saveHRRequestViews(userEmail: string, viewsByRequestId: Record<string, number>): void {
  try {
    localStorage.setItem(
      hrRequestViewsStorageKey(userEmail),
      JSON.stringify(viewsByRequestId)
    );
  } catch {
    // Ignore storage errors and keep UI usable.
  }
}

function requestUpdateTimestampMs(request: EscalatedRequest): number {
  const timestamp = (request.lastUpdatedAt || request.timestamp).getTime();
  return Number.isFinite(timestamp) ? timestamp : 0;
}

export function toPanelRequestStatus(
  status: BackendHRRequest["status"],
  assigneeUserId?: string | null
): EscalatedRequest["status"] {
  if (status === "RESOLVED" || status === "CANCELLED") return "resolved";
  if (status === "NEEDS_INFO") return "in_review";
  if (status === "IN_PROGRESS" || status === "ESCALATED") return "in_progress";
  if (assigneeUserId) return "assigned";
  return "pending";
}

export function matchesHROpsQueueFilters(
  item: BackendHRRequest,
  filters: HROpsQueueFilters
): boolean {
  const priority = mapPriority(item.priority);
  if (filters.priority !== "all" && priority !== filters.priority) return false;

  if (filters.type !== "all" && toTypeLabel(item) !== filters.type) return false;

  if (filters.status !== "all" && item.status !== filters.status) return false;

  if (filters.dueSoon === "due_soon" && !isDueSoon(item)) return false;

  return true;
}

function toMyRequest(
  item: BackendHRRequest,
  detail: BackendHRRequestDetail | null
): EscalatedRequest {
  const status = toPanelRequestStatus(item.status, item.assignee_user_id);

  const panelPriority =
    item.priority === "P0" ? "critical" : item.priority === "P1" ? "high" : "medium";

  return {
    id: String(item.request_id),
    summary: item.summary.length > 60 ? `${item.summary.slice(0, 60)}...` : item.summary,
    fullSummary: `${item.requester_name || item.requester_user_id}: ${item.description}`,
    aiResponse:
      item.last_message_to_requester ||
      item.resolution_text ||
      "No latest update has been recorded yet.",
    status,
    priority: panelPriority,
    category: `${item.type} / ${item.subtype}`,
    timestamp: new Date(item.created_at),
    lastUpdatedAt: new Date(item.updated_at),
    auditLog:
      detail?.timeline?.map((event) => ({
        label: event.event_note || event.event_type.replace(/_/g, " "),
        timestamp: new Date(event.created_at),
      })) || [
        { label: "Request created", timestamp: new Date(item.created_at) },
        { label: "Last update", timestamp: new Date(item.updated_at) },
      ],
  };
}

export default function HROps() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [requestsOpen, setRequestsOpen] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [queueFilters, setQueueFilters] = useState<HROpsQueueFilters>(DEFAULT_QUEUE_FILTERS);
  const [queueSort, setQueueSort] = useState<QueueColumnSort | null>(null);
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<BackendHRRequest[]>([]);
  const [detailById, setDetailById] = useState<Record<number, BackendHRRequestDetail>>({});
  const [messageDraft, setMessageDraft] = useState<Record<number, string>>({});
  const [resolutionNotes, setResolutionNotes] = useState<Record<number, string>>({});
  const [viewedRequestById, setViewedRequestById] = useState<Record<string, number>>({});

  const currentUserEmail = user?.email?.toLowerCase() || "";

  const loadRequests = useCallback(async () => {
    if (!user?.email) return;
    const rows = await fetchHRRequests(user.email);
    setItems(rows);
  }, [user?.email]);

  const loadDetail = useCallback(
    async (requestId: number) => {
      if (!user?.email) return;
      const detail = await fetchHRRequestDetail(user.email, requestId);
      setDetailById((prev) => ({ ...prev, [requestId]: detail }));
    },
    [user?.email]
  );

  const syncRequest = useCallback(
    async (requestId: number) => {
      if (!user?.email) return;
      const detail = await fetchHRRequestDetail(user.email, requestId);
      setDetailById((prev) => ({ ...prev, [requestId]: detail }));
      setItems((prev) =>
        prev.map((item) => (item.request_id === requestId ? detail.request : item))
      );
    },
    [user?.email]
  );

  useEffect(() => {
    if (!user?.email) return;
    let cancelled = false;
    const bootstrap = async () => {
      setLoading(true);
      try {
        const rows = await fetchHRRequests(user.email);
        if (!cancelled) setItems(rows);
      } catch (error: any) {
        toast.error(error?.message || "Failed to load HR queue");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [user?.email]);

  useEffect(() => {
    if (!user?.email) {
      setViewedRequestById({});
      return;
    }
    setViewedRequestById(loadHRRequestViews(user.email));
  }, [user?.email]);

  useEffect(() => {
    if (!user?.email) return;
    let cancelled = false;

    const loadSessions = async () => {
      try {
        const sessions = await fetchSessions(user.email);
        if (cancelled) return;
        setConversations(
          sessions
            .map((session) => ({
              id: session.session_id,
              preview: toSessionPreview(session),
              timestamp: new Date(session.created_at),
            }))
            .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
        );
      } catch {
        // Keep dashboard usable if chat sessions fail to load.
      }
    };

    void loadSessions();
    return () => {
      cancelled = true;
    };
  }, [user?.email]);

  const handleExpand = async (requestId: number) => {
    const isExpanded = expandedId === requestId;
    setExpandedId(isExpanded ? null : requestId);
    if (isExpanded || detailById[requestId]) return;
    try {
      await loadDetail(requestId);
    } catch (error: any) {
      toast.error(error?.message || "Failed to load request detail");
    }
  };

  const runAction = async (
    requestId: number,
    action: () => Promise<unknown>,
    successMessage: string
  ) => {
    try {
      await action();
      toast.success(successMessage);
      try {
        await syncRequest(requestId);
      } catch {
        await loadRequests();
      }
    } catch (error: any) {
      toast.error(error?.message || "Action failed");
    }
  };

  const typeOptions = useMemo(
    () =>
      Array.from(new Set(items.map((item) => toTypeLabel(item)))).sort((a, b) =>
        a.localeCompare(b)
      ),
    [items]
  );

  const filtered = useMemo(
    () => items.filter((item) => matchesHROpsQueueFilters(item, queueFilters)),
    [items, queueFilters]
  );
  const activeFilterCount = useMemo(
    () => countActiveQueueFilters(queueFilters),
    [queueFilters]
  );

  const toggleQueueSort = useCallback((column: SortableQueueColumn) => {
    setQueueSort((prev) => {
      if (!prev || prev.column !== column) {
        return { column, direction: "asc" };
      }
      if (prev.direction === "asc") {
        return { column, direction: "desc" };
      }
      return null;
    });
  }, []);

  const renderSortIcon = useCallback(
    (column: SortableQueueColumn) => {
      if (!queueSort || queueSort.column !== column) {
        return (
          <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground/70 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
        );
      }
      return queueSort.direction === "asc" ? (
        <ChevronUp className="h-3.5 w-3.5 text-primary" />
      ) : (
        <ChevronDown className="h-3.5 w-3.5 text-primary" />
      );
    },
    [queueSort]
  );

  const ariaSortValue = useCallback(
    (column: SortableQueueColumn): "none" | "ascending" | "descending" => {
      if (!queueSort || queueSort.column !== column) return "none";
      return queueSort.direction === "asc" ? "ascending" : "descending";
    },
    [queueSort]
  );

  const assignedToMeAll = items.filter(
    (item) => (item.assignee_user_id || "").toLowerCase() === currentUserEmail
  );
  const queueRows = useMemo(() => applyQueueColumnSort(filtered, queueSort), [filtered, queueSort]);
  const pendingCount = filtered.filter(
    (item) => item.status === "NEW" || item.status === "READY" || item.status === "ESCALATED"
  ).length;
  const inProgressCount = filtered.filter((item) => item.status === "IN_PROGRESS").length;
  const inReviewCount = filtered.filter((item) => item.status === "NEEDS_INFO").length;

  const assignedRequests = sortHRQueue(assignedToMeAll).map((item) =>
    toMyRequest(item, detailById[item.request_id] || null)
  );
  const unreadAssignedRequestCount = assignedRequests.reduce((count, request) => {
    const viewedAt = viewedRequestById[request.id] ?? 0;
    return requestUpdateTimestampMs(request) > viewedAt ? count + 1 : count;
  }, 0);

  const handleRequestViewed = useCallback(
    (request: EscalatedRequest) => {
      const userEmail = user?.email;
      if (!userEmail) return;
      const viewedAt = requestUpdateTimestampMs(request);
      if (viewedAt <= 0) return;

      setViewedRequestById((prev) => {
        if ((prev[request.id] ?? 0) >= viewedAt) return prev;
        const next = { ...prev, [request.id]: viewedAt };
        saveHRRequestViews(userEmail, next);
        return next;
      });
    },
    [user?.email]
  );

  return (
    <div className="min-h-screen flex w-full">
      <HRConversationSidebar
        activeConversationId={activeConversation}
        conversations={conversations}
        onSelectConversation={(id) => {
          setActiveConversation(id);
          navigate("/hr-chat");
        }}
        onNewConversation={() => navigate("/hr-chat")}
        onDeleteConversation={(id) => {
          setConversations((prev) => prev.filter((c) => c.id !== id));
          if (activeConversation === id) setActiveConversation(null);
        }}
        onClearAll={() => {
          setConversations([]);
          setActiveConversation(null);
        }}
        assignedCount={assignedToMeAll.length}
      />

      <main className="flex-1 flex flex-col min-w-0 h-screen overflow-auto">
        <header className="flex items-center justify-between px-6 py-3 border-b bg-card">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-base text-primary">PingHR</span>
            <span className="text-muted-foreground text-sm">/ HR Ops Dashboard</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="gap-2 text-primary border-primary/30 hover:bg-primary/5"
            onClick={() => setRequestsOpen(true)}
          >
            <Mail className="h-4 w-4" />
            My Requests
            {unreadAssignedRequestCount > 0 && (
              <span className="ml-1 h-5 min-w-5 px-1 rounded-full bg-destructive text-destructive-foreground text-[10px] font-bold flex items-center justify-center">
                {unreadAssignedRequestCount}
              </span>
            )}
          </Button>
        </header>

        <div className="p-6 max-w-7xl mx-auto w-full">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold mb-1">HR Request Queue</h1>
              <p className="text-muted-foreground text-sm">
                {pendingCount} pending · {inProgressCount} in progress · {inReviewCount} in review
                {" · "}
                {filtered.length} total
              </p>
            </div>
          </div>

          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs text-muted-foreground">
              {activeFilterCount > 0
                ? `${activeFilterCount} active filter${activeFilterCount === 1 ? "" : "s"}`
                : "No active filters"}
            </div>
            <div className="flex items-center gap-2">
              {activeFilterCount > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setQueueFilters(DEFAULT_QUEUE_FILTERS)}
                >
                  Reset
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={() => setShowFilters((prev) => !prev)}
              >
                <Filter className="h-3.5 w-3.5" />
                {showFilters ? "Hide Filters" : "Show Filters"}
              </Button>
            </div>
          </div>

          {showFilters && (
            <div className="mb-6 rounded-xl border bg-card p-3">
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                <Select
                  value={queueFilters.priority}
                  onValueChange={(value) =>
                    setQueueFilters((prev) => ({
                      ...prev,
                      priority: value as HROpsQueueFilters["priority"],
                    }))
                  }
                >
                  <SelectTrigger className="h-9 text-sm" aria-label="Filter by priority">
                    <SelectValue placeholder="Priority" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All priorities</SelectItem>
                    <SelectItem value="P0">P0</SelectItem>
                    <SelectItem value="P1">P1</SelectItem>
                    <SelectItem value="P2">P2</SelectItem>
                  </SelectContent>
                </Select>

                <Select
                  value={queueFilters.type}
                  onValueChange={(value) =>
                    setQueueFilters((prev) => ({ ...prev, type: value }))
                  }
                >
                  <SelectTrigger className="h-9 text-sm" aria-label="Filter by type">
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All types</SelectItem>
                    {typeOptions.map((type) => (
                      <SelectItem key={type} value={type}>
                        {type}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select
                  value={queueFilters.status}
                  onValueChange={(value) =>
                    setQueueFilters((prev) => ({
                      ...prev,
                      status: value as HROpsQueueFilters["status"],
                    }))
                  }
                >
                  <SelectTrigger className="h-9 text-sm" aria-label="Filter by status">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All statuses</SelectItem>
                    <SelectItem value="NEW">New</SelectItem>
                    <SelectItem value="NEEDS_INFO">Needs Info</SelectItem>
                    <SelectItem value="READY">Ready</SelectItem>
                    <SelectItem value="IN_PROGRESS">In Progress</SelectItem>
                    <SelectItem value="ESCALATED">Escalated</SelectItem>
                    <SelectItem value="RESOLVED">Resolved</SelectItem>
                    <SelectItem value="CANCELLED">Cancelled</SelectItem>
                  </SelectContent>
                </Select>

                <Select
                  value={queueFilters.dueSoon}
                  onValueChange={(value) =>
                    setQueueFilters((prev) => ({
                      ...prev,
                      dueSoon: value as HROpsQueueFilters["dueSoon"],
                    }))
                  }
                >
                  <SelectTrigger className="h-9 text-sm" aria-label="Filter by due soon">
                    <SelectValue placeholder="Due soon" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All due windows</SelectItem>
                    <SelectItem value="due_soon">{`Due soon (${DUE_SOON_HOURS}h)`}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {loading ? (
            <div className="text-sm text-muted-foreground">Loading queue...</div>
          ) : (
            <div className="bg-card border rounded-xl shadow-soft overflow-hidden">
              <div className="px-4 py-3 border-b bg-muted/20 text-sm font-semibold">
                Queue ({queueRows.length})
              </div>
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/30">
                    <TableHead className="w-[110px]" aria-sort={ariaSortValue("priority")}>
                      <button
                        type="button"
                        className="group inline-flex items-center gap-1 rounded-sm px-0 py-0 text-sm font-semibold text-foreground/90 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        onClick={() => toggleQueueSort("priority")}
                      >
                        Priority {renderSortIcon("priority")}
                      </button>
                    </TableHead>
                    <TableHead aria-sort={ariaSortValue("requester")}>
                      <button
                        type="button"
                        className="group inline-flex items-center gap-1 rounded-sm px-0 py-0 text-sm font-semibold text-foreground/90 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        onClick={() => toggleQueueSort("requester")}
                      >
                        Requester {renderSortIcon("requester")}
                      </button>
                    </TableHead>
                    <TableHead className="max-w-[320px]" aria-sort={ariaSortValue("summary")}>
                      <button
                        type="button"
                        className="group inline-flex items-center gap-1 rounded-sm px-0 py-0 text-sm font-semibold text-foreground/90 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        onClick={() => toggleQueueSort("summary")}
                      >
                        Summary {renderSortIcon("summary")}
                      </button>
                    </TableHead>
                    <TableHead aria-sort={ariaSortValue("type")}>
                      <button
                        type="button"
                        className="group inline-flex items-center gap-1 rounded-sm px-0 py-0 text-sm font-semibold text-foreground/90 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        onClick={() => toggleQueueSort("type")}
                      >
                        Type {renderSortIcon("type")}
                      </button>
                    </TableHead>
                    <TableHead className="min-w-[170px]" aria-sort={ariaSortValue("due")}>
                      <button
                        type="button"
                        className="group inline-flex items-center gap-1 rounded-sm px-0 py-0 text-sm font-semibold text-foreground/90 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        onClick={() => toggleQueueSort("due")}
                      >
                        Due {renderSortIcon("due")}
                      </button>
                    </TableHead>
                    <TableHead aria-sort={ariaSortValue("assignee")}>
                      <button
                        type="button"
                        className="group inline-flex items-center gap-1 rounded-sm px-0 py-0 text-sm font-semibold text-foreground/90 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        onClick={() => toggleQueueSort("assignee")}
                      >
                        Assignee {renderSortIcon("assignee")}
                      </button>
                    </TableHead>
                    <TableHead className="w-[220px]">Actions</TableHead>
                    <TableHead aria-sort={ariaSortValue("status")}>
                      <button
                        type="button"
                        className="group inline-flex items-center gap-1 rounded-sm px-0 py-0 text-sm font-semibold text-foreground/90 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        onClick={() => toggleQueueSort("status")}
                      >
                        Status {renderSortIcon("status")}
                      </button>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {queueRows.map((item) => {
                    const requestId = item.request_id;
                    const isExpanded = expandedId === requestId;
                    const priority = mapPriority(item.priority);
                    const pConfig = priorityConfig[priority];
                    const status = item.status as Status;
                    const sConfig = statusConfig[status];
                    const dueSoonFlag = isDueSoon(item);
                    const dueAtTs = toTimestamp(item.sla_due_at);
                    const remainingHours =
                      dueAtTs === null
                        ? null
                        : Math.ceil((dueAtTs - Date.now()) / (1000 * 60 * 60));
                    const isOverdue = remainingHours !== null && remainingHours < 0;
                    const detail = detailById[requestId];
                    const isMine =
                      (item.assignee_user_id || "").toLowerCase() === currentUserEmail;
                    const canAssign = item.status !== "RESOLVED" && item.status !== "CANCELLED";
                    const isResolved = item.status === "RESOLVED";
                    const missingFields = detail?.missing_fields || [];
                    const agentSuggestionRaw =
                      detail?.request?.captured_fields?.["agent_suggestion"] ??
                      item.captured_fields?.["agent_suggestion"];
                    const agentSuggestion =
                      typeof agentSuggestionRaw === "string" && agentSuggestionRaw.trim()
                        ? agentSuggestionRaw
                        : null;

                    return (
                      <Fragment key={requestId}>
                        <TableRow
                          className={`cursor-pointer hover:bg-muted/30 ${isMine ? "bg-primary/5" : ""}`}
                          onClick={() => void handleExpand(requestId)}
                        >
                          <TableCell>
                            <Badge variant="outline" className={`text-xs ${pConfig.className}`}>
                              {pConfig.label}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-medium text-sm">
                            {item.requester_name || item.requester_user_id}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground max-w-[320px] truncate">
                            {item.summary}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline" className="text-xs">
                              {item.type} / {item.subtype}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-xs">
                            <div className="flex flex-col">
                              <span
                                className={
                                  isOverdue
                                    ? "font-medium text-destructive"
                                    : dueSoonFlag
                                    ? "font-medium text-amber-700"
                                    : "text-muted-foreground"
                                }
                              >
                                {remainingHours === null
                                  ? "No SLA"
                                  : isOverdue
                                  ? `${Math.abs(remainingHours)}h overdue`
                                  : `${remainingHours}h left`}
                              </span>
                              {item.sla_due_at && (
                                <span className="text-[10px] text-muted-foreground">
                                  Due {formatDateTime(item.sla_due_at)}
                                </span>
                              )}
                              {dueSoonFlag && !isOverdue && (
                                <span className="text-[10px] text-amber-700">Within 24h</span>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {item.assignee_name || item.assignee_user_id || "Unassigned"}
                          </TableCell>
                          <TableCell>
                            {!isResolved && (
                              <div className="flex items-center gap-2">
                                <Button
                                  size="sm"
                                  variant={isMine ? "secondary" : "outline"}
                                  className="h-8 px-3 text-xs"
                                  disabled={!canAssign}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    if (!canAssign) return;
                                    void runAction(
                                      requestId,
                                      () =>
                                        assignHRRequest(
                                          user!.email,
                                          requestId,
                                          isMine ? null : currentUserEmail
                                        ),
                                      isMine ? "Request unassigned" : "Assigned to you"
                                    );
                                  }}
                                >
                                  {isMine ? "Unassign" : "Assign to me"}
                                </Button>

                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="h-8 w-8"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    void handleExpand(requestId);
                                  }}
                                  aria-label={isExpanded ? "Collapse details" : "Expand details"}
                                >
                                  {isExpanded ? (
                                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                                  ) : (
                                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                  )}
                                </Button>
                              </div>
                            )}
                          </TableCell>
                          <TableCell>
                            <Badge variant="secondary" className="text-xs gap-1">
                              <sConfig.icon className={`h-3 w-3 ${sConfig.color}`} />
                              {sConfig.label}
                            </Badge>
                          </TableCell>
                        </TableRow>

                        {isExpanded && (
                          <TableRow>
                            <TableCell colSpan={8} className="bg-muted/10 p-0">
                              <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="px-6 py-4 space-y-4"
                              >
                                    <div className="grid md:grid-cols-2 gap-4">
                                      <div className="space-y-4">
                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            Employee Question
                                          </h4>
                                          <p className="text-sm bg-card rounded-lg p-3 border whitespace-pre-wrap">
                                            {item.description}
                                          </p>
                                        </div>
                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            AI-Drafted Response
                                          </h4>
                                          <div className="text-sm bg-accent/30 rounded-lg p-3 whitespace-pre-wrap border border-primary/10">
                                            {item.resolution_text || item.last_message_to_requester || "No resolution context yet."}
                                          </div>
                                        </div>
                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            Agent Suggestion
                                          </h4>
                                          <div className="text-sm bg-card rounded-lg p-3 border whitespace-pre-wrap">
                                            {agentSuggestion || "No agent suggestion captured."}
                                          </div>
                                        </div>
                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            Completeness
                                          </h4>
                                          <div className="rounded-lg border bg-card p-3 space-y-1">
                                            <div className="text-sm">
                                              {detail ? `${detail.completeness_percent}% complete` : "Loading..."}
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                              Missing: {missingFields.length > 0 ? missingFields.join(", ") : "None"}
                                            </div>
                                          </div>
                                        </div>
                                      </div>

                                      <div className="space-y-4">
                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            Timeline
                                          </h4>
                                          <div className="rounded-lg border bg-card p-3 max-h-[280px] overflow-auto space-y-2">
                                            {(detail?.timeline || []).length === 0 && (
                                              <div className="text-xs text-muted-foreground">No timeline events yet.</div>
                                            )}
                                            {(detail?.timeline || []).map((event) => (
                                              <div key={event.event_id} className="text-xs">
                                                <div className="font-medium">
                                                  {event.event_type.replace(/_/g, " ")}
                                                </div>
                                                <div className="text-muted-foreground">
                                                  {event.event_note || "No note"} · {formatDateTime(event.created_at)}
                                                </div>
                                              </div>
                                            ))}
                                          </div>
                                        </div>

                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            Message Requester
                                          </h4>
                                          <Textarea
                                            placeholder="Write a message to requester..."
                                            value={messageDraft[requestId] || ""}
                                            onChange={(e) =>
                                              setMessageDraft((prev) => ({
                                                ...prev,
                                                [requestId]: e.target.value,
                                              }))
                                            }
                                            className="text-sm min-h-[80px]"
                                          />
                                        </div>
                                      </div>
                                    </div>

                                    <div className="grid md:grid-cols-2 gap-3">
                                      <Select
                                        value={priority}
                                        onValueChange={(value) => {
                                          const next = value as Priority;
                                          void runAction(
                                            requestId,
                                            () => changeHRRequestPriority(user!.email, requestId, next),
                                            "Priority updated"
                                          );
                                        }}
                                      >
                                        <SelectTrigger className="h-9 text-sm">
                                          <SelectValue placeholder="Change priority" />
                                        </SelectTrigger>
                                        <SelectContent>
                                          <SelectItem value="P0">P0</SelectItem>
                                          <SelectItem value="P1">P1</SelectItem>
                                          <SelectItem value="P2">P2</SelectItem>
                                        </SelectContent>
                                      </Select>

                                      <Textarea
                                        placeholder="Resolution note (used for resolve/escalate)"
                                        value={resolutionNotes[requestId] || ""}
                                        onChange={(e) =>
                                          setResolutionNotes((prev) => ({
                                            ...prev,
                                            [requestId]: e.target.value,
                                          }))
                                        }
                                        className="text-sm min-h-[56px]"
                                      />
                                    </div>

                                    {!isResolved && (
                                      <div className="flex flex-wrap gap-2">
                                        <Button
                                          size="sm"
                                          variant={isMine ? "secondary" : "outline"}
                                          disabled={!canAssign}
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            if (!canAssign) return;
                                            void runAction(
                                              requestId,
                                              () =>
                                                assignHRRequest(
                                                  user!.email,
                                                  requestId,
                                                  isMine ? null : currentUserEmail
                                                ),
                                              isMine ? "Request unassigned" : "Assigned to you"
                                            );
                                          }}
                                        >
                                          {isMine ? (
                                            <UserX className="h-3.5 w-3.5 mr-1.5" />
                                          ) : (
                                            <UserPlus className="h-3.5 w-3.5 mr-1.5" />
                                          )}
                                          {isMine ? "Unassign" : "Assign to me"}
                                        </Button>

                                        <Button
                                          size="sm"
                                          variant="outline"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            const note = messageDraft[requestId]?.trim();
                                            if (!note) {
                                              toast.error("Please enter a message first.");
                                              return;
                                            }
                                            void runAction(
                                              requestId,
                                              () => messageHRRequestRequester(user!.email, requestId, note),
                                              "Requester message logged"
                                            );
                                          }}
                                        >
                                          <MessageSquare className="h-3.5 w-3.5 mr-1.5" />
                                          Message requester
                                        </Button>

                                        {(item.status === "NEW" || item.status === "READY" || item.status === "NEEDS_INFO") && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              void runAction(
                                                requestId,
                                                () => transitionHRRequestStatus(user!.email, requestId, "IN_PROGRESS"),
                                                "Moved to In Progress"
                                              );
                                            }}
                                          >
                                            <Clock className="h-3.5 w-3.5 mr-1.5" />
                                            Move to In Progress
                                          </Button>
                                        )}

                                        {(item.status === "IN_PROGRESS" || item.status === "ESCALATED") && (
                                          <Button
                                            size="sm"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              void runAction(
                                                requestId,
                                                () =>
                                                  transitionHRRequestStatus(
                                                    user!.email,
                                                    requestId,
                                                    "RESOLVED",
                                                    resolutionNotes[requestId]?.trim() || undefined
                                                  ),
                                                "Marked resolved"
                                              );
                                            }}
                                          >
                                            <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />
                                            Mark resolved
                                          </Button>
                                        )}

                                        {item.status !== "RESOLVED" && item.status !== "CANCELLED" && item.status !== "ESCALATED" && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              void runAction(
                                                requestId,
                                                () =>
                                                  escalateHRRequest(
                                                    user!.email,
                                                    requestId,
                                                    resolutionNotes[requestId]?.trim() || undefined
                                                  ),
                                                "Escalated request"
                                              );
                                            }}
                                          >
                                            <ShieldAlert className="h-3.5 w-3.5 mr-1.5" />
                                            Escalate
                                          </Button>
                                        )}

                                        {(item.status === "RESOLVED" || item.status === "CANCELLED") && (
                                          <span className="text-xs text-emerald-600 font-medium flex items-center gap-1">
                                            <CheckCircle2 className="h-3.5 w-3.5" />
                                            Closed
                                          </span>
                                        )}
                                      </div>
                                    )}

                                    <div className="text-xs text-muted-foreground">
                                      <FileText className="h-3.5 w-3.5 inline mr-1" />
                                      Last update: {formatDateTime(item.updated_at)}
                                    </div>
                              </motion.div>
                            </TableCell>
                          </TableRow>
                        )}
                      </Fragment>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </main>

      <MyRequestsPanel
        isOpen={requestsOpen}
        onClose={() => setRequestsOpen(false)}
        requests={assignedRequests}
        onRequestViewed={handleRequestViewed}
      />
    </div>
  );
}
