import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, X, Bot, User, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  confidence?: "high" | "low";
  escalated?: boolean;
}

// Mock responses for prototype
const mockResponses: Record<string, { content: string; confidence: "high" | "low" }> = {
  "wfh": {
    content: "📋 **Work From Home Policy**\n\nOur WFH policy allows employees to work remotely up to 3 days per week. Here are the key points:\n\n- **Eligibility:** All full-time employees after completing their probation period\n- **Core hours:** You must be available between 10 AM – 4 PM in your local timezone\n- **Equipment:** The company provides a laptop and one monitor for home use\n- **Approval:** Coordinate your WFH schedule with your direct manager\n\nWould you like more details on any specific aspect?",
    confidence: "high",
  },
  "pto": {
    content: "🏖️ **Your PTO Balance**\n\n- **Available:** 14 days remaining\n- **Used this year:** 6 days\n- **Pending requests:** None\n- **Accrual rate:** 1.67 days/month\n\nYour next accrual date is **March 15, 2026**. Would you like to submit a time-off request?",
    confidence: "high",
  },
  "enrollment": {
    content: "💊 **Open Enrollment Period**\n\nThe next open enrollment is scheduled for **November 1–15, 2026**. During this window, you can:\n\n- Change your health plan tier\n- Add or remove dependents\n- Enroll in dental/vision coverage\n- Adjust your FSA/HSA contributions\n\nI'll send you a reminder 2 weeks before it starts!",
    confidence: "high",
  },
  "pay": {
    content: "💰 **Payroll Information**\n\nYour next pay date is **March 15, 2026** (bi-weekly cycle).\n\n- **Pay frequency:** Bi-weekly (every other Friday)\n- **Direct deposit:** Active ✅\n- **Tax forms:** Your W-2 for 2025 is available in the HR portal\n\nNeed help with anything else related to payroll?",
    confidence: "high",
  },
  "expense": {
    content: "🧾 **Expense Report Submission**\n\nTo submit an expense report:\n\n1. Go to **HR Portal → Expenses → New Report**\n2. Upload receipts (photos or PDFs)\n3. Categorize each expense (travel, meals, software, etc.)\n4. Submit for manager approval\n\n**Limits:** Meals up to $50/day, travel pre-approval required for >$500\n**Timeline:** Reimbursements processed within 5 business days after approval.",
    confidence: "high",
  },
  "first week": {
    content: "🎉 **Welcome! First Week Checklist**\n\n- [ ] Complete IT setup (laptop, email, Slack)\n- [ ] Badge activation at front desk\n- [ ] Meet your buddy (assigned on Day 1)\n- [ ] Complete compliance training modules\n- [ ] Set up direct deposit in HR Portal\n- [ ] Schedule 1:1 with your manager\n\nYour onboarding buddy is **Sarah Chen** — she'll reach out today!",
    confidence: "high",
  },
  "skip": {
    content: "👥 **Your Reporting Chain**\n\n- **Direct Manager:** Alex Rivera (Engineering Manager)\n- **Skip-Level Manager:** Priya Sharma (VP of Engineering)\n- **Department Head:** James O'Brien (CTO)\n\nWould you like me to look up anyone else in the org chart?",
    confidence: "high",
  },
  "performance": {
    content: "📊 **Performance Review Cycle**\n\nThe next review cycle is **Q2 2026 (April 1–30)**.\n\n- **Self-assessment due:** April 7\n- **Peer feedback window:** April 8–14\n- **Manager review:** April 15–25\n- **Calibration:** April 26–28\n- **Results shared:** May 1\n\nStart preparing your accomplishments list now!",
    confidence: "high",
  },
  "compliance": {
    content: "⚠️ **Reporting a Compliance Concern**\n\nYou have multiple confidential options:\n\n1. **Ethics Hotline:** 1-800-555-ETHC (anonymous)\n2. **Email:** ethics@company.com\n3. **In-person:** Schedule with HR Business Partner\n4. **Online form:** HR Portal → Report Concern\n\nAll reports are handled confidentially. Retaliation against reporters is strictly prohibited per our Code of Conduct.",
    confidence: "high",
  },
  default: {
    content: "I'm not fully confident in answering this question based on current policies. Let me **escalate this to HR Ops** so they can provide you with an accurate answer.\n\n🔄 **Escalated to HR Team** — You'll receive a response within 24 hours.\n\nIs there anything else I can help you with?",
    confidence: "low",
  },
};

function getResponse(input: string): { content: string; confidence: "high" | "low" } {
  const lower = input.toLowerCase();
  if (lower.includes("wfh") || lower.includes("work from home") || lower.includes("remote")) return mockResponses.wfh;
  if (lower.includes("pto") || lower.includes("time off") || lower.includes("leave") || lower.includes("vacation")) return mockResponses.pto;
  if (lower.includes("enrollment") || lower.includes("benefit") || lower.includes("insurance") || lower.includes("health")) return mockResponses.enrollment;
  if (lower.includes("pay") || lower.includes("salary") || lower.includes("payroll")) return mockResponses.pay;
  if (lower.includes("expense") || lower.includes("reimburs") || lower.includes("receipt")) return mockResponses.expense;
  if (lower.includes("first week") || lower.includes("onboarding") || lower.includes("new hire")) return mockResponses["first week"];
  if (lower.includes("skip") || lower.includes("manager") || lower.includes("directory") || lower.includes("org")) return mockResponses.skip;
  if (lower.includes("performance") || lower.includes("review") || lower.includes("promotion")) return mockResponses.performance;
  if (lower.includes("compliance") || lower.includes("ethics") || lower.includes("report") || lower.includes("harassment")) return mockResponses.compliance;
  return mockResponses.default;
}

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  initialPrompt?: string;
}

export default function ChatPanel({ isOpen, onClose, initialPrompt }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const processedPromptRef = useRef<string | null>(null);

  useEffect(() => {
    if (isOpen && initialPrompt && initialPrompt !== processedPromptRef.current) {
      processedPromptRef.current = initialPrompt;
      handleSend(initialPrompt);
    }
  }, [isOpen, initialPrompt]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  const handleSend = (text?: string) => {
    const msg = text || input.trim();
    if (!msg) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: msg,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);

    setTimeout(() => {
      const response = getResponse(msg);
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: response.content,
        timestamp: new Date(),
        confidence: response.confidence,
        escalated: response.confidence === "low",
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsTyping(false);
    }, 800 + Math.random() * 700);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", damping: 28, stiffness: 300 }}
          className="fixed right-0 top-0 h-full w-full sm:w-[440px] bg-card border-l border-border z-50 flex flex-col shadow-elevated"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b">
            <div className="flex items-center gap-2.5">
              <div className="h-9 w-9 rounded-lg bg-primary flex items-center justify-center">
                <Sparkles className="h-5 w-5 text-primary-foreground" />
              </div>
              <div>
                <h2 className="font-semibold text-sm">PingHR Assistant</h2>
                <p className="text-xs text-muted-foreground">Ask me anything about HR</p>
              </div>
            </div>
            <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center px-6">
                <div className="h-14 w-14 rounded-2xl bg-accent flex items-center justify-center mb-4">
                  <Bot className="h-7 w-7 text-accent-foreground" />
                </div>
                <h3 className="font-semibold mb-1">Hi there! 👋</h3>
                <p className="text-sm text-muted-foreground">
                  I'm PingHR, your HR assistant. Ask me about policies, leave, benefits, payroll, and more.
                </p>
              </div>
            )}

            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex gap-2.5 ${msg.role === "user" ? "justify-end" : ""}`}
              >
                {msg.role === "assistant" && (
                  <div className="h-7 w-7 rounded-lg bg-primary/10 flex-shrink-0 flex items-center justify-center mt-0.5">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  }`}
                >
                  {msg.role === "assistant" ? (
                    <div className="whitespace-pre-wrap">
                      {msg.content.split(/(\*\*.*?\*\*)/).map((part, i) =>
                        part.startsWith("**") && part.endsWith("**") ? (
                          <strong key={i}>{part.slice(2, -2)}</strong>
                        ) : (
                          <span key={i}>{part}</span>
                        )
                      )}
                    </div>
                  ) : (
                    msg.content
                  )}
                  {msg.escalated && (
                    <div className="mt-2 px-2 py-1 rounded bg-warning/10 text-warning text-xs font-medium">
                      ⚠ Low confidence — Escalated to HR
                    </div>
                  )}
                </div>
                {msg.role === "user" && (
                  <div className="h-7 w-7 rounded-lg bg-secondary flex-shrink-0 flex items-center justify-center mt-0.5">
                    <User className="h-4 w-4 text-secondary-foreground" />
                  </div>
                )}
              </motion.div>
            ))}

            {isTyping && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex gap-2.5"
              >
                <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="bg-muted rounded-xl px-4 py-3">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                </div>
              </motion.div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex gap-2"
            >
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask PingHR anything..."
                className="flex-1 rounded-lg border bg-background px-3.5 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/20"
              />
              <Button
                type="submit"
                size="icon"
                disabled={!input.trim() || isTyping}
                className="h-10 w-10 rounded-lg"
              >
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
