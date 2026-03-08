import { motion } from "framer-motion";
import {
  CalendarDays,
  HeartPulse,
  Wallet,
  Receipt,
  UserPlus,
  Users,
  TrendingUp,
  ShieldAlert,
  HelpCircle,
  ArrowRight,
} from "lucide-react";

const useCases = [
  {
    icon: HelpCircle,
    title: "Policy Q&A",
    description: "Ask about company policies, handbook, and guidelines",
    prompt: "What is our work from home policy?",
    color: "bg-primary/10 text-primary",
  },
  {
    icon: CalendarDays,
    title: "Leave & PTO",
    description: "Check balances, request time off, understand accrual",
    prompt: "How many PTO days do I have left?",
    color: "bg-info/10 text-info",
  },
  {
    icon: HeartPulse,
    title: "Benefits",
    description: "Health insurance, enrollment periods, claims",
    prompt: "When is the next open enrollment period?",
    color: "bg-success/10 text-success",
  },
  {
    icon: Wallet,
    title: "Payroll",
    description: "Pay schedule, tax forms, salary questions",
    prompt: "When is the next pay day?",
    color: "bg-warning/10 text-warning",
  },
  {
    icon: Receipt,
    title: "Expenses",
    description: "Submission process, limits, reimbursement status",
    prompt: "How do I submit an expense report?",
    color: "bg-destructive/10 text-destructive",
  },
  {
    icon: UserPlus,
    title: "Onboarding",
    description: "First-week checklist, IT setup, key contacts",
    prompt: "What should I do in my first week?",
    color: "bg-primary/10 text-primary",
  },
  {
    icon: Users,
    title: "Company Directory",
    description: "Find team members, org structure, contacts",
    prompt: "Who is my skip-level manager?",
    color: "bg-info/10 text-info",
  },
  {
    icon: TrendingUp,
    title: "Performance & Growth",
    description: "Review cycles, promotion process, development",
    prompt: "When is the next performance review cycle?",
    color: "bg-success/10 text-success",
  },
  {
    icon: ShieldAlert,
    title: "Compliance & Ethics",
    description: "Reporting, whistleblower policy, guidelines",
    prompt: "How do I report a compliance concern?",
    color: "bg-warning/10 text-warning",
  },
];

interface DashboardCardsProps {
  onQuickAction: (prompt: string) => void;
}

export default function DashboardCards({ onQuickAction }: DashboardCardsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {useCases.map((uc, i) => (
        <motion.button
          key={uc.title}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.04, duration: 0.35 }}
          onClick={() => onQuickAction(uc.prompt)}
          className="group text-left p-5 rounded-xl bg-card shadow-soft border border-border/60 hover:shadow-card hover:border-primary/20 transition-all duration-200"
        >
          <div className="flex items-start gap-3">
            <div className={`p-2.5 rounded-lg ${uc.color}`}>
              <uc.icon className="h-5 w-5" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-sm mb-1">{uc.title}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {uc.description}
              </p>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-1.5 text-xs text-primary opacity-0 group-hover:opacity-100 transition-opacity">
            <span>Try: "{uc.prompt}"</span>
            <ArrowRight className="h-3 w-3" />
          </div>
        </motion.button>
      ))}
    </div>
  );
}
