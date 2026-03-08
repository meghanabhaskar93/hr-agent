import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Send,
  Eye,
  ChevronDown,
  ChevronUp,
  UserPlus,
  Filter,
  Mail,
  MessageSquare,
  FileText,
  Timer,
} from "lucide-react";
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
import MyRequestsPanel from "@/components/MyRequestsPanel";
import type { Conversation } from "@/components/ConversationSidebar";
import { useAuth } from "@/contexts/AuthContext";
import { useHRTickets, type ResolutionTag, resolutionTagConfig } from "@/contexts/HRTicketsContext";
import { toast } from "sonner";

type Priority = "critical" | "high" | "medium";
type Status = "pending" | "assigned" | "in_progress" | "in_review" | "resolved";

const priorityConfig: Record<Priority, { label: string; className: string }> = {
  critical: { label: "Critical", className: "bg-destructive/10 text-destructive border-destructive/20" },
  high: { label: "High", className: "bg-warning/10 text-warning border-warning/20" },
  medium: { label: "Medium", className: "bg-muted text-muted-foreground" },
};

const statusConfig: Record<Status, { label: string; icon: typeof Clock; color: string }> = {
  pending: { label: "Pending", icon: AlertTriangle, color: "text-warning" },
  assigned: { label: "Assigned", icon: UserPlus, color: "text-primary" },
  in_progress: { label: "In Progress", icon: MessageSquare, color: "text-primary" },
  in_review: { label: "In Review", icon: Clock, color: "text-info" },
  resolved: { label: "Resolved", icon: CheckCircle2, color: "text-emerald-500" },
};

type FilterCategory = "all" | string;

function slaTimeRemaining(inReviewSince: Date | undefined, slaHours: number): { label: string; urgent: boolean } {
  if (!inReviewSince) return { label: `${slaHours}h SLA`, urgent: false };
  const elapsed = (Date.now() - inReviewSince.getTime()) / 3600000;
  const remaining = slaHours - elapsed;
  if (remaining <= 0) return { label: "SLA expired", urgent: true };
  if (remaining < 6) return { label: `${Math.ceil(remaining)}h left`, urgent: true };
  return { label: `${Math.ceil(remaining)}h left`, urgent: false };
}

export default function HROps() {
  const { user } = useAuth();
  const { tickets, assignTicketToMe, updateTicketStatus, addResolutionNote, getAssignedTickets, getAssignedRequests } = useHRTickets();
  const navigate = useNavigate();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<FilterCategory>("all");
  const [requestsOpen, setRequestsOpen] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [resolutionNotes, setResolutionNotes] = useState<Record<string, string>>({});
  const [resolutionTags, setResolutionTags] = useState<Record<string, ResolutionTag>>({});

  const displayName = user?.email?.split("@")[0] ?? "HR User";
  const categories = Array.from(new Set(tickets.map((t) => t.category)));
  const assignedTickets = getAssignedTickets(displayName);
  const assignedRequests = getAssignedRequests(displayName);

  const filtered = categoryFilter === "all" ? tickets : tickets.filter((t) => t.category === categoryFilter);
  const sorted = [...filtered].sort((a, b) => {
    const statusOrder: Record<Status, number> = { pending: 0, assigned: 1, in_progress: 2, in_review: 3, resolved: 4 };
    const statusDiff = statusOrder[a.status] - statusOrder[b.status];
    if (statusDiff !== 0) return statusDiff;
    const order: Record<Priority, number> = { critical: 0, high: 1, medium: 2 };
    return order[a.priority] - order[b.priority];
  });

  const pendingCount = tickets.filter((t) => t.status === "pending").length;
  const inProgressCount = tickets.filter((t) => ["assigned", "in_progress"].includes(t.status)).length;
  const inReviewCount = tickets.filter((t) => t.status === "in_review").length;

  const handleWorkOnThis = (ticketId: string) => {
    const ticket = tickets.find((t) => t.id === ticketId);
    if (!ticket) return;

    // Update status to in_progress
    updateTicketStatus(ticketId, "in_progress");

    // Navigate to HR Chat with ticket context
    navigate(`/hr-chat?ticket=${ticketId}`);
  };

  const handleMoveToReview = (ticketId: string) => {
    const note = resolutionNotes[ticketId];
    const tag = resolutionTags[ticketId];
    if (!note?.trim()) {
      toast.error("Please add a resolution note before moving to review.");
      return;
    }
    if (!tag) {
      toast.error("Please select a resolution tag before moving to review.");
      return;
    }
    addResolutionNote(ticketId, note.trim(), tag);
    updateTicketStatus(ticketId, "in_review");
    toast.success("Ticket moved to In Review. Waiting for employee confirmation.");
  };

  const handleResolve = (ticketId: string) => {
    updateTicketStatus(ticketId, "resolved");
    toast.success("Ticket resolved!");
  };

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
        onClearAll={() => { setConversations([]); setActiveConversation(null); }}
        assignedCount={assignedTickets.length}
      />

      <main className="flex-1 flex flex-col min-w-0 h-screen overflow-auto">
        <header className="flex items-center justify-between px-6 py-3 border-b bg-card">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-base text-primary">PingHR</span>
            <span className="text-muted-foreground text-sm">/ HR Ops</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="gap-2 text-primary border-primary/30 hover:bg-primary/5"
            onClick={() => setRequestsOpen(true)}
          >
            <Mail className="h-4 w-4" />
            My Requests
            {assignedTickets.length > 0 && (
              <span className="ml-1 h-5 min-w-5 px-1 rounded-full bg-destructive text-destructive-foreground text-[10px] font-bold flex items-center justify-center">
                {assignedTickets.length}
              </span>
            )}
          </Button>
        </header>

        <div className="p-6 max-w-6xl mx-auto w-full">
          {/* Summary stats */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold mb-1">HR Ops Queue</h1>
              <p className="text-muted-foreground text-sm">
                {pendingCount} pending · {inProgressCount} in progress · {inReviewCount} in review · {tickets.length} total
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                <SelectTrigger className="w-48 h-9 text-sm">
                  <SelectValue placeholder="All categories" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All categories</SelectItem>
                  {categories.map((cat) => (
                    <SelectItem key={cat} value={cat}>{cat}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="bg-card border rounded-xl shadow-soft overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/30">
                  <TableHead className="w-[100px]">Priority</TableHead>
                  <TableHead>Employee</TableHead>
                  <TableHead className="max-w-[300px]">Query</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[180px]">Actions</TableHead>
                  <TableHead className="w-[60px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((ticket) => {
                  const pConfig = priorityConfig[ticket.priority];
                  const sConfig = statusConfig[ticket.status];
                  const isExpanded = expandedId === ticket.id;
                  const isAssignedToMe = ticket.assignedTo === displayName;

                  return (
                    <>
                      <TableRow
                        key={ticket.id}
                        className={`cursor-pointer hover:bg-muted/30 ${isAssignedToMe ? "bg-primary/5" : ""}`}
                        onClick={() => setExpandedId(isExpanded ? null : ticket.id)}
                      >
                        <TableCell>
                          <Badge variant="outline" className={`text-xs ${pConfig.className}`}>
                            {pConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-medium text-sm">{ticket.employee}</TableCell>
                        <TableCell className="text-sm text-muted-foreground max-w-[300px] truncate">
                          {ticket.question}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <Badge variant="outline" className="text-xs">{ticket.category}</Badge>
                            {ticket.resolutionTag && (
                              <Badge variant="outline" className={`text-xs ${resolutionTagConfig[ticket.resolutionTag].className}`}>
                                {resolutionTagConfig[ticket.resolutionTag].label}
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="text-xs gap-1">
                            <sConfig.icon className={`h-3 w-3 ${sConfig.color}`} />
                            {sConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {!ticket.assignedTo && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 text-xs gap-1"
                              onClick={(e) => {
                                e.stopPropagation();
                                assignTicketToMe(ticket.id, displayName);
                              }}
                            >
                              <UserPlus className="h-3 w-3" />
                              Assign to me
                            </Button>
                          )}
                          {isAssignedToMe && !["in_review", "resolved"].includes(ticket.status) && (
                            <Button
                              size="sm"
                              className="h-7 text-xs gap-1"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleWorkOnThis(ticket.id);
                              }}
                            >
                              <MessageSquare className="h-3 w-3" />
                              Work on this
                            </Button>
                          )}
                          {isAssignedToMe && ticket.status === "in_review" && (
                            <div className="flex items-center gap-1.5">
                              <Timer className={`h-3 w-3 ${slaTimeRemaining(ticket.inReviewSince, ticket.slaHours).urgent ? "text-destructive" : "text-muted-foreground"}`} />
                              <span className={`text-xs ${slaTimeRemaining(ticket.inReviewSince, ticket.slaHours).urgent ? "text-destructive font-medium" : "text-muted-foreground"}`}>
                                {slaTimeRemaining(ticket.inReviewSince, ticket.slaHours).label}
                              </span>
                            </div>
                          )}
                          {ticket.status === "resolved" && (
                            <span className="text-xs text-emerald-600 font-medium flex items-center gap-1">
                              <CheckCircle2 className="h-3 w-3" /> Resolved
                            </span>
                          )}
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
                        <TableRow key={`${ticket.id}-expanded`}>
                          <TableCell colSpan={7} className="bg-muted/10 p-0">
                            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="px-6 py-4 space-y-4">
                              {/* Employee Question */}
                              <div>
                                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Employee Question</h4>
                                <p className="text-sm bg-card rounded-lg p-3 border">{ticket.question}</p>
                              </div>

                              {/* AI-Drafted Response */}
                              <div>
                                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">AI-Drafted Response</h4>
                                <div className="text-sm bg-accent/30 rounded-lg p-3 whitespace-pre-wrap border border-primary/10">
                                  {ticket.aiDraft.split(/(\*\*.*?\*\*)/).map((part, i) =>
                                    part.startsWith("**") && part.endsWith("**") ? (
                                      <strong key={i}>{part.slice(2, -2)}</strong>
                                    ) : (
                                      <span key={i}>{part}</span>
                                    )
                                  )}
                                </div>
                              </div>

                              {/* Resolution Note */}
                              {isAssignedToMe && ["assigned", "in_progress"].includes(ticket.status) && (
                                <div className="space-y-3">
                                  <div>
                                    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                      <FileText className="h-3 w-3 inline mr-1" />
                                      Resolution Note
                                    </h4>
                                    <Textarea
                                      placeholder="Add your resolution note here... (required to move to In Review)"
                                      value={resolutionNotes[ticket.id] || ""}
                                      onChange={(e) => setResolutionNotes((prev) => ({ ...prev, [ticket.id]: e.target.value }))}
                                      className="text-sm min-h-[80px]"
                                    />
                                  </div>
                                  <div>
                                    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                      Resolution Tag
                                    </h4>
                                    <div className="flex flex-wrap gap-2">
                                      {(Object.entries(resolutionTagConfig) as [ResolutionTag, { label: string; className: string }][]).map(([key, config]) => (
                                        <button
                                          key={key}
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            setResolutionTags((prev) => ({ ...prev, [ticket.id]: key }));
                                          }}
                                          className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                                            resolutionTags[ticket.id] === key
                                              ? `${config.className} ring-2 ring-offset-1 ring-current`
                                              : "border-border text-muted-foreground hover:bg-muted"
                                          }`}
                                        >
                                          {config.label}
                                        </button>
                                      ))}
                                    </div>
                                  </div>
                                </div>
                              )}

                              {/* Existing resolution note display */}
                              {ticket.resolutionNote && (
                                <div>
                                  <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Resolution Note</h4>
                                  <p className="text-sm bg-emerald-50 dark:bg-emerald-950/20 rounded-lg p-3 border border-emerald-200 dark:border-emerald-800">
                                    {ticket.resolutionNote}
                                  </p>
                                </div>
                              )}

                              {/* SLA info for in_review */}
                              {ticket.status === "in_review" && (
                                <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 rounded-lg border">
                                  <Timer className={`h-4 w-4 ${slaTimeRemaining(ticket.inReviewSince, ticket.slaHours).urgent ? "text-destructive" : "text-muted-foreground"}`} />
                                  <span className="text-xs text-muted-foreground">
                                    SLA: Auto-resolves in <span className="font-medium">{slaTimeRemaining(ticket.inReviewSince, ticket.slaHours).label}</span> if employee doesn't respond
                                  </span>
                                </div>
                              )}

                              {/* Actions */}
                              <div className="flex gap-2 pt-1">
                                {!ticket.assignedTo && (
                                  <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); assignTicketToMe(ticket.id, displayName); }}>
                                    <UserPlus className="h-3.5 w-3.5 mr-1.5" /> Assign to me
                                  </Button>
                                )}
                                {isAssignedToMe && !["in_review", "resolved"].includes(ticket.status) && (
                                  <>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={(e) => { e.stopPropagation(); handleWorkOnThis(ticket.id); }}
                                    >
                                      <MessageSquare className="h-3.5 w-3.5 mr-1.5" /> Ask the Agent
                                    </Button>
                                    <Button
                                      size="sm"
                                      onClick={(e) => { e.stopPropagation(); handleMoveToReview(ticket.id); }}
                                    >
                                      <Eye className="h-3.5 w-3.5 mr-1.5" /> Move to In Review
                                    </Button>
                                  </>
                                )}
                                {isAssignedToMe && ticket.status === "in_review" && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="gap-1.5 text-emerald-600 border-emerald-200 hover:bg-emerald-50"
                                    onClick={(e) => { e.stopPropagation(); handleResolve(ticket.id); }}
                                  >
                                    <CheckCircle2 className="h-3.5 w-3.5" /> Mark as Resolved
                                  </Button>
                                )}
                                {ticket.status === "resolved" && (
                                  <span className="text-xs text-emerald-600 font-medium flex items-center gap-1">
                                    <CheckCircle2 className="h-3.5 w-3.5" /> Resolved
                                    {ticket.timeToResolve && ` · ${ticket.timeToResolve} min`}
                                  </span>
                                )}
                              </div>
                            </motion.div>
                          </TableCell>
                        </TableRow>
                      )}
                    </>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </div>
      </main>

      <MyRequestsPanel isOpen={requestsOpen} onClose={() => setRequestsOpen(false)} requests={assignedRequests} onWorkOnRequest={handleWorkOnThis} />
    </div>
  );
}
