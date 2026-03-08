import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, Tag, CheckCircle2, X, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { HRTicket, ResolutionTag } from "@/contexts/HRTicketsContext";
import { resolutionTagConfig } from "@/contexts/HRTicketsContext";

const resolutionTags: ResolutionTag[] = ["needs_info", "ready", "in_progress", "escalated", "resolved"];

const statusFlow: Record<string, { next: string; label: string }> = {
  in_progress: { next: "in_review", label: "Move to In Review" },
  in_review: { next: "resolved", label: "Mark Resolved" },
};

interface TicketActionBarProps {
  ticket: HRTicket;
  onMoveToNext: (note: string, tag: ResolutionTag) => void;
}

export default function TicketActionBar({ ticket, onMoveToNext }: TicketActionBarProps) {
  const [showModal, setShowModal] = useState(false);
  const [selectedTag, setSelectedTag] = useState<ResolutionTag | null>(ticket.resolutionTag ?? null);
  const [note, setNote] = useState(ticket.resolutionNote ?? "");

  const flow = statusFlow[ticket.status];
  if (!flow) return null;

  const canSubmit = !!selectedTag && note.trim().length > 0;

  const handleSubmit = () => {
    if (!canSubmit) return;
    onMoveToNext(note.trim(), selectedTag!);
    setShowModal(false);
  };

  return (
    <>
      {/* Action Bar */}
      <div className="border-b bg-muted/30 px-6 py-2.5 flex items-center justify-between max-w-full">
        <div className="flex items-center gap-3 text-sm">
          <div className="flex items-center gap-1.5">
            <span className="text-muted-foreground">Status:</span>
            <Badge variant="outline" className="text-xs capitalize">
              {ticket.status.replace("_", " ")}
            </Badge>
          </div>
          {ticket.resolutionTag && (
            <Badge
              variant="outline"
              className={`text-xs gap-1 ${resolutionTagConfig[ticket.resolutionTag].className}`}
            >
              <Tag className="h-2.5 w-2.5" />
              {resolutionTagConfig[ticket.resolutionTag].label}
            </Badge>
          )}
        </div>
        <Button
          size="sm"
          className="gap-1.5 text-xs"
          onClick={() => setShowModal(true)}
        >
          {flow.next === "resolved" ? (
            <CheckCircle2 className="h-3.5 w-3.5" />
          ) : (
            <ArrowRight className="h-3.5 w-3.5" />
          )}
          {flow.label}
        </Button>
      </div>

      {/* Modal Overlay */}
      <AnimatePresence>
        {showModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
            onClick={() => setShowModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              transition={{ duration: 0.15 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-card border rounded-2xl shadow-lg w-full max-w-md mx-4 overflow-hidden"
            >
              {/* Modal Header */}
              <div className="flex items-center justify-between px-5 py-4 border-b">
                <div>
                  <h3 className="font-semibold text-base">{flow.label}</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {ticket.employee}'s request · {ticket.category}
                  </p>
                </div>
                <button
                  onClick={() => setShowModal(false)}
                  className="p-1.5 rounded-lg hover:bg-muted transition-colors"
                >
                  <X className="h-4 w-4 text-muted-foreground" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="px-5 py-4 space-y-4">
                {/* Resolution Tag Selection */}
                <div>
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block mb-2">
                    Resolution Tag *
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {resolutionTags.map((tag) => {
                      const config = resolutionTagConfig[tag];
                      const isSelected = selectedTag === tag;
                      return (
                        <button
                          key={tag}
                          onClick={() => setSelectedTag(tag)}
                          className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                            isSelected
                              ? `${config.className} ring-2 ring-offset-1 ring-primary/30`
                              : "border-border text-muted-foreground hover:border-primary/30 hover:text-foreground"
                          }`}
                        >
                          {config.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Resolution Note */}
                <div>
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block mb-2">
                    Resolution Note *
                  </label>
                  <textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Summarize the resolution or next steps..."
                    rows={3}
                    className="w-full rounded-xl border bg-background px-3.5 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/20 resize-none"
                  />
                </div>

                {!canSubmit && (
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <AlertCircle className="h-3 w-3" />
                    Select a tag and add a note to continue.
                  </div>
                )}
              </div>

              {/* Modal Footer */}
              <div className="px-5 py-3 border-t bg-muted/20 flex justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  disabled={!canSubmit}
                  onClick={handleSubmit}
                  className="gap-1.5"
                >
                  {flow.next === "resolved" ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <ArrowRight className="h-3.5 w-3.5" />
                  )}
                  {flow.label}
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
