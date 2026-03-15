import { useState, useRef, useEffect, useCallback } from "react";
import { Navigate } from "react-router-dom";
import { Loader2, ArrowUp, Sparkles, Mail, Bot } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import ConversationSidebar, { type Conversation } from "@/components/ConversationSidebar";
import MyRequestsPanel, { type EscalatedRequest } from "@/components/MyRequestsPanel";
import ChatMessageBubble from "@/components/ChatMessageBubble";
import CategoryCards from "@/components/CategoryCards";
import { useAuth } from "@/contexts/AuthContext";
import {
  createHRRequest,
  deleteSession,
  createSession,
  fetchHRRequests,
  fetchSessionTurns,
  fetchSessions,
  replyToHRRequestAsRequester,
  sendChat,
  type BackendHRRequest,
  type BackendSessionTurn,
} from "@/lib/backend";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  confidence?: "high" | "low";
  escalated?: boolean;
}

function mapTurnsToMessages(turns: BackendSessionTurn[]): Message[] {
  const mapped: Message[] = [];
  turns.forEach((turn, idx) => {
    const ts = new Date(turn.timestamp);
    const turnTime = Number.isNaN(ts.getTime()) ? new Date() : ts;
    mapped.push({
      id: `turn-${idx}-user`,
      role: "user",
      content: turn.query,
      timestamp: turnTime,
    });
    mapped.push({
      id: `turn-${idx}-assistant`,
      role: "assistant",
      content: turn.response,
      timestamp: turnTime,
      confidence: "high",
    });
  });
  return mapped;
}

const NEW_CONVERSATION_LABEL = "New conversation";
const DRAFT_CONVERSATION_ID = "__draft__";

function buildConversationTitleFromMessage(text: string): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) return NEW_CONVERSATION_LABEL;
  return cleaned.length > 48 ? `${cleaned.slice(0, 48)}...` : cleaned;
}

function isGenericConversationTitle(preview: string): boolean {
  return preview === NEW_CONVERSATION_LABEL || preview.startsWith("Session ");
}

function conversationTitlesStorageKey(userEmail: string): string {
  return `pinghr:conversation-titles:${userEmail.toLowerCase()}`;
}

function loadConversationTitles(userEmail: string): Record<string, string> {
  try {
    const raw = localStorage.getItem(conversationTitlesStorageKey(userEmail));
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, string>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveConversationTitles(userEmail: string, titles: Record<string, string>): void {
  try {
    localStorage.setItem(conversationTitlesStorageKey(userEmail), JSON.stringify(titles));
  } catch {
    // Ignore storage errors and keep UI usable.
  }
}

function saveConversationTitleIfMissing(userEmail: string, conversationId: string, title: string): void {
  const normalized = title.trim();
  if (!normalized || normalized === NEW_CONVERSATION_LABEL) return;
  const titles = loadConversationTitles(userEmail);
  if (titles[conversationId]) return;
  titles[conversationId] = normalized;
  saveConversationTitles(userEmail, titles);
}

function removeConversationTitle(userEmail: string, conversationId: string): void {
  const titles = loadConversationTitles(userEmail);
  if (!(conversationId in titles)) return;
  delete titles[conversationId];
  saveConversationTitles(userEmail, titles);
}

function clearConversationTitles(userEmail: string): void {
  try {
    localStorage.removeItem(conversationTitlesStorageKey(userEmail));
  } catch {
    // Ignore storage errors and keep UI usable.
  }
}

function removeConversationTitles(userEmail: string, conversationIds: string[]): void {
  if (conversationIds.length === 0) return;
  const titles = loadConversationTitles(userEmail);
  let changed = false;
  for (const id of conversationIds) {
    if (id in titles) {
      delete titles[id];
      changed = true;
    }
  }
  if (changed) {
    saveConversationTitles(userEmail, titles);
  }
}

function requestViewsStorageKey(userEmail: string): string {
  return `pinghr:request-views:${userEmail.toLowerCase()}`;
}

function loadRequestViews(userEmail: string): Record<string, number> {
  try {
    const raw = localStorage.getItem(requestViewsStorageKey(userEmail));
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

function saveRequestViews(
  userEmail: string,
  viewsByRequestId: Record<string, number>
): void {
  try {
    localStorage.setItem(
      requestViewsStorageKey(userEmail),
      JSON.stringify(viewsByRequestId)
    );
  } catch {
    // Ignore storage errors and keep UI usable.
  }
}

function detectCategory(text: string): string {
  const lower = text.toLowerCase();
  if (
    lower.includes("leave") ||
    lower.includes("pto") ||
    lower.includes("vacation") ||
    lower.includes("time off")
  )
    return "Leave & Time Off";
  if (lower.includes("pay") || lower.includes("salary") || lower.includes("payroll"))
    return "Payroll & Pay";
  if (
    lower.includes("benefit") ||
    lower.includes("insurance") ||
    lower.includes("health") ||
    lower.includes("enrollment")
  )
    return "Benefits";
  if (lower.includes("expense") || lower.includes("reimburs")) return "Expenses";
  if (
    lower.includes("wfh") ||
    lower.includes("remote") ||
    lower.includes("work from home")
  )
    return "Company Policy";
  return "General";
}

function toRequestStatus(
  status: BackendHRRequest["status"],
  assigneeUserId?: string | null
): "pending" | "assigned" | "in_progress" | "in_review" | "resolved" {
  if (status === "RESOLVED" || status === "CANCELLED") return "resolved";
  if (status === "NEEDS_INFO") return "in_review";
  if (status === "IN_PROGRESS" || status === "ESCALATED") return "in_progress";
  if (assigneeUserId) return "assigned";
  return "pending";
}

function mapHRRequestToPanelRequest(item: BackendHRRequest): EscalatedRequest {
  const createdAt = new Date(item.created_at);
  const updatedAt = new Date(item.updated_at);
  const lastMessageAt = item.last_message_at ? new Date(item.last_message_at) : null;
  const hasHrMessage =
    typeof item.last_message_to_requester === "string" &&
    item.last_message_to_requester.trim().length > 0;
  const latestUpdate =
    item.last_message_to_requester ||
    item.resolution_text ||
    (typeof item.captured_fields?.agent_suggestion === "string"
      ? item.captured_fields.agent_suggestion
      : null) ||
    "Your request has been logged for HR follow-up.";
  const mappedPriority = item.priority === "P0" ? "critical" : item.priority === "P1" ? "high" : "medium";

  const auditLog: { label: string; timestamp: Date }[] = [
    { label: "Request created", timestamp: createdAt },
  ];
  if (hasHrMessage && lastMessageAt && !Number.isNaN(lastMessageAt.getTime())) {
    auditLog.push({
      label: "HR sent a clarifying question",
      timestamp: lastMessageAt,
    });
  }
  auditLog.push({
    label: item.status === "RESOLVED" ? "Marked resolved by HR" : "Latest status update",
    timestamp: updatedAt,
  });

  return {
    id: String(item.request_id),
    summary: item.summary.length > 60 ? `${item.summary.slice(0, 60)}...` : item.summary,
    fullSummary: item.description,
    aiResponse: latestUpdate,
    status: toRequestStatus(item.status, item.assignee_user_id),
    priority: mappedPriority,
    category: `${item.type} / ${item.subtype}`,
    timestamp: createdAt,
    lastUpdatedAt: updatedAt,
    auditLog,
  };
}

function requestUpdateTimestampMs(request: EscalatedRequest): number {
  const timestamp = (request.lastUpdatedAt || request.timestamp).getTime();
  return Number.isFinite(timestamp) ? timestamp : 0;
}

export default function ChatPage() {
  const { user, session } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationMessages, setConversationMessages] = useState<
    Record<string, Message[]>
  >({});
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [requestsOpen, setRequestsOpen] = useState(false);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [escalatedRequests, setEscalatedRequests] = useState<EscalatedRequest[]>([]);
  const [viewedRequestById, setViewedRequestById] = useState<
    Record<string, number>
  >({});
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const activeConversationRef = useRef<string | null>(null);

  const displayName = user?.email?.split("@")[0] ?? "there";
  const capitalizedName = displayName.charAt(0).toUpperCase() + displayName.slice(1);

  const loadEscalatedRequests = useCallback(async () => {
    if (!user?.email) return;
    const requests = await fetchHRRequests(user.email);
    setEscalatedRequests(
      requests
        .map(mapHRRequestToPanelRequest)
        .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
    );
  }, [user?.email]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    activeConversationRef.current = activeConversation;
  }, [activeConversation]);

  useEffect(() => {
    if (!user?.email) return;
    let cancelled = false;

    const loadData = async () => {
      try {
        const storedTitles = loadConversationTitles(user.email);
        const sessions = await fetchSessions(user.email);

        if (cancelled) return;

        const loadedConversations = sessions
          .filter((session) => session.turn_count > 0)
          .map((session) => ({
            id: session.session_id,
            preview:
              storedTitles[session.session_id] ||
              session.title ||
              (session.turn_count > 0
                ? `Conversation ${new Date(session.created_at).toLocaleDateString()}`
                : NEW_CONVERSATION_LABEL),
            timestamp: new Date(session.created_at),
          }))
          .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());

        setConversations((prev) => {
          const draftConversation = prev.find(
            (conversation) => conversation.id === DRAFT_CONVERSATION_ID
          );
          if (!draftConversation) {
            return loadedConversations;
          }
          return [
            draftConversation,
            ...loadedConversations.filter(
              (conversation) => conversation.id !== DRAFT_CONVERSATION_ID
            ),
          ];
        });

        await loadEscalatedRequests();
      } catch (error) {
        console.error("Failed to load chat data:", error);
      }
    };

    void loadData();
    return () => {
      cancelled = true;
    };
  }, [user?.email, loadEscalatedRequests]);

  useEffect(() => {
    if (!user?.email) {
      setViewedRequestById({});
      return;
    }
    setViewedRequestById(loadRequestViews(user.email));
  }, [user?.email]);

  const markRequestViewed = useCallback(
    (request: EscalatedRequest) => {
      const userEmail = user?.email;
      if (!userEmail) return;
      const viewedAt = requestUpdateTimestampMs(request);
      if (viewedAt <= 0) return;

      setViewedRequestById((prev) => {
        if ((prev[request.id] ?? 0) >= viewedAt) return prev;
        const next = { ...prev, [request.id]: viewedAt };
        saveRequestViews(userEmail, next);
        return next;
      });
    },
    [user?.email]
  );

  useEffect(() => {
    if (!user?.email || !requestsOpen) return;
    let stopped = false;

    const refresh = async () => {
      if (document.visibilityState !== "visible") return;
      try {
        await loadEscalatedRequests();
      } catch {
        // Keep UI usable if refresh fails transiently.
      }
    };

    void refresh();
    const interval = window.setInterval(() => {
      if (!stopped) void refresh();
    }, 20000);

    return () => {
      stopped = true;
      window.clearInterval(interval);
    };
  }, [user?.email, loadEscalatedRequests, requestsOpen]);

  if (!session || !user) {
    return <Navigate to="/auth" replace />;
  }

  const unreadRequestCount = escalatedRequests.reduce((count, request) => {
    const viewedAt = viewedRequestById[request.id] ?? 0;
    return requestUpdateTimestampMs(request) > viewedAt ? count + 1 : count;
  }, 0);

  const handleRequestViewed = (request: EscalatedRequest) => {
    markRequestViewed(request);
  };

  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || isTyping || !user?.email) return;

    let convId = activeConversation;
    const usingDraftConversation = convId === DRAFT_CONVERSATION_ID;
    if (!convId || usingDraftConversation) {
      try {
        const sessionInfo = await createSession(user.email);
        convId = sessionInfo.session_id;
        const preview = buildConversationTitleFromMessage(msg);
        saveConversationTitleIfMissing(user.email, convId, preview);
        setConversations((prev) => {
          const withoutDraft = prev.filter((item) => item.id !== DRAFT_CONVERSATION_ID);
          const withoutDuplicate = withoutDraft.filter((item) => item.id !== convId);
          return [
            { id: convId!, preview, timestamp: new Date(sessionInfo.created_at) },
            ...withoutDuplicate,
          ];
        });
        setConversationMessages((prev) => {
          const next = { ...prev };
          if (usingDraftConversation) {
            delete next[DRAFT_CONVERSATION_ID];
          }
          return next;
        });
        setActiveConversation(convId);
      } catch (error: any) {
        toast.error(error?.message || "Failed to create session");
        return;
      }
    }

    const generatedTitle = buildConversationTitleFromMessage(msg);
    saveConversationTitleIfMissing(user.email, convId, generatedTitle);
    setConversations((prev) =>
      prev.map((conv) =>
        conv.id === convId && isGenericConversationTitle(conv.preview)
          ? { ...conv, preview: generatedTitle }
          : conv
      )
    );

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: msg,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setConversationMessages((prev) => ({
      ...prev,
      [convId!]: [...(prev[convId!] || []), userMsg],
    }));
    setInput("");
    setIsTyping(true);

    try {
      const response = await sendChat(user.email, msg, convId);
      const assistantMessage: Message = {
        id: `${Date.now()}-assistant`,
        role: "assistant",
        content: response.response,
        timestamp: new Date(response.timestamp),
        confidence: "high",
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setConversationMessages((prev) => ({
        ...prev,
        [convId!]: [...(prev[convId!] || []), assistantMessage],
      }));
    } catch (error: any) {
      const errMessage = error?.message || "Failed to fetch response";
      toast.error(errMessage);
      setMessages((prev) => [
        ...prev,
        {
          id: `${Date.now()}-error`,
          role: "assistant",
          content: `Sorry, I hit an error: ${errMessage}`,
          timestamp: new Date(),
          confidence: "low",
          escalated: false,
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleSelectConversation = (id: string) => {
    if (activeConversation && messages.length > 0) {
      setConversationMessages((prev) => ({
        ...prev,
        [activeConversation]: messages,
      }));
    }

    const existing = conversationMessages[id];
    setActiveConversation(id);
    if (existing) {
      setMessages(existing);
      return;
    }

    setMessages([]);
    if (!user?.email) return;

    void (async () => {
      try {
        const turns = await fetchSessionTurns(user.email, id);
        const loaded = mapTurnsToMessages(turns);
        setConversationMessages((prev) => ({ ...prev, [id]: loaded }));
        if (activeConversationRef.current === id) {
          setMessages(loaded);
        }
      } catch (error: any) {
        toast.error(error?.message || "Failed to load conversation history");
      }
    })();
  };

  const handleNewConversation = () => {
    if (activeConversation && messages.length > 0) {
      setConversationMessages((prev) => ({
        ...prev,
        [activeConversation]: messages,
      }));
    }
    setConversations((prev) => [
      {
        id: DRAFT_CONVERSATION_ID,
        preview: NEW_CONVERSATION_LABEL,
        timestamp: new Date(),
      },
      ...prev.filter((item) => item.id !== DRAFT_CONVERSATION_ID),
    ]);
    setConversationMessages((prev) => ({ ...prev, [DRAFT_CONVERSATION_ID]: [] }));
    setMessages([]);
    setInput("");
    setActiveConversation(DRAFT_CONVERSATION_ID);
  };

  const handleDeleteConversation = async (id: string) => {
    if (id === DRAFT_CONVERSATION_ID) {
      setConversations((prev) => prev.filter((c) => c.id !== id));
      setConversationMessages((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      if (activeConversation === id) {
        setMessages([]);
        setActiveConversation(null);
      }
      return;
    }
    if (!user?.email) return;

    try {
      await deleteSession(user.email, id);
    } catch (error: any) {
      toast.error(error?.message || "Failed to delete conversation");
      return;
    }

    removeConversationTitle(user.email, id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    setConversationMessages((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    if (activeConversation === id) {
      setMessages([]);
      setActiveConversation(null);
    }
  };

  const handleClearAll = async () => {
    if (!user?.email) return;
    const userEmail = user.email;

    const ids = conversations
      .filter((conversation) => conversation.id !== DRAFT_CONVERSATION_ID)
      .map((conversation) => conversation.id);
    if (ids.length === 0) {
      clearConversationTitles(userEmail);
      setConversations([]);
      setConversationMessages({});
      setMessages([]);
      setActiveConversation(null);
      return;
    }

    const results = await Promise.allSettled(ids.map((id) => deleteSession(userEmail, id)));
    const failedIds = results
      .map((result, idx) => (result.status === "rejected" ? ids[idx] : null))
      .filter((id): id is string => id !== null);
    const deletedIds = ids.filter((id) => !failedIds.includes(id));

    if (failedIds.length === 0) {
      clearConversationTitles(userEmail);
      setConversations([]);
      setConversationMessages({});
      setMessages([]);
      setActiveConversation(null);
      toast.success("All conversations cleared");
      return;
    }

    removeConversationTitles(userEmail, deletedIds);
    const failedSet = new Set(failedIds);

    setConversations((prev) => prev.filter((conversation) => failedSet.has(conversation.id)));
    setConversationMessages((prev) => {
      const next: Record<string, Message[]> = {};
      for (const id of failedIds) {
        if (prev[id]) {
          next[id] = prev[id];
        }
      }
      return next;
    });

    if (!activeConversation || !failedSet.has(activeConversation)) {
      setMessages([]);
      setActiveConversation(null);
    }

    toast.error(
      `${failedIds.length} conversation${failedIds.length === 1 ? "" : "s"} could not be deleted`
    );
  };

  const handleEscalate = async (msg: Message) => {
    if (!user?.email) return;
    const msgIdx = messages.findIndex((item) => item.id === msg.id);
    const userMsg = [...messages]
      .slice(0, msgIdx >= 0 ? msgIdx : messages.length)
      .reverse()
      .find((m) => m.role === "user");
    const queryText = userMsg?.content ?? msg.content;

    try {
      const threadId = activeConversation || `manual-${Date.now()}`;
      const detectedCategory = detectCategory(queryText);
      const normalizedSubtype =
        detectedCategory
          .toUpperCase()
          .replace(/[^A-Z0-9]+/g, "_")
          .replace(/^_+|_+$/g, "") || "GENERAL";
      const result = await createHRRequest(user.email, {
        type: "ESCALATION",
        subtype: normalizedSubtype,
        summary: queryText.slice(0, 500),
        description: queryText.slice(0, 5000),
        priority: "P1",
        risk_level: "MED",
        required_fields: [
          "summary",
          "description",
          "requester_user_id",
          "type",
          "subtype",
          "agent_suggestion",
        ],
        captured_fields: {
          thread_id: threadId,
          category: detectedCategory,
          agent_suggestion: msg.content.slice(0, 3500),
        },
      });
      if (!result.success) {
        throw new Error(result.error || "Request creation failed");
      }

      await loadEscalatedRequests();
      toast.success(`Escalated to HR Ops (#${result.request_id ?? "new"})`);
    } catch (error: any) {
      toast.error(error?.message || "Failed to escalate");
    }
  };

  const handleRequesterReply = async (requestId: string, message: string) => {
    if (!user?.email) return;
    const parsedRequestId = Number(requestId);
    if (!Number.isFinite(parsedRequestId)) {
      toast.error("Invalid request id");
      return;
    }

    try {
      await replyToHRRequestAsRequester(user.email, parsedRequestId, message);
      await loadEscalatedRequests();
      toast.success("Reply sent to HR");
    } catch (error: any) {
      toast.error(error?.message || "Failed to send reply");
      throw error;
    }
  };

  const showWelcome = messages.length === 0;

  return (
    <div className="min-h-screen flex w-full">
      <ConversationSidebar
        activeConversationId={activeConversation}
        conversations={conversations}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
        onClearAll={handleClearAll}
      />

      <main className="flex-1 flex flex-col min-w-0 h-screen">
        <header className="flex items-center justify-between px-6 py-3 border-b bg-card">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-base text-primary">PingHR</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="gap-2 text-primary border-primary/30 hover:bg-primary/5"
            onClick={() => setRequestsOpen(true)}
          >
            <Mail className="h-4 w-4" />
            My Requests
            {unreadRequestCount > 0 && (
              <span className="ml-1 h-5 min-w-5 px-1 rounded-full bg-destructive text-destructive-foreground text-[10px] font-bold flex items-center justify-center">
                {unreadRequestCount}
              </span>
            )}
          </Button>
        </header>

        <div className="flex-1 overflow-y-auto">
          {showWelcome ? (
            <div className="flex flex-col items-center justify-center px-6 py-6 max-w-3xl mx-auto h-full">
              <div className="flex-1 min-h-0" />
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-primary/20 bg-primary/5 text-primary text-xs font-medium mb-4">
                <Sparkles className="h-3.5 w-3.5" />
                Your HR assistant · Acme Corp
              </div>
              <h1 className="text-2xl md:text-3xl font-bold mb-2 text-center">
                Hi {capitalizedName}, what can I help with?
              </h1>
              <p className="text-muted-foreground text-center mb-1 max-w-lg text-sm">
                Ask me anything about Acme's HR policies — leave, payroll, benefits,
                and more.
              </p>
              <p className="text-xs text-muted-foreground text-center mb-6">
                Sensitive queries are securely escalated to HR Ops.
              </p>
              <CategoryCards onSelectCategory={handleSend} />
              <div className="flex-1 min-h-0" />
            </div>
          ) : (
            <div className="max-w-3xl mx-auto px-6 py-6 space-y-4">
              {messages.map((msg) => (
                <ChatMessageBubble key={msg.id} msg={msg} onEscalate={handleEscalate} />
              ))}

              {isTyping && (
                <div className="flex gap-3">
                  <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                  <div className="bg-muted rounded-xl px-4 py-3">
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="border-t px-6 py-4 max-w-3xl mx-auto w-full">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void handleSend();
            }}
            className="relative"
          >
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything about HR, leave, payroll, benefits..."
              className="w-full rounded-xl border bg-background px-4 py-3.5 pr-12 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/20"
            />
            <Button
              type="submit"
              size="icon"
              disabled={!input.trim() || isTyping}
              className="absolute right-2 top-1/2 -translate-y-1/2 h-8 w-8 rounded-lg"
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          </form>
          <p className="text-center text-xs text-muted-foreground mt-2">
            Confident answers are grounded in policy. Low-confidence queries go to
            HR Ops.
          </p>
        </div>
      </main>

      <MyRequestsPanel
        isOpen={requestsOpen}
        onClose={() => setRequestsOpen(false)}
        requests={escalatedRequests}
        onReplyToRequest={handleRequesterReply}
        onRequestViewed={handleRequestViewed}
      />
    </div>
  );
}
