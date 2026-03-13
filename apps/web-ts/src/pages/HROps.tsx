import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  Filter,
  Mail,
  MessageSquare,
  ShieldAlert,
  UserMinus,
  UserPlus,
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
  assignEscalation,
  changeEscalationPriority,
  escalateEscalationCase,
  fetchEscalationDetail,
  fetchEscalations,
  messageEscalationRequester,
  transitionEscalation,
  type BackendEscalation,
  type BackendEscalationDetail,
} from "@/lib/backend";

type Priority = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
type Status = "PENDING" | "IN_REVIEW" | "RESOLVED";
type FilterCategory = "all" | string;

const priorityConfig: Record<Priority, { label: string; className: string }> = {
  CRITICAL: { label: "Critical", className: "bg-destructive/10 text-destructive border-destructive/20" },
  HIGH: { label: "High", className: "bg-warning/10 text-warning border-warning/20" },
  MEDIUM: { label: "Medium", className: "bg-muted text-muted-foreground border-border" },
  LOW: { label: "Low", className: "bg-accent/20 text-accent-foreground border-accent/30" },
};

const statusConfig: Record<Status, { label: string; icon: typeof Clock; color: string }> = {
  PENDING: { label: "Pending", icon: AlertTriangle, color: "text-warning" },
  IN_REVIEW: { label: "In Review", icon: Clock, color: "text-info" },
  RESOLVED: { label: "Resolved", icon: CheckCircle2, color: "text-emerald-500" },
};

const priorityOrder: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
};

function mapPriority(p: string | null | undefined): Priority {
  if (p === "CRITICAL" || p === "HIGH" || p === "MEDIUM" || p === "LOW") return p;
  return "MEDIUM";
}

function sortEscalations(items: BackendEscalation[]): BackendEscalation[] {
  return [...items].sort((a, b) => {
    const pDiff = (priorityOrder[a.priority || "MEDIUM"] ?? 2) - (priorityOrder[b.priority || "MEDIUM"] ?? 2);
    if (pDiff !== 0) return pDiff;
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
  });
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString();
}

function toMyRequest(
  item: BackendEscalation,
  detail: BackendEscalationDetail | null
): EscalatedRequest {
  const status =
    item.status === "IN_REVIEW"
      ? "in_review"
      : item.status === "RESOLVED"
        ? "resolved"
        : "pending";

  const priority = mapPriority(item.priority).toLowerCase();
  const panelPriority =
    priority === "critical" || priority === "high" || priority === "medium"
      ? priority
      : "medium";

  return {
    id: String(item.escalation_id),
    summary:
      item.source_message_excerpt.length > 60
        ? `${item.source_message_excerpt.slice(0, 60)}...`
        : item.source_message_excerpt,
    fullSummary: `${item.requester_name || item.requester_email}: ${item.source_message_excerpt}`,
    aiResponse:
      item.agent_suggestion ||
      item.resolution_note ||
      "No agent suggestion captured for this request.",
    status,
    priority: panelPriority,
    category: item.category || "General",
    timestamp: new Date(item.created_at),
    auditLog:
      detail?.timeline?.map((event) => ({
        label: event.event_note || event.event_type.replace(/_/g, " "),
        timestamp: new Date(event.created_at),
      })) || [
        { label: "Escalated", timestamp: new Date(item.created_at) },
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
  const [categoryFilter, setCategoryFilter] = useState<FilterCategory>("all");
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<BackendEscalation[]>([]);
  const [detailById, setDetailById] = useState<Record<number, BackendEscalationDetail>>({});
  const [messageDraft, setMessageDraft] = useState<Record<number, string>>({});
  const [resolutionNotes, setResolutionNotes] = useState<Record<number, string>>({});

  const currentUserEmail = user?.email?.toLowerCase() || "";

  const loadEscalations = useCallback(async () => {
    if (!user?.email) return;
    const rows = await fetchEscalations(user.email);
    setItems(rows);
  }, [user?.email]);

  const loadDetail = useCallback(
    async (escalationId: number) => {
      if (!user?.email) return;
      const detail = await fetchEscalationDetail(user.email, escalationId);
      setDetailById((prev) => ({ ...prev, [escalationId]: detail }));
    },
    [user?.email]
  );

  const syncEscalation = useCallback(
    async (escalationId: number) => {
      if (!user?.email) return;
      const detail = await fetchEscalationDetail(user.email, escalationId);
      setDetailById((prev) => ({ ...prev, [escalationId]: detail }));
      setItems((prev) =>
        prev.map((item) =>
          item.escalation_id === escalationId ? detail.request : item
        )
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
        const rows = await fetchEscalations(user.email);
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

  const handleExpand = async (escalationId: number) => {
    const isExpanded = expandedId === escalationId;
    setExpandedId(isExpanded ? null : escalationId);
    if (isExpanded || detailById[escalationId]) return;
    try {
      await loadDetail(escalationId);
    } catch (error: any) {
      toast.error(error?.message || "Failed to load request detail");
    }
  };

  const runAction = async (
    escalationId: number,
    action: () => Promise<unknown>,
    successMessage: string
  ) => {
    try {
      await action();
      toast.success(successMessage);
      try {
        await syncEscalation(escalationId);
      } catch {
        // Fallback to full queue refresh only if targeted sync fails.
        await loadEscalations();
      }
    } catch (error: any) {
      toast.error(error?.message || "Action failed");
    }
  };

  const categories = useMemo(
    () => Array.from(new Set(items.map((item) => item.category || "General"))),
    [items]
  );

  const filtered = useMemo(() => {
    if (categoryFilter === "all") return items;
    return items.filter((item) => (item.category || "General") === categoryFilter);
  }, [categoryFilter, items]);

  const assignedToMeAll = filtered.filter(
    (item) => (item.assigned_to_email || "").toLowerCase() === currentUserEmail
  );
  const unresolved = filtered.filter((item) => item.status !== "RESOLVED");
  const resolved = filtered.filter((item) => item.status === "RESOLVED");
  const assignedToMe = assignedToMeAll.filter((item) => item.status !== "RESOLVED");
  const unassigned = unresolved.filter((item) => !item.assigned_to_email);
  const assignedToOthers = unresolved.filter(
    (item) => item.assigned_to_email && (item.assigned_to_email || "").toLowerCase() !== currentUserEmail
  );

  const assignedRequests = sortEscalations(assignedToMeAll).map((item) =>
    toMyRequest(item, detailById[item.escalation_id] || null)
  );

  return (
    <div className="min-h-screen flex w-full">
      <HRConversationSidebar
        activeConversationId={activeConversation}
        conversations={conversations}
        onSelectConversation={setActiveConversation}
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
            {assignedToMeAll.length > 0 && (
              <span className="ml-1 h-5 min-w-5 px-1 rounded-full bg-destructive text-destructive-foreground text-[10px] font-bold flex items-center justify-center">
                {assignedToMeAll.length}
              </span>
            )}
          </Button>
        </header>

        <div className="p-6 max-w-7xl mx-auto w-full">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold mb-1">Escalation Queue</h1>
              <p className="text-muted-foreground text-sm">
                {items.length} total · {unresolved.length} active · {resolved.length} resolved
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                <SelectTrigger className="w-56 h-9 text-sm">
                  <SelectValue placeholder="All categories" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All categories</SelectItem>
                  {categories.map((cat) => (
                    <SelectItem key={cat} value={cat}>
                      {cat}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {loading ? (
            <div className="text-sm text-muted-foreground">Loading queue...</div>
          ) : (
            <div className="space-y-5">
              {[
                { label: "Assigned to Me", rows: sortEscalations(assignedToMe) },
                { label: "Unassigned", rows: sortEscalations(unassigned) },
                { label: "Assigned to Others", rows: sortEscalations(assignedToOthers) },
                { label: "Resolved", rows: sortEscalations(resolved) },
              ].map((section) => (
                <div key={section.label} className="bg-card border rounded-xl shadow-soft overflow-hidden">
                  <div className="px-4 py-3 border-b bg-muted/20 text-sm font-semibold">
                    {section.label} ({section.rows.length})
                  </div>
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/30">
                        <TableHead className="w-[110px]">Priority</TableHead>
                        <TableHead>Requester</TableHead>
                        <TableHead className="max-w-[320px]">Request</TableHead>
                        <TableHead>Category</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Assignee</TableHead>
                        <TableHead className="w-[60px]" />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {section.rows.map((item) => {
                        const escalationId = item.escalation_id;
                        const isExpanded = expandedId === escalationId;
                        const priority = mapPriority(item.priority);
                        const pConfig = priorityConfig[priority];
                        const status = (item.status || "PENDING") as Status;
                        const sConfig = statusConfig[status];
                        const detail = detailById[escalationId];
                        const isMine =
                          (item.assigned_to_email || "").toLowerCase() === currentUserEmail;
                        const missingFields = detail?.missing_fields || [];

                        return (
                          <Fragment key={escalationId}>
                            <TableRow
                              className={`cursor-pointer hover:bg-muted/30 ${isMine ? "bg-primary/5" : ""}`}
                              onClick={() => void handleExpand(escalationId)}
                            >
                              <TableCell>
                                <Badge variant="outline" className={`text-xs ${pConfig.className}`}>
                                  {pConfig.label}
                                </Badge>
                              </TableCell>
                              <TableCell className="font-medium text-sm">
                                {item.requester_name || item.requester_email}
                              </TableCell>
                              <TableCell className="text-sm text-muted-foreground max-w-[320px] truncate">
                                {item.source_message_excerpt}
                              </TableCell>
                              <TableCell>
                                <Badge variant="outline" className="text-xs">
                                  {item.category || "General"}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                <Badge variant="secondary" className="text-xs gap-1">
                                  <sConfig.icon className={`h-3 w-3 ${sConfig.color}`} />
                                  {sConfig.label}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-xs text-muted-foreground">
                                {item.assigned_to_name || item.assigned_to_email || "Unassigned"}
                              </TableCell>
                              <TableCell>
                                {isExpanded ? (
                                  <ChevronUp className="h-4 w-4 text-muted-foreground" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                )}
                              </TableCell>
                            </TableRow>

                            {isExpanded && (
                              <TableRow>
                                <TableCell colSpan={7} className="bg-muted/10 p-0">
                                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="px-6 py-4 space-y-4">
                                    <div className="grid md:grid-cols-2 gap-4">
                                      <div className="space-y-4">
                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            Request Detail
                                          </h4>
                                          <p className="text-sm bg-card rounded-lg p-3 border">
                                            {item.source_message_excerpt}
                                          </p>
                                        </div>
                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            Agent Suggestion
                                          </h4>
                                          <div className="text-sm bg-accent/30 rounded-lg p-3 whitespace-pre-wrap border border-primary/10">
                                            {item.agent_suggestion || "No suggestion captured."}
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
                                            value={messageDraft[escalationId] || ""}
                                            onChange={(e) =>
                                              setMessageDraft((prev) => ({
                                                ...prev,
                                                [escalationId]: e.target.value,
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
                                            escalationId,
                                            () =>
                                              changeEscalationPriority(
                                                user!.email,
                                                escalationId,
                                                next
                                              ),
                                            "Priority updated"
                                          );
                                        }}
                                      >
                                        <SelectTrigger className="h-9 text-sm">
                                          <SelectValue placeholder="Change priority" />
                                        </SelectTrigger>
                                        <SelectContent>
                                          <SelectItem value="CRITICAL">Critical</SelectItem>
                                          <SelectItem value="HIGH">High</SelectItem>
                                          <SelectItem value="MEDIUM">Medium</SelectItem>
                                          <SelectItem value="LOW">Low</SelectItem>
                                        </SelectContent>
                                      </Select>

                                      <Textarea
                                        placeholder="Resolution note (used for resolve/escalate)"
                                        value={resolutionNotes[escalationId] || ""}
                                        onChange={(e) =>
                                          setResolutionNotes((prev) => ({
                                            ...prev,
                                            [escalationId]: e.target.value,
                                          }))
                                        }
                                        className="text-sm min-h-[56px]"
                                      />
                                    </div>

                                    <div className="flex flex-wrap gap-2">
                                      {!isMine ? (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            void runAction(
                                              escalationId,
                                              () =>
                                                assignEscalation(
                                                  user!.email,
                                                  escalationId,
                                                  user!.email
                                                ),
                                              "Assigned to you"
                                            );
                                          }}
                                        >
                                          <UserPlus className="h-3.5 w-3.5 mr-1.5" />
                                          Assign to me
                                        </Button>
                                      ) : (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            void runAction(
                                              escalationId,
                                              () => assignEscalation(user!.email, escalationId, null),
                                              "Unassigned"
                                            );
                                          }}
                                        >
                                          <UserMinus className="h-3.5 w-3.5 mr-1.5" />
                                          Unassign
                                        </Button>
                                      )}

                                      <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          const note = messageDraft[escalationId]?.trim();
                                          if (!note) {
                                            toast.error("Please enter a message first.");
                                            return;
                                          }
                                          void runAction(
                                            escalationId,
                                            () =>
                                              messageEscalationRequester(
                                                user!.email,
                                                escalationId,
                                                note
                                              ),
                                            "Requester message logged"
                                          );
                                        }}
                                      >
                                        <MessageSquare className="h-3.5 w-3.5 mr-1.5" />
                                        Message requester
                                      </Button>

                                      {item.status === "PENDING" && (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            void runAction(
                                              escalationId,
                                              () =>
                                                transitionEscalation(
                                                  user!.email,
                                                  escalationId,
                                                  "IN_REVIEW"
                                                ),
                                              "Moved to In Review"
                                            );
                                          }}
                                        >
                                          <Clock className="h-3.5 w-3.5 mr-1.5" />
                                          Move to In Review
                                        </Button>
                                      )}

                                      {item.status === "IN_REVIEW" && (
                                        <Button
                                          size="sm"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            void runAction(
                                              escalationId,
                                              () =>
                                                transitionEscalation(
                                                  user!.email,
                                                  escalationId,
                                                  "RESOLVED",
                                                  resolutionNotes[escalationId]?.trim() || undefined
                                                ),
                                              "Marked resolved"
                                            );
                                          }}
                                        >
                                          <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />
                                          Mark resolved
                                        </Button>
                                      )}

                                      {item.status !== "RESOLVED" && (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            void runAction(
                                              escalationId,
                                              () =>
                                                escalateEscalationCase(
                                                  user!.email,
                                                  escalationId,
                                                  resolutionNotes[escalationId]?.trim() || undefined
                                                ),
                                              "Escalated to critical priority"
                                            );
                                          }}
                                        >
                                          <ShieldAlert className="h-3.5 w-3.5 mr-1.5" />
                                          Escalate
                                        </Button>
                                      )}

                                      {item.status === "RESOLVED" && (
                                        <span className="text-xs text-emerald-600 font-medium flex items-center gap-1">
                                          <CheckCircle2 className="h-3.5 w-3.5" />
                                          Resolved
                                        </span>
                                      )}
                                    </div>

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
              ))}
            </div>
          )}
        </div>
      </main>

      <MyRequestsPanel
        isOpen={requestsOpen}
        onClose={() => setRequestsOpen(false)}
        requests={assignedRequests}
      />
    </div>
  );
}
