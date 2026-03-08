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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import ConversationSidebar from "@/components/ConversationSidebar";

type Priority = "critical" | "high" | "medium";
type Status = "pending" | "reviewed" | "sent";

interface EscalatedQuery {
  id: string;
  employee: string;
  question: string;
  aiDraft: string;
  status: Status;
  priority: Priority;
  category: string;
  timestamp: Date;
  timeToResolve?: number;
}

const mockQueries: EscalatedQuery[] = [
  {
    id: "1",
    employee: "Jordan Lee",
    question: "Can I take unpaid leave for 3 months to care for a family member abroad?",
    aiDraft: "Hi Jordan,\n\nUnder our Extended Leave Policy, you have a few options:\n\n1. **FMLA Leave** — up to 12 weeks protected leave\n2. **Personal Leave** — up to 6 months with VP approval\n3. **Remote Work** — possible depending on role\n\nBest,\nHR Team",
    status: "pending",
    priority: "critical",
    category: "Leave",
    timestamp: new Date(Date.now() - 2 * 3600000),
  },
  {
    id: "2",
    employee: "Sam Patel",
    question: "Stock options vesting schedule differs from offer letter",
    aiDraft: "Hi Sam,\n\nThank you for flagging this. I've created a ticket for Equity Administration to review your vesting schedule.\n\nExpected response: 2–3 business days.\n\nBest,\nHR Team",
    status: "pending",
    priority: "high",
    category: "Compensation",
    timestamp: new Date(Date.now() - 5 * 3600000),
  },
  {
    id: "3",
    employee: "Alex Kim",
    question: "Internal transfer process to another team",
    aiDraft: "Hi Alex,\n\n1. Express interest to current manager\n2. Apply via Internal Job Board\n3. Interview with receiving team\n4. Both managers approve\n5. HR facilitates transition\n\nBest,\nHR Team",
    status: "reviewed",
    priority: "medium",
    category: "Career Development",
    timestamp: new Date(Date.now() - 86400000),
    timeToResolve: 45,
  },
  {
    id: "4",
    employee: "Morgan Chen",
    question: "Tuition reimbursement for part-time MBA program",
    aiDraft: "Hi Morgan,\n\nYes! Up to $10,000/year for approved programs. Requirements: accredited institution, 1 year employment, B average.\n\nBest,\nHR Team",
    status: "sent",
    priority: "medium",
    category: "Benefits",
    timestamp: new Date(Date.now() - 2 * 86400000),
    timeToResolve: 30,
  },
];

const priorityConfig: Record<Priority, { label: string; className: string }> = {
  critical: { label: "Critical", className: "bg-destructive/10 text-destructive border-destructive/20" },
  high: { label: "High", className: "bg-warning/10 text-warning border-warning/20" },
  medium: { label: "Medium", className: "bg-muted text-muted-foreground" },
};

const statusConfig: Record<Status, { label: string; icon: typeof Clock; color: string }> = {
  pending: { label: "Pending", icon: AlertTriangle, color: "text-warning" },
  reviewed: { label: "Reviewed", icon: Clock, color: "text-info" },
  sent: { label: "Sent", icon: CheckCircle2, color: "text-success" },
};

export default function HRQueue() {
  const navigate = useNavigate();
  const [queries, setQueries] = useState(mockQueries);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);

  const handleStatusChange = (id: string, newStatus: "reviewed" | "sent") => {
    setQueries((prev) =>
      prev.map((q) =>
        q.id === id
          ? { ...q, status: newStatus, timeToResolve: newStatus === "sent" ? Math.floor(Math.random() * 60 + 15) : undefined }
          : q
      )
    );
  };

  const sorted = [...queries].sort((a, b) => {
    const order: Record<Priority, number> = { critical: 0, high: 1, medium: 2 };
    return order[a.priority] - order[b.priority];
  });

  const pendingCount = queries.filter((q) => q.status === "pending").length;

  return (
    <div className="min-h-screen flex w-full">
      <ConversationSidebar
        activeConversationId={activeConversation}
        conversations={[]}
        onSelectConversation={setActiveConversation}
        onNewConversation={() => navigate("/hr-chat")}
        onDeleteConversation={() => {}}
        onClearAll={() => {}}
      />
      <main className="flex-1 flex flex-col min-w-0 h-screen overflow-auto">
        <header className="flex items-center px-6 py-3 border-b bg-card">
          <span className="font-semibold text-base text-primary">PingHR</span>
          <span className="text-muted-foreground text-sm ml-3">/ HR Queue</span>
        </header>

        <div className="p-6 max-w-6xl mx-auto w-full">
          <div className="mb-6">
            <h1 className="text-2xl font-bold mb-1">HR Ops Queue</h1>
            <p className="text-muted-foreground text-sm">
              {pendingCount} escalated queries awaiting review · Sorted by priority
            </p>
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
                  <TableHead className="w-[100px]">Resolution</TableHead>
                  <TableHead className="w-[60px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((query) => {
                  const pConfig = priorityConfig[query.priority];
                  const sConfig = statusConfig[query.status];
                  const isExpanded = expandedId === query.id;

                  return (
                    <>
                      <TableRow
                        key={query.id}
                        className="cursor-pointer hover:bg-muted/30"
                        onClick={() => setExpandedId(isExpanded ? null : query.id)}
                      >
                        <TableCell>
                          <Badge variant="outline" className={`text-xs ${pConfig.className}`}>
                            {pConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-medium text-sm">{query.employee}</TableCell>
                        <TableCell className="text-sm text-muted-foreground max-w-[300px] truncate">
                          {query.question}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-xs">{query.category}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="text-xs gap-1">
                            <sConfig.icon className={`h-3 w-3 ${sConfig.color}`} />
                            {sConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">
                          <span className={query.timeToResolve ? "text-success font-medium" : query.status === "pending" ? "text-warning" : "text-muted-foreground"}>
                            {query.timeToResolve ? `${query.timeToResolve} min` : query.status === "pending" ? "Pending" : "—"}
                          </span>
                        </TableCell>
                        <TableCell>
                          {isExpanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                        </TableCell>
                      </TableRow>

                      {isExpanded && (
                        <TableRow key={`${query.id}-expanded`}>
                          <TableCell colSpan={7} className="bg-muted/10 p-0">
                            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="px-6 py-4 space-y-4">
                              <div>
                                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Employee Question</h4>
                                <p className="text-sm bg-card rounded-lg p-3 border">{query.question}</p>
                              </div>
                              <div>
                                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">AI-Drafted Response</h4>
                                <div className="text-sm bg-accent/30 rounded-lg p-3 whitespace-pre-wrap border border-primary/10">
                                  {query.aiDraft.split(/(\*\*.*?\*\*)/).map((part, i) =>
                                    part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : <span key={i}>{part}</span>
                                  )}
                                </div>
                              </div>
                              <div className="flex gap-2">
                                {query.status === "pending" && (
                                  <>
                                    <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); handleStatusChange(query.id, "reviewed"); }}>
                                      <Eye className="h-3.5 w-3.5 mr-1.5" /> Mark Reviewed
                                    </Button>
                                    <Button size="sm" onClick={(e) => { e.stopPropagation(); handleStatusChange(query.id, "sent"); }}>
                                      <Send className="h-3.5 w-3.5 mr-1.5" /> Approve & Send
                                    </Button>
                                  </>
                                )}
                                {query.status === "reviewed" && (
                                  <Button size="sm" onClick={(e) => { e.stopPropagation(); handleStatusChange(query.id, "sent"); }}>
                                    <Send className="h-3.5 w-3.5 mr-1.5" /> Send to Employee
                                  </Button>
                                )}
                                {query.status === "sent" && (
                                  <span className="text-xs text-success font-medium flex items-center gap-1">
                                    <CheckCircle2 className="h-3.5 w-3.5" /> Response sent
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
    </div>
  );
}
