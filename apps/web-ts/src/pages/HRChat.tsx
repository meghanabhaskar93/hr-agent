import { useState, useRef, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { Loader2, ArrowUp, Sparkles, Mail, Bot, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import HRConversationSidebar from "@/components/HRConversationSidebar";
import MyRequestsPanel from "@/components/MyRequestsPanel";
import ChatMessageBubble from "@/components/ChatMessageBubble";
import HRCategoryCards from "@/components/HRCategoryCards";
import TicketActionBar from "@/components/TicketActionBar";
import { useAuth } from "@/contexts/AuthContext";
import { useHRTickets } from "@/contexts/HRTicketsContext";
import type { ResolutionTag } from "@/contexts/HRTicketsContext";
import { mockEmployees } from "@/data/mockEmployees";
import { sendChat } from "@/lib/backend";
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
    toast.error(error instanceof Error ? error.message : "Chat request failed");
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

export default function HRChat() {
  const { user } = useAuth();
  const { getAssignedTickets, getAssignedRequests, getTicketById, addResolutionNote, updateTicketStatus } = useHRTickets();
  const [searchParams, setSearchParams] = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationMessages, setConversationMessages] = useState<Record<string, Message[]>>({});
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [requestsOpen, setRequestsOpen] = useState(false);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeTicketId, setActiveTicketId] = useState<string | null>(null);
  const [processedTickets, setProcessedTickets] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const displayName = user?.email?.split("@")[0] ?? "HR User";
  const capitalizedName = displayName.charAt(0).toUpperCase() + displayName.slice(1);
  const assignedTickets = getAssignedTickets(displayName);
  const assignedRequests = getAssignedRequests(displayName);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Handle deep-link from HR Ops with ?ticket=ID
  useEffect(() => {
    const ticketId = searchParams.get("ticket");
    if (ticketId && !processedTickets.has(ticketId)) {
      const ticket = getTicketById(ticketId);
      if (ticket) {
        setActiveTicketId(ticketId);
        setProcessedTickets((prev) => new Set(prev).add(ticketId));
        // Clear the param so refreshing doesn't re-inject
        setSearchParams({}, { replace: true });

        // Auto-inject the context as a message and send to agent
        const contextPrompt = buildTicketContextPrompt(ticket);
        // Small delay to let the component mount
        setTimeout(() => {
          handleSendWithContext(contextPrompt, `ticket-${ticketId}`);
        }, 300);
      }
    }
  }, [searchParams]);

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

    const convId = convIdOverride || `conv-${Date.now()}`;
    const preview = msg.length > 40 ? msg.slice(0, 40) + "..." : msg;

    // Check if conversation already exists
    setConversations((prev) => {
      if (prev.find((c) => c.id === convId)) return prev;
      return [{ id: convId, preview: `📋 ${preview}`, timestamp: new Date() }, ...prev];
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
            confidence: "high",
          },
        ]);
      }
    }
  }, [updateMessages, user?.email]);

  const handleSend = useCallback(async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || isTyping || !user?.email) return;

    let convId = activeConversation;
    if (!convId) {
      convId = `conv-${Date.now()}`;
      const preview = msg.length > 30 ? msg.slice(0, 30) + "..." : msg;
      setConversations((prev) => [{ id: convId!, preview, timestamp: new Date() }, ...prev]);
      setActiveConversation(convId);
    }

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
            confidence: "high",
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
    setMessages(conversationMessages[id] || []);
  };

  const handleNewConversation = () => {
    if (activeConversation && messages.length > 0) {
      setConversationMessages((cm) => ({ ...cm, [activeConversation]: messages }));
    }
    setMessages([]);
    setActiveConversation(null);
    setActiveTicketId(null);
  };

  const handleDeleteConversation = (id: string) => {
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
    }
  };

  const handleClearAll = () => {
    setConversations([]);
    setConversationMessages({});
    setMessages([]);
    setActiveConversation(null);
    setActiveTicketId(null);
  };

  const handleMoveTicketToNext = (note: string, tag: ResolutionTag) => {
    if (!activeTicketId) return;
    const ticket = getTicketById(activeTicketId);
    if (!ticket) return;
    addResolutionNote(activeTicketId, note, tag);
    const nextStatus = ticket.status === "in_progress" ? "in_review" : "resolved";
    updateTicketStatus(activeTicketId, nextStatus as any);
    toast.success(`Ticket moved to ${nextStatus.replace("_", " ")}`);
  };

  const showWelcome = messages.length === 0 && !isTyping;
  const activeTicket = activeTicketId ? getTicketById(activeTicketId) : null;

  return (
    <div className="min-h-screen flex w-full">
      <HRConversationSidebar
        activeConversationId={activeConversation}
        conversations={conversations}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
        onClearAll={handleClearAll}
        assignedCount={assignedTickets.length}
      />

      <main className="flex-1 flex flex-col min-w-0 h-screen">
        <header className="flex items-center justify-between px-6 py-3 border-b bg-card">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-base text-primary">PingHR</span>
            <span className="text-muted-foreground text-sm">/ HR Chat</span>
            {activeTicket && (
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
            My Requests
            {assignedTickets.length > 0 && (
              <span className="ml-1 h-5 min-w-5 px-1 rounded-full bg-destructive text-destructive-foreground text-[10px] font-bold flex items-center justify-center">
                {assignedTickets.length}
              </span>
            )}
          </Button>
        </header>

        {activeTicket && (
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
                <ChatMessageBubble key={msg.id} msg={msg} onEscalate={() => {}} showEscalate={false} />
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

      <MyRequestsPanel isOpen={requestsOpen} onClose={() => setRequestsOpen(false)} requests={assignedRequests} />
    </div>
  );
}
