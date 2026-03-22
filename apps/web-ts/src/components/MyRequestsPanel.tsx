import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X, ChevronDown, ChevronUp, FileText, MessageSquare, ArrowRight, Timer, CheckCircle2, Tag } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import type { ResolutionTag } from "@/contexts/HRTicketsContext";
import { resolutionTagConfig } from "@/contexts/HRTicketsContext";
import { useAuth } from "@/contexts/AuthContext";

type RequestStatus = "pending" | "assigned" | "in_progress" | "in_review" | "resolved";

export interface AuditEvent {
  label: string;
  timestamp: Date;
}

export interface EscalatedRequest {
  id: string;
  summary: string;
  fullSummary: string;
  aiResponse: string;
  status: RequestStatus;
  priority: "critical" | "high" | "medium";
  category: string;
  timestamp: Date;
  lastUpdatedAt?: Date;
  auditLog: AuditEvent[];
  resolutionTag?: ResolutionTag;
}

function timeAgo(date: Date): string {
  const hours = Math.floor((Date.now() - date.getTime()) / 3600000);
  if (hours < 1) return "just now";
  if (hours < 24) return `about ${hours} hours ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

function formatDate(date: Date): string {
  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }) + ", " + date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

const statusLabels: Record<RequestStatus, string> = {
  pending: "Pending Review",
  assigned: "Assigned",
  in_progress: "In Progress",
  in_review: "In Review",
  resolved: "Resolved",
};

const statusBadgeStyles: Record<RequestStatus, string> = {
  pending: "border-warning/30 text-warning bg-warning/5",
  assigned: "border-accent/30 text-accent-foreground bg-accent/30",
  in_progress: "border-primary/30 text-primary bg-primary/5",
  in_review: "border-info/30 text-info bg-info/5",
  resolved: "border-success/30 text-success bg-success/5",
};

const priorityColors: Record<string, string> = {
  critical: "bg-destructive/10 text-destructive border-destructive/20",
  high: "bg-warning/10 text-warning border-warning/20",
  medium: "bg-muted text-muted-foreground border-border",
};

type FilterTab = "all" | "pending" | "in_progress" | "in_review" | "resolved";

interface MyRequestsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  requests: EscalatedRequest[];
  title?: string;
  subtitle?: string;
  emptyStateMessage?: string;
  onWorkOnRequest?: (requestId: string) => void;
  onReplyToRequest?: (requestId: string, message: string) => Promise<void> | void;
  onRequestViewed?: (request: EscalatedRequest) => void;
}

function isActiveStatus(status: RequestStatus): boolean {
  return status === "in_progress" || status === "assigned";
}

export default function MyRequestsPanel({
  isOpen,
  onClose,
  requests,
  title = "My Requests",
  subtitle,
  emptyStateMessage = "No requests yet. Escalate a response to create one.",
  onWorkOnRequest,
  onReplyToRequest,
  onRequestViewed,
}: MyRequestsPanelProps) {
  const { role } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showAiResponseId, setShowAiResponseId] = useState<string | null>(null);
  const [replyDraftById, setReplyDraftById] = useState<Record<string, string>>({});
  const [replyingId, setReplyingId] = useState<string | null>(null);
  const canWorkOnRequests = role === "hr";

  const handleWorkOn = (reqId: string) => {
    if (!canWorkOnRequests) return;
    if (onWorkOnRequest) {
      onWorkOnRequest(reqId);
    } else {
      navigate(`/hr-chat?ticket=${reqId}`);
    }
    onClose();
  };

  const pendingCount = requests.filter((r) => r.status === "pending").length;
  const inProgressCount = requests.filter((r) => isActiveStatus(r.status)).length;
  const inReviewCount = requests.filter((r) => r.status === "in_review").length;
  const resolvedCount = requests.filter((r) => r.status === "resolved").length;

  const filtered =
    activeTab === "all"
      ? requests
      : requests.filter((r) =>
          activeTab === "in_progress" ? isActiveStatus(r.status) : r.status === activeTab
        );

  const handleReply = async (requestId: string) => {
    if (!onReplyToRequest || canWorkOnRequests) return;
    const message = (replyDraftById[requestId] || "").trim();
    if (!message) return;
    setReplyingId(requestId);
    try {
      await onReplyToRequest(requestId, message);
      setReplyDraftById((prev) => ({ ...prev, [requestId]: "" }));
    } finally {
      setReplyingId(null);
    }
  };

  const tabs: { key: FilterTab; label: string }[] = [
    { key: "all", label: "All" },
    { key: "pending", label: "Pending" },
    { key: "in_progress", label: "Active" },
    { key: "in_review", label: "In Review" },
    { key: "resolved", label: "Resolved" },
  ];

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", damping: 28, stiffness: 300 }}
          className="w-96 border-l bg-card flex flex-col h-full flex-shrink-0 fixed right-0 top-0 bottom-0 z-40"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 pt-5 pb-3">
            <div>
              <h2 className="text-lg font-semibold">{title}</h2>
              <p className="text-xs text-muted-foreground">
                {subtitle ?? `${requests.length} escalated queries`}
              </p>
            </div>
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted transition-colors">
              <X className="h-4 w-4 text-muted-foreground" />
            </button>
          </div>

          {/* Stats */}
          <div className="px-5 pb-4">
            <div className="grid grid-cols-4 gap-2 text-center">
              <div className="py-2">
                <p className="text-2xl font-bold text-warning">{pendingCount}</p>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Pending</p>
              </div>
              <div className="py-2">
                <p className="text-2xl font-bold text-primary">{inProgressCount}</p>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Active</p>
              </div>
              <div className="py-2">
                <p className="text-2xl font-bold text-info">{inReviewCount}</p>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">In Review</p>
              </div>
              <div className="py-2">
                <p className="text-2xl font-bold text-success">{resolvedCount}</p>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Resolved</p>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="px-5 pb-3 flex gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  activeTab === tab.key
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Request Cards */}
          <div className="flex-1 overflow-y-auto px-5 pb-4 space-y-3 bg-card">
            {filtered.length === 0 && (
              <div className="text-center py-8 text-sm text-muted-foreground">
                {emptyStateMessage}
              </div>
            )}
            {filtered.map((req) => {
              const isExpanded = expandedId === req.id;
              const showAi = showAiResponseId === req.id;

              return (
                <div
                  key={req.id}
                  className={`border rounded-xl bg-card transition-all ${
                    isExpanded ? "border-l-[3px] border-l-warning" : ""
                  }`}
                >
                  {/* Collapsed header */}
                  <div className="p-4">
                    <div className="flex items-start gap-2.5">
                      <FileText className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm leading-snug mb-2">{req.summary}</p>
                        <div className="flex items-center gap-1.5 mb-2">
                          <Badge
                            variant="outline"
                            className={`text-[10px] px-1.5 py-0 ${statusBadgeStyles[req.status]}`}
                          >
                            ● {statusLabels[req.status]}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <Badge
                            variant="outline"
                            className={`text-[10px] px-1.5 py-0 ${priorityColors[req.priority]}`}
                          >
                            ● {req.priority.charAt(0).toUpperCase() + req.priority.slice(1)}
                          </Badge>
                          <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                            {req.category}
                          </Badge>
                          {req.resolutionTag && (
                            <Badge
                              variant="outline"
                              className={`text-[10px] px-1.5 py-0 gap-0.5 ${resolutionTagConfig[req.resolutionTag].className}`}
                            >
                              <Tag className="h-2.5 w-2.5" />
                              {resolutionTagConfig[req.resolutionTag].label}
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-2">{timeAgo(req.timestamp)}</p>
                      </div>
                      <button
                        onClick={() => {
                          const shouldExpand = !isExpanded;
                          setExpandedId(shouldExpand ? req.id : null);
                          if (isExpanded) setShowAiResponseId(null);
                          if (shouldExpand) onRequestViewed?.(req);
                        }}
                        aria-label={isExpanded ? `Collapse request ${req.id}` : `Expand request ${req.id}`}
                        className="p-1 rounded hover:bg-muted transition-colors flex-shrink-0"
                      >
                        <ChevronDown
                          className={`h-4 w-4 text-muted-foreground transition-transform ${
                            isExpanded ? "rotate-180" : ""
                          }`}
                        />
                      </button>
                    </div>
                  </div>

                  {/* Expanded content */}
                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                      >
                        <div className="px-4 pb-4 space-y-3">
                          {/* Summary */}
                          <div className="border-l-2 border-warning/40 bg-warning/5 rounded-r-lg p-3">
                            <p className="text-[10px] font-semibold text-warning uppercase tracking-wider mb-1.5">
                              Summary
                            </p>
                            <p className="text-sm leading-relaxed text-foreground">
                              {req.fullSummary}
                            </p>
                          </div>

                          {/* View latest update toggle */}
                          <button
                            onClick={() => setShowAiResponseId(showAi ? null : req.id)}
                            className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider hover:text-foreground transition-colors w-full"
                          >
                            {showAi ? (
                              <ChevronUp className="h-3.5 w-3.5" />
                            ) : (
                              <ChevronDown className="h-3.5 w-3.5" />
                            )}
                            View Latest Update
                          </button>

                          {showAi && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: "auto", opacity: 1 }}
                              transition={{ duration: 0.15 }}
                              className="overflow-hidden"
                            >
                              <div className="border rounded-lg p-3 bg-muted/30">
                                <div className="flex items-center gap-1.5 mb-2">
                                  <MessageSquare className="h-3.5 w-3.5 text-primary" />
                                  <span className="text-[10px] font-semibold text-primary uppercase tracking-wider">
                                    Latest Update
                                  </span>
                                </div>
                                <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap">
                                  {req.aiResponse.replace(/\*\*/g, "")}
                                </p>
                              </div>
                            </motion.div>
                          )}

                          {!canWorkOnRequests && req.status !== "resolved" && (
                            <div className="space-y-2">
                              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                                Reply to HR
                              </p>
                              <Textarea
                                value={replyDraftById[req.id] || ""}
                                onChange={(e) =>
                                  setReplyDraftById((prev) => ({
                                    ...prev,
                                    [req.id]: e.target.value,
                                  }))
                                }
                                placeholder="Add clarification for HR..."
                                className="min-h-[80px] text-sm"
                              />
                              <Button
                                size="sm"
                                variant="outline"
                                className="w-full"
                                disabled={
                                  replyingId === req.id ||
                                  !(replyDraftById[req.id] || "").trim()
                                }
                                onClick={() => void handleReply(req.id)}
                              >
                                {replyingId === req.id ? "Sending..." : "Send reply"}
                              </Button>
                            </div>
                          )}

                          {/* Audit Log */}
                          <div>
                            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                              Audit Log
                            </p>
                            <div className="space-y-0">
                              {(req.auditLog ?? []).map((event, idx) => (
                                <div key={idx} className="flex items-start gap-2.5 relative">
                                  {/* Timeline connector */}
                                  {idx < req.auditLog.length - 1 && (
                                    <div className="absolute left-[7px] top-5 bottom-0 w-px bg-border" />
                                  )}
                                  <MessageSquare className="h-3.5 w-3.5 text-muted-foreground mt-0.5 flex-shrink-0 relative z-10" />
                                  <div className="pb-3">
                                    <p className="text-sm text-foreground">{event.label}</p>
                                    <p className="text-xs text-muted-foreground">{formatDate(event.timestamp)}</p>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>

                          {/* Action buttons based on status */}
                          <div className="pt-1">
                            {canWorkOnRequests && (req.status === "pending" || req.status === "assigned" || req.status === "in_progress") && (
                              <Button
                                size="sm"
                                className="w-full gap-2 text-xs"
                                onClick={() => handleWorkOn(req.id)}
                              >
                                <ArrowRight className="h-3.5 w-3.5" />
                                {req.status === "in_progress" ? "Continue working" : "Work on this"}
                              </Button>
                            )}
                            {!canWorkOnRequests && (req.status === "pending" || req.status === "assigned" || req.status === "in_progress") && (
                              <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 rounded-lg border text-xs text-muted-foreground">
                                <Timer className="h-3.5 w-3.5" />
                                Awaiting HR review
                              </div>
                            )}
                            {req.status === "in_review" && (
                              <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 rounded-lg border text-xs text-muted-foreground">
                                <Timer className="h-3.5 w-3.5" />
                                Waiting for employee confirmation · SLA active
                              </div>
                            )}
                            {req.status === "resolved" && (
                              <div className="flex items-center gap-2 px-3 py-2 bg-success/5 rounded-lg border border-success/20 text-xs text-success">
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                Resolved
                              </div>
                            )}
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
