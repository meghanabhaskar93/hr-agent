import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  AlertTriangle,
  Mail,
  ThumbsUp,
  ThumbsDown,
  TrendingUp,
  Clock,
  MessageSquare,
  BarChart3,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  Legend,
} from "recharts";
import HRConversationSidebar from "@/components/HRConversationSidebar";
import MyRequestsPanel from "@/components/MyRequestsPanel";
import type { Conversation } from "@/components/ConversationSidebar";
import { useAuth } from "@/contexts/AuthContext";
import { useHRTickets } from "@/contexts/HRTicketsContext";
import { fetchHRRequests, fetchSessions, type BackendHRRequest } from "@/lib/backend";

// Analytics data
const categoryData = [
  { name: "Leave & PTO", queries: 34, color: "hsl(var(--primary))" },
  { name: "Payroll", queries: 28, color: "hsl(var(--chart-2))" },
  { name: "Benefits", queries: 18, color: "hsl(var(--chart-3))" },
  { name: "Career Dev", queries: 12, color: "hsl(var(--chart-4))" },
  { name: "Other", queries: 8, color: "hsl(var(--chart-5))" },
];

const dailyTrendData = [
  { date: "Feb 24", queries: 8, resolved: 7, satisfaction: 4.2 },
  { date: "Feb 25", queries: 12, resolved: 11, satisfaction: 4.5 },
  { date: "Feb 26", queries: 10, resolved: 9, satisfaction: 4.1 },
  { date: "Feb 27", queries: 15, resolved: 14, satisfaction: 4.6 },
  { date: "Feb 28", queries: 11, resolved: 11, satisfaction: 4.8 },
  { date: "Mar 1", queries: 14, resolved: 13, satisfaction: 4.4 },
  { date: "Mar 2", queries: 9, resolved: 8, satisfaction: 4.3 },
  { date: "Mar 3", queries: 13, resolved: 11, satisfaction: 4.5 },
];

const feedbackData = [
  { name: "Helpful", value: 72, color: "hsl(var(--chart-2))" },
  { name: "Not Helpful", value: 18, color: "hsl(var(--destructive))" },
  { name: "No Feedback", value: 10, color: "hsl(var(--muted))" },
];

const resolutionData = [
  { name: "Instant (AI)", value: 52, color: "hsl(var(--chart-2))" },
  { name: "<30 min", value: 23, color: "hsl(var(--primary))" },
  { name: "30-60 min", value: 15, color: "hsl(var(--chart-4))" },
  { name: ">1 hr", value: 10, color: "hsl(var(--chart-5))" },
];

// Summary stats
const stats = [
  { label: "Total Queries", value: "92", change: "+12%", icon: MessageSquare, trend: "up" },
  { label: "AI Auto-Resolved", value: "52%", change: "+8%", icon: Zap, trend: "up" },
  { label: "Avg Resolution", value: "42 min", change: "-15%", icon: Clock, trend: "up" },
  { label: "Satisfaction", value: "4.6/5", change: "+0.3", icon: ThumbsUp, trend: "up" },
];

const NEW_CONVERSATION_LABEL = "New conversation";

type AuditLogEntry = {
  id: string;
  timestamp: Date;
  employee: string;
  query: string;
  action: string;
  confidence: "high" | "low";
  resolution: string;
  feedback: "up" | "down";
};

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

function toAuditTimestamp(date: Date): string {
  return date
    .toLocaleString("sv-SE", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })
    .replace(",", "");
}

function toEmployeeLabel(request: BackendHRRequest): string {
  const requesterName = request.requester_name?.trim();
  if (requesterName) return requesterName;
  const requesterUserId = request.requester_user_id?.trim();
  if (!requesterUserId) return "Employee";
  return requesterUserId.split("@")[0];
}

function toEscalationQuery(request: BackendHRRequest): string {
  const original = request.captured_fields?.["original_query"];
  if (typeof original === "string" && original.trim()) return original.trim();
  if (request.description.trim()) return request.description.trim();
  if (request.summary.trim()) return request.summary.trim();
  return "(No escalation query captured)";
}

function toAuditAction(request: BackendHRRequest): string {
  if (request.status === "RESOLVED") return "Escalation resolved by HR";
  if (request.status === "NEEDS_INFO") return "HR requested more information";
  if (request.status === "IN_PROGRESS") return "Escalation under HR review";
  if (request.status === "ESCALATED") return "Escalated for external handoff";
  if (request.status === "CANCELLED") return "Escalation cancelled";
  return "Escalated to HR";
}

function toDurationLabel(startIso: string, endIso: string): string {
  const start = new Date(startIso).getTime();
  const end = new Date(endIso).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return "Resolved";
  const diffMs = end - start;
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "Instant";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.round((minutes / 60) * 10) / 10;
  if (hours < 24) return `${hours} hr`;
  const days = Math.round((hours / 24) * 10) / 10;
  return `${days} d`;
}

function mapHRRequestToAuditEntry(request: BackendHRRequest): AuditLogEntry {
  const isResolved = request.status === "RESOLVED";
  const timestamp = new Date(request.updated_at || request.created_at);
  return {
    id: String(request.request_id),
    timestamp,
    employee: toEmployeeLabel(request),
    query: toEscalationQuery(request),
    action: toAuditAction(request),
    confidence: "low",
    resolution: isResolved
      ? toDurationLabel(request.created_at, request.updated_at || request.created_at)
      : request.status === "CANCELLED"
        ? "Cancelled"
        : "Pending",
    feedback: isResolved ? "up" : "down",
  };
}

export default function AuditLog() {
  const { user } = useAuth();
  const { getAssignedTickets, getAssignedRequests } = useHRTickets();
  const navigate = useNavigate();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [requestsOpen, setRequestsOpen] = useState(false);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(true);

  const displayName = user?.email?.split("@")[0] ?? "HR User";
  const assignedTickets = getAssignedTickets(displayName);
  const assignedRequests = getAssignedRequests(displayName);

  useEffect(() => {
    if (!user?.email) return;
    let cancelled = false;

    const loadData = async () => {
      setAuditLoading(true);
      try {
        const storedTitles = loadConversationTitles(user.email);
        const [sessions, hrRequests] = await Promise.all([
          fetchSessions(user.email),
          fetchHRRequests(user.email),
        ]);
        if (cancelled) return;
        setConversations(
          sessions
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
            .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
        );

        const escalationLogs = hrRequests
          .filter(
            (request) =>
              (request.type || "").toUpperCase() === "ESCALATION" &&
              (request.requester_role || "").toUpperCase() === "EMPLOYEE"
          )
          .map(mapHRRequestToAuditEntry)
          .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
        setAuditLogs(escalationLogs);
      } catch (error) {
        console.error("Failed to load HR conversations:", error);
      } finally {
        if (!cancelled) setAuditLoading(false);
      }
    };

    void loadData();
    return () => {
      cancelled = true;
    };
  }, [user?.email]);

  return (
    <div className="min-h-screen flex w-full">
      <HRConversationSidebar
        activeConversationId={activeConversation}
        conversations={conversations}
        onSelectConversation={(id) => {
          setActiveConversation(id);
          navigate(`/hr-chat?session=${encodeURIComponent(id)}`);
        }}
        onNewConversation={() => navigate("/hr-chat?new=1")}
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
            <span className="text-muted-foreground text-sm ml-1">/ Audit Log & Analytics</span>
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

        <div className="p-6 max-w-7xl mx-auto w-full space-y-6">
          <div>
            <h1 className="text-2xl font-bold mb-1">Analytics & Audit Log</h1>
            <p className="text-muted-foreground text-sm">AI performance metrics, feedback analytics, and interaction history</p>
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {stats.map((stat, i) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Card className="bg-card border shadow-soft">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{stat.label}</span>
                      <stat.icon className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div className="flex items-end gap-2">
                      <span className="text-2xl font-bold">{stat.value}</span>
                      <span className="text-xs font-medium text-emerald-600 flex items-center gap-0.5 mb-1">
                        <TrendingUp className="h-3 w-3" />
                        {stat.change}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>

          <Tabs defaultValue="analytics" className="space-y-4">
            <TabsList>
              <TabsTrigger value="analytics" className="gap-1.5">
                <BarChart3 className="h-3.5 w-3.5" />
                Analytics
              </TabsTrigger>
              <TabsTrigger value="log" className="gap-1.5">
                <MessageSquare className="h-3.5 w-3.5" />
                Audit Log
              </TabsTrigger>
            </TabsList>

            <TabsContent value="analytics" className="space-y-4">
              {/* Charts Row */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Query Volume Trend */}
                <Card className="bg-card border shadow-soft">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-semibold">Query Volume & Resolution Trend</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-[260px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={dailyTrendData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                          <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                          <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                          <Tooltip
                            contentStyle={{
                              background: "hsl(var(--card))",
                              border: "1px solid hsl(var(--border))",
                              borderRadius: "8px",
                              fontSize: "12px",
                            }}
                          />
                          <Legend wrapperStyle={{ fontSize: "11px" }} />
                          <Line type="monotone" dataKey="queries" stroke="hsl(var(--primary))" strokeWidth={2} dot={{ r: 3 }} name="Queries" />
                          <Line type="monotone" dataKey="resolved" stroke="hsl(var(--chart-2))" strokeWidth={2} dot={{ r: 3 }} name="Resolved" />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>

                {/* Category Breakdown */}
                <Card className="bg-card border shadow-soft">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-semibold">Queries by Category</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-[260px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={categoryData} layout="vertical">
                          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                          <XAxis type="number" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                          <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={80} stroke="hsl(var(--muted-foreground))" />
                          <Tooltip
                            contentStyle={{
                              background: "hsl(var(--card))",
                              border: "1px solid hsl(var(--border))",
                              borderRadius: "8px",
                              fontSize: "12px",
                            }}
                          />
                          <Bar dataKey="queries" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Second Row: Feedback + Resolution */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* AI Feedback */}
                <Card className="bg-card border shadow-soft">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-semibold">AI Response Feedback</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-6">
                      <div className="h-[200px] w-[200px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={feedbackData}
                              cx="50%"
                              cy="50%"
                              innerRadius={55}
                              outerRadius={85}
                              paddingAngle={3}
                              dataKey="value"
                            >
                              {feedbackData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.color} />
                              ))}
                            </Pie>
                            <Tooltip
                              contentStyle={{
                                background: "hsl(var(--card))",
                                border: "1px solid hsl(var(--border))",
                                borderRadius: "8px",
                                fontSize: "12px",
                              }}
                              formatter={(value: number) => [`${value}%`, ""]}
                            />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="space-y-3 flex-1">
                        {feedbackData.map((item) => (
                          <div key={item.name} className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <div className="h-3 w-3 rounded-full" style={{ backgroundColor: item.color }} />
                              <span className="text-sm">{item.name}</span>
                            </div>
                            <span className="text-sm font-semibold">{item.value}%</span>
                          </div>
                        ))}
                        <div className="pt-2 border-t">
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <ThumbsUp className="h-3 w-3 text-emerald-500" />
                            <span>72% positive — above 70% target</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Resolution Time */}
                <Card className="bg-card border shadow-soft">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-semibold">Resolution Time Distribution</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-6">
                      <div className="h-[200px] w-[200px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={resolutionData}
                              cx="50%"
                              cy="50%"
                              innerRadius={55}
                              outerRadius={85}
                              paddingAngle={3}
                              dataKey="value"
                            >
                              {resolutionData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.color} />
                              ))}
                            </Pie>
                            <Tooltip
                              contentStyle={{
                                background: "hsl(var(--card))",
                                border: "1px solid hsl(var(--border))",
                                borderRadius: "8px",
                                fontSize: "12px",
                              }}
                              formatter={(value: number) => [`${value}%`, ""]}
                            />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="space-y-3 flex-1">
                        {resolutionData.map((item) => (
                          <div key={item.name} className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <div className="h-3 w-3 rounded-full" style={{ backgroundColor: item.color }} />
                              <span className="text-sm">{item.name}</span>
                            </div>
                            <span className="text-sm font-semibold">{item.value}%</span>
                          </div>
                        ))}
                        <div className="pt-2 border-t">
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <Zap className="h-3 w-3 text-primary" />
                            <span>52% resolved instantly by AI</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="log">
              <Card className="bg-card border shadow-soft overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/30">
                      <TableHead>Time</TableHead>
                      <TableHead>Employee</TableHead>
                      <TableHead>Query</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>Confidence</TableHead>
                      <TableHead>Feedback</TableHead>
                      <TableHead>Resolution</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {auditLoading && (
                      <TableRow>
                        <TableCell colSpan={7} className="text-sm text-muted-foreground py-6 text-center">
                          Loading escalation activity...
                        </TableCell>
                      </TableRow>
                    )}
                    {!auditLoading && auditLogs.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={7} className="text-sm text-muted-foreground py-6 text-center">
                          No employee escalation activity found yet.
                        </TableCell>
                      </TableRow>
                    )}
                    {auditLogs.map((log, i) => (
                      <motion.tr
                        key={log.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: i * 0.03 }}
                        className="border-b last:border-0 hover:bg-muted/20 transition-colors"
                      >
                        <TableCell className="text-muted-foreground whitespace-nowrap text-sm">{toAuditTimestamp(log.timestamp)}</TableCell>
                        <TableCell className="font-medium text-sm">{log.employee}</TableCell>
                        <TableCell className="max-w-[200px] truncate text-sm">{log.query}</TableCell>
                        <TableCell className="text-muted-foreground text-xs">{log.action}</TableCell>
                        <TableCell>
                          <Badge variant={log.confidence === "high" ? "default" : "outline"} className="text-xs">
                            {log.confidence === "high" ? (
                              <CheckCircle2 className="h-3 w-3 mr-1 text-emerald-500" />
                            ) : (
                              <AlertTriangle className="h-3 w-3 mr-1 text-amber-500" />
                            )}
                            {log.confidence}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {log.feedback === "up" ? (
                            <ThumbsUp className="h-4 w-4 text-emerald-500" />
                          ) : (
                            <ThumbsDown className="h-4 w-4 text-destructive" />
                          )}
                        </TableCell>
                        <TableCell>
                          <span className={log.resolution === "Instant" ? "text-emerald-600 font-medium text-sm" : log.resolution === "Pending" ? "text-amber-500 text-sm" : "text-sm"}>
                            {log.resolution}
                          </span>
                        </TableCell>
                      </motion.tr>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </main>

      <MyRequestsPanel isOpen={requestsOpen} onClose={() => setRequestsOpen(false)} requests={assignedRequests} />
    </div>
  );
}
