import { useState } from "react";
import { motion } from "framer-motion";
import { Bot, User, ThumbsUp, ThumbsDown, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  confidence?: "high" | "low";
  escalated?: boolean;
}

interface ChatMessageBubbleProps {
  msg: Message;
  onEscalate: (msg: Message) => void;
  onFeedback?: (msgId: string, feedback: "up" | "down") => void;
  showEscalate?: boolean;
}

export default function ChatMessageBubble({ msg, onEscalate, onFeedback, showEscalate = true }: ChatMessageBubbleProps) {
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const [isEscalated, setIsEscalated] = useState(msg.escalated ?? false);

  const handleThumbsDown = () => {
    setFeedback("down");
    onFeedback?.(msg.id, "down");
  };

  const handleThumbsUp = () => {
    setFeedback("up");
    onFeedback?.(msg.id, "up");
  };

  const handleEscalate = () => {
    setIsEscalated(true);
    onEscalate(msg);
    toast.success("Escalated to HR Ops — check My Requests for updates.");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}
    >
      {msg.role === "assistant" && (
        <div className="h-8 w-8 rounded-lg bg-primary/10 flex-shrink-0 flex items-center justify-center mt-0.5">
          <Bot className="h-4 w-4 text-primary" />
        </div>
      )}
      <div className="max-w-[75%]">
        <div
          className={`rounded-xl px-4 py-3 text-sm leading-relaxed ${
            msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
          }`}
        >
          <div className="whitespace-pre-wrap">
            {msg.content.split(/(\*\*.*?\*\*)/).map((part, i) =>
              part.startsWith("**") && part.endsWith("**") ? (
                <strong key={i}>{part.slice(2, -2)}</strong>
              ) : (
                <span key={i}>{part}</span>
              )
            )}
          </div>
          {(msg.escalated || isEscalated) && (
            <div className="mt-2 px-2 py-1 rounded bg-warning/10 text-warning text-xs font-medium">
              ⚠ Escalated to HR
            </div>
          )}
        </div>

        {/* Feedback row — only for assistant messages */}
        {msg.role === "assistant" && !isEscalated && (
          <div className="flex items-center gap-1 mt-1.5 ml-1">
            <button
              onClick={handleThumbsUp}
              className={`p-1 rounded-md transition-colors ${
                feedback === "up"
                  ? "text-primary bg-primary/10"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
              title="Helpful"
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={handleThumbsDown}
              className={`p-1 rounded-md transition-colors ${
                feedback === "down"
                  ? "text-destructive bg-destructive/10"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
              title="Not helpful"
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </button>

            {/* Escalate button appears after thumbs down — only for employee chat */}
            {feedback === "down" && showEscalate && (
              <motion.div
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
              >
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 ml-1 gap-1.5 text-xs border-destructive/30 text-destructive hover:bg-destructive/5"
                  onClick={handleEscalate}
                >
                  <AlertTriangle className="h-3 w-3" />
                  Escalate to HR
                </Button>
              </motion.div>
            )}
          </div>
        )}
      </div>
      {msg.role === "user" && (
        <div className="h-8 w-8 rounded-lg bg-secondary flex-shrink-0 flex items-center justify-center mt-0.5">
          <User className="h-4 w-4 text-secondary-foreground" />
        </div>
      )}
    </motion.div>
  );
}
