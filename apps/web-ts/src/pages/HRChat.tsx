import { useState, useRef, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { Loader2, ArrowUp, Sparkles, Mail, Bot, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import HRConversationSidebar from "@/components/HRConversationSidebar";
import MyRequestsPanel, { type EscalatedRequest } from "@/components/MyRequestsPanel";
import ChatMessageBubble from "@/components/ChatMessageBubble";
import HRCategoryCards from "@/components/HRCategoryCards";
import TicketActionBar from "@/components/TicketActionBar";
import { useAuth } from "@/contexts/AuthContext";
import { useHRTickets } from "@/contexts/HRTicketsContext";
import type { ResolutionTag } from "@/contexts/HRTicketsContext";
import { mockEmployees } from "@/data/mockEmployees";
import {
  createHRRequest,
  createSession,
  deleteSession,
  fetchHRRequestDetail,
  fetchHRRequests,
  fetchSessions,
  fetchSessionTurns,
  sendChat,
  type BackendHRRequest,
  type BackendSessionTurn,
} from "@/lib/backend";
import { getErrorMessage } from "@/lib/error";
import { mapHRRequestToPanel } from "@/lib/hrRequestPanel";
import { toast } from "sonner";
import type { Conversation } from "@/components/ConversationSidebar";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  confidence?: "high" | "low";
  escalated?: boolean;
}

const NEW_CONVERSATION_LABEL = "New conversation";
const DRAFT_CONVERSATION_ID = "__draft__";

function buildConversationPreview(text: string): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) return NEW_CONVERSATION_LABEL;
  return cleaned.length > 40 ? `${cleaned.slice(0, 40)}...` : cleaned;
}

function mapTurnsToMessages(turns: BackendSessionTurn[]): Message[] {
  const mapped: Message[] = [];
  turns.forEach((turn, idx) => {
    const turnTs = new Date(turn.timestamp);
    const timestamp = Number.isNaN(turnTs.getTime()) ? new Date() : turnTs;
    mapped.push({
      id: `turn-${idx}-user`,
      role: "user",
      content: turn.query,
      timestamp,
    });
    mapped.push({
      id: `turn-${idx}-assistant`,
      role: "assistant",
      content: turn.response,
      timestamp,
      confidence: "high",
    });
  });
  return mapped;
}

function conversationTitlesStorageKey(userEmail: string): string {
  return `pinghr:hr-conversation-titles:${userEmail.toLowerCase()}`;
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
    // Ignore storage failures and keep UI usable.
  }
}

function saveConversationTitleIfMissing(
  userEmail: string,
  conversationId: string,
  title: string
): void {
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
    // Ignore storage failures and keep UI usable.
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

async function streamChat({
  messages,
  userEmail,
  sessionId,
  onDelta,
  onDone,
}: {
  messages: { role: string; content: string }[];
  userEmail: string;
  sessionId?: string;
  onDelta: (text: string) => void;
  onDone: () => void;
}) {
  const latestUserMessage =
    [...messages].reverse().find((message) => message.role === "user")?.content || "";
  if (!latestUserMessage) {
    onDone();
    return;
  }

  try {
    const response = await sendChat(userEmail, latestUserMessage, sessionId);
    onDelta(response.response);
  } catch (error) {
    toast.error(getErrorMessage(error, "Chat request failed"));
    throw error;
  } finally {
    onDone();
  }
}

function buildTicketContextPrompt(ticket: {
  employee: string;
  question: string;
  category: string;
  priority: string;
  aiDraft: string;
}): string {
  const emp = mockEmployees.find((e) => e.name === ticket.employee);
  const empInfo = emp
    ? `\n**Employee Profile:** ${emp.name} · ${emp.role} · ${emp.department} · ${emp.location} · Tenure: ${emp.tenure} · Manager: ${emp.manager}`
    : "";

  return `I'm working on an escalated HR request. Here are the details:

**Employee:** ${ticket.employee}${empInfo}
**Category:** ${ticket.category}
**Priority:** ${ticket.priority.toUpperCase()}
**Employee's Question:** "${ticket.question}"

**AI's Draft Response:**
${ticket.aiDraft}

Help me review this case. Is the AI draft accurate? Are there any policy nuances I should consider? What's the best way to handle this?`;
}

function pickCapturedString(
  request: BackendHRRequest,
  key: string
): string | null {
  const value = request.captured_fields?.[key];
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

function buildHRRequestContextPrompt(request: BackendHRRequest): string {
  const requester = request.requester_name || request.requester_user_id || "Employee";
  const originalQuery =
    pickCapturedString(request, "original_query") || request.description;
  const assistantSuggestion =
    pickCapturedString(request, "assistant_response") ||
    pickCapturedString(request, "agent_suggestion") ||
    request.resolution_text ||
    request.last_message_to_requester ||
    "";

  return `I'm working on an assigned HR request. Here are the details:

**Request ID:** ${request.request_id}
**Requester:** ${requester}
**Category:** ${request.type} / ${request.subtype}
**Priority:** ${request.priority}
**Status:** ${request.status}
**Requester's Question:** "${originalQuery}"

**Latest AI / Draft Context:**
${assistantSuggestion || "(No draft response available)"}

Help me handle this case. What should I do next, and what response should I send to the requester?`;
}

export default function HRChat() {
  const { user } = useAuth();
  const { getTicketById, addResolutionNote, updateTicketStatus } = useHRTickets();
  const [searchParams, setSearchParams] = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationMessages, setConversationMessages] = useState<Record<string, Message[]>>({});
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [requestsOpen, setRequestsOpen] = useState(false);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeTicketId, setActiveTicketId] = useState<string | null>(null);
  const [activeRequestId, setActiveRequestId] = useState<number | null>(null);
  const [assignedRequests, setAssignedRequests] = useState<EscalatedRequest[]>([]);
  const [processedTickets, setProcessedTickets] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const activeConversationRef = useRef<string | null>(null);

  const displayName = user?.email?.split("@")[0] ?? "HR User";
  const capitalizedName = displayName.charAt(0).toUpperCase() + displayName.slice(1);

  const loadAssignedRequests = useCallback(async () => {
    if (!user?.email) return;
    const rows = await fetchHRRequests(user.email);
    const assignedRows = rows.filter(
      (item) => (item.assignee_user_id || "").toLowerCase() === user.email.toLowerCase()
    );
    setAssignedRequests(
      assignedRows
        .map((request) =>
          mapHRRequestToPanel(request, {
            latestUpdateFallback: "No latest update has been recorded yet.",
            hrMessageLabel: "Requested additional info from requester",
            includeRequesterInSummary: true,
          })
        )
        .sort(
          (a, b) =>
            (b.lastUpdatedAt || b.timestamp).getTime() -
            (a.lastUpdatedAt || a.timestamp).getTime()
        )
    );
  }, [user?.email]);

  const openDraftConversation = useCallback(() => {
    if (activeConversation && messages.length > 0) {
      setConversationMessages((cm) => ({ ...cm, [activeConversation]: messages }));
    }
    setConversations((prev) => [
      { id: DRAFT_CONVERSATION_ID, preview: NEW_CONVERSATION_LABEL, timestamp: new Date() },
      ...prev.filter((item) => item.id !== DRAFT_CONVERSATION_ID),
    ]);
    setConversationMessages((cm) => ({ ...cm, [DRAFT_CONVERSATION_ID]: [] }));
    setMessages([]);
    setActiveConversation(DRAFT_CONVERSATION_ID);
    setActiveTicketId(null);
    setActiveRequestId(null);
    setInput("");
  }, [activeConversation, messages]);

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
        await loadAssignedRequests();
      } catch (error: unknown) {
        toast.error(getErrorMessage(error, "Failed to load HR conversations"));
      }
    };

    void loadData();
    return () => {
      cancelled = true;
    };
  }, [user?.email, loadAssignedRequests]);

  useEffect(() => {
    if (!user?.email || !requestsOpen) return;
    let stopped = false;

    const refresh = async () => {
      if (document.visibilityState !== "visible") return;
      try {
        await loadAssignedRequests();
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
  }, [user?.email, requestsOpen, loadAssignedRequests]);

  useEffect(() => {
    const sessionId = searchParams.get("session");
    if (!sessionId || !user?.email) return;

    setActiveTicketId(null);
    setActiveRequestId(null);

    if (activeConversation && messages.length > 0) {
      setConversationMessages((cm) => ({ ...cm, [activeConversation]: messages }));
    }
    setActiveConversation(sessionId);

    const existing = conversationMessages[sessionId];
    if (existing) {
      setMessages(existing);
    } else {
      setMessages([]);
      void (async () => {
        try {
          const turns = await fetchSessionTurns(user.email, sessionId);
          const loaded = mapTurnsToMessages(turns);
          setConversationMessages((cm) => ({ ...cm, [sessionId]: loaded }));
          if (activeConversationRef.current === sessionId) {
            setMessages(loaded);
          }
        } catch (error: unknown) {
          toast.error(getErrorMessage(error, "Failed to load conversation history"));
        }
      })();
    }

    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("session");
    setSearchParams(nextParams, { replace: true });
  }, [activeConversation, conversationMessages, messages, searchParams, setSearchParams, user?.email]);

  useEffect(() => {
    const shouldOpenNewConversation = searchParams.get("new") === "1";
    const ticketId = searchParams.get("ticket");
    const sessionId = searchParams.get("session");
    if (!shouldOpenNewConversation || ticketId || sessionId) return;

    openDraftConversation();
    setActiveTicketId(null);
    setActiveRequestId(null);
    setSearchParams({}, { replace: true });
  }, [openDraftConversation, searchParams, setSearchParams]);

  // Handle deep-link from HR Ops with ?ticket=ID
  useEffect(() => {
    const ticketId = searchParams.get("ticket");
    const sessionId = searchParams.get("session");
    if (!ticketId || sessionId || processedTickets.has(ticketId) || !user?.email) return;
    setProcessedTickets((prev) => new Set(prev).add(ticketId));
    // Clear the param so refreshing doesn't re-inject
    setSearchParams({}, { replace: true });

    const parsedRequestId = Number(ticketId);
    if (Number.isFinite(parsedRequestId)) {
      void (async () => {
        try {
          const detail = await fetchHRRequestDetail(user.email, parsedRequestId);
          setActiveRequestId(parsedRequestId);
          setActiveTicketId(null);
          const contextPrompt = buildHRRequestContextPrompt(detail.request);
          setTimeout(() => {
            void handleSendWithContext(contextPrompt, `request-${parsedRequestId}`);
          }, 300);
          await loadAssignedRequests();
          return;
        } catch {
          // Fall back to legacy local ticket flow below.
        }

        const ticket = getTicketById(ticketId);
        if (ticket) {
          setActiveTicketId(ticketId);
          setActiveRequestId(null);
          const contextPrompt = buildTicketContextPrompt(ticket);
          setTimeout(() => {
            void handleSendWithContext(contextPrompt, `ticket-${ticketId}`);
          }, 300);
          return;
        }

        toast.error(`Request #${ticketId} was not found or is not assigned to you.`);
      })();
      return;
    }

    const ticket = getTicketById(ticketId);
    if (ticket) {
      setActiveTicketId(ticketId);
      setActiveRequestId(null);
      const contextPrompt = buildTicketContextPrompt(ticket);
      setTimeout(() => {
        void handleSendWithContext(contextPrompt, `ticket-${ticketId}`);
      }, 300);
    }
    // handleSendWithContext is intentionally excluded here because this deep-link
    // effect should only react to route/state changes, not callback identity changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, processedTickets, getTicketById, loadAssignedRequests, setSearchParams, user?.email]);

  // Helper to update messages and sync to conversationMessages
  const updateMessages = useCallback((convId: string | null, updater: (prev: Message[]) => Message[]) => {
    setMessages((prev) => {
      const next = updater(prev);
      if (convId) {
        setConversationMessages((cm) => ({ ...cm, [convId]: next }));
      }
      return next;
    });
  }, []);

  const handleSendWithContext = useCallback(async (text: string, convIdOverride?: string) => {
    const msg = text.trim();
    if (!msg || !user?.email) return;

    let convId = convIdOverride || activeConversation;
    const usingDraftConversation = !convIdOverride && convId === DRAFT_CONVERSATION_ID;
    if (!convId || usingDraftConversation) {
      try {
        const sessionInfo = await createSession(user.email);
        convId = sessionInfo.session_id;
      } catch (error: unknown) {
        toast.error(getErrorMessage(error, "Failed to create conversation"));
        return;
      }
    }

    const preview = buildConversationPreview(msg);
    const displayPreview = convIdOverride ? `📋 ${preview}` : preview;
    saveConversationTitleIfMissing(user.email, convId, displayPreview);

    // Check if conversation already exists
    setConversations((prev) => {
      const withoutDraft = prev.filter((c) => c.id !== DRAFT_CONVERSATION_ID);
      if (withoutDraft.find((c) => c.id === convId)) {
        return withoutDraft.map((c) =>
          c.id === convId
            ? {
                ...c,
                preview: c.preview === NEW_CONVERSATION_LABEL ? displayPreview : c.preview,
                timestamp: new Date(),
              }
            : c
        );
      }
      return [{ id: convId, preview: displayPreview, timestamp: new Date() }, ...withoutDraft];
    });
    setConversationMessages((cm) => {
      const next = { ...cm, [convId]: cm[convId] || [] };
      if (usingDraftConversation) {
        delete next[DRAFT_CONVERSATION_ID];
      }
      return next;
    });
    setActiveConversation(convId);

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: msg, timestamp: new Date() };
    updateMessages(convId, (prev) => [...prev, userMsg]);
    setIsTyping(true);

    const history = [{ role: "user", content: msg }];

    let assistantContent = "";

    try {
      await streamChat({
        messages: history,
        userEmail: user.email,
        sessionId: convId,
        onDelta: (chunk) => {
          assistantContent += chunk;
          updateMessages(convId, (prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant" && last.id.startsWith("stream-")) {
              return prev.map((m, i) =>
                i === prev.length - 1 ? { ...m, content: assistantContent } : m
              );
            }
            return [
              ...prev,
              {
                id: `stream-${Date.now()}`,
                role: "assistant" as const,
                content: assistantContent,
                timestamp: new Date(),
                confidence: "high" as const,
              },
            ];
          });
        },
        onDone: () => {
          setIsTyping(false);
        },
      });
    } catch (e) {
      console.error("Stream error:", e);
      setIsTyping(false);
      if (!assistantContent) {
        updateMessages(convId, (prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: "assistant",
            content: "Sorry, I encountered an error. Please try again.",
            timestamp: new Date(),
            confidence: "low",
          },
        ]);
      }
    }
  }, [activeConversation, updateMessages, user?.email]);

  const handleSend = useCallback(async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || isTyping || !user?.email) return;

    let convId = activeConversation;
    const usingDraftConversation = convId === DRAFT_CONVERSATION_ID;
    if (!convId || usingDraftConversation) {
      try {
        const sessionInfo = await createSession(user.email);
        convId = sessionInfo.session_id;
      } catch (error: unknown) {
        toast.error(getErrorMessage(error, "Failed to create conversation"));
        return;
      }
      setConversations((prev) => {
        const withoutDraft = prev.filter((item) => item.id !== DRAFT_CONVERSATION_ID);
        const withoutDuplicate = withoutDraft.filter((item) => item.id !== convId);
        return [{ id: convId!, preview: NEW_CONVERSATION_LABEL, timestamp: new Date() }, ...withoutDuplicate];
      });
      setConversationMessages((cm) => {
        const next = { ...cm, [convId!]: cm[convId!] || [] };
        if (usingDraftConversation) {
          delete next[DRAFT_CONVERSATION_ID];
        }
        return next;
      });
      setActiveConversation(convId);
    }
    const preview = buildConversationPreview(msg);
    saveConversationTitleIfMissing(user.email, convId, preview);
    setConversations((prev) =>
      prev.map((c) =>
        c.id === convId
          ? {
              ...c,
              preview: c.preview === NEW_CONVERSATION_LABEL ? preview : c.preview,
              timestamp: new Date(),
            }
          : c
      )
    );

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: msg, timestamp: new Date() };
    updateMessages(convId, (prev) => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);

    // Build conversation history for context
    const history = [...messages, userMsg].map((m) => ({
      role: m.role,
      content: m.content,
    }));

    let assistantContent = "";
    const currentConvId = convId;

    try {
      await streamChat({
        messages: history,
        userEmail: user.email,
        sessionId: currentConvId,
        onDelta: (chunk) => {
          assistantContent += chunk;
          updateMessages(currentConvId, (prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant" && last.id.startsWith("stream-")) {
              return prev.map((m, i) =>
                i === prev.length - 1 ? { ...m, content: assistantContent } : m
              );
            }
            return [
              ...prev,
              {
                id: `stream-${Date.now()}`,
                role: "assistant" as const,
                content: assistantContent,
                timestamp: new Date(),
                confidence: "high" as const,
              },
            ];
          });
        },
        onDone: () => {
          setIsTyping(false);
        },
      });
    } catch (e) {
      console.error("Stream error:", e);
      setIsTyping(false);
      if (!assistantContent) {
        updateMessages(currentConvId, (prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: "assistant",
            content: "Sorry, I encountered an error. Please try again.",
            timestamp: new Date(),
            confidence: "low",
          },
        ]);
      }
    }
  }, [input, isTyping, activeConversation, messages, updateMessages, user?.email]);

  const handleSelectConversation = (id: string) => {
    if (activeConversation && messages.length > 0) {
      setConversationMessages((cm) => ({ ...cm, [activeConversation]: messages }));
    }
    setActiveConversation(id);
    const existing = conversationMessages[id];
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
        setConversationMessages((cm) => ({ ...cm, [id]: loaded }));
        if (activeConversationRef.current === id) {
          setMessages(loaded);
        }
      } catch (error: unknown) {
        toast.error(getErrorMessage(error, "Failed to load conversation history"));
      }
    })();
  };

  const handleNewConversation = () => {
    openDraftConversation();
    setActiveTicketId(null);
    setActiveRequestId(null);
  };

  const handleDeleteConversation = async (id: string) => {
    if (id === DRAFT_CONVERSATION_ID) {
      setConversations((prev) => prev.filter((c) => c.id !== id));
      setConversationMessages((cm) => {
        const next = { ...cm };
        delete next[id];
        return next;
      });
      if (activeConversation === id) {
        setMessages([]);
        setActiveConversation(null);
        setActiveTicketId(null);
        setActiveRequestId(null);
      }
      return;
    }
    if (!user?.email) return;
    try {
      await deleteSession(user.email, id);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to delete conversation"));
      return;
    }

    removeConversationTitle(user.email, id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    setConversationMessages((cm) => {
      const next = { ...cm };
      delete next[id];
      return next;
    });
    if (activeConversation === id) {
      setMessages([]);
      setActiveConversation(null);
      setActiveTicketId(null);
      setActiveRequestId(null);
    }
  };

  const handleClearAll = async () => {
    if (!user?.email) return;
    const ids = conversations
      .filter((conversation) => conversation.id !== DRAFT_CONVERSATION_ID)
      .map((conversation) => conversation.id);
    if (ids.length === 0) {
      clearConversationTitles(user.email);
      setConversations([]);
      setConversationMessages({});
      setMessages([]);
      setActiveConversation(null);
      setActiveTicketId(null);
      setActiveRequestId(null);
      return;
    }

    const results = await Promise.allSettled(ids.map((id) => deleteSession(user.email, id)));
    const failedIds = results
      .map((result, idx) => (result.status === "rejected" ? ids[idx] : null))
      .filter((id): id is string => id !== null);
    const deletedIds = ids.filter((id) => !failedIds.includes(id));

    if (failedIds.length === 0) {
      clearConversationTitles(user.email);
      setConversations([]);
      setConversationMessages({});
      setMessages([]);
      setActiveConversation(null);
      setActiveTicketId(null);
      setActiveRequestId(null);
      toast.success("All conversations cleared");
      return;
    }

    removeConversationTitles(user.email, deletedIds);
    const failedSet = new Set(failedIds);
    setConversations((prev) => prev.filter((conversation) => failedSet.has(conversation.id)));
    setConversationMessages((prev) => {
      const next: Record<string, Message[]> = {};
      for (const id of failedIds) {
        if (prev[id]) next[id] = prev[id];
      }
      return next;
    });
    if (!activeConversation || !failedSet.has(activeConversation)) {
      setMessages([]);
      setActiveConversation(null);
      setActiveTicketId(null);
      setActiveRequestId(null);
    }
    toast.error(
      `${failedIds.length} conversation${failedIds.length === 1 ? "" : "s"} could not be deleted`
    );
  };

  const handleMoveTicketToNext = (note: string, tag: ResolutionTag) => {
    if (!activeTicketId) return;
    const ticket = getTicketById(activeTicketId);
    if (!ticket) return;
    addResolutionNote(activeTicketId, note, tag);
    const nextStatus: Parameters<typeof updateTicketStatus>[1] =
      ticket.status === "in_progress" ? "in_review" : "resolved";
    updateTicketStatus(activeTicketId, nextStatus);
    toast.success(`Ticket moved to ${nextStatus.replace("_", " ")}`);
  };

  const handleEscalate = async (msg: Message): Promise<boolean> => {
    if (!user?.email) return false;

    const msgIdx = messages.findIndex((item) => item.id === msg.id);
    const userMsg = [...messages]
      .slice(0, msgIdx >= 0 ? msgIdx : messages.length)
      .reverse()
      .find((m) => m.role === "user");
    const originalQuery = (userMsg?.content || "").trim();
    const assistantResponse = msg.content.trim();
    if (!assistantResponse) return false;

    const summary = `HR chat quality escalation${
      originalQuery ? `: ${originalQuery.slice(0, 120)}` : ""
    }`;
    const description =
      "HR user flagged chatbot output as irrelevant/unusable and requested manual follow-up.\n\n" +
      (originalQuery ? `Original query:\n${originalQuery}\n\n` : "") +
      `Assistant response:\n${assistantResponse}`;

    try {
      const result = await createHRRequest(user.email, {
        type: "HR",
        subtype: "ESCALATION",
        summary: summary.slice(0, 500),
        description: description.slice(0, 5000),
        priority: "P1",
        risk_level: "MED",
        required_fields: [
          "summary",
          "description",
          "requester_user_id",
          "type",
          "subtype",
          "classification",
          "assistant_response",
        ],
        captured_fields: {
          classification: "INTERNAL_IMPROVEMENT",
          source_channel: "HR_CHAT",
          taxonomy_path: "HR/ESCALATION/INTERNAL_IMPROVEMENT",
          conversation_id: activeConversation,
          original_query: originalQuery || null,
          assistant_response: assistantResponse.slice(0, 3500),
        },
      });
      if (!result.success) {
        throw new Error(result.error || "Escalation request creation failed");
      }
      toast.success(
        `Escalated to HR Ops queue (#${result.request_id ?? "new"})`
      );
      return true;
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to escalate"));
      return false;
    }
  };

  const showWelcome = messages.length === 0 && !isTyping;
  const activeTicket = activeTicketId ? getTicketById(activeTicketId) : null;
  const activeAssignedRequest = activeRequestId
    ? assignedRequests.find((request) => Number(request.id) === activeRequestId) || null
    : null;

  return (
    <div className="min-h-screen flex w-full">
      <HRConversationSidebar
        activeConversationId={activeConversation}
        conversations={conversations}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
        onClearAll={handleClearAll}
        assignedCount={assignedRequests.length}
      />

      <main className="flex-1 flex flex-col min-w-0 h-screen">
        <header className="flex items-center justify-between px-6 py-3 border-b bg-card">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-base text-primary">PingHR</span>
            <span className="text-muted-foreground text-sm">/ HR Chat</span>
            {activeAssignedRequest && (
              <Badge variant="outline" className="ml-2 text-xs gap-1 border-primary/20 text-primary">
                <FileText className="h-3 w-3" />
                Working on request #{activeAssignedRequest.id}
              </Badge>
            )}
            {!activeAssignedRequest && activeTicket && (
              <Badge variant="outline" className="ml-2 text-xs gap-1 border-primary/20 text-primary">
                <FileText className="h-3 w-3" />
                Working on: {activeTicket.employee}'s request
              </Badge>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            className="gap-2 text-primary border-primary/30 hover:bg-primary/5"
            onClick={() => setRequestsOpen(true)}
          >
            <Mail className="h-4 w-4" />
            My Assigned
            {assignedRequests.length > 0 && (
              <span className="ml-1 h-5 min-w-5 px-1 rounded-full bg-destructive text-destructive-foreground text-[10px] font-bold flex items-center justify-center">
                {assignedRequests.length}
              </span>
            )}
          </Button>
        </header>

        {!activeAssignedRequest && activeTicket && (
          <TicketActionBar
            ticket={activeTicket}
            onMoveToNext={handleMoveTicketToNext}
          />
        )}

        <div className="flex-1 overflow-y-auto">
          {showWelcome ? (
            <div className="flex flex-col items-center justify-center px-6 py-6 max-w-3xl mx-auto h-full">
              <div className="flex-1 min-h-0" />
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-primary/20 bg-primary/5 text-primary text-xs font-medium mb-4">
                <Sparkles className="h-3.5 w-3.5" />
                HR Assistant · Acme Corp
              </div>
              <h1 className="text-2xl md:text-3xl font-bold mb-2 text-center">
                Hi {capitalizedName}, how can I help?
              </h1>
              <p className="text-muted-foreground text-center mb-1 max-w-lg text-sm">
                Look up employees, reference policies, draft responses, or get analytics insights.
              </p>
              <p className="text-xs text-muted-foreground text-center mb-6">
                Your AI-powered HR operations assistant.
              </p>
              <HRCategoryCards onSelectCategory={handleSend} />
              <div className="flex-1 min-h-0" />
            </div>
          ) : (
            <div className="max-w-3xl mx-auto px-6 py-6 space-y-4">
              {messages.map((msg) => (
                <ChatMessageBubble
                  key={msg.id}
                  msg={msg}
                  onEscalate={handleEscalate}
                  showEscalate
                />
              ))}
              {isTyping && messages[messages.length - 1]?.role !== "assistant" && (
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
          <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="relative">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Look up employees, draft responses, check policies..."
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
            AI-assisted responses for HR operations.
          </p>
        </div>
      </main>

      <MyRequestsPanel
        isOpen={requestsOpen}
        onClose={() => setRequestsOpen(false)}
        requests={assignedRequests}
        title="My Assigned Tickets"
        subtitle={`${assignedRequests.length} assigned tickets`}
        emptyStateMessage="No assigned tickets yet. Pick up requests from HR Ops."
      />
    </div>
  );
}
