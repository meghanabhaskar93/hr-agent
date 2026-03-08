import { useState, useRef, useEffect } from "react";
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
  createEscalation,
  createSession,
  fetchEscalations,
  fetchSessions,
  sendChat,
  type BackendEscalation,
} from "@/lib/backend";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  confidence?: "high" | "low";
  escalated?: boolean;
}

const NEW_CONVERSATION_LABEL = "New conversation";

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
  status: BackendEscalation["status"]
): "pending" | "in_review" | "resolved" {
  if (status === "IN_REVIEW") return "in_review";
  if (status === "RESOLVED") return "resolved";
  return "pending";
}

function mapEscalationToRequest(item: BackendEscalation): EscalatedRequest {
  const createdAt = new Date(item.created_at);
  const updatedAt = new Date(item.updated_at);
  return {
    id: String(item.escalation_id),
    summary:
      item.source_message_excerpt.length > 60
        ? `${item.source_message_excerpt.slice(0, 60)}...`
        : item.source_message_excerpt,
    fullSummary: item.source_message_excerpt,
    aiResponse: item.resolution_note || "Escalated from conversation for HR follow-up.",
    status: toRequestStatus(item.status),
    priority: item.status === "PENDING" ? "high" : "medium",
    category: detectCategory(item.source_message_excerpt),
    timestamp: createdAt,
    auditLog: [
      { label: "Escalated to HR by employee", timestamp: createdAt },
      { label: "Last status update", timestamp: updatedAt },
    ],
  };
}

export default function ChatPage() {
  const { user, session } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationMessages, setConversationMessages] = useState<
    Record<string, Message[]>
  >({});
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [isCreatingConversation, setIsCreatingConversation] = useState(false);
  const [requestsOpen, setRequestsOpen] = useState(false);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [escalatedRequests, setEscalatedRequests] = useState<EscalatedRequest[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const displayName = user?.email?.split("@")[0] ?? "there";
  const capitalizedName = displayName.charAt(0).toUpperCase() + displayName.slice(1);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!user?.email) return;
    let cancelled = false;

    const loadData = async () => {
      try {
        const storedTitles = loadConversationTitles(user.email);
        const [sessions, escalations] = await Promise.all([
          fetchSessions(user.email),
          fetchEscalations(user.email),
        ]);

        if (cancelled) return;

        setConversations(
          sessions
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
            .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
        );

        setEscalatedRequests(
          escalations
            .map(mapEscalationToRequest)
            .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
        );
      } catch (error) {
        console.error("Failed to load chat data:", error);
      }
    };

    void loadData();
    return () => {
      cancelled = true;
    };
  }, [user?.email]);

  if (!session || !user) {
    return <Navigate to="/auth" replace />;
  }

  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || isTyping || !user?.email) return;

    let convId = activeConversation;
    if (!convId) {
      try {
        const sessionInfo = await createSession(user.email);
        convId = sessionInfo.session_id;
        const preview = buildConversationTitleFromMessage(msg);
        saveConversationTitleIfMissing(user.email, convId, preview);
        setConversations((prev) => [
          { id: convId!, preview, timestamp: new Date(sessionInfo.created_at) },
          ...prev,
        ]);
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
    setActiveConversation(id);
    setMessages(conversationMessages[id] || []);
  };

  const handleNewConversation = async () => {
    if (!user?.email || isCreatingConversation) return;

    if (activeConversation && messages.length > 0) {
      setConversationMessages((prev) => ({
        ...prev,
        [activeConversation]: messages,
      }));
    }

    setIsCreatingConversation(true);
    try {
      const sessionInfo = await createSession(user.email);
      const newId = sessionInfo.session_id;

      setConversations((prev) => [
        {
          id: newId,
          preview: NEW_CONVERSATION_LABEL,
          timestamp: new Date(sessionInfo.created_at),
        },
        ...prev.filter((item) => item.id !== newId),
      ]);
      setConversationMessages((prev) => ({ ...prev, [newId]: [] }));
      setMessages([]);
      setInput("");
      setActiveConversation(newId);
    } catch (error: any) {
      toast.error(error?.message || "Failed to create a new conversation");
    } finally {
      setIsCreatingConversation(false);
    }
  };

  const handleDeleteConversation = (id: string) => {
    if (user?.email) {
      removeConversationTitle(user.email, id);
    }
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

  const handleClearAll = () => {
    if (user?.email) {
      clearConversationTitles(user.email);
    }
    setConversations([]);
    setConversationMessages({});
    setMessages([]);
    setActiveConversation(null);
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
      const result = await createEscalation(
        user.email,
        threadId,
        queryText.slice(0, 1000)
      );
      if (!result.success) {
        throw new Error(result.error || "Escalation failed");
      }

      const refreshed = await fetchEscalations(user.email);
      setEscalatedRequests(
        refreshed
          .map(mapEscalationToRequest)
          .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
      );
      toast.success(`Escalated to HR Ops (#${result.escalation_id ?? "new"})`);
    } catch (error: any) {
      toast.error(error?.message || "Failed to escalate");
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
            {escalatedRequests.length > 0 && (
              <span className="ml-1 h-5 min-w-5 px-1 rounded-full bg-destructive text-destructive-foreground text-[10px] font-bold flex items-center justify-center">
                {escalatedRequests.length}
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
      />
    </div>
  );
}
