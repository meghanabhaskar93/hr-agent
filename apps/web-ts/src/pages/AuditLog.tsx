import { useState } from "react";
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

// Mock audit log data
const logs = [
  { id: "1", timestamp: "2026-03-03 09:15", employee: "Jordan Lee", query: "Unpaid leave for family care", action: "Escalated to HR", confidence: "low" as const, resolution: "Pending", feedback: "down" as const },
  { id: "2", timestamp: "2026-03-03 08:42", employee: "Sam Patel", query: "Stock options vesting discrepancy", action: "Escalated to HR", confidence: "low" as const, resolution: "Pending", feedback: "down" as const },
  { id: "3", timestamp: "2026-03-02 14:30", employee: "Alex Kim", query: "Internal transfer process", action: "Answered by AI → Reviewed by HR", confidence: "low" as const, resolution: "45 min", feedback: "up" as const },
  { id: "4", timestamp: "2026-03-01 11:20", employee: "Morgan Chen", query: "Tuition reimbursement for MBA", action: "Answered by AI → Approved", confidence: "low" as const, resolution: "30 min", feedback: "up" as const },
  { id: "5", timestamp: "2026-03-01 10:05", employee: "Riley Park", query: "WFH policy details", action: "Answered by AI (auto)", confidence: "high" as const, resolution: "Instant", feedback: "up" as const },
  { id: "6", timestamp: "2026-02-28 16:45", employee: "Casey Liu", query: "PTO balance check", action: "Answered by AI (auto)", confidence: "high" as const, resolution: "Instant", feedback: "up" as const },
  { id: "7", timestamp: "2026-02-28 09:30", employee: "Taylor Singh", query: "Performance review timeline", action: "Answered by AI (auto)", confidence: "high" as const, resolution: "Instant", feedback: "up" as const },
  { id: "8", timestamp: "2026-02-27 15:10", employee: "Sam Patel", query: "Expense report submission help", action: "Answered by AI (auto)", confidence: "high" as const, resolution: "Instant", feedback: "up" as const },
  { id: "9", timestamp: "2026-02-27 11:05", employee: "Jordan Lee", query: "Team headcount planning", action: "Answered by AI → Reviewed by HR", confidence: "low" as const, resolution: "1 hr", feedback: "up" as const },
  { id: "10", timestamp: "2026-02-26 09:20", employee: "Alex Kim", query: "Relocation package inquiry", action: "Escalated to HR", confidence: "low" as const, resolution: "2 hr", feedback: "down" as const },
];

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

export default function AuditLog() {
  const { user } = useAuth();
  const { getAssignedTickets, getAssignedRequests } = useHRTickets();
  const navigate = useNavigate();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [requestsOpen, setRequestsOpen] = useState(false);

  const displayName = user?.email?.split("@")[0] ?? "HR User";
  const assignedTickets = getAssignedTickets(displayName);
  const assignedRequests = getAssignedRequests(displayName);

  return (
    <div className="min-h-screen flex w-full">
      <HRConversationSidebar
        activeConversationId={activeConversation}
        conversations={conversations}
        onSelectConversation={setActiveConversation}
        onNewConversation={() => navigate("/hr-chat")}
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
                    {logs.map((log, i) => (
                      <motion.tr
                        key={log.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: i * 0.03 }}
                        className="border-b last:border-0 hover:bg-muted/20 transition-colors"
                      >
                        <TableCell className="text-muted-foreground whitespace-nowrap text-sm">{log.timestamp}</TableCell>
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